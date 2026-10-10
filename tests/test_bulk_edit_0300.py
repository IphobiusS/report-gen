"""One reviewed assignment, immutable technical evidence and recoverable history."""
from copy import deepcopy

import pytest

import app as api
import bulk_api
import engine
import project_history
import workflows
from _support import auth_client


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'PROJECTS', tmp_path)
    client = auth_client(api.app)
    assert client.post('/api/projects', json={'slug': 'bulk', 'title': 'Synthetic bulk'}).status_code == 200
    data = client.get('/api/projects/bulk').json
    data['root_cause_groups'] = [{'uid': workflows.new_uid(), 'name': 'Shared policy', 'remediation_md': 'Shared fix'}]
    data['findings'] = [dict(uid=workflows.new_uid(), id='F'+str(i+1), mode='vuln', title='Synthetic '+str(i),
                            severity='low', owner='Original', due_date='2026-10-20', status='open',
                            verification='confirmed', description_md='Technical text',
                            retests=[dict(uid=workflows.new_uid(), tested_on='2026-10-01', assessor='Tester',
                                          result='open', notes_md='Still reproducible')]) for i in range(3)]
    assert client.put('/api/projects/bulk', json=data).status_code == 200
    data = client.get('/api/projects/bulk').json
    return client, tmp_path/'bulk', data


def payload(data, **values):
    return dict(finding_uids=[f['uid'] for f in data['findings'][:2]], values=values or {'owner': 'New owner'})


def call(client, operation, body, tag=None):
    return client.post('/api/projects/bulk/bulk-edit/'+operation, json=body,
                       headers={'If-Match': tag or client.get('/api/projects/bulk').headers['ETag']})


def files(directory):
    return {str(p.relative_to(directory)):p.read_bytes() for p in directory.rglob('*') if p.is_file()}


def test_read_only_preview_and_one_recoverable_atomic_version(project):
    client, directory, data = project
    proposal = payload(data, owner='New owner', due_date='2026-11-20', root_cause_uid=data['root_cause_groups'][0]['uid'])
    before = files(directory)
    preview = call(client, 'preview', proposal)
    assert preview.status_code == 200, preview.json
    assert len(preview.json['changes']) == 6
    assert files(directory) == before
    old_history = project_history.history(directory)
    result = call(client, 'apply', {**proposal, 'preview_token': preview.json['preview_token'], 'ack_reviewed': True})
    assert result.status_code == 200, result.json
    expected = deepcopy(data)
    for finding in expected['findings'][:2]:
        finding.update(proposal['values'])
    assert result.json['data'] == expected
    assert engine.load_engagement(directory/'engagement.yaml') == expected
    history = project_history.history(directory)
    assert len(history) == len(old_history)+1
    assert project_history.snapshot_data(directory, history[1]['id']) == data
    assert project_history.snapshot_data(directory, history[0]['id']) == expected


@pytest.mark.parametrize('values', [{'status': 'verified_fixed'}, {'verification': 'confirmed'}, {'retests': []},
                                  {'owner': None}, {'owner': ' '}, {'owner': 'a'*201}, {'owner': 'a\x0bb'},
                                  {'owner': 'a\u202eb'}, {'owner': '\ud800'}, {'due_date': '2026-02-30'}, {'due_date': '20260101'},
                                  {'root_cause_uid': 'missing'}, {}])
def test_rejected_values_preserve_entire_project(project, values):
    client, directory, data = project
    before = files(directory)
    body = payload(data)
    body['values'] = values
    assert call(client, 'preview', body).status_code == 422
    assert files(directory) == before


@pytest.mark.parametrize('selection', [[], ['missing'], ['duplicate', 'duplicate'], [None], 'all', ['uid']*501])
def test_invalid_selection_never_partially_applies(project, selection):
    client, directory, data = project
    before = files(directory)
    body = payload(data)
    body['finding_uids'] = selection
    assert call(client, 'preview', body).status_code == 422
    assert files(directory) == before


def test_explicit_clearing_only_selected_fields(project):
    client, _, data = project
    body = payload(data, owner='', due_date='', root_cause_uid='')
    preview = call(client, 'preview', body)
    result = call(client, 'apply', {**body, 'preview_token': preview.json['preview_token'], 'ack_reviewed': True})
    assert result.status_code == 200
    expected = deepcopy(data)
    for finding in expected['findings'][:2]:
        finding.pop('owner')
        finding.pop('due_date')
    assert result.json['data'] == expected


def test_csrf_revision_and_signed_review_are_required(project):
    client, directory, data = project
    body = payload(data)
    preview = call(client, 'preview', body)
    reviewed = {**body, 'preview_token': preview.json['preview_token'], 'ack_reviewed': True}
    before = files(directory)
    assert api.app.test_client().post('/api/projects/bulk/bulk-edit/preview', json=body).status_code == 403
    assert client.post('/api/projects/bulk/bulk-edit/preview', json=body).status_code == 428
    assert call(client, 'apply', reviewed, 'stale').status_code == 409
    assert call(client, 'apply', {**reviewed, 'values': {'owner': 'Unreviewed'}}).status_code == 409
    assert call(client, 'apply', {**reviewed, 'finding_uids': [data['findings'][2]['uid']]}).status_code == 409
    assert call(client, 'apply', {**reviewed, 'ack_reviewed': False}).status_code == 422
    assert call(client, 'apply', {**reviewed, 'preview_token': '\u00f1'}).status_code == 409
    assert files(directory) == before


def test_changed_revision_requires_new_review_and_replay_fails(project):
    client, _, data = project
    body = payload(data)
    preview = call(client, 'preview', body)
    reviewed = {**body, 'preview_token': preview.json['preview_token'], 'ack_reviewed': True}
    data['findings'][0]['title'] = 'Edited elsewhere'
    assert client.put('/api/projects/bulk', json=data).status_code == 200
    assert call(client, 'apply', reviewed).status_code == 409
    preview = call(client, 'preview', body)
    reviewed['preview_token'] = preview.json['preview_token']
    assert call(client, 'apply', reviewed).status_code == 200
    assert call(client, 'apply', reviewed).status_code == 409


def test_noop_is_explicit_and_creates_no_history(project):
    client, directory, data = project
    body = payload(data, owner='Original')
    before = files(directory)
    preview = call(client, 'preview', body)
    assert preview.json['changes'] == []
    assert call(client, 'apply', {**body, 'preview_token': preview.json['preview_token'], 'ack_reviewed': True}).status_code == 422
    assert files(directory) == before


def test_write_failure_leaves_all_findings_and_history_unchanged(project, monkeypatch):
    client, directory, data = project
    body = payload(data)
    preview = call(client, 'preview', body)
    before = files(directory)
    import wizard
    real_dump = wizard.dump_yaml
    def fail(data, path):
        real_dump(data, path)
        raise OSError('Synthetic disk error after staged write')
    monkeypatch.setattr(wizard, 'dump_yaml', fail)
    result = call(client, 'apply', {**body, 'preview_token': preview.json['preview_token'], 'ack_reviewed': True})
    assert result.status_code >= 400
    assert files(directory) == before


def test_pure_plan_never_mutates_input():
    identity = workflows.new_uid()
    data = {'findings': [{'uid': identity, 'title': 'A', 'owner': 'Before'}]}
    before = deepcopy(data)
    assert bulk_api.plan(data, [identity], {'owner': 'After'})[0]['before'] == 'Before'
    assert data == before


@pytest.mark.parametrize('identity', [None, 'invalid', 'duplicate'])
def test_legacy_or_ambiguous_unselected_identity_is_rejected_without_normalizing(identity):
    uid = workflows.new_uid()
    data = {'findings': [{'uid': uid, 'id': 'F1'}, {'id': 'F2'}]}
    if identity is not None:
        data['findings'][1]['uid'] = uid if identity == 'duplicate' else identity
    before = deepcopy(data)
    with pytest.raises(ValueError, match='identit|identidad'):
        bulk_api.plan(data, [uid], {'owner': 'Reviewed'})
    assert data == before


def test_group_comparison_explains_effective_shared_action_without_overwriting_specific(project):
    _, _, data = project
    data['findings'][0]['remediation_md'] = 'Specific fix stays authoritative'
    changes = bulk_api.plan(data, [f['uid'] for f in data['findings'][:2]],
                            {'root_cause_uid': data['root_cause_groups'][0]['uid']})
    assert changes[0]['effective_action_before'] == changes[0]['effective_action_after'] == 'Specific fix stays authoritative'
    assert changes[1]['effective_action_before'] == ''
    assert changes[1]['effective_action_after'] == 'Shared fix'


def test_api_legacy_unselected_uid_is_a_read_only_actionable_error(project):
    client, directory, data = project
    from storage import revision
    from wizard import dump_yaml
    body = {'finding_uids': [data['findings'][0]['uid']], 'values': {'owner': 'Reviewed'}}
    data['findings'][1].pop('uid')
    dump_yaml(data, directory/'engagement.yaml')
    before = files(directory)
    response = call(client, 'preview', body, '"'+revision(directory/'engagement.yaml')+'"')
    assert response.status_code == 422
    assert 'identit' in response.json['error'] or 'identidad' in response.json['error']
    assert files(directory) == before
