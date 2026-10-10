"""Last publication audit: nullable display values and portable ID budgets."""
from copy import deepcopy
import re

from lxml import html
import pytest

import engine
import export
import export_contract
import validate
import workflows
from wizard import dump_yaml

MAX_SEQUENCE = 2**53 - 1


def nullable_document(sections):
    data = {'meta': {'lang': 'es', 'theme': 'serio', 'report_title': None,
                     'contacts': {'client': [{'name': None, 'title': None, 'email': None}]},
                     'scope': [{'target': None, 'description': None}]},
            'findings': [{'id': 'F1', 'mode': 'vuln', 'title': None, 'severity': 'info', 'cvss': 0,
                          'affected': None, 'description_md': 'NULL_BOUNDARY_CANARY',
                          'proof': [{'name': None, 'value': None, 'notes': None},
                                    {'name': 'Numeric zero', 'value': 0, 'notes': 'ZERO_CANARY'}]}]}
    if sections:
        data['report'] = {'sections': [{'key': 'contacts'}, {'key': 'scope'},
                           {'key': 'document_control', 'version_history': [{'version': None, 'date': None, 'author': None, 'notes': None}]},
                           {'key': 'findings'}, {'key': 'appendix'}]}
    return data


@pytest.mark.parametrize('sections', [False, True])
def test_nullable_display_data_never_becomes_none_text_and_numeric_zero_stays(sections, tmp_path):
    data = nullable_document(sections)
    before = deepcopy(data)
    assert not [m for lev, m in validate.validate(data) if lev == 'error']
    tree = html.document_fromstring(engine.render_html(engine.build_env(), data, tmp_path.resolve(), {}, False, engine.load_lang('es')))
    text = tree.text_content()
    assert not re.search(r'\bNone\b', text), 'An absent value must not be printed as Python None.'
    assert tree.xpath('//code[text()="0"]'), 'A documented numeric zero remains visible.'
    assert 'NULL_BOUNDARY_CANARY' in text
    assert tree.xpath('string(//h1[contains(@class,"cv-title")])') == 'Informe sin título'
    assert tree.xpath('string(//title)') == 'Informe sin título'
    assert tree.xpath('string(//h2[contains(@class,"f-title")])') == 'F1'
    assert any(lev == 'warning' and 'report_title' in m for lev, m in validate.validate(data))
    assert data == before
    data['meta']['report_title'] = 'The literal word None remains'
    tree = html.document_fromstring(engine.render_html(engine.build_env(), data, tmp_path.resolve(), {}, False, engine.load_lang('es')))
    assert tree.xpath('string(//h1[contains(@class,"cv-title")])') == 'The literal word None remains'


@pytest.mark.parametrize('sections', [False, True])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_nullable_fields_export_without_false_data_or_source_mutation(sections, fmt, tmp_path):
    data = nullable_document(sections)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    source = (tmp_path / 'engagement.yaml').read_bytes()
    artifact = export.export(tmp_path / 'engagement.yaml', fmt, tmp_path / ('nullable.' + ('zip' if fmt == 'md' else fmt)))
    text = export_contract.profile(artifact, fmt)['text']
    assert not re.search(r'\bNone\b', text)
    assert 'NULL_BOUNDARY_CANARY' in text
    scoped = export_contract.profile(artifact, fmt, {'scopes': []})
    cover = scoped['']['text'] if fmt == 'pdf' else scoped['']['cover_text']
    assert 'Informe sin título' in cover
    assert 'ZERO_CANARY' in text
    assert (tmp_path / 'engagement.yaml').read_bytes() == source


@pytest.mark.parametrize('key', ['title', 'description_md', 'impact_md', 'remediation_md'])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_missing_required_field_warning_is_same_for_null_empty_and_absent(key, language, tmp_path):
    base = {'meta': {'lang': language}, 'findings': [{'id': 'F1', 'mode': 'vuln', 'title': 'Finding'}]}
    messages = []
    for state in ('null', 'empty', 'absent'):
        data = deepcopy(base)
        if state == 'absent': data['findings'][0].pop(key, None)
        else: data['findings'][0][key] = None if state == 'null' else ''
        before = deepcopy(data)
        issue = [row for row in workflows.review(data, tmp_path, language) if row['path'] == 'findings[0].' + key]
        assert len(issue) == 1, 'Nullable missing content must stay visible in the review.'
        assert issue[0]['level'] == 'warning'
        messages.append(issue[0]['message'])
        assert data == before
    assert messages[0] == messages[1] == messages[2]


@pytest.mark.parametrize('score', [10**400, -(10**400)])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_huge_integer_cvss_is_controlled_validation_error(score, language):
    data = {'meta': {'report_title': 'Boundary'}, 'findings': [{'id': 'F1', 'cvss': score}]}
    before = deepcopy(data)
    assert validate.severity_from_score(score) is None
    errors = [m for lev, m in validate.validate(data, lang=language) if lev == 'error']
    assert any('cvss' in message.lower() for message in errors)
    assert data == before


@pytest.mark.parametrize('source', ['counter', 'finding', 'reference'])
def test_exhausted_sequence_rejects_allocation_without_mutation(source):
    data = {'findings': [{'id': 'F1'}]}
    if source == 'counter': data['finding_sequence'] = MAX_SEQUENCE
    elif source == 'finding': data['findings'][0]['id'] = 'F' + str(MAX_SEQUENCE)
    else: data['findings'][0]['description_md'] = 'Removed anchor: #F' + str(MAX_SEQUENCE)
    before = deepcopy(data)
    with pytest.raises(ValueError, match='contador de identificadores'):
        workflows.allocate_finding_id(data)
    assert data == before


@pytest.mark.parametrize('source', ['counter', 'finding', 'reference'])
def test_last_portable_identifier_is_allocated_once_then_remains_readable(source):
    data = {'meta': {'lang': 'es'}, 'findings': [{'id': 'F1'}]}
    if source == 'counter': data['finding_sequence'] = MAX_SEQUENCE - 1
    elif source == 'finding': data['findings'][0]['id'] = 'F' + str(MAX_SEQUENCE - 1)
    else: data['findings'][0]['description_md'] = 'Removed anchor: #F' + str(MAX_SEQUENCE - 1)
    assert workflows.allocate_finding_id(data) == 'F' + str(MAX_SEQUENCE)
    before = deepcopy(data)
    assert not validate.structure_issues(data)
    with pytest.raises(ValueError, match='contador de identificadores'):
        workflows.allocate_finding_id(data)
    assert data == before


@pytest.mark.parametrize('identity', ['F' + str(MAX_SEQUENCE + 1), 'F' + '9' * 5000])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_nonportable_numeric_identity_is_rejected_before_normalization(identity, language):
    data = {'findings': [{'id': identity}]}
    before = deepcopy(data)
    errors = [m for lev, m in validate.validate(data, lang=language) if lev == 'error']
    assert any('id' in message.lower() for message in errors)
    assert data == before
    with pytest.raises(ValueError, match='identificadores'):
        workflows.normalize(data)
    assert data == before


def test_unicode_identity_is_opaque_and_leading_zero_numeric_identity_reserves_number():
    data = {'findings': [{'id': 'F١'}, {'id': 'F00000000000000002'}]}
    assert workflows.allocate_finding_id(data) == 'F3'
    assert [f['id'] for f in data['findings']] == ['F١', 'F00000000000000002']
