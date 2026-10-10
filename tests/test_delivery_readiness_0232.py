"""R06: preparation facts are saved-revision-bound and never certification."""
from copy import deepcopy
from hashlib import sha256
import json
import uuid

import app as webapp
import publication
import readiness
import workflows
import pytest
from PIL import Image
from storage import revision
from wizard import dump_yaml
from _support import auth_client


def document():
    return workflows.normalize({'meta': {'report_title': 'Synthetic preparation', 'lang': 'es'},
        'report': {'sections': [{'key': 'findings'}]},
        'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'Synthetic observation',
            'severity': 'low', 'description_md': 'Observed a synthetic response.',
            'impact_md': 'Synthetic impact.', 'remediation_md': 'Check authorization.',
            'walkthrough': [{'command': 'printf synthetic_proof'}], 'proof': [{'name':'Observed output','value':'Synthetic proof.'}]}]})


def prepared(data, directory, lang='es'):
    return readiness.checklist(data, directory, workflows.preflight(data, directory, lang), lang)


def item(result, key):
    return next(check for check in result['checks'] if check['key'] == key)


def annex(data, directory, include=False, required=False, reviewed=False):
    member='attachments/'+uuid.uuid4().hex+'.txt'
    blob=b'Synthetic annex only.\n'
    path=directory/member;path.parent.mkdir(exist_ok=True);path.write_bytes(blob)
    row=dict(uid=workflows.new_uid(),name='synthetic.txt',member=member,
             sha256=sha256(blob).hexdigest(),include=include,required=required,reviewed=reviewed)
    data.setdefault('attachments',[]).append(row)
    return row


def test_no_issues_never_implies_technical_or_human_approval(tmp_path):
    data=document();before=deepcopy(data)
    result=prepared(data,tmp_path)
    assert result['source']=='saved_project'
    assert result['technical_validation'] is False and result['manual_review_required'] is True
    assert item(result,'human_review')['status']=='manual'
    assert 'patterns' == item(result,'secrets')['scope'].split('_')[-1]
    assert 'imágenes' in item(result,'secrets')['detail']
    assert 'approved' not in result and 'passed' not in result and 'ready' not in result
    assert data==before and not list(tmp_path.iterdir())


def test_annex_status_comes_from_actual_bytes_and_saved_decisions(tmp_path):
    data=document();row=annex(data,tmp_path,required=True)
    assert item(prepared(data,tmp_path),'annexes')['status']=='blocked'
    row.update(include=True,reviewed=True)
    check=item(prepared(data,tmp_path),'annexes')
    assert check['counts']==dict(included=1,excluded=0,unreviewed=0,required_pending=0,selected_missing=0)
    assert check['status']=='checked'
    (tmp_path/row['member']).write_bytes(b'Changed synthetic annex.\n')
    check=item(prepared(data,tmp_path),'annexes')
    assert check['status']=='blocked' and check['counts']['selected_missing']==1
    assert check['counts']['required_pending']==1


def test_optional_private_annex_is_visible_but_not_a_delivery_error(tmp_path):
    data=document();annex(data,tmp_path)
    check=item(prepared(data,tmp_path),'annexes')
    assert check['status']=='attention'
    assert check['counts']['excluded']==1 and check['counts']['unreviewed']==1
    assert check['counts']['required_pending']==0


def test_outgoing_patterns_are_redaction_bound_and_do_not_echo_secrets(tmp_path):
    data=document();secret='R06_SYNTHETIC_PRIVATE_98765'
    data['findings'][0]['description_md']='password='+secret
    result=prepared(data,tmp_path)
    assert item(result,'secrets')['counts']==dict(unresolved=1,excepted=0)
    assert secret not in json.dumps(result) and 'password=' not in json.dumps(result)
    alert=publication.inspect(data,tmp_path)['alerts'][0]
    data['publication']={'exceptions':[{'id':alert['id'],'reason':'Synthetic published demonstration'}]}
    result=prepared(data,tmp_path)
    assert item(result,'secrets')['counts']==dict(unresolved=0,excepted=1)
    assert item(result,'human_review')['status']=='manual'
    data['findings'][0]['description_md']='password='+secret+'_changed'
    assert item(prepared(data,tmp_path),'secrets')['counts']==dict(unresolved=1,excepted=0)
    data['publication']={'redactions':[{'needle':secret+'_changed','replacement':'[REDACTED]'}]}
    assert item(prepared(data,tmp_path),'secrets')['counts']==dict(unresolved=0,excepted=0)


def test_private_capture_and_editorial_reasoning_do_not_enter_secret_counts(tmp_path):
    import capture_inbox
    import insights
    data=document()
    # These private areas must not change the publication-oriented summary.
    data,_=capture_inbox.create(data,tmp_path,dict(kind='note',title='Private synthetic note',
                                                raw_text='password=R06_PRIVATE_CAPTURE_12345'))
    data=insights.mutate(data,dict(action='add_comment',finding_uid=data['findings'][0]['uid'],
        field='description_md',body='password=R06_PRIVATE_COMMENT_12345',author='Synthetic reviewer',visibility='private'),
        'a'*64,tmp_path)
    result=readiness.checklist(data,tmp_path,[], 'en')
    assert item(result,'secrets')['counts']==dict(unresolved=0,excepted=0)
    assert 'R06_PRIVATE' not in json.dumps(result)


def test_broken_reference_and_missing_evidence_remain_different_facts(tmp_path):
    data=document();finding=data['findings'][0];finding['evidence_uids']=[workflows.new_uid()]
    result=prepared(data,tmp_path)
    assert item(result,'associations')['status']=='blocked'
    assert item(result,'associations')['counts']['errors']==1
    finding.pop('evidence_uids');finding.pop('proof')
    result=prepared(data,tmp_path)
    assert item(result,'associations')['status']=='attention'
    assert item(result,'associations')['counts']['errors']==0
    assert item(result,'associations')['counts']['warnings']==1


def test_structural_error_does_not_invent_completed_checks(tmp_path):
    data=document();data['findings']='invalid structure'
    result=prepared(data,tmp_path,'en')
    assert item(result,'review')['status']=='blocked'
    assert all(item(result,key)['status']=='not_checked' for key in ('annexes','secrets','associations'))
    assert item(result,'human_review')['status']=='manual'


def test_missing_image_cannot_produce_clean_secret_check(tmp_path):
    data=document();data['findings'][0]['walkthrough'].append({'figure':{'src':'img/missing.png'}})
    result=prepared(data,tmp_path)
    assert item(result,'review')['status']=='blocked'
    assert item(result,'secrets')['status']=='not_checked'


def test_invalid_image_bytes_do_not_break_review_or_invent_clean_result(tmp_path):
    data=document();path=tmp_path/'img'/'invalid.png';path.parent.mkdir();path.write_bytes(b'invalid synthetic image')
    data['findings'][0]['walkthrough'].append({'figure':{'src':'img/invalid.png'}})
    result=prepared(data,tmp_path)
    assert item(result,'secrets')['status']=='not_checked'
    assert 'invalid.png' not in json.dumps(item(result,'secrets'))


@pytest.mark.parametrize('fmt,extension', [('PNG','png'),('JPEG','jpg'),('WEBP','webp'),('GIF','gif')])
def test_text_readiness_preserves_alerts_without_reencoding_images(tmp_path,monkeypatch,fmt,extension):
    data=document()
    data['findings'][0]['description_md']='password=SYNTHETIC_READINESS_TOKEN_0310'
    path=tmp_path/'img'/f'example.{extension}';path.parent.mkdir()
    image=Image.new('RGB',(120,80),(24,80,45))
    image.save(path,format=fmt)
    data['findings'][0]['walkthrough'].append({'figure':{'src':f'img/example.{extension}'}})
    original=path.read_bytes()
    full=publication.inspect(data,tmp_path)
    data['publication']={'exceptions':[{'id':full['alerts'][0]['id'],'reason':'Synthetic fixture'}]}
    full=publication.inspect(data,tmp_path)
    def no_reencode(_):
        raise AssertionError('Readiness must not create sanitized copies of every image.')
    monkeypatch.setattr(publication,'clean_image',no_reencode)
    text=publication.inspect_text(data,tmp_path)
    assert text=={key:value for key,value in full.items() if key!='images'}
    result=prepared(data,tmp_path)
    assert item(result,'secrets')['counts']==dict(unresolved=0,excepted=1)
    assert path.read_bytes()==original


@pytest.mark.parametrize('allow_truncated', [False, True])
@pytest.mark.parametrize('fmt,extension', [('PNG','png'),('JPEG','jpg'),('WEBP','webp'),('GIF','gif')])
def test_truncated_decodable_header_still_blocks_text_readiness(tmp_path,monkeypatch,allow_truncated,fmt,extension):
    from PIL import ImageFile
    # WeasyPrint enables this global flag. Neither inspection path may inherit
    # that permissive behavior or toggle global decoder state across threads.
    monkeypatch.setattr(ImageFile,'LOAD_TRUNCATED_IMAGES',allow_truncated)
    data=document();path=tmp_path/'img'/f'truncated.{extension}';path.parent.mkdir()
    pixels=bytes((index*17+(index//113)*19)%256 for index in range(120*80*3))
    Image.frombytes('RGB',(120,80),pixels).save(path,format=fmt)
    original=path.read_bytes()
    assert len(original)>200
    data['findings'][0]['walkthrough'].append({'figure':{'src':f'img/truncated.{extension}'}})
    assert publication.validate_image(original) is None
    assert item(prepared(data,tmp_path),'secrets')['status']=='checked'
    for damaged in (original[:200],original[:-2]):
        path.write_bytes(damaged)
        from error_messages import language_scope
        from image_integrity import verify_container
        for language,expected in [('es','La imagen está incompleta o dañada.'),
                                  ('en','The image is incomplete or damaged.')]:
            with language_scope(language),pytest.raises(ValueError) as failure:
                verify_container(damaged,fmt)
            assert str(failure.value)
            if fmt!='JPEG':
                assert str(failure.value)==expected
        with pytest.raises((OSError,ValueError)):
            publication.inspect(data,tmp_path)
        with pytest.raises((OSError,ValueError)):
            publication.validate_image(damaged)
        assert item(prepared(data,tmp_path),'secrets')['status']=='not_checked'
        assert ImageFile.LOAD_TRUNCATED_IMAGES is allow_truncated


@pytest.mark.parametrize('language,expected', [('es','La imagen está incompleta o dañada.'),
                                             ('en','The image is incomplete or damaged.')])
def test_publication_api_returns_readable_localized_image_error(tmp_path,monkeypatch,language,expected):
    from PIL import ImageFile
    monkeypatch.setattr(ImageFile,'LOAD_TRUNCATED_IMAGES',True)
    monkeypatch.setattr(webapp,'PROJECTS',tmp_path)
    directory=tmp_path/'readiness';(directory/'img').mkdir(parents=True)
    path=directory/'img'/'private-evidence-name.png'
    pixels=bytes((index*17+(index//113)*19)%256 for index in range(120*80*3))
    Image.frombytes('RGB',(120,80),pixels).save(path,format='PNG')
    path.write_bytes(path.read_bytes()[:200])
    data=document()
    data['findings'][0]['walkthrough'].append({'figure':{'src':'img/private-evidence-name.png'}})
    dump_yaml(data,directory/'engagement.yaml')
    response=auth_client(webapp.app).get('/api/projects/readiness/publication',headers={'X-UI-Language':language})
    assert response.status_code==422
    assert response.get_json()=={'error':expected}
    assert response.headers['Content-Language']==language
    assert 'private-evidence-name' not in response.get_data(as_text=True)


def test_api_returns_etag_revision_and_recomputes_without_writing(tmp_path,monkeypatch):
    monkeypatch.setattr(webapp,'PROJECTS',tmp_path)
    directory=tmp_path/'readiness';directory.mkdir();dump_yaml(document(),directory/'engagement.yaml')
    client=auth_client(webapp.app)
    # First project read performs the existing legacy normalization, if needed.
    client.get('/api/projects/readiness')
    before=(directory/'engagement.yaml').read_bytes()
    response=client.get('/api/projects/readiness/review?lang=en')
    assert response.status_code==200
    report=response.get_json();assert report['revision']==revision(directory/'engagement.yaml')
    assert response.headers['ETag']=='"'+report['revision']+'"'
    assert report['readiness']['technical_validation'] is False
    assert item(report['readiness'],'human_review')['title']=='Human review'
    assert (directory/'engagement.yaml').read_bytes()==before
    data=client.get('/api/projects/readiness').get_json()
    data['findings'][0]['description_md']='password=R06_API_SYNTHETIC_12345'
    assert client.put('/api/projects/readiness',json=data).status_code==200
    changed=client.get('/api/projects/readiness/review').get_json()
    assert changed['revision']!=report['revision']
    assert item(changed['readiness'],'secrets')['counts']['unresolved']==1
    assert 'R06_API_SYNTHETIC' not in json.dumps(changed['readiness'])
