"""Explicit PDF pairing: actual page coverage, isolated metadata and receipts."""
from copy import deepcopy
from hashlib import sha256
from html import escape
from io import BytesIO
import json
from pathlib import Path
import subprocess

from pypdf import PdfWriter
import pytest
from werkzeug.datastructures import MultiDict

import app as api
import pdf_compare
from _support import auth_client
from test_pdf_compare_0360 import blank, pdf


def colored(*colors):
    writer, stream = PdfWriter(), BytesIO()
    for color in colors:
        writer.append(BytesIO(pdf(square=color)))
    writer.write(stream)
    return stream.getvalue()


def comparison(before, after, pairs=None, lang='en'):
    html = pdf_compare.compare(before, after, lang, pairs)
    return html, pdf_compare.comparison_manifest(html)


def test_inserted_page_does_not_shift_following_explicit_pairs():
    red, blue, green = (1, 0, 0), (0, 0, 1), (0, 1, 0)
    before, after = colored(red, blue), colored(red, green, blue)
    _, positional = comparison(before, after)
    pairs = [{'before': 1, 'after': 1}, {'before': None, 'after': 2}, {'before': 2, 'after': 3}]
    html, value = comparison(before, after, pairs)
    assert value['schema'] == 'report-gen-pdf-comparison/2' and value['pairing_mode'] == 'manual'
    assert positional['pairing_mode'] == 'positional' and positional['summary']['changed'] == 1
    assert value['summary'] == dict(unchanged=2, changed=0, added=1, removed=0, dimensions_changed=0, total_pages=3)
    assert [(row['number'], row['before_page'], row['after_page']) for row in value['pages']] == [(1, 1, 1), (2, None, 2), (3, 2, 3)]
    assert 'Before 2 → After 3' in html.decode() and 'Pairing: Manual' in html.decode()
    assert 'alt="Before · Page 2"' in html.decode() and 'alt="After · Page 3"' in html.decode()
    assert value['alignment'] == 'page_pairs_top_left'
    assert value['semantic_equivalence_verified'] is False


def test_reordered_pairs_render_selected_actual_pages():
    before, after = colored((1, 0, 0), (0, 0, 1)), colored((0, 0, 1), (1, 0, 0))
    _, positional = comparison(before, after)
    _, manual = comparison(before, after, [{'before': 1, 'after': 2}, {'before': 2, 'after': 1}])
    assert positional['summary']['changed'] == 2 and manual['summary']['unchanged'] == 2
    assert all(row['changed_pixels'] == 0 for row in manual['pages'])


@pytest.mark.parametrize('lang,title', [('es', 'Emparejamiento: Manual'), ('en', 'Pairing: Manual'), ('pt', 'Pareamento: Manual')])
def test_manual_deletion_and_addition_keep_explicit_nulls_and_localized_mode(lang, title):
    html, value = comparison(blank(), blank(), [{'before': 1, 'after': None}, {'before': None, 'after': 1}], lang)
    assert title in html.decode('utf-8')
    assert value['summary']['removed'] == value['summary']['added'] == 1
    assert all(row['changed_pixels'] == row['total_pixels'] for row in value['pages'])
    assert value['identical_pdf_bytes'] is True  # Manual selection does not change input hashes.


@pytest.mark.parametrize('pairs', [
    [], {}, '1:1', [1], [{'before': 1}], [{'before': 1, 'after': 1, 'extra': 0}],
    [{'before': None, 'after': None}], [{'before': True, 'after': 1}], [{'before': 1, 'after': False}],
    [{'before': 1.0, 'after': 1}], [{'before': '1', 'after': 1}], [{'before': 0, 'after': 1}],
    [{'before': -1, 'after': 1}], [{'before': 81, 'after': 1}],
    [{'before': 1, 'after': 1}] * 161,
    [{'before': 1, 'after': 1}, {'before': 1, 'after': 2}],
    [{'before': 1, 'after': 1}, {'before': 2, 'after': 1}],
])
def test_invalid_pair_shape_is_rejected_before_starting_worker(pairs, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('invalid pairing must not reach worker')
    monkeypatch.setattr(pdf_compare, '_execute', forbidden)
    with pytest.raises(ValueError):
        pdf_compare.compare(blank(), blank(), 'en', pairs)


@pytest.mark.parametrize('pairs', [
    [{'before': 1, 'after': 1}],  # Page2 omitted on both sides.
    [{'before': 1, 'after': 1}, {'before': 3, 'after': 2}],
    [{'before': 1, 'after': 1}, {'before': 2, 'after': None}],
])
def test_real_page_coverage_rejected_inside_worker(pairs):
    with pytest.raises(ValueError, match='every page exactly once'):
        pdf_compare.compare(blank(2), blank(2), 'en', pairs)


def test_manual_total_budget_preflight_occurs_before_first_raster(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('raster must not start before all pair budgets are checked')
    monkeypatch.setattr(pdf_compare, '_raster', forbidden)
    pairs = ([{'before': n, 'after': None} for n in range(1, 41)] +
             [{'before': None, 'after': n} for n in range(1, 41)])
    with pytest.raises(pdf_compare._Rejected, match='pixels'):
        pdf_compare._comparison(blank(40, size=(612, 792)), blank(40, size=(612, 792)), 'en', pairs)


def test_metadata_reports_only_actual_hashes_and_geometry_without_raster_or_plan(monkeypatch):
    before, after = pdf(metadata='private-title-not-for-metadata'), blank(2, size=(320, 200))
    value = pdf_compare.metadata(before, after, 'pt')
    assert set(value) == {'schema', 'before', 'after'} and value['schema'] == 'report-gen-pdf-metadata/1'
    assert value['before']['sha256'] == sha256(before).hexdigest()
    assert value['before']['bytes'] == len(before)
    assert value['after']['pages'] == [dict(number=n, width=320, height=200) for n in (1, 2)]
    assert 'private-title' not in json.dumps(value) and 'data:image' not in json.dumps(value)
    def forbidden(*args, **kwargs):
        pytest.fail('metadata must not plan, rasterize or compare pages')
    monkeypatch.setattr(pdf_compare, '_plans', forbidden)
    monkeypatch.setattr(pdf_compare, '_raster', forbidden)
    assert pdf_compare._metadata(before, after) == value


def test_metadata_accepts_full_page_count_without_comparison_pixel_budget():
    assert len(pdf_compare.metadata(blank(80, size=(612, 792)), blank(), 'en')['before']['pages']) == 80


@pytest.mark.parametrize('raw', [b'bad', blank(encrypted=''), blank(81)])
def test_metadata_keeps_pdf_validation_limits(raw):
    with pytest.raises(ValueError):
        pdf_compare.metadata(raw, blank(), 'en')


def test_metadata_timeout_cleans_up_and_shares_worker_semaphore(monkeypatch):
    paths = []
    def timeout(command, **options):
        path = Path(command[-2]); paths.append(path)
        assert json.loads((path / 'request.json').read_text()) == dict(operation='metadata', page_pairs=None)
        assert options['timeout'] == 45
        raise subprocess.TimeoutExpired(command, 45)
    monkeypatch.setattr(pdf_compare, '_execute', timeout)
    with pytest.raises(ValueError, match='45 seconds'):
        pdf_compare.metadata(blank(), blank(), 'en')
    assert all(not path.exists() for path in paths)
    assert pdf_compare._WORKERS.acquire(blocking=False)
    try:
        with pytest.raises(ValueError, match='already running'):
            pdf_compare.metadata(blank(), blank(), 'en')
    finally:
        pdf_compare._WORKERS.release()


def changed_manifest(html, mutate):
    value = deepcopy(pdf_compare.comparison_manifest(html))
    mutate(value)
    marker = b'<pre id="comparison-manifest" hidden>'
    return html[:html.index(marker) + len(marker)] + escape(json.dumps(value)).encode() + b'</pre></body></html>'


@pytest.mark.parametrize('mutate', [
    lambda value: value.update(schema='report-gen-pdf-comparison/1'),
    lambda value: value.update(semantic_equivalence_verified=True),
    lambda value: value.update(before_sha256='not-a-hash'),
    lambda value: value.update(before_pages=2),
    lambda value: value['pages'][0].update(before_page=True),
    lambda value: value['pages'][0].update(total_pixels=True),
    lambda value: value['pages'][0].update(changed_pixels=5),
    lambda value: value['pages'][0].update(scale=2),
    lambda value: value['summary'].update(unchanged=2),
    lambda value: value.update(extra='private data must not be accepted'),
])
def test_receipt_helper_rejects_inconsistent_or_unexpected_server_manifest(mutate):
    html = pdf_compare.compare(blank(), blank(), 'en')
    with pytest.raises(ValueError, match='recibo|receipt'):
        pdf_compare.comparison_manifest(changed_manifest(html, mutate))


def test_receipt_helper_rejects_missing_oversized_or_duplicate_terminal_blocks():
    for html in (b'<html>arbitrary</html>', b'<!doctype html><pre id="comparison-manifest" hidden>' +
                 b'x' * (pdf_compare.MAX_MANIFEST + 1) + b'</pre></body></html>'):
        with pytest.raises(ValueError):
            pdf_compare.comparison_manifest(html)
    html = pdf_compare.compare(blank(), blank(), 'en')
    with pytest.raises(ValueError):
        pdf_compare.comparison_manifest(html.replace(b'<main>', b'<main><pre id="comparison-manifest" hidden>'))


@pytest.fixture
def client():
    return auth_client(api.app)


def upload(client, route='/api/pdf-compare', fields=None, before=None, after=None, headers=None):
    data = MultiDict([('before', (BytesIO(before or blank()), 'private-before.pdf')),
                      ('after', (BytesIO(after or blank()), 'private-after.pdf')), ('language', 'en')])
    for key, value in (fields or []):
        data.add(key, value)
    return client.post(route, data=data, headers=headers or {})


def test_metadata_endpoint_csrf_origin_type_private_and_read_only(client):
    response = upload(client, '/api/pdf-compare/metadata')
    assert response.status_code == 200, response.get_json(silent=True)
    assert response.mimetype == 'application/json' and response.headers['Cache-Control'] == 'no-store'
    assert response.json['schema'] == 'report-gen-pdf-metadata/1'
    assert b'private-before' not in response.data
    assert upload(api.app.test_client(), '/api/pdf-compare/metadata').status_code == 403
    assert upload(client, '/api/pdf-compare/metadata', headers={'Origin': 'https://hostile.test'}).status_code == 403
    assert upload(client, '/api/pdf-compare/metadata', fields=[('page_pairs', '[]')]).status_code == 415
    assert client.post('/api/pdf-compare/metadata', json={}).status_code == 415


@pytest.mark.parametrize('raw', ['null', '[{"before":1,"before":2,"after":1}]', '[' + ' ' * 16384 + ']'])
def test_api_rejects_null_duplicate_json_keys_and_pairing_byte_limit(client, raw):
    assert upload(client, fields=[('page_pairs', raw)]).status_code == 422


def test_api_rejects_duplicate_form_plan_and_expected_hash_fields(client):
    plan = '[{"before":1,"after":1}]'
    assert upload(client, fields=[('page_pairs', plan), ('page_pairs', plan)]).status_code == 415
    digest = sha256(blank()).hexdigest()
    fields = [('page_pairs', plan), ('expected_before_sha256', digest), ('expected_after_sha256', digest)]
    assert upload(client, fields=fields + [('expected_before_sha256', digest)]).status_code == 415


def test_inspection_hash_binding_rejects_changed_pdf_before_worker(client, monkeypatch):
    before = blank()
    plan = '[{"before":1,"after":1}]'
    digest = sha256(before).hexdigest()
    fields = [('page_pairs', plan), ('expected_before_sha256', digest), ('expected_after_sha256', digest)]
    good = upload(client, fields=fields)
    assert good.status_code == 200
    def forbidden(*args, **kwargs):
        pytest.fail('changed source must be rejected before starting the worker')
    monkeypatch.setattr(pdf_compare, '_execute', forbidden)
    response = upload(client, fields=fields, after=pdf(metadata='changed'), headers={'X-UI-Language': 'en'})
    assert response.status_code == 422 and 'changed since inspection' in response.json['error']


@pytest.mark.parametrize('fields', [
    [('expected_before_sha256', 'a' * 64)],
    [('page_pairs', '[{"before":1,"after":1}]'), ('expected_before_sha256', 'a' * 64)],
    [('page_pairs', '[{"before":1,"after":1}]'), ('expected_before_sha256', 'A' * 64), ('expected_after_sha256', 'a' * 64)],
    [('expected_before_sha256', 'a' * 64), ('expected_after_sha256', 'a' * 64)],
])
def test_hash_binding_requires_both_valid_lowercase_hashes_and_manual_plan(client, fields):
    assert upload(client, fields=fields).status_code == 415


def test_capabilities_distinguish_discarded_content_from_receipts_and_saved_reviews(client):
    from pdf_comparison_reviews import TTL
    caps = client.get('/api/pdf-compare/capabilities').get_json()
    assert 'server_retention' not in caps  # A single False no longer describes the feature.
    assert caps['retention'] == {
        'content_after_request': {'pdf_bytes': False, 'html_bytes': False, 'raster_images': False},
        'temporary_receipts': {'metadata_only': True, 'storage': 'process_memory',
                               'ttl_seconds': TTL, 'expiry_enforcement': 'on_access',
                               'cleanup': 'lazy_on_store_operation'},
        'saved_reviews': {'opt_in': True, 'storage': 'private_project_attachment',
                          'included_in_project_history_and_backups': True},
    }
