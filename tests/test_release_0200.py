"""Regressions from the independent 0.18 audit, using only synthetic secrets."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import base64
import zipfile
import pytest
from PIL import Image, PngImagePlugin
import workflows
import finding_imports
import capture_inbox
import report_compare
import delivery
import export
from wizard import dump_yaml


def basic():
    return workflows.normalize({'meta':{'report_title':'Synthetic audit','lang':'en','theme':'serio'},'findings':[dict(id='F1',mode='vuln',title='Finding',severity='low',description_md='Description',impact_md='Impact',remediation_md='Fix',walkthrough=[{'command':'id'}])]})

def png(marker=''):
    out=BytesIO();meta=PngImagePlugin.PngInfo();meta.add_text('Comment',marker);Image.new('RGB',(40,30),'#476583').save(out,'PNG',pnginfo=meta);return out.getvalue()

def test_a01_private_comparison_excludes_unlinked_captures(tmp_path):
    before=basic();after=deepcopy(before)
    after['capture_inbox']=[dict(uid=workflows.new_uid(),kind='note',title='Private',raw_text='PRIVATE_TOKEN_0200',sha256='a'*64)]
    markup=report_compare.render(before,after,{}, {'img/private.png':png('PRIVATE_IMAGE_METADATA_0200')},'before','after','en')
    assert 'PRIVATE_TOKEN_0200' not in markup
    assert 'data:image/png' not in markup

def test_a03_orphan_capture_can_relink(tmp_path):
    data=basic();data,item=capture_inbox.create(data,tmp_path,dict(kind='command',title='Command',raw_text='id'))
    data=capture_inbox.link(data,tmp_path,item['uid'],data['findings'][0]['uid'])
    orphan=data['findings'][0]['uid'];data['findings'][0]['uid']=workflows.new_uid()
    result=capture_inbox.link(data,tmp_path,item['uid'],data['findings'][0]['uid'])
    assert result['capture_inbox'][0]['finding_uid']==data['findings'][0]['uid']
    assert result['capture_inbox'][0]['previous_finding_uid']==orphan

def test_a04_invalid_csv_does_not_block_valid_alternative():
    body=dict(format='csv',text='title,severity,affected\nSame,unknown,host\nSame,low,host\n',selected=[1])
    data,count=finding_imports.apply(body,basic());assert count==1 and data['findings'][-1]['severity']=='low'

def test_a04_deselected_csv_does_not_block_alternative():
    body=dict(format='csv',text='title,severity,affected\nSame,high,host\nSame,low,host\n',selected=[1])
    data,count=finding_imports.apply(body,basic());assert count==1 and data['findings'][-1]['severity']=='low'
    body['selected']=[0,1]
    with pytest.raises(ValueError): finding_imports.apply(body,basic())

@pytest.mark.parametrize('bom',[b'',b'\xef\xbb\xbf'])
@pytest.mark.parametrize('newline',['\n','\r\n'])
def test_a05_hash_original_bytes(bom,newline):
    blob=bom+('title,severity'+newline+'Prueba ñ,low'+newline).encode()
    result=finding_imports.preview(dict(format='csv',text=blob.decode('utf-8-sig'),bytes_base64=base64.b64encode(blob).decode()),basic())
    assert result['sha256']==sha256(blob).hexdigest()
    assert result['rows'][0]['finding']['import_source']['hash_scope']=='original_bytes'

def test_a06_metadata_removed_all_archive_exports(tmp_path):
    data=basic();(tmp_path/'img').mkdir();original=png('PRIVATE_IMAGE_METADATA_0200');(tmp_path/'img/proof.png').write_bytes(original)
    data['findings'][0]['walkthrough'].append({'figure':{'src':'img/proof.png','caption':'Proof'}});dump_yaml(data,tmp_path/'engagement.yaml')
    for fmt in ['md','docx']:
        out=export.export(tmp_path/'engagement.yaml',fmt,tmp_path/('output.'+fmt))
        with zipfile.ZipFile(out) as z:
            media=[z.read(n) for n in z.namelist() if n.startswith(('img/','word/media/'))]
            assert media and all(b'PRIVATE_IMAGE_METADATA_0200' not in blob for blob in media)
    assert (tmp_path/'img/proof.png').read_bytes()==original

def test_a08_english_delivery_wrapper(tmp_path):
    data=basic();dump_yaml(data,tmp_path/'engagement.yaml');snapshot=tmp_path/'snapshot';captured=delivery.capture(tmp_path,snapshot)
    payload=delivery.build(snapshot,['md'],'rev','Synthetic',captured,tmp_path/'out')
    with zipfile.ZipFile(BytesIO(payload)) as z:
        assert 'README.txt' in z.namelist();text=z.read('README.txt').decode();assert 'same saved revision' in text and 'Entrega:' not in text

def test_a09_latest_retest_controls_review(tmp_path):
    data=basic();f=data['findings'][0];f['status']='verified_fixed';f['retests']=[dict(uid=workflows.new_uid(),result='fixed',tested_on='2026-01-01'),dict(uid=workflows.new_uid(),result='open',tested_on='2026-02-01')]
    assert any(i['path'].endswith('.status') for i in workflows.review(data,tmp_path))
    f['retests'].reverse();assert any(i['path'].endswith('.status') for i in workflows.review(data,tmp_path))

def test_publication_redactions_are_private_and_consistent(tmp_path):
    import publication
    data=basic();secret='API_KEY=synthetic_sensitive_value';data['findings'][0]['walkthrough'][0]['command']=secret
    data['publication']={'redactions':[{'needle':'synthetic_sensitive_value','replacement':'[REDACTED]'}],'exceptions':[]}
    before=deepcopy(data);dump_yaml(data,tmp_path/'engagement.yaml')
    inspected=publication.inspect(data,tmp_path)
    assert secret not in inspected['text'] and '[REDACTED]' in inspected['text'];assert data==before
    for fmt in ['html','md','docx']:
        path=export.export(tmp_path/'engagement.yaml',fmt,tmp_path/('redacted.'+fmt))
        if fmt=='html': text=path.read_text()
        else:
            with zipfile.ZipFile(path) as z:text=''.join(z.read(n).decode('utf-8','ignore') for n in z.namelist() if n.endswith(('.xml','.md')))
        assert secret not in text and '[REDACTED]' in text

def test_portable_html_embeds_assets_and_hashes_script(tmp_path):
    data=basic();(tmp_path/'img').mkdir();(tmp_path/'img/proof.png').write_bytes(png('PRIVATE_METADATA'))
    data['findings'][0]['walkthrough'].append({'figure':{'src':'img/proof.png','caption':'Example'}});dump_yaml(data,tmp_path/'engagement.yaml')
    path=export.export(tmp_path/'engagement.yaml','html',tmp_path/'report.html');markup=path.read_text()
    assert 'src="data:image/png;base64,' in markup and "script-src 'sha256-" in markup
    assert 'file://' not in markup and 'PRIVATE_METADATA' not in markup and 'id="severity"' in markup

def test_inspector_patterns_exceptions_and_disabled_content(tmp_path):
    import publication
    data=basic();data['findings'][0]['walkthrough'][0]['command']='Authorization: Bearer synthetic_sensitive_token'
    result=publication.inspect(data,tmp_path);assert any(a['kind']=='bearer' for a in result['alerts'])
    a=result['alerts'][0];data['publication']={'exceptions':[{'id':a['id'],'reason':'Synthetic example'}]}
    assert publication.inspect(data,tmp_path)['alerts'][0]['reason']=='Synthetic example'
    data['capture_inbox']=[{'raw_text':'API_KEY=private_unlinked_secret'}]
    assert 'private_unlinked_secret' not in publication.inspect(data,tmp_path)['text']

def test_shared_comparison_never_restores_before_redaction(tmp_path):
    before=basic();after=deepcopy(before)
    before['findings'][0]['description_md']='Private key API_KEY=old_sensitive_value'
    after['findings'][0]['description_md']=before['findings'][0]['description_md']
    after['publication']={'redactions':[{'needle':'old_sensitive_value','replacement':'[REDACTED]'}]}
    before['findings'][0]['walkthrough'].append({'figure':{'src':'img/old.png','caption':'Before'}})
    after['findings'][0]['walkthrough'].append({'figure':{'src':'img/new.png','caption':'After'}})
    markup=report_compare.render(before,after,{'img/old.png':png('secret')},{'img/new.png':png()},'old','new','en')
    assert 'old_sensitive_value' not in markup and markup.count('src="data:image/')==1
    internal=report_compare.render(before,after,{'img/old.png':png('secret')},{'img/new.png':png()},'old','new','en',internal=True)
    assert 'INTERNAL:' in internal and 'old_sensitive_value' in internal

@pytest.mark.parametrize('fmt',['PNG','JPEG','WEBP','GIF'])
def test_publication_image_sanitizer_is_idempotent(fmt):
    import publication
    buffer=BytesIO();Image.new('RGB',(30,20),'#487369').save(buffer,fmt)
    cleaned=publication.clean_image(buffer.getvalue())
    assert publication.clean_image(cleaned)==cleaned

def test_jpeg_unknown_metadata_removed_without_pixel_recompression():
    import publication
    buffer=BytesIO();Image.new('RGB',(30,20),'#487369').save(buffer,'JPEG',progressive=True)
    raw=buffer.getvalue();secret=b'PRIVATE_APP_SEGMENT_0200';tag=b'\xff\xed'+(len(secret)+2).to_bytes(2,'big')+secret
    original=raw[:2]+tag+raw[2:]+b'PRIVATE_TRAILING_BYTES'
    cleaned=publication.clean_image(original)
    assert secret not in cleaned and b'PRIVATE_TRAILING_BYTES' not in cleaned
    assert Image.open(BytesIO(raw)).tobytes()==Image.open(BytesIO(cleaned)).tobytes()

def test_inspector_json_credentials_and_redaction_placeholder(tmp_path):
    import publication
    data=basic();data['findings'][0]['walkthrough'][0]['command']='{"password": "synthetic_password_0200"}'
    assert publication.inspect(data,tmp_path)['alerts']
    data['publication']={'redactions':[{'needle':'synthetic_password_0200','replacement':'[REDACTED]'}]}
    assert publication.inspect(data,tmp_path)['alerts']==[]


def test_export_accepts_custom_yaml_filename(tmp_path):
    data=basic();data['meta']['report_title']='Named source'
    dump_yaml(data,tmp_path/'custom-name.yaml')
    path=export.export(tmp_path/'custom-name.yaml','html',tmp_path/'report.html')
    assert 'Named source' in path.read_text()
    assert not (tmp_path/'engagement.yaml').exists()


def test_draft_check_rejects_bad_schema_without_writing(tmp_path,monkeypatch):
    import app as api
    from _support import auth_client
    monkeypatch.setattr(api,'PROJECTS',tmp_path)
    directory=tmp_path/'draft';directory.mkdir();data=basic();dump_yaml(data,directory/'engagement.yaml')
    original=(directory/'engagement.yaml').read_bytes();client=auth_client(api.app)
    tag=client.get('/api/projects/draft').headers['ETag']
    invalid=deepcopy(data);invalid['schema_version']=99
    assert client.post('/api/projects/draft/draft-check',json=invalid,headers={'If-Match':tag}).status_code==422
    unfinished=deepcopy(data);unfinished['findings'][0]['description_md']=''
    response=client.post('/api/projects/draft/draft-check',json=unfinished,headers={'If-Match':tag})
    assert response.status_code==200 and response.json['data']['findings'][0]['description_md']==''
    assert client.post('/api/projects/draft/draft-check',json=data,headers={'If-Match':'"stale"'}).status_code==409
    assert (directory/'engagement.yaml').read_bytes()==original
