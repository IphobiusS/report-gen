"""Synthetic, offline SARIF extension fixtures; no external scanner attribution."""
from copy import deepcopy
import socket
import urllib.request
from pathlib import Path

import pytest
import error_messages
import finding_imports as intake
import scanner_imports
import validate
from test_sarif_imports_0360 import body, fixture as driver_fixture, first, preview, project

DRIVER_GUID = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
PYTHON_GUID = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
JAVASCRIPT_GUID = 'cccccccc-cccc-4ccc-8ccc-cccccccccccc'


def fixture():
    """Two deliberately synthetic plugins with colliding local rule IDs."""
    document = driver_fixture()
    tool = document['runs'][0]['tool']
    tool['driver'].update(name='Synthetic pipeline driver', guid=DRIVER_GUID,
                          globalMessageStrings={'global': {'text': 'Driver-only diagnostic {0}.'}})
    rule = tool['driver']['rules'][0]
    rule['messageStrings'] = {'rule': {'text': 'Rule diagnostic for {0}.'}}
    tool['extensions'] = [
        {'name': 'Synthetic Python pack', 'guid': PYTHON_GUID, 'semanticVersion': '1.0.0',
         'informationUri': 'https://example.invalid/synthetic-python',
         'globalMessageStrings': {'global': {'text': 'Python diagnostic for {0}.'}},
         'rules': [deepcopy(rule)]},
        {'name': 'Synthetic JavaScript pack', 'guid': JAVASCRIPT_GUID, 'version': '2.0',
         'globalMessageStrings': {'global': {'text': 'JavaScript diagnostic for {0}.'}},
         'rules': [deepcopy(rule)]}]
    first(document)['rule'] = {'index': 0, 'toolComponent': {'index': 0}}
    return document


def extension(document, index=0):
    return document['runs'][0]['tool']['extensions'][index]


@pytest.mark.parametrize('reference', [
    {'index': 0}, {'guid': PYTHON_GUID}, {'index': -1, 'guid': PYTHON_GUID},
    {'name': 'Synthetic Python pack', 'index': 0},
    {'name': 'Synthetic Python pack', 'guid': PYTHON_GUID},
    {'index': 0, 'name': 'Synthetic Python pack', 'guid': PYTHON_GUID.upper()},
])
def test_extension_selection_preserves_pending_state_provenance_and_original_reference(reference):
    document = fixture(); first(document)['rule']['toolComponent'] = reference
    before = project(); expected = deepcopy(before)
    result = preview(document, before)
    assert before == expected and result['counts']['valid'] == 1
    updated, count = intake.apply(body(document, selected=[0]), before)
    finding = updated['findings'][0]; source = finding['import_source']
    assert count == 1 and before == expected
    assert source['tool']['name'] == 'Synthetic pipeline driver'
    assert source['tool_component_kind'] == 'extension' and source['tool_component_index'] == 0
    assert source['tool_component'] == {key: extension(document)[key] for key in
                                       ('name', 'guid', 'semanticVersion', 'informationUri')}
    assert source['rule_reference']['toolComponent'] == reference
    assert source['rule_id'] == 'EXAMPLE001' and source['rule_index'] == 0
    assert 'Synthetic Python pack' in finding['title']
    assert source['reviewed'] is False and finding['verification'] == 'unverified'
    assert finding['severity'] == 'info' and finding['cvss_vector'] == finding['cwe'] == ''
    assert 'cvss' not in finding and finding['references'] == finding['walkthrough'] == []
    assert not validate.structure_issues(updated)


@pytest.mark.parametrize('reference', [{}, {'name': 'Synthetic pipeline driver'}, {'index': -1},
    {'guid': DRIVER_GUID}, {'index': -1, 'guid': DRIVER_GUID, 'name': 'Synthetic pipeline driver'}])
def test_driver_references_and_unknown_index_select_driver_not_last_extension(reference):
    document = fixture(); first(document)['rule']['toolComponent'] = reference
    source = preview(document)['rows'][0]['finding']['import_source']
    assert source['tool_component_kind'] == 'driver' and source['tool_component_index'] is None
    assert source['tool_component']['name'] == 'Synthetic pipeline driver'
    first(document)['rule'].pop('toolComponent')
    assert source['fingerprint'] == preview(document)['rows'][0]['finding']['import_source']['fingerprint']


def test_driver_fingerprint_remains_compatible_with_published_0360():
    # Golden computed using scanner_imports.py at published main 69e130b.
    expected = 'd8799fb1e5ade8ecb8adfa400ac43ec5f5d75643098c456f6a6c78389718b445'
    source = preview()['rows'][0]['finding']['import_source']
    assert source['fingerprint'] == expected
    imported = project()
    imported['findings'] = [{'title': 'Edited by author', 'affected': 'Edited scope',
                             'import_source': {'format': 'sarif', 'fingerprint': expected}}]
    assert preview(data=imported)['rows'][0]['existing_duplicate'] is True


def test_driver_and_each_extension_with_identical_rule_context_remain_distinct():
    document = fixture()
    original = deepcopy(first(document))
    driver_result = deepcopy(original); driver_result['rule'].pop('toolComponent')
    second = deepcopy(original); second['rule']['toolComponent'] = {'index': 1}
    document['runs'][0]['results'] = [driver_result, original, second]
    rows = preview(document)['rows']
    assert [row['duplicate'] for row in rows] == [False, False, False]
    updated, count = intake.apply(body(document, selected=[0, 1, 2]), project())
    assert count == 3
    assert [row['existing_duplicate'] for row in preview(document, updated)['rows']] == [True] * 3
    updated['findings'][1]['title'] = 'Author title'
    assert preview(document, updated)['rows'][1]['existing_duplicate'] is True


def test_extension_reordering_and_equivalent_reference_styles_keep_identity():
    document = fixture()
    original = preview(document)['rows'][0]['finding']['import_source']['fingerprint']
    document['runs'][0]['tool']['extensions'].reverse()
    first(document)['rule']['toolComponent'] = {'index': 1}
    assert preview(document)['rows'][0]['finding']['import_source']['fingerprint'] == original
    first(document)['rule']['toolComponent'] = {'guid': PYTHON_GUID}
    assert preview(document)['rows'][0]['finding']['import_source']['fingerprint'] == original
    extension(document, 1)['name'] = 'Synthetic Python pack renamed'
    extension(document, 1)['semanticVersion'] = '2.0.0'
    assert preview(document)['rows'][0]['finding']['import_source']['fingerprint'] == original


def test_name_does_not_search_extensions():
    document = fixture()
    first(document)['rule']['toolComponent'] = {'name': 'Synthetic Python pack'}
    with pytest.raises(ValueError, match='toolComponent.name'):
        preview(document)


@pytest.mark.parametrize('reference', [None, [], 'extension',
    {'index': True}, {'index': 0.0}, {'index': -2}, {'index': 2}, {'index': '0'},
    {'index': 0, 'name': 'Synthetic JavaScript pack'}, {'index': 0, 'guid': JAVASCRIPT_GUID},
    {'index': 0, 'guid': DRIVER_GUID}, {'index': 0, 'guid': 'invalid-guid'},
    {'guid': 'dddddddd-dddd-4ddd-8ddd-dddddddddddd'}, {'guid': None},
    {'index': 0, 'name': None}, {'index': 0, 'name': ''},
    {'index': 0, 'properties': []}, {'index': 0, 'extensionName': 'Synthetic Python pack'}])
def test_bad_or_conflicting_component_references_are_atomic_validation_errors(reference):
    document = fixture(); first(document)['rule']['toolComponent'] = reference
    original = project(); before = deepcopy(original)
    with pytest.raises(ValueError):
        intake.apply(body(document, selected=[0]), original)
    assert original == before


@pytest.mark.parametrize('value', [None, {}, 'plugins', [None], [True], [{'rules': []}], [{'name': ''}]])
def test_bad_extension_collections_and_component_shapes_fail(value):
    document = fixture(); document['runs'][0]['tool']['extensions'] = value
    with pytest.raises(ValueError):
        preview(document)


def test_duplicate_component_guids_are_rejected_even_when_index_is_supplied():
    document = fixture(); extension(document, 1)['guid'] = PYTHON_GUID.upper()
    with pytest.raises(ValueError, match='ambiguous'):
        preview(document)
    document = fixture(); extension(document)['guid'] = DRIVER_GUID
    with pytest.raises(ValueError, match='ambiguous'):
        preview(document)


def test_missing_or_conflicting_component_guid_cannot_be_guessed():
    document = fixture(); extension(document).pop('guid')
    first(document)['rule']['toolComponent'] = {'index': 0, 'guid': PYTHON_GUID}
    with pytest.raises(ValueError, match='toolComponent.guid'):
        preview(document)
    first(document)['rule']['toolComponent'] = {'guid': PYTHON_GUID}
    with pytest.raises(ValueError, match='toolComponent.guid'):
        preview(document)


def test_without_guids_duplicate_names_keep_distinct_components_and_array_order_independence():
    document = fixture()
    for component in document['runs'][0]['tool']['extensions']:
        component.pop('guid'); component['name'] = 'Synthetic language pack'
    second = deepcopy(first(document)); second['rule']['toolComponent'] = {'index': 1}
    document['runs'][0]['results'].append(second)
    rows = preview(document)['rows']
    assert [row['duplicate'] for row in rows] == [False, False]
    keys = [row['finding']['import_source']['fingerprint'] for row in rows]
    document['runs'][0]['tool']['extensions'].reverse()
    first(document)['rule']['toolComponent'] = {'index': 1}
    second['rule']['toolComponent'] = {'index': 0}
    assert [row['finding']['import_source']['fingerprint'] for row in preview(document)['rows']] == keys


def test_duplicate_extension_objects_are_rejected():
    document = fixture(); extension(document).pop('guid')
    document['runs'][0]['tool']['extensions'] = [extension(document), deepcopy(extension(document))]
    with pytest.raises(ValueError, match='duplicate'):
        preview(document)


@pytest.mark.parametrize('message, expected', [
    ({'text': 'Literal {0}.', 'id': 'global', 'arguments': ['source']}, 'Literal source.'),
    ({'id': 'rule', 'arguments': ['source']}, 'Rule diagnostic for source.'),
    ({'id': 'global', 'arguments': ['source']}, 'Python diagnostic for source.'),
])
def test_message_lookup_uses_selected_component_catalog(message, expected):
    document = fixture(); first(document)['message'] = message
    source = preview(document)['rows'][0]['finding']['import_source']
    assert source['message_text'] == expected


def test_extension_missing_message_never_borrows_driver_or_other_extension_catalog():
    document = fixture(); first(document)['message'] = {'id': 'global', 'arguments': ['source']}
    extension(document)['globalMessageStrings'] = {}
    with pytest.raises(ValueError, match='message.id'):
        preview(document)


def test_rule_lookup_is_scoped_to_component_and_defaults_stay_informational():
    document = fixture(); first(document).pop('level')
    extension(document)['rules'][0]['defaultConfiguration']['level'] = 'note'
    row = preview(document)['rows'][0]
    assert row['finding']['import_source']['level'] == 'note'
    assert row['finding']['severity'] == 'info'
    extension(document)['rules'][0]['defaultConfiguration']['enabled'] = False
    assert preview(document)['rows'][0]['excluded'] is True
    extension(document)['rules'] = []
    with pytest.raises(ValueError, match='ruleIndex'):
        preview(document)


def test_extension_rule_guid_does_not_resolve_identical_driver_rule_id():
    document = fixture()
    driver_rule = document['runs'][0]['tool']['driver']['rules'][0]
    driver_rule['guid'] = DRIVER_GUID
    extension(document)['rules'][0]['guid'] = PYTHON_GUID
    first(document)['rule']['guid'] = DRIVER_GUID
    with pytest.raises(ValueError, match='rule.guid'):
        preview(document)
    first(document)['rule']['guid'] = PYTHON_GUID
    assert preview(document)['rows'][0]['finding']['import_source']['rule_descriptor_identity'] == PYTHON_GUID


def test_extension_rules_do_not_override_trusted_review_and_risk_fields():
    document = fixture()
    first(document).update(verification='confirmed', severity='critical', cvss=10,
                           import_source={'reviewed': True, 'format': 'csv'})
    extension(document)['rules'][0]['properties'].update(verification='confirmed', cvss='10.0')
    updated, _ = intake.apply(body(document, selected=[0]), project())
    finding = updated['findings'][0]
    assert finding['verification'] == 'unverified' and finding['severity'] == 'info'
    assert finding['import_source']['reviewed'] is False and finding['import_source']['format'] == 'sarif'
    assert 'cvss' not in finding


def test_extension_import_has_no_network_or_file_reads(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Offline extension import attempted I/O')
    monkeypatch.setattr(Path, 'read_text', forbidden)
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    document = fixture()
    extension(document).update(downloadUri='file:///never/read/plugin', informationUri='https://example.invalid/plugin')
    assert preview(document)['counts']['valid'] == 1


def test_extension_count_aggregate_rules_and_message_expansion_are_bounded(monkeypatch):
    document = fixture()
    document['runs'][0]['tool']['extensions'] *= 51
    with pytest.raises(ValueError, match='tool.extensions'):
        preview(document)
    document = fixture()
    monkeypatch.setattr(scanner_imports, 'MAX_SARIF_REFERENCES', 2)
    with pytest.raises(ValueError, match=r'driver \+ extensions'):
        preview(document)
    monkeypatch.setattr(scanner_imports, 'MAX_SARIF_REFERENCES', 10000)
    monkeypatch.setattr(scanner_imports, 'MAX_SARIF_TEXT', 100)
    document = fixture()
    extension(document)['globalMessageStrings']['global'] = {'text': '{0}' * 20}
    first(document)['message'] = {'id': 'global', 'arguments': ['x' * 60]}
    with pytest.raises(ValueError, match='message.expanded'):
        preview(document)


@pytest.mark.parametrize('language, expected', [('es', 'valor inválido'), ('en', 'invalid or conflicting'), ('pt', 'valor inválido')])
def test_component_validation_is_localized(language, expected):
    document = fixture(); first(document)['rule']['toolComponent'] = {'index': 0, 'name': 'Wrong component'}
    with error_messages.language_scope(language), pytest.raises(ValueError, match=expected):
        preview(document)


def test_same_name_plugins_without_guids_in_separate_runs_cannot_false_merge():
    document = fixture()
    one = extension(document); one.pop('guid'); one['name'] = 'Synthetic language pack'
    document['runs'][0]['tool']['extensions'] = [one]
    another = deepcopy(document['runs'][0])
    another['tool']['extensions'][0]['informationUri'] = 'https://example.invalid/a-distinct-plugin'
    document['runs'].append(another)
    rows = preview(document)['rows']
    assert [row['duplicate'] for row in rows] == [False, False]
    source = rows[0]['finding']['import_source']
    assert source['tool_component_identity']['component_sha256'] == scanner_imports.sha256(scanner_imports._sarif_json(one)).hexdigest()
    updated, count = intake.apply(body(document, selected=[0, 1]), project())
    assert count == 2
    assert [row['existing_duplicate'] for row in preview(document, updated)['rows']] == [True, True]


def test_extension_reference_cannot_bypass_external_property_rejection():
    document = fixture()
    document['runs'][0]['externalPropertyFileReferences'] = {'extensions': [
        {'location': {'uri': 'https://example.invalid/external.sarif'}, 'itemCount': 1}]}
    with error_messages.language_scope('en'), pytest.raises(ValueError, match='self-contained'):
        preview(document)
