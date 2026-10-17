"""Exact-byte resume, private-by-default retention and coherent reversible history."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO

import pytest
from pypdf import PdfReader, PdfWriter

import app as api
import attachments
import engine
import project_history
import visual_review
from storage import atomic_write, revision
from wizard import dump_yaml
from _support import auth_client


def pdf(pages=2):
    output = BytesIO()
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=612, height=792)
    writer.write(output)
    return output.getvalue()


@pytest.fixture
def case(tmp_path, monkeypatch):
    directory = tmp_path / 'projects' / 'case'
    directory.mkdir(parents=True)
    dump_yaml({'meta': {'lang': 'es', 'theme': 'serio'}, 'findings': []}, directory / 'engagement.yaml')
    monkeypatch.setattr(api, 'PROJECTS', directory.parent)
    store = api.app.extensions['visual_reviews']
    with store.lock:
        store.records.clear()
    # Raster isolation is exercised by test_visual_review_0230; this suite
    # focuses on durable byte identity, transactions and imported records.
    monkeypatch.setattr(visual_review, 'raster', lambda raw, page=None: [
        dict(number=index + 1, width=612, height=792) for index, _ in enumerate(PdfReader(BytesIO(raw)).pages)])
    return auth_client(api.app), directory, store


def etag(directory):
    return {'If-Match': '"' + revision(directory / 'engagement.yaml') + '"'}


def upload(case, raw=None):
    client, directory, _ = case
    result = client.post('/api/projects/case/visual', data={'file': (BytesIO(raw or pdf()), 'original.pdf')}, headers=etag(directory))
    assert result.status_code == 200, result.json
    return result.json


def progress():
    return dict(page=2, author='Revisor de prueba', decision='pending', note='Nota privada',
                pages=[dict(number=1, issue='other', note='Pendiente sintético', resolved=False)],
                draft=dict(number=2, issue='table_cut', note='Observación sin terminar'))


def save(case, visual, *, keep=False, uid=None, value=None, headers=None):
    client, directory, _ = case
    return client.post('/api/projects/case/visual-reviews', json=dict(visual_id=visual['id'], uid=uid,
                       progress=value or progress(), keep_pdf=keep), headers=headers or etag(directory))


def reopen(case, uid, visual_id=None):
    client, directory, _ = case
    return client.post('/api/projects/case/visual-reviews/' + uid + '/open',
                       json={'visual_id': visual_id}, headers=etag(directory))


def test_metadata_only_opt_in_read_only_until_save_and_default_exclusion(case, tmp_path):
    client, directory, _ = case
    before = (directory / 'engagement.yaml').read_bytes()
    visual = upload(case)
    assert client.get('/api/projects/case/visual-reviews').json['records'] == []
    assert (directory / 'engagement.yaml').read_bytes() == before
    result = save(case, visual)
    assert result.status_code == 201, result.json
    record = result.json['record']
    assert record['progress'] == progress() and record['pdf_attachment_uid'] is None
    assert record['revision'] == visual['revision'] and record['pdf_sha256'] == sha256(pdf()).hexdigest()
    assert record['author_identity'] == 'local_self_declaration'
    assert record['original_word_verified'] is record['automated_layout_verification'] is False
    data = engine.load_engagement(directory / 'engagement.yaml')
    assert len(data['attachments']) == 1
    assert data['attachments'][0]['include'] is data['attachments'][0]['reviewed'] is False
    assert attachments.capture(data, directory, tmp_path / 'out') == {}
    assert list((directory / 'attachments').glob('*.pdf')) == []
    assert reopen(case, record['uid']).status_code == 422
    reopened = reopen(case, record['uid'], visual['id'])
    assert reopened.status_code == 200, reopened.json
    assert reopened.json['saved'] == record and reopened.json['manually_verified'] is False


def test_private_copy_survives_new_session_and_expired_preview(case):
    client, directory, store = case
    visual = upload(case)
    record = save(case, visual, keep=True).json['record']
    with store.lock:
        store.records.clear()
    fresh = auth_client(api.app)
    result = reopen((fresh, directory, store), record['uid'])
    assert result.status_code == 200, result.json
    assert result.json['pdf_sha256'] == visual['pdf_sha256']
    assert result.json['saved']['progress']['page'] == 2
    assert result.json['revision'] == visual['revision'] != revision(directory / 'engagement.yaml')
    assert client.get('/api/visual/' + result.json['id']).status_code == 404


def test_original_reopen_requires_exact_bytes_not_name_or_current_revision(case):
    visual = upload(case)
    record = save(case, visual).json['record']
    other = upload(case, pdf(1))
    assert reopen(case, record['uid'], other['id']).status_code == 409
    same = upload(case)
    assert same['revision'] != record['revision']
    response = reopen(case, record['uid'], same['id'])
    assert response.status_code == 200
    assert response.json['revision'] == record['revision']
    assert response.json['saved']['progress'] == record['progress']


def test_update_history_restore_backup_preserve_coherent_old_and_new_bytes(case):
    _, directory, _ = case
    visual = upload(case)
    first = save(case, visual, keep=True).json['record']
    sid = project_history.history(directory)[0]['id']
    edited = progress(); edited['page'] = 1; edited['note'] = 'Nota posterior'
    second = save(case, visual, keep=False, uid=first['uid'], value=edited)
    assert second.status_code == 200, second.json
    assert second.json['record']['pdf_attachment_uid'] is None
    assert list((directory / 'attachments').glob('*.pdf')) == []
    # Export/import carries metadata and historical PDF, not just the active YAML.
    imported = directory.parent / 'restored'
    project_history.import_bundle(project_history.export_bundle(directory), imported)
    active = visual_review.saved_records(engine.load_engagement(imported / 'engagement.yaml'), imported)
    assert active[0]['progress']['note'] == 'Nota posterior'
    project_history.restore(imported, sid)
    data = engine.load_engagement(imported / 'engagement.yaml')
    restored = visual_review.saved_records(data, imported)[0]
    assert restored == first
    assert visual_review.saved_pdf(data, imported, restored) == pdf()


def test_delete_current_state_keeps_recoverable_history_and_no_delivery(case):
    client, directory, _ = case
    visual = upload(case)
    record = save(case, visual, keep=True).json['record']
    sid = project_history.history(directory)[0]['id']
    result = client.delete('/api/projects/case/visual-reviews/' + record['uid'], json={}, headers=etag(directory))
    assert result.status_code == 200, result.json
    assert result.json['records'] == [] and result.json['data']['attachments'] == []
    assert list((directory / 'attachments').iterdir()) == []
    project_history.restore(directory, sid)
    assert visual_review.saved_records(engine.load_engagement(directory / 'engagement.yaml'), directory)[0] == record


def test_revision_csrf_owner_and_expiry_reject_without_writes(case):
    client, directory, store = case
    visual = upload(case)
    before = (directory / 'engagement.yaml').read_bytes()
    assert save(case, visual, headers={'If-Match': '"old"'}).status_code == 409
    other = auth_client(api.app)
    assert save((other, directory, store), visual).status_code == 404
    assert save((api.app.test_client(), directory, store), visual).status_code == 403
    with store.lock:
        store.records[visual['id']]['expires'] = 0
    assert save(case, visual).status_code == 404
    assert (directory / 'engagement.yaml').read_bytes() == before


@pytest.mark.parametrize('change', [
    {'page': True}, {'page': 0}, {'page': 3}, {'author': 'x' * 121}, {'author': '\x00'},
    {'decision': 'certified'}, {'pages': [{'number': 1, 'issue': 'other', 'note': 'x', 'resolved': 1}]},
    {'draft': {'number': 1, 'issue': 'unknown', 'note': ''}}, {'note': 'x' * 4001},
    {'decision': 'accepted'}, {'extra': True},
])
def test_invalid_or_false_acceptance_progress_is_rejected(case, change):
    visual = upload(case)
    value = progress(); value.update(change)
    assert save(case, visual, value=value).status_code == 422


def test_resolved_issues_allow_explicit_acceptance_but_never_certify_identity(case):
    visual = upload(case)
    value = progress(); value['decision'] = 'accepted'; value['pages'][0]['resolved'] = True; value['draft']['note'] = ''
    result = save(case, visual, value=value)
    assert result.status_code == 201
    assert result.json['record']['author_identity'] == 'local_self_declaration'


def test_tampered_copy_metadata_and_path_are_not_resumable(case):
    client, directory, _ = case
    visual = upload(case)
    record = save(case, visual, keep=True).json['record']
    data = engine.load_engagement(directory / 'engagement.yaml')
    row = next(row for row in data['attachments'] if row['uid'] == record['pdf_attachment_uid'])
    atomic_write(directory / row['member'], pdf(1))
    assert reopen(case, record['uid']).status_code == 422
    # An attachment with a review-like name and arbitrary JSON is not listed.
    review_row = next(row for row in data['attachments'] if row['uid'] == record['uid'])
    broken = deepcopy(record); broken['pdf_attachment_uid'] = '../../outside'
    raw = visual_review.dumps(broken)
    atomic_write(directory / review_row['member'], raw)
    review_row['sha256'] = sha256(raw).hexdigest()
    dump_yaml(data, directory / 'engagement.yaml')
    assert client.get('/api/projects/case/visual-reviews').json['records'] == []
    assert reopen(case, record['uid']).status_code == 422


def test_symlinked_copy_is_rejected(case, tmp_path):
    _, directory, _ = case
    visual = upload(case)
    record = save(case, visual, keep=True).json['record']
    data = engine.load_engagement(directory / 'engagement.yaml')
    row = next(row for row in data['attachments'] if row['uid'] == record['pdf_attachment_uid'])
    target = tmp_path / 'external.pdf'; target.write_bytes(pdf())
    path = directory / row['member']; path.unlink()
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip('symlinks unavailable')
    assert reopen(case, record['uid']).status_code == 422


def test_metadata_size_and_attachment_quota_are_bounded(case, monkeypatch):
    visual = upload(case)
    value = progress(); value['pages'] *= 500
    for row in value['pages']:
        row['note'] = 'x' * 4000
    assert save(case, visual, value=value).status_code == 422
    monkeypatch.setattr(attachments, 'MAX_TOTAL', len(pdf()) - 1)
    assert save(case, visual, keep=True).status_code == 422


def test_atomic_write_failure_keeps_old_progress_and_pdf(case, monkeypatch):
    _, directory, _ = case
    visual = upload(case)
    first = save(case, visual, keep=True).json['record']
    before = (directory / 'engagement.yaml').read_bytes()
    import visual_api
    original = visual_api.atomic_write
    def fail(path, data):
        if path.suffix == '.json' and path.parent.name == 'attachments':
            raise OSError(28, 'synthetic disk full')
        return original(path, data)
    monkeypatch.setattr(visual_api, 'atomic_write', fail)
    result = save(case, visual, uid=first['uid'])
    assert result.status_code == 503
    assert (directory / 'engagement.yaml').read_bytes() == before
    data = engine.load_engagement(directory / 'engagement.yaml')
    assert visual_review.saved_records(data, directory) == [first]
    assert visual_review.saved_pdf(data, directory, first) == pdf()


def test_saving_shared_preview_does_not_cross_contaminate_project_progress(case):
    client, directory, store = case
    visual = upload(case)
    first = save(case, visual, keep=True).json['record']
    # Importing a backup deliberately preserves the review UID in a second project.
    other = directory.parent / 'other'
    project_history.import_bundle(project_history.export_bundle(directory), other)
    one = reopen(case, first['uid']).json
    two = client.post('/api/projects/other/visual-reviews/' + first['uid'] + '/open',
                      json={'visual_id': None}, headers=etag(other)).json
    assert one['id'] != two['id']
    assert store.get(client.get('/api/session').json['csrf'], visual['id']).get('saved') is None
    # A project-owned resumed view cannot update the same imported UID elsewhere.
    response = client.post('/api/projects/other/visual-reviews',
                           json=dict(visual_id=one['id'], uid=first['uid'], progress=progress(), keep_pdf=True),
                           headers=etag(other))
    assert response.status_code == 409
    assert client.get('/api/visual/' + one['id']).json['saved'] == first


def test_remove_copy_preserves_another_declared_attachment_alias(case):
    _, directory, _ = case
    visual = upload(case)
    first = save(case, visual, keep=True).json['record']
    data = engine.load_engagement(directory / 'engagement.yaml')
    row = next(row for row in data['attachments'] if row['uid'] == first['pdf_attachment_uid'])
    from uuid import uuid4
    alias = dict(row, uid=str(uuid4()), name='separate-explicit-attachment.pdf')
    data['attachments'].append(alias)
    project_history.save(directory, data)
    result = save(case, visual, uid=first['uid'], keep=False)
    assert result.status_code == 200, result.json
    assert attachments.read(directory, alias) == pdf()


def test_uid_collision_never_overwrites_unrelated_file(case, monkeypatch):
    _, directory, _ = case
    visual = upload(case)
    import visual_api
    import uuid
    fixed = uuid.uuid4()
    member = 'attachments/' + fixed.hex + '.json'
    atomic_write(directory / member, b'{"unrelated":true}')
    monkeypatch.setattr(visual_api.uuid, 'uuid4', lambda: fixed)
    assert save(case, visual).status_code == 409
    assert (directory / member).read_bytes() == b'{"unrelated":true}'


def test_saved_review_count_limit_does_not_block_updating_existing(case, monkeypatch):
    visual = upload(case)
    first = save(case, visual).json['record']
    monkeypatch.setattr(visual_review, 'MAX_SAVED', 1)
    assert save(case, visual).status_code == 422
    assert save(case, visual, uid=first['uid']).status_code == 200
