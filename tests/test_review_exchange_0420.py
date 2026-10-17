"""Review exchange: exact disclosure, issued provenance, three-way review and CAS."""
from copy import deepcopy
import json

import pytest
import app as api
import client_profiles
import editorial_assistant as assistant
import review_exchange as exchange
from storage import revision
import workflows
from wizard import dump_yaml
from _support import auth_client


def document():
    return workflows.normalize(dict(meta=dict(report_title='Review', client='CLIENT_PRIVATE', theme='serio', lang='es'),
        findings=[dict(id='F1', title='Finding', mode='vuln', severity='info', cvss=0,
            description_md='Original text', impact_md='PRIVATE_IMPACT', remediation_md='Check permissions',
            proof=[{'name':'SECRET_PROOF','value':'PRIVATE_PROOF'}], status='open')]))


def returned(package, after='Reviewer text'):
    row=package['rows'][0]
    return dict(package=deepcopy(package),reviewer='Declared reviewer',changes=[dict(finding_uid=row['finding_uid'],field=row['field'],after=after,note='Check this wording')])


def issued(data=None):
    data=data or document()
    return exchange.issue(data,'case','a'*64,[data['findings'][0]['uid']],['description_md'])


@pytest.fixture
def client(tmp_path,monkeypatch):
    directory=tmp_path/'projects'/'case';directory.mkdir(parents=True)
    data=document();dump_yaml(data,directory/'engagement.yaml')
    monkeypatch.setattr(api,'PROJECTS',directory.parent)
    monkeypatch.setitem(api.app.config,'CLIENT_PROFILES_PATH',str(tmp_path/'client-profiles.json'))
    return auth_client(api.app),directory,data


def post(client,suffix,body,tag=None):
    c,directory,_=client
    return c.post('/api/projects/case'+suffix,json=body,headers={'If-Match':tag or revision(directory/'engagement.yaml')})


def test_issue_discloses_only_selected_fields_and_offline_html_escapes_payload():
    data=document();data['findings'][0]['description_md']='</script><img src=x onerror=alert(1)>'
    updated,package=issued(data)
    source=exchange.editor_html(package)
    assert 'PRIVATE_' not in source and 'SECRET_PROOF' not in source and 'CLIENT_PRIVATE' not in source
    assert '</script><img' not in source and '\\u003c/script' in source
    assert 'Content-Security-Policy' in source and "default-src &#" not in source
    assert len(updated['review_exchange']['packages'])==1
    assert 'review_exchange' not in data
    assert exchange.validate_structure(updated)==[]


def test_three_way_conflict_only_explicit_field_is_applied():
    data,package=issued();data['findings'][0]['description_md']='Author later edit'
    proposed=exchange.preview(data,'case',returned(package))
    assert proposed['changes'][0]['conflict'] is True
    assert proposed['changes'][0]['base']=='Original text'
    assert proposed['changes'][0]['before']=='Author later edit'
    key=proposed['changes'][0]['key'];updated=exchange.apply(data,proposed,[key])
    assert updated['findings'][0]['description_md']=='Reviewer text'
    assert updated['findings'][0]['impact_md']=='PRIVATE_IMPACT'
    assert proposed['authenticated'] is False
    assert data['findings'][0]['description_md']=='Author later edit'


def test_removed_finding_cannot_be_resurrected_and_changed_source_blocks_apply():
    data,package=issued();proposed=exchange.preview(data,'case',returned(package));key=proposed['changes'][0]['key']
    data['findings'][0]['description_md']='Concurrent edit'
    with pytest.raises(ValueError):exchange.apply(data,proposed,[key])
    data['findings']=[];proposed=exchange.preview(data,'case',returned(package))
    assert proposed['changes'][0]['missing']
    with pytest.raises(ValueError):exchange.apply(data,proposed,[key])


@pytest.mark.parametrize('change',[
    lambda p:p['package']['rows'][0].update(base='Altered original'),
    lambda p:p.update(reviewer=''),
    lambda p:p['changes'].append(deepcopy(p['changes'][0])),
    lambda p:p['changes'][0].update(field='status'),
    lambda p:p['changes'][0].update(after=123),
    lambda p:p['changes'][0].update(after='A'*24001),
    lambda p:p['changes'][0].update(note='A'*4001),
    lambda p:p.update(extra='ignored'),
    lambda p:p['changes'][0].update(after='bad\x00'),
    lambda p:p.update(changes={}),
])
def test_malformed_returns_rejected(change):
    data,package=issued();value=returned(package);change(value)
    with pytest.raises(ValueError):exchange.preview(data,'case',value)


def test_forged_rehashed_baseline_wrong_project_and_forgotten_package_rejected():
    data,package=issued();value=returned(package)
    value['package']['rows'][0]['base']='Forgery';value['package']['digest']=exchange.digest({k:v for k,v in value['package'].items() if k!='digest'})
    with pytest.raises(ValueError):exchange.preview(data,'case',value)
    with pytest.raises(ValueError):exchange.preview(data,'other',returned(package))
    data=exchange.forget(data,package['uid'])
    with pytest.raises(ValueError):exchange.preview(data,'case',returned(package))


def test_package_count_and_field_count_limits():
    data=document()
    for _ in range(exchange.MAX_BATCHES):data,_=issued(data)
    with pytest.raises(ValueError):issued(data)
    with pytest.raises(ValueError):exchange.issue(document(),'case','a'*64,[],['description_md'])
    with pytest.raises(ValueError):exchange.issue(document(),'case','a'*64,['none'],['status'])


def issue_api(client):
    body={'finding_uids':[client[2]['findings'][0]['uid']],'fields':['description_md']}
    preview=post(client,'/review-exchange/issue-preview',body)
    assert preview.status_code==200,preview.get_json()
    response=post(client,'/review-exchange/issue',{**body,'preview_token':preview.json['preview_token'],'ack_private':True,'lang':'es'})
    assert response.status_code==200,response.get_json()
    return response


def test_api_issue_roundtrip_and_explicit_accept(client):
    response=issue_api(client);value=response.get_json();package=value['data']['review_exchange']['packages'][0]
    text=json.dumps(returned(package));preview=post(client,'/review-exchange/preview',{'text':text})
    assert preview.status_code==200,preview.get_json()
    accepted=post(client,'/review-exchange/apply',dict(text=text,preview_token=preview.json['preview_token'],selected=[preview.json['changes'][0]['key']],ack_reviewed=True))
    assert accepted.status_code==200,accepted.get_json()
    assert accepted.json['data']['findings'][0]['description_md']=='Reviewer text'
    assert accepted.json['authenticated'] is False


def test_api_requires_revision_private_ack_and_unchanged_preview(client):
    c,directory,data=client;body={'finding_uids':[data['findings'][0]['uid']],'fields':['description_md']}
    assert c.post('/api/projects/case/review-exchange/issue-preview',json=body).status_code==428
    pv=post(client,'/review-exchange/issue-preview',body).json
    assert post(client,'/review-exchange/issue',{**body,'preview_token':pv['preview_token'],'ack_private':False,'lang':'es'}).status_code==422
    assert post(client,'/review-exchange/issue',{**body,'fields':['impact_md'],'preview_token':pv['preview_token'],'ack_private':True,'lang':'es'}).status_code==409
    data['findings'][0]['description_md']='New';dump_yaml(data,directory/'engagement.yaml')
    assert post(client,'/review-exchange/issue',{**body,'preview_token':pv['preview_token'],'ack_private':True,'lang':'es'}).status_code==409


def test_api_return_preview_token_rejects_tampering_and_other_session(client):
    response=issue_api(client);package=response.json['data']['review_exchange']['packages'][0]
    value=returned(package);text=json.dumps(value);pv=post(client,'/review-exchange/preview',{'text':text}).json
    body=dict(text=text,preview_token=pv['preview_token'],selected=[pv['changes'][0]['key']],ack_reviewed=True)
    other=auth_client(api.app)
    assert other.post('/api/projects/case/review-exchange/apply',json=body,headers={'If-Match':revision(client[1]/'engagement.yaml')}).status_code==409
    value['changes'][0]['after']='Swap after preview';body['text']=json.dumps(value)
    assert post(client,'/review-exchange/apply',body).status_code==409


def profile():
    return dict(uid=None,name='Bank client',client='Bank',terms=[dict(term='hack',preferred='security assessment')],
                required_sections=['executive_summary','risk_posture'],acceptance_criteria=['All findings reviewed'],
                delivery=dict(formats=['pdf','docx'],audience='technical',language='es'))


def test_client_profile_versions_stale_update_and_content_preservation(tmp_path):
    path=tmp_path/'profiles.json';p=client_profiles.save(path,profile(),0)
    value=profile();value['uid']=p['uid'];value['name']='Bank revised';p2=client_profiles.save(path,value,1)
    assert p2['version']==2 and client_profiles.get(path,p['uid'],1)['name']=='Bank client'
    with pytest.raises(ValueError):client_profiles.save(path,value,1)
    data=document();data['report']['sections']=[dict(key='executive_summary',summary='Authored summary')]
    pv=client_profiles.preview(data,p2);updated=client_profiles.apply(data,pv,[row['key'] for row in pv['changes']])
    assert updated['report']['sections'][0]['summary']=='Authored summary'
    assert updated['meta']['client']=='Bank' and updated['meta']['lang']=='es'
    assert updated['client_profile']['version']==2
    assert client_profiles.validate_structure(updated)==[]


@pytest.mark.parametrize('change',[
    lambda p:p.update(required_sections=['../../etc/passwd']),
    lambda p:p['delivery'].update(formats=['exe']),
    lambda p:p['delivery'].update(audience='unknown'),
    lambda p:p.update(terms=[{'term':'hack','preferred':'safe'},{'term':'HACK','preferred':'other'}]),
    lambda p:p.update(extra=True),
    lambda p:p.update(acceptance_criteria=['x'*2001]),
])
def test_invalid_client_profile_rejected(tmp_path,change):
    value=profile();change(value)
    with pytest.raises(ValueError):client_profiles.save(tmp_path/'profiles.json',value,0)


def test_profile_api_preview_explicit_apply_and_requirements(client):
    c,_,_=client;r=c.post('/api/client-profiles',json={'profile':profile(),'expected_version':0});assert r.status_code==200,r.get_json()
    p=r.json['profile'];catalog=c.get('/api/client-profiles');assert catalog.status_code==200 and catalog.json['sections']
    pv=post(client,'/client-profile/preview',{'profile_uid':p['uid'],'version':1});assert pv.status_code==200,pv.get_json()
    applied=post(client,'/client-profile/apply',{'profile_uid':p['uid'],'version':1,'preview_token':pv.json['preview_token'],'selected':['profile']})
    assert applied.status_code==200,applied.get_json()
    assert applied.json['data']['meta']['client']=='CLIENT_PRIVATE'
    req=c.get('/api/projects/case/client-profile');assert req.json['active'] and req.json['acceptance_criteria']


def test_deterministic_precheck_never_contacts_model(monkeypatch):
    monkeypatch.setattr(assistant,'_call',lambda *_a,**_k:pytest.fail('Network not allowed'))
    data=document();f=data['findings'][0];f['proof']=[];f['status']='verified_fixed'
    result=assistant.editorial_precheck(data,[f['uid']])
    assert {row['kind'] for row in result['issues']}=={'missing_evidence','incomplete_action','status_conflict'}
    assert result['network_used'] is False


def critique_body(data,**extras):
    return dict(finding_uid=data['findings'][0]['uid'],fields=['description_md'],evidence_uids=[],model='writer:local',confirmed_local=True,**extras)


def mock_critique(monkeypatch,data,issue=None):
    calls=[]
    def call(path,payload=None,**_):
        calls.append((path,deepcopy(payload)))
        if path=='/api/tags':return {'models':[{'name':'writer:local','size':4000000,'details':{'format':'gguf'}}]}
        if path=='/api/show':return {'details':{'format':'gguf'}}
        return {'message':{'content':json.dumps({'issues':[issue or dict(kind='missing_evidence',message='Review support',source_id=data['findings'][0]['uid']+':description_md',quote='Original')]})}}
    monkeypatch.setattr(assistant,'_call',call)
    return calls


def test_critique_only_sends_explicit_sources_and_does_not_apply(monkeypatch):
    data=document();before=deepcopy(data);calls=mock_critique(monkeypatch,data)
    value=assistant.critique(data,critique_body(data))
    assert data==before and value['verified'] is False
    assert 'PRIVATE_' not in json.dumps(calls) and 'SECRET_PROOF' not in json.dumps(calls)
    assert value['sources'][0]['sha256']==assistant.digest('Original text')
    assert 'proposal_id' not in value


@pytest.mark.parametrize('source_id,quote', [('forged-id','Original'),('correct','invented quote'),('correct','')])
def test_critique_rejects_invented_references_or_quotes(monkeypatch,source_id,quote):
    data=document();source_id=data['findings'][0]['uid']+':description_md' if source_id=='correct' else source_id
    mock_critique(monkeypatch,data,dict(kind='contradiction',message='Unsupported',source_id=source_id,quote=quote))
    with pytest.raises(ValueError):assistant.critique(data,critique_body(data))


def test_critique_evidence_requires_link_and_only_caption_sent():
    data=document();ev=dict(uid=workflows.new_uid(),title='PRIVATE_TITLE',caption='Public selected caption',src='img/private.png',original='img/original.png')
    data['evidence']=[ev];body=critique_body(data);body['evidence_uids']=[ev['uid']]
    with pytest.raises(ValueError):assistant.critique_context(data,body)
    data['findings'][0]['evidence_uids']=[ev['uid']];context=assistant.critique_context(data,body)
    assert context['sources'][1]['text']=='Public selected caption'
    assert 'private' not in json.dumps(context).lower() and 'PRIVATE_TITLE' not in json.dumps(context)


def test_critique_api_precheck_preview_and_consent(client,monkeypatch):
    data=client[2];calls=mock_critique(monkeypatch,data)
    r=post(client,'/assistant/precheck',{'finding_uids':[data['findings'][0]['uid']]});assert r.status_code==200 and not calls
    body=critique_body(data);pv={k:v for k,v in body.items() if k not in ('model','confirmed_local')}
    r=post(client,'/assistant/critique-preview',pv);assert r.status_code==200 and not calls
    body['confirmed_local']=False
    assert post(client,'/assistant/critique',body).status_code==422 and not calls
    body['confirmed_local']=True
    r=post(client,'/assistant/critique',body);assert r.status_code==200,r.get_json()
    assert r.json['verified'] is False and r.headers['ETag']


def test_canonical_references_roundtrip_uses_exported_list():
    data=document();uid=data['findings'][0]['uid'];data['findings'][0]['references']=['https://example.test/a','https://example.test/b']
    data,package=exchange.issue(data,'case','a'*64,[uid],['references'])
    assert package['rows'][0]['base']=='https://example.test/a\nhttps://example.test/b'
    value=returned(package,'https://example.test/c\nhttps://example.test/d')
    pv=exchange.preview(data,'case',value);result=exchange.apply(data,pv,[pv['changes'][0]['key']])
    assert result['findings'][0]['references']==['https://example.test/c','https://example.test/d']
    assert 'references_md' not in result['findings'][0]


def test_local_check_recognizes_canonical_closure_criteria(monkeypatch):
    monkeypatch.setattr(assistant,'_call',lambda *_a,**_k:pytest.fail('Network not allowed'))
    data=document();finding=data['findings'][0];finding['closure_criteria_md']='Repeat the authorization test across two users.'
    result=assistant.editorial_precheck(data,[finding['uid']])
    assert not any(row['kind']=='incomplete_action' for row in result['issues'])


def test_acceptance_receipts_are_bounded_and_validated():
    data,package=issued()
    for index in range(52):
        pv=exchange.preview(data,'case',returned(package,'Revision '+str(index)))
        data=exchange.apply(data,pv,[pv['changes'][0]['key']])
    assert len(data['review_exchange']['accepted'])==50
    assert data['review_exchange']['accepted_omitted']==2
    assert exchange.validate_structure(data)==[]
    data['review_exchange']['accepted'][0]['changes'][0]['field']='status'
    assert exchange.validate_structure(data)


def test_editorial_checks_account_for_instance_retests_and_http_sources():
    data=document();finding=data['findings'][0];finding['proof']=[];finding['closure_criteria_md']='Repeat test';finding['status']='verified_fixed'
    evidence_uid=workflows.new_uid();data['evidence']=[dict(uid=evidence_uid,title='Instance evidence')]
    finding['instances']=[dict(uid=workflows.new_uid(),status='verified_fixed',evidence_uids=[evidence_uid],retests=[dict(uid=workflows.new_uid(),tested_on='2026-10-17',result='fixed',evidence_uids=[evidence_uid])])]
    assert not assistant.editorial_precheck(data,[finding['uid']])['issues']
    finding['instances'][0]['retests'].append(dict(uid=workflows.new_uid(),tested_on='2026-10-18',result='open',evidence_uids=[evidence_uid]))
    assert {row['kind'] for row in assistant.editorial_precheck(data,[finding['uid']])['issues']}=={'status_conflict'}
    finding['instances']=[];finding['status']='open';data['http_evidence']=[dict(finding_uids=[finding['uid']])]
    assert not assistant.editorial_precheck(data,[finding['uid']])['issues']
