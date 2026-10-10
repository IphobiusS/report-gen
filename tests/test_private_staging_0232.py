"""Private preparations must not leave recovery journals after publication."""
from io import BytesIO
from pathlib import Path
import zipfile

import pytest
from PIL import Image

import engine
import project_history as history
import workspace_backup as backup


def files(directory):
    return {path.relative_to(directory).as_posix(): path.read_bytes()
            for path in directory.rglob('*') if path.is_file()}


@pytest.fixture
def portable(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'img').mkdir()
    Image.new('RGB', (8, 8), 'blue').save(source / 'img' / 'proof.png')
    data = {'meta': {'report_title': 'Previous state', 'lang': 'es'},
            'findings': [{'id': 'F1', 'title': 'Proof', 'severity': 'info',
                          'cvss': 0, 'description_md': '![Proof](img/proof.png)',
                          'walkthrough': []}]}
    history.save(source, data)
    data['meta']['report_title'] = 'Current state'
    history.save(source, data)
    projects = tmp_path / 'projects'
    projects.mkdir()
    return source, projects, history.export_bundle(source)


def fail_cleanup_once(monkeypatch, failure):
    """A successful commit may legitimately retain a cleanup journal."""
    if failure == 'previous':
        original = history.shutil.rmtree
        called = False

        def interrupted(path, *args, **kwargs):
            nonlocal called
            if Path(path).name.startswith('.previous-') and not called:
                called = True
                raise OSError('transient previous cleanup failure')
            return original(path, *args, **kwargs)

        monkeypatch.setattr(history.shutil, 'rmtree', interrupted)
    else:
        original = Path.unlink
        called = False

        def interrupted(path, *args, **kwargs):
            nonlocal called
            if path.name.startswith('.commit-') and not called:
                called = True
                raise OSError('transient journal cleanup failure')
            return original(path, *args, **kwargs)

        monkeypatch.setattr(Path, 'unlink', interrupted)


@pytest.mark.parametrize('failure', ['previous', 'journal'])
def test_import_recovery_never_recreates_its_private_preparation(portable, monkeypatch, failure):
    source, projects, blob = portable
    before = files(source)
    expected = engine.load_engagement(source / 'engagement.yaml')
    target = projects / 'published'
    fail_cleanup_once(monkeypatch, failure)
    history.import_bundle(blob, target)
    history.recover_transactions(projects)
    history.recover_transactions(projects)
    assert sorted(path.name for path in projects.iterdir()) == ['published']
    assert engine.load_engagement(target / 'engagement.yaml') == expected
    for name, content in before.items():
        if name.startswith(('history/', 'img/')):
            assert (target / name).read_bytes() == content
    for record in history.history(target):
        assert dict(history.snapshot_blobs(target, record))
    exported = backup.export_workspace(projects, projects.parent / 'findings.json',
                                       projects.parent / 'designs.json')
    with zipfile.ZipFile(BytesIO(exported)) as archive:
        assert 'projects/published.zip' in archive.namelist()
    assert files(source) == before


@pytest.mark.parametrize('failure', ['yaml', 'checkpoint', 'publication'])
def test_failed_import_never_publishes_or_reserves_the_name(portable, monkeypatch, failure):
    source, projects, blob = portable
    before = files(source)
    target = projects / 'published'
    outer = (projects.parent / 'unrelated-private-state').resolve()
    token = history._STAGING.set((*history._STAGING.get(), outer))
    expected_context = history._STAGING.get()
    try:
        with monkeypatch.context() as context:
            if failure == 'yaml':
                import wizard
                original = wizard.dump_yaml

                def interrupted(data, path):
                    original(data, path)
                    raise OSError('failed after writing private YAML')

                context.setattr(wizard, 'dump_yaml', interrupted)
            elif failure == 'checkpoint':
                original = history.checkpoint

                def interrupted(*args, **kwargs):
                    original(*args, **kwargs)
                    raise OSError('failed after writing private history')

                context.setattr(history, 'checkpoint', interrupted)
            else:
                original = Path.rename

                def interrupted(path, destination):
                    if path.name.startswith('.import-'):
                        raise OSError('failed before publication')
                    return original(path, destination)

                context.setattr(Path, 'rename', interrupted)
            with pytest.raises(OSError):
                history.import_bundle(blob, target)
        assert history._STAGING.get() == expected_context
        assert not list(projects.iterdir())
        assert files(source) == before
        history.import_bundle(blob, target)
        assert history._STAGING.get() == expected_context
        assert engine.load_engagement(target / 'engagement.yaml')['meta']['report_title'] == 'Current state'
    finally:
        history._STAGING.reset(token)


@pytest.mark.parametrize('failure', ['previous', 'journal'])
def test_restore_recovery_never_recreates_its_private_preparation(portable, monkeypatch, failure):
    _, projects, blob = portable
    target = projects / 'published'
    history.import_bundle(blob, target)
    before = files(target)
    sid = history.history(target)[-1]['id']
    expected = history.snapshot_data(target, sid)
    current = engine.load_engagement(target / 'engagement.yaml')
    assert current['meta']['report_title'] != expected['meta']['report_title']
    fail_cleanup_once(monkeypatch, failure)
    history.restore(target, sid)
    history.recover_transactions(projects)
    history.recover_transactions(projects)
    assert sorted(path.name for path in projects.iterdir()) == ['published']
    restored = engine.load_engagement(target / 'engagement.yaml')
    assert restored == expected
    assert restored['findings'][0]['uid'] == current['findings'][0]['uid']
    # Current and requested states remain recoverable by snapshot; dump_yaml's
    # legacy .bak follows its last write rather than the pre-restore document.
    assert any(history.snapshot_data(target, record['id']) == current
               for record in history.history(target))
    assert (target / 'history' / 'objects' / history.digest(before['engagement.yaml'])).read_bytes() == before['engagement.yaml']
    for name, content in before.items():
        if name.startswith('history/'):
            assert (target / name).read_bytes() == content
    for record in history.history(target):
        assert dict(history.snapshot_blobs(target, record))
    assert backup.export_workspace(projects, projects.parent / 'findings.json',
                                   projects.parent / 'designs.json')


@pytest.mark.parametrize('failure', ['yaml', 'checkpoint', 'publication'])
def test_failed_restore_preserves_public_data_and_restores_staging_context(portable, monkeypatch, failure):
    _, projects, blob = portable
    target = projects / 'published'
    history.import_bundle(blob, target)
    before = files(target)
    sid = history.history(target)[-1]['id']
    outer = (projects.parent / 'unrelated-private-state').resolve()
    token = history._STAGING.set((*history._STAGING.get(), outer))
    expected_context = history._STAGING.get()
    try:
        with monkeypatch.context() as context:
            if failure == 'yaml':
                import wizard
                original = wizard.dump_yaml

                def interrupted(data, path):
                    original(data, path)
                    raise OSError('failed after writing private YAML')

                context.setattr(wizard, 'dump_yaml', interrupted)
            elif failure == 'checkpoint':
                original = history.checkpoint

                def interrupted(directory, *args, **kwargs):
                    result = original(directory, *args, **kwargs)
                    if Path(directory).name.startswith('.restore-'):
                        raise OSError('failed after writing private history')
                    return result

                context.setattr(history, 'checkpoint', interrupted)
            else:
                original = Path.rename

                def interrupted(path, destination):
                    if path.name.startswith('.restore-'):
                        raise OSError('failed before restoration activation')
                    return original(path, destination)

                context.setattr(Path, 'rename', interrupted)
            with pytest.raises(OSError):
                history.restore(target, sid)
        assert history._STAGING.get() == expected_context
        history.recover_transactions(projects)
        assert sorted(path.name for path in projects.iterdir()) == ['published']
        assert files(target) == before
        # A later ordinary edit still uses activation and must roll back if it
        # cannot publish. An import/restore token must never leak into that edit.
        value = engine.load_engagement(target / 'engagement.yaml')
        value['meta']['report_title'] = 'Must not commit'
        with monkeypatch.context() as context:
            original = Path.rename

            def interrupted(path, destination):
                if path.name.startswith('.transaction-'):
                    raise OSError('failed ordinary edit activation')
                return original(path, destination)

            context.setattr(Path, 'rename', interrupted)
            with pytest.raises(OSError):
                history.save(target, value)
        assert files(target) == before
        assert history._STAGING.get() == expected_context
    finally:
        history._STAGING.reset(token)

