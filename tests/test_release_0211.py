"""Release 0.21.1: mutation testing and privacy controls on disposable projects."""
from copy import deepcopy
from io import BytesIO
from pathlib import Path
import zipfile

from lxml import html
import pytest
import delivery
import export
import export_contract
import workflows
from wizard import dump_yaml


def document():
    return workflows.normalize({'meta':{'report_title':'Control sintético 0.21.1','lang':'es','theme':'corporativo'},
       'report':{'sections':[{'key':'findings'}]},
       'findings':[{'id':fid,'title':'Hallazgo '+fid,'mode':'vuln',
           'description_md':'Descripción completa de '+fid+'.\n\nPárrafo compartido.\n\nPárrafo compartido.',
           'impact_md':'Impacto exclusivo de '+fid+'.','remediation_md':'Remediación de '+fid,
           'walkthrough':[{'command':"  if true; then\n\tprintf '%s' 'A  B'\n  fi\n\n"}]} for fid in ('F01','F02')]})


def prepare(tmp_path,fmt,data=None):
    data=deepcopy(data or document());dump_yaml(data,tmp_path/'engagement.yaml')
    captured=delivery.capture(tmp_path,tmp_path/'capture')
    output=export.export(tmp_path/'engagement.yaml',fmt,tmp_path/('report.'+delivery.get(fmt).extension))
    return output,captured


def edit_zip(path, member, edit):
    with zipfile.ZipFile(path) as z: files={name:z.read(name) for name in z.namelist()}
    files[member]=edit(files[member])
    with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
        for name,blob in files.items():z.writestr(name,blob)


def mutate_text(path,fmt,old,new):
    change=lambda blob:blob.replace(old.encode(),new.encode(),1)
    if fmt=='html':path.write_bytes(change(path.read_bytes()))
    else:edit_zip(path,'report.md' if fmt=='md' else 'word/document.xml',change)


@pytest.mark.parametrize('fmt',['html','md','docx'])
def test_literal_code_preserves_indentation_tabs_trailing_newlines(tmp_path,fmt):
    output,captured=prepare(tmp_path,fmt)
    check=delivery.inspect_export(output,fmt,captured)
    assert check['literal_code_blocks_checked']==2
    assert check['finding_association_checked'] is True
    assert check['paragraphs_checked']>=10
    assert check['contract_version']==3


@pytest.mark.parametrize('fmt',['html','md','docx'])
@pytest.mark.parametrize('old,new',[("A  B","AB"),("A  B","A B"),("%s","%d"),("Impacto exclusivo de F01.",""),("Párrafo compartido.","")])
def test_mutated_content_cannot_receive_success(tmp_path,fmt,old,new):
    output,captured=prepare(tmp_path,fmt)
    mutate_text(output,fmt,old,new)
    with pytest.raises(ValueError):delivery.inspect_export(output,fmt,captured)


@pytest.mark.parametrize('fmt',['html','md','docx'])
def test_moving_paragraph_to_another_finding_fails(tmp_path,fmt):
    output,captured=prepare(tmp_path,fmt)
    mutate_text(output,fmt,'Impacto exclusivo de F01.','TEMP_0211')
    mutate_text(output,fmt,'Impacto exclusivo de F02.','Impacto exclusivo de F01.')
    mutate_text(output,fmt,'TEMP_0211','Impacto exclusivo de F02.')
    with pytest.raises(ValueError,match='Párrafo'):delivery.inspect_export(output,fmt,captured)


def test_html_duplicate_or_missing_finding_identity_fails(tmp_path):
    output,captured=prepare(tmp_path,'html');tree=html.document_fromstring(output.read_text())
    tree.get_element_by_id('F02').set('id','F01');output.write_text(html.tostring(tree,encoding='unicode'))
    with pytest.raises(ValueError):export_contract.inspect(output,'html',captured['contract'])


def test_pdf_record_explicitly_requires_literal_and_visual_review(tmp_path):
    data=document()
    for finding in data['findings']:finding['walkthrough'][0]['command']="printf '%s' 'A B'"
    output,captured=prepare(tmp_path,'pdf',data)
    result=delivery.inspect_export(output,'pdf',captured)
    assert result['manual_review_required'] is True
    assert result['literal_code_blocks_checked']==0
    assert result['finding_association_checked'] is False
    assert result['verification_scope']=='text_presence_only'


def test_old_unscoped_contract_is_not_silently_accepted(tmp_path):
    with pytest.raises(ValueError,match='antiguo'):export_contract.inspect(tmp_path/'unused','html',{'titles':['x']})


def test_markdown_fences_keep_tabs_and_cannot_forge_html_stash():
    from safe_markup import md
    tree=html.fragment_fromstring(str(md("```sh\n\tprintf '%s' 'A  B'\n```")),create_parent='div')
    assert tree.xpath('string(.//pre)')=="\tprintf '%s' 'A  B'\n"
    malicious=str(md('\x02wzxhzdk:0\x03\n\n<script>alert(1)</script>'))
    assert not html.fragment_fromstring(malicious,create_parent='div').xpath('.//script')


def annex(data,directory,blob=b'password=SYNTHETIC_SECRET_0211\nuser@example.invalid\n',required=False,include=False):
    from hashlib import sha256
    import uuid
    member='attachments/'+uuid.uuid4().hex+'.txt'
    path=directory/member;path.parent.mkdir(exist_ok=True);path.write_bytes(blob)
    row=dict(uid=str(uuid.uuid4()),name='revisado.txt',member=member,sha256=sha256(blob).hexdigest(),required=required,include=include,reviewed=include)
    data.setdefault('attachments',[]).append(row)
    return row


@pytest.mark.parametrize('include',[False,True])
def test_required_annex_blocks_until_selected_and_intact(tmp_path,include):
    import attachments
    data=document();row=annex(data,tmp_path,required=True,include=include)
    if include:
        assert attachments.capture(data,tmp_path,tmp_path/'out')
        (tmp_path/row['member']).unlink()
    with pytest.raises(ValueError,match='obligatorio'):attachments.capture(data,tmp_path,tmp_path/'missing')
    assert any(i['level']=='error' and i['path']=='attachments' for i in workflows.review(data,tmp_path))


def test_required_declared_annex_is_draft_valid_but_not_deliverable(tmp_path):
    import uuid,attachments,validate
    data=document();data['attachments']=[dict(uid=str(uuid.uuid4()),name='pendiente.txt',required=True)]
    assert not validate.structure_issues(data)
    with pytest.raises(ValueError,match='obligatorio'):attachments.capture(data,tmp_path,tmp_path/'out')


def test_scan_is_hash_bound_advisory_and_never_echoes_secrets(tmp_path):
    import json,attachments
    data=document();row=annex(data,tmp_path)
    before=(tmp_path/row['member']).read_bytes();report=attachments.scan(tmp_path,row)
    assert report['complete'] and report['manual_review_required']
    assert {a['kind'] for a in report['alerts']}=={'credential','possible_email'}
    assert 'SYNTHETIC_SECRET' not in json.dumps(report)
    assert (tmp_path/row['member']).read_bytes()==before
    (tmp_path/row['member']).write_bytes(b'modified')
    with pytest.raises(ValueError,match='alterado'):attachments.scan(tmp_path,row)


def test_scan_size_bound_and_pdf_not_falsely_clean(tmp_path):
    import attachments
    from hashlib import sha256
    data=document();row=annex(data,tmp_path,b'x'*(1024*1024+50))
    result=attachments.scan(tmp_path,row)
    assert not result['complete'] and result['bytes_inspected']==1024*1024
    old=tmp_path/row['member'];row['member']=row['member'].removesuffix('.txt')+'.pdf';blob=b'%PDF-1.7\nsynthetic, not parsed';old.unlink();(tmp_path/row['member']).write_bytes(blob);row['sha256']=sha256(blob).hexdigest()
    result=attachments.scan(tmp_path,row)
    assert result['scope']=='manual' and not result['complete'] and result['bytes_inspected']==0


def test_scan_image_metadata_without_pixel_or_metadata_mutation(tmp_path):
    import attachments
    from hashlib import sha256
    from PIL import Image,PngImagePlugin
    data=document();row=annex(data,tmp_path)
    out=BytesIO();meta=PngImagePlugin.PngInfo();meta.add_text('Comment','PRIVATE_METADATA_SENTINEL')
    Image.new('RGB',(8,8),'blue').save(out,format='PNG',pnginfo=meta);blob=out.getvalue()
    (tmp_path/row['member']).unlink();row['member']=row['member'].removesuffix('.txt')+'.png';row['sha256']=sha256(blob).hexdigest();(tmp_path/row['member']).write_bytes(blob)
    result=attachments.scan(tmp_path,row)
    assert result['scope']=='image_metadata' and result['alerts'][0]['count']>=1 and not result['complete']
    assert 'PRIVATE_METADATA_SENTINEL' not in str(result)
    assert (tmp_path/row['member']).read_bytes()==blob


def private_fixture(tmp_path):
    import project_history
    from PIL import Image
    root=tmp_path/'audit';root.mkdir();data=document();row=annex(data,root)
    (root/'originals').mkdir();Image.new('RGB',(8,8),'red').save(root/'originals/private.png')
    project_history.save(root,data)
    data['attachments']=[];project_history.save(root,data)
    (root/'engagement.yaml.bak').write_text('private legacy backup')
    return root,row


def test_private_cleanup_is_explicit_preserves_current_data_and_baseline(tmp_path):
    import private_data,project_history
    root,row=private_fixture(tmp_path);before=(root/'engagement.yaml').read_bytes();image=(root/'originals/private.png').read_bytes()
    inventory=private_data.public_inventory(root)
    assert '_groups' not in inventory
    assert next(c for c in inventory['categories'] if c['key']=='unused_annexes')['count']==1
    after=private_data.prune(root,['history','unused_annexes','legacy_backup'],inventory['inventory_revision'])
    assert after['versions']==1
    assert (root/'engagement.yaml').read_bytes()==before
    assert (root/'originals/private.png').read_bytes()==image
    assert not (root/row['member']).exists() and not (root/'engagement.yaml.bak').exists()
    snapshot=project_history.history(root)[0]
    assert row['member'] not in snapshot['files'] and 'originals/private.png' in snapshot['files']


@pytest.mark.parametrize('categories',[None,[],['originals'],['history','history'],[{}],[1]])
def test_invalid_private_cleanup_never_mutates(tmp_path,categories):
    import private_data,project_history
    root,row=private_fixture(tmp_path);before=project_history.export_bundle(root)
    token=private_data.public_inventory(root)['inventory_revision']
    with pytest.raises(ValueError):private_data.prune(root,categories,token)
    assert (root/row['member']).exists()
    with zipfile.ZipFile(BytesIO(before)) as z:
        assert (root/'engagement.yaml').read_bytes()==z.read('engagement.yaml')


def test_changed_inventory_and_symlinks_fail_closed(tmp_path):
    import private_data
    root,row=private_fixture(tmp_path);token=private_data.public_inventory(root)['inventory_revision']
    (root/'engagement.yaml.bak').write_text('new backup')
    with pytest.raises(ValueError,match='cambió'):private_data.prune(root,['history'],token)
    (root/'originals/link.txt').symlink_to(tmp_path/'external')
    with pytest.raises(ValueError,match='simbólico'):private_data.public_inventory(root)


def test_privacy_api_requires_session_confirmation_revision_and_no_store(tmp_path,monkeypatch):
    import app as api
    from _support import auth_client
    from storage import revision
    root,row=private_fixture(tmp_path);monkeypatch.setattr(api,'PROJECTS',tmp_path)
    client=auth_client(api.app);etag=revision(root/'engagement.yaml')
    response=client.get('/api/projects/audit/privacy');assert response.status_code==200
    assert response.headers['Cache-Control']=='no-store'
    body=dict(categories=['history'],inventory_revision=response.json['inventory_revision'],confirm_project='wrong')
    assert client.post('/api/projects/audit/privacy/prune',json=body,headers={'If-Match':etag}).status_code==422
    body['confirm_project']='audit'
    assert client.post('/api/projects/audit/privacy/prune',json=body,headers={'If-Match':'stale'}).status_code==409
    assert client.post('/api/projects/audit/privacy/prune',json=body,headers={'If-Match':etag}).status_code==200
    unauth=api.app.test_client()
    assert unauth.post('/api/projects/audit/privacy/prune',json=body,headers={'If-Match':etag}).status_code==403


@pytest.mark.parametrize('errno_name',['ENOSPC','EACCES'])
def test_os_write_failures_preserve_project_and_allow_retry(tmp_path,monkeypatch,errno_name):
    import errno,storage,project_history
    root,row=private_fixture(tmp_path);before=(root/'engagement.yaml').read_bytes();data=document();data['meta']['report_title']='RECUPERADO_0211'
    original=storage.os.replace
    def fail(source,target):
        if Path(target).name=='engagement.yaml':raise OSError(getattr(errno,errno_name),'injected')
        return original(source,target)
    with monkeypatch.context() as m:
        m.setattr(storage.os,'replace',fail)
        with pytest.raises(OSError):project_history.save(root,data)
    assert (root/'engagement.yaml').read_bytes()==before and (root/row['member']).is_file()
    project_history.save(root,data)
    assert b'RECUPERADO_0211' in (root/'engagement.yaml').read_bytes()


@pytest.mark.parametrize('fmt',['html','md','docx','pdf'])
def test_legacy_overview_keeps_default_assessment_team(tmp_path,fmt):
    data=workflows.normalize({'meta':{'report_title':'Legacy','lang':'en'},'findings':[{'id':'F01','title':'One','mode':'vuln'}]})
    output,captured=prepare(tmp_path,fmt,data)
    assert delivery.inspect_export(output,fmt,captured)['paragraphs_checked']>0


def test_pdf_page_join_does_not_drop_source_words_or_skip_a_page():
    unit='First part remains. Second part remains.'
    assert export_contract._pdf_across_pages(unit,['First part remains. footer','header Second part remains.'])
    assert not export_contract._pdf_across_pages(unit,['First part remains. footer','header Second remains.'])
    assert not export_contract._pdf_across_pages(unit,['First part remains.','unrelated','Second part remains.'])
    assert not export_contract._pdf_pattern('A B').search('AB')


def test_pdf_long_paragraph_can_span_three_consecutive_pages():
    assert export_contract._pdf_across_pages('Alpha beta gamma delta epsilon zeta.',
        ['Alpha beta footer','header gamma delta footer','header epsilon zeta.'])
