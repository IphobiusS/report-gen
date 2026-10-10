"""Publication validation invariants for explicitly supported vector-only data."""
from copy import deepcopy
from pathlib import Path

from lxml import html
import pytest

import engine
import validate


VECTORS = [
    ('CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H', 'critical'),
    ('CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N', 'info'),
    ('CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:H/SC:N/SI:N/SA:N', 'high'),
    ('CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N', 'info'),
]


def document(vector, severity, missing_score, language):
    finding = {'id': 'F1', 'mode': 'vuln', 'title': 'Caso sintético',
               'cvss_vector': vector, 'severity': severity}
    if missing_score != 'absent':
        finding['cvss'] = {'null': None, 'empty': ''}[missing_score]
    return {'meta': {'report_title': 'Validación sintética', 'lang': language, 'theme': 'serio'},
            'findings': [finding]}


@pytest.mark.parametrize('vector,severity', VECTORS)
@pytest.mark.parametrize('missing_score', ['absent', 'null', 'empty'])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_vector_only_conflicting_severity_is_rejected(vector, severity, missing_score, language):
    wrong = 'critical' if severity == 'info' else 'low'
    data = document(vector, wrong, missing_score, language)
    issues = validate.validate(data, lang=language)
    messages = [message for level, message in issues if level == 'error']
    assert any(('no coincide' if language == 'es' else 'does not match') in message
               and severity in message for message in messages)
    with pytest.raises(ValueError, match='no coincide'):
        validate.require_valid(data, final=True)


@pytest.mark.parametrize('vector,severity', VECTORS)
@pytest.mark.parametrize('missing_score', ['absent', 'null', 'empty'])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_vector_only_consistent_severity_preserves_absent_score(vector, severity, missing_score, language):
    data = document(vector, severity, missing_score, language)
    before = deepcopy(data)
    assert not [x for x in validate.validate(data, lang=language) if x[0] == 'error']
    validate.require_valid(data, final=True)
    tree = html.document_fromstring(engine.render_html(
        engine.build_env(), data, Path.cwd(), {}, False, engine.load_lang(language)))
    assert not tree.xpath('//span[@class="score"]')
    assert tree.xpath('string(//code[@class="vector"])') == vector
    assert data == before


@pytest.mark.parametrize('vector,severity', [row for row in VECTORS if row[1] == 'info'])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_zero_score_remains_explicit_and_matches_vector(vector, severity, language):
    data = document(vector, severity, 'absent', language)
    data['findings'][0]['cvss'] = 0
    validate.require_valid(data, final=True)
    tree = html.document_fromstring(engine.render_html(
        engine.build_env(), data, Path.cwd(), {}, False, engine.load_lang(language)))
    assert tree.xpath('string(//span[@class="score"])') == '0'
    data['findings'][0]['severity'] = 'critical'
    assert any(level == 'error' for level, _ in validate.validate(data, lang=language))


@pytest.mark.parametrize('language', ['es', 'en'])
def test_null_theme_is_rejected_before_export(language):
    data = document(VECTORS[0][0], 'critical', 'absent', language)
    data['meta']['theme'] = None
    assert any(level == 'error' and 'meta.theme' in message
               for level, message in validate.validate(data, lang=language))
    with pytest.raises(ValueError, match='meta.theme'):
        validate.require_valid(data, final=True)


@pytest.mark.parametrize('language', ['es', 'en'])
def test_missing_theme_keeps_renderer_default(language):
    data = document(VECTORS[0][0], 'critical', 'absent', language)
    data['meta'].pop('theme')
    validate.require_valid(data, final=True)
    tree = html.document_fromstring(engine.render_html(
        engine.build_env(), data, Path.cwd(), {}, False, engine.load_lang(language)))
    assert tree.xpath('string(//code[@class="vector"])') == VECTORS[0][0]


@pytest.mark.parametrize('fmt', ['html', 'pdf', 'docx', 'md'])
def test_saved_vector_only_conflict_blocks_api_export_without_rewriting_draft(tmp_path, monkeypatch, fmt):
    import app as api
    import project_history
    from _support import auth_client
    from wizard import dump_yaml

    monkeypatch.setattr(api, 'PROJECTS', tmp_path / 'projects')
    directory = api.PROJECTS / 'vector-conflict'
    data = document(VECTORS[0][0], 'low', 'null', 'es')
    directory.mkdir(parents=True)
    dump_yaml(data, directory / 'engagement.yaml')
    before = {p.relative_to(directory).as_posix(): p.read_bytes()
              for p in directory.rglob('*') if p.is_file()}
    response = auth_client(api.app).post('/api/projects/vector-conflict/export/' + fmt)
    assert response.status_code == 422, response.get_json()
    assert 'no coincide' in response.get_json()['error']
    assert {p.relative_to(directory).as_posix(): p.read_bytes()
            for p in directory.rglob('*') if p.is_file()} == before
    assert not project_history.history(directory)


def test_api_normalizes_null_theme_without_persisting_invalid_theme(tmp_path, monkeypatch):
    import app as api
    from _support import auth_client
    from input_guard import load_yaml_file

    monkeypatch.setattr(api, 'PROJECTS', tmp_path / 'projects')
    client = auth_client(api.app)
    assert client.post('/api/projects', json={'slug': 'null-theme', 'title': 'Sintético'}).status_code == 200
    data = client.get('/api/projects/null-theme').get_json()
    data['meta']['theme'] = None
    assert client.put('/api/projects/null-theme', json=data).status_code == 200
    assert load_yaml_file(api.PROJECTS / 'null-theme' / 'engagement.yaml')['meta']['theme'] == 'serio'


def test_null_theme_capture_fails_at_validation_without_snapshot(tmp_path):
    import delivery
    from wizard import dump_yaml

    data = document(VECTORS[0][0], 'critical', 'absent', 'es')
    data['meta']['theme'] = None
    dump_yaml(data, tmp_path / 'engagement.yaml')
    source = (tmp_path / 'engagement.yaml').read_bytes()
    with pytest.raises(ValueError, match='meta.theme'):
        delivery.capture(tmp_path, tmp_path / 'snapshot')
    assert not (tmp_path / 'snapshot').exists()
    assert (tmp_path / 'engagement.yaml').read_bytes() == source
