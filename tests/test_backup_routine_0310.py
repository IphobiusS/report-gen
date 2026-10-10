"""Backups restore real histories; rotation is limited to intact owned archives."""
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import os
import threading
import zipfile

import pytest
import app as api
import backup_routine as module
import project_history
import workspace_backup
from _support import auth_client


@pytest.fixture
def setup(tmp_path):
    root = tmp_path/'workspace'
    paths = (root/'projects', root/'library/findings.json', root/'library/designs.json')
    project_history.save(paths[0]/'synthetic', {'meta': {'report_title': 'PRIVATE_SENTINEL', 'lang': 'es'}, 'findings': []})
    app = tmp_path/'application'
    app.mkdir()
    destination = tmp_path/'private-backups'
    destination.mkdir()
    clock = [1791660000.0]
    routine = module.BackupRoutine(*paths, app, threading.RLock(), clock=lambda: clock[0])
    body = dict(enabled=False, destination=str(destination), interval_seconds=3600, retention=2, ack_unencrypted=True)
    return routine, body, clock


def test_default_off_and_no_copy_until_opt_in(setup):
    routine, _, _ = setup
    routine.tick()
    assert routine.status()['enabled'] is False
    assert routine.status()['last_success'] is None
    assert not routine.state_path.exists()


def test_real_capture_restore_and_private_configuration_excluded(setup, tmp_path):
    routine, body, clock = setup
    routine.configure(body)
    before = (routine.paths[0]/'synthetic/engagement.yaml').read_bytes()
    result = routine.run()
    archive = Path(result['directory'])/result['latest_name']
    assert result['last_success'] == clock[0] == result['last_verified']
    assert sha256(archive.read_bytes()).hexdigest() == result['latest_sha256']
    with zipfile.ZipFile(BytesIO(archive.read_bytes())) as package:
        assert set(package.namelist()) == {'manifest.json', 'projects/synthetic.zip', *workspace_backup.LIBRARIES}
        assert module.STATE_NAME not in package.namelist()
    restored = tmp_path/'restored'
    counts = workspace_backup.restore_workspace(archive.read_bytes(), restored/'projects', restored/'library/findings.json', restored/'library/designs.json')
    assert counts['projects'] == 1
    assert (restored/'projects/synthetic/engagement.yaml').read_bytes() == before
    assert not list(Path(result['directory']).glob('.restore-check-*'))
    clock[0] += 100
    assert routine.verify_latest()['last_verified'] == clock[0]
    assert routine.status()['last_success'] != routine.status()['last_verified']
    assert (routine.paths[0]/'synthetic/engagement.yaml').read_bytes() == before
    if os.name != 'nt':
        assert archive.stat().st_mode & 0o077 == 0
        assert routine.state_path.stat().st_mode & 0o077 == 0


def test_due_restart_disable_and_no_browser_requirement(setup):
    routine, body, clock = setup
    routine.configure({**body, 'enabled': True})
    routine.tick()
    first = routine.status()
    clock[0] += 3599
    routine.tick()
    assert routine.status()['latest_name'] == first['latest_name']
    clock[0] += 2
    restarted = module.BackupRoutine(*routine.paths, routine.installation, routine.mutation_lock, clock=lambda: clock[0])
    restarted.tick()
    assert restarted.status()['latest_name'] != first['latest_name']
    restarted.disable()
    last = restarted.status()['latest_name']
    clock[0] += 90000
    restarted.tick()
    assert restarted.status()['latest_name'] == last


def test_retention_deletes_only_registered_intact_copies(setup):
    routine, body, clock = setup
    routine.configure(body)
    first = routine.run()
    folder = Path(first['directory'])
    unrelated = folder/'workspace-20261010T111111Z-aaaaaaaaaaaaaaaa.zip'
    unrelated.write_bytes(b'UNRELATED_PRIVATE_COPY')
    (folder/'notes.md').write_text('user-authored, not owned')
    clock[0] += 10
    second = routine.run()
    clock[0] += 10
    third = routine.run()
    assert not (folder/first['latest_name']).exists()
    assert (folder/second['latest_name']).exists() and (folder/third['latest_name']).exists()
    assert unrelated.read_bytes() == b'UNRELATED_PRIVATE_COPY'
    assert (folder/'notes.md').read_text() == 'user-authored, not owned'
    assert third['copies'] == 2


def test_changed_old_archive_is_preserved_and_reported(setup):
    routine, body, clock = setup
    routine.configure({**body, 'retention': 1})
    first = routine.run()
    old = Path(first['directory'])/first['latest_name']
    old.write_bytes(b'USER_REPLACED_COPY')
    clock[0] += 5
    result = routine.run()
    assert old.read_bytes() == b'USER_REPLACED_COPY'
    assert result['copies'] == 2 and result['last_error'] == 'retention_pending'


def test_directory_changes_never_rotate_previous_destination(setup, tmp_path):
    routine, body, clock = setup
    routine.configure({**body, 'retention': 1})
    first = routine.run()
    old = Path(first['directory'])/first['latest_name']
    elsewhere = tmp_path/'other-backups'
    elsewhere.mkdir()
    routine.configure({**body, 'destination': str(elsewhere), 'retention': 1})
    routine.run()
    clock[0] += 10
    routine.run()
    assert old.exists()
    routine.configure(body)
    assert routine.status()['directory'] != first['directory']
    assert old.exists() and routine.status()['last_success'] is None


@pytest.mark.parametrize('kind', ['workspace', 'application', 'parent', 'child', 'relative', 'missing', 'traversal', 'nul'])
def test_destination_rejects_overlaps_or_unsafe_input(setup, kind):
    routine, body, _ = setup
    values = dict(workspace=str(routine.root), application=str(routine.installation), parent=str(routine.root.parent),
                  child=str(routine.paths[0]), relative='relative-path', missing=str(routine.root.parent/'missing'),
                  traversal=str(routine.root/'..'/'private-backups'), nul='\x00')
    with pytest.raises((ValueError, OSError)):
        routine.configure({**body, 'destination': values[kind]})
    assert not routine.state_path.exists()


@pytest.mark.parametrize('field,value', [('ack_unencrypted', False), ('enabled', 1), ('retention', 0), ('retention', 91),
    ('retention', True), ('retention', 1.5), ('interval_seconds', 60), ('interval_seconds', True)])
def test_configuration_strict_types_and_ack(setup, field, value):
    routine, body, _ = setup
    with pytest.raises(ValueError):
        routine.configure({**body, field: value})
    assert not routine.state_path.exists()


@pytest.mark.parametrize('phase', ['export', 'restore', 'write'])
def test_failed_new_copy_preserves_existing_before_rotation(setup, monkeypatch, phase):
    routine, body, clock = setup
    routine.configure({**body, 'retention': 1, 'enabled': True})
    first = routine.run()
    previous = Path(first['directory'])/first['latest_name']
    before = previous.read_bytes()
    clock[0] += 3700
    def fail(*args, **kwargs):
        raise OSError('PRIVATE_PATH_SENTINEL_AND_CUSTOMER_MUST_NOT_ESCAPE')
    if phase == 'export':
        monkeypatch.setattr(workspace_backup, 'export_workspace', fail)
    elif phase == 'restore':
        monkeypatch.setattr(routine, '_restore_check', fail)
    else:
        monkeypatch.setattr(module.tempfile, 'mkstemp', fail)
    with pytest.raises(ValueError) as error:
        routine.run()
    assert 'PRIVATE_PATH' not in str(error.value)
    assert previous.read_bytes() == before
    assert routine.status()['last_success'] == first['last_success']
    assert routine.status()['last_error'] == module.FAILURE
    assert routine.retry_after == clock[0] + 300


def test_last_copy_verification_detects_corruption_without_touching_projects(setup):
    routine, body, clock = setup
    routine.configure(body)
    result = routine.run()
    before = (routine.paths[0]/'synthetic/engagement.yaml').read_bytes()
    (Path(result['directory'])/result['latest_name']).write_bytes(b'corrupted')
    clock[0] += 10
    with pytest.raises(ValueError):
        routine.verify_latest()
    assert routine.status()['last_verified'] == result['last_verified']
    assert routine.status()['last_error'] == module.FAILURE
    assert (routine.paths[0]/'synthetic/engagement.yaml').read_bytes() == before


def test_capture_holds_the_same_mutation_lock(setup, monkeypatch):
    routine, body, _ = setup
    routine.configure(body)
    export = workspace_backup.export_workspace
    observed = []
    def capture(*args):
        observed.append(routine.mutation_lock._is_owned())
        return export(*args)
    monkeypatch.setattr(workspace_backup, 'export_workspace', capture)
    routine.run()
    assert observed == [True]


def test_bad_configuration_is_not_silently_replaced(setup):
    routine, body, _ = setup
    routine.state_path.write_bytes(b'{"format":"unknown"}')
    with pytest.raises(ValueError):
        routine.configure(body)
    routine.tick()
    assert routine.state_path.read_bytes() == b'{"format":"unknown"}'


@pytest.mark.skipif(os.name == 'nt', reason='symlink creation is permission-dependent on Windows')
@pytest.mark.parametrize('kind', ['destination', 'managed', 'archive', 'config', 'hardlink'])
def test_link_targets_are_never_read_or_rotated(setup, tmp_path, kind):
    routine, body, clock = setup
    if kind == 'destination':
        link = tmp_path/'alias'
        link.symlink_to(Path(body['destination']), target_is_directory=True)
        with pytest.raises(ValueError):
            routine.configure({**body, 'destination': str(link)})
        return
    routine.configure({**body, 'retention': 1})
    result = routine.run()
    folder = Path(result['directory'])
    source = folder/result['latest_name']
    protected = tmp_path/'protected-copy'
    protected.write_bytes(source.read_bytes())
    if kind == 'managed':
        moved = folder.with_name('renamed-private')
        folder.rename(moved)
        folder.symlink_to(moved, target_is_directory=True)
    elif kind == 'config':
        copied = tmp_path/'settings'
        copied.write_bytes(routine.state_path.read_bytes())
        routine.state_path.unlink()
        routine.state_path.symlink_to(copied)
    else:
        source.unlink()
        if kind == 'archive':
            source.symlink_to(protected)
        else:
            os.link(protected, source)
    if kind in ('archive', 'hardlink'):
        with pytest.raises(ValueError):
            routine.verify_latest()
        clock[0] += 10
        assert routine.run()['last_error'] == 'retention_pending'
    else:
        with pytest.raises(ValueError):
            routine.run()
    assert protected.exists()


def test_api_session_csrf_scope_and_routes(setup, monkeypatch):
    routine, body, _ = setup
    monkeypatch.setattr(api, 'PROJECTS', routine.paths[0])
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(routine.paths[1]))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(routine.paths[2]))
    client = auth_client(api.app)
    endpoint = '/api/workspace/backup-routine'
    assert client.get(endpoint).get_json()['enabled'] is False
    assert client.get(endpoint).headers['Cache-Control'] == 'no-store'
    assert client.put(endpoint, json=body, headers={'X-CSRF-Token': 'incorrect'}).status_code == 403
    assert client.put(endpoint, json=body, headers={'X-Report-Gen-Workspace': 'wrong'}).status_code == 409
    assert client.put(endpoint, json=body).status_code == 200
    assert client.post(endpoint+'/run', json={}).status_code == 200
    assert client.post(endpoint+'/verify', json={}).status_code == 200
    assert client.post(endpoint+'/disable', json={}).get_json()['enabled'] is False
    assert client.post(endpoint+'/run', json={'path': 'ignored-is-forbidden'}).status_code == 422


def test_real_scheduler_starts_and_stops_without_enabling(setup):
    routine, _, _ = setup
    routine.start()
    assert routine.status()['scheduler_running'] is True
    routine.stop()
    assert routine.status()['scheduler_running'] is False
    assert not routine.state_path.exists()


@pytest.mark.parametrize('occupied_name', [False, True])
def test_rotation_path_replaced_after_validation_is_preserved(setup, monkeypatch, occupied_name):
    routine, body, clock = setup
    routine.configure({**body, 'retention': 1})
    first = routine.run()
    source = Path(first['directory']) / first['latest_name']
    original_rename = module.os.rename
    replaced = []
    def replace_before_claim(old, new):
        if Path(old) == source:
            source.write_bytes(b'UNRELATED_REPLACEMENT_DO_NOT_DELETE')
            result = original_rename(old, new)
            if occupied_name:
                source.write_bytes(b'ANOTHER_NEW_FILE_DO_NOT_OVERWRITE')
            replaced.append(True)
            return result
        return original_rename(old, new)
    monkeypatch.setattr(module.os, 'rename', replace_before_claim)
    clock[0] += 5
    result = routine.run()
    assert replaced == [True]
    assert result['last_error'] == 'retention_pending'
    folder = Path(result['directory'])
    if occupied_name:
        assert source.read_bytes() == b'ANOTHER_NEW_FILE_DO_NOT_OVERWRITE'
        saved = list(folder.glob('.retention-*/*.zip'))
        assert len(saved) == 1 and saved[0].read_bytes() == b'UNRELATED_REPLACEMENT_DO_NOT_DELETE'
    else:
        assert source.read_bytes() == b'UNRELATED_REPLACEMENT_DO_NOT_DELETE'
        assert not list(folder.glob('.retention-*'))
    assert (folder/result['latest_name']).is_file()
