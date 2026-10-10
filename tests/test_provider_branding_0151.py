"""Regressions found in the 0.15.1 review and provider-logo export contracts."""
from copy import deepcopy
from hashlib import sha256
import zipfile

import pytest
from lxml import html, etree
import app as webapp
import design_library as lib
import engine
import export
from provider_branding import ASSETS
from design_samples import sample_data
from _support import auth_client
from wizard import dump_yaml


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(webapp, 'PROJECTS', tmp_path/'projects')
    webapp.PROJECTS.mkdir()
    monkeypatch.setitem(webapp.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path/'designs.json'))
    return auth_client(webapp.app)


@pytest.mark.parametrize('bad', [['ejecutivo'], {'x':'ejecutivo'}, True, 7, None, '', 'unknown'])
def test_invalid_general_theme_never_500_or_changes_project(client, bad):
    slug=client.post('/api/design-library/projects',json={'id':'htb-cpts','title':'Unchanged'}).get_json()['slug']
    path=webapp.PROJECTS/slug/'engagement.yaml'
    before=path.read_bytes();etag=client.get('/api/projects/'+slug).headers['ETag']
    result=client.post('/api/projects/'+slug+'/design',json={'general':bad},headers={'If-Match':etag})
    assert result.status_code==422 and isinstance(result.get_json()['error'], str)
    assert path.read_bytes()==before


@pytest.mark.parametrize('sections', [[{'key':'findings'}], [{'key':'notes','title':'Notas','body':'TODO: redactar'}],
    [{'key':'notes','title':'Notas','body':'TODO: redactar'},{'key':'findings'}]])
def test_minimal_personal_design_preview_and_stored_variant(client, sections):
    p=lib.profile('htb-cpts');d=lib.appearance(p,'quiet')
    version=client.get('/api/design-library').headers['ETag']
    saved=client.post('/api/design-library/personal',json={'name':'Personal','design':d,'sections':sections},headers={'If-Match':version})
    assert saved.status_code==200
    ident=saved.get_json()['id']
    for lang in ('es','en'):
        preview=client.post('/api/design-library/preview',json={'id':ident,'lang':lang})
        assert preview.status_code==200
        assert b'sample-technical' in preview.data and b'provider-logo' in preview.data
    slug=client.post('/api/design-library/projects',json={'id':ident,'title':'My saved design'}).get_json()['slug']
    data=client.get('/api/projects/'+slug)
    assert data.get_json()['meta']['design']['variant']=='quiet'
    changed=client.post('/api/projects/'+slug+'/design',json={'id':ident,'variant':'brand'},headers={'If-Match':data.headers['ETag']})
    assert changed.status_code==200 and changed.get_json()['data']['meta']['design']['variant']=='brand'


@pytest.mark.parametrize('p',lib.catalog()['profiles'],ids=lambda p:p['id'])
@pytest.mark.parametrize('variant',lib.VARIANTS)
def test_every_profile_embeds_correct_offline_logo_without_mutating_content(p,variant,tmp_path):
    data=sample_data(p,variant);before=deepcopy(data)
    output=engine.render_html(engine.build_env(),data,tmp_path,{},False,engine.load_lang('es'))
    tree=html.fromstring(output)
    mark=tree.xpath('//span[@class="provider-logo"]')
    assert len(mark)==1
    assert mark[0].get('aria-label')==('OffSec' if p['provider']=='OffSec' else 'Hack The Box')
    assert len(mark[0].xpath('.//*[local-name()="svg"]'))==1
    assert not mark[0].xpath('.//*[@href or @src]')
    assert data==before


@pytest.mark.parametrize('ident,variant,expected', [('offsec-oscp','brand','offsec-on-light'),
    ('offsec-oswa','brand','offsec-on-dark'),('htb-cwes','brand','htb-on-dark'),
    ('htb-cpts','quiet','htb-mono')])
def test_word_embeds_provider_image_in_editable_document(ident,variant,expected,tmp_path):
    data=sample_data(lib.profile(ident),variant)
    dump_yaml(data,tmp_path/'engagement.yaml')
    path=export.export(tmp_path/'engagement.yaml','docx',tmp_path/'test.docx')
    wanted=sha256((ASSETS/(expected+'.png')).read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as z:
        assert wanted in {sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')}
        tree=etree.fromstring(z.read('word/document.xml'))
        assert tree.xpath('//*[local-name()="docPr"]/@descr')
        assert 'Evaluación de seguridad' in ''.join(tree.itertext())


def test_provider_identity_survives_personal_renaming(tmp_path):
    from provider_branding import provider_mark
    p=lib.profile('offsec-oscp');d=lib.appearance(p);d.update(provider='Personal',name='My company')
    assert provider_mark(d)['provider']=='OffSec'
    d['guidance_id']='../../outside'
    with pytest.raises(ValueError):provider_mark(d)


def test_custom_client_logos_remain_separate_from_provider(tmp_path):
    from PIL import Image
    data=sample_data(lib.profile('htb-cpts'))
    for name in ('author','client'):
        Image.new('RGB',(120,40),'#125580').save(tmp_path/(name+'.png'))
    data['meta']['branding'].update(logo='author.png',client_logo='client.png')
    tree=html.fromstring(engine.render_html(engine.build_env(),data,tmp_path,{},False,engine.load_lang('es')))
    assert len(tree.xpath('//span[@class="provider-logo"]'))==1
    assert len(tree.xpath('//div[@class="cv-logos"]/img'))==2
    dump_yaml(data,tmp_path/'engagement.yaml')
    path=export.export(tmp_path/'engagement.yaml','docx',tmp_path/'logos.docx')
    with zipfile.ZipFile(path) as z:
        tree=etree.fromstring(z.read('word/document.xml'))
        descriptions=tree.xpath('//*[local-name()="docPr"]/@descr')
        assert 'Hack The Box' in descriptions and 'logo' in descriptions and 'client logo' in descriptions


def test_word_logo_rasters_retain_brand_colors_and_transparency():
    from PIL import Image
    for key in ('offsec-on-dark','offsec-on-light','htb-on-dark','htb-on-light'):
        im=Image.open(ASSETS/(key+'.png')).convert('RGBA')
        pixels=list(im.getdata())
        assert any(a==0 for r,g,b,a in pixels),key
        assert sum(a>200 and max(r,g,b)-min(r,g,b)>50 for r,g,b,a in pixels)>500,key
