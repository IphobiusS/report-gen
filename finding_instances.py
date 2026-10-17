"""Explicit affected occurrences and their independent remediation observations.

Instances are opt-in: no legacy asset list is converted into technical claims.
All projections are pure and preserve the author’s original evidence records.
"""
from collections import Counter
from copy import deepcopy
from datetime import date, datetime
import re

from error_messages import current_language
from languages import language_index
import workflows

MAX_INSTANCES = 500
MAX_TOTAL = 10000
MAX_RETESTS = 200
MAX_EVIDENCE = 500
STATUSES = {**workflows.STATUSES, 'blocked': ('Verificación bloqueada', 'Verification blocked', 'Verificação bloqueada')}
FIELDS = {'asset_uid', 'endpoint', 'parameter', 'identity', 'environment', 'owner', 'due_date', 'status', 'notes_md', 'evidence_uids'}
TEXT_LIMITS = {'endpoint': 2048, 'parameter': 300, 'identity': 300, 'environment': 300,
               'owner': 200, 'notes_md': 16000}
UNSAFE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]')


def _error(es, en, pt):
    """Select complete authored prose without interpreting literal braces."""
    return (es, en, pt)[language_index(current_language())]


def _rows(value):
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _date(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        return False
    try:
        return date.fromisoformat(value).isoformat() == value
    except ValueError:
        return False


def aggregate_status(finding):
    """A closed occurrence never closes an unresolved sibling occurrence."""
    rows = _rows(finding.get('instances', []))
    if not rows:
        return finding.get('status', 'open')
    states = {row.get('status') if isinstance(row.get('status'), str) and row['status'] in STATUSES else 'open' for row in rows}
    if states == {'verified_fixed'}:
        return 'verified_fixed'
    if states == {'accepted'}:
        return 'accepted'
    if states <= {'not_verified', 'blocked'}:
        return 'not_verified'
    if states == {'reported_fixed'}:
        return 'reported_fixed'
    if states & {'verified_fixed', 'in_progress', 'reported_fixed'}:
        return 'in_progress'
    return 'open'


def update_aggregate(finding):
    if finding.get('instances'):
        finding['status'] = aggregate_status(finding)


def structure_errors(data, seen=None):
    """Strict, bounded opt-in schema; optional occupied IDs from core validation."""
    errors = []
    def fail(path, es, en, pt):
        errors.append(('error', path + ': ' + _error(es, en, pt)))
    findings = _rows(data.get('findings', []))
    occupied = set(seen or ())
    # Standalone callers receive the same identity protection as core callers.
    for key in ('findings', 'assets', 'evidence', 'coverage', 'root_cause_groups'):
        for row in _rows(data.get(key, [])):
            if isinstance(row.get('uid'), str): occupied.add(row['uid'])
    for finding in findings:
        for row in _rows(finding.get('retests', [])):
            if isinstance(row.get('uid'), str): occupied.add(row['uid'])
    assets = {row.get('uid') for row in _rows(data.get('assets', [])) if isinstance(row.get('uid'), str)}
    evidence = {row.get('uid') for row in _rows(data.get('evidence', [])) if isinstance(row.get('uid'), str)}

    def text(row, key, path, limit, required=False, multiline=False):
        value = row.get(key, '')
        valid = isinstance(value, str) and len(value) <= limit
        if valid:
            valid = not UNSAFE.search(value) and (multiline or not any(c in value for c in '\r\n\t'))
            try: value.encode('utf-8')
            except UnicodeEncodeError: valid = False
        if not valid or required and not value.strip():
            fail(path+'.'+key, 'texto inválido, vacío o demasiado largo', 'invalid, empty or oversized text', 'texto inválido, vazio ou muito longo')

    def identity(row, path):
        uid = row.get('uid')
        if not isinstance(uid, str) or not workflows.UID.fullmatch(uid) or uid in occupied:
            fail(path+'.uid', 'identidad permanente inválida o duplicada', 'invalid or duplicate permanent identity', 'identidade permanente inválida ou duplicada')
        else: occupied.add(uid)

    def refs(row, path):
        refs = row.get('evidence_uids', [])
        valid = (isinstance(refs, list) and len(refs) <= MAX_EVIDENCE
                 and all(isinstance(uid, str) and uid in evidence for uid in refs))
        if not valid or len(refs) != len(set(refs)):
            fail(path+'.evidence_uids', 'evidencias inexistentes, repetidas o inválidas', 'missing, duplicate or invalid evidence references', 'referências de evidência ausentes, duplicadas ou inválidas')

    total = 0
    for fi, finding in enumerate(findings):
        if 'instances' not in finding:
            continue
        path = f'findings[{fi}].instances'
        rows = finding['instances']
        if not isinstance(rows, list) or len(rows) > MAX_INSTANCES:
            fail(path, 'se permiten hasta 500 instancias', 'up to 500 instances are allowed', 'são permitidas até 500 instâncias')
            continue
        total += len(rows)
        for index, row in enumerate(rows):
            rp = f'{path}[{index}]'
            if not isinstance(row, dict):
                fail(rp, 'debe ser un objeto', 'must be an object', 'deve ser um objeto'); continue
            if set(row) - (FIELDS | {'uid', 'retests'}):
                fail(rp, 'campos de instancia no reconocidos', 'unrecognized instance fields', 'campos de instância não reconhecidos')
            identity(row, rp)
            for key, maximum in TEXT_LIMITS.items():
                text(row, key, rp, maximum, multiline=key == 'notes_md')
            reference = row.get('asset_uid', '')
            if not isinstance(reference, str) or reference and reference not in assets:
                fail(rp+'.asset_uid', 'activo inexistente', 'asset does not exist', 'ativo inexistente')
            if not reference and not (isinstance(row.get('endpoint'), str) and row['endpoint'].strip()):
                fail(rp+'.endpoint', 'indica un activo o destino', 'specify an asset or target', 'informe um ativo ou destino')
            status = row.get('status', 'open')
            if not isinstance(status, str) or status not in STATUSES:
                fail(rp+'.status', 'estado de instancia inválido', 'invalid instance status', 'status de instância inválido')
            if not isinstance(row.get('due_date', ''), str) or row.get('due_date') and not _date(row['due_date']):
                fail(rp+'.due_date', 'usa AAAA-MM-DD', 'use YYYY-MM-DD', 'use AAAA-MM-DD')
            refs(row, rp)
            tests = row.get('retests', [])
            if not isinstance(tests, list) or len(tests) > MAX_RETESTS:
                fail(rp+'.retests', 'se permiten hasta 200 retests', 'up to 200 retests are allowed', 'são permitidos até 200 retestes'); continue
            valid_tests = []
            for ri, record in enumerate(tests):
                tp = f'{rp}.retests[{ri}]'
                if not isinstance(record, dict):
                    fail(tp, 'debe ser un objeto', 'must be an object', 'deve ser um objeto'); continue
                if set(record) - {'uid', 'created', 'tested_on', 'assessor', 'notes_md', 'result', 'evidence_uids'}:
                    fail(tp, 'campos de retest no reconocidos', 'unrecognized retest fields', 'campos de reteste não reconhecidos')
                identity(record, tp)
                text(record, 'assessor', tp, 200, required=True)
                text(record, 'notes_md', tp, 16000, required=True, multiline=True)
                text(record, 'created', tp, 40)
                if record.get('created'):
                    try:
                        dt = datetime.fromisoformat(record['created'].replace('Z', '+00:00'))
                        if dt.tzinfo is None: raise ValueError
                    except (ValueError, TypeError, AttributeError):
                        fail(tp+'.created', 'fecha de registro inválida', 'invalid record timestamp', 'data do registro inválida')
                if not _date(record.get('tested_on')):
                    fail(tp+'.tested_on', 'usa AAAA-MM-DD', 'use YYYY-MM-DD', 'use AAAA-MM-DD')
                else: valid_tests.append(record)
                if not isinstance(record.get('result'), str) or record.get('result') not in workflows.RESULTS:
                    fail(tp+'.result', 'resultado inválido', 'invalid result', 'resultado inválido')
                refs(record, tp)
            latest = workflows.latest_retest({'retests': valid_tests})
            if status == 'verified_fixed' and latest.get('result') != 'fixed':
                fail(rp+'.status', 'la corrección verificada requiere un último retest corregido', 'verified fixed requires the latest retest to be fixed', 'a correção verificada exige que o último reteste esteja corrigido')
        if rows and finding.get('status', 'open') != aggregate_status(finding):
            fail(f'findings[{fi}].status', 'el estado general debe coincidir con todas las instancias; revisa sus estados y retests',
                 'overall status must match all instances; review their states and retests',
                 'o status geral deve corresponder a todas as instâncias; revise seus estados e retestes')
    if total > MAX_TOTAL:
        fail('findings.instances', 'el proyecto admite hasta 10000 instancias', 'the project supports up to 10000 instances', 'o projeto aceita até 10000 instâncias')
    return errors


def validate(data):
    errors = structure_errors(data)
    if errors:
        raise ValueError('; '.join(text for _, text in errors))


def new_instance(values):
    if not isinstance(values, dict) or set(values) - FIELDS:
        raise ValueError(_error('Campos de instancia inválidos', 'Invalid instance fields', 'Campos de instância inválidos'))
    return {'uid': workflows.new_uid(), 'status': 'open', 'evidence_uids': [], 'retests': [], **deepcopy(values)}


def record_retest(data, finding, instance_uid, values, created):
    proposed = deepcopy(finding)
    instance = next((row for row in proposed.get('instances', []) if row.get('uid') == instance_uid), None)
    if instance is None:
        raise ValueError(_error('Instancia inexistente', 'Instance does not exist', 'Instância inexistente'))
    allowed = {'tested_on', 'assessor', 'notes_md', 'result', 'evidence_uids'}
    if not isinstance(values, dict) or set(values) - allowed:
        raise ValueError(_error('Campos de retest inválidos', 'Invalid retest fields', 'Campos de reteste inválidos'))
    record = {**deepcopy(values), 'uid': workflows.new_uid(), 'created': created}
    instance.setdefault('retests', []).append(record)
    # Validate before sorting author-supplied dates and before touching input.
    instance['status'] = 'open'
    update_aggregate(proposed)
    trial = {**data, 'findings': [proposed if row is finding else row for row in data.get('findings', [])]}
    validate(trial)
    latest = workflows.latest_retest(instance)
    instance['status'] = {'fixed': 'verified_fixed', 'open': 'open', 'partial': 'in_progress', 'not_verified': 'not_verified'}.get(latest.get('result'), 'open')
    update_aggregate(proposed)
    validate(trial)
    finding['instances'] = proposed['instances']
    finding['status'] = proposed['status']
    return record


def summary(finding, lang='es'):
    slot = language_index(lang)
    counts = Counter(row.get('status', 'open') for row in _rows(finding.get('instances', [])))
    return {'total': sum(counts.values()), 'status': aggregate_status(finding),
            'counts': {key: counts.get(key, 0) for key in STATUSES},
            'labels': {key: labels[slot] for key, labels in STATUSES.items()}}


def export_rows(data, finding, lang='es'):
    """Plain text only: caller owns escaping and its chosen report layout."""
    slot = language_index(lang)
    def tr(es, en, pt): return (es, en, pt)[slot]
    assets = {a.get('uid'): a for a in _rows(data.get('assets', []))}
    evidence = {e.get('uid'): e for e in _rows(data.get('evidence', []))}
    rows = []
    for index, instance in enumerate(_rows(finding.get('instances', []))):
        asset = assets.get(instance.get('asset_uid'), {})
        latest = workflows.latest_retest(instance)
        details = [instance.get('endpoint', ''), instance.get('parameter', ''), instance.get('identity', ''), instance.get('environment', '')]
        linked = [evidence[uid].get('title') or evidence[uid].get('caption') or uid for uid in instance.get('evidence_uids', []) if uid in evidence]
        latest_text = ' · '.join(str(part) for part in [latest.get('tested_on'), workflows.RESULTS.get(latest.get('result'), ('', '', ''))[slot], latest.get('assessor')] if part)
        rows.append([str(index+1), asset.get('name') or asset.get('target') or '', ' · '.join(part for part in details if part),
                     STATUSES.get(instance.get('status', 'open'), ('', '', ''))[slot], instance.get('owner', ''), instance.get('due_date', ''),
                     '; '.join(linked), latest_text, instance.get('notes_md', '')])
    return {'title': tr('Instancias afectadas', 'Affected instances', 'Instâncias afetadas'), 'summary': summary(finding, lang),
            'headers': [tr('Instancia', 'Instance', 'Instância'), tr('Activo', 'Asset', 'Ativo'), tr('Destino / parámetro / identidad / entorno', 'Target / parameter / identity / environment', 'Destino / parâmetro / identidade / ambiente'),
                        tr('Estado', 'Status', 'Status'), tr('Responsable', 'Owner', 'Responsável'), tr('Plazo', 'Due date', 'Prazo'),
                        tr('Evidencia', 'Evidence', 'Evidência'), tr('Último retest', 'Latest retest', 'Último reteste'), tr('Notas', 'Notes', 'Notas')], 'rows': rows}
