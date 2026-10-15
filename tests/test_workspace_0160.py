"""Workspace data must survive backup, validation failures and interrupted restore."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import stat
import zipfile

import pytest
import app as webapp
import design_library as designs
import finding_library as findings
import workspace_backup as backup
from _support import auth_client


@pytest.fixture
def source(tmp_path, monkeypatch):
    root=tmp_path/'source';root.mkdir()
    paths=(root/'projects',root/'library'/'findings.json',root/'library'/'designs.json')
    paths[0].mkdir()
    monkeypatch.setattr(webapp,'PROJECTS',paths[0])
    monkeypatch.setitem(webapp.app.config,'LIBRARY_PATH',str(paths[1]))
    monkeypatch.setitem(webapp.app.config,'DESIGN_LIBRARY_PATH',str(paths[2]))
    client=auth_client(webapp.app)
    slug=client.post('/api/demo',json={}).get_json()['slug']
    data=client.get('/api/projects/'+slug).get_json()
    entry=findings.put(paths[1],{'name':'Reusable finding','content':{'title':'Test','mode':'vuln','severity':'info'}})
    findings.put(paths[1],{'name':'Updated finding','content':{'title':'Second version','mode':'vuln','severity':'info'}},entry['uid'])
    p=designs.profile('offsec-oscp')
    designs.put_personal(paths[2],{'name':'Personal bilingual','design':designs.appearance(p,'quiet'),'sections':p['sections']})
    return paths,client,slug,data


def destination(tmp_path):
    root=tmp_path/'destination';root.mkdir(exist_ok=True)
    return root/'projects',root/'library'/'findings.json',root/'library'/'designs.json'


def unpack(blob):
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        return {n:archive.read(n) for n in archive.namelist()}


def repack(files, hashes=True):
    if hashes:
        manifest=json.loads(files['manifest.json'])
        manifest['files']={n:sha256(v).hexdigest() for n,v in files.items() if n!='manifest.json'}
        files['manifest.json']=json.dumps(manifest).encode()
    out=BytesIO()
    with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
        for n,v in files.items():z.writestr(n,v)
    return out.getvalue()


def test_round_trip_all_data_and_libraries(source,tmp_path):
    paths,client,slug,original=source
    r=client.post('/api/workspace/backup',json={})
    assert r.status_code==200,r.get_json()
    target=destination(tmp_path)
    result=backup.restore_workspace(r.data,*target)
    assert result=={'projects':1,'findings':1,'designs':1}
    from input_guard import load_yaml_file
    assert load_yaml_file(target[0]/slug/'engagement.yaml')==original
    assert findings.load(paths[1])==findings.load(target[1])
    assert designs.load_personal(paths[2])==designs.load_personal(target[2])
    for folder in ('img','originals','history/objects','history/snapshots'):
        expected={p.relative_to(paths[0]/slug/folder).as_posix():p.read_bytes() for p in (paths[0]/slug/folder).rglob('*') if p.is_file()}
        actual={p.relative_to(target[0]/slug/folder).as_posix():p.read_bytes() for p in (target[0]/slug/folder).rglob('*') if p.is_file()}
        assert actual==expected
    assert not (target[0].parent/'.workspace-restore.json').exists()


@pytest.mark.parametrize('which',[0,1,2])
def test_no_overwrite_of_existing_work(source,tmp_path,which):
    paths,_,_,_=source
    blob=backup.export_workspace(*paths);target=destination(tmp_path)
    if which==0:
        target[0].mkdir();(target[0]/'keep.txt').write_text('original')
    else:
        target[which].parent.mkdir(parents=True,exist_ok=True)
        target[which].write_bytes(paths[which].read_bytes())
    before={p.relative_to(target[0].parent):p.read_bytes() for p in target[0].parent.rglob('*') if p.is_file()}
    with pytest.raises(ValueError,match='vacía'):backup.restore_workspace(blob,*target)
    assert {p.relative_to(target[0].parent):p.read_bytes() for p in target[0].parent.rglob('*') if p.is_file()}==before


@pytest.mark.parametrize('failure',range(1,7))
def test_interruption_rolls_back_every_activation_rename(source,tmp_path,monkeypatch,failure):
    paths,_,_,_=source;blob=backup.export_workspace(*paths);target=destination(tmp_path)
    target[0].mkdir();target[1].parent.mkdir()
    target[1].write_text(json.dumps(findings.load(target[1])))
    target[2].write_text(json.dumps(designs.load_personal(target[2])))
    previous=[None,target[1].read_bytes(),target[2].read_bytes()]
    real=backup._move;calls=0
    def interrupt(a,b):
        nonlocal calls
        calls+=1
        real(a,b)
        if calls==failure:raise OSError('simulated interruption')
    monkeypatch.setattr(backup,'_move',interrupt)
    with pytest.raises(OSError):backup.restore_workspace(blob,*target)
    monkeypatch.setattr(backup,'_move',real)
    backup.recover(*target);backup.recover(*target)
    assert not list(target[0].iterdir())
    assert target[1].read_bytes()==previous[1] and target[2].read_bytes()==previous[2]
    assert backup.restore_workspace(blob,*target)['projects']==1


@pytest.mark.parametrize('attack',['traversal','checksum','missing','library','nested','duplicate','symlink','truncated','template-path'])
def test_invalid_archive_never_installs_anything(source,tmp_path,attack):
    paths,_,_,_=source;files=unpack(backup.export_workspace(*paths))
    if attack=='traversal':files['../outside.txt']=b'no'
    if attack=='checksum':files['libraries/designs.json']+=b' '
    if attack=='missing':del files['libraries/findings.json']
    if attack=='library':files['libraries/findings.json']=b'{"format":"report-gen-library","version":1,"templates":[null]}'
    if attack=='nested':files[next(n for n in files if n.startswith('projects/'))]=b'not a ZIP'
    if attack=='template-path':
        library=json.loads(files['libraries/findings.json']);library['templates'][0]['uid']='../projects/test'
        files['libraries/findings.json']=json.dumps(library).encode()
    blob=repack(files,hashes=attack!='checksum')
    if attack in ('duplicate','symlink'):
        stream=BytesIO(blob)
        with zipfile.ZipFile(stream,'a') as z:
            if attack=='duplicate':z.writestr('libraries/findings.json',b'{}')
            else:
                link=zipfile.ZipInfo('projects/linked.zip');link.create_system=3;link.external_attr=(stat.S_IFLNK|0o777)<<16;z.writestr(link,'/tmp')
        blob=stream.getvalue()
    if attack=='truncated':blob=blob[:len(blob)//2]
    target=destination(tmp_path)
    with pytest.raises(ValueError):backup.restore_workspace(blob,*target)
    assert not any(p.is_file() for p in target[0].parent.rglob('*'))


def test_size_budget_includes_nested_expansion(source,tmp_path,monkeypatch):
    paths,_,_,_=source;blob=backup.export_workspace(*paths)
    files=unpack(blob);outer=sum(map(len,files.values()))
    monkeypatch.setattr(backup,'MAX_EXPANDED',outer+10)
    with pytest.raises(ValueError,match='integral'):backup.restore_workspace(blob,*destination(tmp_path))


def test_api_restore_and_csrf(source,tmp_path,monkeypatch):
    paths,client,_,_=source;blob=backup.export_workspace(*paths)
    plain=webapp.app.test_client()
    assert plain.post('/api/workspace/backup',json={}).status_code==403
    target=destination(tmp_path);target[0].mkdir()
    monkeypatch.setattr(webapp,'PROJECTS',target[0])
    monkeypatch.setitem(webapp.app.config,'LIBRARY_PATH',str(target[1]))
    monkeypatch.setitem(webapp.app.config,'DESIGN_LIBRARY_PATH',str(target[2]))
    r=client.post('/api/workspace/restore',data={'file':(BytesIO(blob),'backup.zip')})
    assert r.status_code==200,r.get_json()
    assert r.get_json()['projects']==1
    assert len(client.get('/api/projects').get_json())==1


@pytest.mark.parametrize('profile',designs.catalog()['profiles'],ids=lambda p:p['id'])
@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
def test_every_enabled_profile_has_complete_localizations(profile, language):
    # Check source translations instead of accepting localized()'s Spanish fallback.
    for section in profile['sections']:
        for field in ('title','body'):
            if field in section:
                assert isinstance(section[field],dict) and set(section[field])=={'es','en','pt'}
                assert all(isinstance(v,str) and v.strip() for v in section[field].values())
    assert profile['guidance']['note'][language]
    report=designs.new_report(profile,'Localized assessment',language)
    assert report['meta']['branding']['confidential_text']=={'es':'CONFIDENCIAL','en':'CONFIDENTIAL','pt':'CONFIDENCIAL'}[language]
    assert report['report']['sections']==designs.starter_sections(profile,language)
    snapshot=deepcopy(report)
    assert designs.apply(report,profile,'quiet')['report']==snapshot['report']
