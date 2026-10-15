"""Private, bounded field notes. Explicit linking is the only report promotion."""
from languages import language_index
from error_messages import message as backend_message
from copy import deepcopy
from hashlib import sha256
import re

import project_history
import workflows
from resources import local_image
from storage import atomic_write

KINDS = {'note', 'command', 'http', 'image'}
MAX_ITEMS = 500
MAX_TEXT = 128 * 1024


def validate_rows(rows):
    if not isinstance(rows, list) or len(rows) > MAX_ITEMS:
        raise ValueError(backend_message('Bandeja: máximo 500 capturas / Inbox: maximum 500 captures'))
    seen = set()
    for row in rows:
        if not isinstance(row, dict): raise ValueError(backend_message('Captura inválida / Invalid capture'))
        uid = row.get('uid')
        if not isinstance(uid, str) or not workflows.UID.fullmatch(uid) or uid in seen:
            raise ValueError(backend_message('Identificador de captura inválido / Invalid capture ID'))
        seen.add(uid)
        if not isinstance(row.get('kind'), str) or row['kind'] not in KINDS:
            raise ValueError(backend_message('Tipo de captura inválido / Invalid capture type'))
        for key, limit in [('title', 300), ('note', 8000), ('raw_text', MAX_TEXT), ('created', 80), ('linked_at', 80)]:
            if key in row and (not isinstance(row[key], str) or len(row[key].encode('utf-8')) > limit):
                raise ValueError(backend_message('Campo de captura inválido / Invalid capture field: {p0}', p0=key))
        if not row.get('title', '').strip(): raise ValueError(backend_message('Título obligatorio / Title required'))
        if not isinstance(row.get('sha256'), str) or not re.fullmatch('[a-f0-9]{64}', row['sha256']):
            raise ValueError(backend_message('Huella de captura inválida / Invalid capture hash'))
        if row.get('finding_uid') and (not isinstance(row['finding_uid'], str) or not workflows.UID.fullmatch(row['finding_uid'])):
            raise ValueError(backend_message('Vínculo de captura inválido / Invalid capture link'))
        if row['kind'] == 'image':
            for key, prefix in [('src', 'img/'), ('original', 'originals/')]:
                if not workflows.safe_member(row.get(key), prefix): raise ValueError(backend_message('Ruta de captura inválida / Invalid capture path'))


def create(data, directory, body):
    if not isinstance(body, dict) or set(body) - {'kind', 'title', 'note', 'raw_text', 'src'}:
        raise ValueError(backend_message('Campos de captura inválidos / Invalid capture fields'))
    out = deepcopy(data)
    rows = out.setdefault('capture_inbox', [])
    if len(rows) >= MAX_ITEMS: raise ValueError(backend_message('Bandeja llena / Inbox is full (500)'))
    kind = body.get('kind')
    if not isinstance(kind, str) or kind not in KINDS: raise ValueError(backend_message('Tipo de captura inválido / Invalid capture type'))
    item = dict(uid=workflows.new_uid(), kind=kind, title=body.get('title', ''), note=body.get('note', ''),
                raw_text=body.get('raw_text', ''), created=project_history.now())
    if kind == 'image':
        src = body.get('src')
        if not workflows.safe_member(src, 'img/'): raise ValueError(backend_message('Usa una imagen local / Use a local image'))
        image = local_image(src, directory)
        blob = image.read_bytes()
        item.update(src=src, original='originals/' + item['uid'] + image.suffix.lower())
    else:
        if not isinstance(item['raw_text'], str) or not item['raw_text'].strip():
            raise ValueError(backend_message('Contenido obligatorio / Content required'))
        blob = item['raw_text'].encode('utf-8')
    item['sha256'] = sha256(blob).hexdigest()
    rows.append(item)
    validate_rows(rows)
    if kind == 'image': atomic_write(directory / item['original'], blob)
    return out, item


def link(data, directory, uid, finding_uid):
    from engine import report_language
    out = deepcopy(data)
    item = next((x for x in out.get('capture_inbox', []) if x['uid'] == uid), None)
    finding = next((x for x in out.get('findings', []) if x['uid'] == finding_uid), None)
    if not item or not finding: raise ValueError(backend_message('Captura o hallazgo inexistente / Capture or finding not found'))
    if item.get('finding_uid') in {f.get('uid') for f in out.get('findings', [])}: raise ValueError(backend_message('La captura ya está incorporada / Capture already linked'))
    if item['kind'] == 'image':
        original = directory / item['original']
        if original.is_symlink() or not original.resolve().is_relative_to(directory.resolve()):
            raise ValueError(backend_message('Original no permitido / Original not allowed'))
        if sha256(original.read_bytes()).hexdigest() != item['sha256']:
            raise ValueError(backend_message('La captura original cambió / Original capture changed'))
        local_image(item['src'], directory)
        entry = next((x for x in out.get('evidence', []) if x['src'] == item['src']), None)
        if not entry:
            entry = dict(uid=workflows.new_uid(), title=item['title'], caption=item['note'], src=item['src'], original=item['original'])
            out.setdefault('evidence', []).append(entry)
        finding['evidence_uids'] = list(dict.fromkeys([*finding.get('evidence_uids', []), entry['uid']]))
    else:
        if sha256(item['raw_text'].encode('utf-8')).hexdigest() != item['sha256']:
            raise ValueError(backend_message('El contenido original cambió / Original content changed'))
        step = dict(lead=item['title'], capture_uid=uid)
        if item['kind'] == 'note':
            # Plain notes must not acquire Markdown/HTML semantics during promotion.
            step['text_md'] = '\n\n'.join(workflows.md_text(line) for line in (item['note'] + '\n' + item['raw_text']).splitlines())
        else:
            step.update(command=item['raw_text'], text_md='\n\n'.join(workflows.md_text(line) for line in item['note'].splitlines()))
        if finding.get('mode') == 'machine':
            phases = finding.setdefault('phases', [])
            if not phases: phases.append(dict(name=('Capturas', 'Captures', 'Capturas')[language_index(report_language(out))], steps=[]))
            phases[-1].setdefault('steps', []).append(step)
        else: finding.setdefault('walkthrough', []).append(step)
    if item.get('finding_uid'): item['previous_finding_uid'] = item['finding_uid']
    item.update(finding_uid=finding_uid, linked_at=project_history.now())
    return out
