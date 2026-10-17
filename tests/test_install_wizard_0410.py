"""Real workspace snapshots/recovery, process guards and native wizard contracts."""
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from types import SimpleNamespace

import pytest
import project_history
from input_guard import load_yaml_file
import workspace_access
from scripts import install_manager as manager
from scripts import install_snapshot as snapshots
from scripts import install_wizard as gui


def application(root, version='0.41.0'):
    (root / 'webapp').mkdir(parents=True)
    for name in ('start.py', 'engine.py', 'webapp/app.py', 'requirements-audited.txt', 'workspace_access.py'):
        (root / name).write_text('# fixture: no downloads or execution of old application code\n')
    (root / 'version.py').write_text('__version__ = ' + repr(version) + '\n')
    (root / 'diagnostics.py').write_text('import json\nprint(json.dumps({"editor_ready": True, "pdf_ready": False, "checks": []}))\n')
    return root


@pytest.fixture
def plan(tmp_path, monkeypatch):
    new = application(tmp_path / 'new')
    old = application(tmp_path / 'old', '0.40.0')
    workspace = tmp_path / 'workspace'
    project_history.save(workspace / 'projects/bank', {'meta': {'report_title': 'Before update', 'lang': 'es'}, 'findings': []})
    project_history.checkpoint(workspace / 'projects/bank', 'Preserved checkpoint', force=True)
    monkeypatch.setattr(manager, 'python_for', lambda *args: Path(sys.executable))
    monkeypatch.setattr(manager, '_stopped', lambda port: None)
    monkeypatch.setattr(workspace_access, '_directory', lambda: tmp_path / 'locks')
    return manager.Plan(new, workspace, tmp_path / 'report-gen', tmp_path / 'backups', old, 'en')


def data_bytes(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}


def test_install_and_real_recovery_restore_previous_snapshot_without_touching_current(plan):
    before = data_bytes(plan.workspace)
    stages = []
    result = manager.install(plan, allow_network=True, progress=stages.append)
    assert stages == ['setup', 'diagnose', 'backup', 'activate', 'done']
    assert data_bytes(plan.workspace) == before
    assert Path(result['backup']).exists()
    assert sha256(Path(result['backup']).read_bytes()).hexdigest() == result['backup_sha256']
    assert result['projects'] == 1 and result['previous_version'] == '0.40.0'
    assert str(plan.application) in plan.launcher.read_text()
    project_history.save(plan.workspace / 'projects/bank', {'meta': {'report_title': 'After update', 'lang': 'es'}, 'findings': []})
    current = data_bytes(plan.workspace)
    restored = manager.recovery(result['receipt'])
    assert data_bytes(plan.workspace) == current
    destination = Path(restored['workspace'])
    assert destination != plan.workspace
    assert manager.separate(destination, plan.backups)
    assert load_yaml_file(destination / 'projects/bank/engagement.yaml')['meta']['report_title'] == 'Before update'
    assert project_history.history(destination / 'projects/bank')
    assert str(plan.previous) in plan.launcher.read_text()
    assert str(destination) in plan.launcher.read_text()
    assert restored['current_workspace_preserved'] == str(plan.workspace)


def test_no_network_authorization_never_runs_setup_or_changes_launcher(plan, monkeypatch):
    monkeypatch.setattr(manager, 'run', lambda *args, **kwargs: pytest.fail('No process should run'))
    before = data_bytes(plan.workspace)
    with pytest.raises(ValueError):
        manager.install(plan)
    assert data_bytes(plan.workspace) == before
    assert not plan.launcher.exists() and not plan.backups.exists()


@pytest.mark.parametrize('field,target', [('backups', 'workspace'), ('backups', 'application'),
                                        ('launcher', 'workspace'), ('previous', 'application')])
def test_reject_overlapping_paths_before_any_write(plan, field, target):
    values = vars(plan).copy(); values[field] = getattr(plan, target)
    with pytest.raises(ValueError):
        manager.Plan(**values).validate()
    assert not plan.launcher.exists()


def test_refuse_unowned_launcher_and_symlink_path(plan):
    plan.launcher.write_text('user file')
    with pytest.raises(ValueError):
        plan.validate()
    assert plan.launcher.read_text() == 'user file'
    plan.launcher.unlink()
    try:
        plan.launcher.symlink_to(plan.workspace / 'private-file')
    except OSError:
        pytest.skip('This Windows account cannot create symlinks')
    with pytest.raises(ValueError):
        plan.validate()


def test_failure_before_activation_preserves_old_launcher(plan, monkeypatch):
    old_content, marker = manager.launcher_content(plan.previous, plan.workspace, 'en')
    manager._publish_launcher(plan.launcher, old_content, marker)
    monkeypatch.setattr(manager, 'diagnose', lambda *args: {'editor_ready': False})
    with pytest.raises(ValueError):
        manager.install(plan, allow_network=True)
    assert plan.launcher.read_bytes() == old_content.encode()


def test_installer_with_shared_launcher_is_blocked_even_for_other_application_data(plan):
    with workspace_access.exclusive_paths(plan.launcher):
        with pytest.raises(ValueError):
            manager.install(plan, allow_network=True)
    assert not plan.launcher.exists()


@pytest.mark.parametrize('operation', ['install', 'recover'])
def test_changed_launcher_during_work_is_never_overwritten(plan, monkeypatch, operation):
    result = manager.install(plan, allow_network=True) if operation == 'recover' else None
    original = manager._helper
    changed, marker = manager.launcher_content(plan.previous, plan.workspace, 'pt')
    def mutate(*args, **kwargs):
        result = original(*args, **kwargs)
        manager._publish_launcher(plan.launcher, changed, marker)
        return result
    monkeypatch.setattr(manager, '_helper', mutate)
    before = data_bytes(plan.workspace)
    with pytest.raises(ValueError, match='changed|cambió'):
        if operation == 'install':
            manager.install(plan, allow_network=True)
        else:
            manager.recovery(result['receipt'])
    assert plan.launcher.read_bytes() == changed.encode()
    assert data_bytes(plan.workspace) == before


@pytest.mark.parametrize('damage', ['backup', 'launcher', 'previous_version'])
def test_recovery_refuses_modified_backup_launcher_or_previous_version(plan, damage):
    result = manager.install(plan, allow_network=True)
    if damage == 'backup':
        Path(result['backup']).write_bytes(b'corrupted')
    elif damage == 'launcher':
        with plan.launcher.open('a') as stream:
            stream.write('# manually edited\n')
    else:
        (plan.previous / 'version.py').write_text('__version__ = "0.39.0"\n')
    before = data_bytes(plan.workspace)
    launcher_before = plan.launcher.read_bytes()
    with pytest.raises(ValueError):
        manager.recovery(result['receipt'])
    assert data_bytes(plan.workspace) == before
    assert plan.launcher.read_bytes() == launcher_before


def test_os_lock_blocks_another_installation_and_releases_after_exit(plan):
    with workspace_access.exclusive_paths(plan.workspace):
        with pytest.raises(ValueError, match='en uso|in use'):
            manager.install(plan, allow_network=True)
        code = ('from workspace_access import exclusive_paths\n'
                'import sys\n'
                'with exclusive_paths(sys.argv[1], lock_directory=sys.argv[2]): pass\n')
        process = subprocess.run([sys.executable, '-c', code, str(plan.workspace),
                                  str(workspace_access._directory())], capture_output=True, text=True)
        assert process.returncode != 0
    with workspace_access.exclusive_paths(plan.workspace):
        pass
    assert not plan.launcher.exists()


def test_port_check_rejects_running_legacy_editor():
    # Actual listening socket: old releases did not participate in OS locks.
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0)); server.listen()
        with pytest.raises(ValueError):
            manager._stopped(server.getsockname()[1])


def test_windows_launcher_quotes_paths_and_does_not_install_or_expand_env():
    content, marker = manager.launcher_content(Path('C:/app & 50% !name'), Path('C:/private data'), 'pt', windows=True, port=8181)
    assert '50%% !name' in content and 'DisableDelayedExpansion' in content
    assert '"--port" "8181"' in content and '--setup' not in content and '--ready' not in content
    assert content.startswith(marker)


@pytest.mark.skipif(os.name != 'nt', reason='Actual cmd.exe execution requires Windows')
def test_windows_launcher_executes_literal_unicode_percent_ampersand_paths(tmp_path, monkeypatch):
    root = tmp_path / 'aplicación %PATH% ! & (literal)'; root.mkdir()
    workspace = tmp_path / 'datos ñ %TEMP% ! &'; workspace.mkdir()
    output = workspace / 'observed.json'
    (root / 'start.py').write_text('import json, pathlib, sys\npathlib.Path(sys.argv[2], "observed.json").write_text(json.dumps(sys.argv[1:]), encoding="utf-8")\n', encoding='utf-8')
    monkeypatch.setattr(manager, 'python_for', lambda *args: Path(sys.executable))
    content, marker = manager.launcher_content(root, workspace, 'pt', windows=True, port=8181)
    launcher = tmp_path / 'report-gen.cmd'
    manager._publish_launcher(launcher, content, marker)
    result = subprocess.run([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/c', str(launcher)], capture_output=True, timeout=30)
    assert result.returncode == 0, result.stderr.decode(errors='replace')
    assert json.loads(output.read_text(encoding='utf-8')) == ['--workspace', str(workspace), '--lang', 'pt', '--port', '8181']


def test_recovery_never_overwrites_existing_destination(plan):
    snapshot = snapshots.snapshot(plan.workspace, plan.backups)
    with pytest.raises(ValueError):
        snapshots.restore(snapshot['backup'], snapshot['backup_sha256'], plan.workspace)


def test_snapshot_hash_failure_never_creates_recovery_target(plan):
    snapshot = snapshots.snapshot(plan.workspace, plan.backups)
    target = plan.backups / 'new-data'
    with pytest.raises(ValueError):
        snapshots.restore(snapshot['backup'], '0' * 64, target)
    assert not target.exists()


def test_pending_workspace_recovery_is_not_implicitly_activated_by_installer(plan):
    (plan.workspace / '.workspace-restore.json').write_text('{}')
    before = data_bytes(plan.workspace)
    with pytest.raises(ValueError):
        manager.install(plan, allow_network=True)
    assert data_bytes(plan.workspace) == before
    assert not plan.launcher.exists() and not plan.backups.exists()


def test_update_preparation_uses_separate_application_directory(plan, monkeypatch):
    monkeypatch.setattr(manager, '_helper', lambda root, action, workspace, *args, **kwargs:
                        {'available': False, 'arguments': args})
    result = manager.prepare_update(plan)
    args = result['arguments']
    directory = args[args.index('--directory') + 1]
    assert directory == plan.application.parent / 'report-gen-updates'
    assert manager.separate(directory, plan.backups)


def test_update_detects_editor_started_during_download_before_any_backup_or_staging(plan, monkeypatch):
    import update_helper
    guard = workspace_access.exclusive_paths(plan.application, plan.workspace)
    release = {'assets': {'zip': {'browser_download_url': 'https://github.com/synthetic/package.zip'}}}
    monkeypatch.setattr(update_helper, 'inspect_release', lambda current: (release, {}))
    def downloaded(*args):
        guard.__enter__()  # Editor starts after the initial wizard check.
        return b'not-used-because-workspace-is-active'
    monkeypatch.setattr(update_helper, 'fetch', downloaded)
    monkeypatch.setattr(update_helper, 'prepare', lambda *args, **kwargs: pytest.fail('Active workspace must not be backed up or staged'))
    try:
        with pytest.raises(ValueError):
            snapshots.check_update(plan.application, plan.workspace, plan.backups, 'en')
    finally:
        guard.__exit__(None, None, None)
    assert not plan.backups.exists()


@pytest.mark.parametrize('lang', ['es', 'en', 'pt'])
def test_wizard_copy_and_help_cover_every_available_language(lang):
    assert all(len(values) == 3 and all(values) for values in gui.TEXT.values())
    result = subprocess.run([sys.executable, str(Path(gui.__file__)), '--help', '--lang', lang], capture_output=True)
    assert result.returncode == 0


@pytest.mark.parametrize('failure', [None, 'factory', 'start'])
def test_local_server_releases_guard_on_close_and_startup_failure(tmp_path, monkeypatch, failure):
    import app
    import waitress
    monkeypatch.setattr(workspace_access, '_directory', lambda: tmp_path / 'locks')
    monkeypatch.setattr(app, 'REPORT_ROOT', tmp_path / 'app')
    monkeypatch.setattr(app, 'WORKSPACE', SimpleNamespace(root=tmp_path / 'data'))
    calls = []
    fake = SimpleNamespace(close=lambda: calls.append('close'))
    monkeypatch.setattr(waitress, 'create_server', lambda *args, **kwargs: fake)
    def routine():
        if failure == 'factory':
            raise RuntimeError('factory failed')
        def start():
            if failure == 'start':
                raise RuntimeError('start failed')
        return SimpleNamespace(start=start, stop=lambda: calls.append('stop'))
    monkeypatch.setattr(app, 'backup_routine', routine)
    if failure:
        with pytest.raises(RuntimeError):
            app.create_local_server(0)
        assert calls.count('close') == 1
    else:
        server = app.create_local_server(0)
        with pytest.raises(ValueError):
            app.create_local_server(0)
        server.close(); server.close()
        assert calls.count('stop') == calls.count('close') == 1
    with workspace_access.exclusive_paths(tmp_path / 'app', tmp_path / 'data'):
        pass
