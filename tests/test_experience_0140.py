"""Release contracts: real client package, demo isolation and preset correctness."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import zipfile

import pytest
from PIL import Image
import app as webapp
import engine
import delivery
import project_history as history
import sections
import workflows
import resources
from _support import auth_client


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path/'projects')
    webapp.PROJECTS.mkdir()
    monkeypatch.setitem(webapp.app.config, 'LIBRARY_PATH', str(tmp_path/'library.json'))
    return auth_client(webapp.app)


def create(client):
    assert client.post('/api/projects', json={'slug':'test','title':'Prueba'}).status_code==200
    directory=webapp.PROJECTS/'test'
    data=engine.load_engagement(directory/'engagement.yaml')
    data['meta'].update(assessor='Evaluador',theme='corporativo')
    data['report']={'sections':[{'key':'findings'}]}
    data['findings']=[{'id':'F1','title':'CONTROL-ORIGINAL','mode':'vuln','severity':'info','cvss':0,
                      'description_md':'Descripción','impact_md':'Impacto','remediation_md':'Remediación',
                      'walkthrough':[{'text_md':'Resultado observado','figure':{'src':'img/proof.png','caption':'Prueba'}}]}]
    Image.new('RGB',(60,40),'red').save(directory/'img/proof.png')
    (directory/'originals').mkdir();(directory/'originals/private.txt').write_text('INTERNAL-ORIGINAL')
    history.save(directory,data)
    return directory,client.get('/api/projects/test').headers['ETag']


def test_demo_creates_independent_complete_copies(client):
    a=client.post('/api/demo',json={}).get_json()['slug']
    b=client.post('/api/demo',json={}).get_json()['slug']
    assert a!=b
    da=client.get('/api/projects/'+a).get_json(); db=client.get('/api/projects/'+b).get_json()
    assert da==db and len(da['findings'])==12 and len(da['evidence'])==18
    assert len(resources.referenced_images(da))==19
    da['findings'][0]['title']='Only copy A'
    assert client.put('/api/projects/'+a,json=da).status_code==200
    assert client.get('/api/projects/'+b).get_json()==db


@pytest.mark.parametrize('body',[
 {'formats':[],'label':'Test'}, {'formats':['pdf','pdf'],'label':'Test'},
 {'formats':['exe'],'label':'Test'}, {'formats':[{}],'label':'Test'},
 {'formats':['md'],'label':''}, {'formats':['md'],'label':'x'*121},
 {'formats':['md'],'label':'Test','acknowledge_warnings':'yes'},
 {'formats':['md'],'label':'Test','unknown':True},
])
def test_invalid_delivery_rejected_without_modifying_project(client,body):
    directory,tag=create(client);before=(directory/'engagement.yaml').read_bytes()
    r=client.post('/api/projects/test/delivery',json=body,headers={'If-Match':tag})
    assert r.status_code==422 and (directory/'engagement.yaml').read_bytes()==before


def test_delivery_requires_exact_saved_revision(client):
    _,tag=create(client);body={'formats':['md'],'label':'Test'}
    # auth_client fills If-Match for normal writes, so use its underlying client
    with webapp.app.test_client() as raw:
        token=raw.get('/api/session').get_json()['csrf']
        assert raw.post('/api/projects/test/delivery',json=body,headers={'X-CSRF-Token':token}).status_code==428
    assert client.post('/api/projects/test/delivery',json=body,headers={'If-Match':'wrong'}).status_code==409
    assert client.post('/api/projects/test/delivery',json=body,headers={'If-Match':tag}).status_code==200


def test_delivery_includes_only_client_files_and_checks(client):
    directory,tag=create(client);before=(directory/'engagement.yaml').read_bytes()
    r=client.post('/api/projects/test/delivery',json={'formats':['pdf','docx','md'],'label':'Entrega'},headers={'If-Match':tag})
    assert r.status_code==200,r.get_json()
    with zipfile.ZipFile(BytesIO(r.data)) as z:
        assert set(z.namelist())=={'informe.pdf','informe.docx','markdown.zip','verificacion.json','LEEME.txt'}
        record=json.loads(z.read('verificacion.json'))
        assert record['source_revision']==sha256(before).hexdigest()
        assert record['files']['informe.pdf']['checks']['expected_image_placements']==1
        for name,info in record['files'].items(): assert sha256(z.read(name)).hexdigest()==info['sha256']
        with zipfile.ZipFile(BytesIO(z.read('markdown.zip'))) as md:
            assert set(md.namelist())=={'report.md','img/proof.png'}
    assert (directory/'engagement.yaml').read_bytes()==before


def test_delivery_captures_images_and_text_before_unlocked_render(client,monkeypatch):
    directory,tag=create(client);original=delivery.export.export; calls=[]
    def change_then_export(source,fmt,target):
        if not calls:
            data=engine.load_engagement(directory/'engagement.yaml');data['findings'][0]['title']='LATER-REVISION'
            history.save(directory,data);Image.new('RGB',(60,40),'blue').save(directory/'img/proof.png')
        calls.append(fmt)
        assert engine.load_engagement(source)['findings'][0]['title']=='CONTROL-ORIGINAL'
        assert Image.open(source.parent/'img/proof.png').getpixel((0,0))==(255,0,0)
        return original(source,fmt,target)
    monkeypatch.setattr(delivery.export,'export',change_then_export)
    r=client.post('/api/projects/test/delivery',json={'formats':['docx','md'],'label':'Consistente'},headers={'If-Match':tag})
    assert r.status_code==200,r.get_json()
    assert calls==['docx','md']


def test_failed_format_returns_no_partial_package(client,monkeypatch):
    directory,tag=create(client);before=(directory/'engagement.yaml').read_bytes()
    def fail(*args,**kwargs): raise ValueError('Prueba de fallo de exportación')
    monkeypatch.setattr(delivery.export,'export',fail)
    r=client.post('/api/projects/test/delivery',json={'formats':['docx','md'],'label':'No parcial'},headers={'If-Match':tag})
    assert r.status_code==422 and r.is_json
    assert (directory/'engagement.yaml').read_bytes()==before


def test_warnings_require_acknowledgement_and_are_retained(client):
    directory,_=create(client);data=engine.load_engagement(directory/'engagement.yaml')
    data['findings'][0]['impact_md']='TODO: completar';history.save(directory,data)
    tag=client.get('/api/projects/test').headers['ETag'];body={'formats':['md'],'label':'Borrador revisado'}
    assert client.post('/api/projects/test/delivery',json=body,headers={'If-Match':tag}).status_code==422
    body['acknowledge_warnings']=True
    r=client.post('/api/projects/test/delivery',json=body,headers={'If-Match':tag})
    assert r.status_code==200
    with zipfile.ZipFile(BytesIO(r.data)) as z:
        assert 'Texto pendiente' in json.loads(z.read('verificacion.json'))['warnings'][0]['message']


@pytest.mark.parametrize('preset', [p['id'] for p in sections.load_presets()])
@pytest.mark.parametrize('lang',['es','en'])
def test_every_preset_resolves_to_text_and_warns_on_guidance(preset,lang,tmp_path):
    resolved=sections.preset_sections(preset,lang)
    assert all(isinstance(s.get('title',''),str) for s in resolved)
    assert len({s['key'] for s in resolved})==len(resolved)
    data={'meta':{'lang':lang},'report':{'sections':deepcopy(resolved)},'findings':[]}
    issues=workflows.review(data,tmp_path)
    if any('TODO:' in text for _,text in workflows.strings(resolved)):
        assert any('Texto pendiente' in i['message'] for i in issues)


def test_certification_presets_match_their_disciplines():
    web=sections.preset_by_id('cwee');wifi=sections.preset_by_id('cwpe')
    assert 'web' in web['cert_es'].lower() and 'Wi-Fi' not in json.dumps(web)
    assert 'Wi-Fi' in wifi['cert_es']
    assert any(s['key']=='code_review' for s in web['sections'])
