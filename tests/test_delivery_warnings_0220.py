"""Review counts survive delivery; private diagnostic detail stays with the author."""
from hashlib import sha256
from io import BytesIO
import json
import time
import zipfile

import pytest
from PIL import Image

import app as api
import delivery
import engine
from export_jobs import ExportQueue
import project_history
import validate
import workflows
from wizard import dump_yaml
from _support import auth_client


def document(language='es', score=True, pending=False):
    finding = {'id': 'F1', 'title': 'Control sintético', 'mode': 'vuln',
               'severity': 'info', 'description_md': 'Descripción documentada',
               'impact_md': 'TODO: contrastar impacto' if pending else 'Impacto observado',
               'remediation_md': 'Corrección propuesta',
               'walkthrough': [{'text_md': 'Resultado observado',
                                'figure': {'src': 'img/proof.png', 'caption': 'Evidencia sintética'}}]}
    if score:
        finding['cvss'] = 0
    return workflows.normalize({'meta': {'report_title': 'Entrega sintética', 'theme': 'serio',
                                         'lang': language, 'assessor': 'Evaluador'},
                                'report': {'sections': [{'key': 'findings'}]},
                                'findings': [finding]})


def save(directory, data):
    (directory / 'img').mkdir(parents=True, exist_ok=True)
    Image.new('RGB', (40, 30), 'green').save(directory / 'img/proof.png')
    dump_yaml(data, directory / 'engagement.yaml')


@pytest.fixture
def client(tmp_path, monkeypatch):
    directory = tmp_path / 'projects' / 'test'
    save(directory, document())
    monkeypatch.setattr(api, 'PROJECTS', directory.parent)
    queue = ExportQueue(timeout=90)
    monkeypatch.setitem(api.app.extensions, 'export_queue', queue)
    yield auth_client(api.app), directory, queue
    queue.close()


def record(response):
    assert response.status_code == 200, response.get_json()
    with zipfile.ZipFile(BytesIO(response.data)) as archive:
        return json.loads(archive.read('verificacion.json')), archive.read('LEEME.txt').decode()


@pytest.mark.parametrize('language', ['es', 'en'])
@pytest.mark.parametrize('score,pending,count', [(True, False, 0), (False, False, 1),
                                               (True, True, 1), (False, True, 2)])
def test_capture_and_api_review_share_all_checks(client, language, score, pending, count):
    c, directory, _ = client
    data = document(language, score, pending)
    save(directory, data)
    before = (directory / 'engagement.yaml').read_bytes()
    reviewed = c.get('/api/projects/test/review?lang=' + language).get_json()['issues']
    captured = delivery.capture(directory, directory.parent / 'capture')
    assert captured['issues'] == reviewed
    assert len(reviewed) == count
    assert all(issue['level'] == 'warning' for issue in reviewed)
    assert all(set(('level', 'message', 'path', 'finding_uid', 'help')) <= issue.keys()
               for issue in reviewed)
    assert (directory / 'engagement.yaml').read_bytes() == before
    if pending:
        issue = next(i for i in reviewed if 'TODO' in i['message'])
        assert issue['path'] == 'findings[0].impact_md'
        assert issue['finding_uid'] == data['findings'][0]['uid']


def test_same_warning_keeps_workflow_metadata_without_duplication(tmp_path, monkeypatch):
    data = document(pending=True)
    save(tmp_path, data)
    original = workflows.review(data, tmp_path)[0]
    monkeypatch.setattr(validate, 'validate', lambda *args, **kwargs: [('warning', original['message'])])
    assert workflows.preflight(data, tmp_path) == [original]


def test_invalid_structure_is_reported_without_workflow_traversal(tmp_path):
    issues = workflows.preflight({'meta': {}, 'findings': 'broken'}, tmp_path)
    assert issues and all(i['level'] == 'error' for i in issues)


@pytest.mark.parametrize('endpoint', ['delivery', 'jobs'])
def test_cvss_only_warning_requires_acknowledgement_at_api_boundary(client, endpoint):
    c, directory, _ = client
    save(directory, document(score=False))
    tag = c.get('/api/projects/test').headers['ETag']
    before = (directory / 'engagement.yaml').read_bytes()
    body = {'formats': ['md'], 'label': 'Revisión pendiente'}
    if endpoint == 'jobs':
        body['kind'] = 'delivery'
    response = c.post('/api/projects/test/' + endpoint, json=body, headers={'If-Match': tag})
    assert response.status_code == 422 and 'avisos' in response.get_json()['error']
    assert not c.get('/api/jobs').get_json()
    assert (directory / 'engagement.yaml').read_bytes() == before


def test_acknowledged_validation_warning_survives_all_four_formats(client):
    c, directory, _ = client
    save(directory, document(score=False))
    before = (directory / 'engagement.yaml').read_bytes()
    tag = c.get('/api/projects/test').headers['ETag']
    reviewed = c.get('/api/projects/test/review').get_json()['issues']
    response = c.post('/api/projects/test/delivery',
                      json={'formats': ['pdf', 'docx', 'md', 'html'], 'label': 'Entrega revisada',
                            'acknowledge_warnings': True}, headers={'If-Match': tag})
    manifest, readme = record(response)
    assert len(manifest['warnings']) == len(reviewed) == 1
    assert manifest['warnings'][0]['category'] == 'report'
    assert 'validación' in manifest['warnings'][0]['message']
    assert 'CVSS' in reviewed[0]['message']
    assert 'path' not in manifest['warnings'][0] and 'finding_uid' not in manifest['warnings'][0]
    assert 'Avisos revisados: 1' in readme
    assert set(manifest['files']) == {'informe.pdf', 'informe.docx', 'markdown.zip', 'informe.html'}
    assert manifest['source_revision'] == sha256(before).hexdigest()
    assert (directory / 'engagement.yaml').read_bytes() == before


def test_acknowledged_mixed_warnings_and_clean_delivery_are_not_changed(client):
    c, directory, _ = client
    for score, pending in [(False, True), (True, False)]:
        save(directory, document(score=score, pending=pending))
        reviewed = c.get('/api/projects/test/review').get_json()['issues']
        tag = c.get('/api/projects/test').headers['ETag']
        manifest, readme = record(c.post('/api/projects/test/delivery',
            json={'formats': ['md'], 'label': 'Revisado', 'acknowledge_warnings': bool(reviewed)},
            headers={'If-Match': tag}))
        assert len(manifest['warnings']) == len(reviewed)
        assert all(row['level'] == 'warning' and 'details' in row for row in manifest['warnings'])
        assert f'Avisos revisados: {len(reviewed)}' in readme


@pytest.mark.parametrize('endpoint', ['delivery', 'jobs'])
def test_invalid_data_remains_blocking_even_when_warnings_are_acknowledged(client, endpoint):
    c, directory, _ = client
    data = document()
    data['findings'][0]['cvss'] = 99
    save(directory, data)
    before = (directory / 'engagement.yaml').read_bytes()
    tag = c.get('/api/projects/test').headers['ETag']
    body = {'formats': ['md'], 'label': 'Inválido', 'acknowledge_warnings': True}
    if endpoint == 'jobs':
        body['kind'] = 'delivery'
    response = c.post('/api/projects/test/' + endpoint, json=body, headers={'If-Match': tag})
    assert response.status_code == 422 and 'CVSS' in response.get_json()['error']
    assert not c.get('/api/jobs').get_json()
    assert (directory / 'engagement.yaml').read_bytes() == before


@pytest.mark.parametrize('endpoint', ['delivery', 'jobs'])
def test_acknowledgement_cannot_apply_to_a_stale_revision(client, endpoint):
    c, directory, _ = client
    save(directory, document(score=False))
    tag = c.get('/api/projects/test').headers['ETag']
    data = engine.load_engagement(directory / 'engagement.yaml')
    data['findings'][0]['title'] = 'Revisión nueva'
    project_history.save(directory, data)
    body = {'formats': ['md'], 'label': 'Obsoleto', 'acknowledge_warnings': True}
    if endpoint == 'jobs':
        body['kind'] = 'delivery'
    assert c.post('/api/projects/test/' + endpoint, json=body,
                  headers={'If-Match': tag}).status_code == 409
    assert not c.get('/api/jobs').get_json()


@pytest.mark.parametrize('endpoint', ['delivery', 'jobs'])
def test_review_changes_do_not_bypass_csrf_or_required_revision(client, endpoint):
    body = {'formats': ['md'], 'label': 'Protegido', 'acknowledge_warnings': True}
    if endpoint == 'jobs':
        body['kind'] = 'delivery'
    with api.app.test_client() as raw:
        token = raw.get('/api/session').get_json()['csrf']
        assert raw.post('/api/projects/test/' + endpoint, json=body).status_code == 403
        assert raw.post('/api/projects/test/' + endpoint, json=body,
                        headers={'X-CSRF-Token': token}).status_code == 428


def wait_job(client, key):
    deadline = time.monotonic() + 55
    while time.monotonic() < deadline:
        response = client.get('/api/jobs/' + key)
        state = response.get_json()
        if state['stage'] in ('done', 'error', 'cancelled'):
            assert state['stage'] == 'done', state
            return
        time.sleep(.05)
    pytest.fail('La exportación no terminó')


@pytest.mark.parametrize('kind', ['delivery', 'export'])
def test_queued_exports_keep_validation_warnings_and_saved_snapshot(client, monkeypatch, kind):
    c, directory, queue = client
    save(directory, document(score=False))
    tag = c.get('/api/projects/test').headers['ETag']
    reviewed = c.get('/api/projects/test/review').get_json()['issues']
    source = (directory / 'engagement.yaml').read_bytes()
    original_submit = queue.submit
    def submit_then_edit(*args, **kwargs):
        result = original_submit(*args, **kwargs)
        later = document()
        later['findings'][0]['title'] = 'POSTERIOR'
        project_history.save(directory, later)
        return result
    monkeypatch.setattr(queue, 'submit', submit_then_edit)
    response = c.post('/api/projects/test/jobs',
        json={'kind': kind, 'formats': ['md'], 'label': 'Captura revisada',
              'acknowledge_warnings': True}, headers={'If-Match': tag})
    assert response.status_code == 202, response.get_json()
    key = response.get_json()['id']
    wait_job(c, key)
    verification = c.get('/api/jobs/' + key + '/verification').get_json()
    assert len(verification['warnings']) == len(reviewed) == 1
    assert verification['warnings'][0]['category'] == 'report'
    assert 'validación' in verification['warnings'][0]['message']
    assert 'CVSS' in reviewed[0]['message']
    assert verification['source_revision'] == sha256(source).hexdigest()
    downloaded = c.get('/api/jobs/' + key + '/download')
    assert downloaded.status_code == 200
    if kind == 'delivery':
        manifest, readme = record(downloaded)
        assert manifest == verification and 'Avisos revisados: 1' in readme
        with zipfile.ZipFile(BytesIO(downloaded.data)) as archive:
            markdown = archive.read('markdown.zip')
    else:
        markdown = downloaded.data
    with zipfile.ZipFile(BytesIO(markdown)) as archive:
        text = archive.read('report.md').decode()
    assert 'Control sintético' in text and 'POSTERIOR' not in text


def test_capture_uses_the_document_reviewed_without_reloading_it(tmp_path, monkeypatch):
    save(tmp_path, document(score=False))
    original = delivery.engine.load_engagement
    loads = []
    def once(path):
        loads.append(path)
        if len(loads) > 1:
            pytest.fail('Captura volvió a cargar una revisión que no había revisado')
        return original(path)
    monkeypatch.setattr(delivery.engine, 'load_engagement', once)
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    assert len(loads) == 1 and len(captured['issues']) == 1
    frozen = original(tmp_path / 'snapshot/engagement.yaml')
    assert 'cvss' not in frozen['findings'][0]


@pytest.mark.parametrize('key,value', [('meta', None), ('meta', 'invalid'), ('findings', None)])
def test_malformed_source_capture_keeps_controlled_error_and_no_snapshot(tmp_path, key, value):
    data = document()
    data[key] = value
    save(tmp_path, data)
    before = (tmp_path / 'engagement.yaml').read_bytes()
    with pytest.raises(ValueError):
        delivery.capture(tmp_path, tmp_path / 'snapshot')
    assert not (tmp_path / 'snapshot').exists()
    assert (tmp_path / 'engagement.yaml').read_bytes() == before


def test_missing_legacy_meta_stays_supported_and_its_warning_is_retained(tmp_path):
    data = document()
    del data['meta']
    save(tmp_path, data)
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    assert any('meta.report_title' in issue['message'] and issue['level'] == 'warning'
               for issue in captured['issues'])
