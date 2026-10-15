"""SARIF observations stay offline, bounded, traceable and unverified."""
from copy import deepcopy
from hashlib import sha256
import base64
import json
from pathlib import Path
import socket
import urllib.request

import pytest
import app as api
import error_messages
import finding_imports as intake
import scanner_imports
import validate
import workflows
from wizard import dump_yaml
from _support import auth_client


def project():
    return workflows.normalize({'meta': {'report_title': 'Synthetic SARIF', 'theme': 'serio', 'lang': 'en'},
                                'findings': [], 'report': {'sections': []}})


def fixture():
    return {'version': '2.1.0', '$schema': 'https://json.schemastore.org/sarif-2.1.0.json', 'runs': [{
        'tool': {'driver': {'name': 'Synthetic scanner', 'version': '1.0', 'rules': [{
            'id': 'EXAMPLE001', 'name': 'ExampleObservation',
            'shortDescription': {'text': 'Synthetic source observation'},
            'defaultConfiguration': {'level': 'warning'},
            'properties': {'security-severity': '9.8', 'tags': ['external/cwe/cwe-89']}}]}},
        'originalUriBaseIds': {'ROOT': {'uri': 'file:///synthetic/project/'},
                              'SRC': {'uri': 'src/', 'uriBaseId': 'ROOT'}},
        'artifacts': [{'location': {'uri': 'app.py', 'uriBaseId': 'SRC'}}],
        'results': [{'ruleId': 'EXAMPLE001', 'ruleIndex': 0,
            'level': 'error', 'message': {'text': 'Potential observation; requires human verification.'},
            'locations': [{'physicalLocation': {'artifactLocation': {'index': 0},
                                               'region': {'startLine': 12, 'startColumn': 3}}}],
            'fingerprints': {'synthetic/v1': 'opaque-trustless-identifier'},
            'partialFingerprints': {'lineHash/v1': 'abcdef'}, 'suppressions': []}]}]}


def body(document=None, **extra):
    return {'format': 'sarif', 'text': json.dumps(fixture() if document is None else document, ensure_ascii=False), **extra}


def first(document):
    return document['runs'][0]['results'][0]


def preview(document=None, data=None):
    return intake.preview(body(document), project() if data is None else data)


def test_import_retains_provenance_and_no_implicit_risk_or_confirmation():
    document, data = fixture(), project()
    before = deepcopy(data)
    result = preview(document, data)
    assert data == before
    assert result['kind'] == 'findings'
    assert result['counts'] == {'rows': 1, 'valid': 1, 'duplicates': 0, 'excluded': 0}
    updated, count = intake.apply(body(document, selected=[0]), data)
    finding = updated['findings'][0]
    assert count == 1 and data == before
    assert finding['severity'] == 'info' and finding['verification'] == 'unverified'
    assert finding['status'] == 'open' and finding['cvss_vector'] == finding['cwe'] == ''
    assert 'cvss' not in finding and finding['references'] == finding['walkthrough'] == []
    source = finding['import_source']
    assert source['format'] == 'sarif' and source['reviewed'] is False
    assert source['tool'] == {'name': 'Synthetic scanner', 'version': '1.0'}
    assert source['level'] == 'error' and source['level_explicit'] is True
    assert source['rule_id'] == 'EXAMPLE001' and source['rule_index'] == 0
    assert source['fingerprints'] == first(document)['fingerprints']
    assert source['partialFingerprints'] == first(document)['partialFingerprints']
    assert source['record_sha256'] == sha256(scanner_imports._sarif_json(first(document))).hexdigest()
    assert source['message'] == first(document)['message']
    assert source['locations'][0]['original'] == first(document)['locations'][0]
    assert finding['affected'] == 'file:///synthetic/project/src/app.py:12:3'
    assert not validate.structure_issues(updated)
    assert any(issue['level'] == 'error' and 'import awaiting review' in issue['message']
               for issue in workflows.review(updated, Path('.')))
    source['reviewed'] = True
    assert finding['verification'] == 'unverified'


def test_no_schema_uri_or_source_file_is_opened(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('SARIF import must never perform source/network I/O')
    monkeypatch.setattr(Path, 'read_bytes', forbidden)
    monkeypatch.setattr(Path, 'read_text', forbidden)
    monkeypatch.setattr(urllib.request, 'urlopen', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)
    document = fixture()
    document['$schema'] = 'file:///etc/passwd'
    first(document)['locations'][0]['physicalLocation']['artifactLocation'] = {'uri': 'https://example.invalid/source.py'}
    assert preview(document)['rows'][0]['finding']['affected'].startswith('https://example.invalid/')


def test_original_utf8_bom_and_unmodified_document_hash():
    original = b'\xef\xbb\xbf' + body()['text'].encode('utf-8')
    result = intake.preview(body(bytes_base64=base64.b64encode(original).decode()), project())
    source = result['rows'][0]['finding']['import_source']
    assert result['sha256'] == source['file_sha256'] == sha256(original).hexdigest()
    assert source['hash_scope'] == 'original_bytes'
    assert source['normalized_sha256'] == sha256(original[3:]).hexdigest()


def test_multiple_runs_duplicates_exact_context_and_reimport_after_author_edits():
    document = fixture()
    duplicate = deepcopy(first(document))
    other_line = deepcopy(duplicate)
    other_line['locations'][0]['physicalLocation']['region']['startLine'] = 13
    document['runs'][0]['results'].extend([duplicate, other_line])
    second_run = deepcopy(document['runs'][0])
    second_run['tool']['driver']['name'] = 'Another scanner'
    second_run['results'] = [deepcopy(duplicate)]
    document['runs'].append(second_run)
    rows = preview(document)['rows']
    assert [row['duplicate'] for row in rows] == [False, True, False, False]
    assert rows[3]['finding']['import_source']['run_index'] == 1
    updated, count = intake.apply(body(document, selected=[1, 2, 3]), project())
    assert count == 3
    updated['findings'][0]['title'] = 'Author title'
    updated['findings'][0]['affected'] = 'Author scope'
    assert [row['existing_duplicate'] for row in preview(document, updated)['rows']] == [True] * 4
    with pytest.raises(ValueError):
        intake.apply(body(document, selected=[0]), updated)
    untouched = project()
    with pytest.raises(ValueError):
        intake.apply(body(document, selected=[0, 1]), untouched)
    assert untouched['findings'] == []


def test_location_index_and_equivalent_inline_reference_share_identity():
    indexed = preview()['rows'][0]['finding']['import_source']['fingerprint']
    document = fixture()
    first(document)['locations'][0]['physicalLocation']['artifactLocation'] = {
        'uri': 'file:///synthetic/project/src/app.py'}
    inline = preview(document)['rows'][0]['finding']['import_source']['fingerprint']
    assert inline == indexed
    first(document)['locations'][0]['physicalLocation']['artifactLocation']['index'] = 0
    assert preview(document)['rows'][0]['finding']['import_source']['fingerprint'] == indexed


def test_unresolved_base_is_preserved_without_guessing_a_local_directory():
    document = fixture()
    document['runs'][0].pop('originalUriBaseIds')
    location = preview(document)['rows'][0]['finding']['import_source']['locations'][0]
    assert location['uri'] == 'app.py' and location['unresolved_base_id'] == 'SRC'
    assert preview(document)['rows'][0]['finding']['affected'] == 'SRC: app.py:12:3'


@pytest.mark.parametrize('level', ['error', 'warning', 'note'])
def test_scanner_level_never_maps_to_report_risk(level):
    document = fixture(); first(document)['level'] = level
    finding = preview(document)['rows'][0]['finding']
    assert finding['severity'] == 'info' and finding['import_source']['level'] == level


@pytest.mark.parametrize('state', ['accepted', 'underReview', ''])
def test_pending_or_accepted_suppressions_are_visible_but_unselectable(state):
    document = fixture()
    row = deepcopy(first(document))
    row['suppressions'] = [{'kind': 'inSource', **({'status': state} if state else {})}]
    document['runs'][0]['results'].append(row)
    result = preview(document)
    assert result['counts']['valid'] == 1 and result['counts']['excluded'] == 1
    assert result['rows'][1]['excluded'] is True and result['rows'][1]['errors']
    assert result['rows'][1]['finding']['import_source']['suppressions'] == row['suppressions']
    assert intake.apply(body(document, selected=[0]), project())[1] == 1
    with pytest.raises(ValueError):
        intake.apply(body(document, selected=[0, 1]), project())


def test_rejected_suppression_is_still_only_an_unverified_observation():
    document = fixture()
    first(document)['suppressions'] = [{'kind': 'external', 'status': 'rejected'}]
    finding = preview(document)['rows'][0]
    assert not finding['errors'] and finding['finding']['verification'] == 'unverified'


@pytest.mark.parametrize('changes', [{'baselineState': 'absent'}, {'level': 'none'},
    *({'kind': kind, 'level': 'none'} for kind in ['pass', 'notApplicable', 'review', 'open', 'informational'])])
def test_absent_and_non_active_observations_cannot_be_imported(changes):
    document = fixture(); first(document).update(changes)
    result = preview(document)
    assert result['counts']['excluded'] == 1 and result['counts']['valid'] == 0
    with pytest.raises(ValueError):
        intake.apply(body(document, selected=[0]), project())


def test_message_text_wins_markdown_is_literal_and_arguments_are_not_code():
    document = fixture()
    first(document)['message'] = {'text': 'Use {0} literally {{value}}.', 'markdown': '**not selected**',
                                  'arguments': ['<script>alert(1)</script>']}
    finding = preview(document)['rows'][0]['finding']
    assert finding['import_source']['message_text'] == 'Use <script>alert(1)</script> literally {value}.'
    assert '<script>' not in finding['description_md']
    assert '&lt;script&gt;' in finding['description_md'] and '**not selected**' not in finding['description_md']
    first(document)['message'] = {'markdown': '![external](https://example.invalid/a.png)\n<script>bad</script>'}
    finding = preview(document)['rows'][0]['finding']
    assert finding['import_source']['message_format'] == 'markdown'
    assert finding['description_md'].startswith(r'\!\[external\]\(https://example\.invalid/a\.png\)')
    assert '\n&lt;script&gt;' in finding['description_md']


def test_message_id_uses_driver_rule_catalog_and_rule_index_identity():
    document = fixture()
    first(document).pop('ruleId')
    first(document).pop('level')
    first(document)['message'] = {'id': 'diagnostic', 'arguments': ['42']}
    document['runs'][0]['tool']['driver']['rules'][0]['messageStrings'] = {'diagnostic': {'text': 'Observed {0}.'}}
    finding = preview(document)['rows'][0]['finding']
    assert finding['import_source']['message_text'] == 'Observed 42.'
    assert finding['import_source']['rule_id'] == 'EXAMPLE001'
    assert finding['import_source']['level'] == 'warning' and not finding['import_source']['level_explicit']


def test_hierarchical_rule_id_and_descriptor_reference():
    document = fixture()
    first(document)['ruleId'] = 'EXAMPLE001/subset'
    first(document)['rule'] = {'id': 'EXAMPLE001/subset', 'index': 0}
    assert preview(document)['rows'][0]['finding']['import_source']['rule_id'] == 'EXAMPLE001/subset'


def test_no_location_and_logical_location_are_explicit():
    document = fixture(); first(document).pop('locations')
    assert preview(document)['rows'][0]['finding']['affected'] == ''
    first(document)['locations'] = [{'logicalLocations': [{'fullyQualifiedName': 'synthetic.module.function'}]}]
    assert preview(document)['rows'][0]['finding']['affected'] == 'synthetic.module.function'


@pytest.mark.parametrize('raw', ['[]', 'null', '{}', '{', '{"version":"2.1.0","version":"2.1.0"}',
    '{"version":"2.1.0","runs":null}', '{"version":"2.0.0","runs":[]}',
    '{"version":"2.1.0","runs":[]}'])
def test_invalid_documents(raw):
    with pytest.raises(ValueError):
        intake.preview({'format': 'sarif', 'text': raw}, project())


@pytest.mark.parametrize('changes', [
    {'ruleIndex': True}, {'ruleIndex': -2}, {'ruleIndex': 1}, {'ruleId': 'CONFLICT'},
    {'rule': {'id': 'CONFLICT'}}, {'rule': {'index': 1}}, {'rule': {'toolComponent': {'name': 'extension'}}},
    {'ruleId': []}, {'message': None}, {'message': {'text': 7}}, {'message': {'id': 'missing'}},
    {'message': {'text': '{1}', 'arguments': ['zero']}}, {'message': {'text': 'text', 'arguments': [7]}},
    {'locations': {}}, {'locations': [{}]}, {'level': 'critical'}, {'kind': 'confirmed'},
    {'kind': 'pass', 'level': 'error'}, {'baselineState': 'fixed'},
    {'fingerprints': []}, {'fingerprints': {'key': 4}}, {'partialFingerprints': None},
    {'suppressions': {}}, {'suppressions': [{'kind': 'bad'}]},
    {'suppressions': [{'kind': 'inSource', 'status': 'confirmed'}]},
])
def test_malformed_or_conflicting_results_fail_atomically(changes):
    document = fixture(); first(document).update(changes)
    original = project()
    with pytest.raises(ValueError):
        intake.apply(body(document, selected=[0]), original)
    assert original['findings'] == []


@pytest.mark.parametrize('location', [
    {'index': True}, {'index': -1}, {'index': 1}, {'uri': 'different.py', 'index': 0},
    {'uri': 'file:///a.py', 'uriBaseId': 'ROOT'}, {'uri': 'bad path.py'}, {'uri': 'a\\b.py'},
    {'uri': 'https://[invalid'}, {},
])
def test_artifact_reference_conflicts_or_bad_uri_rejected(location):
    document = fixture()
    first(document)['locations'][0]['physicalLocation']['artifactLocation'] = location
    with pytest.raises(ValueError):
        preview(document)


@pytest.mark.parametrize('region', [{'startLine': True}, {'startLine': 0}, {'startColumn': -1},
    {'startLine': 5, 'endLine': 4}, {'startLine': 5, 'startColumn': 9, 'endColumn': 2},
    {'byteOffset': -1}, {'byteLength': '4'}])
def test_invalid_location_ranges(region):
    document = fixture(); first(document)['locations'][0]['physicalLocation']['region'] = region
    with pytest.raises(ValueError):
        preview(document)


def test_uri_base_and_artifact_cycles_are_rejected():
    document = fixture()
    document['runs'][0]['originalUriBaseIds']['ROOT'] = {'uri': 'root/', 'uriBaseId': 'SRC'}
    with pytest.raises(ValueError):
        preview(document)
    document = fixture()
    document['runs'][0]['artifacts'][0]['location'] = {'index': 0}
    with pytest.raises(ValueError):
        preview(document)


@pytest.mark.parametrize('field', ['externalPropertyFileReferences', 'inlineExternalProperties'])
def test_external_property_fragments_are_explicitly_rejected(field):
    document = fixture()
    if field == 'externalPropertyFileReferences':
        document['runs'][0][field] = {'results': [{'location': {'uri': 'https://example.invalid/results.sarif-external-properties'}}]}
    else:
        document[field] = [{'results': [first(document)]}]
    with error_messages.language_scope('en'), pytest.raises(ValueError, match='self-contained'):
        preview(document)


def test_invocation_override_requires_explicit_level():
    document = fixture()
    first(document).pop('level')
    document['runs'][0]['invocations'] = [{'executionSuccessful': True, 'ruleConfigurationOverrides': [
        {'descriptor': {'id': 'EXAMPLE001'}, 'configuration': {'level': 'none'}}]}]
    with pytest.raises(ValueError, match='ruleConfigurationOverrides'):
        preview(document)
    first(document)['level'] = 'none'
    assert preview(document)['rows'][0]['excluded']


def test_input_record_count_reference_depth_and_output_budgets(monkeypatch):
    document = fixture()
    document['runs'][0]['results'] *= 501
    with pytest.raises(ValueError):
        preview(document)
    document = fixture(); document['runs'] *= 51
    with pytest.raises(ValueError):
        preview(document)
    document = fixture(); first(document)['properties'] = {'large': 'x' * 65536}
    with pytest.raises(ValueError):
        preview(document)
    document = fixture(); document['runs'][0]['tool']['driver']['rules'] *= 10001
    with pytest.raises(ValueError):
        preview(document)
    with pytest.raises(ValueError):
        intake.preview({'format': 'sarif', 'text': 'x' * (intake.MAX_BYTES + 1)}, project())
    document = fixture()
    bases = document['runs'][0]['originalUriBaseIds']
    for index in range(34):
        bases[f'B{index}'] = {'uri': 'dir/', 'uriBaseId': f'B{index + 1}'}
    bases['SRC'] = {'uri': 'src/', 'uriBaseId': 'B0'}
    with pytest.raises(ValueError):
        preview(document)
    monkeypatch.setattr(scanner_imports, 'MAX_SARIF_OUTPUT_BYTES', 32)
    with pytest.raises(ValueError):
        preview()


@pytest.mark.parametrize('language, expected', [('es', 'valor inválido'), ('en', 'invalid or conflicting'), ('pt', 'valor inválido')])
def test_new_errors_and_notices_are_localized(language, expected):
    document = fixture(); first(document)['ruleIndex'] = -2
    with error_messages.language_scope(language):
        with pytest.raises(ValueError, match=expected):
            preview(document)
        notice = preview()['notice']
    assert {'es': 'revisión humana', 'en': 'human review', 'pt': 'revisão humana'}[language] in notice


@pytest.mark.parametrize('selected', [[], [True], [-1], [1], [0, 0], '0', None])
def test_invalid_selected_rows(selected):
    original = project()
    with pytest.raises(ValueError):
        intake.apply(body(selected=selected), original)
    assert not original['findings']


def test_api_revision_guard_atomic_apply_history_and_reimport(tmp_path, monkeypatch):
    projects = tmp_path / 'projects'; projects.mkdir()
    directory = projects / 'synthetic'; directory.mkdir()
    dump_yaml(project(), directory / 'engagement.yaml')
    monkeypatch.setattr(api, 'PROJECTS', projects)
    client = auth_client(api.app)
    endpoint = '/api/projects/synthetic/intake/'
    before = (directory / 'engagement.yaml').read_bytes()
    revision = client.get('/api/projects/synthetic').headers['ETag']
    assert client.post(endpoint + 'preview', json=body(), headers={'If-Match': revision}).status_code == 200
    assert (directory / 'engagement.yaml').read_bytes() == before
    assert client.post(endpoint + 'apply', json=body(selected=[0])).status_code == 428
    assert client.post(endpoint + 'apply', json=body(selected=[0]), headers={'If-Match': 'stale'}).status_code == 409
    assert client.post(endpoint + 'apply', json=body(selected=[0, 99]), headers={'If-Match': revision}).status_code == 422
    assert (directory / 'engagement.yaml').read_bytes() == before
    response = client.post(endpoint + 'apply', json=body(selected=[0]), headers={'If-Match': revision})
    assert response.status_code == 200, response.json
    assert response.json['import_kind'] == 'findings'
    saved = client.get('/api/projects/synthetic').json
    assert len(saved['findings']) == 1 and saved['findings'][0]['verification'] == 'unverified'
    assert saved['findings'][0]['import_source']['reviewed'] is False
    assert len(client.get('/api/projects/synthetic/history').json) >= 2
    assert client.post(endpoint + 'apply', json=body(selected=[0]), headers={'If-Match': response.headers['ETag']}).status_code == 422


def test_literal_braces_and_missing_argument_fail_without_truthiness_shortcuts():
    document = fixture(); first(document)['message'] = {'text': 'Use {{x}} and {{}}.'}
    assert preview(document)['rows'][0]['finding']['import_source']['message_text'] == 'Use {x} and {}.'
    for invalid in ['Missing {0}.', 'Unbalanced {brace', 'Unbalanced }', '{' + '1' * 6000 + '}']:
        first(document)['message'] = {'text': invalid}
        with pytest.raises(ValueError):
            preview(document)


def test_expansion_budget_stops_before_materializing_large_repetition(monkeypatch):
    # A tiny artificial limit demonstrates that repeated substitutions stop at
    # the same pre-append boundary used for real 16 KiB message budgets.
    document = fixture()
    first(document)['message'] = {'text': '{0}' * 20, 'arguments': ['x' * 60]}
    monkeypatch.setattr(scanner_imports, 'MAX_SARIF_TEXT', 100)
    with pytest.raises(ValueError, match='message.expanded'):
        preview(document)


def test_rule_guid_lookup_conflicts_duplicate_ids_and_unknown_index():
    document = fixture()
    guid = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    document['runs'][0]['tool']['driver']['rules'][0]['guid'] = guid
    first(document)['rule'] = {'guid': guid, 'index': 0}
    assert preview(document)['rows'][0]['finding']['import_source']['rule_reference']['guid'] == guid
    first(document)['rule']['guid'] = 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'
    with pytest.raises(ValueError, match='rule.guid'):
        preview(document)
    first(document).pop('rule')
    first(document)['ruleIndex'] = -1
    assert preview(document)['rows'][0]['finding']['import_source']['rule_index'] == 0
    first(document)['locations'][0]['physicalLocation']['artifactLocation'] = {'uri': 'app.py', 'index': -1}
    assert preview(document)['rows'][0]['finding']['affected'] == 'app.py:12:3'
    document['runs'][0]['tool']['driver']['rules'].append(deepcopy(document['runs'][0]['tool']['driver']['rules'][0]))
    with pytest.raises(ValueError, match='ambiguous'):
        preview(document)
    first(document)['ruleIndex'] = 0
    assert preview(document)['counts']['valid'] == 1


def test_repository_namespace_keeps_different_projects_distinct_but_revision_changes_dedup():
    document = fixture()
    run = document['runs'][0]
    run.pop('originalUriBaseIds')
    run['versionControlProvenance'] = [{'repositoryUri': 'https://example.invalid/repo-a.git', 'revisionId': '111'}]
    second = deepcopy(run)
    second['versionControlProvenance'][0]['repositoryUri'] = 'https://example.invalid/repo-b.git'
    document['runs'].append(second)
    result = preview(document)
    assert [row['duplicate'] for row in result['rows']] == [False, False]
    updated, count = intake.apply(body(document, selected=[0, 1]), project())
    assert count == 2
    assert updated['findings'][1]['import_source']['version_control_provenance'][0]['repositoryUri'].endswith('repo-b.git')
    run['versionControlProvenance'][0]['revisionId'] = '222'
    assert preview(document, updated)['rows'][0]['existing_duplicate']


def test_resolved_uri_budget_and_base_uri_constraints(monkeypatch):
    document = fixture()
    document['runs'][0]['originalUriBaseIds']['ROOT']['uri'] = 'file:///' + 'a' * 80 + '/'
    first(document)['locations'][0]['physicalLocation']['artifactLocation'] = {'uri': 'b' * 80 + '.py', 'uriBaseId': 'ROOT'}
    monkeypatch.setattr(scanner_imports, 'MAX_SARIF_TEXT', 100)
    with pytest.raises(ValueError, match='resolvedUri'):
        preview(document)
    for invalid in ['relative/', 'file:///root/?query=bad/', 'file:///root/#bad/', 'file:///root']:
        document['runs'][0]['originalUriBaseIds']['ROOT']['uri'] = invalid
        with pytest.raises(ValueError):
            preview(document)


def test_disabled_rule_and_bad_configuration_are_not_silently_active():
    document = fixture()
    document['runs'][0]['tool']['driver']['rules'][0]['defaultConfiguration']['enabled'] = False
    assert preview(document)['counts']['excluded'] == 1
    document['runs'][0]['tool']['driver']['rules'][0]['defaultConfiguration']['enabled'] = 'false'
    with pytest.raises(ValueError):
        preview(document)


def test_distinct_duplicate_rule_ids_with_guids_do_not_collapse_and_guid_resolves():
    document = fixture()
    rules = document['runs'][0]['tool']['driver']['rules']
    rules[0]['guid'] = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'
    rules.append({**deepcopy(rules[0]), 'guid': 'bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb'})
    second = deepcopy(first(document)); second['ruleIndex'] = 1
    document['runs'][0]['results'].append(second)
    assert [row['duplicate'] for row in preview(document)['rows']] == [False, False]
    second.pop('ruleIndex'); second['rule'] = {'guid': rules[1]['guid']}
    assert preview(document)['rows'][1]['finding']['import_source']['rule_index'] == 1
    # Reordering descriptors preserves both identities when references are fixed.
    before = [row['finding']['import_source']['fingerprint'] for row in preview(document)['rows']]
    rules.reverse(); first(document)['ruleIndex'] = 1
    assert [row['finding']['import_source']['fingerprint'] for row in preview(document)['rows']] == before


def test_distinct_duplicate_rule_ids_without_guids_use_descriptor_identity():
    document = fixture()
    rules = document['runs'][0]['tool']['driver']['rules']
    rules.append({**deepcopy(rules[0]), 'name': 'AnotherDescriptor'})
    second = deepcopy(first(document)); second['ruleIndex'] = 1
    document['runs'][0]['results'].append(second)
    assert [row['duplicate'] for row in preview(document)['rows']] == [False, False]


def test_malformed_artifacts_with_repository_mapping_are_validation_errors():
    document = fixture()
    document['runs'][0]['artifacts'] = None
    document['runs'][0]['versionControlProvenance'] = [{'repositoryUri': 'https://example.invalid/repo.git', 'mappedTo': {'index': 0}}]
    with pytest.raises(ValueError, match='artifacts'):
        preview(document)


def test_nested_artifact_and_indexed_logical_scopes_are_not_flattened():
    document = fixture()
    document['runs'][0]['artifacts'][0]['parentIndex'] = 1
    document['runs'][0]['artifacts'].append({'location': {'uri': 'archive.zip'}})
    with pytest.raises(ValueError, match='parentIndex'):
        preview(document)
    document = fixture()
    first(document)['locations'] = [{'logicalLocations': [{'name': 'same-name', 'index': 5}]}]
    with pytest.raises(ValueError, match='logicalLocation.index'):
        preview(document)
