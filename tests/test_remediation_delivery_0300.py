"""Owner deliveries and bounded events remain private, revision-bound and explicit."""
from copy import deepcopy
import hashlib
import io
import json
import zipfile

import pytest

import remediation_return as returns
import workflows
from test_remediation_return_0290 import project as project
from test_remediation_return_0290 import call, issue_api, propose_api, apply_api, document, issued, edit


def options(data, **kwargs):
    return {'finding_uids': [f['uid'] for f in data['findings']], 'fields': ['id', 'finding_uid', 'title'],
            'lang': 'es', 'ack_private': True, 'ack_retention': True, **kwargs}


def test_delivery_exact_selected_cards_and_owner_csv_from_same_revision():
    data = document()
    data['findings'][0]['title'] = '<script>alert(1)</script>'
    data['findings'][0]['owner'] = '../same<script>'
    data['findings'][0]['description_md'] = 'DO_NOT_INCLUDE_DESCRIPTION'
    data['findings'][0]['reported_remediation'] = 'VISIBLE_IN_RETURN_PREVIEW'
    data['findings'][1]['owner'] = 'Another'
    opts = options(data)
    before = deepcopy(data)
    preview = returns.delivery_preview(data, 'tasks', opts['finding_uids'], opts['fields'], 'es')
    assert data == before
    assert set(preview[0]['card']) == set(opts['fields'])
    assert preview[0]['return_values']['reported_remediation'] == 'VISIBLE_IN_RETURN_PREVIEW'
    updated, blob = returns.delivery(data, 'tasks', opts['finding_uids'], opts['fields'], 'es', 'a'*64)
    assert updated['findings'] == data['findings']
    assert updated['remediation_exchanges'][-1]['events'][-1]['sha256'] == hashlib.sha256(blob).hexdigest()
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert manifest['source_revision'] == 'a'*64
        assert manifest['fields'] == opts['fields']
        assert len(manifest['owners']) == 2
        assert set(archive.namelist()) == {'manifest.json', *manifest['files']}
        for name, expected in manifest['files'].items():
            payload = archive.read(name)
            assert hashlib.sha256(payload).hexdigest() == expected
            assert b'DO_NOT_INCLUDE_DESCRIPTION' not in payload
            assert '..' not in name
            if name.endswith('.html'):
                assert b'<script>' not in payload
                assert b'Content-Security-Policy' in payload
            if name.endswith('.csv'):
                proposal = returns.plan(updated, 'tasks', payload.decode('utf-8-sig'))
                assert proposal['rows'] == 1 and proposal['changes'] == []


def test_same_owner_groups_without_normalizing_distinct_recipients():
    data = document()
    for finding in data['findings']:
        finding['owner'] = 'Team A'
    updated, blob = returns.delivery(data, 'tasks', options(data)['finding_uids'], ['id', 'finding_uid'], 'en', 'b'*64)
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        manifest = json.loads(archive.read('manifest.json'))
        assert len(manifest['owners']) == 1
        assert returns.plan(updated, 'tasks', archive.read('owner-001/return.csv').decode('utf-8'))['rows'] == 2
        assert b'<html lang="en">' in archive.read('owner-001/index.html')


def test_api_delivery_preview_readonly_and_export_bound_to_revision_options(project):
    client, directory, data = project
    before = {p.relative_to(directory): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    opts = options(data)
    preview = call(client, 'delivery-preview', opts)
    assert preview.status_code == 200, preview.json
    assert {p.relative_to(directory): p.read_bytes() for p in directory.rglob('*') if p.is_file()} == before
    body = {**opts, 'preview_token': preview.json['preview_token']}
    assert call(client, 'delivery-export', {**body, 'fields': ['id', 'finding_uid', 'assets']}).status_code == 409
    assert call(client, 'delivery-export', {**body, 'finding_uids': opts['finding_uids'][:1]}).status_code == 409
    assert call(client, 'delivery-export', {**body, 'lang': 'en'}).status_code == 409
    response = call(client, 'delivery-export', body)
    assert response.status_code == 200, response.json
    current = client.get('/api/projects/tasks').json
    assert current['findings'] == data['findings']
    event = current['remediation_exchanges'][-1]['events'][-1]
    assert event['source_revision'] == preview.json['revision']
    assert event['sha256'] == hashlib.sha256(response.data).hexdigest()
    assert call(client, 'delivery-export', body).status_code == 409


@pytest.mark.parametrize('update', [dict(ack_private=False), dict(ack_retention=False), dict(fields=['owner']),
                                   dict(finding_uids=[]), dict(lang='xx'), dict(extra=True)])
def test_delivery_options_reject_without_mutation(project, update):
    client, directory, data = project
    before = (directory / 'engagement.yaml').read_bytes()
    assert call(client, 'delivery-preview', options(data, **update)).status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before


def test_receipt_explicit_idempotent_and_acceptance_has_separate_hash(project):
    client, _, data = project
    response = issue_api(client, data)
    first = client.get('/api/projects/tasks').json['remediation_exchanges'][0]['events'][0]
    assert first['kind'] == 'issued' and first['sha256'] == hashlib.sha256(response.data).hexdigest()
    text = edit(response.data, {'owner': "'A received owner"})
    proposal = propose_api(client, text)
    payload = {'text': text, 'preview_token': proposal.json['preview_token'], 'ack_reviewed': True}
    received = call(client, 'return-receive', payload)
    assert received.status_code == 200, received.json
    assert received.json['data']['findings'] == data['findings']
    events = received.json['data']['remediation_exchanges'][0]['events']
    assert [e['kind'] for e in events] == ['issued', 'received']
    assert events[-1]['sha256'] == proposal.json['file_sha256']
    proposal = propose_api(client, text)
    again = call(client, 'return-receive', {**payload, 'preview_token': proposal.json['preview_token']})
    assert again.status_code == 200
    assert len(again.json['data']['remediation_exchanges'][0]['events']) == 2
    accepted = apply_api(client, text, propose_api(client, text))
    assert accepted.status_code == 200
    events = accepted.json['data']['remediation_exchanges'][0]['events']
    assert [e['kind'] for e in events] == ['issued', 'received', 'accepted']
    assert events[-1]['count'] == 1 and events[-1]['sha256'] != events[-2]['sha256']
    assert accepted.json['data']['findings'][0]['verification'] == data['findings'][0]['verification']


def test_revocation_prevents_return_and_preserves_original_findings(project):
    client, _, data = project
    response = issue_api(client, data)
    text = edit(response.data, {'owner': "'New owner"})
    proposal = propose_api(client, text)
    current = client.get('/api/projects/tasks').json
    uid = current['remediation_exchanges'][0]['uid']
    assert call(client, 'return-revoke', {'batch_uid': uid, 'ack_reviewed': False}).status_code == 422
    revoked = call(client, 'return-revoke', {'batch_uid': uid, 'ack_reviewed': True})
    assert revoked.status_code == 200
    assert revoked.json['data']['findings'] == data['findings']
    assert revoked.json['data']['remediation_exchanges'][0]['events'][-1]['kind'] == 'revoked'
    assert call(client, 'return-preview', {'text': text}).status_code == 422
    assert apply_api(client, text, proposal).status_code == 422


def test_bounded_events_and_legacy_batches_remain_valid():
    data, blob = issued()
    assert 'events' not in data['remediation_exchanges'][0]
    for index in range(20):
        proposal = returns.plan(data, 'tasks', edit(blob, {'owner': "'Owner " + str(index)}))
        data = returns.record(data, proposal, 'c'*64)
    batch = data['remediation_exchanges'][0]
    assert len(batch['events']) == returns.MAX_EVENTS
    assert batch['events_omitted'] == 4
    assert workflows.structure_errors(data) == []


@pytest.mark.parametrize('event', [dict(kind='verified'), dict(sha256='../'), dict(source_revision='x'),
                                  dict(at='2026-02-31T00:00:00Z'), dict(count=True), dict(count=5000)])
def test_invalid_events_rejected_in_ordinary_project_save(event):
    data = document()
    data, _ = returns.issue(data, 'tasks', [data['findings'][0]['uid']], source_revision='d'*64)
    data['remediation_exchanges'][0]['events'][0].update(event)
    assert any('remediation_exchanges' in text for _, text in workflows.structure_errors(data))


def test_failed_save_does_not_issue_partial_delivery(project, monkeypatch):
    import project_history
    client, directory, data = project
    opts = options(data)
    preview = call(client, 'delivery-preview', opts)
    before = {p.relative_to(directory): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    def fail(*args, **kwargs):
        raise OSError('synthetic storage failure')
    monkeypatch.setattr(project_history, 'save', fail)
    response = call(client, 'delivery-export', {**opts, 'preview_token': preview.json['preview_token']})
    assert response.status_code >= 500
    assert {p.relative_to(directory): p.read_bytes() for p in directory.rglob('*') if p.is_file()} == before
