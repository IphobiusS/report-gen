"""Known PDF pagination locations survive the renderer and export worker."""
import json
from pathlib import Path
import subprocess
import time

import pytest

import engine
import export
import exporters.pdf as pdf
from diagnostic_locations import DiagnosticError, error_diagnostics
from error_messages import language_scope
from export_jobs import ExportQueue
from pdf_pagination import table_error
from wizard import dump_yaml


LOCATION = {'operation': 'export', 'format': 'pdf', 'finding_id': 'F12'}


@pytest.fixture
def oversized(tmp_path):
    directory = tmp_path / 'project'
    directory.mkdir()
    data = {'meta': {'report_title': 'Fictional PDF diagnostic case', 'lang': 'en', 'theme': 'serio'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F12', 'title': 'Synthetic protected control table',
                          'mode': 'vuln', 'severity': 'info',
                          'description_md': '| ' + 'IMPOSSIBLE_HEADER ' * 1000 +
                          ' | Result |\n| --- | --- |\n| One | Original retained. |'}]}
    dump_yaml(data, directory / 'engagement.yaml')
    return directory


@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
def test_real_renderer_failure_preserves_exact_finding_and_previous_output(oversized, language):
    source = oversized / 'engagement.yaml'
    before = source.read_bytes()
    output = oversized / 'report.pdf'
    previous = b'PREVIOUS_VERIFIED_REPORT'
    output.write_bytes(previous)
    with language_scope(language), pytest.raises(DiagnosticError) as caught:
        export.export(source, 'pdf', output)
    details = error_diagnostics(caught.value)
    assert len(details) == 1 and details[0]['location'] == LOCATION
    assert details[0]['code'] == 'export.pdf.table_oversized'
    assert details[0]['message'] in str(caught.value) and '[!]' in str(caught.value)
    assert source.read_bytes() == before and output.read_bytes() == previous
    assert {path.name for path in oversized.iterdir()} == {'engagement.yaml', 'report.pdf'}


def test_real_pdf_api_queue_retains_location_after_two_child_boundaries(oversized, monkeypatch):
    import app as api
    from _support import auth_client
    monkeypatch.setattr(api, 'PROJECTS', oversized.parent)
    queue = ExportQueue(timeout=60)
    monkeypatch.setitem(api.app.extensions, 'export_queue', queue)
    source = oversized / 'engagement.yaml'
    try:
        client = auth_client(api.app)
        opened = client.get('/api/projects/project')
        # Opening a legacy fixture applies the application's normal migration.
        # The export itself must preserve this saved, revision-bound snapshot.
        before = source.read_bytes()
        created = client.post('/api/projects/project/jobs',
            json={'kind': 'export', 'formats': ['pdf'], 'label': 'Synthetic PDF diagnostic'},
            headers={'If-Match': opened.headers['ETag'], 'X-UI-Language': 'en'})
        assert created.status_code == 202, created.get_json()
        key = created.get_json()['id']
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            response = client.get('/api/jobs/' + key)
            value = response.get_json()
            if value['stage'] in {'done', 'error', 'cancelled'}:
                break
            time.sleep(.025)
        else:
            pytest.fail('PDF queue did not complete within its test deadline')
        assert value['stage'] == 'error', value
        assert value['diagnostics'][0]['location'] == LOCATION
        assert value['formats'] == ['pdf'] and not value['verification_available']
        assert response.headers['Cache-Control'] == 'no-store'
        assert client.get('/api/jobs/' + key + '/download').status_code == 422
        assert auth_client(api.app).get('/api/jobs/' + key).status_code == 404
        assert not list((queue.root / key).iterdir())
        assert source.read_bytes() == before
    finally:
        queue.close()


@pytest.mark.parametrize('payload', [b'invalid-json', b'null', b'{}', b'[]' + b' ' * (512 * 1024)],
                         ids=['invalid-json', 'null', 'wrong-shape', 'oversized'])
def test_damaged_or_oversized_private_sidecar_preserves_original_error(tmp_path, monkeypatch, payload):
    source = tmp_path / 'engagement.yaml'
    dump_yaml({'meta': {'report_title': 'Synthetic fallback'}, 'findings': []}, source)
    output = tmp_path / 'report.pdf'
    output.write_bytes(b'previous')
    def fail(command, **_options):
        assert '--private-diagnostics' in command
        destination = Path(command[command.index('-o') + 1])
        (destination.parent / 'engine-error.json').write_bytes(payload)
        raise subprocess.CalledProcessError(1, command, stderr='Original renderer failure')
    monkeypatch.setattr(pdf.subprocess, 'run', fail)
    with pytest.raises(ValueError) as caught:
        pdf.export_pdf(source, output)
    assert str(caught.value) == 'Original renderer failure'
    assert error_diagnostics(caught.value) == []
    assert output.read_bytes() == b'previous'
    assert {path.name for path in tmp_path.iterdir()} == {'engagement.yaml', 'report.pdf'}


def test_private_writer_cannot_overwrite_or_write_beside_public_output(tmp_path):
    error = table_error('F12')
    engine._write_private_diagnostics(tmp_path / 'report.pdf', error)
    assert not list(tmp_path.iterdir())
    directory = tmp_path / '.report-gen-pdf-owned'
    directory.mkdir()
    engine._write_private_diagnostics(directory / 'report.pdf', error)
    target = directory / 'engine-error.json'
    assert json.loads(target.read_text())[0]['location'] == LOCATION
    target.write_bytes(b'existing-private-file')
    engine._write_private_diagnostics(directory / 'report.pdf', error)
    assert target.read_bytes() == b'existing-private-file'


def test_missing_dom_id_does_not_become_a_fabricated_finding_locator():
    error = table_error('sin ID')
    assert 'sin ID' in str(error)
    assert error_diagnostics(error)[0]['location'] == {'operation': 'export', 'format': 'pdf'}
