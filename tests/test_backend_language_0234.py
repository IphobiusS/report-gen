"""Actual local API errors select prose before inserting opaque authored values."""
import ast
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from string import Formatter
import subprocess
import sys
import time

import pytest
import app as api
import error_messages as messages
from _support import auth_client

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def local(tmp_path, monkeypatch):
    projects = tmp_path / 'projects'; projects.mkdir()
    monkeypatch.setattr(api, 'PROJECTS', projects)
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(tmp_path / 'findings.json'))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path / 'designs.json'))
    client = auth_client(api.app)
    assert client.post('/api/projects', json={'slug': 'keep', 'title': 'falta evidencia / auteur'}).status_code == 200
    return client, projects


def contents(directory):
    return {str(p.relative_to(directory)): p.read_bytes() for p in directory.rglob('*') if p.is_file()}


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('case', ['csrf', 'origin', 'fetch-site', 'json-required', 'json-object',
                                  'duplicate-json', 'revision-required', 'revision-conflict',
                                  'image-missing', 'image-invalid', 'cvss', 'missing-project',
                                  'retest-option', 'intake-field', 'design-revision', 'schema'])
def test_api_failure_preserves_codes_revision_and_saved_files(local, language, case):
    client, projects = local; before = contents(projects)
    current = client.get('/api/projects/keep'); tag = current.headers['ETag']
    headers = {'X-UI-Language': language}; payload = current.get_json()
    if case == 'csrf':
        headers['X-CSRF-Token'] = 'expired'
        response = client.post('/api/projects', json={}, headers=headers)
        status, fragment = 403, ('Sesión local caducada', 'Local session expired')
    elif case == 'origin':
        headers['Origin'] = 'https://elsewhere.invalid'
        response = client.get('/api/projects', headers=headers)
        status, fragment = 403, ('Origen no permitido', 'Origin is not allowed')
    elif case == 'fetch-site':
        headers['Sec-Fetch-Site'] = 'cross-site'
        response = client.get('/api/projects', headers=headers)
        status, fragment = 403, ('Solicitud entre sitios bloqueada', 'Cross-site request blocked')
    elif case == 'json-required':
        response = client.post('/api/projects', data='input', headers=headers)
        status, fragment = 415, ('Se requiere application/json', 'application/json is required')
    elif case == 'json-object':
        response = client.post('/api/projects', json=[], headers=headers)
        status, fragment = 400, ('Se esperaba un objeto JSON', 'Expected a JSON object')
    elif case == 'duplicate-json':
        response = client.post('/api/projects', data='{"falta evidencia":1,"falta evidencia":2}', content_type='application/json', headers=headers)
        status, fragment = 422, ('Clave JSON duplicada: falta evidencia', 'Duplicate JSON key: falta evidencia')
    elif case == 'revision-required':
        response = client.post('/api/projects/keep/history', json={'label': 'a'}, headers=headers)
        status, fragment = 428, ('Falta la revisión del proyecto', 'Project revision is required')
    elif case == 'revision-conflict':
        headers['If-Match'] = 'changed'; response = client.put('/api/projects/keep', json=payload, headers=headers)
        status, fragment = 409, ('El proyecto cambió en otra pestaña', 'Project changed in another tab')
    elif case == 'image-missing':
        response = client.post('/api/projects/keep/image', headers=headers)
        status, fragment = 400, ('sin archivo', 'no file')
    elif case == 'image-invalid':
        from io import BytesIO
        response = client.post('/api/projects/keep/image', data={'file': (BytesIO(b'bad'), 'falta evidencia.png')}, headers=headers)
        status, fragment = 400, ('el archivo no es una imagen valida', 'file is not a valid image')
    elif case == 'cvss':
        response = client.post('/api/cvss', json={'version': '4.0', 'vector': 'CVSS:4.0/bad'}, headers=headers)
        status, fragment = 400, ('vector CVSS 4.0 invalido', 'invalid CVSS 4.0 vector')
    elif case == 'missing-project':
        response = client.get('/api/projects/falta-evidencia', headers=headers)
        status, fragment = 404, ('proyecto no encontrado: falta-evidencia', 'project not found: falta-evidencia')
    elif case == 'retest-option':
        response = client.get('/api/projects/keep/retest-diff?revision=' + tag.strip('"') + '&unknown=1', headers=headers)
        status, fragment = 422, ('Opciones de comparación inválidas', 'Invalid comparison options')
    elif case == 'intake-field':
        headers['If-Match'] = tag
        response = client.post('/api/projects/keep/intake/preview', json={'unknown': 1}, headers=headers)
        status, fragment = 422, ('Campos de importación desconocidos', 'Unknown import fields')
    elif case == 'design-revision':
        response = client.post('/api/design-library/personal', json={}, headers=headers)
        status, fragment = 428, ('Recarga la biblioteca antes de modificarla', 'Reload the library before modifying it')
    else:
        headers['If-Match'] = tag; payload['findings'] = [{'id': 'falta evidencia', 'title': 4}]
        response = client.put('/api/projects/keep', json=payload, headers=headers)
        status, fragment = 422, ('findings[0].title: se esperaba text', 'findings[0].title: expected text')
    assert response.status_code == status, response.get_json()
    assert fragment[language == 'en'] in response.get_json()['error']
    assert response.headers['Content-Language'] == language
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['X-Content-Type-Options'] == 'nosniff'
    assert contents(projects) == before
    assert client.get('/api/projects/keep').headers['ETag'] == tag
    assert messages.current_language() == 'es'


@pytest.mark.parametrize('language', [None, 'es', 'EN', 'en-US', 'fr', ''])
def test_unsupported_header_preserves_spanish_ignoring_browser_language(local, language):
    client, _ = local; headers = {'Accept-Language': 'en-US,en;q=0.9'}
    if language is not None: headers['X-UI-Language'] = language
    response = client.get('/api/projects/falta-evidencia', headers=headers)
    assert response.get_json() == {'error': 'proyecto no encontrado: falta-evidencia'}
    assert response.headers['Content-Language'] == 'es'


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('case', ['host', '404', '405', '413', '503'])
def test_framework_and_storage_errors_keep_guards_and_hide_paths(local, monkeypatch, tmp_path, language, case):
    client, projects = local; before = contents(projects); headers = {'X-UI-Language': language}
    if case == 'host':
        response = client.get('/api/projects', base_url='http://untrusted.invalid', headers=headers); status = 400
    elif case == '404':
        response = client.get('/api/not-a-route', headers=headers); status = 404
    elif case == '405':
        response = client.delete('/api/session', headers=headers); status = 405
    elif case == '413':
        monkeypatch.setitem(api.app.config, 'MAX_CONTENT_LENGTH', 3)
        response = client.post('/api/projects', data='123456789', content_type='application/json', headers=headers); status = 413
    else:
        unavailable = tmp_path / 'private-storage-path'; unavailable.write_text('not a directory')
        monkeypatch.setattr(api, 'PROJECTS', unavailable)
        response = client.get('/api/projects', headers=headers); status = 503
        assert 'private-storage-path' not in response.get_json()['error']
        assert ('Could not complete the operation' if language == 'en' else 'No se pudo completar la operación') in response.get_json()['error']
    assert response.status_code == status, response.get_json()
    assert response.headers['Content-Language'] == language
    assert response.headers['Cache-Control'] == 'no-store'
    assert contents(projects) == before
    assert messages.current_language() == 'es'


def test_review_english_keeps_opaque_identity_and_path(local):
    import workflows
    import validate
    _, projects = local
    identity = 'falta evidencia importación pendiente de revisión'; path = 'img/falta evidencia.png'
    document = {'meta': {'lang': 'es'}, 'findings': [{'id': identity, 'title': 'Authored title',
        'walkthrough': [{'figure': {'src': path}}], 'severity': 'info', 'cvss': 0}]}
    rows = workflows.preflight(document, projects / 'keep', 'en')
    assert any(row['message'] == identity + ': missing description_md' for row in rows)
    assert any(row['message'] == 'Missing or disallowed image: ' + path for row in rows)
    with messages.language_scope('en'):
        assert validate.structure_issues({'finding_sequence': -1}) == [('error', 'finding_sequence: invalid identifier counter')]
        assert ('error', 'findings: se esperaba list') in validate.structure_issues({'findings': 'wrong'}, 'es')
    assert messages.current_language() == 'es'


def test_api_validation_ui_preference_keeps_report_language_and_authored_content(local):
    client, projects = local; before = contents(projects)
    document = {'meta': {'lang': 'es', 'report_title': 'falta evidencia'}, 'findings': [
        {'id': 'falta evidencia', 'severity': 'wrong', 'title': 'falta evidencia'}]}
    snapshot = json.loads(json.dumps(document))
    response = client.post('/api/validate', json=document, headers={'X-UI-Language': 'en'})
    assert response.status_code == 200
    assert any(row['message'] == "falta evidencia: invalid severity 'wrong'" for row in response.get_json()['issues'])
    assert document == snapshot and contents(projects) == before


def test_catalog_preserves_format_fields_and_covers_every_source_message():
    formatter = Formatter()
    for source, english in messages.CATALOG.items():
        fields = lambda text: sorted((key, conversion, spec) for _, key, spec, conversion in formatter.parse(text) if key is not None)
        assert fields(source) == fields(english), source
    sites = 0
    for path in list(ROOT.glob('*.py')) + list((ROOT / 'webapp').glob('*.py')) + list((ROOT / 'exporters').glob('*.py')):
        if path.name == 'error_messages.py': continue
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                values = node.args[1:2] if node.func.id == 'abort' else node.args[:1] if node.func.id in {'ValueError', 'TypeError', 'RuntimeError'} else []
                assert not any(isinstance(value, (ast.Constant, ast.JoinedStr, ast.BinOp)) for value in values), (path, node.lineno)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in {'backend_message', 'message'}:
                assert node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str), path
                assert node.args[0].value in messages.CATALOG or any(k.arg == 'en' for k in node.keywords), (path, node.args[0].value)
                sites += 1
    assert sites >= 600


def test_unknown_template_and_opaque_parameter_use_safe_fallback():
    opaque = 'falta evidencia / Invalid text {p0} 20 MB'
    with messages.language_scope('en'):
        assert messages.message('Future detail: {value}', value=opaque) == 'Future detail: ' + opaque
        assert messages.message('{p0}: texto obligatorio y acotado / bounded text required', p0=opaque).startswith(opaque + ':')
    assert messages.current_language() == 'es'


def test_concurrent_request_languages_are_isolated(local):
    def read(language):
        client = api.app.test_client()
        for _ in range(10):
            response = client.get('/api/projects/falta-evidencia', headers={'X-UI-Language': language})
            expected = 'project not found: falta-evidencia' if language == 'en' else 'proyecto no encontrado: falta-evidencia'
            assert response.get_json()['error'] == expected
            assert response.headers['Content-Language'] == language
            assert messages.current_language() == 'es'
        return language
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(read, ['en', 'es', 'en', 'es'])) == ['en', 'es', 'en', 'es']


@pytest.mark.parametrize('language', ['es', 'en'])
def test_real_worker_retains_submission_language_when_poll_language_differs(tmp_path, language):
    from export_jobs import ExportQueue
    queue = ExportQueue(timeout=20)
    def prepare(target):
        target.mkdir(); (target / 'engagement.yaml').write_text('meta: {lang: es, report_title: authored}\nfindings: []\n')
        return {}
    try:
        with messages.language_scope(language):
            submitted = queue.submit('owner', prepare, dict(kind='export', formats=['not-a-format'],
                label='falta evidencia', revision='saved', filename='falta evidencia.pdf'))
        key = submitted['id']; deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            with messages.language_scope('es' if language == 'en' else 'en'): row = queue.status('owner', key)
            if row['stage'] in {'done', 'error', 'cancelled'}: break
            time.sleep(.05)
        assert row['stage'] == 'error', row
        assert row['label'] == 'falta evidencia' and row['filename'] == 'falta evidencia.pdf'
        assert ('Unsupported format' if language == 'en' else 'Formato no soportado / Unsupported format') in row['error'], row
        assert messages.current_language() == 'es'
    finally:
        queue.close()


@pytest.mark.parametrize('language', ['es', 'en'])
def test_engine_error_preference_is_independent_from_document_language(tmp_path, language):
    source = tmp_path / 'engagement.yaml'; source.write_text('meta: {lang: es, theme: serio}\nfindings: []\n')
    response = subprocess.run([sys.executable, str(ROOT / 'engine.py'), str(source), '--error-language', language,
        '--theme', 'unknown', '--html', '-o', str(tmp_path / 'report.pdf')], capture_output=True, text=True, timeout=15)
    assert response.returncode != 0
    assert ('unsupported meta.theme' if language == 'en' else 'meta.theme no soportado') in response.stderr
    assert not (tmp_path / 'report.pdf').exists()
    assert source.read_text() == 'meta: {lang: es, theme: serio}\nfindings: []\n'
