"""Explicit external data selection, legacy continuity and lossless migration."""
from hashlib import sha256
import json
import os
from pathlib import Path
import stat
import subprocess
import sys

import pytest

import design_library
import finding_library
from input_guard import load_yaml_file
import launcher_upgrade
import project_history
import start
import workspace_backup
from workspace_paths import ENVIRONMENT_KEY, select_workspace, workspace_environment

ROOT = Path(__file__).resolve().parents[1]


def installation(root):
    (root / 'webapp/projects').mkdir(parents=True)
    (root / 'webapp/app.py').write_text('raise RuntimeError("do not execute old code")')
    (root / 'engine.py').write_text('raise RuntimeError("do not execute old code")')
    (root / 'webapp/projects/.gitkeep').touch()
    return root


def contents(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_default_preserves_legacy_and_selection_is_read_only(tmp_path):
    app = installation(tmp_path / 'application')
    (app / 'webapp/projects/keep.txt').write_text('Existing project')
    before = contents(app)
    legacy = select_workspace(app, environ={})
    assert not legacy.external and legacy.projects == app / 'webapp/projects'
    external = select_workspace(app, tmp_path / 'data', environ={})
    assert external.external and not external.root.exists()
    assert contents(app) == before


def test_cli_precedes_environment_and_child_path_survives_cwd_change(tmp_path, monkeypatch):
    app = installation(tmp_path / 'application')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(ENVIRONMENT_KEY, str(tmp_path / 'environment'))
    selected = select_workspace(app, 'selected')
    assert selected.root == tmp_path / 'selected'
    with workspace_environment(selected):
        monkeypatch.chdir(app)
        child = select_workspace(app)
        assert child == selected
    assert os.environ[ENVIRONMENT_KEY] == str(tmp_path / 'environment')


def test_create_external_layout_with_private_new_directories(tmp_path):
    selected = select_workspace(tmp_path / 'application', tmp_path / 'data', environ={}, create=True)
    assert selected.projects.is_dir() and selected.findings.parent.is_dir()
    assert not selected.findings.exists() and not selected.designs.exists()
    assert not (tmp_path / 'application').exists()
    if os.name == 'posix':
        assert all(stat.S_IMODE(p.stat().st_mode) == 0o700 for p in (
            selected.root, selected.projects, selected.findings.parent))


@pytest.mark.parametrize('relative', ['', '.', 'webapp/data', '..'])
def test_empty_or_overlapping_selection_is_rejected_without_writes(tmp_path, relative):
    app = installation(tmp_path / 'application')
    target = '' if relative == '' else app / relative
    before = contents(app)
    with pytest.raises(ValueError):
        select_workspace(app, target, environ={}, create=True)
    assert contents(app) == before


@pytest.mark.parametrize('component', ['root', 'projects', 'library', 'findings'])
def test_links_in_managed_paths_are_rejected_before_creation(tmp_path, component):
    app = installation(tmp_path / 'application')
    outside = tmp_path / 'outside'
    outside.mkdir()
    root = tmp_path / 'data'
    try:
        if component == 'root':
            root.symlink_to(outside, target_is_directory=True)
        else:
            root.mkdir()
            if component == 'findings':
                (root / 'library').mkdir()
                (outside / 'findings.json').write_text('private')
                (root / 'library/findings.json').symlink_to(outside / 'findings.json')
            else:
                (root / component).symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip('Creating symbolic links is unavailable')
    before = contents(outside)
    with pytest.raises(ValueError):
        select_workspace(app, root, environ={}, create=True)
    assert contents(outside) == before


def test_hardlinked_library_is_rejected(tmp_path):
    root = tmp_path / 'data'
    (root / 'library').mkdir(parents=True)
    original = tmp_path / 'private.json'
    original.write_text('{}')
    os.link(original, root / 'library/findings.json')
    with pytest.raises(ValueError):
        select_workspace(tmp_path / 'application', root, environ={}, create=True)
    assert not (root / 'projects').exists()


@pytest.mark.parametrize('selected', ['cli', 'environment'])
def test_launcher_propagates_selection_and_restores_environment(tmp_path, monkeypatch, capsys, selected):
    app = installation(tmp_path / 'application')
    root = tmp_path / 'private data'
    monkeypatch.setattr(start, 'ROOT', app)
    monkeypatch.setattr(start, '_dependencies', lambda python: True)
    monkeypatch.delenv(ENVIRONMENT_KEY, raising=False)
    if selected == 'environment':
        monkeypatch.setenv(ENVIRONMENT_KEY, str(root))
    observed = []
    monkeypatch.setattr(start, '_run_server', lambda *args: observed.append(select_workspace(app)) or 0)
    assert start.main(['--workspace', str(root)] if selected == 'cli' else []) == 0
    assert observed[0].root == root
    assert str(root) in capsys.readouterr().out
    assert os.environ.get(ENVIRONMENT_KEY) == (str(root) if selected == 'environment' else None)


def test_external_migration_keeps_history_libraries_and_original_bytes(tmp_path):
    app = installation(tmp_path / 'application')
    directory = app / 'webapp/projects/client'
    data = {'meta': {'report_title': 'Before', 'lang': 'es'}, 'findings': []}
    project_history.save(directory, data)
    project_history.checkpoint(directory, 'Before', force=True)
    data['meta']['report_title'] = 'Current'
    project_history.save(directory, data)
    finding_library.put(app / 'webapp/library/findings.json', {
        'name': 'Reusable', 'content': {'title': 'Finding', 'mode': 'vuln', 'severity': 'info'}})
    design = design_library.profile('offsec-oscp')
    design_library.put_personal(app / 'webapp/library/designs.json', {
        'name': 'Personal design', 'design': design_library.appearance(design, 'quiet'),
        'sections': design['sections']})
    before = contents(app)
    root = tmp_path / 'external'
    result = launcher_upgrade.upgrade(app, app, workspace=root,
        backup_directory=tmp_path / 'backups', lang='en')
    assert result['source_preserved'] and result['projects'] == result['findings'] == result['designs'] == 1
    assert contents(app) == before
    assert load_yaml_file(root / 'projects/client/engagement.yaml') == data
    assert project_history.history(root / 'projects/client')
    assert finding_library.load(root / 'library/findings.json') == finding_library.load(app / 'webapp/library/findings.json')
    assert design_library.load_personal(root / 'library/designs.json') == design_library.load_personal(app / 'webapp/library/designs.json')
    archive = Path(result['backup']).read_bytes()
    assert result['sha256'] == sha256(archive).hexdigest()
    restore = tmp_path / 'independent-restore'
    assert workspace_backup.restore_workspace(archive, restore / 'projects', restore / 'library/findings.json',
                                               restore / 'library/designs.json')['projects'] == 1
    # Replacing the installation changes no chosen data location.
    second = installation(tmp_path / 'new-version')
    assert select_workspace(second, root, environ={}).projects == root / 'projects'


def test_external_migration_never_merges_occupied_destination(tmp_path):
    app = installation(tmp_path / 'application')
    root = tmp_path / 'external'
    (root / 'projects/keep').mkdir(parents=True)
    (root / 'projects/keep/private.txt').write_text('keep')
    before = contents(root)
    with pytest.raises(ValueError, match='empty'):
        launcher_upgrade.upgrade(app, app, workspace=root,
            backup_directory=tmp_path / 'backups', lang='en')
    assert contents(root) == before and not (tmp_path / 'backups').exists()


def test_external_migration_rejects_backup_inside_current_installation(tmp_path):
    source = installation(tmp_path / 'old')
    app = installation(tmp_path / 'application')
    root = tmp_path / 'external'
    with pytest.raises(ValueError, match='outside'):
        launcher_upgrade.upgrade(source, app, workspace=root,
            backup_directory=app / 'backups', lang='en')
    assert not root.exists() and not (app / 'backups').exists()


@pytest.mark.parametrize('failure', [1, 2, 3])
def test_interrupted_external_activation_rolls_back_and_keeps_verified_backup(tmp_path, monkeypatch, failure):
    app = installation(tmp_path / 'application')
    project_history.save(app / 'webapp/projects/client', {
        'meta': {'report_title': 'Original', 'lang': 'es'}, 'findings': []})
    before = contents(app)
    root = tmp_path / 'external'
    paths = (root / 'projects', root / 'library/findings.json', root / 'library/designs.json')
    original_move = workspace_backup._move
    calls = 0

    def interrupted_move(source, destination):
        nonlocal calls
        original_move(source, destination)
        if destination in paths:
            calls += 1
            if calls == failure:
                raise OSError('Interrupted activation')

    monkeypatch.setattr(workspace_backup, '_move', interrupted_move)
    with pytest.raises(ValueError, match='Keep both installations and the backup'):
        launcher_upgrade.upgrade(app, app, workspace=root,
            backup_directory=tmp_path / 'backups', lang='en')
    monkeypatch.setattr(workspace_backup, '_move', original_move)
    assert contents(app) == before
    assert (root / '.workspace-restore.json').exists()
    workspace_backup.recover(*paths)
    assert not list(paths[0].iterdir())
    assert not paths[1].exists() and not paths[2].exists()
    assert not (root / '.workspace-restore.json').exists()
    archive, = (tmp_path / 'backups').glob('upgrade-*/workspace.zip')
    assert workspace_backup.restore_workspace(archive.read_bytes(), *paths)['projects'] == 1
    assert load_yaml_file(root / 'projects/client/engagement.yaml')['meta']['report_title'] == 'Original'


def test_external_flask_creation_library_and_backup_use_only_selected_paths(tmp_path):
    root = tmp_path / 'external'
    script = '''
import json
from pathlib import Path
from io import BytesIO
import zipfile
import sys
sys.path.insert(0, 'webapp')
import app as api
import finding_library
c = api.app.test_client()
csrf = c.get('/api/session').get_json()['csrf']
headers = {'X-CSRF-Token': csrf}
r = c.post('/api/projects', json={'slug':'external-only','title':'External'}, headers=headers)
assert r.status_code == 200, r.get_json()
finding_library.put(Path(api.app.config['LIBRARY_PATH']), {'name':'Reusable','content':{'title':'Finding','mode':'vuln','severity':'info'}})
r = c.post('/api/workspace/backup', json={}, headers=headers)
assert r.status_code == 200, r.get_json()
with zipfile.ZipFile(BytesIO(r.data)) as archive:
    names = sorted(archive.namelist())
print(json.dumps({'projects':str(api.PROJECTS),'library':api.app.config['LIBRARY_PATH'],
 'designs':api.app.config['DESIGN_LIBRARY_PATH'],'names':names}))
'''
    completed = subprocess.run([sys.executable, '-c', script], cwd=ROOT,
        env=dict(os.environ, **{ENVIRONMENT_KEY: str(root)}), capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert Path(result['projects']) == root / 'projects'
    assert Path(result['library']) == root / 'library/findings.json'
    assert Path(result['designs']) == root / 'library/designs.json'
    assert result['names'] == ['libraries/designs.json', 'libraries/findings.json', 'manifest.json', 'projects/external-only.zip']
    assert not (ROOT / 'webapp/projects/external-only').exists()
