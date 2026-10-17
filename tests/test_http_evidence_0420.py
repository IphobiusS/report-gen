"""HTTP intake: immutable originals, explicit publication and paired local intake."""
import base64
from copy import deepcopy
import json

import pytest
import app as api
import audience
import http_evidence as http
import publication
from storage import revision
import workflows
from wizard import dump_yaml
from _support import auth_client

PRIVATE = 'HTTP_PRIVATE_CANARY_0420'


def document():
    return workflows.normalize(dict(meta=dict(report_title='HTTP test', theme='serio', lang='es'),
        assets=[dict(name='Bank API', target='https://bank.test', kind='web', notes='')],
        findings=[dict(id='F001', mode='vuln', title='Role comparison', description_md='Synthetic test',
                       impact_md='Example', remediation_md='Review access', severity='high', cvss=8.1)]))


def record():
    return dict(title=PRIVATE, notes=PRIVATE, original=dict(captured_at='2026-10-17T10:00:00Z', identity=PRIVATE, source=PRIVATE,
        request=dict(method='GET', url='https://bank.test/accounts/1?token='+PRIVATE, http_version='HTTP/1.1',
                     headers=[dict(name='Authorization', value='Bearer '+PRIVATE)], body='', body_encoding='utf-8'),
        response=dict(status=200, http_version='HTTP/1.1', headers=[dict(name='Set-Cookie',value=PRIVATE)],
                      body='{"private":"'+PRIVATE+'"}', body_encoding='utf-8')))


def captured():
    data=document()
    return http.add(data, [record()], [data['findings'][0]['uid']], [data['assets'][0]['uid']])


def reviewed(data, uid):
    return http.update(data, uid, dict(publication=dict(request_text='GET /accounts/1 HTTP/1.1\nAuthorization: [redacted]',
        response_text='HTTP/1.1 200\n\n{"synthetic":true}', caption='Reviewed role comparison'), ack_reviewed=True))


def har():
    return dict(log=dict(version='1.2', entries=[dict(startedDateTime='2026-10-17T10:00:00Z',
        request=dict(method='GET',url='https://bank.test/1',httpVersion='HTTP/2',headers=[dict(name='Authorization',value=PRIVATE)]),
        response=dict(status=200,httpVersion='HTTP/2',headers=[],content=dict(text='\x01binary',encoding='base64')))]))


def test_private_original_is_separate_and_never_published_by_default():
    data,uids=captured();before=deepcopy(data)
    projected=publication.project(data)
    assert PRIVATE not in json.dumps(projected)
    assert 'http_evidence' not in projected
    assert projected['http_evidence_refs']==[dict(uid=uids[0],sha256=data['http_evidence'][0]['sha256'],published=False)]
    assert data==before
    assert not http.structure_errors(projected)


def test_reviewed_copy_only_bound_to_original_and_content_idempotently():
    data,uids=captured();data=reviewed(data,uids[0]);before=deepcopy(data)
    projected=publication.project(data)
    assert PRIVATE not in json.dumps(projected)
    assert projected['http_evidence_refs'][0]['published'] is True
    assert 'Authorization: [redacted]' in json.dumps(projected)
    assert len(projected['findings'][0]['walkthrough'])==2
    assert publication.project(projected)==projected and data==before
    assert not workflows.structure_errors(projected)
    data['http_evidence'][0]['publication']['request_text']+='tampered'
    assert http.structure_errors(data)
    with pytest.raises(ValueError):publication.project(data)


def test_http_assessment_references_identify_rendered_copies_and_withhold_hidden_findings(tmp_path):
    import attack_paths
    import test_plans
    import uuid
    data, uids = captured(); data = reviewed(data, uids[0]); data['meta']['lang'] = 'en'
    data['test_cases'] = [test_plans.create(dict(title='HTTP traceability', http_evidence_uids=uids))]
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    path = attack_paths.create(dict(title='HTTP causal traceability',
        nodes=[dict(uid=a, title='Reader'), dict(uid=b, title='Controlled record')],
        edges=[dict(uid=str(uuid.uuid4()), source_uid=a, target_uid=b, state='observed',
                    observation='Synthetic controlled record returned', http_evidence_uids=uids)]))
    data['attack_paths'] = [path]
    before = deepcopy(data)
    projected = publication.project(data)
    full = publication.render(projected, tmp_path)
    assert projected['http_evidence_refs'][0]['published'] is True
    finding_text = publication.rendered_text(full.xpath('//*[@id="F001"]')[0])
    assert 'HTTP request · ' + uids[0] in finding_text
    assert 'HTTP response · ' + uids[0] in finding_text
    assert 'GET /accounts/1' in finding_text
    assert PRIVATE not in publication.rendered_text(full)
    sectioned = deepcopy(data); sectioned['report'] = {'sections': [{'key': 'findings'}]}
    sectioned = publication.project(sectioned)
    assert sectioned['http_evidence_refs'][0]['published'] is True
    assert 'HTTP request · ' + uids[0] in publication.rendered_text(publication.render(sectioned, tmp_path))
    for section in ('rg_test_cases', 'rg_attack_' + path['uid'].replace('-', '')):
        subset, _ = audience.project(data, dict(profile='technical', section_keys=[section]))
        text = publication.rendered_text(publication.render(subset, tmp_path))
        assert subset['http_evidence_refs'][0]['published'] is False
        assert uids[0] + ' (content withheld)' in text
        assert 'GET /accounts/1' not in text and PRIVATE not in text
        assert not subset['findings'][0].get('walkthrough')
        assert publication.project(subset) == subset
        projected_subset, _ = audience.project(projected, dict(profile='technical', section_keys=[section]))
        assert projected_subset['http_evidence_refs'][0]['published'] is False
        assert uids[0] + ' (content withheld)' in publication.rendered_text(publication.render(projected_subset, tmp_path))
    assert data == before


def test_no_publication_without_explicit_ack_or_for_public_or_executive():
    data,uids=captured()
    for ack in (False,None,'true',1):
        with pytest.raises(ValueError):
            http.update(data,uids[0],dict(publication=dict(request_text='GET /',response_text='',caption=''),ack_reviewed=ack))
    data=reviewed(data,uids[0])
    for profile in ('executive','public'):
        out=http.project_for_export(data,profile)
        assert 'http_evidence' not in out and 'http_evidence_refs' not in out
        assert not out['findings'][0].get('walkthrough')
    projected,_=audience.project(data,dict(profile='executive'))
    assert PRIVATE not in json.dumps(projected) and 'GET /accounts/1' not in json.dumps(projected)


def test_literal_redactions_apply_to_copy_after_private_original_is_removed():
    data,uids=captured();data=reviewed(data,uids[0])
    data['publication']={'redactions':[dict(needle='accounts',replacement='resource')]}
    projected=publication.project(data)
    assert 'GET /resource/1' in json.dumps(projected) and PRIVATE not in json.dumps(projected)
    assert 'accounts' in data['http_evidence'][0]['publication']['request_text']


def test_original_is_immutable_in_edit_and_full_project_save_guard():
    data,uids=captured();changed=deepcopy(data)
    with pytest.raises(ValueError):http.update(data,uids[0],{'original':record()['original']})
    changed['http_evidence'][0]['original']['identity']='changed'
    changed['http_evidence'][0]['sha256']=http.digest(changed['http_evidence'][0]['original'])
    with pytest.raises(ValueError):http.assert_originals_unchanged(data,changed)
    assert not http.structure_errors(data)


@pytest.mark.parametrize('field,value', [('finding_uids',None),('finding_uids',1),('finding_uids',True),('finding_uids','abc'),
    ('asset_uids',None),('asset_uids',{}),('asset_uids',[None]),('asset_uids',['missing'])])
def test_malformed_associations_are_validation_errors(field,value):
    with pytest.raises(ValueError):http.add(document(),[record()],**{field:value})


@pytest.mark.parametrize('parent,link', [('findings', 'finding_uids'), ('assets', 'asset_uids')])
@pytest.mark.parametrize('bad', [None, 1, True, {}, 'wrong', [None], [{'uid': []}], [{'uid': {}}]])
def test_malformed_reference_parents_remain_controlled_and_pure(parent, link, bad):
    data, _ = captured()
    expected_uid = data['http_evidence'][0][link][0]
    data[parent] = bad
    before = deepcopy(data)
    assert http.structure_errors(data)
    with pytest.raises(ValueError):
        http.add(data, [record()], **{link: [expected_uid]})
    assert data == before
    # Without HTTP records, leave the malformed core container to its validator.
    data.pop('http_evidence')
    assert http.structure_errors(data) == []


@pytest.mark.parametrize('change', ['bad_method','bad_url','bad_scheme','bad_port','status_bool','status_range','header_crlf',
    'header_name','body_large','base64_invalid','base64_noncanonical','duplicate_uid','hash','unknown_original','publication_audience'])
def test_bounded_malformed_originals_and_publication_rejected(change):
    data,uids=captured();row=data['http_evidence'][0];req=row['original']['request'];res=row['original']['response']
    if change=='bad_method':req['method']='GET\r\nHost: bad'
    if change=='bad_url':req['url']='https://bad host/'
    if change=='bad_scheme':req['url']='file:///tmp/private'
    if change=='bad_port':req['url']='http://bank.test:999999/'
    if change=='status_bool':res['status']=True
    if change=='status_range':res['status']=999
    if change=='header_crlf':req['headers'][0]['value']='x\r\nInjected: yes'
    if change=='header_name':req['headers'][0]['name']='bad:name'
    if change=='body_large':req['body']='x'*(http.MAX_BODY+1)
    if change=='base64_invalid':req.update(body_encoding='base64',body='not base64')
    if change=='base64_noncanonical':req.update(body_encoding='base64',body='Zh==')
    if change=='duplicate_uid':data['http_evidence'].append(deepcopy(row))
    if change=='hash':row['sha256']='0'*64
    if change=='unknown_original':row['original']['extra']='bad'
    if change=='publication_audience':data=reviewed(data,uids[0]);data['http_evidence'][0]['publication']['audiences']=['public']
    assert http.structure_errors(data)


def test_har_selected_entries_only_and_binary_preserved_without_decoding():
    payload=har();payload['log']['entries'][0]['response']['content']['text']=base64.b64encode(b'\x00\xffbinary').decode()
    payload['log']['entries'].append(deepcopy(payload['log']['entries'][0]));payload['log']['entries'][1]['request']['url']='https://bank.test/2'
    result=http.from_har(payload,[1]);assert len(result)==1
    assert result[0]['original']['request']['url'].endswith('/2')
    assert base64.b64decode(result[0]['original']['response']['body'])==b'\x00\xffbinary'
    assert '[binary body; base64]' in http.wire_text(result[0]['original']['response'])


@pytest.mark.parametrize('bad', [None,{},[],True,1,'invalid'])
def test_har_malformed_header_container(bad):
    payload=har();payload['log']['entries'][0]['request']['headers']=bad
    if bad==[]:payload['log']['entries'][0]['response']['headers']=None
    with pytest.raises(ValueError):http.from_har(payload)


def test_har_missing_body_and_unanswered_request_are_not_invented():
    payload=har();entry=payload['log']['entries'][0];entry['response']['status']=0
    entry['request']['postData']={'params':[dict(name='p',value='v')]}
    records=http.from_har(payload)
    assert records[0]['original']['response'] is None
    assert records[0]['original']['request']['body']=='' and 'not captured' in records[0]['notes']


def test_comparison_roles_and_budget_does_not_modify_or_verify_findings():
    data,uids=captured();second=record();second['original']['identity']='role B';second['original']['response']['status']=403
    data,second_uids=http.add(data,[second]);before=deepcopy(data)
    result=http.comparison(data,uids[0],second_uids[0]);assert '403' in result['response']['diff']
    assert result['left_identity']==PRIVATE and result['right_identity']=='role B' and data==before
    data['http_evidence'][0]['original']['request']['body']='x'*(128*1024)
    assert http.comparison(data,uids[0],second_uids[0])['request']['truncated']


@pytest.fixture
def client(tmp_path,monkeypatch):
    directory=tmp_path/'projects'/'case';directory.mkdir(parents=True)
    data=document();dump_yaml(data,directory/'engagement.yaml')
    monkeypatch.setattr(api,'PROJECTS',directory.parent)
    api.app.extensions['report_gen_http_pairings'].clear()
    return auth_client(api.app),directory,data


def post(client,suffix,body,headers=None):
    c,d,_=client
    return c.post('/api/projects/case/http-evidence'+suffix,json=body,
                  headers={'If-Match':revision(d/'engagement.yaml'),**(headers or {})})


def pair(client):
    c,d,data=client
    response=post(client,'/pairing',dict(finding_uids=[data['findings'][0]['uid']]))
    assert response.status_code==200,response.json
    code=response.json['code'][4:];config=json.loads(base64.urlsafe_b64decode(code+'='*((-len(code))%4)))
    return config


def test_pairing_explicit_destination_one_use_normal_csrf_and_cas(client):
    c,d,data=client;config=pair(client);original=revision(d/'engagement.yaml')
    headers={'X-Report-Gen-Pairing':config['token'],'X-Report-Gen-Workspace':config['workspace']}
    fresh=api.app.test_client()
    denied=fresh.post('/api/projects/case/http-evidence/bridge',json={'records':[record()]},headers={**headers,'If-Match':original})
    assert denied.status_code==403
    csrf=fresh.get('/api/session').json['csrf']
    allowed=fresh.post('/api/projects/case/http-evidence/bridge',json={'records':[record()]},
        headers={**headers,'If-Match':original,'X-CSRF-Token':csrf})
    assert allowed.status_code==200,allowed.json
    row=allowed.json['data']['http_evidence'][0]
    assert row['finding_uids']==[data['findings'][0]['uid']] and row['original']['source']=='Burp Montoya selected messages'
    assert row['publication'] is None
    assert post(client,'/bridge',{'records':[record()]},headers).status_code==403


@pytest.mark.parametrize('headers', [{'Origin':'https://attacker.test'}, {'Sec-Fetch-Site':'cross-site'}, {'Host':'attacker.test'}, {'X-Report-Gen-Workspace':'wrong'}])
def test_pairing_never_bypasses_origin_host_workspace(client,headers):
    config=pair(client);before=revision(client[1]/'engagement.yaml')
    result=post(client,'/bridge',{'records':[record()]},{'X-Report-Gen-Pairing':config['token'],**headers})
    assert result.status_code in (400,403,409) and revision(client[1]/'engagement.yaml')==before


def test_pairing_rotates_revokes_expires(client):
    first=pair(client);second=pair(client)
    assert post(client,'/bridge',{'records':[record()]},{'X-Report-Gen-Pairing':first['token']}).status_code==403
    assert post(client,'/pairing/revoke',{}).status_code==200
    assert post(client,'/bridge',{'records':[record()]},{'X-Report-Gen-Pairing':second['token']}).status_code==403
    config=pair(client)
    for value in api.app.extensions['report_gen_http_pairings'].values():value['expires']=0
    assert post(client,'/bridge',{'records':[record()]},{'X-Report-Gen-Pairing':config['token']}).status_code==403


def test_pairing_changed_revision_rejected_and_malformed_records_do_not_consume(client):
    config=pair(client);headers={'X-Report-Gen-Pairing':config['token']}
    assert post(client,'/bridge',{'records':[record()],'finding_uids':[]},headers).status_code==422
    assert post(client,'/bridge',{'records':[dict(original={})]},headers).status_code==422
    assert post(client,'',{'records':[record()]}).status_code==200
    assert post(client,'/bridge',{'records':[record()]},headers).status_code==409


@pytest.mark.parametrize('value',[None,True,1,'bad',{}])
def test_api_malformed_associations_422_not_500(client,value):
    before=revision(client[1]/'engagement.yaml')
    assert post(client,'',{'records':[record()],'finding_uids':value}).status_code==422
    assert revision(client[1]/'engagement.yaml')==before


def test_api_har_selection_preview_no_write_and_stale_cas(client):
    payload=har();payload['log']['entries'][0]['response']['content']={'text':'synthetic'}
    before=revision(client[1]/'engagement.yaml')
    response=post(client,'/har-preview',{'har':payload})
    assert response.status_code==200 and len(response.json['entries'])==1 and before==revision(client[1]/'engagement.yaml')
    assert post(client,'/har',{'har':payload}).status_code==422
    assert post(client,'/har',{'har':payload,'indices':[0]}, {'If-Match':'"stale"'}).status_code==409
    assert post(client,'/har',{'har':payload,'indices':[0]}).status_code==200


@pytest.mark.parametrize('bad',[{},None,'invalid',[None],[{}],[{'uid':'invalid'}]])
def test_publication_malformed_http_shape_is_validation_error(bad):
    data=document();data['http_evidence']=bad
    with pytest.raises(ValueError):publication.project(data)


def test_technical_finding_subset_never_promotes_excluded_http_content():
    data,uids=captured();data=reviewed(data,uids[0]);data['findings']=[]
    projected=publication.project(data)
    assert PRIVATE not in json.dumps(projected) and 'GET /accounts/1' not in json.dumps(projected)
    assert projected['http_evidence_refs'][0]['published'] is False
