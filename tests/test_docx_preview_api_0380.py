"""HTTP ownership, immutable queue provenance and explicit preview lifecycle."""
from hashlib import sha256
from io import BytesIO
import json
import threading
import zipfile

import pytest

import app as api
import docx_preview
from _support import auth_client
from test_docx_preview_0380 import docx, pdf, verified


class Queue:
    def __init__(self, owner, raw, name='synthetic.docx'):
        self.owner, self.raw, self.name = owner, raw, name
        self.lock = threading.RLock()
        self.stage, self.revision = 'done', 'frozen-source-revision'
        self.record = verified(raw, name, self.revision)

    def status(self, owner, key):
        if owner != self.owner or key != 'own-job':
            raise KeyError(key)
        return dict(id=key, stage=self.stage, revision=self.revision)

    def result(self, owner, key):
        self.status(owner, key)
        return self.raw, self.name

    def verification(self, owner, key):
        self.status(owner, key)
        return self.record


@pytest.fixture
def setup(monkeypatch):
    client = auth_client(api.app)
    with client.session_transaction() as session:
        owner = session['csrf']
    queue = Queue(owner, docx())
    store = docx_preview.Store()
    monkeypatch.setitem(api.app.extensions, 'export_queue', queue)
    monkeypatch.setitem(api.app.extensions, 'docx_previews', store)
    yield client, queue, store
    store.close()


def test_no_client_paths_options_or_unowned_exports(setup):
    client, queue, store = setup
    for body in ({'path': '/tmp/arbitrary.docx'}, {'executable': '/bin/sh'}, {'bytes': 'AAAA'}):
        assert client.post('/api/jobs/own-job/docx-preview', json=body).status_code == 422
    assert client.post('/api/jobs/own-job/docx-preview', data=b'raw').status_code == 415
    other = auth_client(api.app)
    assert other.post('/api/jobs/own-job/docx-preview', json={}).status_code == 404
    assert not store.records


def test_incomplete_or_changed_job_never_starts(setup):
    client, queue, store = setup
    queue.stage = 'rendering_docx'
    assert client.post('/api/jobs/own-job/docx-preview', json={}).status_code == 409
    queue.stage = 'done'
    queue.record['files'][queue.name]['sha256'] = '0' * 64
    assert client.post('/api/jobs/own-job/docx-preview', json={}).status_code == 422
    assert not store.records


@pytest.mark.parametrize('language,word', [('es', 'Instala'), ('en', 'Install'), ('pt', 'Instale')])
def test_unavailable_message_is_actionable_in_three_languages(setup, monkeypatch, language, word):
    client, _queue, _store = setup
    monkeypatch.setattr(docx_preview, 'executable', lambda: None)
    headers = {'X-UI-Language': language}
    capability = client.get('/api/docx-preview/capabilities', headers=headers).get_json()
    assert capability['available'] is False and word in capability['unavailable_message']
    response = client.post('/api/jobs/own-job/docx-preview', json={}, headers=headers)
    assert response.status_code == 422 and word in response.get_json()['error']


def test_native_snapshot_and_receipt_are_separate_from_export_and_project(setup, monkeypatch):
    client, queue, store = setup
    started = []
    def start(owner, raw, revision, job_id):
        started.append((owner, raw, revision, job_id))
        return dict(id='preview-id', stage='rendering', revision=revision, job_id=job_id,
                    source_docx_sha256=sha256(raw).hexdigest())
    monkeypatch.setattr(store, 'start', start)
    response = client.post('/api/jobs/own-job/docx-preview', json={})
    assert response.status_code == 202
    assert started == [(queue.owner, queue.raw, queue.revision, 'own-job')]
    assert response.get_json()['revision'] == queue.revision
    assert response.headers['Cache-Control'] == 'no-store'


def test_source_job_can_disappear_after_freeze_without_substitution(setup, monkeypatch):
    client, queue, store = setup
    raw, revision = queue.raw, queue.revision
    captured = []
    def start(owner, document, identity, job_id):
        # Simulate removal/replacement of the export once the locked capture is
        # complete. The derivative already owns its verified immutable bytes.
        queue.raw, queue.revision = b'replacement must not be read', 'different'
        monkeypatch.delitem(api.app.extensions, 'export_queue')
        captured.append((document, identity))
        return {'id': 'frozen', 'stage': 'rendering', 'source_docx_sha256': sha256(document).hexdigest()}
    monkeypatch.setattr(store, 'start', start)
    response = client.post('/api/jobs/own-job/docx-preview', json={})
    assert response.status_code == 202 and captured == [(raw, revision)]
    assert response.get_json()['source_docx_sha256'] == sha256(raw).hexdigest()


def test_workspace_mismatch_blocks_preview_even_for_local_owner(setup):
    client, _queue, store = setup
    response = client.post('/api/jobs/own-job/docx-preview', json={},
                           headers={'X-Report-Gen-Workspace': 'stale-workspace'})
    assert response.status_code == 409 and not store.records


def test_delivery_selects_only_verified_root_docx(setup, monkeypatch):
    client, queue, store = setup
    raw = queue.raw
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('informe.docx', raw)
        archive.writestr('attachments/untrusted.docx', b'untrusted')
    queue.raw, queue.name = stream.getvalue(), 'delivery.zip'
    queue.record = verified(raw, 'informe.docx', queue.revision)
    seen = []
    monkeypatch.setattr(store, 'start', lambda owner, payload, revision, job_id: seen.append(payload) or {'id': 'native', 'stage': 'rendering'})
    assert client.post('/api/jobs/own-job/docx-preview', json={}).status_code == 202
    assert seen == [raw]


def test_completed_derivative_access_is_session_private_and_discardable(setup):
    client, queue, store = setup
    key = 'preview-id'
    directory = store.root / key
    directory.mkdir()
    raw = pdf()
    (directory / 'preview.pdf').write_bytes(raw)
    receipt = {'engine': {'name': 'LibreOffice', 'version': 'Synthetic test renderer'},
               'source_revision': queue.revision, 'source_docx_sha256': sha256(queue.raw).hexdigest(),
               'pdf_sha256': sha256(raw).hexdigest(), 'pages': 2, 'word_verified': False}
    # Completed synthetic record exercises transport only; real conversion is
    # separately covered by the optional engine test, never attributed here.
    store.records[key] = dict(id=key, root=directory, owner=queue.owner, stage='done', revision=queue.revision,
                             job_id='own-job', source_docx_sha256=receipt['source_docx_sha256'], error_code=None,
                             receipt=receipt, expires=float('inf'), cancel=threading.Event(),
                             thread=threading.Thread())
    other = auth_client(api.app)
    for suffix in ('', '/pdf', '/receipt'):
        assert other.get('/api/docx-preview/' + key + suffix).status_code == 404
    assert other.post('/api/docx-preview/' + key + '/cancel', json={}).status_code == 404
    assert other.delete('/api/docx-preview/' + key, json={}).status_code == 404
    value = client.get('/api/docx-preview/' + key).get_json()
    assert value['receipt'] == receipt
    response = client.get('/api/docx-preview/' + key + '/pdf')
    assert response.data == raw and response.mimetype == 'application/pdf'
    assert json.loads(client.get('/api/docx-preview/' + key + '/receipt').data) == receipt
    assert client.delete('/api/docx-preview/' + key, json={}).status_code == 200
    assert not directory.exists() and not store.records


def test_create_and_cancel_require_csrf(setup):
    _client, _queue, _store = setup
    unauthenticated = api.app.test_client()
    for path in ('/api/jobs/own-job/docx-preview', '/api/docx-preview/preview-id/cancel'):
        assert unauthenticated.post(path, json={}).status_code == 403
