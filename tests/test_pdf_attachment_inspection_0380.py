"""Real bounded PDF annex scans: private localizers, no rewriting or approval."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import subprocess
import uuid
import zlib

from pypdf import PdfWriter
from pypdf.generic import (ArrayObject, DecodedStreamObject, DictionaryObject, EncodedStreamObject,
                           NameObject, NumberObject, TextStringObject)
import pytest

import attachments
import pdf_attachment_inspection as inspection


def pdf(edit=None, *, pages=1, password=None):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(180, 180)
    if edit:
        edit(writer)
    if password is not None:
        writer.encrypt(password)
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def attach(directory, blob):
    member = 'attachments/' + uuid.uuid4().hex + '.pdf'
    path = directory / member
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob)
    return dict(uid=str(uuid.uuid4()), name='synthetic-annex.pdf', member=member,
                sha256=sha256(blob).hexdigest(), include=False, reviewed=False)


def alerts(result):
    return {alert['kind']: alert for alert in result['alerts']}


def assert_private(result, *markers):
    encoded = json.dumps(result)
    assert not result['complete'] and result['manual_review_required']
    assert all(marker not in encoded for marker in markers)


def test_real_report_gen_pdf_text_is_scanned_without_mutation(tmp_path):
    import export
    from wizard import dump_yaml
    dump_yaml({'meta': {'report_title': 'Synthetic annex inspection', 'theme': 'serio'},
               'findings': [{'id': 'F01', 'title': 'Synthetic finding',
                             'description_md': 'password=SYNTHETIC_PAGE_CREDENTIAL_0380\n\nprivate@example.invalid'}]},
              tmp_path / 'engagement.yaml')
    output = export.export(tmp_path / 'engagement.yaml', 'pdf', tmp_path / 'report.pdf')
    blob = output.read_bytes()
    row = attach(tmp_path, blob)
    result = attachments.scan(tmp_path, row)
    assert result['scope'] == 'pdf_structural'
    assert result['pdf']['pages_inspected'] == result['pdf']['pages_total'] >= 1
    assert 'credential' in alerts(result) and 'possible_email' in alerts(result)
    assert any(location['category'] == 'page_text' and location['page'] >= 1
               for location in alerts(result)['credential']['locations'])
    assert_private(result, 'SYNTHETIC_PAGE_CREDENTIAL_0380', 'private@example.invalid')
    assert result['sha256'] == sha256(blob).hexdigest()
    assert (tmp_path / row['member']).read_bytes() == blob
    assert not row['reviewed'] and not row['include']


def test_metadata_info_and_compressed_xmp_return_only_categories_and_object_ids():
    def edit(writer):
        writer.add_metadata({'/Author': 'metadata@example.invalid', '/Subject': 'password=SYNTHETIC_INFO_0380'})
        stream = DecodedStreamObject()
        stream.set_data(b'<x:xmpmeta xmlns:x="adobe:ns:meta/">token=SYNTHETIC_XMP_0380</x:xmpmeta>')
        stream = stream.flate_encode()
        stream[NameObject('/Type')] = NameObject('/Metadata')
        stream[NameObject('/Subtype')] = NameObject('/XML')
        writer._root_object[NameObject('/Metadata')] = writer._add_object(stream)
    result = inspection.inspect_pdf(pdf(edit))
    assert alerts(result)['credential']['count'] == 2
    assert all(location['category'] == 'metadata' and location['object'] > 0
               for location in alerts(result)['credential']['locations'])
    assert result['pdf']['stream_bytes_inspected'] > 0
    assert 'xml_entities_not_resolved' in result['pdf']['limitations']
    assert_private(result, 'SYNTHETIC_INFO_0380', 'SYNTHETIC_XMP_0380', 'metadata@example.invalid')


@pytest.mark.parametrize('feature,expected', [('annotation', 'annotation'), ('form', 'form'), ('uri', 'link'), ('javascript', 'action')])
def test_hidden_pdf_features_have_bounded_locations_without_echoing_values(feature, expected):
    marker = 'SYNTHETIC_PRIVATE_FEATURE_0380'
    def edit(writer):
        if feature == 'javascript':
            writer._root_object[NameObject('/OpenAction')] = writer._add_object(DictionaryObject({
                NameObject('/S'): NameObject('/JavaScript'),
                NameObject('/JS'): TextStringObject('const password="' + marker + '";')}))
            return
        item = DictionaryObject({NameObject('/Type'): NameObject('/Annot'),
             NameObject('/Subtype'): NameObject('/Widget' if feature == 'form' else '/Link' if feature == 'uri' else '/Text'),
             NameObject('/Rect'): ArrayObject([NumberObject(value) for value in (0, 0, 50, 50)])})
        if feature == 'form':
            item.update({NameObject('/FT'): NameObject('/Tx'), NameObject('/T'): TextStringObject('private-field'),
                         NameObject('/V'): TextStringObject('password=' + marker)})
        elif feature == 'uri':
            item[NameObject('/A')] = DictionaryObject({NameObject('/S'): NameObject('/URI'),
                NameObject('/URI'): TextStringObject('https://example.invalid/?token=' + marker)})
        else:
            item[NameObject('/Contents')] = TextStringObject('password=' + marker)
        writer.pages[0][NameObject('/Annots')] = writer._add_object(ArrayObject([writer._add_object(item)]))
    result = inspection.inspect_pdf(pdf(edit))
    assert 'credential' in alerts(result)
    location = alerts(result)['credential']['locations'][0]
    assert location['category'] == expected and location['object'] > 0
    if feature != 'javascript':
        assert location['page'] == 1
    assert_private(result, marker, 'private-field')


def test_embedded_file_is_flagged_without_decoding_payload_or_leaking_name():
    payload = b'password=SYNTHETIC_EMBEDDED_PAYLOAD_0380'
    result = inspection.inspect_pdf(pdf(lambda writer: writer.add_attachment('PRIVATE_FILENAME_0380.txt', payload)))
    assert alerts(result)['pdf_embedded_file']['count'] == 1
    assert 'credential' not in alerts(result)
    assert 'embedded_files_not_opened' in result['pdf']['limitations']
    assert_private(result, 'PRIVATE_FILENAME_0380', 'SYNTHETIC_EMBEDDED_PAYLOAD_0380')


@pytest.mark.parametrize('password', ['', 'synthetic-password'])
def test_encrypted_pdf_never_claims_scanned_even_with_empty_password(password):
    result = inspection.inspect_pdf(pdf(password=password))
    assert result['scope'] == 'manual' and result['pdf']['status'] == 'encrypted'
    assert result['pdf']['pages_inspected'] == result['pdf']['objects_inspected'] == 0
    assert_private(result)


@pytest.mark.parametrize('blob', [b'%PDF-1.7\nmalformed-private-content', b'%PDF-1.7\n', b'not-pdf'])
def test_invalid_pdf_never_returns_a_clean_inspection(blob):
    result = inspection.inspect_pdf(blob)
    assert result['scope'] == 'manual' and result['pdf']['status'] == 'invalid'
    assert result['alerts'] == [] and result['bytes_inspected'] == 0
    assert_private(result, 'malformed-private-content')


def test_read_hash_guard_precedes_pdf_parser(tmp_path, monkeypatch):
    row = attach(tmp_path, pdf())
    (tmp_path / row['member']).write_bytes(pdf(pages=2))
    monkeypatch.setattr(inspection, 'inspect_pdf', lambda _: pytest.fail('parser must not run'))
    with pytest.raises(ValueError, match='alterado'):
        attachments.scan(tmp_path, row)


def test_decompression_bomb_in_xmp_is_partial_and_bounded():
    def edit(writer):
        stream = EncodedStreamObject()
        stream._data = zlib.compress(b'x' * (inspection.MAX_STREAM + 100))
        stream[NameObject('/Filter')] = NameObject('/FlateDecode')
        stream[NameObject('/Type')] = NameObject('/Metadata')
        writer._root_object[NameObject('/Metadata')] = writer._add_object(stream)
    result = inspection.inspect_pdf(pdf(edit))
    assert result['pdf']['status'] == 'partial'
    assert 'stream_limit' in result['pdf']['limitations']
    assert result['pdf']['stream_bytes_inspected'] == 0
    assert_private(result)


def test_compressed_script_stream_is_scanned_without_execution():
    def edit(writer):
        stream = DecodedStreamObject()
        stream.set_data(b'const password="SYNTHETIC_JS_STREAM_0380";')
        writer._root_object[NameObject('/OpenAction')] = writer._add_object(DictionaryObject({
            NameObject('/S'): NameObject('/JavaScript'), NameObject('/JS'): writer._add_object(stream.flate_encode())}))
    result = inspection.inspect_pdf(pdf(edit))
    assert alerts(result)['credential']['locations'][0]['category'] == 'action'
    assert result['pdf']['stream_bytes_inspected'] > 0
    assert_private(result, 'SYNTHETIC_JS_STREAM_0380')


def test_indirect_object_cycle_does_not_recurse_forever_or_report_complete():
    def edit(writer):
        obj = DictionaryObject({NameObject('/Contents'): TextStringObject('password=SYNTHETIC_CYCLE_0380')})
        reference = writer._add_object(obj)
        obj[NameObject('/Cycle')] = reference
        writer._root_object[NameObject('/Cycle')] = reference
    result = inspection.inspect_pdf(pdf(edit))
    assert result['pdf']['objects_inspected'] == result['pdf']['objects_total']
    assert alerts(result)['credential']['count'] == 1
    assert_private(result, 'SYNTHETIC_CYCLE_0380')


def test_many_objects_and_locations_are_truncated_explicitly():
    def edit(writer):
        for _ in range(inspection.MAX_OBJECTS + 1):
            writer._add_object(DictionaryObject({NameObject('/Contents'): TextStringObject('password=SYNTHETIC_REPEAT_0380')}))
    result = inspection.inspect_pdf(pdf(edit))
    assert result['pdf']['objects_inspected'] == inspection.MAX_OBJECTS
    assert {'object_limit', 'location_limit'} <= set(result['pdf']['limitations'])
    assert sum(len(alert['locations']) for alert in result['alerts']) == inspection.MAX_LOCATIONS
    assert_private(result, 'SYNTHETIC_REPEAT_0380')


def test_document_structure_tag_is_not_misclassified_as_pdf_action():
    def edit(writer):
        writer._root_object[NameObject('/StructTreeRoot')] = writer._add_object(DictionaryObject({
            NameObject('/Type'): NameObject('/StructElem'), NameObject('/S'): NameObject('/P')}))
    result = inspection.inspect_pdf(pdf(edit))
    assert 'pdf_action' not in alerts(result)
    assert_private(result)


def test_image_pdf_requires_visual_review_without_ocr():
    def edit(writer):
        image = DecodedStreamObject()
        image.set_data(b'\xff\xff\xff')
        image.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                      NameObject('/Width'): NumberObject(1), NameObject('/Height'): NumberObject(1),
                      NameObject('/BitsPerComponent'): NumberObject(8), NameObject('/ColorSpace'): NameObject('/DeviceRGB')})
        writer.pages[0][NameObject('/Resources')] = DictionaryObject({NameObject('/XObject'):
            DictionaryObject({NameObject('/Im1'): writer._add_object(image)})})
    result = inspection.inspect_pdf(pdf(edit))
    assert alerts(result)['pdf_image']['count'] == 1
    assert {'no_ocr', 'images_present', 'textless_pages'} <= set(result['pdf']['limitations'])
    assert_private(result)


def test_page_limit_is_reported_instead_of_implying_all_pages_checked():
    result = inspection.inspect_pdf(pdf(pages=inspection.MAX_PAGES + 1))
    assert result['pdf']['pages_total'] == inspection.MAX_PAGES + 1
    assert result['pdf']['pages_inspected'] == inspection.MAX_PAGES
    assert result['pdf']['status'] == 'partial' and 'page_limit' in result['pdf']['limitations']
    assert_private(result)


def test_long_metadata_limits_text_and_alert_locations():
    def edit(writer):
        writer.add_metadata({'/Subject': 'password=VALUE_0380\n' * (inspection.MAX_TEXT // 18 + 2)})
    result = inspection.inspect_pdf(pdf(edit))
    assert result['pdf']['text_characters_inspected'] == inspection.MAX_TEXT
    assert 'text_limit' in result['pdf']['limitations'] and result['pdf']['status'] == 'partial'
    assert_private(result, 'VALUE_0380')


@pytest.mark.parametrize('failure,status', [(subprocess.TimeoutExpired('worker', 20), 'timeout'), (OSError('PRIVATE_FAILURE_0380'), 'limits')])
def test_worker_failures_are_private_and_temporary_inputs_removed(tmp_path, monkeypatch, failure, status):
    destinations = []
    def fail(command, **kwargs):
        destinations.append(Path(command[-1]))
        assert (destinations[-1] / 'input.pdf').is_file()
        assert kwargs['timeout'] == inspection.TIMEOUT
        raise failure
    monkeypatch.setattr(inspection.pdf_compare, '_execute', fail)
    result = inspection.inspect_pdf(pdf())
    assert result['pdf']['status'] == status
    assert destinations and all(not path.exists() for path in destinations)
    assert_private(result, 'PRIVATE_FAILURE_0380')


def test_shared_worker_budget_rejects_concurrent_inspection_without_leak():
    assert inspection.pdf_compare._WORKERS.acquire(blocking=False)
    try:
        result = inspection.inspect_pdf(pdf())
        assert result['pdf']['status'] == 'busy' and result['scope'] == 'manual'
    finally:
        inspection.pdf_compare._WORKERS.release()
    assert inspection.inspect_pdf(pdf())['pdf']['status'] == 'inspected'


@pytest.mark.parametrize('edit', [lambda receipt: receipt.update(private='SYNTHETIC_LEAK'),
    lambda receipt: receipt['pdf'].update(extra='SYNTHETIC_LEAK'),
    lambda receipt: receipt['pdf']['limitations'].append('SYNTHETIC_LEAK'),
    lambda receipt: receipt['alerts'].append(dict(kind='credential', count=1, locations=[dict(category='metadata', value='SYNTHETIC_LEAK')]))])
def test_parent_rejects_extra_or_arbitrary_worker_text(edit):
    receipt = dict(sha256='a' * 64, pdf=inspection._empty('inspected'), alerts=[])
    edit(receipt)
    with pytest.raises(inspection._Rejected):
        inspection._validate_receipt(receipt, 'a' * 64)


def test_api_result_is_no_store_revision_bound_and_absent_from_delivery_manifest(tmp_path, monkeypatch):
    import app as api
    import delivery
    import engine
    from _support import auth_client
    from storage import revision
    from wizard import dump_yaml
    directory = tmp_path / 'projects' / 'case'
    directory.mkdir(parents=True)
    blob = pdf(lambda writer: writer.add_metadata({'/Author': 'PRIVATE_OWNER@example.invalid'}))
    row = attach(directory, blob)
    data = {'meta': {'report_title': 'Synthetic private annex'}, 'findings': [], 'attachments': [row]}
    dump_yaml(data, directory / 'engagement.yaml')
    monkeypatch.setattr(api, 'PROJECTS', directory.parent)
    monkeypatch.setitem(api.app.config, 'TESTING', True)
    client = auth_client(api.app)
    before = {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob('*') if path.is_file()}
    response = client.get('/api/projects/case/attachments/scan', query_string={'uid': row['uid']})
    assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
    assert response.json['uid'] == row['uid'] and response.json['sha256'] == row['sha256']
    assert response.get_etag()[0] == revision(directory / 'engagement.yaml')
    assert 'PRIVATE_OWNER' not in response.get_data(as_text=True)
    assert {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob('*') if path.is_file()} == before
    manifest = delivery.capture(directory, tmp_path / 'capture')
    assert 'PRIVATE_OWNER' not in json.dumps(manifest)
    assert attachments.capture(engine.load_engagement(directory / 'engagement.yaml'), directory, tmp_path / 'annexes') == {}
    assert not (tmp_path / 'annexes').exists()
    assert deepcopy(row) == data['attachments'][0]
