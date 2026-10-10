"""A pristine source package can be backed up/restored without ignoring user data."""
from io import BytesIO
import zipfile

import pytest

import project_history
import workspace_backup


def paths(root):
    return root / 'projects', root / 'library/findings.json', root / 'library/designs.json'


@pytest.mark.parametrize('project_count', [0, 1])
def test_empty_packaged_marker_allows_backup_and_fresh_restore(tmp_path, project_count):
    source = paths(tmp_path / 'source')
    source[0].mkdir(parents=True)
    (source[0] / '.gitkeep').write_bytes(b'')
    if project_count:
        project_history.save(source[0] / 'example', {'meta': {'report_title': 'Kept'}, 'findings': []})
    blob = workspace_backup.export_workspace(*source)
    assert (source[0] / '.gitkeep').read_bytes() == b''
    with zipfile.ZipFile(BytesIO(blob)) as package:
        assert '.gitkeep' not in package.namelist()
        assert sum(name.startswith('projects/') for name in package.namelist()) == project_count
    target = paths(tmp_path / 'target')
    target[0].mkdir(parents=True)
    (target[0] / '.gitkeep').write_bytes(b'')
    result = workspace_backup.restore_workspace(blob, *target)
    assert result['projects'] == project_count
    assert (target[0] / 'example/engagement.yaml').exists() == bool(project_count)


@pytest.mark.parametrize('kind', ['nonempty', 'symlink', 'directory', 'other_empty_file'])
def test_marker_exemption_never_ignores_other_content(tmp_path, kind):
    source = paths(tmp_path / 'source')
    source[0].mkdir(parents=True)
    marker = source[0] / '.gitkeep'
    if kind == 'nonempty':
        marker.write_bytes(b'USER_CONTENT_030')
    elif kind == 'symlink':
        original = tmp_path / 'original'
        original.write_bytes(b'')
        try:
            marker.symlink_to(original)
        except OSError:
            pytest.skip('Symlinks unavailable on this platform')
    elif kind == 'directory':
        marker.mkdir()
    else:
        (source[0] / 'user-notes.txt').write_bytes(b'')
    with pytest.raises(ValueError):
        workspace_backup.export_workspace(*source)
    empty = paths(tmp_path / 'empty')
    blob = workspace_backup.export_workspace(*empty)
    with pytest.raises(ValueError):
        workspace_backup.restore_workspace(blob, *source)
    if kind == 'nonempty':
        assert marker.read_bytes() == b'USER_CONTENT_030'
    elif kind == 'symlink':
        assert marker.is_symlink() and original.read_bytes() == b''
