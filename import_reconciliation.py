"""Explicit, revision-bound reconciliation. Scanner disappearance is not a retest."""
from copy import deepcopy
from hashlib import sha256
import json
import re

from error_messages import message
import finding_imports
from input_guard import ensure_data_tree
from project_history import now
import workflows

COPY_FIELDS = ('title', 'affected', 'description_md', 'impact_md', 'remediation_md', 'cwe', 'references', 'walkthrough')
MACHINE_COPY_FIELDS = ('title', 'references', 'walkthrough')
SNAPSHOT_FIELDS = COPY_FIELDS + ('cvss_vector', 'severity')
MAX_PER_FINDING, MAX_TOTAL, MAX_BYTES = 100, 500, 4 * 1024 * 1024


def _invalid():
    return ValueError(message('Decisión de conciliación inválida; revisa la selección', en='Invalid reconciliation decision; review the selection', pt='Decisão de conciliação inválida; revise a seleção'))


def _sources(finding):
    if isinstance(finding.get('import_source'), dict):
        yield finding['import_source'], finding
    for observation in finding.get('import_observations', []):
        yield observation['source'], observation['snapshot']


def _snapshot(finding):
    return {field: deepcopy(finding.get(field, [] if field in ('references', 'walkthrough') else '')) for field in SNAPSHOT_FIELDS}


def _digest(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()).hexdigest()


def structure_errors(data):
    errors, identities, count, size = [], set(), 0, 0
    if not isinstance(data, dict) or not isinstance(data.get('findings', []), list):
        return errors
    for i, finding in enumerate(data.get('findings', [])):
        if not isinstance(finding, dict):
            continue
        path = f'findings[{i}].import_observations'
        observations = finding.get('import_observations', [])
        def error(part=''):
            errors.append(('error', message('{path}: observación de importación inválida o fuera de límite', en='{path}: invalid or over-budget import observation', pt='{path}: observação de importação inválida ou acima do limite', path=path + part)))
        if not isinstance(observations, list) or len(observations) > MAX_PER_FINDING:
            error(); continue
        instance_ids = {item['uid'] for item in finding.get('instances', [])
                        if isinstance(item, dict) and isinstance(item.get('uid'), str)} if isinstance(finding.get('instances', []), list) else set()
        for j, row in enumerate(observations):
            count += 1
            if not isinstance(row, dict) or set(row) != {'uid', 'imported_at', 'instance_uid', 'source', 'snapshot', 'selected_fields'}:
                error(f'[{j}]'); continue
            uid = row['uid']
            if not isinstance(uid, str) or not workflows.UID.fullmatch(uid) or uid in identities:
                error(f'[{j}].uid')
            else:
                identities.add(uid)
            if (not isinstance(row['instance_uid'], str) or row['instance_uid'] and row['instance_uid'] not in instance_ids
                    or not isinstance(row['imported_at'], str) or not re.fullmatch(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|\+00:00)', row['imported_at'])):
                error(f'[{j}]')
            source, snapshot, fields = row['source'], row['snapshot'], row['selected_fields']
            if not isinstance(source, dict) or source.get('format') not in ('csv', 'burp', 'nuclei', 'sarif', 'zap', 'nessus') or not isinstance(source.get('fingerprint'), str) or not re.fullmatch('[a-f0-9]{64}', source.get('fingerprint', '')):
                error(f'[{j}].source')
            if not isinstance(fields, list) or any(not isinstance(field, str) or field not in COPY_FIELDS for field in fields) or len(set(field for field in fields if isinstance(field, str))) != len(fields):
                error(f'[{j}].selected_fields')
            if not isinstance(snapshot, dict) or set(snapshot) != set(SNAPSHOT_FIELDS):
                error(f'[{j}].snapshot'); continue
            if any(not isinstance(snapshot[field], str) for field in SNAPSHOT_FIELDS if field not in ('references', 'walkthrough')):
                error(f'[{j}].snapshot')
            if not isinstance(snapshot['references'], list) or any(not isinstance(value, str) for value in snapshot['references']):
                error(f'[{j}].snapshot.references')
            steps = snapshot['walkthrough']
            if not isinstance(steps, list) or len(steps) > 1000 or any(not isinstance(step, dict) or set(step) - {'lead', 'text_md', 'command'} or any(not isinstance(value, str) for value in step.values()) for step in steps):
                error(f'[{j}].snapshot.walkthrough')
            try:
                size += len(json.dumps(row, ensure_ascii=True).encode())
            except (ValueError, TypeError):
                error(f'[{j}]')
    if count > MAX_TOTAL or size > MAX_BYTES:
        errors.append(('error', message('Las observaciones superan 500 entradas o 4 MiB; conserva un respaldo y depura el historial antes de importar', en='Observations exceed 500 entries or 4 MiB; keep a backup and prune history before importing', pt='As observações excedem 500 entradas ou 4 MiB; mantenha um backup e limpe o histórico antes de importar')))
    return errors


def preview(body, data):
    result = finding_imports.preview(body, data)
    if result.get('kind') != 'findings':
        raise ValueError(message('Nmap conserva su importación de inventario', en='Nmap uses the inventory importer', pt='Nmap utiliza o importador de inventário'))
    findings = data.get('findings', [])
    for row in result['rows']:
        incoming = row['finding']
        key = finding_imports.source_fingerprint(incoming)
        candidates = []
        for finding in findings:
            kind = None
            for source, snapshot in _sources(finding):
                if source.get('format') == result['format'] and finding_imports.source_fingerprint({'import_source': source, **snapshot}) == key:
                    kind = 'exact'; break
            if kind is None and (finding_imports.fingerprint(finding) == finding_imports.fingerprint(incoming)
                    or any(source.get('format') == result['format'] and source.get('external_id') and source.get('external_id') == incoming['import_source'].get('external_id') for source, _ in _sources(finding))):
                kind = 'probable'
            if kind:
                differences = [{'field': field, 'before': deepcopy(finding.get(field, [] if field in ('references', 'walkthrough') else '')), 'after': deepcopy(incoming.get(field, [] if field in ('references', 'walkthrough') else ''))}
                               for field in SNAPSHOT_FIELDS if finding.get(field, [] if field in ('references', 'walkthrough') else '') != incoming.get(field, [] if field in ('references', 'walkthrough') else '')]
                candidates.append(dict(finding_uid=finding.get('uid'), id=finding.get('id', ''), title=finding.get('title', ''), match=kind, differences=differences,
                    instances=[dict(uid=item['uid'], endpoint=item.get('endpoint', ''), identity=item.get('identity', '')) for item in finding.get('instances', [])]))
        row['matches'] = candidates
        row['match'] = 'exact' if any(item['match'] == 'exact' for item in candidates) else 'probable' if candidates else 'new'
        row['suggested_action'] = 'skip' if row['errors'] or row['duplicate'] else 'create' if not candidates else 'skip'
    result['copy_fields'] = list(COPY_FIELDS)
    result['notice'] = message('Adjuntar conserva la redacción, CVSS, estado y retests. Solo se copian los campos elegidos. Una ausencia en el escaneo no cierra hallazgos.', en='Attaching preserves authored text, CVSS, status and retests. Only selected fields are copied. Absence from a scan does not close findings.', pt='Anexar preserva o texto, CVSS, estado e retestes. Somente os campos escolhidos são copiados. A ausência na varredura não encerra achados.')
    result['counts'].update(exact=sum(row['match'] == 'exact' for row in result['rows']), probable=sum(row['match'] == 'probable' for row in result['rows']), new=sum(row['match'] == 'new' for row in result['rows']))
    return result


def apply(body, data):
    result = preview(body, data)
    decisions = body.get('decisions')
    if not isinstance(decisions, list) or not decisions or len(decisions) > len(result['rows']):
        raise _invalid()
    out, count, seen, created = deepcopy(data), 0, set(), set()
    by_uid = {finding.get('uid'): finding for finding in out.get('findings', [])}
    for decision in decisions:
        if not isinstance(decision, dict) or set(decision) - {'index', 'action', 'finding_uid', 'instance_uid', 'fields'}:
            raise _invalid()
        index, action = decision.get('index'), decision.get('action')
        if type(index) is not int or index < 0 or index >= len(result['rows']) or index in seen or action not in ('create', 'attach', 'skip'):
            raise _invalid()
        seen.add(index)
        if action == 'skip':
            if set(decision) - {'index', 'action'}:
                raise _invalid()
            continue
        row = result['rows'][index]
        if row['errors']:
            raise _invalid()
        incoming, fields = row['finding'], decision.get('fields', [])
        key = finding_imports.source_fingerprint(incoming)
        if action == 'create':
            if set(decision) - {'index', 'action'} or key in created or row['match'] == 'exact':
                raise _invalid()
            finding = deepcopy(incoming)
            finding.update(uid=workflows.new_uid(), id=workflows.allocate_finding_id(out))
            finding['import_source']['imported_at'] = now()
            out['findings'].append(finding)
            created.add(key)
        else:
            if not isinstance(decision.get('finding_uid'), str):
                raise _invalid()
            finding = by_uid.get(decision['finding_uid'])
            instance_uid = decision.get('instance_uid', '')
            if (finding is None or not isinstance(instance_uid, str) or instance_uid and instance_uid not in {item['uid'] for item in finding.get('instances', [])}
                    or not isinstance(fields, list) or any(not isinstance(field, str) or field not in COPY_FIELDS for field in fields) or len(set(fields)) != len(fields)):
                raise _invalid()
            if finding.get('mode') == 'machine' and any(field not in MACHINE_COPY_FIELDS for field in fields):
                raise _invalid()
            snapshot = _snapshot(incoming)
            identity = _digest([incoming['import_source'], snapshot, instance_uid])
            if any(_digest([item['source'], item['snapshot'], item['instance_uid']]) == identity for item in finding.get('import_observations', [])):
                raise ValueError(message('Esta observación ya está adjunta; omítela', en='This observation is already attached; skip it', pt='Esta observação já está anexada; ignore-a'))
            finding.setdefault('import_observations', []).append(dict(uid=workflows.new_uid(), imported_at=now(), instance_uid=instance_uid,
                source=deepcopy(incoming['import_source']), snapshot=snapshot, selected_fields=deepcopy(fields)))
            for field in fields:
                if field == 'walkthrough':
                    # Adding evidence never destroys the analyst's reproduction.
                    if finding.get('mode') == 'machine':
                        finding.setdefault('phases', []).append(dict(name='Import: ' + incoming['import_source']['format'], steps=deepcopy(snapshot[field])))
                    else:
                        finding.setdefault('walkthrough', []).extend(deepcopy(snapshot[field]))
                else:
                    finding[field] = deepcopy(snapshot[field])
        count += 1
    if not count:
        raise ValueError(message('No hay observaciones seleccionadas', en='No observations selected', pt='Nenhuma observação selecionada'))
    ensure_data_tree(out)
    errors = structure_errors(out)
    if errors:
        raise ValueError(errors[0][1])
    return out, count
