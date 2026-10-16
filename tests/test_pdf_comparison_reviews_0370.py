"""Optional receipts: session binding, private transactions and portable recovery."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import uuid

from pypdf import PdfWriter
import pytest

import app as api
import attachments
import engine
import pdf_compare
import pdf_comparison_reviews as reviews
import project_history
from storage import revision
from wizard import dump_yaml
from _support import auth_client


ROUTE = '/api/projects/case/pdf-comparisons'


def pdf(pages=1):
    stream, writer = BytesIO(), PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=120, height=140)
    writer.add_metadata({'/Title': 'PRIVATE_PDF_TITLE_NOT_A_REVIEW_FIELD'})
    writer.write(stream)
    return stream.getvalue()


@pytest.fixture(scope='module')
def comparison():
    return pdf_compare.compare(pdf(), pdf(2), 'en')


@pytest.fixture
def local(tmp_path, monkeypatch):
    directory = tmp_path / 'projects' / 'case'
    directory.mkdir(parents=True)
    dump_yaml({'meta': {'lang': 'es', 'theme': 'serio', 'report_title': 'Preserve authored content'},
               'findings': []}, directory / 'engagement.yaml')
    monkeypatch.setattr(api, 'PROJECTS', directory.parent)
    monkeypatch.setitem(api.app.config, 'LIBRARY_PATH', str(tmp_path / 'findings.json'))
    monkeypatch.setitem(api.app.config, 'DESIGN_LIBRARY_PATH', str(tmp_path / 'designs.json'))
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    store = reviews.ReceiptStore()
    monkeypatch.setitem(api.app.extensions, 'pdf_comparison_receipts', store)
    return auth_client(api.app), directory, store


def owner(client):
    with client.session_transaction() as session:
        return session['csrf']


def payload(key, **changes):
    return dict(comparison_id=key, author='Reviewer / revisão / revisión', decision='accepted', note='', **changes)


def save(local, key, *, body=None, headers=None):
    client, directory, _ = local
    return client.post(ROUTE, json=payload(key) if body is None else body,
                       headers={'If-Match': revision(directory / 'engagement.yaml'), **(headers or {})})


def tree(directory):
    return {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob('*') if path.is_file()}


def test_store_keeps_only_bounded_metadata_and_independent_copies(comparison):
    store = reviews.ReceiptStore()
    key = store.add('session-a', comparison)
    receipt = store.get('session-a', key)
    assert receipt['html_sha256'] == sha256(comparison).hexdigest()
    assert receipt['manifest']['before_sha256'] == sha256(pdf()).hexdigest()
    assert receipt['manifest']['after_pages'] == 2
    assert receipt['manifest']['page_pairs'] == [{'before_page': 1, 'after_page': 1}, {'before_page': None, 'after_page': 2}]
    encoded = reviews.dumps(store._records)
    assert len(encoded) < reviews.MAX_METADATA
    assert all(marker not in encoded for marker in (b'%PDF-', b'<html', b'data:image', b'PRIVATE_PDF_TITLE'))
    receipt['manifest']['summary']['added'] = 75
    assert store.get('session-a', key)['manifest']['summary']['added'] == 1
    with pytest.raises(KeyError):
        store.get('session-b', key)
    assert store.discard('session-b', key) is False
    assert store.discard('session-a', key) is True
    assert store.discard('session-a', key) is False


def test_store_rotates_oldest_same_owner_and_expires_without_disk(comparison):
    tick = [100.0]
    store = reviews.ReceiptStore(clock=lambda: tick[0])
    other = store.add('other', comparison)
    keys = [store.add('mine', comparison) for _ in range(reviews.MAX_OWNER)]
    new = store.add('mine', comparison)
    with pytest.raises(KeyError):
        store.get('mine', keys[0])
    assert store.get('other', other)
    assert store.get('mine', keys[-1]) and store.get('mine', new)
    tick[0] += reviews.TTL
    with pytest.raises(KeyError):
        store.get('mine', new)
    assert store._records == {}


def test_global_quota_does_not_evict_other_sessions_and_recovers_after_discard(comparison):
    store = reviews.ReceiptStore()
    keys = [store.add(str(index), comparison) for index in range(reviews.MAX_RECEIPTS)]
    with pytest.raises(reviews.ReceiptLimitError):
        store.add('new owner', comparison)
    assert len(store._records) == reviews.MAX_RECEIPTS
    assert store.get('0', keys[0])
    store.discard('0', keys[0])
    assert store.get('new owner', store.add('new owner', comparison))


def test_concurrent_additions_respect_owner_limit_and_never_share_ids(comparison):
    store = reviews.ReceiptStore()
    with ThreadPoolExecutor(max_workers=6) as executor:
        keys = list(executor.map(lambda _: store.add('one', comparison), range(20)))
    assert len(set(keys)) == 20 and len(store._records) == reviews.MAX_OWNER
    assert all(item['owner'] == 'one' for item in store._records.values())


def test_metadata_cap_rejects_without_retention(comparison, monkeypatch):
    store = reviews.ReceiptStore()
    monkeypatch.setattr(reviews, 'MAX_METADATA', 32)
    with pytest.raises(reviews.ReceiptLimitError):
        store.add('one', comparison)
    assert not store._records


def test_real_api_comparison_receipt_is_optional_read_only_and_hash_bound(local):
    client, directory, store = local
    before = tree(directory)
    response = client.post('/api/pdf-compare', data={'before': (BytesIO(pdf()), 'secret-before.pdf'),
                                                   'after': (BytesIO(pdf(2)), 'secret-after.pdf')})
    assert response.status_code == 200
    key = response.headers['X-Report-Gen-Comparison-Id']
    metadata = client.get('/api/pdf-compare/receipts/' + key)
    assert metadata.status_code == 200 and metadata.json['html_sha256'] == sha256(response.data).hexdigest()
    assert metadata.headers['Cache-Control'] == 'no-store'
    assert tree(directory) == before and len(store._records) == 1
    assert b'secret-before' not in metadata.data and b'secret-after' not in metadata.data


def test_saved_review_is_private_preserves_project_and_downloads_exact_hash(local, comparison):
    client, directory, store = local
    key = store.add(owner(client), comparison)
    old_tag = revision(directory / 'engagement.yaml')
    response = save(local, key)
    assert response.status_code == 201, response.json
    record, data = response.json['record'], response.json['data']
    assert data['meta']['report_title'] == 'Preserve authored content'
    assert response.headers['ETag'].strip('"') != old_tag
    assert record['schema'] == reviews.SCHEMA and record['author_identity'] == 'local_self_declaration'
    assert record['semantic_equivalence_verified'] is False and record['original_word_verified'] is False
    assert record['html_sha256'] == sha256(comparison).hexdigest()
    row = data['attachments'][0]
    assert row['include'] is row['reviewed'] is row['required'] is False
    assert row['member'] == 'attachments/' + uuid.UUID(record['uid']).hex + '.json'
    assert row['name'] == 'pdf-comparison-review-' + record['uid'] + '.json'
    raw = (directory / row['member']).read_bytes()
    assert sha256(raw).hexdigest() == row['sha256'] and json.loads(raw) == record
    listing = client.get(ROUTE)
    assert listing.json == {'records': [record]} and listing.headers['ETag'] == response.headers['ETag']
    downloaded = client.get(ROUTE + '/' + record['uid'])
    assert downloaded.status_code == 200 and downloaded.data == raw
    assert downloaded.mimetype == 'application/json' and row['name'] in downloaded.headers['Content-Disposition']
    assert attachments.capture(data, directory, directory / 'delivery') == {}
    assert store.get(owner(client), key), 'saving a durable record does not discard the temporary comparison'


def test_manual_pair_order_and_add_remove_summary_are_retained(local):
    client, _, store = local
    output = pdf_compare.compare(pdf(2), pdf(2), 'en',
                                 [{'before': 2, 'after': 1}, {'before': 1, 'after': None}, {'before': None, 'after': 2}])
    response = save(local, store.add(owner(client), output))
    assert response.status_code == 201, response.json
    record = response.json['record']
    assert record['pairing_mode'] == 'manual'
    assert record['page_pairs'] == [{'before_page': 2, 'after_page': 1}, {'before_page': 1, 'after_page': None},
                                    {'before_page': None, 'after_page': 2}]
    assert record['summary']['added'] == record['summary']['removed'] == record['summary']['unchanged'] == 1


@pytest.mark.parametrize('identity', ['cross_session', 'forged', 'wrong_type', 'expired'])
def test_foreign_forged_and_expired_receipts_cannot_write(local, comparison, identity):
    client, directory, store = local
    key = store.add('foreign' if identity == 'cross_session' else owner(client), comparison)
    if identity == 'forged':
        key = 'x' * 43
    elif identity == 'wrong_type':
        key = {'arbitrary': 'json'}
    elif identity == 'expired':
        store._records[key]['deadline'] = -1
    before = tree(directory)
    response = save(local, key)
    assert response.status_code == 404, response.json
    assert tree(directory) == before


def test_receipt_get_and_delete_enforce_session_and_csrf(local, comparison):
    client, _, store = local
    key = store.add(owner(client), comparison)
    path = '/api/pdf-compare/receipts/' + key
    other = auth_client(api.app)
    assert other.get(path).status_code == 404
    assert other.delete(path).status_code == 404
    assert client.delete(path, headers={'X-CSRF-Token': 'forged'}).status_code == 403
    assert client.get(path).status_code == 200
    assert client.delete(path).status_code == 204
    assert client.get(path).status_code == 404
    assert api.app.test_client().get(path).status_code == 403


@pytest.mark.parametrize('tag,status', [(None, 428), ('stale-revision', 409)])
def test_save_requires_current_project_revision_without_losing_receipt(local, comparison, tag, status):
    client, directory, store = local
    key = store.add(owner(client), comparison)
    before = tree(directory)
    response = client.post(ROUTE, json=payload(key), headers={} if tag is None else {'If-Match': tag})
    assert response.status_code == status and tree(directory) == before
    assert store.get(owner(client), key)


@pytest.mark.parametrize('change', [
    {'author': ''}, {'author': ' '}, {'author': 'a' * 121}, {'author': 'a\n'}, {'author': False},
    {'decision': 'approved'}, {'decision': []}, {'note': 'x' * 4001}, {'note': None},
    {'decision': 'issues', 'note': ' '}, {'note': '\u0000'}, {'original_word_verified': True},
    {'before_sha256': 'a' * 64},
])
def test_bad_or_forged_review_fields_rejected_without_changes(local, comparison, change):
    client, directory, store = local
    key = store.add(owner(client), comparison)
    body = payload(key)
    body.update(change)
    before = tree(directory)
    response = save(local, key, body=body)
    assert response.status_code == 422, response.json
    assert tree(directory) == before


@pytest.mark.parametrize('language,author_error,note_error', [
    ('es', 'Indica un autor', 'La nota admite'),
    ('en', 'Enter an author', 'The note allows'),
    ('pt-BR', 'Informe um autor', 'A nota permite'),
])
def test_errors_localize_without_translating_authored_review(local, comparison, language, author_error, note_error):
    client, _, store = local
    key = store.add(owner(client), comparison)
    body = payload(key)
    body['author'] = ''
    response = save(local, key, body=body, headers={'X-UI-Language': language})
    assert response.status_code == 422 and author_error in response.json['error']
    body.update(author='Nome conservado / autor original', decision='issues', note='')
    response = save(local, key, body=body, headers={'X-UI-Language': language})
    assert response.status_code == 422 and note_error in response.json['error']
    body['note'] = '  Observación: página revisada.\nConfirmação manual.  '
    response = save(local, key, body=body, headers={'X-UI-Language': language})
    assert response.status_code == 201
    assert response.json['record']['author'] == body['author']
    assert response.json['record']['note'] == body['note'].strip()


def test_save_failure_rolls_back_files_history_and_yaml_without_consuming_receipt(local, comparison, monkeypatch):
    client, directory, store = local
    key = store.add(owner(client), comparison)
    first = save(local, key)
    assert first.status_code == 201
    before = tree(directory)
    original = project_history.save
    def fail_after_write(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError('synthetic storage failure after staged checkpoint')
    monkeypatch.setattr(project_history, 'save', fail_after_write)
    response = save(local, key)
    assert response.status_code == 503 and tree(directory) == before
    assert store.get(owner(client), key)
    assert sorted(path.name for path in directory.parent.iterdir()) == ['case']


@pytest.mark.parametrize('kind', ['project', 'workspace'])
def test_private_receipt_survives_backup_roundtrip_and_history(local, comparison, tmp_path, kind):
    import workspace_backup
    client, directory, store = local
    key = store.add(owner(client), comparison)
    response = save(local, key)
    assert response.status_code == 201
    record, row = response.json['record'], response.json['data']['attachments'][0]
    snapshot = project_history.history(directory)[0]
    assert snapshot['files'][row['member']] == row['sha256']
    if kind == 'project':
        target = tmp_path / 'restored'
        project_history.import_bundle(project_history.export_bundle(directory), target)
    else:
        source = (directory.parent, api.app.config['LIBRARY_PATH'], api.app.config['DESIGN_LIBRARY_PATH'])
        restored = (tmp_path / 'restored-projects', tmp_path / 'restored-findings.json', tmp_path / 'restored-designs.json')
        assert workspace_backup.restore_workspace(workspace_backup.export_workspace(*source), *restored)['projects'] == 1
        target = restored[0] / 'case'
    imported = engine.load_engagement(target / 'engagement.yaml')
    assert reviews.records(imported, target) == [record]
    assert (target / row['member']).read_bytes() == (directory / row['member']).read_bytes()
    assert imported['attachments'][0]['include'] is False
    assert attachments.capture(imported, target, tmp_path / 'delivery') == {}
    assert reviews.records(imported, target)[0]['author_identity'] == 'local_self_declaration'


@pytest.mark.parametrize('kind', ['modified_hash', 'undeclared', 'invalid_schema', 'symlink_file', 'symlink_directory'])
def test_listing_and_download_never_accept_unvalidated_or_undeclared_paths(local, comparison, tmp_path, kind):
    client, directory, store = local
    response = save(local, store.add(owner(client), comparison))
    assert response.status_code == 201
    data, record = response.json['data'], response.json['record']
    row = data['attachments'][0]
    path = directory / row['member']
    if kind == 'modified_hash':
        path.write_bytes(path.read_bytes() + b' ')
    elif kind == 'undeclared':
        data['attachments'] = []
        dump_yaml(data, directory / 'engagement.yaml')
    elif kind == 'invalid_schema':
        invalid = deepcopy(record)
        invalid['original_word_verified'] = True
        raw = reviews.dumps(invalid)
        path.write_bytes(raw)
        row['sha256'] = sha256(raw).hexdigest()
        dump_yaml(data, directory / 'engagement.yaml')
    elif kind == 'symlink_file':
        outside = tmp_path / 'outside.json'
        outside.write_bytes(path.read_bytes())
        path.unlink()
        try:
            path.symlink_to(outside)
        except OSError:
            pytest.skip('symlink creation unavailable')
    else:
        outside = tmp_path / 'outside-attachments'
        (directory / 'attachments').rename(outside)
        try:
            (directory / 'attachments').symlink_to(outside, target_is_directory=True)
        except OSError:
            pytest.skip('symlink creation unavailable')
    listed = client.get(ROUTE)
    assert listed.status_code == 200 and listed.json == {'records': []}
    assert client.get(ROUTE + '/' + record['uid']).status_code == 404


def test_existing_attachment_count_quota_is_shared(local, comparison):
    client, directory, store = local
    data = engine.load_engagement(directory / 'engagement.yaml')
    data['attachments'] = [dict(uid=str(uuid.uuid4()), name=f'declared-{index}.json', include=False,
                                reviewed=False, required=False) for index in range(100)]
    dump_yaml(data, directory / 'engagement.yaml')
    before = tree(directory)
    response = save(local, store.add(owner(client), comparison))
    assert response.status_code == 422 and tree(directory) == before


def test_existing_total_bytes_quota_is_shared_with_other_private_attachments(local, comparison, monkeypatch):
    client, directory, store = local
    data = engine.load_engagement(directory / 'engagement.yaml')
    identity = uuid.uuid4()
    blob = b'other private attachment'
    member = 'attachments/' + identity.hex + '.txt'
    (directory / 'attachments').mkdir()
    (directory / member).write_bytes(blob)
    data['attachments'] = [dict(uid=str(identity), name='other.txt', member=member, sha256=sha256(blob).hexdigest(),
                                include=False, reviewed=False, required=False)]
    dump_yaml(data, directory / 'engagement.yaml')
    monkeypatch.setattr(attachments, 'MAX_TOTAL', len(blob) + 1)
    before = tree(directory)
    response = save(local, store.add(owner(client), comparison))
    assert response.status_code == 422 and tree(directory) == before


def test_successful_saves_and_snapshot_restore_preserve_existing_private_attachment(local, comparison):
    client, directory, store = local
    data = engine.load_engagement(directory / 'engagement.yaml')
    identity = uuid.uuid4()
    member, blob = 'attachments/' + identity.hex + '.txt', b'UNCHANGED PRIVATE EVIDENCE'
    (directory / 'attachments').mkdir()
    (directory / member).write_bytes(blob)
    data['attachments'] = [dict(uid=str(identity), name='existing.txt', member=member,
                                sha256=sha256(blob).hexdigest(), include=False, reviewed=False, required=False)]
    dump_yaml(data, directory / 'engagement.yaml')
    key = store.add(owner(client), comparison)
    first = save(local, key)
    assert first.status_code == 201
    snapshot = project_history.history(directory)[0]
    second = save(local, key)
    assert second.status_code == 201 and len(second.json['records']) == 2
    assert (directory / member).read_bytes() == blob
    project_history.restore(directory, snapshot['id'])
    restored = engine.load_engagement(directory / 'engagement.yaml')
    assert reviews.records(restored, directory) == [first.json['record']]
    assert (directory / member).read_bytes() == blob
    assert any(second.json['data']['attachments'][-1]['member'] in entry['files']
               for entry in project_history.history(directory)), 'later records remain in private history after restore'


def test_equal_pdf_hashes_cannot_claim_different_page_counts(comparison):
    store = reviews.ReceiptStore()
    record = reviews.make_record(store.get('one', store.add('one', comparison)), 'Reviewer', 'accepted', '')
    assert record['before_pages'] == 1 and record['after_pages'] == 2
    record['after_sha256'] = record['before_sha256']
    with pytest.raises(ValueError):
        reviews.validate_record(record)


@pytest.mark.parametrize('mutate', [
    lambda record: record.update(uid='../escape'),
    lambda record: record.update(created='not-a-time'),
    lambda record: record.update(created='2026-10-16T12:00:00'),
    lambda record: record.update(author_identity='verified'),
    lambda record: record.update(semantic_equivalence_verified=True),
    lambda record: record.update(original_word_verified=True),
    lambda record: record.update(filename='private.pdf'),
    lambda record: record.update(before_pages=True),
    lambda record: record['summary'].update(total_pages=100),
    lambda record: record['page_pairs'][0].update(before_page=2),
    lambda record: record['page_pairs'][0].update(before_page=True),
])
def test_imported_record_validation_rejects_false_claims_paths_and_broken_pair_coverage(comparison, mutate):
    store = reviews.ReceiptStore()
    record = reviews.make_record(store.get('one', store.add('one', comparison)), 'Reviewer', 'accepted', '')
    mutate(record)
    with pytest.raises(ValueError):
        reviews.validate_record(record)
