"""New projects remain portable without changing existing project identities."""
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import PureWindowsPath
import zipfile

import pytest
import app as api
import project_history
import workspace_backup
from _support import auth_client


def project_bundle():
    value = b'meta: {report_title: Portable}\nfindings: []\n'
    output = BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('engagement.yaml', value)
        archive.writestr('manifest.json', json.dumps(dict(format='report-gen-project', version=1,
            files={'engagement.yaml': sha256(value).hexdigest()})))
    return output.getvalue()


@pytest.fixture
def local(tmp_path, monkeypatch):
    paths = (tmp_path/'workspace/projects', tmp_path/'workspace/library/findings.json',
             tmp_path/'workspace/library/designs.json')
    paths[0].mkdir(parents=True)
    monkeypatch.setattr(api, 'PROJECTS', paths[0])
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(paths[1]))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(paths[2]))
    return auth_client(api.app), paths


@pytest.mark.parametrize('name', ['CON', 'AUX', 'PRN', 'NUL', 'COM1', 'LPT9', 'COM¹', 'LPT²', 'COM³', '𐐀'*80])
@pytest.mark.parametrize('route', ['create', 'design', 'import'])
def test_all_creation_paths_use_portable_names_and_restore(local, tmp_path, name, route):
    client, paths = local
    if route == 'create':
        result = client.post('/api/projects', json={'title': name})
    elif route == 'design':
        result = client.post('/api/design-library/projects', json={'id': 'htb-cwee', 'title': name})
    else:
        result = client.post('/api/projects/import', data={'slug': name, 'file': (BytesIO(project_bundle()), 'project.zip')})
    assert result.status_code == 200, result.get_json()
    slug = result.get_json()['slug']
    assert not PureWindowsPath(slug).is_reserved()
    assert len(slug.encode('utf-8')) <= 240 and len(slug) <= 80
    assert workspace_backup._slug(slug)
    loaded = client.get('/api/projects/' + slug)
    assert loaded.status_code == 200
    if route != 'import':
        assert loaded.get_json()['meta']['report_title'] == name
    archive = workspace_backup.export_workspace(*paths)
    restored = tmp_path/'restored'
    assert workspace_backup.restore_workspace(archive, restored/'projects', restored/'findings.json', restored/'designs.json')['projects'] == 1
    assert (restored/'projects'/slug/'engagement.yaml').read_bytes() == (paths[0]/slug/'engagement.yaml').read_bytes()


@pytest.mark.skipif(os.name == 'nt', reason='Windows cannot contain these legacy project directories')
def test_legacy_reserved_name_stays_readable_and_individually_exportable(local):
    client, paths = local
    project_history.save(paths[0]/'con', {'meta': {'report_title': 'Existing identity'}, 'findings': []})
    result = client.get('/api/projects/con')
    assert result.status_code == 200 and result.get_json()['meta']['report_title'] == 'Existing identity'
    assert client.get('/api/projects/con/bundle').status_code == 200
    created = client.post('/api/projects', json={'title': 'CON'})
    assert created.get_json()['slug'] == 'con-project'
    assert (paths[0]/'con/engagement.yaml').is_file()
    assert client.post('/api/projects', json={'title': 'CON'}).status_code == 409


@pytest.mark.parametrize('slug', ['con', 'aux', 'nul', 'prn', 'com1', 'lpt9', 'com¹', 'lpt²', 'com³', '𐐨'*80])
def test_workspace_rejects_unportable_nested_names_before_activation(local, tmp_path, slug):
    _, paths = local
    source = workspace_backup.export_workspace(*paths)
    with zipfile.ZipFile(BytesIO(source)) as archive:
        files = {name: archive.read(name) for name in archive.namelist() if name != 'manifest.json'}
    files['projects/' + slug + '.zip'] = project_bundle()
    manifest = dict(format='report-gen-workspace', version=1,
        files={name: sha256(blob).hexdigest() for name, blob in files.items()})
    output = BytesIO()
    with zipfile.ZipFile(output, 'w') as archive:
        archive.writestr('manifest.json', json.dumps(manifest))
        for name, blob in files.items():
            archive.writestr(name, blob)
    target = tmp_path/'rejected'
    with pytest.raises(ValueError):
        workspace_backup.restore_workspace(output.getvalue(), target/'projects', target/'findings.json', target/'designs.json')
    assert not target.exists()
