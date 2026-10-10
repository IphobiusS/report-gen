"""Actual PDF pixels, private sessions, bounded inputs and truthful manual records."""
from hashlib import sha256
from io import BytesIO
import json
import zipfile

import pytest
from pypdf import PdfWriter

import app as api
import visual_review
from storage import revision
from wizard import dump_yaml
from _support import auth_client


def pdf(pages=2):
    stream = BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    writer.write(stream)
    return stream.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    directory = tmp_path / 'projects' / 'case'
    directory.mkdir(parents=True)
    dump_yaml({'meta': {'lang': 'es', 'theme': 'serio'}, 'findings': []}, directory / 'engagement.yaml')
    monkeypatch.setattr(api, 'PROJECTS', directory.parent)
    monkeypatch.setitem(api.app.extensions, 'visual_reviews_test', True)
    # Each test owns its local session and clears previous synthetic records.
    store = api.app.extensions['visual_reviews']
    with store.lock:
        store.records.clear()
    return auth_client(api.app), directory


def upload(client, raw=None, tag=None):
    c, directory = client
    return c.post('/api/projects/case/visual', data={'file': (BytesIO(pdf() if raw is None else raw), 'proof.pdf')},
                  headers={'If-Match': tag or '"' + revision(directory / 'engagement.yaml') + '"'})


def body(value, **extra):
    return dict(revision=value['revision'], pdf_sha256=value['pdf_sha256'], author='Synthetic reviewer',
                decision='accepted', pages=[], note='Manual review, not technical validation', **extra)


def test_real_pdf_metadata_and_pixels():
    if not visual_review.available():
        pytest.skip('optional PyMuPDF preview dependency not installed')
    raw = pdf()
    pages = visual_review.raster(raw)
    assert len(pages) == 2 and pages[0]['number'] == 1
    image = visual_review.raster(raw, 1)
    from PIL import Image
    with Image.open(BytesIO(image)) as actual:
        assert actual.format == 'PNG' and actual.size == (pages[0]['width'], pages[0]['height'])
        assert actual.convert('RGB').getpixel((10, 10)) == (255, 255, 255)


def test_upload_read_only_hash_and_real_page(client):
    c, directory = client
    before = (directory / 'engagement.yaml').read_bytes()
    result = upload(client)
    assert result.status_code == 200, result.json
    value = result.json
    assert value['origin'] == 'uploaded' and value['pdf_sha256'] == sha256(pdf()).hexdigest()
    assert value['original_word_verified'] is False and value['manually_verified'] is False
    assert len(value['pages']) == 2 and c.get(value['pages'][0]['image_url']).data.startswith(b'\x89PNG')
    assert (directory / 'engagement.yaml').read_bytes() == before
    assert list(directory.iterdir()) == [directory / 'engagement.yaml']


def test_manual_record_exact_hash_session_private_and_clear(client):
    c, _ = client
    value = upload(client).json
    route = '/api/visual/' + value['id']
    result = c.post(route + '/review', json=body(value))
    assert result.status_code == 200
    assert result.json['author_identity'] == 'local_self_declaration'
    assert result.json['automated_layout_verification'] is False
    assert json.loads(c.get(route + '/review/download').data)['pdf_sha256'] == value['pdf_sha256']
    other = auth_client(api.app)
    assert other.get(route).status_code == other.get(route + '/page/1').status_code == 404
    assert other.post(route + '/review', json=body(value)).status_code == 404
    assert c.delete(route, json={}).status_code == 200
    assert c.get(route).status_code == 404


@pytest.mark.parametrize('change', [
    {'pdf_sha256': '0' * 64}, {'revision': 'old'}, {'author': ''}, {'author': True},
    {'decision': 'automated_verified'}, {'pages': 'all'}, {'pages': [{'number': True, 'issue': 'other', 'note': 'x'}]},
    {'pages': [{'number': 3, 'issue': 'other', 'note': 'x'}]},
    {'pages': [{'number': 1, 'issue': 'other', 'note': 'x'}]},
    {'note': 'x' * 4001}, {'unknown': 'field'},
])
def test_review_rejects_mismatch_false_certification_and_invalid_inputs(client, change):
    c, _ = client
    value = upload(client).json
    selected = body(value)
    selected.update(change)
    assert c.post('/api/visual/' + value['id'] + '/review', json=selected).status_code == 422


def test_issue_record_and_unrecorded_download(client):
    c, _ = client
    value = upload(client).json
    route = '/api/visual/' + value['id']
    assert c.get(route + '/review/download').status_code == 404
    record = body(value)
    record.update(decision='issues', pages=[{'number': 2, 'issue': 'orphan_title', 'note': 'Synthetic annotation'}])
    assert c.post(route + '/review', json=record).status_code == 200
    assert c.get(route).json['review']['pages'][0]['number'] == 2


@pytest.mark.parametrize('raw', [b'', b'%PDF-broken', b'<html>fake</html>', b'%PDF-' + b'a' * visual_review.MAX_PDF])
def test_invalid_pdf_controlled(client, raw):
    response = upload(client, raw)
    assert response.status_code in (413, 422)


def test_csrf_origin_revision_and_type(client):
    c, _ = client
    assert c.post('/api/projects/case/visual', json={}).status_code == 415
    assert upload(client, tag='"stale"').status_code == 409
    assert c.post('/api/projects/case/visual', data={'file': (BytesIO(pdf()), 'x.pdf')}).status_code == 428
    assert c.post('/api/projects/case/visual', data={'file': (BytesIO(pdf()), 'x.pdf')},
                  headers={'Origin': 'https://other.example'}).status_code == 403
    unauthed = api.app.test_client()
    assert unauthed.post('/api/projects/case/visual', data={'file': (BytesIO(pdf()), 'x.pdf')}).status_code == 403


def test_zip_pdf_selection_is_exact_and_does_not_extract_paths():
    for count in (0, 2):
        stream = BytesIO()
        with zipfile.ZipFile(stream, 'w') as archive:
            for n in range(count):
                archive.writestr(f'../../outside{n}.pdf', pdf())
        with pytest.raises(ValueError):
            visual_review.extract_pdf(stream.getvalue(), 'package.zip')
    stream = BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('../../outside.pdf', pdf())
    with pytest.raises(ValueError):
        visual_review.extract_pdf(stream.getvalue(), 'package.zip')


def test_canonical_report_is_selected_without_confusing_pdf_attachments():
    raw, stream = pdf(2), BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('informe.pdf', raw)
        archive.writestr('attachments/politica.pdf', pdf(1))
    assert visual_review.extract_pdf(stream.getvalue(), 'delivery.zip') == raw


def test_identical_pdf_from_two_jobs_keeps_separate_context_and_review():
    store, raw = visual_review.Store(), pdf()
    first = store.add('owner', raw, 'same-revision', 'job-a.zip', 'generated', 'job-a')
    second = store.add('owner', raw, 'same-revision', 'job-b.zip', 'generated', 'job-b')
    assert first != second
    assert store.metadata('owner', second, '/view')['job_id'] == 'job-b'
    assert store.metadata('owner', second, '/view')['filename'] == 'job-b.zip'
    value = store.metadata('owner', first, '/view')
    store.review('owner', first, body(value))
    assert store.get('owner', second)['review'] is None


def test_generated_result_revision_exact_bytes(client, monkeypatch):
    c, _ = client
    raw = pdf()
    class Queue:
        def status(self, owner, key):
            if key != 'job':
                raise KeyError(key)
            return {'stage': 'done', 'revision': 'immutable-source-revision'}
        def result(self, owner, key):
            return raw, 'report.pdf'
    monkeypatch.setitem(api.app.extensions, 'export_queue', Queue())
    value = c.get('/api/jobs/job/visual').json
    assert value['origin'] == 'generated' and value['revision'] == 'immutable-source-revision'
    assert value['pdf_sha256'] == sha256(raw).hexdigest()
    assert c.get(value['pages'][1]['image_url']).status_code == 200
    assert c.post('/api/jobs/job/visual/review', json=body(value)).status_code == 200
    assert c.get('/api/jobs/missing/visual').status_code == 404


def test_store_expiry_limits_and_no_dependency(monkeypatch):
    store = visual_review.Store()
    monkeypatch.setattr(visual_review, 'raster', lambda payload, page=None: [{'number': 1, 'width': 100, 'height': 100}])
    for n in range(4):
        store.add('owner', b'%PDF-' + str(n).encode(), str(n), 'local.pdf', 'uploaded')
    with pytest.raises(ValueError):
        store.add('owner', b'%PDF-other', 'new', 'local.pdf', 'uploaded')
    for row in store.records.values():
        row['expires'] = 0
    key = store.add('owner', b'%PDF-new', 'new', 'local.pdf', 'uploaded')
    assert len(store.records) == 1 and store.get('owner', key)
    monkeypatch.setattr(visual_review, 'available', lambda: False)
    with pytest.raises(ValueError, match='previews'):
        # Restore raster to test the actual capability guard.
        monkeypatch.undo()
        monkeypatch.setattr(visual_review, 'available', lambda: False)
        visual_review.raster(pdf())
