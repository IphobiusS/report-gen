"""Adversarial storage boundaries keep filesystem aliases outside mutations."""
from io import BytesIO
import os
from pathlib import Path
import subprocess
import sys

import pytest
from PIL import Image
import app as api
import project_history
import workspace_backup
from _support import auth_client


@pytest.fixture
def client(tmp_path, monkeypatch):
    root = tmp_path / 'workspace'
    projects = root / 'projects'
    projects.mkdir(parents=True)
    monkeypatch.setattr(api, 'PROJECTS', projects)
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', root / 'library/findings.json')
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', root / 'library/designs.json')
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    browser = auth_client(api.app)
    assert browser.post('/api/projects', json={'slug': 'original'}).status_code == 200
    return browser, projects


@pytest.mark.skipif(os.name == 'nt', reason='symlink creation is permission-dependent on Windows')
@pytest.mark.parametrize('action', ['read', 'save', 'delete'])
def test_project_alias_cannot_read_mutate_or_delete_another_project(client, action):
    browser, projects = client
    source = projects / 'original'
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()}
    current = browser.get('/api/projects/original')
    (projects / 'alias').symlink_to(source, target_is_directory=True)
    if action == 'read':
        response = browser.get('/api/projects/alias')
    elif action == 'save':
        data = current.get_json()
        data['meta']['report_title'] = 'Must not change through alias'
        response = browser.put('/api/projects/alias', json=data, headers={'If-Match': current.headers['ETag']})
    else:
        response = browser.delete('/api/projects/alias', headers={'If-Match': current.headers['ETag']})
    assert response.status_code in (404, 422)
    assert source.is_dir()
    assert {p.relative_to(source): p.read_bytes() for p in source.rglob('*') if p.is_file()} == before
    assert (projects / 'alias').is_symlink()


@pytest.mark.skipif(os.name == 'nt', reason='symlink creation is permission-dependent on Windows')
def test_image_upload_never_follows_a_linked_image_directory(client, tmp_path):
    browser, projects = client
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = outside / 'keep.txt'
    sentinel.write_bytes(b'PRIVATE_SENTINEL')
    images = projects / 'original/img'
    images.rmdir()
    images.symlink_to(outside, target_is_directory=True)
    image = BytesIO()
    Image.new('RGB', (8, 8), 'red').save(image, format='PNG')
    image.seek(0)
    response = browser.post('/api/projects/original/image', data={'file': (image, 'picture.png')})
    assert response.status_code in (404, 422)
    assert list(outside.iterdir()) == [sentinel]
    assert sentinel.read_bytes() == b'PRIVATE_SENTINEL'
    assert images.is_symlink()


@pytest.mark.parametrize('kind', ['single', 'aggregate', 'count'])
def test_project_resource_budget_is_checked_before_reading_excess_bytes(tmp_path, monkeypatch, kind):
    root = tmp_path / 'project'
    (root / 'img').mkdir(parents=True)
    document = b'meta: {report_title: audit, lang: es}\nfindings: []\n'
    (root / 'engagement.yaml').write_bytes(document)
    first = root / 'img/a.png'
    first.write_bytes(b'x' * 2048)
    excess = first
    if kind != 'single':
        excess = root / 'img/b.png'
        excess.write_bytes(b'y' * 2048)
    monkeypatch.setattr(project_history, 'MAX_EXPANDED', len(document) + (1024 if kind == 'single' else 3072))
    if kind == 'count':
        monkeypatch.setattr(project_history, 'MAX_EXPANDED', 99999)
        monkeypatch.setattr(project_history, 'MAX_FILES', 2)
    original_open = Path.open

    class NoContentRead:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def fileno(self):
            return self.stream.fileno()

        def read(self, *_args, **_kwargs):
            pytest.fail('Oversized input must be rejected before reading its content')

    def guarded_open(path, *args, **kwargs):
        stream = original_open(path, *args, **kwargs)
        return NoContentRead(stream) if path == excess else stream

    monkeypatch.setattr(Path, 'open', guarded_open)
    with pytest.raises(ValueError, match='límite'):
        project_history.export_bundle(root)


def test_changed_resource_is_rejected_instead_of_exporting_truncated_bytes(tmp_path, monkeypatch):
    resource = tmp_path / 'image.png'
    resource.write_bytes(b'previous')
    original_stat = project_history.os.fstat

    def changed_stat(descriptor):
        result = original_stat(descriptor)
        # Simulate growth after the descriptor size is observed.
        with resource.open('ab') as writer:
            writer.write(b'changed')
        return result

    monkeypatch.setattr(project_history.os, 'fstat', changed_stat)
    with pytest.raises(ValueError, match='cambió'):
        project_history._read_project_file(resource, 100)


def project_fixture(root):
    project = root / 'projects/source'
    data = {'meta': {'report_title': 'Prior revision', 'lang': 'es'}, 'findings': []}
    project_history.save(project, data)
    previous = project_history.history(project)[0]['id']
    data['meta']['report_title'] = 'Current revision'
    project_history.save(project, data)
    archive = root / 'copy.zip'
    archive.write_bytes(project_history.export_bundle(project))
    return project, data, previous, archive


def tree_bytes(root):
    return {p.relative_to(root): p.read_bytes() for p in root.rglob('*') if p.is_file()}


@pytest.mark.parametrize('operation', ['transaction', 'restore', 'import'])
def test_killed_preparation_recovers_without_blocking_workspace_backups(tmp_path, operation):
    project, _, previous, archive = project_fixture(tmp_path)
    before = tree_bytes(project)
    script = r'''
import os, sys
from pathlib import Path
import project_history as history
from input_guard import load_yaml_file
operation, source, previous, archive = sys.argv[1:]
source = Path(source)
if operation == 'import':
    write = history.atomic_write
    def killed_write(path, value, *args, **kwargs):
        write(path, value, *args, **kwargs)
        if Path(path).name == 'engagement.yaml':
            os._exit(86)
    history.atomic_write = killed_write
    history.import_bundle(Path(archive).read_bytes(), source.parent / 'copy')
else:
    copy = history.shutil.copytree
    def killed_copy(*args, **kwargs):
        result = copy(*args, **kwargs)
        os._exit(86)
        return result
    history.shutil.copytree = killed_copy
    if operation == 'restore':
        history.restore(source, previous)
    else:
        data = load_yaml_file(source / 'engagement.yaml')
        data['meta']['report_title'] = 'Must not commit'
        history.save(source, data)
'''
    result = subprocess.run([sys.executable, '-c', script, operation, str(project), previous, str(archive)],
                            cwd=Path(__file__).resolve().parents[1], timeout=30, capture_output=True, text=True)
    assert result.returncode == 86, result.stderr
    assert list(project.parent.glob('.commit-*.json'))
    project_history.recover_transactions(project.parent)
    project_history.recover_transactions(project.parent)
    assert tree_bytes(project) == before
    assert not (project.parent / 'copy').exists()
    assert [p.name for p in project.parent.iterdir()] == ['source']
    bundle = workspace_backup.export_workspace(project.parent, tmp_path / 'library/findings.json', tmp_path / 'library/designs.json')
    destination = tmp_path / 'verified'
    assert workspace_backup.restore_workspace(bundle, destination / 'projects', destination / 'library/findings.json',
                                             destination / 'library/designs.json')['projects'] == 1
    restored = destination / 'projects/source'
    assert dict(project_history.project_files(restored)) == dict(project_history.project_files(project))
    assert project_history.history(restored) == project_history.history(project)
    for record in project_history.history(project):
        assert dict(project_history.snapshot_blobs(restored, record)) == dict(project_history.snapshot_blobs(project, record))


@pytest.mark.parametrize('operation', ['transaction', 'restore', 'import'])
def test_failed_preparation_journal_writes_no_private_payload(tmp_path, monkeypatch, operation):
    project, data, previous, archive = project_fixture(tmp_path)
    before = tree_bytes(project)
    real_write = project_history.atomic_write

    def reject_journal(path, *args, **kwargs):
        if Path(path).name.startswith('.commit-'):
            raise OSError('Injected full disk before staging data')
        return real_write(path, *args, **kwargs)

    def forbidden_copy(*_args, **_kwargs):
        pytest.fail('No private content may be copied before its recovery record is durable')

    monkeypatch.setattr(project_history, 'atomic_write', reject_journal)
    monkeypatch.setattr(project_history.shutil, 'copytree', forbidden_copy)
    with pytest.raises(OSError, match='Injected'):
        if operation == 'import':
            project_history.import_bundle(archive.read_bytes(), project.parent / 'copy')
        elif operation == 'restore':
            project_history.restore(project, previous)
        else:
            data['meta']['report_title'] = 'Must not commit'
            project_history.save(project, data)
    assert tree_bytes(project) == before
    assert [p.name for p in project.parent.iterdir()] == ['source']


def test_recovery_does_not_guess_ownership_of_unregistered_directories(tmp_path):
    private = tmp_path / '.transaction-user-owned'
    private.mkdir()
    (private / 'keep.txt').write_bytes(b'USER_AUTHORED')
    project_history.recover_transactions(tmp_path)
    assert (private / 'keep.txt').read_bytes() == b'USER_AUTHORED'
