"""Report library contracts: isolation, persistence, untrusted inputs and rendering."""
from copy import deepcopy
import pytest
import app as webapp
import design_library as lib
import design_render as render
from design_samples import sample_data
import engine
import project_history as history
import validate
from _support import auth_client


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(webapp,'PROJECTS',tmp_path/'projects');webapp.PROJECTS.mkdir()
    monkeypatch.setitem(webapp.app.config,'DESIGN_LIBRARY_PATH',str(tmp_path/'designs.json'))
    return auth_client(webapp.app)


def test_catalog_groups_and_distinct_compositions():
    cat=lib.catalog();profiles=cat['profiles']
    assert len(profiles)==29
    assert len([p for p in profiles if p['provider']=='OffSec'])==14
    assert len([p for p in profiles if p['provider']=='HTB'])==8
    assert {p['layout'] for p in profiles}==set(lib.LAYOUTS)
    assert len({p['id'] for p in profiles})==29
    assert lib.profile('htb-cwpe')['domain']=='wifi'
    assert lib.profile('htb-cwee')['domain']=='code'
    assert all(p['accent']=='#9FEF00' for p in profiles if p['provider']=='HTB')


@pytest.mark.parametrize('profile',lib.catalog()['profiles'],ids=lambda p:p['id'])
@pytest.mark.parametrize('variant',lib.VARIANTS)
def test_starters_and_rendered_profile_tokens(profile,variant,tmp_path):
    data=lib.new_report(profile,'A report','en',variant)
    validate.require_valid(data,final=True)
    assert not data['findings']
    assert any('TODO:' in s.get('body','') for s in data['report']['sections'])
    assert all(not isinstance(v,dict) for s in data['report']['sections'] for v in s.values())
    pal=render.palette(data['meta']['design'])
    assert render.contrast(pal['--cover-title'],pal['--profile-middle'])>=4.5
    assert render.contrast(pal['--cover-fg'],pal['--cover-bg'])>=4.5
    assert render.contrast(pal['--accent-ink'],'#FFFFFF')>=4.5
    sample=sample_data(profile,variant)
    html=engine.render_html(engine.build_env(),sample,tmp_path,{},False,engine.load_lang('es'))
    assert 'profile-cover layout-'+profile['layout'] in html
    assert pal['--cover-rule'] in html
    assert 'TODO:' not in html


def test_new_profile_bilingual_and_no_exam_ready_claim(client):
    r=client.post('/api/design-library/projects',json={'id':'htb-cwee','title':'CWEE training','lang':'en','variant':'quiet'})
    assert r.status_code==200,r.get_json()
    slug=r.get_json()['slug'];data=client.get('/api/projects/'+slug).get_json()
    assert data['meta']['design']['variant']=='quiet'
    assert data['report']['sections'][0]['title']=='Work summary'
    guide=client.get('/api/projects/'+slug+'/review').get_json()['delivery_guidance']
    assert guide['formats']==['md'] and 'does not encrypt' in guide['note']
    assert client.post('/api/design-library/projects',json={'id':'htb-cwee','title':'CWEE training','lang':'en'}).status_code==409


def test_apply_only_changes_appearance_and_rejects_stale(client):
    slug=client.post('/api/demo',json={}).get_json()['slug']
    r=client.get('/api/projects/'+slug);old=r.get_json();etag=r.headers['ETag']
    directory=webapp.PROJECTS/slug
    image_before={p.name:p.read_bytes() for p in (directory/'img').iterdir()}
    new=client.post('/api/projects/'+slug+'/design',json={'id':'offsec-oscp','variant':'brand'},headers={'If-Match':etag})
    assert new.status_code==200,new.get_json()
    actual=deepcopy(new.get_json()['data']);actual['meta'].pop('design');actual['meta']['theme']=old['meta']['theme']
    assert actual==old
    assert image_before=={p.name:p.read_bytes() for p in (directory/'img').iterdir()}
    assert client.post('/api/projects/'+slug+'/design',json={'id':'htb-cwee'},headers={'If-Match':etag}).status_code==409
    current=client.get('/api/projects/'+slug).headers['ETag']
    reset=client.post('/api/projects/'+slug+'/design',json={'general':'corporativo'},headers={'If-Match':current})
    assert reset.status_code==200 and 'design' not in reset.get_json()['data']['meta']
    assert reset.get_json()['data']['findings']==old['findings']


def test_personal_snapshot_survives_edits_deletion_and_backup(client,tmp_path):
    initial=client.get('/api/design-library');p=lib.profile('htb-cpts')
    body={'name':'Mi diseño','design':lib.appearance(p),'sections':p['sections']}
    body['design']['accent']='#195080';body['design']['layout']='frame'
    assert client.post('/api/design-library/personal',json=body).status_code==428
    r=client.post('/api/design-library/personal',json=body,headers={'If-Match':initial.headers['ETag']})
    assert r.status_code==200,r.get_json()
    item=r.get_json();uid=item['id'];version=r.headers['ETag']
    created=client.post('/api/design-library/projects',json={'id':uid,'title':'Personal test'}).get_json()['slug']
    report=client.get('/api/projects/'+created).get_json()
    assert report['meta']['design']['accent']=='#195080'
    body['design']['accent']='#C12448'
    edited=client.put('/api/design-library/personal/'+uid,json=body,headers={'If-Match':version})
    assert edited.status_code==200 and edited.get_json()['revision']==2
    assert client.delete('/api/design-library/personal/'+uid,headers={'If-Match':version}).status_code==412
    assert client.delete('/api/design-library/personal/'+uid,headers={'If-Match':edited.headers['ETag']}).status_code==200
    assert client.get('/api/projects/'+created).get_json()==report
    bundle=history.export_bundle(webapp.PROJECTS/created)
    history.import_bundle(bundle,tmp_path/'restored')
    assert engine.load_engagement(tmp_path/'restored/engagement.yaml')['meta']['design']==report['meta']['design']
    html=engine.render_html(engine.build_env(),report,webapp.PROJECTS/created,{},False,engine.load_lang('es'))
    assert '#195080' in html


@pytest.mark.parametrize('key,value',[('accent','red; background:url(https://example.org/x)'),('background','</style><script>alert(1)</script>'),('layout','../../etc/passwd'),('variant','<img>'),('guidance_id',{}),('schema',True)])
def test_untrusted_design_rejected(key,value,client):
    d=lib.appearance(lib.profile('htb-cpts'));d[key]=value
    r=client.post('/api/design-library/preview',json={'design':d})
    assert r.status_code==422


def test_custom_section_limits_and_html_escaped(client):
    p=lib.profile('htb-cpts');d=lib.appearance(p)
    d['name']='<script>alert(1)</script>'
    d['certificate']='<script>alert(1)</script>'
    r=client.post('/api/design-library/preview',json={'design':d})
    assert r.status_code==200 and b'<script>alert(1)</script>' not in r.data
    assert b'&lt;script&gt;' in r.data
    bad=[{'key':'dup','title':'A'},{'key':'dup','title':'B'}]
    with pytest.raises(ValueError):lib.validate_sections(bad)
    with pytest.raises(ValueError):lib.validate_sections([{'key':'../foo','title':'A'}])
    with pytest.raises(ValueError):lib.validate_sections([{'key':'x','title':'A','client':'SECRET'}])


def test_palette_handles_user_extremes():
    p=lib.profile('htb-cpts');d=lib.appearance(p)
    for color in ('#FFFFFF','#000000','#FFFF00','#F0F0F0'):
        d.update(background=color,accent=color,layout='frame')
        pal=render.palette(d)
        assert render.contrast(pal['--cover-title'],pal['--profile-middle'])>=4.5
        assert render.contrast(pal['--accent-ink'],'#FFFFFF')>=4.5


def test_personal_structure_does_not_reintroduce_default_prose(tmp_path):
    p=lib.profile('offsec-oscp')
    item=lib.put_personal(tmp_path/'library.json',{'name':'Outline','design':lib.appearance(p),
       'sections':[{'key':'scope','title':'Mi alcance','body':'TODO: Escribe el alcance.'},{'key':'findings'}]})
    assert item['sections'][0]['key']=='personal-scope'
    report=lib.new_report(item,'Outline')
    html=engine.render_html(engine.build_env(),report,tmp_path,{},False,engine.load_lang('es'))
    assert 'TODO: Escribe el alcance.' in html


def test_personal_library_never_commits_an_unreadable_size(tmp_path,monkeypatch):
    import input_guard
    p=lib.profile('offsec-oscp');path=tmp_path/'library.json'
    monkeypatch.setattr(input_guard,'MAX_DOCUMENT_BYTES',128*1024)
    sections=[{'key':'section-'+str(i),'title':'A','body':'X'*4000} for i in range(40)]
    with pytest.raises(ValueError):lib.put_personal(path,{'name':'Size','design':lib.appearance(p),'sections':sections})
    assert not path.exists()


def test_delivery_with_profile_exports_all_formats_and_keeps_guidance(client):
    from io import BytesIO
    import json
    import zipfile
    slug=client.post('/api/demo',json={}).get_json()['slug']
    revision=client.get('/api/projects/'+slug).headers['ETag']
    applied=client.post('/api/projects/'+slug+'/design',json={'id':'htb-cpts','variant':'quiet'},headers={'If-Match':revision})
    assert applied.status_code==200
    delivered=client.post('/api/projects/'+slug+'/delivery',json={'formats':['pdf','docx','md'],'label':'Profile regression','acknowledge_warnings':True},headers={'If-Match':applied.headers['ETag']})
    assert delivered.status_code==200,delivered.get_json()
    with zipfile.ZipFile(BytesIO(delivered.data)) as archive:
        assert set(archive.namelist())=={'informe.pdf','informe.docx','markdown.zip','LEEME.txt','verificacion.json'}
        manifest=json.loads(archive.read('verificacion.json'))
        assert manifest['design_guidance']['name']=='CPTS'
        assert manifest['design_guidance']['source'] in archive.read('LEEME.txt').decode()
        assert len(manifest['files'])==3
    after=client.get('/api/projects/'+slug)
    assert after.headers['ETag']==applied.headers['ETag']
    assert after.get_json()['findings']==applied.get_json()['data']['findings']
