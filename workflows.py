"""Portable project model, delivery checks and report projection (no network access)."""
from copy import deepcopy
from datetime import date
from pathlib import Path
import re
import uuid

STATUSES = {'open': ('Abierto', 'Open'), 'in_progress': ('En corrección', 'In progress'),
            'reported_fixed': ('Corrección comunicada', 'Reported fixed'),
            'verified_fixed': ('Corregido y verificado', 'Verified fixed'),
            'accepted': ('Riesgo aceptado', 'Risk accepted'), 'not_verified': ('No verificable', 'Not verifiable')}
RESULTS = {'fixed': ('Corregido', 'Fixed'), 'open': ('Sigue abierto', 'Still open'),
           'partial': ('Corrección parcial', 'Partially fixed'), 'not_verified': ('No verificable', 'Not verifiable')}
COVERAGE = {'pending': ('Pendiente', 'Pending'), 'done': ('Realizada', 'Performed'),
            'blocked': ('Bloqueada', 'Blocked'), 'not_applicable': ('No aplica', 'Not applicable')}
UID = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')


def new_uid():
    return str(uuid.uuid4())


def normalize(data):
    """Assign identities once; keep existing IDs, display numbers and legacy fields."""
    data['schema_version'] = 2
    for key in ('findings', 'assets', 'evidence', 'coverage'):
        for row in data.setdefault(key, []):
            row.setdefault('uid', new_uid())
    data.setdefault('report', {})
    return data


def structure_errors(data):
    """Validate workflow fields before they reach filesystem/image/report code."""
    errors = []
    def err(path, msg): errors.append(('error', f'{path}: {msg}'))
    def text(obj, key, path):
        if key in obj and not isinstance(obj[key], str): err(path + '.' + key, 'debe ser texto')
    def rows(obj, key, path):
        value = obj.get(key, [])
        if not isinstance(value, list) or len(value) > 10000 or any(not isinstance(x, dict) for x in value):
            err(path + '.' + key, 'debe ser una lista de objetos'); return []
        return value
    def refs(obj, key, path):
        value = obj.get(key, [])
        if not isinstance(value, list) or any(not isinstance(x, str) or not UID.fullmatch(x) for x in value):
            err(path + '.' + key, 'referencias inválidas')
    def ident(row, path, seen):
        if 'uid' in row:
            uid = row['uid']
            if not isinstance(uid, str) or not UID.fullmatch(uid): err(path + '.uid', 'identificador inválido')
            elif uid in seen: err(path + '.uid', 'identificador duplicado')
            else: seen.add(uid)
    def dt(row, key, path):
        if row.get(key):
            try: date.fromisoformat(str(row[key]))
            except (ValueError, TypeError): err(path + '.' + key, 'usa AAAA-MM-DD')
    if 'schema_version' in data and (type(data['schema_version']) is not int or data['schema_version'] not in (1, 2)):
        err('schema_version', 'versión de proyecto no soportada')
    seen = set()
    for group in ('assets', 'evidence', 'coverage', 'findings'):
        for n, row in enumerate(rows(data, group, 'project')):
            path = f'{group}[{n}]'; ident(row, path, seen)
            fields = {'assets': ('name', 'target', 'kind', 'notes'),
                      'evidence': ('title', 'src', 'original', 'caption'),
                      'coverage': ('test', 'status', 'notes', 'asset_uid'),
                      'findings': ('owner', 'due_date', 'status')}[group]
            for key in fields: text(row, key, path)
            if group == 'evidence':
                if not row.get('src'): err(path + '.src', 'ruta de imagen obligatoria')
                for key, prefix in [('src', 'img/'), ('original', 'originals/')]:
                    if row.get(key) and not safe_member(row[key], prefix): err(path + '.' + key, 'ruta inválida')
            if group == 'coverage' and (not isinstance(row.get('status', 'pending'), str) or row.get('status', 'pending') not in COVERAGE): err(path, 'estado de cobertura inválido')
            if group == 'findings':
                if not isinstance(row.get('status', 'open'), str) or row.get('status', 'open') not in STATUSES: err(path, 'estado inválido')
                dt(row, 'due_date', path)
                refs(row, 'asset_uids', path); refs(row, 'evidence_uids', path)
                for i, retest in enumerate(rows(row, 'retests', path)):
                    rp = path + f'.retests[{i}]'; ident(retest, rp, seen)
                    for key in ('tested_on', 'assessor', 'notes_md', 'result'): text(retest, key, rp)
                    dt(retest, 'tested_on', rp); refs(retest, 'evidence_uids', rp)
                    if not isinstance(retest.get('result'), str) or retest.get('result') not in RESULTS: err(rp, 'resultado de retest inválido')
    report = data.get('report', {})
    if isinstance(report, dict) and 'workflow' in report:
        cfg = report['workflow']
        if not isinstance(cfg, dict): err('report.workflow', 'debe ser un objeto')
        else:
            for key in ('include_assets', 'include_coverage', 'include_retest'):
                if key in cfg and not isinstance(cfg[key], bool): err('report.workflow.' + key, 'debe ser booleano')
    if 'limitations_md' in data and not isinstance(data['limitations_md'], str): err('limitations_md', 'debe ser texto')
    return errors


def safe_member(name, prefix=''):
    return (isinstance(name, str) and name.startswith(prefix) and not name.startswith('/')
            and not any(c in name for c in ('\\', ':', '\x00'))
            and all(part not in ('', '.', '..') for part in name.split('/')))


def strings(obj, path=''):
    if isinstance(obj, dict):
        for k, v in obj.items(): yield from strings(v, f'{path}.{k}' if path else k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj): yield from strings(v, f'{path}[{i}]')
    elif isinstance(obj, str): yield path, obj


def review(data, directory):
    """Actionable warnings; never asserts that a pentest is complete or secure."""
    issues = []
    def add(level, message, path, uid=None):
        issues.append(dict(level=level, message=message, path=path, finding_uid=uid))
    assets = {x.get('uid') for x in data.get('assets', [])}
    evidence = {x.get('uid'): x for x in data.get('evidence', [])}
    for i, f in enumerate(data.get('findings', [])):
        p = f'findings[{i}]'; uid = f.get('uid'); name = f.get('id', f'F{i+1}')
        fields = ['title'] + (['description_md', 'impact_md', 'remediation_md'] if f.get('mode') != 'machine' else [])
        for key in fields:
            if not str(f.get(key, '')).strip(): add('warning', f'{name}: falta {key}', p + '.' + key, uid)
        content = list(strings(f.get('walkthrough', f.get('phases', []))))
        if not any(value.strip() for _, value in content): add('warning', f'{name}: faltan pasos de reproducción', p + '.walkthrough', uid)
        image_present = any((path.endswith('.src') or '![' in value or '<img' in value) for path, value in strings(f))
        if not f.get('evidence_uids') and not f.get('proof') and not f.get('flags') and not image_present: add('warning', f'{name}: falta evidencia', p + '.evidence_uids', uid)
        for key, pool in [('asset_uids', assets), ('evidence_uids', evidence)]:
            for ref in f.get(key, []):
                if ref not in pool: add('error', f'{name}: referencia inexistente en {key}', p + '.' + key, uid)
        for j, record in enumerate(f.get('retests', [])):
            for ref in record.get('evidence_uids', []):
                if ref not in evidence: add('error', f'{name}: evidencia de retest inexistente', p + f'.retests[{j}]', uid)
            if record.get('result') == 'fixed' and not record.get('evidence_uids'):
                add('warning', f'{name}: retest corregido sin evidencia vinculada', p + f'.retests[{j}]', uid)
        if f.get('status') == 'verified_fixed' and not any(r.get('result') == 'fixed' for r in f.get('retests', [])):
            add('warning', f'{name}: figura corregido sin un retest que lo verifique', p + '.status', uid)
        if f.get('due_date') and f['due_date'] < date.today().isoformat() and f.get('status', 'open') not in ('verified_fixed', 'accepted'):
            add('warning', f'{name}: fecha de corrección vencida', p + '.due_date', uid)
    for i, row in enumerate(data.get('coverage', [])):
        if row.get('asset_uid') and row['asset_uid'] not in assets: add('error', 'Cobertura vinculada a un activo inexistente', f'coverage[{i}].asset_uid')
        if row.get('status', 'pending') in ('pending', 'blocked'):
            add('warning', 'Prueba pendiente o bloqueada: ' + row.get('test', ''), f'coverage[{i}].status')
    for path, value in strings(data):
        match = re.search(r'\b(TODO|TBD|FIXME|pendiente de completar|lorem ipsum)\b|\{\{[^}]+\}\}|<COMPLETAR>', value, re.I)
        uid = None
        fm = re.match(r'findings\[(\d+)\]', path)
        if fm: uid = data['findings'][int(fm[1])].get('uid')
        if match: add('warning', 'Texto pendiente: ' + match[0], path, uid)
        sources = []
        if path.endswith(('.src', '.logo', '.client_logo', '.cover_image')): sources.append(value)
        sources.extend(re.findall(r'!\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)', value))
        # HTML images also occur in Markdown fields.
        sources.extend(re.findall(r'<img\b[^>]*\bsrc=[\"\']([^\"\']+)', value, re.I))
        for source in sources:
            if not source.startswith(('data:', 'https:', 'http:')):
                from resources import local_image
                try: local_image(source, Path(directory))
                except ValueError: add('error', 'Imagen ausente o no permitida: ' + source, path, uid)
    if not data.get('findings'): add('warning', 'El proyecto no contiene hallazgos', 'findings')
    return issues


def compare(before, after):
    """Compare findings by permanent identity, so reordering is not deletion."""
    result = []
    def walk(a, b, path, uid=None):
        if a == b: return
        if isinstance(a, dict) and isinstance(b, dict):
            for key in sorted(a.keys() | b.keys()): walk(a.get(key), b.get(key), path + '.' + key, uid)
        else: result.append(dict(path=path, finding_uid=uid, before=a, after=b))
    old = {f.get('uid', f.get('id')): f for f in before.get('findings', [])}
    new = {f.get('uid', f.get('id')): f for f in after.get('findings', [])}
    for uid in sorted(old.keys() | new.keys()): walk(old.get(uid), new.get(uid), 'findings.' + str(uid), uid)
    walk({k: v for k, v in before.items() if k != 'findings'}, {k: v for k, v in after.items() if k != 'findings'}, 'project')
    return result


def label(group, key, lang):
    return group.get(key, (key, key))[lang != 'es']


def md_text(value):
    """Plain user data in generated Markdown tables/headings, never markup."""
    from html import escape
    value = escape(str(value or '')).replace('\n', ' ').replace('\r', ' ')
    return re.sub(r'([\\`*_{}\[\]()#+.!|>~-])', r'\\\1', value)


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(md_text(v) for v in headers) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(md_text(v) for v in row) + ' |' for row in rows])


def report_sections(data):
    lang = data.get('meta', {}).get('lang', 'es'); es = lang == 'es'
    cfg = data.get('report', {}).get('workflow', {})
    assets = {a.get('uid'): a for a in data.get('assets', [])}
    out = []
    def add(key, title, body): out.append(dict(key=key, title=title, body=body))
    if cfg.get('include_assets', True) and assets:
        add('rg_assets', 'Activos evaluados' if es else 'Assessed assets', table(
            ['Activo', 'Objetivo', 'Tipo', 'Notas'] if es else ['Asset', 'Target', 'Type', 'Notes'],
            [[a.get(k, '') for k in ('name', 'target', 'kind', 'notes')] for a in assets.values()]))
    if cfg.get('include_coverage', True) and (data.get('coverage') or data.get('limitations_md')):
        body = table(['Prueba', 'Activo', 'Estado', 'Observaciones'] if es else ['Test', 'Asset', 'Status', 'Notes'],
                     [[c.get('test'), assets.get(c.get('asset_uid'), {}).get('target', ''), label(COVERAGE, c.get('status', 'pending'), lang), c.get('notes')]
                      for c in data.get('coverage', [])]) if data.get('coverage') else ''
        if data.get('limitations_md'): body += '\n\n### ' + ('Limitaciones' if es else 'Limitations') + '\n\n' + data['limitations_md']
        add('rg_coverage', 'Cobertura y limitaciones' if es else 'Coverage and limitations', body)
    fs = data.get('findings', [])
    if cfg.get('include_retest', True) and any(f.get('retests') or f.get('owner') or f.get('due_date') or f.get('status', 'open') != 'open' for f in fs):
        counts = {key: sum(f.get('status', 'open') == key for f in fs) for key in STATUSES}
        overview = ' · '.join(label(STATUSES, key, lang) + ': ' + str(value) for key, value in counts.items() if value)
        body = md_text(overview) + '\n\n' + table(['Hallazgo', 'Estado', 'Responsable', 'Fecha objetivo', 'Último retest'] if es else ['Finding', 'Status', 'Owner', 'Due date', 'Last retest'],
                     [[f.get('id', '') + ' · ' + f.get('title', ''), label(STATUSES, f.get('status', 'open'), lang), f.get('owner'), f.get('due_date'),
                       (f.get('retests') or [{}])[-1].get('tested_on')] for f in fs])
        for f in fs:
            for r in f.get('retests', []):
                body += '\n\n### ' + md_text(f.get('id', '') + ' · ' + r.get('tested_on', '') + ' · ' + label(RESULTS, r['result'], lang))
                body += '\n\n' + ('Evaluador: ' if es else 'Assessor: ') + md_text(r.get('assessor', '')) + '\n\n' + r.get('notes_md', '')
                by_uid = {e.get('uid'): e for e in data.get('evidence', [])}
                for uid in r.get('evidence_uids', []):
                    e = by_uid.get(uid)
                    if e: body += '\n\n![' + md_text(e.get('caption') or e.get('title') or 'Evidence') + '](' + e['src'] + ')'
        add('rg_retest', 'Seguimiento de correcciones y retest' if es else 'Remediation tracking and retest', body)
    return out


def project_report(source):
    """Pure projection: add asset links/evidence to copies, outside indivisible tables."""
    data = deepcopy(source)
    assets = {a.get('uid'): a for a in data.get('assets', [])}
    evidence = {e.get('uid'): e for e in data.get('evidence', [])}
    for c in data.get('coverage', []):
        if c.get('asset_uid') and c['asset_uid'] not in assets:
            raise ValueError('Cobertura vinculada a un activo inexistente')
    for f in data.get('findings', []):
        for key, pool in [('asset_uids', assets), ('evidence_uids', evidence)]:
            if any(ref not in pool for ref in f.get(key, [])):
                raise ValueError(str(f.get('id', 'Hallazgo')) + ': referencia inexistente en ' + key)
        for r in f.get('retests', []):
            if any(ref not in evidence for ref in r.get('evidence_uids', [])):
                raise ValueError(str(f.get('id', 'Hallazgo')) + ': evidencia de retest inexistente')
        extra = []
        targets = [assets[x].get('target', '') for x in f.get('asset_uids', []) if x in assets]
        if targets:
            extra.append({'text_md': '**' + ('Activos afectados' if data.get('meta', {}).get('lang') == 'es' else 'Affected assets') + '**\n\n' + '\n'.join('- ' + md_text(x) for x in targets)})
        existing = {value for path, value in strings(f) if path.endswith('.src')}
        for uid in f.get('evidence_uids', []):
            e = evidence.get(uid)
            if e and e['src'] not in existing:
                extra.append({'figure': {'src': e['src'], 'caption': e.get('caption') or e.get('title', '')}})
        if extra:
            if f.get('mode') == 'machine': f.setdefault('phases', []).append({'name': 'Evidencias' if data.get('meta', {}).get('lang') == 'es' else 'Evidence', 'steps': extra})
            else: f.setdefault('walkthrough', []).extend(extra)
    return data
