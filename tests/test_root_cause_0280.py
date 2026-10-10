"""Groups preserve independent evidence and history across saves and exports."""
from copy import deepcopy
import json

import pytest

import app
import audience
import engine
import export
import export_contract
import finding_library
import project_history
import root_cause
import validate
import workflows
from _support import auth_client
from wizard import dump_yaml


def document():
    group = dict(uid=workflows.new_uid(), name='Control de acceso común',
                 cause_md='El servicio omite la autorización de objetos.',
                 remediation_md='Aplicar autorización por propietario en el servicio.')
    other = dict(uid=workflows.new_uid(), name='PRIVATE_GROUP_0280',
                 cause_md='PRIVATE_CAUSE_0280', remediation_md='PRIVATE_ACTION_0280')
    findings = []
    for number in range(1, 4):
        findings.append(dict(uid=workflows.new_uid(), id=f'F{number}', mode='vuln',
            title=f'Objeto independiente {number}', severity='info', cvss=0,
            description_md=f'Observación específica {number}.', impact_md='Acceso indebido.',
            remediation_md=f'Corregir ruta {number}.', root_cause_uid=group['uid'] if number < 3 else other['uid'],
            closure_criteria_md=f'Cuenta ajena recibe 403 en ruta {number}.',
            walkthrough=[dict(text_md=f'Solicitar ruta {number} con dos cuentas.')],
            evidence_uids=[], retests=[dict(uid=workflows.new_uid(), result='open',
                tested_on='2026-10-10', assessor=f'Evaluador {number}',
                notes_md=f'Resultado independiente {number}.', evidence_uids=[])]))
    return workflows.normalize(dict(meta=dict(report_title='Agrupación sintética', lang='es', theme='serio'),
        report=dict(sections=[dict(key='findings')]), findings=findings, root_cause_groups=[group, other]))


def test_group_relationship_roundtrip_history_restore_and_portable_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'PROJECTS', tmp_path)
    client = auth_client(app.app)
    assert client.post('/api/projects', json={'slug': 'groups', 'title': 'Groups'}).status_code == 200
    data = document()
    evidence = dict(uid=workflows.new_uid(), title='Evidencia separada', src='img/proof.png')
    from PIL import Image
    directory = tmp_path / 'groups'
    (directory / 'img').mkdir(exist_ok=True)
    Image.new('RGB', (12, 12), 'blue').save(directory / 'img/proof.png')
    data['evidence'] = [evidence]
    data['findings'][0]['evidence_uids'] = [evidence['uid']]
    data['findings'][1]['retests'][0]['evidence_uids'] = [evidence['uid']]
    response = client.put('/api/projects/groups', json=data)
    assert response.status_code == 200, response.get_json()
    saved = client.get('/api/projects/groups').get_json()
    assert saved == data
    snapshot = project_history.checkpoint(directory, 'Agrupación entregada', 'delivered')
    changed = deepcopy(data)
    changed['findings'][0]['root_cause_uid'] = changed['root_cause_groups'][1]['uid']
    changed['root_cause_groups'][0]['name'] = 'Nombre revisado'
    assert client.put('/api/projects/groups', json=changed).status_code == 200
    after = client.get('/api/projects/groups').get_json()
    for original, current in zip(data['findings'], after['findings']):
        assert {k: v for k, v in current.items() if k != 'root_cause_uid'} == {
            k: v for k, v in original.items() if k != 'root_cause_uid'}
    blob = project_history.export_bundle(directory)
    project_history.import_bundle(blob, tmp_path / 'restored')
    assert engine.load_engagement(tmp_path / 'restored/engagement.yaml') == changed
    project_history.restore(directory, snapshot['id'])
    assert engine.load_engagement(directory / 'engagement.yaml') == data
    assert any(project_history.snapshot_data(directory, row['id']).get('root_cause_groups') == changed['root_cause_groups']
               for row in project_history.history(directory))


@pytest.mark.parametrize('mutation', [
    lambda d: d.update(root_cause_groups='invalid'),
    lambda d: d['root_cause_groups'].append(deepcopy(d['root_cause_groups'][0])),
    lambda d: d['root_cause_groups'][0].update(uid=d['findings'][0]['uid']),
    lambda d: d['root_cause_groups'][0].update(cause_md=[]),
    lambda d: d['root_cause_groups'][0].update(name='x' * 201),
    lambda d: d['findings'][0].update(root_cause_uid=workflows.new_uid()),
    lambda d: d['findings'][0].update(root_cause_uid=None),
    lambda d: d['findings'][0].update(closure_criteria_md=[]),
    lambda d: d['report'].update(workflow={'include_root_causes': 'yes'}),
])
def test_invalid_or_dangling_relationships_rejected_before_save(mutation):
    data = document()
    mutation(data)
    assert validate.structure_issues(data)


def test_legacy_projects_stay_unchanged_and_library_has_no_project_relationship():
    legacy = dict(meta={}, findings=[dict(id='F1', title='Legacy')])
    assert not validate.structure_issues(legacy)
    before = deepcopy(legacy)
    assert root_cause.group_for_finding(legacy, legacy['findings'][0]) is None
    assert workflows.report_sections(legacy) == []
    assert legacy == before
    data = document()
    safe = finding_library.sanitize(data['findings'][0])
    assert 'root_cause_uid' not in safe and 'closure_criteria_md' not in safe
    assert not validate.structure_issues(dict(meta={}, findings=[dict(safe, id='F1')]))


def test_shared_action_is_fallback_and_does_not_overwrite_individual_remediation():
    data = document()
    before = deepcopy(data)
    finding = data['findings'][0]
    assert root_cause.resolved_action(data, finding) == finding['remediation_md']
    assert root_cause.resolved_action(data, dict(finding, remediation_md='  ')) == data['root_cause_groups'][0]['remediation_md']
    assert root_cause.resolved_action(data, dict(finding, remediation_md=None)) == data['root_cause_groups'][0]['remediation_md']
    assert data == before


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_opt_in_shared_section_exports_with_independent_findings_and_redactions(tmp_path, fmt):
    import delivery
    data = document()
    data['root_cause_groups'][0]['cause_md'] += ' REDACT_GROUP_0280'
    data['publication'] = {'redactions': [{'needle': 'REDACT_GROUP_0280', 'replacement': '[CENSURADO]'}]}
    assert not any(s['key'] == 'rg_root_causes' for s in workflows.report_sections(data))
    data['report']['workflow'] = {'include_root_causes': True}
    before = deepcopy(data)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    original = (tmp_path / 'engagement.yaml').read_bytes()
    target = export.export(tmp_path / 'engagement.yaml', fmt, tmp_path / ('report.' + delivery.get(fmt).extension))
    profile = export_contract.profile(target, fmt)
    text = profile['text']
    assert 'Causas raíz y acciones comunes' in text
    assert 'Control de acceso común' in text and 'Aplicar autorización por propietario' in text
    assert 'REDACT_GROUP_0280' not in text and 'CENSURADO' in text
    for number in range(1, 4):
        assert f'Objeto independiente {number}' in text
        assert f'Resultado independiente {number}' in text
        assert f'Corregir ruta {number}' in text
    assert data == before and (tmp_path / 'engagement.yaml').read_bytes() == original


def test_technical_selection_omits_unselected_groups_and_can_disable_shared_section(tmp_path):
    data = document()
    data['report']['workflow'] = {'include_root_causes': True}
    uid = data['findings'][0]['uid']
    selected, _ = audience.project(data, {'profile': 'technical', 'finding_uids': [uid]})
    assert len(selected['root_cause_groups']) == 1
    body = next(row['body'] for row in workflows.report_sections(selected) if row['key'] == 'rg_root_causes')
    assert 'F1' in body and 'F2' not in body and 'F3' not in body
    assert 'PRIVATE_' not in json.dumps(selected)
    selected, _ = audience.project(data, {'profile': 'technical', 'finding_uids': [uid], 'section_keys': ['findings']})
    assert not any(row['key'] == 'rg_root_causes' for row in workflows.report_sections(selected))
    executive, plan = audience.project(data, {'profile': 'executive', 'finding_uids': [uid]})
    assert 'root_cause_groups' not in executive and 'PRIVATE_' not in json.dumps(executive)
    assert 'root_cause_groups' in plan['excluded']


def test_group_section_anchor_is_reserved_only_when_enabled():
    data = document()
    data['findings'][0]['id'] = 'rg_root_causes'
    assert not any(level == 'error' for level, _ in validate.validate(data))
    data['report']['workflow'] = {'include_root_causes': True}
    assert any(level == 'error' and 'rg_root_causes' in message for level, message in validate.validate(data))
