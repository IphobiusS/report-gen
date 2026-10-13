"""Final review: real report destinations, identity references and date order."""
from copy import deepcopy
from pathlib import Path
import subprocess
import sys

from lxml import html
import pdfplumber
import pytest
from pypdf import PdfReader

import engine
import validate
import workflows
from wizard import dump_yaml


def document():
    return {'meta': {'report_title': 'Synthetic model consistency audit', 'theme': 'serio', 'lang': 'en'},
            'findings': [{'id': 'F1', 'mode': 'vuln', 'title': 'Synthetic condition',
                          'severity': 'info', 'cvss': 0, 'description_md': 'Synthetic; not executed.'}]}


@pytest.mark.parametrize('fragment', ['#F%32', '#%46%32', '#F%30%30%32', '#F2'])
def test_removed_url_encoded_numeric_destination_is_not_reassigned(fragment):
    data = document(); data['findings'][0]['description_md'] = '[Former condition](' + fragment + ')'
    workflows.normalize(data)
    before = deepcopy(data['findings'])
    assert workflows.allocate_finding_id(data) == 'F3'
    assert data['findings'] == before


@pytest.mark.parametrize('fragment', ['#F%2532', '#F%E0%A4%A', '#F%FF', '#f%32', '#F%32.suffix'])
def test_literal_or_malformed_encoded_identity_is_not_decoded_again(fragment):
    data = document(); data['findings'][0]['description_md'] = '[Literal identity](' + fragment + ')'
    assert workflows.allocate_finding_id(data) == 'F2'


def test_url_encoded_exhausted_destination_rejects_before_mutation():
    data = document()
    data['findings'][0]['description_md'] = '[Former condition](#%46' + str(workflows.MAX_SEQUENCE) + ')'
    before = deepcopy(data)
    with pytest.raises(ValueError, match='agotó|exhausted'):
        workflows.allocate_finding_id(data)
    assert data == before


@pytest.mark.parametrize('field', ['due_date', 'tested_on'])
@pytest.mark.parametrize('value', ['20261007', '2026-W41-3', '2026W413', '2026-10-08T00:00:00', '2026-02-30'])
def test_noncanonical_or_impossible_workflow_date_is_rejected_without_rewriting(field, value):
    data = document()
    if field == 'due_date': data['findings'][0][field] = value
    else: data['findings'][0]['retests'] = [{'tested_on': value, 'result': 'not_verified'}]
    before = deepcopy(data)
    errors = [msg for level, msg in validate.validate(data) if level == 'error']
    assert any(field in message and 'AAAA-MM-DD' in message for message in errors)
    assert data == before


def test_canonical_retest_dates_order_chronologically_and_ties_use_record_order():
    data = document(); finding = data['findings'][0]
    finding['status'] = 'verified_fixed'
    finding['retests'] = [{'tested_on': '2026-10-07', 'result': 'open'},
                         {'tested_on': '2026-10-08', 'result': 'open'},
                         {'tested_on': '2026-10-08', 'result': 'fixed'}]
    assert not [msg for level, msg in validate.validate(data) if level == 'error']
    assert workflows.latest_retest(finding) is finding['retests'][2]


def test_canonical_overdue_date_remains_visible_in_review(tmp_path):
    data = document(); data['findings'][0]['due_date'] = '2000-01-01'
    issues = workflows.review(data, tmp_path)
    assert any(issue['path'] == 'findings[0].due_date' and 'vencida' in issue['message'] for issue in issues)


@pytest.mark.parametrize('with_details', [False, True])
def test_page_keys_match_only_sections_and_findings_actually_emitted(with_details, tmp_path):
    data = document()
    data['report'] = {'sections': [{'key': 'findings_summary'}, {'key': 'appendix'}]}
    if with_details: data['report']['sections'].insert(1, {'key': 'findings'})
    data['assets'] = [{'name': 'Synthetic asset', 'target': 'scope.example'}]
    before = deepcopy(data)
    rendered = html.document_fromstring(engine.render_html(
        engine.build_env(), data, tmp_path.resolve(), {}, True, engine.load_lang('en')))
    keys = engine.toc_keys(data)
    assert 'appendix' not in keys
    assert ('F1' in keys) == with_details
    assert ('findings' in keys) == with_details
    assert 'rg_assets' in keys
    expected_markers = {str(node.text_content()) for node in rendered.xpath('//*[contains(concat(" ",normalize-space(@class)," ")," pm ")]')}
    assert expected_markers == {'PGMK' + __import__('urllib.parse', fromlist=['quote']).quote(key, safe='') + 'PGMK' for key in keys}
    assert data == before


@pytest.mark.parametrize('sections', [False, True])
def test_percent_encoded_page_markers_keep_distinct_documentary_keys(sections, tmp_path):
    data = document()
    if sections:
        data['findings'] = []
        data['report'] = {'sections': [
            {'key': 'Appendix A', 'title': 'First appendix', 'body': 'SPACE_KEY_CANARY'},
            {'key': 'AppendixA', 'title': 'Second appendix', 'body': 'COMPACT_KEY_CANARY'},
            {'key': 'Annexe %41', 'title': 'Literal percent appendix', 'body': 'PERCENT_KEY_CANARY'}]}
        keys = ['Appendix A', 'AppendixA', 'Annexe %41']
    else:
        data['findings'] = [dict(data['findings'][0], id='Finding A', description_md='SPACE_KEY_CANARY'),
                            dict(data['findings'][0], id='FindingA', description_md='COMPACT_KEY_CANARY'),
                            dict(data['findings'][0], id='Finding %41', description_md='PERCENT_KEY_CANARY')]
        keys = ['Finding A', 'FindingA', 'Finding %41']
    assert not [message for level, message in validate.validate(data) if level == 'error']
    rendered = engine.render_html(engine.build_env(), data, tmp_path.resolve(), {}, True, engine.load_lang('en'))
    target = tmp_path / 'markers.pdf'
    engine.render_pdf_weasyprint(rendered, target, tmp_path)
    mapping = engine.read_page_map(target, engine.toc_keys(data))
    with pdfplumber.open(target) as pdf:
        texts = [page.extract_text() or '' for page in pdf.pages]
    for key, canary in zip(keys, ['SPACE_KEY_CANARY', 'COMPACT_KEY_CANARY', 'PERCENT_KEY_CANARY']):
        assert key in mapping
        assert canary in texts[mapping[key] - 1], 'The page number must point to the correct body.'


def test_delivery_rejects_encoded_internal_marker_and_accepts_clean_final_pdf(tmp_path):
    import delivery
    data = document(); data['findings'] = []
    data['report'] = {'sections': [{'key': 'Appendix A', 'title': 'Appendix', 'body': 'FINAL_BODY_CANARY'}]}
    rendered = engine.render_html(engine.build_env(), data, tmp_path.resolve(), {}, True, engine.load_lang('en'))
    first = tmp_path / 'first-pass.pdf'; engine.render_pdf_weasyprint(rendered, first, tmp_path)
    with pytest.raises(ValueError, match='marcadores internos'):
        delivery.inspect_pdf(first, 0)
    mapping = engine.read_page_map(first, engine.toc_keys(data))
    final = tmp_path / 'final.pdf'
    rendered = engine.render_html(engine.build_env(), data, tmp_path.resolve(), mapping, False, engine.load_lang('en'))
    engine.render_pdf_weasyprint(rendered, final, tmp_path)
    assert delivery.inspect_pdf(final, 0)['pages'] > 0


@pytest.mark.parametrize('identity', ['conf', 'contacts', 'overview', 'summary', 'appendix'])
def test_legacy_short_name_finding_keeps_its_own_toc_destination(identity, tmp_path):
    import delivery
    data = document(); data['findings'][0]['id'] = identity
    data['findings'][0]['description_md'] = 'LEGACY_NAMESPACE_CANARY'
    data['findings'][0]['proof'] = [{'name': 'Synthetic proof', 'value': 'APPENDIX_BODY_CANARY'}]
    # An earlier long finding places this condition beyond the legacy summary,
    # so a swapped page number cannot accidentally pass on a shared page.
    data['findings'].insert(0, dict(data['findings'][0], id='F0', title='Earlier synthetic condition',
                                   description_md='Earlier synthetic condition.', proof=[],
                                   walkthrough=[{'text_md': '\n\n'.join(['Earlier synthetic documentation.'] * 30)}]))
    before = deepcopy(data)
    assert not [message for level, message in validate.validate(data) if level == 'error']
    keys = engine.toc_keys(data)
    assert len(keys) == len(set(keys)), 'Distinct report destinations need distinct page markers.'
    assert identity in keys and 'sec-' + identity in keys
    first = tmp_path / 'first-pass.pdf'
    rendered = engine.render_html(engine.build_env(), data, tmp_path.resolve(), {}, True, engine.load_lang('en'))
    engine.render_pdf_weasyprint(rendered, first, tmp_path)
    mapping = engine.read_page_map(first, keys)
    reader = PdfReader(first)
    destinations = reader.named_destinations
    def position(key):
        destination = destinations[key]
        return (reader.get_destination_page_number(destination) + 1,
                float(destination.left), float(destination.top))
    finding_position = position(identity)
    section_position = position('sec-' + identity)
    # Continuous chapters may share a page. Distinct native destination
    # coordinates, rather than distinct page numbers, establish identity.
    assert finding_position != section_position
    assert finding_position[0] == mapping[identity]
    assert section_position[0] == mapping['sec-' + identity]
    with pdfplumber.open(first) as pdf:
        page = pdf.pages[mapping[identity]-1]
        top = page.height - finding_position[2]
        bottom = page.height
        if section_position[0] == finding_position[0] and section_position[2] < finding_position[2]:
            bottom = page.height - section_position[2]
        finding_region = page.crop((finding_position[1], top, page.width, bottom))
        assert 'LEGACY_NAMESPACE_CANARY' in (finding_region.extract_text() or '')
    rendered = engine.render_html(engine.build_env(), data, tmp_path.resolve(), mapping, False, engine.load_lang('en'))
    final = tmp_path / 'final-pass.pdf'; engine.render_pdf_weasyprint(rendered, final, tmp_path)
    reader = PdfReader(final)
    destinations = reader.named_destinations
    assert position(identity) != position('sec-' + identity)
    assert delivery.inspect_pdf(final, 0)['toc_references_checked'] >= 6
    assert data == before


@pytest.mark.parametrize('field,invalid,override', [('lang', 'xx', 'en'), ('theme', 'unknown', 'serio')])
def test_cli_override_is_applied_before_final_metadata_validation(field, invalid, override, tmp_path):
    data = document(); data['meta'][field] = invalid
    source = tmp_path / 'engagement.yaml'; dump_yaml(data, source)
    before = source.read_bytes(); target = tmp_path / 'overridden.pdf'
    result = subprocess.run([sys.executable, str(Path(engine.__file__)), str(source), '-o', str(target),
                             '--backend', 'weasyprint', '--' + field, override], capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    assert target.is_file() and target.stat().st_size > 1000
    with pdfplumber.open(target) as pdf:
        assert 'Synthetic condition' in ''.join(page.extract_text() or '' for page in pdf.pages)
    assert source.read_bytes() == before
