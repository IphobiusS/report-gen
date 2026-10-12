"""Gallery selection and project details survive the real creation boundary."""
import pytest

import app as api
from _support import auth_client


@pytest.fixture
def local(tmp_path, monkeypatch):
    projects = tmp_path / 'projects'
    projects.mkdir()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path / 'designs.json'))
    return auth_client(api.app), projects


def test_explicit_appearance_and_structure_are_independent(local):
    client, _ = local
    result = client.post('/api/projects', json={
        'title': 'Synthetic board report', 'client': 'Synthetic client', 'slug': 'board',
        'model': 'laboratorio-en', 'preset': 'base', 'appearance': 'laboratorio',
    })
    assert result.status_code == 200
    data = client.get('/api/projects/board').get_json()
    assert data['meta']['theme'] == 'laboratorio'
    assert data['meta']['lang'] == 'en'
    assert data['meta']['client'] == 'Synthetic client'
    assert data['report']['sections']


def test_unknown_appearance_never_creates_a_fallback_project(local):
    client, projects = local
    result = client.post('/api/projects', json={'title': 'Synthetic', 'appearance': 'missing'})
    assert result.status_code == 422
    assert list(projects.iterdir()) == []


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_specialized_design_preserves_client_slug_language_and_variant(local, lang):
    client, _ = local
    result = client.post('/api/design-library/projects', json={
        'title': 'Synthetic assessment', 'client': 'Synthetic bank', 'slug': 'chosen-folder',
        'id': 'enterprise-purple-team', 'lang': lang, 'variant': 'quiet',
    })
    assert result.status_code == 200
    assert result.get_json()['slug'] == 'chosen-folder'
    data = client.get('/api/projects/chosen-folder').get_json()
    assert data['meta']['client'] == 'Synthetic bank'
    assert data['meta']['lang'] == lang
    assert data['meta']['design']['id'] == 'enterprise-purple-team'
    assert data['meta']['design']['variant'] == 'quiet'
    assert data['findings'] == []


@pytest.mark.parametrize('route', ['/api/projects', '/api/design-library/projects'])
@pytest.mark.parametrize('field,value', [('client', ['not text']), ('slug', {'name': 'bad'})])
def test_both_creation_routes_reject_nontext_before_writing(local, route, field, value):
    client, projects = local
    result = client.post(route, json={'title': 'Synthetic', 'id': 'htb-cpts', field: value})
    assert result.status_code == 400
    assert list(projects.iterdir()) == []


def test_specialized_custom_slug_obeys_cross_route_collision_guard(local):
    client, projects = local
    assert client.post('/api/projects', json={'title': 'Existing', 'slug': 'Straße'}).status_code == 200
    before = {str(p.relative_to(projects)): p.read_bytes() for p in projects.rglob('*') if p.is_file()}
    result = client.post('/api/design-library/projects', json={
        'title': 'Different title', 'slug': 'strasse', 'client': 'Synthetic', 'id': 'htb-cpts',
    })
    assert result.status_code == 409
    assert {str(p.relative_to(projects)): p.read_bytes() for p in projects.rglob('*') if p.is_file()} == before
