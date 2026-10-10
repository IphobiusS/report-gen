"""Portable legacy recovery, Unicode project names and completed restore cleanup."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import zipfile

from PIL import Image
import pytest
import app as api
import project_history as history
import workspace_backup as backup
from input_guard import load_yaml_file
from storage import revision
from wizard import dump_yaml
from _support import auth_client


def paths(root):
    return root/'projects', root/'library/findings.json', root/'library/designs.json'


def configure(monkeypatch, locations):
    monkeypatch.setattr(api, 'PROJECTS', locations[0])
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(locations[1]))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(locations[2]))
    return auth_client(api.app)


def tree(root):
    return {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mode)
            for p in root.rglob('*') if p.is_file()}


def legacy_project(root):
    root.mkdir(parents=True)
    (root/'diagrams').mkdir()
    Image.new('RGB', (9, 7), 'red').save(root/'diagrams/old proof.png')
    old = {'meta': {'report_title': 'PREVIOUS_UNIQUE', 'lang': 'es', 'theme': 'corporativo'},
           'report': {'sections': [{'key': 'custom', 'title': 'Anterior',
                                   'body': '![Anterior](diagrams/old%20proof.png)'}]},
           'findings': []}
    current = deepcopy(old)
    current['meta']['report_title'] = 'CURRENT_UNIQUE'
    current['report']['sections'][0]['body'] = 'Texto actual sin la imagen anterior.'
    dump_yaml(old, root/'engagement.yaml.bak')
    dump_yaml(current, root/'engagement.yaml')
    return (root/'engagement.yaml.bak').read_bytes(), (root/'diagrams/old proof.png').read_bytes()


@pytest.mark.parametrize('integral', [False, True])
def test_legacy_previous_yaml_and_its_own_images_survive_backup_without_source_writes(tmp_path, monkeypatch, integral):
    source = paths(tmp_path/'source')
    project = source[0]/'legacy'
    previous_yaml, previous_image = legacy_project(project)
    before = tree(source[0])
    blob = backup.export_workspace(*source) if integral else history.export_bundle(project)
    assert tree(source[0]) == before
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        nested = archive.read('projects/legacy.zip') if integral else blob
    with zipfile.ZipFile(BytesIO(nested)) as archive:
        assert 'engagement.yaml.bak' not in archive.namelist()
        assert archive.read('history/objects/' + history.digest(previous_yaml)) == previous_yaml
        assert archive.read('diagrams/old proof.png') == previous_image
    target = paths(tmp_path/'target')
    target[0].mkdir(parents=True)
    if integral:
        assert backup.restore_workspace(blob, *target)['projects'] == 1
    else:
        history.import_bundle(blob, target[0]/'legacy')
    imported = target[0]/'legacy'
    assert load_yaml_file(imported/'engagement.yaml')['meta']['report_title'] == 'CURRENT_UNIQUE'
    client = configure(monkeypatch, target)
    response = client.post('/api/projects/legacy/restore', json={},
                           headers={'If-Match': revision(imported/'engagement.yaml')})
    assert response.status_code == 200, response.get_json()
    assert load_yaml_file(imported/'engagement.yaml')['meta']['report_title'] == 'PREVIOUS_UNIQUE'
    assert (imported/'diagrams/old proof.png').read_bytes() == previous_image
    assert (imported/'history/objects'/history.digest(previous_yaml)).read_bytes() == previous_yaml


def test_previous_backup_not_lost_when_an_old_export_already_added_only_current_history(tmp_path):
    project = tmp_path/'legacy'
    previous_yaml, _ = legacy_project(project)
    history.checkpoint(project)
    before = tree(project)
    blob = history.export_bundle(project)
    assert tree(project) == before
    with zipfile.ZipFile(BytesIO(blob)) as archive:
        assert archive.read('history/objects/' + history.digest(previous_yaml)) == previous_yaml


def test_unicode_casefold_collision_is_rejected_before_backup_changes_source(tmp_path):
    locations = paths(tmp_path)
    locations[0].mkdir()
    for slug in ('straße', 'strasse'):
        history.save(locations[0]/slug, {'meta': {'report_title': slug}, 'findings': []})
    before = tree(locations[0])
    with pytest.raises(ValueError, match='Unicode'):
        backup.export_workspace(*locations)
    assert tree(locations[0]) == before


def test_new_project_rejects_unicode_casefold_collision_and_keeps_existing_project(tmp_path, monkeypatch):
    locations = paths(tmp_path)
    locations[0].mkdir()
    client = configure(monkeypatch, locations)
    assert client.post('/api/projects', json={'slug': 'straße'}).status_code == 200
    before = tree(locations[0])
    response = client.post('/api/projects', json={'slug': 'strasse'})
    assert response.status_code == 409
    assert 'Unicode' in response.get_json()['error']
    assert tree(locations[0]) == before


@pytest.mark.parametrize('failure', ['stage_cleanup', 'journal_cleanup'])
def test_cleanup_failure_after_workspace_commit_is_success_and_retryable(tmp_path, monkeypatch, caplog, failure):
    source = paths(tmp_path/'source')
    source[0].mkdir(parents=True)
    history.save(source[0]/'one', {'meta': {'report_title': 'INSTALLED_UNIQUE'}, 'findings': []})
    payload = backup.export_workspace(*source)
    target = paths(tmp_path/'target')
    target[0].parent.mkdir()
    client = configure(monkeypatch, target)
    real_rmtree, real_unlink = backup.shutil.rmtree, Path.unlink
    def fail_stage(path, *args, **kwargs):
        if Path(path).name.startswith('.workspace-stage-'):
            # A partially removed stage must also be safe on the next retry.
            real_rmtree(Path(path)/'new')
            raise OSError('simulated cleanup failure')
        return real_rmtree(path, *args, **kwargs)
    def fail_journal(path, *args, **kwargs):
        if path.name == '.workspace-restore.json': raise OSError('simulated journal cleanup failure')
        return real_unlink(path, *args, **kwargs)
    with monkeypatch.context() as patcher:
        if failure == 'stage_cleanup': patcher.setattr(backup.shutil, 'rmtree', fail_stage)
        else: patcher.setattr(Path, 'unlink', fail_journal)
        response = client.post('/api/workspace/restore', data={'file': (BytesIO(payload), 'workspace.zip')})
        assert response.status_code == 200, response.get_json()
        result = response.get_json()
        assert result['projects'] == 1 and result['warnings'] == [backup.CLEANUP_WARNING]
        journal = target[0].parent/'.workspace-restore.json'
        assert json.loads(journal.read_bytes())['committed'] is True
        assert load_yaml_file(target[0]/'one/engagement.yaml')['meta']['report_title'] == 'INSTALLED_UNIQUE'
        assert 'limpieza privada pendiente' in caplog.text
    backup.recover(*target)
    backup.recover(*target)
    assert not (target[0].parent/'.workspace-restore.json').exists()
    assert not list(target[0].parent.glob('.workspace-stage-*'))
    assert client.get('/api/projects').get_json()[0]['slug'] == 'one'
