"""Reviewed return of explicitly assigned remediation tasks, without retest authority.

The informational CSV is deliberately not an import format. Return templates use
fixed columns and an explicit text marker so spreadsheet formula neutralisation
is reversible; a stripped marker is rejected rather than guessed.
"""
from copy import deepcopy
import csv
from datetime import date, datetime, timezone
import hashlib
import io
import json
import re
import unicodedata
import zipfile
from html import escape

import workflows
from error_messages import message

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 500
MAX_BATCHES = 20
MAX_BATCH_BYTES = 4 * 1024 * 1024
FORMAT = 'report-gen-remediation-return-1'
FIELDS = ('owner', 'due_date', 'reported_remediation')
HEADERS = ('format', 'project_slug', 'batch_uid', 'finding_uid', *FIELDS)
MAX_EVENTS = 16
HASH = re.compile(r'^[0-9a-f]{64}$')


def _invalid():
    return ValueError(message('Plantilla de retorno inválida. Conserva las columnas, referencias y el apóstrofo inicial de los campos de texto.', en='Invalid return template. Preserve columns, references and the initial apostrophe in text fields.'))


def _values(values):
    if not isinstance(values, dict) or set(values) != set(FIELDS):
        raise _invalid()
    for key, value in values.items():
        maximum = 8000 if key == 'reported_remediation' else 200 if key == 'owner' else 10
        if not isinstance(value, str) or len(value) > maximum:
            raise _invalid()
        if any(unicodedata.category(char).startswith('C') and not (key == 'reported_remediation' and char in '\r\n') for char in value):
            raise ValueError(message('El retorno contiene caracteres de control no permitidos', en='The return contains disallowed control characters'))
    if not values['owner'].strip():
        raise ValueError(message('Cada tarea de retorno necesita un responsable asignado', en='Each return task needs an assigned owner'))
    if values['due_date']:
        try:
            if not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', values['due_date']):
                raise ValueError()
            date.fromisoformat(values['due_date'])
        except ValueError:
            raise ValueError(message('El plazo debe ser una fecha válida AAAA-MM-DD o estar vacío', en='The due date must be a valid YYYY-MM-DD date or empty')) from None
    return values


def validate_batches(data):
    """Validate portable internal provenance on ordinary project saves/imports too."""
    batches = data.get('remediation_exchanges', [])
    if not isinstance(batches, list) or len(batches) > MAX_BATCHES:
        raise _invalid()
    if len(json.dumps(batches, ensure_ascii=False).encode('utf-8')) > MAX_BATCH_BYTES:
        raise _invalid()
    seen = set()
    for batch in batches:
        if (not isinstance(batch, dict) or not {'uid', 'project_slug', 'rows'} <= set(batch)
                or set(batch) - {'uid', 'project_slug', 'rows', 'events', 'events_omitted', 'revoked'}):
            raise _invalid()
        if type(batch.get('revoked', False)) is not bool or type(batch.get('events_omitted', 0)) is not int or not 0 <= batch.get('events_omitted', 0) <= 1_000_000:
            raise _invalid()
        events = batch.get('events', [])
        if not isinstance(events, list) or len(events) > MAX_EVENTS:
            raise _invalid()
        for event in events:
            if (not isinstance(event, dict) or set(event) != {'kind', 'at', 'source_revision', 'sha256', 'count'}
                    or event['kind'] not in ('issued', 'received', 'accepted', 'revoked')
                    or not isinstance(event['at'], str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z', event['at'])
                    or any(not isinstance(event[key], str) or not HASH.fullmatch(event[key]) for key in ('source_revision', 'sha256'))
                    or type(event['count']) is not int or not 0 <= event['count'] <= MAX_ROWS * len(FIELDS)):
                raise _invalid()
            try:
                datetime.strptime(event['at'], '%Y-%m-%dT%H:%M:%SZ')
            except ValueError:
                raise _invalid() from None
        uid, slug, rows = batch['uid'], batch['project_slug'], batch['rows']
        if not isinstance(uid, str) or not workflows.UID.fullmatch(uid) or uid in seen:
            raise _invalid()
        seen.add(uid)
        if not isinstance(slug, str) or not 1 <= len(slug) <= 80 or any(not (char.isalnum() or char in '-_') for char in slug):
            raise _invalid()
        if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_ROWS:
            raise _invalid()
        assigned = set()
        for row in rows:
            if not isinstance(row, dict) or set(row) != {'finding_uid', 'base'}:
                raise _invalid()
            ref = row['finding_uid']
            if not isinstance(ref, str) or not workflows.UID.fullmatch(ref) or ref in assigned:
                raise _invalid()
            assigned.add(ref)
            _values(row['base'])


def issue(data, slug, finding_uids, *, source_revision=None):
    if (not isinstance(finding_uids, list) or not 1 <= len(finding_uids) <= MAX_ROWS
            or any(not isinstance(uid, str) or not workflows.UID.fullmatch(uid) for uid in finding_uids)
            or len(set(finding_uids)) != len(finding_uids)):
        raise ValueError(message('Selecciona entre 1 y 500 referencias de hallazgo únicas', en='Select between 1 and 500 unique finding references'))
    validate_batches(data)
    findings = {finding['uid']: finding for finding in data.get('findings', [])}
    if any(uid not in findings for uid in finding_uids):
        raise ValueError(message('La selección contiene un hallazgo inexistente', en='The selection contains a missing finding'))
    batch = {'uid': workflows.new_uid(), 'project_slug': slug, 'rows': [
        {'finding_uid': uid, 'base': _values({key: findings[uid].get(key, '') for key in FIELDS})}
        for uid in finding_uids]}
    result = deepcopy(data)
    # Deliberate issuance is a saved project change. Preview never adds a batch.
    blob = template(batch)
    if source_revision is not None:
        _event(batch, 'issued', source_revision, hashlib.sha256(blob).hexdigest(), len(batch['rows']))
    kept = [*data.get('remediation_exchanges', []), batch][-MAX_BATCHES:]
    while len(kept) > 1 and len(json.dumps(kept, ensure_ascii=False).encode('utf-8')) > MAX_BATCH_BYTES:
        kept.pop(0)
    result['remediation_exchanges'] = kept
    validate_batches(result)
    return result, blob


def template(batch):
    output = io.StringIO(newline='')
    writer = csv.writer(output, quoting=csv.QUOTE_ALL, lineterminator='\r\n')
    writer.writerow(HEADERS)
    for row in batch['rows']:
        values = row['base']
        # ALWAYS prefix text, including an existing apostrophe. This makes the
        # transformation injective; import removes exactly one required marker.
        writer.writerow((FORMAT, "'" + batch['project_slug'], batch['uid'], row['finding_uid'],
                         "'" + values['owner'], values['due_date'], "'" + values['reported_remediation']))
    blob = b'\xef\xbb\xbf' + output.getvalue().encode('utf-8')
    if len(blob) > MAX_BYTES:
        raise ValueError(message('La plantilla supera 2 MiB; selecciona menos hallazgos', en='The template exceeds 2 MiB; select fewer findings'))
    return blob


def plan(data, slug, text):
    if not isinstance(text, str) or not text or len(text) > MAX_BYTES:
        raise ValueError(message('El retorno debe ser un CSV UTF-8 de hasta 2 MiB', en='The return must be a UTF-8 CSV of at most 2 MiB'))
    try:
        blob = text.encode('utf-8', errors='strict')
    except UnicodeError:
        raise _invalid() from None
    if len(blob) > MAX_BYTES:
        raise ValueError(message('El retorno debe ser un CSV UTF-8 de hasta 2 MiB', en='The return must be a UTF-8 CSV of at most 2 MiB'))
    validate_batches(data)
    batches = {batch['uid']: batch for batch in data.get('remediation_exchanges', [])}
    findings = {finding['uid']: finding for finding in data.get('findings', [])}
    changes, seen, selected_batch = [], set(), None
    try:
        reader = csv.reader(io.StringIO(text.removeprefix('\ufeff'), newline=''), strict=True)
        if next(reader, None) != list(HEADERS):
            raise _invalid()
        for index, cells in enumerate(reader):
            if index >= MAX_ROWS or len(cells) != len(HEADERS):
                raise _invalid()
            row = dict(zip(HEADERS, cells))
            if row['format'] != FORMAT or row['project_slug'] != "'" + slug:
                raise ValueError(message('El CSV pertenece a otro proyecto o formato', en='The CSV belongs to another project or format'))
            batch = batches.get(row['batch_uid'])
            if batch is None or batch.get('revoked') or batch['project_slug'] != slug or (selected_batch and selected_batch != batch['uid']):
                raise ValueError(message('El lote no fue emitido por este proyecto, ya caducó o se revocó. No mezcles lotes.', en='This batch was not issued by this project, has expired or was revoked. Do not mix batches.'))
            selected_batch = batch['uid']
            assigned = {item['finding_uid']: item['base'] for item in batch['rows']}
            uid = row['finding_uid']
            if uid not in assigned or uid not in findings or uid in seen:
                raise ValueError(message('El retorno contiene referencias duplicadas, eliminadas o no asignadas a este lote', en='The return contains duplicate, deleted or unassigned references'))
            seen.add(uid)
            if not row['owner'].startswith("'") or not row['reported_remediation'].startswith("'"):
                raise _invalid()
            proposed = _values({'owner': row['owner'][1:], 'due_date': row['due_date'],
                                'reported_remediation': row['reported_remediation'][1:]})
            finding, base = findings[uid], assigned[uid]
            for key in FIELDS:
                current = finding.get(key, '')
                if proposed[key] != current:
                    changes.append({'key': uid + ':' + key, 'finding_uid': uid, 'finding_id': finding.get('id', ''),
                                    'field': key, 'before': current, 'after': proposed[key], 'issued': base[key],
                                    'changed_since_issue': current != base[key]})
    except (csv.Error, UnicodeError):
        raise _invalid() from None
    if not seen:
        raise _invalid()
    return {'batch_uid': selected_batch, 'file_sha256': hashlib.sha256(blob).hexdigest(),
            'rows': len(seen), 'changes': changes}


def apply(data, proposal, selected):
    if (not isinstance(selected, list) or not selected or len(selected) > MAX_ROWS * len(FIELDS)
            or any(not isinstance(key, str) for key in selected) or len(set(selected)) != len(selected)):
        raise ValueError(message('Selecciona explícitamente al menos un cambio de la vista previa', en='Explicitly select at least one previewed change'))
    changes = {change['key']: change for change in proposal['changes']}
    if any(key not in changes for key in selected):
        raise ValueError(message('La selección no coincide con los cambios previsualizados', en='The selection does not match the previewed changes'))
    result = deepcopy(data)
    findings = {finding['uid']: finding for finding in result['findings']}
    for key in selected:
        change = changes[key]
        # FIELDS is a fixed server-owned allowlist; status, verification, evidence
        # and retests are NEVER writable through this endpoint.
        if change['field'] not in FIELDS:
            raise _invalid()
        findings[change['finding_uid']][change['field']] = change['after']
    return result


def _event(batch, kind, source_revision, sha256, count):
    """A bounded local log, not proof of delivery or a tamper-proof audit trail."""
    event = {'kind': kind, 'at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
             'source_revision': source_revision, 'sha256': sha256, 'count': count}
    events = [*batch.get('events', []), event]
    batch['events_omitted'] = min(1_000_000, batch.get('events_omitted', 0) + max(0, len(events) - MAX_EVENTS))
    batch['events'] = events[-MAX_EVENTS:]


def record(data, proposal, source_revision, *, selected=None):
    """Record explicit reception or acceptance; comparison itself stays read-only."""
    result = deepcopy(data)
    batch = next((b for b in result.get('remediation_exchanges', []) if b['uid'] == proposal['batch_uid']), None)
    if batch is None or batch.get('revoked'):
        raise _invalid()
    # Re-reading a previously registered file does not imply a second receipt.
    if not any(e['kind'] == 'received' and e['sha256'] == proposal['file_sha256'] for e in batch.get('events', [])):
        _event(batch, 'received', source_revision, proposal['file_sha256'], proposal['rows'])
    if selected is not None:
        changes = {change['key']: change for change in proposal['changes']}
        digest = hashlib.sha256(json.dumps([changes[key] for key in sorted(selected)],
                                          sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()
        _event(batch, 'accepted', source_revision, digest, len(selected))
    validate_batches(result)
    return result


def revoke(data, batch_uid, source_revision):
    result = deepcopy(data)
    validate_batches(result)
    batch = next((b for b in result.get('remediation_exchanges', []) if b['uid'] == batch_uid), None)
    if batch is None:
        raise _invalid()
    if not batch.get('revoked'):
        batch['revoked'] = True
        _event(batch, 'revoked', source_revision, hashlib.sha256(batch_uid.encode()).hexdigest(), 0)
    validate_batches(result)
    return result


def delivery_preview(data, slug, finding_uids, fields, lang):
    """Preview exactly the selected card fields plus every return-template value."""
    import remediation_tasks as tasks
    # Validate selection and return values without persisting this temporary batch.
    issued, _ = issue(data, slug, finding_uids)
    batch = issued['remediation_exchanges'][-1]
    selected = set(finding_uids)
    task_rows = {row['finding_uid']: row for row in tasks.rows(data, fields, lang) if row['finding_uid'] in selected}
    return [{'card': task_rows[row['finding_uid']], 'return_values': row['base']} for row in batch['rows']]


def delivery(data, slug, finding_uids, fields, lang, source_revision):
    """Build cards and editable CSV from one locked revision, with no external send."""
    import remediation_tasks as tasks
    updated, _ = issue(data, slug, finding_uids)
    batch = updated['remediation_exchanges'][-1]
    preview = delivery_preview(data, slug, finding_uids, fields, lang)
    cards = {row['card']['finding_uid']: row['card'] for row in preview}
    groups = {}
    for row in batch['rows']:
        groups.setdefault(row['base']['owner'], []).append(row)
    instructions = ('Este ZIP y manifest.json reúnen todos los responsables seleccionados. No los envíes completos a un solo responsable. '
                    'Extrae y comparte únicamente su carpeta owner-NNN, tras revisar index.html, las fichas y return.csv. '
                    'El registro acredita solo generación local, no envío ni recepción por terceros.\n' if lang == 'es' else
                    'This ZIP and manifest.json combine all selected owners. Do not send them in full to a single owner. '
                    'Extract and share only their owner-NNN folder, after reviewing index.html, the cards and return.csv. '
                    'The record describes local generation only, not external delivery or receipt.\n')
    files, owners = {'INSTRUCTIONS.txt': instructions.encode()}, []
    for index, (owner, rows) in enumerate(groups.items(), 1):
        prefix = f'owner-{index:03d}/'
        files[prefix + 'return.csv'] = template({**batch, 'rows': rows})
        links = []
        for row in rows:
            name = 'task-' + row['finding_uid'] + '.html'
            files[prefix + name] = tasks.card_html(cards[row['finding_uid']], fields, lang)
            links.append('<li><a href="' + name + '">' + escape(cards[row['finding_uid']]['id']) + '</a></li>')
        heading = 'Entrega de tareas' if lang == 'es' else 'Task delivery'
        note = ('Contenido seleccionado para este responsable. Edita solo owner, due_date y reported_remediation en return.csv. '
                'Conserva referencias y el apóstrofo inicial de los campos de texto. Guarda CSV UTF-8 con comas. '
                'Los avances comunicados no acreditan una corrección verificada.' if lang == 'es' else
                'Selected content for this owner. Edit only owner, due_date and reported_remediation in return.csv. '
                'Preserve references and the initial apostrophe in text fields. Save comma-separated UTF-8 CSV. '
                'Reported progress does not prove a verified fix.')
        files[prefix + 'index.html'] = ('<!doctype html><html lang="' + lang + '"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src &#39;none&#39;; style-src &#39;unsafe-inline&#39;; base-uri &#39;none&#39;; form-action &#39;none&#39;">'
            '<title>' + heading + '</title><style>body{font:16px/1.6 system-ui;max-width:54rem;margin:2rem auto;padding:0 1rem;'
            'overflow-wrap:anywhere;color:#17212c;background:white}a{color:#004a9f}li{margin:.6rem 0}</style></head><body><main><h1>'
            + heading + '</h1><p>' + escape(owner) + '</p><p>' + note + '</p><ul>' + ''.join(links)
            + '<li><a href="return.csv">CSV</a></li></ul></main></body></html>').encode()
        owners.append({'folder': prefix, 'owner': owner, 'finding_uids': [row['finding_uid'] for row in rows]})
    manifest = {'format': 'report-gen-owner-delivery-1', 'project_slug': slug, 'batch_uid': batch['uid'],
                'source_revision': source_revision, 'fields': fields, 'lang': lang, 'owners': owners,
                'files': {name: hashlib.sha256(blob).hexdigest() for name, blob in files.items()}}
    files['manifest.json'] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, blob in files.items():
            info = zipfile.ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, blob)
    blob = output.getvalue()
    _event(batch, 'issued', source_revision, hashlib.sha256(blob).hexdigest(), len(batch['rows']))
    validate_batches(updated)
    return updated, blob
