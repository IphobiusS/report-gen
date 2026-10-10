"""Opaque persistent browser scope and stale-tab API/resource rejection."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
import os
import shutil
import stat
import zipfile

from lxml import html
from PIL import Image
import pytest

import app as api
import project_history
import workspace_backup
from workspace_paths import BROWSER_ID_FILE, browser_namespace


def paths(root):
    return root / 'projects', root / 'library/findings.json', root / 'library/designs.json'


def test_namespace_is_stable_private_and_distinct_without_path_disclosure(tmp_path):
    first, second = tmp_path / 'first', tmp_path / 'second'
    scope = browser_namespace(*paths(first))
    assert scope == browser_namespace(*paths(first))
    assert scope != browser_namespace(*paths(second))
    assert len(scope) == 64 and all(letter in '0123456789abcdef' for letter in scope)
    identity = first / BROWSER_ID_FILE
    assert len(identity.read_bytes()) == 65 and scope not in identity.read_text()
    if os.name == 'posix':
        assert stat.S_IMODE(identity.stat().st_mode) == 0o600
    # Copying to another root must not make two independently used locations
    # share browser drafts, even if someone copied the local identity file.
    moved = tmp_path / 'moved'
    shutil.copytree(first, moved)
    assert browser_namespace(*paths(moved)) != scope


def test_concurrent_first_boot_keeps_one_identity(tmp_path):
    selected = paths(tmp_path / 'data')
    with ThreadPoolExecutor(max_workers=12) as executor:
        ids = list(executor.map(lambda _: browser_namespace(*selected), range(24)))
    assert len(set(ids)) == 1
    assert browser_namespace(*selected) == ids[0]


@pytest.mark.parametrize('content', [b'', b'not-an-identity', b'a' * 64, b'z' * 64 + b'\n', b'a' * 65 + b'\n'])
def test_damaged_identity_is_never_regenerated(tmp_path, content):
    root = tmp_path / 'data'
    root.mkdir()
    identity = root / BROWSER_ID_FILE
    identity.write_bytes(content)
    with pytest.raises(ValueError, match='identidad'):
        browser_namespace(*paths(root))
    assert identity.read_bytes() == content


@pytest.mark.parametrize('kind', ['symlink', 'hardlink'])
def test_linked_identity_is_rejected_without_touching_target(tmp_path, kind):
    root = tmp_path / 'data'
    root.mkdir()
    original = tmp_path / 'outside'
    original.write_bytes(b'a' * 64 + b'\n')
    try:
        if kind == 'symlink':
            (root / BROWSER_ID_FILE).symlink_to(original)
        else:
            os.link(original, root / BROWSER_ID_FILE)
    except OSError:
        pytest.skip('Filesystem link creation is unavailable')
    with pytest.raises(ValueError):
        browser_namespace(*paths(root))
    assert original.read_bytes() == b'a' * 64 + b'\n'


@pytest.fixture
def selected(tmp_path, monkeypatch):
    def select(name):
        root = tmp_path / name
        locations = paths(root)
        locations[0].mkdir(parents=True, exist_ok=True)
        monkeypatch.setattr(api, 'PROJECTS', locations[0])
        monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(locations[1]))
        monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(locations[2]))
        return root
    select('first')
    return select


def test_bootstrap_exposes_only_opaque_scope_and_preserves_unscoped_api_clients(selected, tmp_path):
    client = api.app.test_client()
    response = client.get('/api/session')
    data = response.get_json()
    assert set(data) == {'version', 'csrf', 'workspace_id'}
    assert data['workspace_id'] == response.headers['X-Report-Gen-Workspace']
    assert str(tmp_path) not in response.get_data(as_text=True)
    assert client.get('/api/projects').status_code == 200
    assert client.post('/api/projects', json={'slug': 'same'}, headers={'X-CSRF-Token': data['csrf']}).status_code == 200


def test_stale_scope_is_rejected_before_read_write_or_session_refresh(selected):
    client = api.app.test_client()
    first = client.get('/api/session').get_json()
    headers = {'X-CSRF-Token': first['csrf'], 'X-Report-Gen-Workspace': first['workspace_id']}
    assert client.post('/api/projects', json={'slug': 'same', 'title': 'A'}, headers=headers).status_code == 200
    root = selected('second')
    second = client.get('/api/session').get_json()
    assert first['workspace_id'] != second['workspace_id']
    assert client.post('/api/projects', json={'slug': 'same', 'title': 'B'}, headers={'X-CSRF-Token': second['csrf']}).status_code == 200
    target = root / 'projects/same/engagement.yaml'
    before = target.read_bytes()
    current = client.get('/api/projects/same')
    for url in ('/api/session', '/api/projects', '/api/projects/same'):
        rejected = client.get(url, headers=headers)
        assert rejected.status_code == 409
        assert rejected.headers['X-Report-Gen-Workspace'] == second['workspace_id']
    rejected = client.put('/api/projects/same', json=current.get_json(),
                          headers={**headers, 'If-Match': current.headers['ETag']})
    assert rejected.status_code == 409 and target.read_bytes() == before
    selected('first')
    assert client.get('/api/session').get_json()['workspace_id'] == first['workspace_id']


def test_native_images_and_live_markdown_use_query_scope(selected):
    root = selected('first')
    directory = root / 'projects/same'
    (directory / 'img').mkdir(parents=True)
    Image.new('RGB', (2, 2), 'red').save(directory / 'img/example.png')
    project_history.save(directory, {'meta': {'report_title': 'Example', 'theme': 'serio', 'lang': 'es'},
        'findings': [{'id': 'F1', 'mode': 'vuln', 'severity': 'info', 'title': 'Finding',
                      'walkthrough': [{'figure': {'src': 'img/example.png', 'caption': 'Evidence'}}]}]})
    client = api.app.test_client()
    session = client.get('/api/session').get_json()
    headers = {'X-CSRF-Token': session['csrf'], 'X-Report-Gen-Workspace': session['workspace_id']}
    scope = session['workspace_id']
    assert client.get('/api/projects/same/img/example.png?workspace_id=' + scope).status_code == 200
    assert client.get('/api/projects/same/resource/img/example.png?workspace_id=' + '0' * 64).status_code == 409
    assert client.get('/api/projects/same/img/example.png?workspace_id=' + scope + '&workspace_id=' + scope).status_code == 409
    response = client.post('/api/md', json={'slug': 'same', 'text': '![Evidence](img/example.png)'}, headers=headers)
    assert response.status_code == 200
    image = html.fragment_fromstring(response.get_json()['html'], create_parent=True).xpath('.//img/@src')[0]
    assert 'workspace_id=' + scope in image
    preview = client.post('/api/projects/same/preview', headers=headers)
    assert preview.status_code == 200, preview.get_json()
    sources = html.fromstring(preview.data).xpath('//img/@src')
    assert sources and all('workspace_id=' + scope in src for src in sources if src.startswith('/api/'))


def test_workspace_backup_excludes_browser_identity_and_drafts(selected):
    root = selected('first')
    scope = browser_namespace(*paths(root))
    payload = workspace_backup.export_workspace(*paths(root))
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        assert set(archive.namelist()) == {'libraries/designs.json', 'libraries/findings.json', 'manifest.json'}
        assert all(scope.encode() not in archive.read(name) and BROWSER_ID_FILE.encode() not in archive.read(name)
                   for name in archive.namelist())
