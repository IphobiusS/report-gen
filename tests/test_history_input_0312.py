"""Malformed checkpoint options fail before changing a saved project or history."""
import pytest

import app as api
from _support import auth_client


@pytest.mark.parametrize('stage', [[], {}, None, True, 4])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_checkpoint_rejects_nontext_stage_without_writing(tmp_path, monkeypatch, stage, language):
    projects = tmp_path / 'projects'
    projects.mkdir()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(tmp_path / 'findings.json'))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path / 'designs.json'))
    client = auth_client(api.app)
    assert client.post('/api/projects', json={'slug': 'audit'}).status_code == 200
    saved = client.get('/api/projects/audit')
    before = {p.relative_to(projects): p.read_bytes() for p in projects.rglob('*') if p.is_file()}
    response = client.post('/api/projects/audit/history', json={'label': 'Review', 'stage': stage},
                           headers={'If-Match': saved.headers['ETag'], 'X-UI-Language': language})
    assert response.status_code == 422
    assert response.get_json()['error']
    assert response.headers['Content-Language'] == language
    assert {p.relative_to(projects): p.read_bytes() for p in projects.rglob('*') if p.is_file()} == before
    assert client.get('/api/projects/audit').headers['ETag'] == saved.headers['ETag']
