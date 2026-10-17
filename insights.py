"""Optional, local reasoning and editorial review. Never certifies a pentest.

Reading a view does not normalize, add identities, edit fields or write files.
An editorial decision refers to documentary content and referenced image bytes;
it neither authenticates the self-declared reviewer nor verifies a vulnerability.
"""
from languages import normalize_language, language_index
from error_messages import message as backend_message
from copy import deepcopy
from datetime import date, datetime
from hashlib import sha256
import json
from pathlib import Path
import re

import workflows

VERSION = 1
GROUP_LIMITS = {'claims': 2000, 'risks': 1000, 'comments': 5000, 'reviews': 500}
KINDS = {'observed', 'inference', 'hypothesis'}
PRIORITIES = {'P1', 'P2', 'P3', 'unassigned'}
DECISIONS = {'approved', 'changes_requested'}
_HEX = re.compile(r'^[0-9a-f]{64}$')
_FIELD = re.compile(r'^[A-Za-z0-9_.\[\]-]{1,200}$')
_FIELDS = {
    'claims': {'uid', 'finding_uid', 'statement', 'kind', 'demonstrates',
               'does_not_demonstrate', 'evidence_uids'},
    'risks': {'uid', 'finding_uid', 'service', 'objective', 'consequence',
              'tolerance', 'source', 'assumptions', 'priority', 'rationale', 'owner'},
    'comments': {'uid', 'finding_uid', 'field', 'body', 'author', 'visibility',
                 'created', 'revision', 'status', 'resolution', 'resolved_at',
                 'resolved_revision', 'resolved_by'},
    'reviews': {'uid', 'decision', 'author', 'notes', 'created', 'content_digest',
                'comment_digest', 'revision'},
}
RULES = [
    {'id': 'scope_absolute', 'es': 'Una afirmación absoluta de alcance necesita límites y evidencia explícitos.',
     'en': 'An absolute scope claim needs explicit limits and evidence.', 'pt': 'Uma afirmação absoluta de escopo exige limites e evidências explícitos.'},
    {'id': 'security_absolute', 'es': 'Una evaluación no acredita seguridad completa o ausencia de vulnerabilidades.',
     'en': 'An assessment does not establish complete security or absence of vulnerabilities.', 'pt': 'Uma avaliação não comprova segurança completa nem ausência de vulnerabilidades.'},
    {'id': 'fixed_without_retest', 'es': 'Una corrección comunicada no equivale a un retest documentado.',
     'en': 'A reported fix is not equivalent to a documented retest.', 'pt': 'Uma correção comunicada não equivale a um reteste documentado.'},
    {'id': 'claim_without_evidence', 'es': 'Una observación declarada necesita la evidencia que sustenta esta afirmación.',
     'en': 'A declared observation needs the evidence supporting that specific claim.', 'pt': 'Uma observação declarada exige evidência que sustente essa afirmação específica.'},
    {'id': 'priority_without_basis', 'es': 'La prioridad de intervención necesita una justificación y una fuente.',
     'en': 'An intervention priority needs a rationale and a source.', 'pt': 'A prioridade de intervenção exige uma justificativa e uma fonte.'},
]


def _uid(value):
    return isinstance(value, str) and bool(workflows.UID.fullmatch(value))


def validate_structure(data):
    """Bounded optional model validation, callable from save/import guards.

Historical references may outlive a removed finding/evidence. They are shown as
missing links rather than preventing deletion; new references are checked by
the explicit mutation API. Absence of the whole model remains valid.
"""
    if not isinstance(data, dict) or 'insights' not in data:
        return []
    value = data['insights']
    errors = []

    def err(path, message):
        errors.append(('error', f'{path}: {message}'))

    if not isinstance(value, dict):
        return [('error', backend_message('insights: debe ser un objeto / must be an object'))]
    if type(value.get('version')) is not int or value['version'] != VERSION:
        err('insights.version', backend_message('versión no soportada / unsupported version'))
    if set(value) - ({'version'} | set(GROUP_LIMITS)):
        err('insights', backend_message('campo desconocido / unknown field'))
    def source_rows(source, key):
        rows = source.get(key, [])
        return rows if isinstance(rows, list) else []

    seen = {row.get('uid') for group in ('findings', 'assets', 'evidence', 'coverage')
            for row in source_rows(data, group) if isinstance(row, dict) and _uid(row.get('uid'))}
    for finding in source_rows(data, 'findings'):
        if isinstance(finding, dict):
            seen.update(row['uid'] for row in source_rows(finding, 'retests')
                        if isinstance(row, dict) and _uid(row.get('uid')))
    for group, limit in GROUP_LIMITS.items():
        rows = value.get(group, [])
        if not isinstance(rows, list) or len(rows) > limit:
            err('insights.' + group, backend_message('lista de hasta {p0} objetos / list of up to {p1} objects', p0=limit, p1=limit))
            continue
        risk_findings = set()
        for idx, row in enumerate(rows):
            path = f'insights.{group}[{idx}]'
            if not isinstance(row, dict):
                err(path, backend_message('debe ser un objeto / must be an object'))
                continue
            if set(row) - _FIELDS[group]:
                err(path, backend_message('campo desconocido / unknown field'))
            if not _uid(row.get('uid')) or row.get('uid') in seen:
                err(path + '.uid', backend_message('identificador inválido o duplicado / invalid or duplicate identity'))
            else:
                seen.add(row['uid'])
            for key, item in row.items():
                if key == 'evidence_uids':
                    if (not isinstance(item, list) or len(item) > 1000
                            or any(not _uid(ref) for ref in item)
                            or (all(isinstance(x, str) for x in item) and len(set(item)) != len(item))):
                        err(path + '.' + key, backend_message('referencias inválidas / invalid references'))
                elif not isinstance(item, str) or len(item) > (
                        200 if key in {'author', 'resolved_by', 'field'} else
                        64 if key in {'created', 'resolved_at', 'revision', 'resolved_revision', 'content_digest', 'comment_digest'} else
                        8000 if key in {'body', 'resolution', 'notes', 'rationale', 'assumptions', 'consequence'} else 4000):
                    err(path + '.' + key, backend_message('texto demasiado largo o inválido / invalid or overlong text'))
            if group in {'claims', 'risks'} and not _uid(row.get('finding_uid')):
                err(path + '.finding_uid', backend_message('hallazgo obligatorio / finding identity required'))
            if group == 'claims':
                if not isinstance(row.get('kind'), str) or row['kind'] not in KINDS:
                    err(path + '.kind', backend_message('observed, inference o hypothesis'))
                if not isinstance(row.get('statement'), str) or not row['statement'].strip():
                    err(path + '.statement', backend_message('afirmación obligatoria / statement required'))
            elif group == 'risks':
                if not isinstance(row.get('priority'), str) or row['priority'] not in PRIORITIES:
                    err(path + '.priority', backend_message('P1, P2, P3 o unassigned'))
                ref = row.get('finding_uid')
                if isinstance(ref, str) and ref in risk_findings:
                    err(path + '.finding_uid', backend_message('riesgo duplicado para el hallazgo / duplicate finding risk'))
                elif isinstance(ref, str):
                    risk_findings.add(ref)
            elif group == 'comments':
                for field in ('field', 'body', 'author', 'created', 'revision'):
                    if not isinstance(row.get(field), str) or not row[field].strip():
                        err(path + '.' + field, backend_message('campo obligatorio / required field'))
                if not isinstance(row.get('field'), str) or not _FIELD.fullmatch(row['field']):
                    err(path + '.field', backend_message('referencia de campo inválida / invalid field reference'))
                if 'finding_uid' in row and not _uid(row['finding_uid']):
                    err(path + '.finding_uid', backend_message('referencia inválida / invalid reference'))
                if row.get('visibility') not in ('private', 'public') or row.get('status') not in ('open', 'resolved'):
                    err(path, backend_message('estado o visibilidad inválidos / invalid status or visibility'))
                if not isinstance(row.get('revision'), str) or not _HEX.fullmatch(row['revision']):
                    err(path + '.revision', backend_message('revisión inválida / invalid revision'))
                if row.get('status') == 'resolved':
                    for field in ('resolution', 'resolved_by', 'resolved_at', 'resolved_revision'):
                        if not isinstance(row.get(field), str) or not row[field].strip():
                            err(path + '.' + field, backend_message('resolución obligatoria / resolution required'))
                    if not isinstance(row.get('resolved_revision'), str) or not _HEX.fullmatch(row['resolved_revision']):
                        err(path + '.resolved_revision', backend_message('revisión inválida / invalid revision'))
            elif group == 'reviews':
                if not isinstance(row.get('decision'), str) or row['decision'] not in DECISIONS:
                    err(path + '.decision', backend_message('decisión inválida / invalid decision'))
                for field in ('author', 'created', 'revision', 'content_digest'):
                    if not isinstance(row.get(field), str) or not row[field].strip():
                        err(path + '.' + field, backend_message('campo obligatorio / required field'))
                for field in ('revision', 'content_digest', 'comment_digest'):
                    if field == 'comment_digest' and field not in row:
                        continue
                    if not isinstance(row.get(field), str) or not _HEX.fullmatch(row[field]):
                        err(path + '.' + field, backend_message('hash inválido / invalid digest'))
    return errors


def require_structure(data):
    errors = validate_structure(data)
    if errors:
        raise ValueError('; '.join(message for _, message in errors))


def _json_value(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(backend_message('Unsupported documentary value'))


def _comment_digest(model):
    """Separate review context: new objections need an explicit new decision."""
    blob = json.dumps(model.get('comments', []), sort_keys=True, ensure_ascii=False,
                      separators=(',', ':'), default=_json_value,
                      allow_nan=False).encode('utf-8')
    return sha256(blob).hexdigest()


def content_digest(data, directory=None):
    """Hash current documentary content, excluding review/comment bookkeeping.

Referenced image bytes are included when a directory is supplied. The digest
proves change/integrity only. It cannot prove an event, identity or authorization.
Missing/unsafe resources explicitly prevent a new approved decision.
"""
    payload = {key: value for key, value in data.items() if key != 'insights'}
    model = data.get('insights') or {}
    for group in ('claims', 'risks'):
        if model.get(group):
            payload['insights_' + group] = model[group]
    complete = True
    resources = {}
    if directory is not None:
        from resources import local_image, referenced_images
        sources = set(referenced_images(payload))
        total_bytes = 0
        for index, source in enumerate(sorted(sources)):
            try:
                if index >= 10000:
                    raise ValueError(backend_message('Resource count budget exceeded'))
                path = local_image(source, Path(directory))
                digest = sha256()
                consumed = 0
                with path.open('rb') as stream:
                    while chunk := stream.read(65536):
                        consumed += len(chunk)
                        total_bytes += len(chunk)
                        if consumed > 64 * 1024 * 1024 or total_bytes > 256 * 1024 * 1024:
                            raise ValueError(backend_message('Resource budget exceeded'))
                        digest.update(chunk)
                resources[source] = digest.hexdigest()
            except (ValueError, OSError):
                complete = False
                resources[source] = 'unavailable'
    blob = json.dumps({'document': payload, 'resources': resources}, sort_keys=True,
                      ensure_ascii=False, separators=(',', ':'), default=_json_value,
                      allow_nan=False).encode('utf-8')
    return sha256(blob).hexdigest(), complete


def relationship_map(data):
    assets = [{key: row.get(key, '') for key in ('uid', 'name', 'target')}
              for row in data.get('assets', [])]
    evidence = [{key: row.get(key, '') for key in ('uid', 'title', 'caption', 'src')}
                for row in data.get('evidence', [])]
    findings = []
    links = []
    pools = {'asset': {row['uid'] for row in assets}, 'evidence': {row['uid'] for row in evidence}}
    for finding in data.get('findings', []):
        item = {key: finding.get(key, '') for key in ('uid', 'id', 'title', 'severity', 'status')}
        for key in ('asset_uids', 'evidence_uids'):
            item[key] = list(finding.get(key, []))
        item['retests'] = [{key: row.get(key, [] if key == 'evidence_uids' else '')
                           for key in ('uid', 'result', 'tested_on', 'evidence_uids')}
                          for row in finding.get('retests', [])]
        findings.append(item)
        for kind, key in [('asset', 'asset_uids'), ('evidence', 'evidence_uids')]:
            for ref in item[key]:
                links.append(dict(kind=kind, **{'from': item['uid'], 'to': ref}, missing=ref not in pools[kind]))
        for retest in item['retests']:
            links.append(dict(kind='retest', **{'from': item['uid'], 'to': retest['uid']}, missing=False))
            for ref in retest['evidence_uids']:
                links.append(dict(kind='evidence', **{'from': retest['uid'], 'to': ref}, missing=ref not in pools['evidence']))
    pool = {row['uid'] for row in findings}
    for claim in (data.get('insights') or {}).get('claims', []):
        links.append(dict(kind='claim', **{'from': claim['uid'], 'to': claim['finding_uid']}, missing=claim['finding_uid'] not in pool))
        for ref in claim.get('evidence_uids', []):
            links.append(dict(kind='evidence', **{'from': claim['uid'], 'to': ref}, missing=ref not in pools['evidence']))
    return dict(assets=assets, findings=findings, evidence=evidence, links=links)


def editorial(data, language='es'):
    """Transparent deterministic prompts, with no invented technical conclusion."""
    findings = data.get('findings', [])
    live = {row.get('uid'): row for row in findings}
    messages = {rule['id']: rule[normalize_language(language)] for rule in RULES}
    issues = []

    def add(rule, path, uid=None):
        issues.append(dict(rule=rule, level='warning', message=messages[rule],
                           help=((('Revisa el contexto y documenta los límites; no se modificó ningún texto.', 'Review the context and document limits; no text was changed.', 'Revise o contexto e documente os limites; nenhum texto foi alterado.')[language_index(language)])),
                           path=path, finding_uid=uid, technical_verification=False))

    for idx, finding in enumerate(findings):
        text = ' '.join(str(finding.get(key) or '') for key in
                        ('description_md', 'summary_md', 'impact_md', 'remediation_md'))
        path = f'findings[{idx}]'
        if re.search(r'\b(acceso total|todos los documentos|acesso total|todos os documentos|total access|all documents)\b', text, re.I):
            add('scope_absolute', path, finding.get('uid'))
        if re.search(r'\b(completamente segur[oa]|sin vulnerabilidades|sem vulnerabilidades|completely secure|no vulnerabilities)\b', text, re.I):
            add('security_absolute', path, finding.get('uid'))
        fixed = re.search(r'\b(corregid[oa]|corrigid[oa]|fixed|resolved)\b', text, re.I) or finding.get('status') in ('reported_fixed', 'verified_fixed')
        last = workflows.latest_retest(finding)
        if fixed and not (last.get('result') == 'fixed' and last.get('evidence_uids')):
            add('fixed_without_retest', path, finding.get('uid'))
    model = data.get('insights') or {}
    for idx, claim in enumerate(model.get('claims', [])):
        if claim.get('kind') == 'observed' and not claim.get('evidence_uids'):
            add('claim_without_evidence', f'insights.claims[{idx}]', claim['finding_uid'])
    for idx, risk in enumerate(model.get('risks', [])):
        if risk.get('priority') != 'unassigned' and not (risk.get('rationale', '').strip() and risk.get('source', '').strip()):
            add('priority_without_basis', f'insights.risks[{idx}]', risk['finding_uid'])
    # Historical missing links stay visible after deleting a referenced record.
    evidence = {row.get('uid') for row in data.get('evidence', [])}
    for group in ('claims', 'risks'):
        for idx, row in enumerate(model.get(group, [])):
            if row['finding_uid'] not in live or any(ref not in evidence for ref in row.get('evidence_uids', [])):
                issues.append(dict(rule='missing_reference', level='warning',
                                   message=(('Referencia histórica ausente', 'Missing historical reference', 'Referência histórica ausente')[language_index(language)]),
                                   help=(('Revisa el vínculo', 'Review the link', 'Revise o vínculo')[language_index(language)]),
                                   path=f'insights.{group}[{idx}]', finding_uid=row['finding_uid'],
                                   technical_verification=False))
    return issues


def view(data, directory=None, language='es'):
    require_structure(data)
    model = data.get('insights') or {}
    digest, complete = content_digest(data, directory)
    reviews = model.get('reviews', [])
    latest = reviews[-1] if reviews else None
    state = 'not_reviewed'
    if latest:
        state = latest['decision'] if latest['content_digest'] == digest and complete else 'stale'
        if ('comment_digest' in latest or model.get('comments')) and latest.get('comment_digest') != _comment_digest(model):
            state = 'stale'
    return dict(version=VERSION, map=relationship_map(data),
                **{group: deepcopy(model.get(group, [])) for group in GROUP_LIMITS},
                editorial=editorial(data, language), digest=digest, resources_complete=complete,
                review_status=dict(state=state, record=deepcopy(latest), local_self_declared=True),
                capabilities=dict(local_editorial_rules=True, optional_local_ai=True, external_ai=False))


def mutate(data, body, source_revision, directory=None, now=None):
    """An explicit action returns a new model; neither input object is mutated."""
    require_structure(data)
    if not isinstance(body, dict) or not isinstance(body.get('action'), str):
        raise ValueError(backend_message('Acción de análisis inválida / Invalid analysis action'))
    if not isinstance(source_revision, str) or not _HEX.fullmatch(source_revision):
        raise ValueError(backend_message('Revisión inválida / Invalid revision'))
    from project_history import now as utc_now
    timestamp = now or utc_now()
    result = deepcopy(data)
    # This is an explicit write. Existing history.save normalizes identities;
    # bind the decision to that actual saved form so a legacy draft does not
    # immediately invalidate its own review on its first optional-model save.
    workflows.normalize(result)
    model = result.setdefault('insights', {'version': VERSION})
    action = body['action']
    allowed = {
        'set_claim': _FIELDS['claims'] | {'action'},
        'set_risk': _FIELDS['risks'] | {'action'},
        'delete_claim': {'action', 'uid'}, 'delete_risk': {'action', 'uid'},
        'add_comment': {'action', 'finding_uid', 'field', 'body', 'author', 'visibility'},
        'resolve_comment': {'action', 'uid', 'resolution', 'author'},
        'review': {'action', 'decision', 'author', 'notes'},
    }
    if action not in allowed or set(body) - allowed[action]:
        raise ValueError(backend_message('Acción o campos desconocidos / Unknown action or fields'))
    finding_pool = {row.get('uid') for row in data.get('findings', [])}
    evidence_pool = {row.get('uid') for row in data.get('evidence', [])}

    def required(key, limit=8000):
        value = body.get(key)
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise ValueError(backend_message('{p0}: texto obligatorio y acotado / bounded text required', p0=key))
        return value.strip()

    def identified(group):
        identity = body.get('uid')
        row = next((row for row in model.get(group, []) if row['uid'] == identity), None)
        if not row:
            raise ValueError(backend_message('Registro inexistente / Record not found'))
        return row

    if action in ('set_claim', 'set_risk'):
        group = 'claims' if action == 'set_claim' else 'risks'
        ref = body.get('finding_uid')
        if not _uid(ref) or ref not in finding_pool:
            raise ValueError(backend_message('Hallazgo inexistente / Finding not found'))
        identity = body.get('uid')
        rows = model.setdefault(group, [])
        if identity:
            old = identified(group)
            if old['finding_uid'] != ref:
                raise ValueError(backend_message('No se puede cambiar el hallazgo vinculado / Cannot change the linked finding'))
        elif group == 'risks' and any(row['finding_uid'] == ref for row in rows):
            raise ValueError(backend_message('Ya existe un riesgo para este hallazgo / A risk already exists for this finding'))
        else:
            identity = workflows.new_uid()
        row = {key: deepcopy(body[key]) for key in _FIELDS[group] - {'uid'} if key in body}
        row.update(uid=identity, finding_uid=ref)
        if group == 'claims':
            row['statement'] = required('statement', 4000)
            row.setdefault('kind', 'observed')
            row.setdefault('evidence_uids', [])
            if (not isinstance(row['evidence_uids'], list)
                    or any(not isinstance(uid, str) or uid not in evidence_pool for uid in row['evidence_uids'])):
                raise ValueError(backend_message('Evidencia inexistente / Evidence not found'))
        else:
            row.setdefault('priority', 'unassigned')
        if body.get('uid'):
            rows[rows.index(old)] = row
        else:
            rows.append(row)
    elif action in ('delete_claim', 'delete_risk'):
        group = 'claims' if action == 'delete_claim' else 'risks'
        row = identified(group)
        model[group].remove(row)
    elif action == 'add_comment':
        field = required('field', 200)
        if not _FIELD.fullmatch(field):
            raise ValueError(backend_message('Referencia de campo inválida / Invalid field reference'))
        ref = body.get('finding_uid')
        if ref is not None and (not isinstance(ref, str) or ref not in finding_pool):
            raise ValueError(backend_message('Hallazgo inexistente / Finding not found'))
        row = dict(uid=workflows.new_uid(), field=field, body=required('body'),
                   author=required('author', 200), visibility=body.get('visibility', 'private'),
                   created=timestamp, revision=source_revision, status='open')
        if ref is not None:
            row['finding_uid'] = ref
        model.setdefault('comments', []).append(row)
    elif action == 'resolve_comment':
        row = identified('comments')
        if row['status'] != 'open':
            raise ValueError(backend_message('Comentario ya resuelto / Comment already resolved'))
        row.update(status='resolved', resolution=required('resolution'),
                   resolved_by=required('author', 200), resolved_at=timestamp,
                   resolved_revision=source_revision)
    elif action == 'review':
        decision = body.get('decision')
        if not isinstance(decision, str) or decision not in DECISIONS:
            raise ValueError(backend_message('Decisión inválida / Invalid decision'))
        digest, complete = content_digest(result, directory)
        if decision == 'approved' and not complete:
            raise ValueError(backend_message('Recursos ausentes: no puede registrarse aprobación / Missing resources prevent approval'))
        if decision == 'approved' and any(row['status'] == 'open' for row in model.get('comments', [])):
            raise ValueError(backend_message('Resuelve los comentarios abiertos antes de aprobar / Resolve open comments before approval'))
        notes = body.get('notes', '')
        if not isinstance(notes, str) or len(notes) > 8000:
            raise ValueError(backend_message('Notas inválidas / Invalid notes'))
        model.setdefault('reviews', []).append(dict(uid=workflows.new_uid(), decision=decision,
            author=required('author', 200), notes=notes, created=timestamp,
            content_digest=digest, comment_digest=_comment_digest(model), revision=source_revision))
    require_structure(result)
    return result
