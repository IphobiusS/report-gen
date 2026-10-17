"""Practice identity is local server provenance, never a project name or import claim."""
from hashlib import sha256
from io import BytesIO
import json
import zipfile

import pytest

import app
import project_catalog
import project_history
from _support import auth_client


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / 'projects'
    root.mkdir()
    monkeypatch.setattr(app, 'PROJECTS', root)
    monkeypatch.setitem(app.app.config, 'LIBRARY_PATH', str(tmp_path / 'library.json'))
    return auth_client(app.app), root


def row(client, slug):
    return next(item for item in client.get('/api/projects').get_json() if item['slug'] == slug)


def test_normal_project_with_demo_shaped_name_is_not_practice(workspace):
    client, root = workspace
    slug = 'nimbus-demo-0123456789ab'
    assert client.post('/api/projects', json={'slug': slug, 'title': 'Real customer'}).status_code == 200
    before = (root / slug / 'engagement.yaml').read_bytes()
    assert row(client, slug)['practice'] is False
    assert not project_catalog.is_practice_project(root / slug)
    assert (root / slug / 'engagement.yaml').read_bytes() == before


@pytest.mark.parametrize('lang', ['es', 'en', 'pt'])
def test_demo_origin_is_server_recorded_without_report_metadata_changes(workspace, lang):
    client, root = workspace
    response = client.post('/api/demo', json={'lang': lang})
    assert response.status_code == 200
    assert response.get_json()['practice'] is True
    slug = response.get_json()['slug']
    project = root / slug
    before = {path.relative_to(project): path.read_bytes() for path in project.rglob('*') if path.is_file()}
    assert row(client, slug)['practice'] is True
    data = client.get('/api/projects/' + slug).get_json()
    assert data['meta']['lang'] == lang
    assert 'practice' not in data and 'practice' not in data['meta']
    assert before == {path.relative_to(project): path.read_bytes() for path in project.rglob('*') if path.is_file()}
    assert (project / project_catalog.PRACTICE_MARKER).read_bytes() == project_catalog.PRACTICE_ORIGIN


def test_save_rename_and_local_history_restore_preserve_origin(workspace):
    client, root = workspace
    slug = client.post('/api/demo', json={}).get_json()['slug']
    data = client.get('/api/projects/' + slug).get_json()
    original_title = data['meta']['report_title']
    data['meta']['report_title'] = 'Renamed practice'
    assert client.put('/api/projects/' + slug, json=data).status_code == 200
    assert row(client, slug)['practice'] is True
    tag = client.get('/api/projects/' + slug).headers['ETag']
    assert client.post('/api/projects/' + slug + '/restore', json={}, headers={'If-Match': tag}).status_code == 200
    assert client.get('/api/projects/' + slug).get_json()['meta']['report_title'] == original_title
    assert row(client, slug)['practice'] is True
    assert project_catalog.is_practice_project(root / slug)


def test_deleted_practice_identity_does_not_transfer_to_a_new_customer_project(workspace):
    client, _root = workspace
    slug = client.post('/api/demo', json={}).get_json()['slug']
    assert client.delete('/api/projects/' + slug).status_code == 200
    assert client.post('/api/projects', json={'slug': slug, 'title': 'Real customer replacement'}).status_code == 200
    assert row(client, slug)['practice'] is False


def test_portable_backup_cannot_carry_or_forge_local_origin(workspace):
    client, root = workspace
    slug = client.post('/api/demo', json={}).get_json()['slug']
    blob = project_history.export_bundle(root / slug)
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        assert project_catalog.PRACTICE_MARKER not in archive.namelist()
        members = {name: archive.read(name) for name in archive.namelist()}
    restored = 'nimbus-demo-ffffffffffff'
    project_history.import_bundle(blob, root / restored)
    assert row(client, restored)['practice'] is False
    # An otherwise intact archive cannot self-assert server creation provenance.
    manifest = json.loads(members['manifest.json'])
    manifest['files'][project_catalog.PRACTICE_MARKER] = sha256(project_catalog.PRACTICE_ORIGIN).hexdigest()
    members['manifest.json'] = json.dumps(manifest).encode()
    members[project_catalog.PRACTICE_MARKER] = project_catalog.PRACTICE_ORIGIN
    forged = BytesIO()
    with zipfile.ZipFile(forged, 'w') as archive:
        for name, value in members.items():
            archive.writestr(name, value)
    with pytest.raises(ValueError):
        project_history.import_bundle(forged.getvalue(), root / 'forged-copy')
    assert not (root / 'forged-copy').exists()


def test_marker_requires_bounded_exact_regular_local_file(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    marker = project / project_catalog.PRACTICE_MARKER
    for content in (b'{}', b'{"version":2,"origin":"nimbus-demo"}\n', project_catalog.PRACTICE_ORIGIN + b' ', b'x' * 65536):
        marker.write_bytes(content)
        assert project_catalog.is_practice_project(project) is False
    marker.unlink()
    target = tmp_path / 'external'
    target.write_bytes(project_catalog.PRACTICE_ORIGIN)
    try:
        marker.symlink_to(target)
    except OSError:
        pytest.skip('Symlinks unavailable on this platform')
    assert project_catalog.is_practice_project(project) is False
