"""Bounded HTTP evidence. Private originals and reviewed publication are separate.

No function in this module performs network requests. Imported URLs are evidence,
never destinations. Hashes prove consistency, not authenticity of supplied data.
"""
from copy import deepcopy
from hashlib import sha256
from urllib.parse import urlsplit
import base64
import binascii
import difflib
import json
import re

from error_messages import current_language
from languages import language_index
import project_history
import workflows

MAX_ITEMS = 500
MAX_IMPORT = 100
MAX_IMPORT_BYTES = 4 * 1024 * 1024
MAX_BODY = 256 * 1024
MAX_TOTAL = 8 * 1024 * 1024
MAX_HEADERS = 200
TOKEN = re.compile(r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$")


def fail(es, en, pt):
    # Preserve complete authored prose, including braces in opaque field names.
    raise ValueError((es, en, pt)[language_index(current_language())])


def text(value, limit, field, required=False):
    if (not isinstance(value, str) or len(value.encode('utf-8')) > limit
            or '\x00' in value or required and not value.strip()):
        fail('HTTP: texto inválido en ' + field, 'HTTP: invalid text in ' + field,
             'HTTP: texto inválido em ' + field)
    return value


def digest(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(',', ':')).encode('utf-8')).hexdigest()


def headers(value):
    if not isinstance(value, list) or len(value) > MAX_HEADERS:
        fail('HTTP: máximo 200 cabeceras', 'HTTP: maximum 200 headers', 'HTTP: máximo de 200 cabeçalhos')
    out = []
    for row in value:
        if not isinstance(row, dict) or set(row) != {'name', 'value'}:
            fail('HTTP: cabecera inválida', 'HTTP: invalid header', 'HTTP: cabeçalho inválido')
        name = text(row['name'], 300, 'header.name', True)
        val = text(row['value'], 16000, 'header.value')
        if not TOKEN.fullmatch(name) or '\r' in val or '\n' in val:
            fail('HTTP: cabecera inválida', 'HTTP: invalid header', 'HTTP: cabeçalho inválido')
        out.append(dict(name=name, value=val))
    return out


def http_message(value, request=False):
    keys = {'http_version', 'headers', 'body', 'body_encoding'} | ({'method', 'url'} if request else {'status'})
    if not isinstance(value, dict) or set(value) - keys:
        fail('HTTP: mensaje inválido', 'HTTP: invalid message', 'HTTP: mensagem inválida')
    out = dict(http_version=text(value.get('http_version', 'HTTP/1.1'), 20, 'http_version'),
               headers=headers(value.get('headers', [])),
               body=text(value.get('body', ''), MAX_BODY * 4 // 3 + 4, 'body'),
               body_encoding=value.get('body_encoding', 'utf-8'))
    if out['body_encoding'] not in ('utf-8', 'base64'):
        fail('HTTP: codificación inválida', 'HTTP: invalid encoding', 'HTTP: codificação inválida')
    if out['body_encoding'] == 'base64':
        try:
            raw = base64.b64decode(out['body'], validate=True)
        except (ValueError, binascii.Error):
            fail('HTTP: base64 inválido', 'HTTP: invalid base64', 'HTTP: base64 inválido')
        if base64.b64encode(raw).decode('ascii') != out['body']:
            fail('HTTP: base64 no canónico', 'HTTP: noncanonical base64', 'HTTP: base64 não canônico')
    else:
        raw = out['body'].encode('utf-8')
    if len(raw) > MAX_BODY:
        fail('HTTP: cuerpo superior a 256 KiB', 'HTTP: body exceeds 256 KiB', 'HTTP: corpo acima de 256 KiB')
    if '\r' in out['http_version'] or '\n' in out['http_version']:
        fail('HTTP: versión inválida', 'HTTP: invalid version', 'HTTP: versão inválida')
    if request:
        out['method'] = text(value.get('method'), 40, 'method', True)
        out['url'] = text(value.get('url'), 16000, 'url', True)
        try:
            url = urlsplit(out['url'])
            valid = url.scheme in ('http', 'https') and bool(url.hostname) and not any(c.isspace() for c in out['url'])
            url.port
        except ValueError:
            valid = False
        if not TOKEN.fullmatch(out['method']) or not valid:
            fail('HTTP: método o URL inválidos', 'HTTP: invalid method or URL', 'HTTP: método ou URL inválidos')
    else:
        status = value.get('status')
        if type(status) is not int or not 100 <= status <= 599:
            fail('HTTP: estado inválido', 'HTTP: invalid status', 'HTTP: status inválido')
        out['status'] = status
    return out


def original(value):
    if not isinstance(value, dict) or set(value) - {'request', 'response', 'captured_at', 'identity', 'source'}:
        fail('HTTP: original inválido', 'HTTP: invalid original', 'HTTP: original inválido')
    return dict(request=http_message(value.get('request'), True),
                response=http_message(value['response']) if value.get('response') is not None else None,
                captured_at=text(value.get('captured_at', ''), 100, 'captured_at'),
                identity=text(value.get('identity', ''), 500, 'identity'),
                source=text(value.get('source', 'manual'), 1000, 'source'))


def refs(value, pool, field):
    if (not isinstance(value, list) or len(value) > 500
            or any(not isinstance(uid, str) or uid not in pool for uid in value)
            or len(set(value)) != len(value)):
        fail('HTTP: vínculo inexistente en ' + field, 'HTTP: unknown link in ' + field,
             'HTTP: vínculo inexistente em ' + field)
    return list(value)


def publication(value, original_hash):
    if value is None:
        return None
    keys = {'request_text', 'response_text', 'caption', 'reviewed_sha256', 'reviewed_at', 'audiences'}
    if not isinstance(value, dict) or set(value) != keys:
        fail('HTTP: copia publicable inválida', 'HTTP: invalid publication copy', 'HTTP: cópia publicável inválida')
    out = {key: text(value[key], MAX_BODY if key.endswith('_text') else 8000, key)
           for key in ('request_text', 'response_text', 'caption')}
    out['reviewed_at'] = text(value['reviewed_at'], 100, 'reviewed_at', True)
    out['audiences'] = value['audiences']
    out['reviewed_sha256'] = value['reviewed_sha256']
    # The public/executive flows have separate, explicit authored prose consent.
    if out['audiences'] != ['technical'] or not out['request_text'].strip():
        fail('HTTP: revisa una copia técnica explícita', 'HTTP: review an explicit technical copy',
             'HTTP: revise uma cópia técnica explícita')
    if out['reviewed_sha256'] != digest(dict(original_sha256=original_hash,
            request_text=out['request_text'], response_text=out['response_text'], caption=out['caption'])):
        fail('HTTP: la copia cambió después de revisarla', 'HTTP: publication copy changed after review',
             'HTTP: a cópia mudou após a revisão')
    return out


def _reference_pool(data, key):
    """Ignore malformed parent containers; central validation reports them.

    An HTTP reference to any ignored parent still fails through ``refs``.
    This optional module must not turn a core schema error into a TypeError.
    """
    rows = data.get(key, [])
    return {row['uid'] for row in rows
            if isinstance(row, dict) and isinstance(row.get('uid'), str)} if isinstance(rows, list) else set()


def validate_rows(data):
    rows = data.get('http_evidence', [])
    if not isinstance(rows, list) or len(rows) > MAX_ITEMS:
        fail('HTTP: máximo 500 evidencias', 'HTTP: maximum 500 evidence pairs', 'HTTP: máximo de 500 evidências')
    seen = set()
    finding_pool = _reference_pool(data, 'findings')
    asset_pool = _reference_pool(data, 'assets')
    for row in rows:
        keys = {'uid', 'title', 'notes', 'created', 'original', 'sha256', 'finding_uids', 'asset_uids', 'publication'}
        if not isinstance(row, dict) or set(row) != keys:
            fail('HTTP: registro inválido', 'HTTP: invalid record', 'HTTP: registro inválido')
        uid = row['uid']
        if not isinstance(uid, str) or not workflows.UID.fullmatch(uid) or uid in seen:
            fail('HTTP: identificador inválido', 'HTTP: invalid identity', 'HTTP: identificador inválido')
        seen.add(uid)
        text(row['title'], 500, 'title', True)
        text(row['notes'], 16000, 'notes')
        text(row['created'], 100, 'created', True)
        normal = original(row['original'])
        if normal != row['original'] or digest(normal) != row['sha256']:
            fail('HTTP: el original cambió', 'HTTP: original changed', 'HTTP: o original mudou')
        refs(row['finding_uids'], finding_pool, 'finding_uids')
        refs(row['asset_uids'], asset_pool, 'asset_uids')
        publication(row['publication'], row['sha256'])
    if len(json.dumps(rows, ensure_ascii=False).encode('utf-8')) > MAX_TOTAL:
        fail('HTTP: presupuesto total de 8 MiB excedido', 'HTTP: total 8 MiB budget exceeded',
             'HTTP: orçamento total de 8 MiB excedido')
    projection_refs = data.get('http_evidence_refs', [])
    if not isinstance(projection_refs, list) or len(projection_refs) > MAX_ITEMS:
        fail('HTTP: referencias publicadas inválidas', 'HTTP: invalid publication references', 'HTTP: referências publicadas inválidas')
    for ref in projection_refs:
        if (not isinstance(ref, dict) or set(ref) != {'uid', 'sha256', 'published'}
                or not isinstance(ref['uid'], str) or not workflows.UID.fullmatch(ref['uid']) or ref['uid'] in seen
                or not isinstance(ref['sha256'], str) or not re.fullmatch('[a-f0-9]{64}', ref['sha256'])
                or type(ref['published']) is not bool):
            fail('HTTP: referencia publicada inválida', 'HTTP: invalid publication reference', 'HTTP: referência publicada inválida')
        seen.add(ref['uid'])


def structure_errors(data):
    try:
        validate_rows(data)
        return []
    except ValueError as exc:
        return [('error', 'http_evidence: ' + str(exc))]


def add(data, records, finding_uids=(), asset_uids=()):
    if not isinstance(records, list) or not records or len(records) > MAX_IMPORT:
        fail('HTTP: selecciona entre 1 y 100 mensajes', 'HTTP: select between 1 and 100 messages',
             'HTTP: selecione entre 1 e 100 mensagens')
    if len(json.dumps(records, ensure_ascii=False).encode('utf-8')) > MAX_IMPORT_BYTES:
        fail('HTTP: importación superior a 4 MiB', 'HTTP: import exceeds 4 MiB', 'HTTP: importação acima de 4 MiB')
    finding_uids = refs(list(finding_uids) if isinstance(finding_uids, tuple) else finding_uids,
                        _reference_pool(data, 'findings'), 'finding_uids')
    asset_uids = refs(list(asset_uids) if isinstance(asset_uids, tuple) else asset_uids,
                     _reference_pool(data, 'assets'), 'asset_uids')
    out = deepcopy(data)
    rows = out.setdefault('http_evidence', [])
    added = []
    for record in records:
        if not isinstance(record, dict) or set(record) - {'title', 'notes', 'original'}:
            fail('HTTP: captura inválida', 'HTTP: invalid capture', 'HTTP: captura inválida')
        value = original(record.get('original'))
        # Only the generated display label is shortened. The evidence URL stays
        # exact, and the limit is bytes (not characters), as in validate_rows.
        default_title = (value['request']['method'] + ' ' + value['request']['url']).encode('utf-8')[:500].decode('utf-8', errors='ignore')
        row = dict(uid=workflows.new_uid(), title=record.get('title') or default_title,
                   notes=record.get('notes', ''), created=project_history.now(), original=value, sha256=digest(value),
                   finding_uids=list(finding_uids), asset_uids=list(asset_uids), publication=None)
        rows.append(row)
        added.append(row['uid'])
    validate_rows(out)
    return out, added


def update(data, uid, body):
    if not isinstance(body, dict) or set(body) - {'title', 'notes', 'finding_uids', 'asset_uids', 'publication', 'ack_reviewed'}:
        fail('HTTP: campos de edición inválidos', 'HTTP: invalid edit fields', 'HTTP: campos de edição inválidos')
    out = deepcopy(data)
    row = next((row for row in out.get('http_evidence', []) if row['uid'] == uid), None)
    if row is None:
        fail('HTTP: evidencia inexistente', 'HTTP: evidence not found', 'HTTP: evidência inexistente')
    for key in ('title', 'notes', 'finding_uids', 'asset_uids'):
        if key in body:
            row[key] = deepcopy(body[key])
    if 'publication' in body:
        value = body['publication']
        if value is None:
            row['publication'] = None
        else:
            if not isinstance(value, dict) or set(value) != {'request_text', 'response_text', 'caption'} or body.get('ack_reviewed') is not True:
                fail('HTTP: confirma la revisión de la copia publicable', 'HTTP: confirm review of the publication copy',
                     'HTTP: confirme a revisão da cópia publicável')
            row['publication'] = dict(value, audiences=['technical'], reviewed_at=project_history.now(),
                reviewed_sha256=digest(dict(original_sha256=row['sha256'], **value)))
    validate_rows(out)
    return out


def from_har(payload, indices=None):
    if not isinstance(payload, dict) or not isinstance(payload.get('log'), dict):
        fail('HAR inválido', 'Invalid HAR', 'HAR inválido')
    entries = payload['log'].get('entries')
    if not isinstance(entries, list) or len(entries) > MAX_IMPORT:
        fail('HAR: máximo 100 entradas por archivo', 'HAR: maximum 100 entries per file', 'HAR: máximo de 100 entradas por arquivo')
    if len(json.dumps(payload, ensure_ascii=False).encode('utf-8')) > MAX_IMPORT_BYTES:
        fail('HAR: archivo superior a 4 MiB', 'HAR: file exceeds 4 MiB', 'HAR: arquivo acima de 4 MiB')
    if indices is None:
        indices = list(range(len(entries)))
    if (not isinstance(indices, list) or not indices or any(type(i) is not int or not 0 <= i < len(entries) for i in indices)
            or len(set(indices)) != len(indices)):
        fail('HAR: selección inválida', 'HAR: invalid selection', 'HAR: seleção inválida')
    result = []
    for index in indices:
        entry = entries[index]
        if not isinstance(entry, dict) or not isinstance(entry.get('request'), dict) or not isinstance(entry.get('response'), dict):
            fail('HAR: entrada inválida', 'HAR: invalid entry', 'HAR: entrada inválida')
        req, res = entry['request'], entry['response']
        if not isinstance(req.get('headers', []), list) or not isinstance(res.get('headers', []), list):
            fail('HAR: cabeceras inválidas', 'HAR: invalid headers', 'HAR: cabeçalhos inválidos')
        post = req.get('postData', {})
        content = res.get('content', {})
        if not isinstance(post, dict) or not isinstance(content, dict):
            fail('HAR: cuerpo inválido', 'HAR: invalid body', 'HAR: corpo inválido')
        # Multipart/form data without the captured wire body cannot be recreated
        # faithfully from params: make that absence explicit, never invent it.
        notes = ''
        if post and 'text' not in post:
            notes = 'HAR: request body text was not captured; parameters were not reconstructed.'
        if content.get('encoding', '') not in ('', 'base64'):
            fail('HAR: codificación no admitida', 'HAR: unsupported encoding', 'HAR: codificação não suportada')
        status = res.get('status')
        if type(status) is not int:
            fail('HAR: estado inválido', 'HAR: invalid status', 'HAR: status inválido')
        response = None if status == 0 else dict(status=status, http_version=res.get('httpVersion', 'HTTP/1.1'),
            headers=[dict(name=h.get('name'), value=h.get('value')) if isinstance(h, dict) else h for h in res.get('headers', [])],
            body=content.get('text', ''), body_encoding='base64' if content.get('encoding') == 'base64' else 'utf-8')
        record = dict(notes=notes, original=dict(captured_at=entry.get('startedDateTime', ''), identity='', source='HAR',
            request=dict(method=req.get('method'), url=req.get('url'), http_version=req.get('httpVersion', 'HTTP/1.1'),
                headers=[dict(name=h.get('name'), value=h.get('value')) if isinstance(h, dict) else h for h in req.get('headers', [])],
                body=post.get('text', ''), body_encoding='utf-8'), response=response))
        record['original'] = original(record['original'])
        result.append(record)
    return result


def wire_text(msg, request=False):
    if msg is None:
        return ''
    first = (msg['method'] + ' ' + msg['url'] + ' ' + msg['http_version']) if request else (msg['http_version'] + ' ' + str(msg['status']))
    body = msg['body']
    if msg['body_encoding'] == 'base64':
        raw = base64.b64decode(body, validate=True)
        try:
            body = raw.decode('utf-8')
            if any(ord(c) < 32 and c not in '\n\r\t' for c in body):
                raise UnicodeError()
        except UnicodeError:
            body = '[binary body; base64]\n' + msg['body']
    return first + '\n' + '\n'.join(h['name'] + ': ' + h['value'] for h in msg['headers']) + '\n\n' + body


def comparison(data, left_uid, right_uid):
    pool = {r['uid']: r for r in data.get('http_evidence', [])}
    if left_uid not in pool or right_uid not in pool or left_uid == right_uid:
        fail('HTTP: selecciona dos evidencias diferentes', 'HTTP: select two different evidence pairs',
             'HTTP: selecione duas evidências diferentes')
    result = dict(left=left_uid, right=right_uid, left_identity=pool[left_uid]['original']['identity'],
                  right_identity=pool[right_uid]['original']['identity'])
    for key in ('request', 'response'):
        a = wire_text(pool[left_uid]['original'][key], key == 'request')
        b = wire_text(pool[right_uid]['original'][key], key == 'request')
        # Bound line-level work. Long one-line bodies remain visible in editors.
        if len(a) + len(b) > 128 * 1024 or a.count('\n') + b.count('\n') > 4000:
            result[key] = dict(equal=a == b, diff='', truncated=True)
        else:
            diff = '\n'.join(difflib.unified_diff(a.splitlines(), b.splitlines(), fromfile='A', tofile='B', lineterm=''))
            result[key] = dict(equal=a == b, diff=diff, truncated=False)
    return result


def project_for_export(source, audience='technical'):
    """Consume HTTP once before normal publication redactions and rendering."""
    data = deepcopy(source)
    rows = data.pop('http_evidence', [])
    if not isinstance(rows, list) or len(rows) > MAX_ITEMS:
        fail('HTTP: evidencias de publicación inválidas', 'HTTP: invalid publication evidence', 'HTTP: evidências de publicação inválidas')
    seen = set()
    for row in rows:
        # Audience selection may have removed linked findings, so source-link
        # existence is not revalidated here. Shapes and copy binding still are.
        if (not isinstance(row, dict) or not isinstance(row.get('uid'), str)
                or not workflows.UID.fullmatch(row['uid']) or row['uid'] in seen
                or not isinstance(row.get('sha256'), str) or not re.fullmatch('[a-f0-9]{64}', row['sha256'])
                or not isinstance(row.get('finding_uids'), list)
                or any(not isinstance(uid, str) or not workflows.UID.fullmatch(uid) for uid in row['finding_uids'])):
            fail('HTTP: referencia de publicación inválida', 'HTTP: invalid publication reference', 'HTTP: referência de publicação inválida')
        seen.add(row['uid'])
        publication(row.get('publication'), row['sha256'])
    if audience != 'technical':
        data.pop('http_evidence_refs', None)
        return data
    from engine import report_language
    from languages import language_index
    labels = (('Petición HTTP', 'Respuesta HTTP'), ('HTTP request', 'HTTP response'),
              ('Requisição HTTP', 'Resposta HTTP'))[language_index(report_language(source))]
    # Section-only technical derivatives can retain finding data without
    # rendering finding bodies. A reference is published only when its copy is
    # actually included in that report, including the legacy full-report mode.
    from sections import catalog_by_key
    sections = (data.get('report') or {}).get('sections') or []
    catalog = catalog_by_key()
    findings_visible = not sections or any(catalog.get(section.get('key'), {}).get('special') == 'findings'
                                          for section in sections)
    included = {finding.get('uid') for finding in data.get('findings', [])} if findings_visible else set()
    if rows:
        data['http_evidence_refs'] = [dict(uid=row['uid'], sha256=row['sha256'],
            published=bool(row.get('publication') and included.intersection(row['finding_uids']))) for row in rows]
    elif not findings_visible:
        for reference in data.get('http_evidence_refs', []):
            reference['published'] = False
    for row in rows:
        pub = row.get('publication')
        if not pub:
            continue
        for finding in data.get('findings', []):
            if finding.get('uid') not in included or finding.get('uid') not in row['finding_uids']:
                continue
            steps = []
            for label, key in ((labels[0], 'request_text'), (labels[1], 'response_text')):
                if pub[key]:
                    steps.append(dict(lead=label + ' · ' + row['uid'], command=pub[key],
                        text_md='\n\n'.join(workflows.md_text(line) for line in pub['caption'].splitlines()) if key == 'request_text' else ''))
            if finding.get('mode') == 'machine':
                finding.setdefault('phases', []).append(dict(name='HTTP', steps=steps))
            else:
                finding.setdefault('walkthrough', []).extend(steps)
    return data


def assert_originals_unchanged(before, after):
    """Protect stable captures in normal whole-project editor saves.

    Restores/imports remain explicit history operations and do not use this hook.
    """
    old = {row['uid']: row for row in before.get('http_evidence', [])}
    for row in after.get('http_evidence', []):
        previous = old.get(row.get('uid'))
        if previous and (row.get('original') != previous['original'] or row.get('sha256') != previous['sha256']):
            fail('HTTP: el original es inmutable; captura otra evidencia',
                 'HTTP: original is immutable; capture another evidence pair',
                 'HTTP: o original é imutável; capture outra evidência')
