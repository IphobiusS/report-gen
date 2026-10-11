"""Explicit setup consent and fail-safe migration of real workspace backups."""
from hashlib import sha256
from pathlib import Path
import os
import stat
from types import SimpleNamespace

import pytest
import diagnostics
import launcher_upgrade as migration
import project_history as history
import finding_library
import start
from input_guard import load_yaml_file


def installation(path):
    (path / 'webapp/projects').mkdir(parents=True)
    (path / 'webapp/app.py').write_text('raise RuntimeError("old code must never execute")')
    (path / 'engine.py').write_text('raise RuntimeError("old code must never execute")')
    (path / 'webapp/projects/.gitkeep').touch()
    return path


def tree(path):
    return {p.relative_to(path).as_posix(): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode))
            for p in path.rglob('*') if p.is_file()}


@pytest.fixture
def workspaces(tmp_path):
    old = installation(tmp_path / 'old')
    new = installation(tmp_path / 'new')
    project = old / 'webapp/projects/customer'
    history.save(project, {'meta': {'report_title': 'Original', 'lang': 'es'}, 'findings': []})
    history.checkpoint(project, 'Previous state', force=True)
    history.save(project, {'meta': {'report_title': 'Current', 'lang': 'es'}, 'findings': []})
    finding_library.put(old / 'webapp/library/findings.json',
                        {'name': 'Reusable', 'content': {'title': 'Finding', 'mode': 'vuln', 'severity': 'info'}})
    return old, new, tmp_path / 'private-backups'


def test_real_upgrade_keeps_source_bytes_and_preserves_history_library_and_private_backup(workspaces):
    old, new, backups = workspaces
    before = tree(old)
    result = migration.upgrade(old, new, backup_directory=backups, lang='en')
    assert (result['projects'], result['findings'], result['designs']) == (1, 1, 0)
    assert result['source_preserved'] is True
    assert tree(old) == before
    project = new / 'webapp/projects/customer'
    assert load_yaml_file(project / 'engagement.yaml')['meta']['report_title'] == 'Current'
    assert history.history(project)
    sid = next(row['id'] for row in history.history(project) if row['label'] == 'Previous state')
    history.restore(project, sid)
    assert load_yaml_file(project / 'engagement.yaml')['meta']['report_title'] == 'Original'
    assert finding_library.load(new / 'webapp/library/findings.json') == finding_library.load(old / 'webapp/library/findings.json')
    archive = Path(result['backup'])
    assert archive.is_relative_to(backups)
    assert result['sha256'] == sha256(archive.read_bytes()).hexdigest()
    assert archive.with_name('result.json').exists()
    assert (new / 'webapp/projects/.gitkeep').read_bytes() == b''
    if os.name == 'posix':
        assert stat.S_IMODE(archive.stat().st_mode) == 0o600
        assert stat.S_IMODE(archive.parent.stat().st_mode) == 0o700


@pytest.mark.parametrize('occupied', ['project', 'personal_library', 'unknown_library', 'nonempty_marker'])
def test_upgrade_rejects_nonempty_destination_without_backup_or_source_writes(workspaces, occupied):
    old, new, backups = workspaces
    if occupied == 'project':
        (new / 'webapp/projects/keep.txt').write_text('keep me')
    elif occupied == 'personal_library':
        finding_library.put(new / 'webapp/library/findings.json',
                            {'name': 'Keep', 'content': {'title': 'Keep', 'mode': 'vuln', 'severity': 'info'}})
    elif occupied == 'unknown_library':
        (new / 'webapp/library').mkdir()
        (new / 'webapp/library/notes.txt').write_text('keep me')
    else:
        (new / 'webapp/projects/.gitkeep').write_text('unexpected user content')
    before_old, before_new = tree(old), tree(new)
    with pytest.raises(ValueError, match='empty'):
        migration.upgrade(old, new, backup_directory=backups, lang='en')
    assert tree(old) == before_old and tree(new) == before_new
    assert not backups.exists()


@pytest.mark.parametrize('case', ['same', 'nested', 'source_journal', 'target_journal', 'backup_inside'])
def test_invalid_paths_or_pending_recovery_never_change_old_workspace(workspaces, case):
    old, new, backups = workspaces
    if case == 'same':
        new = old
    if case == 'nested':
        new = installation(old / 'nested')
    if case == 'source_journal':
        (old / 'webapp/.workspace-restore.json').write_text('{}')
    if case == 'target_journal':
        (new / 'webapp/.workspace-restore.json').write_text('{}')
    if case == 'backup_inside':
        backups = old / 'backups'
    before = tree(old)
    with pytest.raises(ValueError):
        migration.upgrade(old, new, backup_directory=backups)
    assert tree(old) == before
    assert not backups.exists()


@pytest.mark.skipif(os.name != 'posix', reason='POSIX link permissions')
@pytest.mark.parametrize('location', ['source', 'target', 'ancestor', 'hardlink'])
def test_upgrade_rejects_linked_data(workspaces, tmp_path, location):
    old, new, backups = workspaces
    if location == 'source':
        (old / 'webapp/projects/linked').symlink_to(tmp_path)
    elif location == 'target':
        (new / 'webapp/projects/.gitkeep').unlink()
        (new / 'webapp/projects/.gitkeep').symlink_to(old / 'webapp/projects/.gitkeep')
    elif location == 'ancestor':
        alias = tmp_path / 'alias'
        alias.symlink_to(old, target_is_directory=True)
        old = alias
    else:
        os.link(old / 'webapp/projects/customer/engagement.yaml', tmp_path / 'hardlink.yaml')
    with pytest.raises(ValueError):
        migration.upgrade(old, new, backup_directory=backups)
    assert not backups.exists()


def test_damaged_archive_is_fully_validated_before_destination_or_backup(workspaces, monkeypatch):
    old, new, backups = workspaces
    before_old, before_new = tree(old), tree(new)
    monkeypatch.setattr(migration.backup, 'export_workspace', lambda *args: b'not a zip')
    with pytest.raises(ValueError):
        migration.upgrade(old, new, backup_directory=backups)
    assert tree(old) == before_old and tree(new) == before_new
    assert not backups.exists()


def test_source_change_during_validation_stops_before_restoration(workspaces, monkeypatch):
    old, new, backups = workspaces
    before = tree(new)
    restore = migration.backup.restore_workspace
    def changing_restore(*args):
        result = restore(*args)
        (old / 'webapp/projects/customer/extra.txt').write_text('concurrent edit')
        return result
    monkeypatch.setattr(migration.backup, 'restore_workspace', changing_restore)
    with pytest.raises(ValueError, match='source changed'):
        migration.upgrade(old, new, backup_directory=backups, lang='en')
    assert tree(new) == before and not backups.exists()


@pytest.mark.parametrize('backup_name', ['plain', '{customer}'])
def test_activation_failure_retains_backup_and_source_for_recovery(workspaces, monkeypatch, backup_name):
    old, new, backups = workspaces
    backups = backups / backup_name
    before = tree(old)
    restore = migration.backup.restore_workspace
    def fail_target(blob, projects, findings, designs):
        if projects == new / 'webapp/projects':
            raise OSError('disk unavailable')
        return restore(blob, projects, findings, designs)
    monkeypatch.setattr(migration.backup, 'restore_workspace', fail_target)
    with pytest.raises(ValueError, match='Keep both installations and the backup') as captured:
        migration.upgrade(old, new, backup_directory=backups, lang='en')
    archive, = backups.glob('upgrade-*/workspace.zip')
    assert str(archive) in str(captured.value)
    assert tree(old) == before
    assert (new / 'webapp/projects/.gitkeep').exists()
    assert not (new / 'webapp/projects/customer').exists()


@pytest.mark.parametrize('flag', [[], ['--diagnose'], ['--upgrade-from', '/previous']])
def test_plain_launch_diagnosis_and_upgrade_never_install_without_consent(tmp_path, monkeypatch, flag):
    monkeypatch.setattr(start, 'ROOT', tmp_path)
    monkeypatch.setattr(start, '_dependencies', lambda python: False)
    monkeypatch.setattr(start, '_install', lambda *args: pytest.fail('Unexpected network/setup'))
    assert start.main(flag) == 1
    assert not (tmp_path / '.venv').exists()


@pytest.mark.parametrize('flag', [[], ['--setup'], ['--ready'], ['--diagnose']])
def test_launcher_rejects_python_310_before_setup_or_child_process(monkeypatch, capsys, flag):
    monkeypatch.setattr(start.sys, 'version_info', (3, 10, 19))
    monkeypatch.setattr(start, '_install', lambda *args: pytest.fail('Unsupported Python must not install'))
    monkeypatch.setattr(start, '_dependencies', lambda *args: pytest.fail('Unsupported Python must not launch'))
    with pytest.raises(SystemExit) as caught:
        start.main(flag)
    assert caught.value.code == 2
    assert 'Python 3.11+' in capsys.readouterr().err


def test_ready_installs_diagnoses_and_launches_selected_venv(tmp_path, monkeypatch):
    monkeypatch.setattr(start, 'ROOT', tmp_path)
    events = []
    monkeypatch.setattr(start, '_install', lambda python, lang: events.append(('install', python)))
    monkeypatch.setattr(start, '_dependencies', lambda python: True)
    monkeypatch.setattr(start, '_readiness', lambda python, lang: events.append(('diagnose', python)) or True)
    monkeypatch.setattr(start, '_run_server', lambda python, port: events.append(('start', python)) or 0)
    assert start.main(['--ready']) == 0
    local = tmp_path / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    assert events == [('install', local), ('diagnose', local), ('start', local)]


def test_ready_reuses_complete_venv_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(start, 'ROOT', tmp_path)
    local = tmp_path / '.venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    local.parent.mkdir(parents=True)
    local.touch()
    monkeypatch.setattr(start, '_dependencies', lambda python: True)
    monkeypatch.setattr(start, '_install', lambda *args: pytest.fail('Unnecessary dependency installation'))
    monkeypatch.setattr(start, '_readiness', lambda *args: True)
    monkeypatch.setattr(start, '_run_server', lambda *args: 0)
    assert start.main(['--ready']) == 0


def test_required_diagnostic_failure_does_not_launch(monkeypatch):
    monkeypatch.setattr(start, '_dependencies', lambda python: True)
    monkeypatch.setattr(start, '_install', lambda *args: None)
    monkeypatch.setattr(start, '_readiness', lambda *args: False)
    monkeypatch.setattr(start, '_run_server', lambda *args: pytest.fail('Broken editor must not launch'))
    assert start.main(['--ready']) == 1


def test_upgrade_without_ready_reports_and_stops(monkeypatch):
    monkeypatch.setattr(start, '_dependencies', lambda python: True)
    events = []
    monkeypatch.setattr(start, '_upgrade', lambda python, source, lang: events.append(source))
    monkeypatch.setattr(start, '_readiness', lambda *args: True)
    monkeypatch.setattr(start, '_run_server', lambda *args: pytest.fail('Standalone migration must not launch'))
    assert start.main(['--upgrade-from', '/old']) == 0
    assert events == ['/old']


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_missing_optional_pdf_engines_do_not_block_editor(monkeypatch, lang):
    def absent(root):
        raise ImportError('not installed')
    monkeypatch.setattr(diagnostics, 'weasy', absent)
    monkeypatch.setattr(diagnostics, 'chromium', absent)
    monkeypatch.setattr(diagnostics, 'word', lambda root: None)
    result = diagnostics.run(lang)
    assert result['editor_ready'] is True and result['pdf_ready'] is False
    assert [row['required'] for row in result['checks']] == [False, False, True]
    assert all(('optional' if lang == 'en' else 'opcional') in row['detail'].lower() for row in result['checks'][:2])


def test_setup_failures_are_actionable_without_traceback(monkeypatch, capsys):
    def failed(*args):
        raise start.subprocess.CalledProcessError(1, 'pip')
    monkeypatch.setattr(start, '_dependencies', lambda python: False)
    monkeypatch.setattr(start, '_run_server', lambda *args: pytest.fail('A failed setup must not launch the server'))
    monkeypatch.setattr(start, '_install', failed)
    assert start.main(['--ready', '--lang', 'en']) == 1
    error = capsys.readouterr().err
    assert 'python start.py --setup' in error and 'Traceback' not in error


def test_readiness_prints_optional_status_but_accepts_editor(monkeypatch, capsys):
    report = {'checks': [{'ready': False, 'label': 'PDF', 'detail': 'Optional unavailable'}],
              'editor_ready': True, 'note': 'Word is available'}
    import json
    monkeypatch.setattr(start.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(report)))
    assert start._readiness(Path('python'), 'en')
    assert 'Optional unavailable' in capsys.readouterr().out


@pytest.mark.parametrize('failure', range(1, 7))
def test_interrupted_activation_preserves_existing_recovery_contract(workspaces, monkeypatch, failure):
    old, new, backups = workspaces
    before = tree(old)
    # Include empty destination libraries so all six activation renames occur.
    findings, designs = migration._locations(new)[1:]
    findings.parent.mkdir(parents=True)
    import json
    import design_library
    findings.write_text(json.dumps(finding_library.load(findings)))
    designs.write_text(json.dumps(design_library.load_personal(designs)))
    original_move = migration.backup._move
    calls = 0
    def interrupt_source_only(source, destination):
        nonlocal calls
        original_move(source, destination)
        # Validation also restores, but only actual destination moves fail.
        if new in source.parents or new in destination.parents:
            calls += 1
            if calls == failure:
                raise OSError('simulated interrupted activation')
    monkeypatch.setattr(migration.backup, '_move', interrupt_source_only)
    with pytest.raises(ValueError, match='Keep both installations and the backup'):
        migration.upgrade(old, new, backup_directory=backups, lang='en')
    assert tree(old) == before
    archive, = backups.glob('upgrade-*/workspace.zip')
    monkeypatch.setattr(migration.backup, '_move', original_move)
    paths = migration._locations(new)
    migration.backup.recover(*paths)
    migration.backup.recover(*paths)
    assert not list(paths[0].iterdir())
    result = migration.backup.restore_workspace(archive.read_bytes(), *paths)
    assert result['projects'] == 1
    assert load_yaml_file(paths[0] / 'customer/engagement.yaml')['meta']['report_title'] == 'Current'


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_receipt_write_failure_reports_committed_migration_with_backup_and_warning(workspaces, monkeypatch, lang):
    old, new, backups = workspaces
    before = tree(old)
    write = migration._write_private
    def fail_receipt(path, blob):
        if path.name == 'result.json':
            raise OSError('receipt disk unavailable')
        return write(path, blob)
    monkeypatch.setattr(migration, '_write_private', fail_receipt)
    result = migration.upgrade(old, new, backup_directory=backups, lang=lang)
    assert result['source_preserved'] is True and tree(old) == before
    assert result['projects'] == 1 and result['findings'] == 1
    assert load_yaml_file(new / 'webapp/projects/customer/engagement.yaml')['meta']['report_title'] == 'Current'
    archive = Path(result['backup'])
    assert result['sha256'] == sha256(archive.read_bytes()).hexdigest()
    assert not archive.with_name('result.json').exists()
    assert len(result['warnings']) == 1
    assert ('Migration completed' if lang == 'en' else 'Migración completada') in result['warnings'][0]
    assert 'SHA-256' in result['warnings'][0]


def test_marker_write_failure_does_not_hide_committed_migration(workspaces, monkeypatch):
    old, new, backups = workspaces
    before = tree(old)
    open_path = Path.open
    marker = new / 'webapp/projects/.gitkeep'
    def fail_marker(path, mode='r', *args, **kwargs):
        if path == marker and mode == 'xb':
            raise OSError('marker write unavailable')
        return open_path(path, mode, *args, **kwargs)
    monkeypatch.setattr(Path, 'open', fail_marker)
    result = migration.upgrade(old, new, backup_directory=backups, lang='en')
    assert tree(old) == before
    assert result['projects'] == 1
    assert load_yaml_file(new / 'webapp/projects/customer/engagement.yaml')['meta']['report_title'] == 'Current'
    archive = Path(result['backup'])
    assert result['sha256'] == sha256(archive.read_bytes()).hexdigest()
    assert archive.with_name('result.json').exists()
    assert not marker.exists()
    assert any('Migration completed' in row and '.gitkeep' in row for row in result['warnings'])


@pytest.mark.parametrize('side', ['source', 'destination'])
def test_windows_reparse_attributes_rejected_even_when_not_a_symlink(workspaces, monkeypatch, side):
    old, new, backups = workspaces
    junction = (old if side == 'source' else new) / 'webapp/projects'
    lstat = Path.lstat
    def reparse_stat(path, *args, **kwargs):
        details = lstat(path, *args, **kwargs)
        if path == junction:
            return SimpleNamespace(st_mode=details.st_mode, st_file_attributes=0x400)
        return details
    monkeypatch.setattr(Path, 'lstat', reparse_stat)
    with pytest.raises(ValueError, match='reparse points'):
        migration.upgrade(old, new, backup_directory=backups, lang='en')
    assert not backups.exists()


def test_private_stage_cleanup_failure_is_success_with_local_cleanup_warning(workspaces, monkeypatch):
    old, new, backups = workspaces
    before = tree(old)
    cleanup = migration.tempfile.TemporaryDirectory.cleanup
    leftovers = []
    def fail_upgrade_cleanup(stage):
        if Path(stage.name).name.startswith('report-gen-upgrade-'):
            leftovers.append(stage)
            raise OSError('temporary cleanup unavailable')
        return cleanup(stage)
    monkeypatch.setattr(migration.tempfile.TemporaryDirectory, 'cleanup', fail_upgrade_cleanup)
    try:
        result = migration.upgrade(old, new, backup_directory=backups, lang='en')
        assert result['projects'] == 1 and tree(old) == before
        assert load_yaml_file(new / 'webapp/projects/customer/engagement.yaml')['meta']['report_title'] == 'Current'
        archive = Path(result['backup'])
        assert result['sha256'] == sha256(archive.read_bytes()).hexdigest()
        assert archive.with_name('result.json').exists()
        stage, = leftovers
        assert Path(stage.name).exists()
        assert any('Migration completed' in row and stage.name in row for row in result['warnings'])
    finally:
        for stage in leftovers:
            cleanup(stage)
