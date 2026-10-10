"""Legacy language and exhausted IDs remain safe in the actual local API."""
from copy import deepcopy

from lxml import html
import pytest

import app as api
from _support import auth_client


@pytest.fixture
def local(tmp_path, monkeypatch):
    projects = tmp_path / 'projects'; projects.mkdir()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(tmp_path / 'findings.json'))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path / 'designs.json'))
    client = auth_client(api.app)
    client.post('/api/projects', json={'slug': 'keep', 'title': 'Saved project'})
    return client, projects / 'keep'


@pytest.mark.parametrize('language', ['missing', None, ''])
@pytest.mark.parametrize('route', ['preview', 'export/html'])
def test_legacy_language_api_matches_the_renderer_without_writing_source(local, language, route):
    client, directory = local
    data = {'meta': {'report_title': 'Legacy', 'theme': 'corporativo'}, 'findings': [],
            'report': {'sections': [{'key': 'findings'}]}}
    if language != 'missing': data['meta']['lang'] = language
    before = {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    original = deepcopy(data)
    response = client.post('/api/projects/keep/' + route, json=data)
    assert response.status_code == 200, response.get_json()
    tree = html.fromstring(response.data)
    assert tree.get('lang') == 'en'
    assert data == original
    assert {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()} == before


def test_new_project_keeps_explicit_spanish_while_legacy_fallback_is_english(local):
    client, _ = local
    document = client.get('/api/projects/keep').get_json()
    assert document['meta']['lang'] == 'es'
    supplied = {'meta': {'theme': 'corporativo', 'lang': 'xx'}}
    assert api.sanitize_meta(supplied)['meta']['lang'] == 'es'


@pytest.mark.parametrize('identity', ['F9007199254740992', 'F' + '9' * 5000])
def test_unportable_numeric_id_put_fails_before_replacing_project(local, identity):
    client, directory = local
    response = client.get('/api/projects/keep'); document = response.get_json()
    before = {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    document['findings'] = [{'id': identity, 'title': 'Input cannot replace saved data', 'severity': 'info', 'cvss': 0}]
    updated = client.put('/api/projects/keep', json=document, headers={'If-Match': response.headers['ETag']})
    assert updated.status_code == 422
    assert updated.get_json()['error']
    assert {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()} == before
    assert client.get('/api/projects/keep').headers['ETag'] == response.headers['ETag']


def test_maximum_counter_still_allows_editing_and_exporting(local):
    client, directory = local
    response = client.get('/api/projects/keep'); document = response.get_json()
    document['finding_sequence'] = 2**53 - 1
    document['findings'] = [{'id': 'F9007199254740991', 'title': 'Last safe ID', 'severity': 'info', 'cvss': 0}]
    saved = client.put('/api/projects/keep', json=document, headers={'If-Match': response.headers['ETag']})
    assert saved.status_code == 200, saved.get_json()
    current = client.get('/api/projects/keep').get_json(); current['findings'][0]['title'] = 'Still editable'
    edited = client.put('/api/projects/keep', json=current, headers={'If-Match': saved.headers['ETag']})
    assert edited.status_code == 200, edited.get_json()
    output = client.post('/api/projects/keep/export/html', json=current)
    assert output.status_code == 200
    assert b'Still editable' in output.data
    assert b'Still editable' in (directory / 'engagement.yaml').read_bytes()


def test_unrepresentable_numeric_cvss_put_preserves_saved_data(local):
    client, directory = local
    response = client.get('/api/projects/keep'); document = response.get_json()
    before = {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    document['findings'] = [{'id': 'F1', 'title': 'Unrepresentable score', 'severity': 'info', 'cvss': int('9' * 400)}]
    saved = client.put('/api/projects/keep', json=document, headers={'If-Match': response.headers['ETag']})
    assert saved.status_code == 422
    assert {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()} == before
    assert client.get('/api/projects/keep').headers['ETag'] == response.headers['ETag']


def test_huge_text_cvss_draft_reports_error_and_cannot_be_exported(local):
    client, directory = local
    response = client.get('/api/projects/keep'); document = response.get_json()
    document['findings'] = [{'id': 'F1', 'title': 'Oversized score', 'severity': 'info', 'cvss': '9' * 400}]
    saved = client.put('/api/projects/keep', json=document, headers={'If-Match': response.headers['ETag']})
    assert saved.status_code == 200
    assert any(issue['level'] == 'error' and 'CVSS' in issue['message'] for issue in saved.get_json()['issues'])
    before = {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}
    exported = client.post('/api/projects/keep/export/html', json=document)
    assert exported.status_code == 422
    assert {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()} == before
