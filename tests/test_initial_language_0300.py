"""The launcher's initial language is independent from report language."""
import os

import pytest

import app as api
import start


@pytest.mark.parametrize('previous', [None, 'es', 'en'])
def test_launcher_language_reaches_server_and_restores_embedding_environment(tmp_path, monkeypatch, previous):
    if previous is None:
        monkeypatch.delenv('REPORT_GEN_UI_LANG', raising=False)
    else:
        monkeypatch.setenv('REPORT_GEN_UI_LANG', previous)
    monkeypatch.setattr(start, 'ROOT', tmp_path)
    monkeypatch.setattr(start, '_dependencies', lambda _python: True)
    observed = []
    monkeypatch.setattr(start, '_run_server', lambda _python, _port: observed.append(os.environ['REPORT_GEN_UI_LANG']) or 0)
    assert start.main(['--lang', 'en']) == 0
    assert observed == ['en']
    assert os.environ.get('REPORT_GEN_UI_LANG') == previous


@pytest.mark.parametrize('configured,expected', [('en', 'en'), ('es', 'es'), ('unsupported', 'es')])
def test_session_exposes_bounded_initial_language_without_touching_project_data(tmp_path, monkeypatch, configured, expected):
    monkeypatch.setattr(api, 'PROJECTS', tmp_path / 'projects')
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(tmp_path / 'library/findings.json'))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path / 'library/designs.json'))
    monkeypatch.setitem(api.app.config, 'UI_LANGUAGE', configured)
    response = api.app.test_client().get('/api/session')
    assert response.status_code == 200
    assert response.get_json()['ui_language'] == expected
    assert not (tmp_path / 'projects').exists()
    assert not (tmp_path / 'library').exists()
