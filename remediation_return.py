"""Reviewed return of explicitly assigned remediation tasks, without retest authority.

The informational CSV is deliberately not an import format. Return templates use
fixed columns and an explicit text marker so spreadsheet formula neutralisation
is reversible; a stripped marker is rejected rather than guessed.
"""
from copy import deepcopy
import csv
from datetime import date
import hashlib
import io
import json
import re
import unicodedata

import workflows
from error_messages import message

MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 500
MAX_BATCHES = 20
MAX_BATCH_BYTES = 4 * 1024 * 1024
FORMAT = 'report-gen-remediation-return-1'
FIELDS = ('owner', 'due_date', 'reported_remediation')
HEADERS = ('format', 'project_slug', 'batch_uid', 'finding_uid', *FIELDS)
LABELS = {'owner': ('Responsable', 'Owner'), 'due_date': ('Plazo', 'Due date'),
          'reported_remediation': ('Corrección comunicada (sin verificar)', 'Reported remediation (unverified)')}


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
        if not isinstance(batch, dict) or set(batch) != {'uid', 'project_slug', 'rows'}:
            raise _invalid()
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


def issue(data, slug, finding_uids):
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
    kept = [*data.get('remediation_exchanges', []), batch][-MAX_BATCHES:]
    while len(json.dumps(kept, ensure_ascii=False).encode('utf-8')) > MAX_BATCH_BYTES:
        kept.pop(0)
    result['remediation_exchanges'] = kept
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
            if batch is None or batch['project_slug'] != slug or (selected_batch and selected_batch != batch['uid']):
                raise ValueError(message('El lote no fue emitido por este proyecto o ya caducó. No mezcles lotes.', en='This batch was not issued by this project or has expired. Do not mix batches.'))
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
