"""Creation and raw JSON imports obey the same portable local input boundary."""
from pathlib import Path

import pytest

import app as api
import workspace_backup
from _support import auth_client


@pytest.fixture
def local(tmp_path, monkeypatch):
    projects = tmp_path / 'projects'
    projects.mkdir()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(tmp_path / 'findings.json'))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path / 'designs.json'))
    return auth_client(api.app), projects


@pytest.mark.parametrize('first_route', ['/api/projects', '/api/design-library/projects'])
@pytest.mark.parametrize('first,second', [('Straße', 'strasse'), ('strasse', 'Straße')])
def test_design_creation_cannot_break_workspace_backup_with_unicode_alias(local, first_route, first, second):
    client, projects = local
    initial = client.post(first_route, json={'id': 'htb-cpts', 'title': first})
    assert initial.status_code == 200
    before = {str(p.relative_to(projects)): p.read_bytes() for p in projects.rglob('*') if p.is_file()}
    rejected = client.post('/api/design-library/projects', json={'id': 'htb-cpts', 'title': second})
    assert rejected.status_code == 409
    assert rejected.get_json()['error']
    assert {str(p.relative_to(projects)): p.read_bytes() for p in projects.rglob('*') if p.is_file()} == before
    blob = workspace_backup.export_workspace(projects, api.app.config['LIBRARY_PATH'], api.app.config['DESIGN_LIBRARY_PATH'])
    assert blob.startswith(b'PK')
    # A distinct title is still usable after the rejected creation.
    assert client.post('/api/design-library/projects', json={'id': 'htb-cpts', 'title': 'Distinct project'}).status_code == 200


@pytest.mark.parametrize('payload', [
    b'{"name":"one.txt","name":"two.txt"}',
    b'{"name":"one.txt","required":false,"required":true}',
])
def test_raw_duplicate_attachment_keys_are_rejected_without_history_changes(local, payload):
    client, projects = local
    assert client.post('/api/projects', json={'title': 'Keep', 'slug': 'keep'}).status_code == 200
    current = client.get('/api/projects/keep')
    directory = projects / 'keep'
    before = {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    rejected = client.post('/api/projects/keep/attachments/declare', data=payload,
                           content_type='application/json', headers={'If-Match': current.headers['ETag']})
    assert rejected.status_code == 422
    assert 'duplicada' in rejected.get_json()['error']
    assert {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()} == before
    assert client.get('/api/projects/keep').headers['ETag'] == current.headers['ETag']
    valid = client.post('/api/projects/keep/attachments/declare', json={'name': 'one.txt'},
                        headers={'If-Match': current.headers['ETag']})
    assert valid.status_code == 200


@pytest.mark.parametrize('version', [True, 1.0])
def test_library_import_requires_an_integer_schema_before_any_write(local, version):
    client, _ = local
    current = client.get('/api/library')
    rejected = client.post('/api/library/import', json={'format': 'report-gen-library', 'version': version, 'templates': []},
                           headers={'If-Match': current.headers['ETag']})
    assert rejected.status_code == 422
    assert not Path(api.app.config['LIBRARY_PATH']).exists()
    assert client.get('/api/library').headers['ETag'] == current.headers['ETag']
    assert client.post('/api/library/import', json={'format': 'report-gen-library', 'version': 1, 'templates': []},
                       headers={'If-Match': current.headers['ETag']}).status_code == 200


@pytest.mark.parametrize('date', ['20261007', '2026-W41-3', '2026-10-08T00:00:00'])
def test_noncanonical_retest_date_does_not_change_saved_project(local, date):
    client, projects = local
    assert client.post('/api/projects', json={'slug': 'dates', 'title': 'Dates'}).status_code == 200
    response = client.get('/api/projects/dates')
    data = response.get_json()
    data['findings'] = [{'id': 'F1', 'title': 'Synthetic', 'severity': 'info'}]
    assert client.put('/api/projects/dates', json=data, headers={'If-Match': response.headers['ETag']}).status_code == 200
    current = client.get('/api/projects/dates')
    uid = current.get_json()['findings'][0]['uid']
    directory = projects / 'dates'
    before = {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    record = {'finding_uid': uid, 'tested_on': date, 'assessor': 'Synthetic',
              'notes_md': 'Synthetic observation.', 'result': 'open', 'evidence_uids': []}
    rejected = client.post('/api/projects/dates/retest', json=record, headers={'If-Match': current.headers['ETag']})
    assert rejected.status_code == 422
    assert {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()} == before
    assert client.get('/api/projects/dates').headers['ETag'] == current.headers['ETag']
    record['tested_on'] = '2026-10-08'
    assert client.post('/api/projects/dates/retest', json=record, headers={'If-Match': current.headers['ETag']}).status_code == 200


@pytest.mark.parametrize('route', ['get', 'put'])
def test_unsafe_scalar_integer_is_rejected_before_editor_or_disk_can_round_it(local, route):
    client, projects = local
    assert client.post('/api/projects', json={'slug': 'precision', 'title': 'Precision'}).status_code == 200
    current = client.get('/api/projects/precision')
    directory = projects / 'precision'
    document = current.get_json()
    document['findings'] = [{'id': 'F1', 'title': 'Synthetic machine', 'mode': 'machine',
                             'proof': [{'name': 'Opaque business ID', 'value': 9007199254740993}]}]
    if route == 'get':
        import yaml
        # Represent an already existing legacy file, bypassing guarded writers.
        (directory / 'engagement.yaml').write_text(yaml.safe_dump(document), encoding='utf-8')
    before = {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    response = client.get('/api/projects/precision') if route == 'get' else client.put(
        '/api/projects/precision', json=document, headers={'If-Match': current.headers['ETag']})
    assert response.status_code == 422
    assert response.get_json()['error']
    assert {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()} == before
    # Literal text preserves the complete business identifier across actual JSON transport.
    document['findings'][0]['proof'][0]['value'] = '9007199254740993'
    if route == 'get':
        from wizard import dump_yaml
        dump_yaml(document, directory / 'engagement.yaml')
    else:
        assert client.put('/api/projects/precision', json=document, headers={'If-Match': current.headers['ETag']}).status_code == 200
    loaded = client.get('/api/projects/precision')
    assert loaded.status_code == 200
    assert loaded.get_json()['findings'][0]['proof'][0]['value'] == '9007199254740993'
