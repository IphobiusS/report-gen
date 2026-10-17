"""External progress is reconciled explicitly and never becomes technical proof."""
from copy import deepcopy
import json

import pytest

import app as api
from _support import auth_client
import publication
import ticket_connectors as tickets
import workflows


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.setattr(api, 'PROJECTS', tmp_path)
    client = auth_client(api.app)
    assert client.post('/api/projects', json={'slug': 'tickets', 'title': 'Synthetic tickets'}).status_code == 200
    data = client.get('/api/projects/tickets').json
    finding = dict(uid=workflows.new_uid(), id='F1', mode='vuln', title='Authorization', owner='Original',
                   due_date='2026-12-01', description_md='Manual analysis', remediation_md='Check ownership',
                   status='open', verification='confirmed')
    data['findings'] = [finding]
    assert client.put('/api/projects/tickets', json=data).status_code == 200
    return client, tmp_path / 'tickets', finding


def call(client, route, body, tag=None):
    tag = tag or client.get('/api/projects/tickets').headers['ETag']
    return client.post('/api/projects/tickets/tickets' + route, json=body, headers={'If-Match': tag})


def link(client, finding, provider='jira'):
    result = call(client, '', dict(finding_uid=finding['uid'], provider=provider,
                                  base_url='https://tickets.example.com', external_id='SEC-12' if provider == 'jira' else '12'))
    assert result.status_code == 200, result.json
    return result.json['data']['external_tickets'][0]


def test_external_closed_ticket_never_closes_local_finding(project, monkeypatch):
    client, directory, finding = project
    linked = link(client, finding)
    secret = 'synthetic-token-not-for-storage'
    monkeypatch.setattr(tickets, 'remote_request', lambda *a, **k: {'fields': {'assignee': {'displayName': 'Team'},
                         'duedate': '2026-12-20', 'status': {'name': 'Done'}}})
    preview = call(client, '/'+linked['uid']+'/pull-preview', {'credentials': {'username': 'analyst@example.com', 'token': secret}})
    assert preview.status_code == 200, preview.json
    assert len(preview.json['changes']) == 3
    applied = call(client, '/'+linked['uid']+'/pull-apply', dict(remote_state=preview.json['remote_state'],
                   accepted=['owner', 'reported_remediation'], preview_token=preview.json['preview_token'], ack_reviewed=True))
    assert applied.status_code == 200, applied.json
    final = applied.json['data']['findings'][0]
    assert final['status'] == 'open' and final['verification'] == 'confirmed'
    assert final['due_date'] == finding['due_date'] and final['owner'] == 'Team'
    assert 'Done' in final['reported_remediation'] and 'retests' not in final
    assert all(secret.encode() not in path.read_bytes() for path in directory.rglob('*') if path.is_file())
    assert 'external_tickets' not in publication.project(applied.json['data'])


def test_three_way_conflict_keeps_technical_fields_and_unselected_text():
    uid = workflows.new_uid()
    data = {'findings': [dict(uid=uid, owner='Locally changed', due_date='', status='open', description_md='Human')],
            'external_tickets': [dict(uid=workflows.new_uid(), finding_uid=uid, provider='jira',
                                     base_url='https://example.com', external_id='SEC-1', baseline={'owner': 'Base'})]}
    linked = data['external_tickets'][0]
    state = {'owner': 'External change', 'reported_remediation': 'Done'}
    assert next(row for row in tickets.pull_plan(data, linked, state) if row['field'] == 'owner')['conflict']
    before = deepcopy(data)
    after = tickets.apply_pull(data, linked['uid'], state, ['reported_remediation'])
    assert data == before and after['findings'][0]['owner'] == 'Locally changed'
    assert after['findings'][0]['status'] == 'open' and after['findings'][0]['description_md'] == 'Human'


def test_preview_token_rejects_injection_revision_change_and_other_link(project, monkeypatch):
    client, _, finding = project
    linked = link(client, finding)
    monkeypatch.setattr(tickets, 'remote_request', lambda *a, **k: {'fields': {'status': {'name': 'Done'}}})
    preview = call(client, '/'+linked['uid']+'/pull-preview', {'credentials': {}}).json
    body = dict(remote_state={**preview['remote_state'], 'owner': 'Injected'}, accepted=['owner'],
                preview_token=preview['preview_token'], ack_reviewed=True)
    assert call(client, '/'+linked['uid']+'/pull-apply', body).status_code == 409
    body['remote_state'] = preview['remote_state']
    body['accepted'] = ['reported_remediation']
    data = client.get('/api/projects/tickets').json
    data['findings'][0]['owner'] = 'Changed after preview'
    assert client.put('/api/projects/tickets', json=data).status_code == 200
    assert call(client, '/'+linked['uid']+'/pull-apply', body).status_code == 409


def test_push_is_selected_and_remote_change_blocks_write(project, monkeypatch):
    client, _, finding = project
    linked = link(client, finding)
    calls = []
    raw = {'fields': {'summary': 'External original', 'description': 'Unchanged external text'}}
    def remote(link, credentials, method='GET', payload=None):
        calls.append((method, deepcopy(payload)))
        return deepcopy(raw)
    monkeypatch.setattr(tickets, 'remote_request', remote)
    preview = call(client, '/'+linked['uid']+'/push-preview', {'fields': ['title'], 'credentials': {}})
    assert preview.status_code == 200, preview.json
    assert preview.json['payload'] == {'fields': {'summary': 'Authorization'}}
    body = dict(fields=['title'], credentials={}, remote_hash=preview.json['remote_hash'],
                preview_token=preview.json['preview_token'], ack_reviewed=True)
    raw['fields']['summary'] = 'Concurrent external edit'
    assert call(client, '/'+linked['uid']+'/push-apply', body).status_code == 409
    assert all(method == 'GET' for method, _ in calls)
    raw['fields']['summary'] = 'External original'
    assert call(client, '/'+linked['uid']+'/push-apply', body).status_code == 200
    assert calls[-1] == ('PUT', {'fields': {'summary': 'Authorization'}})


@pytest.mark.parametrize('value', ['http://example.com', 'https://127.0.0.1', 'https://10.0.0.1',
    'https://169.254.169.254', 'https://[::1]', 'https://localhost', 'https://foo.local',
    'https://user:secret@example.com', 'https://example.com/a', 'https://example.com#x',
    'https://example.com:8443', 'https://example.com?token=secret', None, [], {}])
def test_bad_origins_rejected(value):
    with pytest.raises((ValueError, TypeError)):
        tickets.base_url(value)


def test_network_rebinding_private_dns_rejected_before_connect(monkeypatch):
    linked = dict(uid=workflows.new_uid(), finding_uid=workflows.new_uid(), provider='jira',
                  base_url='https://example.com', external_id='SEC-1')
    monkeypatch.setattr(tickets.socket, 'getaddrinfo', lambda *a, **k: [(2, 1, 6, '', ('127.0.0.1', 443))])
    monkeypatch.setattr(tickets, '_PinnedHTTPS', lambda *a: pytest.fail('Must not connect'))
    with pytest.raises(ValueError):
        tickets.remote_request(linked, {'username': 'analyst@example.com', 'token': 'synthetic'})


def test_defectdojo_reporter_is_not_assignee_and_no_technical_fields_sent():
    linked = dict(uid=workflows.new_uid(), finding_uid=workflows.new_uid(), provider='defectdojo',
                  base_url='https://example.com', external_id='12')
    result = tickets.remote_state(linked, {'reporter': 99, 'active': False, 'verified': True})
    assert set(result) == {'reported_remediation'}
    payload = tickets.push_payload({'title': 'Synthetic', 'remediation_md': 'Fix', 'status': 'verified_fixed'},
                                   'defectdojo', ['title', 'remediation_md'])
    assert payload == {'title': 'Synthetic', 'mitigation': 'Fix'}
    assert not {'active', 'verified', 'status'} & payload.keys()


@pytest.mark.parametrize('selected', [[], ['status'], ['verification'], ['retests'], ['title', 'title'], [{}], None])
def test_push_rejects_technical_or_invalid_fields(selected):
    with pytest.raises((ValueError, TypeError)):
        tickets.push_payload({'title': 'Synthetic'}, 'jira', selected)


def test_payload_does_not_include_structured_proof_or_private_state():
    payload = tickets.push_payload({'title': 'Synthetic', 'description_md': 'Reviewed text',
        'http_evidence': {'secret': 'canary'}, 'instances': [{'owner': 'private'}]}, 'jira', ['title'])
    assert 'canary' not in json.dumps(payload) and 'private' not in json.dumps(payload)


def raw_link(provider='jira'):
    return dict(uid=workflows.new_uid(),finding_uid=workflows.new_uid(),provider=provider,
                base_url='https://example.com',external_id='SEC-1' if provider=='jira' else '1')


def test_jira_missing_fields_never_propose_erasing_local_owner_or_date():
    linked=raw_link()
    state=tickets.remote_state(linked,{'fields':{'status':{'name':'Done'}}})
    assert state=={'reported_remediation':'Jira SEC-1: Done'}
    data={'findings':[{'uid':linked['finding_uid'],'owner':'Analyst assignment','due_date':'2026-12-01','status':'open'}]}
    assert [row['field'] for row in tickets.pull_plan(data,linked,state)]==['reported_remediation']
    explicit=tickets.remote_state(linked,{'fields':{'assignee':None,'duedate':None}})
    assert explicit=={'owner':'','due_date':''}


@pytest.mark.parametrize('fields',[{}, {'assignee':False},{'assignee':0},{'assignee':{}}, {'assignee':{'displayName':None}},
                                   {'duedate':False},{'duedate':3},{'status':None},{'status':{'name':None}}, {'status':{'name':''}}])
def test_jira_incomplete_or_wrongly_typed_tracking_rejected(fields):
    with pytest.raises(ValueError):tickets.remote_state(raw_link(),{'fields':fields})


@pytest.mark.parametrize('raw',[{}, {'reporter':12},{'active':'false'},{'verified':1},{'false_p':None},{'mitigated':{}}])
def test_dojo_tracking_fields_are_typed_and_never_guessed(raw):
    with pytest.raises(ValueError):tickets.remote_state(raw_link('defectdojo'),raw)


def test_outgoing_jira_preview_compares_exact_replaced_fields_only(project,monkeypatch):
    client,_,finding=project;linked=link(client,finding)
    remote={'fields':{'summary':'Server title','description':{'type':'doc','content':[{'type':'paragraph','text':'Remote remediation also lives here'}]},'comment':'secret unrelated comment'}}
    monkeypatch.setattr(tickets,'remote_request',lambda *a,**k:deepcopy(remote))
    result=call(client,'/'+linked['uid']+'/push-preview',{'fields':['remediation_md'],'credentials':{}})
    assert result.status_code==200,result.json
    assert result.json['changes']==[{'field':'description','before':remote['fields']['description'],
                                   'after':result.json['payload']['fields']['description'],'available':True}]
    assert 'secret unrelated comment' not in json.dumps(result.json)
    assert tickets.push_changes(raw_link(),{'fields':{}},{'fields':{'duedate':None}})==[
        {'field':'duedate','before':None,'after':None,'available':False}]


def test_public_ipv6_origin_is_canonical_and_private_scoped_ips_are_rejected():
    value='https://[2606:4700:4700::1111]'
    assert tickets.base_url(value)==value
    linked=raw_link();linked['base_url']=value
    assert tickets.validate_link(linked)==linked
    for value in ['https://[fe80::1%25eth0]','https://[2606:4700:4700::1111%25eth0]']:
        with pytest.raises(ValueError):tickets.base_url(value)


@pytest.mark.parametrize('raw',[b'{"fields":{},"fields":{}}',b'{"score":NaN}', b'{"x":' + b'['*80 + b'0'+b']'*80+b'}'])
def test_external_json_rejects_ambiguous_nonportable_and_deep_input(monkeypatch,raw):
    class Response:
        status=200
        def read(self,maximum):return raw
    class Connection:
        def request(self,*a,**k):pass
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr(tickets.socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('8.8.8.8',443))])
    monkeypatch.setattr(tickets,'_PinnedHTTPS',lambda *a:Connection())
    with pytest.raises(ValueError):tickets.remote_request(raw_link(),{'username':'analyst@example.com','token':'never-log-this-token'})


def test_failed_tls_wrap_closes_socket(monkeypatch):
    class Socket:
        closed=False
        def close(self):self.closed=True
    sock=Socket()
    class Context:
        def wrap_socket(self,*a,**k):raise tickets.ssl.SSLError('synthetic handshake failure')
    monkeypatch.setattr(tickets.socket,'create_connection',lambda *a,**k:sock)
    connection=tickets._PinnedHTTPS('example.com','8.8.8.8');connection._context=Context()
    with pytest.raises(tickets.ssl.SSLError):connection.connect()
    assert sock.closed


def test_push_deadline_validated_before_outbound_payload():
    with pytest.raises(ValueError):tickets.push_payload({'due_date':'2026-02-31'},'jira',['due_date'])


def test_pinned_ipv6_preserves_full_tls_identity_and_https_port():
    connection=tickets._PinnedHTTPS('2606:4700:4700::1111','2606:4700:4700::1111')
    assert connection.host=='2606:4700:4700::1111'
    assert connection.port==443


@pytest.mark.parametrize('findings',[None,{},[None],['text'],[{'uid':[]}],[[{}]]])
def test_malformed_project_findings_return_structure_errors(findings):
    assert tickets.structure_errors({'findings':findings,'external_tickets':[raw_link()]})
