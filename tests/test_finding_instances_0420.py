"""Independent occurrence closure, preserved observations and revision safety."""
from copy import deepcopy

import pytest

import app as api
import engine
import finding_instances as instances
import project_history
import workflows
from _support import auth_client


def model():
    asset, evidence, finding = [workflows.new_uid() for _ in range(3)]
    return {'assets': [{'uid': asset, 'name': 'Fictional API'}],
            'evidence': [{'uid': evidence, 'title': 'Reviewed response', 'src': 'img/response.png'}],
            'findings': [{'uid': finding, 'id': 'F1', 'title': 'Authorization', 'status': 'open', 'instances':
                [instances.new_instance({'asset_uid': asset, 'endpoint': '/account/'+str(index), 'status': 'open', 'evidence_uids': [evidence]}) for index in range(18)]}]}


def retest(data, index, result='fixed', when='2026-10-17'):
    finding = data['findings'][0]
    return instances.record_retest(data, finding, finding['instances'][index]['uid'],
        {'tested_on': when, 'assessor': 'Synthetic tester', 'notes_md': 'Compared permitted and rejected responses.',
         'result': result, 'evidence_uids': [data['evidence'][0]['uid']]}, '2026-10-17T05:00:00+00:00')


def test_eighteen_instances_preserve_fifteen_fixed_two_open_one_blocked():
    data = model()
    for index in range(15): retest(data, index)
    data['findings'][0]['instances'][17]['status'] = 'blocked'
    report = instances.summary(data['findings'][0], 'en')
    assert report['total'] == 18
    assert report['counts']['verified_fixed'] == 15
    assert report['counts']['open'] == 2
    assert report['counts']['blocked'] == 1
    assert report['status'] == 'in_progress'
    assert not instances.structure_errors(data)
    for index in range(15, 18): retest(data, index)
    assert data['findings'][0]['status'] == 'verified_fixed'
    retest(data, 3, 'open', '2026-10-18')
    assert data['findings'][0]['status'] == 'in_progress'
    assert len(data['findings'][0]['instances'][3]['retests']) == 2


def test_backdated_observation_does_not_overwrite_latest_result():
    data = model()
    retest(data, 0, 'open', '2026-10-17')
    retest(data, 0, 'fixed', '2026-10-16')
    assert data['findings'][0]['instances'][0]['status'] == 'open'
    retest(data, 0, 'fixed', '2026-10-17')
    assert data['findings'][0]['instances'][0]['status'] == 'verified_fixed'


def test_literal_publication_redactions_preserve_retest_result_and_closure():
    import publication
    data = model()
    retest(data, 0)
    data['findings'][0]['instances'][0]['notes_md'] = 'fixed in this explanatory text'
    data['publication'] = {'redactions': [{'needle': 'fixed', 'replacement': 'masked'}]}
    before = deepcopy(data)
    projected = publication.project(data)
    instance = projected['findings'][0]['instances'][0]
    assert instance['retests'][0]['result'] == 'fixed'
    assert instance['status'] == 'verified_fixed'
    assert instance['notes_md'] == 'masked in this explanatory text'
    assert not instances.structure_errors(projected)
    assert data == before


@pytest.mark.parametrize('mutate', [
    lambda data: data['findings'][0]['instances'][0].update(asset_uid=workflows.new_uid()),
    lambda data: data['findings'][0]['instances'][0].update(evidence_uids=['missing']),
    lambda data: data['findings'][0]['instances'][0].update(evidence_uids=[[]]),
    lambda data: data['findings'][0]['instances'][0].update(evidence_uids=[data['evidence'][0]['uid']]*2),
    lambda data: data['findings'][0]['instances'][0].update(uid=data['assets'][0]['uid']),
    lambda data: data['findings'][0]['instances'][1].update(uid=data['findings'][0]['instances'][0]['uid']),
    lambda data: data['findings'][0]['instances'][0].update(status='verified_fixed'),
    lambda data: data['findings'][0].update(status='verified_fixed'),
    lambda data: data['findings'][0].update(status='accepted'),
    lambda data: data['findings'][0].update(status='reported_fixed'),
    lambda data: data['findings'][0]['instances'][0].update(status={}),
    lambda data: data['findings'][0]['instances'][0].update(due_date='2026-02-30'),
    lambda data: data['findings'][0]['instances'][0].update(endpoint='a'*2049),
    lambda data: data['findings'][0]['instances'][0].update(owner='a\u202eb'),
    lambda data: data['findings'][0]['instances'][0].update(owner='\ud800'),
    lambda data: data['findings'][0]['instances'][0].update(unexpected='field'),
    lambda data: data['findings'][0].update(instances=[{}]*501),
    lambda data: data['findings'][0]['instances'][0].update(asset_uid='', endpoint=''),
])
def test_invalid_schema_and_references_rejected_without_mutation(mutate):
    data = model(); mutate(data); before = deepcopy(data)
    assert instances.structure_errors(data)
    assert data == before


@pytest.mark.parametrize('values', [
    {'tested_on': [], 'assessor': 'A', 'notes_md': 'Observed', 'result': 'fixed'},
    {'tested_on': '2026-02-30', 'assessor': 'A', 'notes_md': 'Observed', 'result': 'fixed'},
    {'tested_on': '2026-10-17', 'assessor': '', 'notes_md': 'Observed', 'result': 'fixed'},
    {'tested_on': '2026-10-17', 'assessor': 'A', 'notes_md': 'Observed', 'result': []},
    {'tested_on': '2026-10-17', 'assessor': 'A', 'notes_md': 'Observed', 'result': 'fixed', 'evidence_uids': ['missing']},
])
def test_failed_retest_preserves_in_memory_model(values):
    data = model(); before = deepcopy(data)
    with pytest.raises(ValueError):
        instances.record_retest(data, data['findings'][0], data['findings'][0]['instances'][0]['uid'], values, '2026-10-17T05:00:00+00:00')
    assert data == before


def test_legacy_and_projection_are_read_only():
    legacy = {'findings': [{'title': 'Legacy', 'status': 'verified_fixed', 'asset_uids': [workflows.new_uid()]}]}
    before = deepcopy(legacy)
    assert instances.structure_errors(legacy) == []
    assert instances.aggregate_status(legacy['findings'][0]) == 'verified_fixed'
    assert legacy == before
    data = model(); retest(data, 0); before = deepcopy(data)
    for lang in ('es', 'en', 'pt-BR'):
        projection = instances.export_rows(data, data['findings'][0], lang)
        assert len(projection['rows']) == 18
        assert all(isinstance(cell, str) for row in projection['rows'] for cell in row)
        assert projection['summary']['counts']['verified_fixed'] == 1
    assert data == before


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'PROJECTS', tmp_path)
    client = auth_client(api.app)
    assert client.post('/api/projects', json={'slug': 'instances', 'title': 'Synthetic instances'}).status_code == 200
    data = client.get('/api/projects/instances').json
    data['findings'] = [{'uid': workflows.new_uid(), 'id': 'F1', 'title': 'Synthetic finding', 'mode': 'vuln', 'severity': 'low', 'status': 'open'}]
    assert client.put('/api/projects/instances', json=data).status_code == 200
    return client, tmp_path/'instances', data['findings'][0]['uid']


def call(project, method, suffix='', body=None, etag=None):
    client, _, finding_uid = project
    return client.open('/api/projects/instances/findings/'+finding_uid+'/instances'+suffix, method=method, json=body,
                       headers={'If-Match': etag or client.get('/api/projects/instances').headers['ETag']})


def files(directory):
    return {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob('*') if path.is_file()}


def test_api_cas_roundtrip_history_and_independent_retest(project):
    client, directory, finding_uid = project
    before = client.get('/api/projects/instances').headers['ETag']
    created = call(project, 'POST', body={'endpoint': '/one', 'owner': 'Team A'})
    assert created.status_code == 200, created.json
    uid = created.json['instance']['uid']
    assert call(project, 'POST', body={'endpoint': '/two'}).status_code == 200
    snapshot = files(directory)
    assert call(project, 'PUT', '/'+uid, {'owner': 'Stale'}, before).status_code == 409
    assert files(directory) == snapshot
    result = call(project, 'POST', '/'+uid+'/retests', {'tested_on': '2026-10-17', 'assessor': 'Tester', 'notes_md': 'Fixed in isolated test.', 'result': 'fixed'})
    assert result.status_code == 200, result.json
    assert result.json['data']['findings'][0]['status'] == 'in_progress'
    assert result.json['summary']['counts']['open'] == 1
    assert result.json['summary']['counts']['verified_fixed'] == 1
    persisted = engine.load_engagement(directory/'engagement.yaml')
    assert persisted == result.json['data']
    assert len(project_history.history(directory)) >= 4
    assert client.post('/api/projects/instances/retest', json={'finding_uid': finding_uid, 'tested_on': '2026-10-18', 'assessor': 'Tester', 'notes_md': 'General observation.', 'result': 'fixed'}, headers={'If-Match': result.headers['ETag']}).json['data']['findings'][0]['status'] == 'in_progress'


def test_api_full_project_cannot_bypass_closure_rules(project):
    client, directory, _ = project
    assert call(project, 'POST', body={'endpoint': '/open'}).status_code == 200
    data = client.get('/api/projects/instances').json
    data['findings'][0]['status'] = 'verified_fixed'
    before = files(directory)
    assert client.put('/api/projects/instances', json=data).status_code == 422
    assert files(directory) == before


def test_api_metadata_cannot_rewrite_observations_and_delete_requires_ack(project):
    _, directory, _ = project
    uid = call(project, 'POST', body={'endpoint': '/one'}).json['instance']['uid']
    before = files(directory)
    assert call(project, 'PUT', '/'+uid, {'retests': []}).status_code == 422
    assert call(project, 'DELETE', '/'+uid, {}).status_code == 422
    assert files(directory) == before
    result = call(project, 'DELETE', '/'+uid, {'ack_delete': True})
    assert result.status_code == 200
    assert result.json['instances'] == []


def test_api_retest_failure_never_writes(project):
    _, directory, _ = project
    uid = call(project, 'POST', body={'endpoint': '/one'}).json['instance']['uid']
    before = files(directory)
    result = call(project, 'POST', '/'+uid+'/retests', {'tested_on': [], 'assessor': 'Tester', 'notes_md': 'Synthetic', 'result': 'fixed'})
    assert result.status_code == 422
    assert files(directory) == before


def test_removing_referenced_asset_or_evidence_and_duplicated_identity_rejected():
    data = model()
    for key in ('assets', 'evidence'):
        removed = deepcopy(data); removed[key].clear()
        assert instances.structure_errors(removed)
    copied = deepcopy(data); copied['findings'].append(deepcopy(copied['findings'][0]))
    copied['findings'][1]['uid'] = workflows.new_uid()
    assert any('.uid:' in text for _, text in instances.structure_errors(copied))


def test_matrix_general_fixed_observation_cannot_hide_outstanding_instances():
    import retest_summary
    data = model()
    data['findings'][0]['retests'] = [{'uid': workflows.new_uid(), 'tested_on': '2026-10-17', 'assessor': 'General reviewer', 'notes_md': 'General observation.', 'result': 'fixed'}]
    for index in range(15): retest(data, index)
    data['findings'][0]['instances'][17]['status'] = 'blocked'
    result = retest_summary.summarize(data, 'en')
    row = result['rows'][0]
    assert row['outcome'] == 'instances_partial'
    assert row['status'] == 'in_progress'
    assert row['latest'] is None
    assert row['general_latest']['assessor'] == 'General reviewer'
    assert row['instance_summary']['counts']['verified_fixed'] == 15
    assert row['instance_summary']['counts']['blocked'] == 1
    assert row['assets']['registered'] == 1
    assert result['result_counts']['fixed'] == 0
    assert result['result_counts']['instances_partial'] == 1
    for index in range(15,18): retest(data,index)
    assert retest_summary.summarize(data)['rows'][0]['outcome'] == 'instances_fixed'
