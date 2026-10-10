"""Portable project organization, revision conflicts and private support projection."""
from copy import deepcopy
from io import BytesIO
import json
from types import SimpleNamespace
import zipfile

import pytest

import app
import engine
import experience_api
import project_history
import support_report
import validate
from _support import auth_client


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(app, 'PROJECTS', tmp_path)
    client = auth_client(app.app)
    assert client.post('/api/projects', json={'slug': 'alpha', 'title': 'Informe Águila', 'client': 'Cliente Norte'}).status_code == 200
    assert client.post('/api/projects', json={'slug': 'beta', 'title': 'Informe Beta', 'client': 'Cliente Sur'}).status_code == 200
    return client, tmp_path


def modify(client, slug, values, tag=None):
    tag = tag or client.get('/api/projects/' + slug).headers['ETag']
    return client.post('/api/projects/' + slug + '/management', json=values, headers={'If-Match': tag})


def test_archive_reactivate_preserves_findings_files_history_and_backup(workspace):
    client, root = workspace
    before = client.get('/api/projects/alpha').get_json()
    (root / 'alpha' / 'originals').mkdir()
    from PIL import Image
    Image.new('RGB', (16, 16), 'blue').save(root / 'alpha' / 'originals' / 'raw.png')
    original = (root / 'alpha' / 'originals' / 'raw.png').read_bytes()
    assert modify(client, 'alpha', {'archived': True, 'delivery_date': '2026-12-03'}).status_code == 200
    data = client.get('/api/projects/alpha').get_json()
    assert data.pop('project_management') == {'archived': True, 'delivery_date': '2026-12-03'}
    assert data == before
    assert (root / 'alpha' / 'originals' / 'raw.png').read_bytes() == original
    assert project_history.history(root / 'alpha')
    blob = project_history.export_bundle(root / 'alpha')
    with zipfile.ZipFile(BytesIO(blob)) as bundle:
        assert b'archived: true' in bundle.read('engagement.yaml')
        assert bundle.read('originals/raw.png') == original
    project_history.import_bundle(blob, root / 'restored')
    assert engine.load_engagement(root / 'restored' / 'engagement.yaml')['project_management']['archived'] is True
    assert modify(client, 'alpha', {'archived': False}).status_code == 200
    assert client.get('/api/projects/alpha').get_json()['project_management'] == {'archived': False, 'delivery_date': '2026-12-03'}
    rows = client.get('/api/projects').get_json()
    assert {row['slug'] for row in rows} == {'alpha', 'beta', 'restored'}


def test_catalog_reads_summaries_without_rewriting_and_ignores_closed_deadlines(workspace):
    client, root = workspace
    data = client.get('/api/projects/alpha').get_json()
    data['findings'] = [dict(id='F1', title='Retest', status='reported_fixed', due_date='2026-11-20'),
                        dict(id='F2', title='Closed', status='verified_fixed', due_date='2026-01-01')]
    assert client.put('/api/projects/alpha', json=data).status_code == 200
    assert modify(client, 'alpha', {'delivery_date': '2026-11-25'}).status_code == 200
    before = {str(path): path.read_bytes() for path in root.rglob('*') if path.is_file()}
    response = client.get('/api/projects')
    row = next(item for item in response.json if item['slug'] == 'alpha')
    assert row['client'] == 'Cliente Norte' and row['title'] == 'Informe Águila'
    assert row['pending_retests'] == 1 and row['finding_count'] == 2
    assert row['next_due_date'] == '2026-11-20' and row['delivery_date'] == '2026-11-25'
    assert row['modified_at'].endswith('+00:00') and len(row['revision']) == 64
    assert {str(path): path.read_bytes() for path in root.rglob('*') if path.is_file()} == before


@pytest.mark.parametrize('value', [{'archived': 'false'}, {'archived': 1}, {'delivery_date': '2026-02-30'},
                                  {'delivery_date': '20260101'}, {'delivery_date': None}, {'client': 'replace'}, {}, []])
def test_management_rejects_invalid_metadata_without_mutation(workspace, value):
    client, root = workspace
    source = root / 'alpha' / 'engagement.yaml'
    before = source.read_bytes()
    assert modify(client, 'alpha', value).status_code in (400, 422)
    assert source.read_bytes() == before


def test_management_revision_and_csrf_guard(workspace):
    client, root = workspace
    old = client.get('/api/projects/alpha').headers['ETag']
    assert modify(client, 'alpha', {'delivery_date': '2026-12-20'}).status_code == 200
    assert modify(client, 'alpha', {'archived': True}, old).status_code == 409
    response = client.post('/api/projects/alpha/management', json={'archived': True})
    assert response.status_code == 428
    unauth = app.app.test_client()
    assert unauth.post('/api/projects/alpha/management', json={'archived': True}, headers={'If-Match': old}).status_code == 403
    assert client.get('/api/projects/alpha').get_json()['project_management'] == {'delivery_date': '2026-12-20'}


def test_bad_entries_remain_visible_but_symlink_is_not_followed(workspace):
    client, root = workspace
    (root / 'alpha' / 'engagement.yaml').write_text('not: [valid')
    (root / 'shadow').symlink_to(root / 'beta', target_is_directory=True)
    rows = client.get('/api/projects').json
    assert len(rows) == 2 and next(row for row in rows if row['slug'] == 'alpha')['available'] is False


def test_bad_metadata_also_rejected_by_normal_save(workspace):
    client, root = workspace
    data = client.get('/api/projects/alpha').json
    data['project_management'] = {'archived': 'yes'}
    assert client.put('/api/projects/alpha', json=data).status_code == 422
    assert any(level == 'error' for level, _ in validate.validate(data))


def diagnostic_fixture():
    return {'checks': [{'id': key, 'ready': key != 'chromium', 'label': 'PRIVATE USER', 'detail': '/secret/path client-secret hostname-secret'} for key in ('weasyprint', 'chromium', 'docx')],
            'pdf_ready': True, 'note': 'PRIVATE NOTE', 'project': 'SECRET PROJECT'}


def test_support_projection_drops_all_arbitrary_content(monkeypatch):
    report = diagnostic_fixture()
    before = deepcopy(report)
    monkeypatch.setattr(support_report.platform, 'system', lambda: 'PRIVATE HOSTNAME')
    public = support_report.project(report)
    text = support_report.encode(public).decode()
    assert report == before
    assert public['system'] == 'Other'
    assert public['synthetic_exports'] == {'weasyprint': 'passed', 'chromium': 'failed', 'docx': 'passed'}
    assert public['workspace_write'] == 'not_checked'
    assert all(marker not in text for marker in ('PRIVATE', 'SECRET', 'client-secret', 'hostname-secret', '/secret'))
    assert set(public) == {'schema', 'application', 'version', 'system', 'python', 'synthetic_exports', 'workspace_write'}


def test_download_is_exact_signed_preview_and_rejects_new_fields(workspace, monkeypatch):
    client, root = workspace
    monkeypatch.setattr(experience_api.subprocess, 'run', lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=json.dumps(diagnostic_fixture())))
    response = client.post('/api/diagnostics', json={'lang': 'es'})
    assert response.status_code == 200
    preview = response.json
    body = {'report': preview['support_report'], 'preview_token': preview['support_token']}
    download = client.post('/api/diagnostics/download', json=body)
    assert download.status_code == 200
    assert download.data == support_report.encode(body['report'])
    assert 'attachment' in download.headers['Content-Disposition']
    assert b'PRIVATE' not in download.data and b'SECRET' not in download.data
    forged = deepcopy(body); forged['report']['client'] = 'Secret'
    assert client.post('/api/diagnostics/download', json=forged).status_code == 409
    forged = deepcopy(body); forged['report']['synthetic_exports']['chromium'] = 'passed'
    assert client.post('/api/diagnostics/download', json=forged).status_code == 409
    assert client.post('/api/diagnostics/download', json={'report': body['report'], 'preview_token': ''}).status_code == 409
