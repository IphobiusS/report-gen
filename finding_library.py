"""Versioned local templates. Project-specific evidence and tracking never travel."""
from error_messages import message as backend_message
from copy import deepcopy
import json
import re
from storage import atomic_write
from project_history import now, dumps
from workflows import new_uid
from input_guard import load_json, load_json_file

VARIABLE = re.compile(r'\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}')
TECHNICAL = {'mode', 'title', 'severity', 'cvss', 'cvss_vector', 'cvss_version', 'cwe',
             'description_md', 'impact_md', 'remediation_md', 'remediation_summary',
             'references', 'walkthrough', 'summary_md', 'phases'}


def sanitize(finding, context=None):
    """Remove structured client data; free prose still requires human review."""
    from reusable_markup import sanitize_markdown, private_reference
    from resources import markdown_fields
    fields = markdown_fields()
    context = context or {}
    replacements = [(str(v), '{{' + k + '}}') for k, v in context.items() if v and len(str(v)) >= 3]
    replacements.sort(key=lambda pair: len(pair[0]), reverse=True)
    def clean(value, key=''):
        if isinstance(value, dict): return {k: clean(v, k) for k, v in value.items() if k not in ('figure', 'src', 'original', 'uid', 'number')}
        if isinstance(value, list):
            return [clean(x) for x in value if key != 'references' or not isinstance(x, str) or not private_reference(x)]
        if isinstance(value, str):
            if key.endswith('_md') or key in fields:
                value = sanitize_markdown(value)
            for old, new in replacements: value = value.replace(old, new)
        return value
    return clean({key: deepcopy(value) for key, value in finding.items() if key in TECHNICAL})


def load(path):
    return load_json_file(path) if path.is_file() else {'format': 'report-gen-library', 'version': 1, 'templates': []}


def validate_entry(entry):
    if not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not entry['name'].strip() or len(entry['name']) > 200:
        raise ValueError(backend_message('La plantilla necesita un nombre (1–200 caracteres)'))
    if not isinstance(entry.get('tags', []), list) or any(not isinstance(t, str) or len(t) > 80 for t in entry.get('tags', [])) or len(entry.get('tags', [])) > 30:
        raise ValueError(backend_message('Etiquetas inválidas'))
    if not isinstance(entry.get('content'), dict): raise ValueError(backend_message('Contenido de plantilla inválido'))
    content = sanitize(entry['content'])
    from validate import require_valid
    require_valid({'meta': {}, 'findings': [dict(content, id='F1')]})
    return {'name': entry['name'].strip(), 'tags': entry.get('tags', []), 'content': content}


def put(path, entry, uid=None):
    entry = validate_entry(entry)
    data = load(path)
    row = next((r for r in data['templates'] if r['uid'] == uid), None)
    if uid and not row: raise ValueError(backend_message('Plantilla inexistente'))
    if not row:
        if len(data['templates']) >= 500: raise ValueError(backend_message('Límite de 500 plantillas'))
        row = {'uid': new_uid(), 'versions': []}; data['templates'].append(row)
    if len(row['versions']) >= 200: raise ValueError(backend_message('Límite de 200 versiones por plantilla'))
    row.update(entry); row['updated'] = now()
    row['variables'] = sorted(set(VARIABLE.findall(json.dumps(entry['content']))))
    row['versions'].append(dict(entry, version=len(row['versions']) + 1, created=row['updated']))
    blob = dumps(data)
    load_json(blob)  # Do not commit a library that exceeds its own reader's limits.
    atomic_write(path, blob, backup=True)
    return row


def instantiate(entry, values):
    if not isinstance(values, dict) or any(not isinstance(v, str) for v in values.values()): raise ValueError(backend_message('Variables inválidas'))
    content = sanitize(entry['content'])
    def fill(value):
        if isinstance(value, dict): return {k: fill(v) for k, v in value.items()}
        if isinstance(value, list): return [fill(v) for v in value]
        if isinstance(value, str):
            def replace(match):
                key = match[1]
                if not values.get(key, '').strip(): raise ValueError(backend_message('Completa la variable: {p0}', p0=key))
                return values[key]
            return VARIABLE.sub(replace, value)
        return value
    content = sanitize(fill(content)); content['uid'] = new_uid()
    if content.get('mode') == 'machine': content['host'] = {'name': values.get('objetivo', ''), 'ip': '', 'os': ''}
    else: content['affected'] = values.get('objetivo', '')
    content['verification']='unverified'
    return content
