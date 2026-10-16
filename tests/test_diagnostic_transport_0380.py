"""Structured failures cross real worker and API boundaries, staying private."""
from io import BytesIO
import json
import subprocess
import sys
import time
import zipfile

import pytest

import app as api
import export_jobs
import publication
import workflows
from _support import auth_client
from wizard import dump_yaml


@pytest.fixture
def source(tmp_path):
    directory = tmp_path / 'project'
    directory.mkdir()
    data = workflows.normalize({'meta': {'report_title': 'Private diagnostic transport',
        'lang': 'en', 'theme': 'corporativo'},
        'report': {'sections': [{'key': 'findings_summary'}, {'key': 'findings'}]},
        'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'Synthetic approval workflow',
            'severity': 'info', 'cvss': 0,
            'description_md': '| Stage | State |\n| --- | --- |\n| Review | Required |',
            'impact_md': 'Synthetic impact.', 'remediation_md': 'Review the control.'}]})
    dump_yaml(data, directory / 'engagement.yaml')
    return directory


def specification(kind='single'):
    return dict(kind=kind, formats=['html'], label='Synthetic delivery', revision='synthetic-revision',
                filename='report.html' if kind == 'single' else 'delivery.zip')


def capture(source, target, *, mismatch=False):
    result = publication.snapshot(source, target)
    result['issues'] = []  # The queue API adds the acknowledged preflight issues.
    if mismatch:
        # Fault injection at the captured contract boundary: the real worker
        # renders the unchanged source and must reject this mismatched contract.
        scope = next(item for item in result['contract']['scopes'] if item['id'] == 'F01')
        assert scope['tables'][0][1][1] == 'Required'
        scope['tables'][0][1][1] = 'Expected approval'
        scope['table_rows'][1][1] = 'Expected approval'
    return result


def terminal(queue, owner, key):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        state = queue.status(owner, key)
        if state['stage'] in export_jobs.TERMINAL:
            return state
        time.sleep(.025)
    pytest.fail('Real export worker did not finish within 30 seconds')


def test_real_worker_writes_structured_error_without_publishing_result(source, tmp_path):
    root = tmp_path / 'job'
    root.mkdir()
    config = dict(specification(), captured=capture(source, root / 'source', mismatch=True), error_language='en')
    (root / 'job.json').write_text(json.dumps(config), encoding='utf-8')
    worker = subprocess.run([sys.executable, export_jobs.__file__, '--worker', str(root)],
                            capture_output=True, text=True, timeout=30)
    assert worker.returncode == 1, worker.stderr
    details = json.loads((root / 'error.json').read_text(encoding='utf-8'))
    assert details[0]['location'] == {'operation': 'export', 'format': 'html', 'finding_id': 'F01',
                                      'field': 'tables', 'table': 1, 'row': 2, 'cell': 2}
    assert details[0]['message'] == (root / 'error.txt').read_text(encoding='utf-8')
    assert 'Expected approval' not in json.dumps(details)
    assert not (root / 'result').exists() and not (root / 'verification.json').exists()


def test_real_queue_transports_worker_location_then_removes_private_work_files(source):
    queue = export_jobs.ExportQueue(timeout=30)
    try:
        job = queue.submit('owner-a', lambda target: capture(source, target, mismatch=True), specification())
        state = terminal(queue, 'owner-a', job['id'])
        assert state['stage'] == 'error', state
        assert state['diagnostics'][0]['location'] == {
            'operation': 'export', 'format': 'html', 'finding_id': 'F01',
            'field': 'tables', 'table': 1, 'row': 2, 'cell': 2}
        assert not state['verification_available']
        with pytest.raises(KeyError):
            queue.status('owner-b', job['id'])
        with pytest.raises(ValueError):
            queue.result('owner-a', job['id'])
        assert not list((queue.root / job['id']).iterdir())
    finally:
        queue.close()


def test_successful_real_delivery_has_no_diagnostic_metadata_in_public_manifest(source):
    queue = export_jobs.ExportQueue(timeout=30)
    try:
        job = queue.submit('owner-a', lambda target: capture(source, target), specification('delivery'))
        state = terminal(queue, 'owner-a', job['id'])
        assert state['stage'] == 'done', state
        assert state['diagnostics'] == [] and state['verification_available']
        payload, filename = queue.result('owner-a', job['id'])
        assert filename == 'delivery.zip'
        with zipfile.ZipFile(BytesIO(payload)) as archive:
            assert not {'error.json', 'error.txt'} & set(archive.namelist())
            manifest = archive.read('verificacion.json').decode()
        assert 'diagnostics' not in manifest and 'source_location' not in manifest
        assert 'finding_uid' not in manifest
    finally:
        queue.close()


@pytest.mark.parametrize(('language', 'tag'), [('es', 'es'), ('en', 'en'), ('pt', 'pt-BR')])
def test_real_api_invalid_data_returns_localized_diagnostics_without_writing_source(source, monkeypatch, language, tag):
    monkeypatch.setattr(api, 'PROJECTS', source.parent)
    client = auth_client(api.app)
    opened = client.get('/api/projects/project')
    before = (source / 'engagement.yaml').read_bytes()
    body = {'format': 'nuclei', 'text': json.dumps({'template-id': 'synthetic', 'matched-at': 'https://example.test/',
            'info': {'name': 'Observation', 'severity': {'private': 'DO-NOT-COPY-PRIVATE-VALUE'}}})}
    response = client.post('/api/projects/project/intake/preview', json=body,
                           headers={'If-Match': opened.headers['ETag'], 'X-UI-Language': language})
    assert response.status_code == 422, response.json
    assert response.headers['Content-Language'] == tag
    assert response.json['error'] == response.json['diagnostics'][0]['message']
    assert response.json['diagnostics'][0]['location'] == {
        'operation': 'import', 'format': 'nuclei', 'record': 1, 'line': 1, 'field': 'info.severity'}
    assert 'DO-NOT-COPY-PRIVATE-VALUE' not in response.get_data(as_text=True)
    assert (source / 'engagement.yaml').read_bytes() == before
