"""Audit regressions: dated retests, private history labels and occurrence links."""
from copy import deepcopy

import pytest
from PIL import Image

import app as api
import project_history
import readiness
import insights
import remediation_return
import workflows
from _support import auth_client
from wizard import dump_yaml


def document():
    return workflows.normalize({'meta': {'report_title': 'Synthetic audit', 'lang': 'en'},
        'report': {'sections': [{'key': 'findings'}]}, 'findings': [
            {'uid': workflows.new_uid(), 'id': 'F1', 'mode': 'vuln', 'title': 'Synthetic finding',
             'description_md': 'Controlled observation', 'impact_md': 'Synthetic impact',
             'remediation_md': 'Check the boundary', 'walkthrough': [{'text_md': 'Repeat the test'}]}]})


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'PROJECTS', tmp_path)
    directory = tmp_path / 'audit'; directory.mkdir()
    data = document(); dump_yaml(data, directory / 'engagement.yaml')
    return auth_client(api.app), directory, data


@pytest.mark.parametrize('current,older,status', [
    ('open', 'fixed', 'open'), ('fixed', 'open', 'verified_fixed'),
    ('partial', 'fixed', 'in_progress'), ('not_verified', 'fixed', 'not_verified')])
def test_general_retest_status_uses_latest_test_date(project, current, older, status):
    client, _, data = project
    for when, result in [('2026-10-17', current), ('2026-10-16', older)]:
        response = client.post('/api/projects/audit/retest', json={
            'finding_uid': data['findings'][0]['uid'], 'tested_on': when,
            'assessor': 'Synthetic assessor', 'result': result,
            'notes_md': 'Controlled observation', 'evidence_uids': []},
            headers={'If-Match': client.get('/api/projects/audit').headers['ETag']})
        assert response.status_code == 200, response.json
    finding = response.json['data']['findings'][0]
    assert len(finding['retests']) == 2
    assert workflows.latest_retest(finding)['result'] == current
    assert finding['status'] == status


@pytest.mark.parametrize('when', [['2026-10-18'], 20261018, '2026-02-30'])
def test_invalid_retest_date_cannot_mutate_or_crash(project, when):
    client, directory, data = project
    tag = client.get('/api/projects/audit').headers['ETag']
    before = (directory / 'engagement.yaml').read_bytes()
    response = client.post('/api/projects/audit/retest', json={
        'finding_uid': data['findings'][0]['uid'], 'tested_on': when,
        'assessor': 'Synthetic assessor', 'result': 'fixed', 'notes_md': 'Synthetic'},
        headers={'If-Match': tag})
    assert response.status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before


@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
@pytest.mark.parametrize('target', ['current', 'snapshot'])
def test_shared_history_comparison_omits_private_snapshot_labels(project, language, target):
    client, directory, data = project
    old = project_history.checkpoint(directory, 'PRIVATE_OLD_LABEL_0450', 'delivered', True)
    data['findings'][0]['title'] = 'Updated finding'
    dump_yaml(data, directory / 'engagement.yaml')
    new = project_history.checkpoint(directory, 'PRIVATE_NEW_LABEL_0450', 'retest', True)
    url = '/api/projects/audit/history/' + old['id'] + '/visual?lang=' + language
    if target == 'snapshot':
        url += '&to=' + new['id']
    before = (directory / 'engagement.yaml').read_bytes()
    response = client.get(url + '&download=1')
    assert response.status_code == 200
    assert b'PRIVATE_OLD_LABEL_0450' not in response.data
    assert b'PRIVATE_NEW_LABEL_0450' not in response.data
    assert old['id'].encode() in response.data
    internal = client.get(url + '&internal=1&download=1&ack_private=1')
    assert internal.status_code == 200
    assert b'PRIVATE_OLD_LABEL_0450' in internal.data
    assert (directory / 'engagement.yaml').read_bytes() == before


@pytest.mark.parametrize('lang', ['es', 'en', 'pt'])
def test_readiness_counts_instance_and_instance_retest_evidence(tmp_path, lang):
    data = document()
    (tmp_path / 'img').mkdir()
    evidence = []
    for name in ('occurrence', 'retest', 'unlinked'):
        Image.new('RGB', (20, 20), 'blue').save(tmp_path / 'img' / (name + '.png'))
        evidence.append({'uid': workflows.new_uid(), 'src': 'img/' + name + '.png', 'title': name})
    data['evidence'] = evidence
    data['findings'][0]['instances'] = [{'uid': workflows.new_uid(), 'endpoint': 'https://synthetic.example',
        'status': 'open', 'evidence_uids': [evidence[0]['uid']], 'retests': [
            {'uid': workflows.new_uid(), 'tested_on': '2026-10-17', 'assessor': 'Synthetic assessor',
             'notes_md': 'Controlled observation', 'result': 'open', 'evidence_uids': [evidence[1]['uid']]}]}]
    data['findings'][0]['status'] = 'open'
    before = deepcopy(data)
    result = readiness.checklist(data, tmp_path, [], lang)
    check = next(item for item in result['checks'] if item['key'] == 'associations')
    assert check['counts']['without_explicit_association'] == 1
    assert data == before


@pytest.mark.parametrize('uid', [[], {}, ['bad'], {'bad': True}])
def test_malformed_instance_identity_is_validation_error_without_write(project, uid):
    client, directory, data = project
    tag = client.get('/api/projects/audit').headers['ETag']
    before = (directory / 'engagement.yaml').read_bytes()
    data['findings'][0]['instances'] = [{'uid': uid, 'endpoint': 'https://synthetic.example', 'status': 'open'}]
    response = client.put('/api/projects/audit', json=data, headers={'If-Match': tag})
    assert response.status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before


def test_remediation_issuance_does_not_share_existing_batches():
    data = document()
    finding = data['findings'][0]; finding['owner'] = 'Synthetic owner'
    first, _ = remediation_return.issue(data, 'audit', [finding['uid']])
    before = deepcopy(first)
    second, _ = remediation_return.issue(first, 'audit', [finding['uid']])
    second['remediation_exchanges'][0]['rows'][0]['base']['owner'] = 'Changed copy'
    assert first == before


def test_insights_mutation_does_not_share_caller_reference_list():
    data = document(); evidence_uid = workflows.new_uid()
    data['evidence'] = [{'uid': evidence_uid, 'src': 'img/synthetic.png'}]
    body = {'action': 'set_claim', 'finding_uid': data['findings'][0]['uid'],
            'statement': 'Synthetic observation', 'evidence_uids': [evidence_uid]}
    result = insights.mutate(data, body, 'a' * 64)
    result['insights']['claims'][0]['evidence_uids'].clear()
    assert body['evidence_uids'] == [evidence_uid]
    assert 'insights' not in data


def test_unknown_insights_action_is_rejected_before_mutation():
    data = document(); before = deepcopy(data)
    with pytest.raises(ValueError):
        insights.mutate(data, {'action': 'unknown'}, 'a' * 64)
    assert data == before


@pytest.mark.parametrize('edges', [None, True, 1])
def test_malformed_attack_path_edges_with_figures_return_validation_error(project, edges):
    client, directory, data = project
    tag = client.get('/api/projects/audit').headers['ETag']
    before = (directory / 'engagement.yaml').read_bytes()
    uid, digest = workflows.new_uid(), 'a' * 64
    data['attack_paths'] = [{'uid': uid, 'title': 'Synthetic path', 'nodes': [], 'edges': edges}]
    data['attack_path_figures'] = [{'path_uid': uid, 'src': f'img/rg-attack-{uid}-001-{digest[:16]}.png',
        'sha256': digest, 'part': 1, 'parts': 1}]
    response = client.put('/api/projects/audit', json=data, headers={'If-Match': tag})
    assert response.status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before
