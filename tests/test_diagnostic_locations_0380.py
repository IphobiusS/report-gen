"""Invalid real imports and altered exports identify known source coordinates."""
from copy import deepcopy
import json
import zipfile

from lxml import etree, html
from PIL import Image
import pytest

import delivery
import error_messages
import export
import finding_imports
import publication
import workflows
from diagnostic_locations import DiagnosticError, error_diagnostics, sanitize_diagnostics
from wizard import dump_yaml


def project():
    return workflows.normalize({'meta': {'report_title': 'Diagnostic case', 'lang': 'en', 'theme': 'corporativo'},
                                'findings': [], 'report': {'sections': []}})


def preview(kind, text, **extra):
    return finding_imports.preview(dict(format=kind, text=text, **extra), project())


@pytest.mark.parametrize('lang', ['es', 'en', 'pt'])
def test_csv_multiline_blank_rows_and_mapped_column_are_physical_coordinates(lang):
    raw = 'Risk,Name,Description\nlow,First,Valid\n\nUNKNOWN,Second,"Two\nlines"\n'
    mapping = {'title': 'Name', 'severity': 'Risk', 'description_md': 'Description'}
    with error_messages.language_scope(lang):
        rows = preview('csv', raw, mapping=mapping)['rows']
    assert not rows[0]['errors'] and not rows[0]['diagnostics']
    assert rows[1]['diagnostics'][0]['code'] == 'import.severity.unknown'
    assert rows[1]['diagnostics'][0]['location'] == {
        'operation': 'import', 'format': 'csv', 'record': 2, 'line': 4, 'line_end': 5,
        'field': 'severity', 'column': 1}
    assert rows[1]['diagnostics'][0]['message'] == rows[1]['errors'][0]
    assert 'UNKNOWN' not in json.dumps(rows[1]['diagnostics'])
    # Runtime-only diagnostics never become persistent scanner provenance.
    updated, count = finding_imports.apply(dict(format='csv', text=raw, mapping=mapping, selected=[0]), project())
    assert count == 1
    assert 'source_location' not in updated['findings'][0]
    assert '_source_location' not in updated['findings'][0]
    assert 'diagnostics' not in updated['findings'][0]['import_source']


def test_csv_failed_selection_retains_specific_fields_and_does_not_modify_project():
    data = project()
    before = deepcopy(data)
    with pytest.raises(DiagnosticError) as failure:
        finding_imports.apply(dict(format='csv', text='title,severity\n,unknown\n', selected=[0]), data)
    details = error_diagnostics(failure.value)
    assert [item['location']['field'] for item in details] == ['title', 'severity']
    assert all(item['location']['record'] == 1 and item['location']['line'] == 2 for item in details)
    assert data == before


def test_csv_bad_column_count_after_multiline_record_points_to_next_physical_line():
    raw = 'title,severity\n"First\ncontinued",low\nSecond,low,extra\n'
    with pytest.raises(DiagnosticError) as failure:
        preview('csv', raw)
    assert error_diagnostics(failure.value)[0]['location'] == {
        'operation': 'import', 'format': 'csv', 'record': 2, 'line': 4, 'line_end': 4}


def test_burp_bad_base64_points_to_second_issue_and_actual_xml_node():
    raw = ('<issues>\n<issue><name>First</name><severity>Low</severity></issue>\n'
           '<issue><name>Second</name><severity>Low</severity>\n<requestresponse>\n'
           '<request base64="true">not-valid@@</request>\n</requestresponse></issue>\n</issues>')
    with pytest.raises(DiagnosticError) as failure:
        preview('burp', raw)
    assert error_diagnostics(failure.value)[0]['location'] == {
        'operation': 'import', 'format': 'burp', 'record': 2, 'line': 5,
        'field': 'requestresponse[0].request'}
    assert 'not-valid' not in json.dumps(error_diagnostics(failure.value))


@pytest.mark.parametrize('kind,raw', [('burp', '<issues>\n<issue></issues>'),
                                     ('nmap', '<nmaprun>\n<host></nmaprun>')])
def test_xml_parser_reports_real_line_and_column_without_claiming_a_record(kind, raw):
    with pytest.raises(DiagnosticError) as failure:
        preview(kind, raw)
    location = error_diagnostics(failure.value)[0]['location']
    assert location['line'] == 2 and location['column'] > 1
    assert location['format'] == kind and 'record' not in location


def nuclei_record():
    return {'template-id': 'synthetic-check', 'matched-at': 'https://example.test/',
            'info': {'name': 'Observation', 'severity': 'low'}}


def test_nuclei_typed_nested_field_in_second_record_has_no_private_value():
    valid = nuclei_record()
    invalid = deepcopy(valid)
    invalid['info']['severity'] = {'credential': 'PRIVATE-CANARY-NOT-A-LOCATION'}
    with pytest.raises(DiagnosticError) as failure:
        preview('nuclei', json.dumps(valid) + '\n\n' + json.dumps(invalid))
    assert error_diagnostics(failure.value)[0]['location'] == {
        'operation': 'import', 'format': 'nuclei', 'record': 2, 'line': 3, 'field': 'info.severity'}
    assert 'PRIVATE-CANARY' not in json.dumps(error_diagnostics(failure.value))


def test_nuclei_syntax_error_uses_file_line_not_json_fragment_line():
    with pytest.raises(DiagnosticError) as failure:
        preview('nuclei', json.dumps(nuclei_record()) + '\n\n{"info": invalid}')
    assert error_diagnostics(failure.value)[0]['location'] == {
        'operation': 'import', 'format': 'nuclei', 'record': 2, 'line': 3, 'column': 10}


def test_nmap_second_host_bad_port_points_to_port_line():
    raw = ('<nmaprun>\n<host><address addr="192.0.2.1" addrtype="ipv4"/></host>\n'
           '<host><address addr="192.0.2.2" addrtype="ipv4"/>\n<ports>\n'
           '<port portid="65536" protocol="tcp"><state state="open"/></port>\n'
           '</ports></host></nmaprun>')
    with pytest.raises(DiagnosticError) as failure:
        preview('nmap', raw)
    assert error_diagnostics(failure.value)[0]['location'] == {
        'operation': 'import', 'format': 'nmap', 'record': 2, 'line': 5, 'field': 'ports.port'}


def sarif_document():
    result = {'ruleId': 'SYNTHETIC', 'message': {'text': 'Review required'},
              'locations': [{'physicalLocation': {'artifactLocation': {'uri': 'synthetic.py'},
                                                  'region': {'startLine': 5}}}]}
    return {'version': '2.1.0', 'runs': [{'tool': {'driver': {'name': 'Synthetic'}},
                                       'results': [result, deepcopy(result)]}]}


def test_sarif_bad_region_in_second_result_keeps_container_and_field_separate():
    document = sarif_document()
    document['runs'][0]['results'][1]['locations'][0]['physicalLocation']['region']['endLine'] = 3
    with pytest.raises(DiagnosticError) as failure:
        preview('sarif', json.dumps(document))
    assert error_diagnostics(failure.value)[0]['location'] == {
        'operation': 'import', 'format': 'sarif', 'record': 2, 'run_index': 0,
        'result_index': 1, 'field': 'region.endLine'}
    assert 'line' not in error_diagnostics(failure.value)[0]['location']


def test_sarif_excluded_result_has_diagnostic_without_changing_admission():
    document = sarif_document()
    document['runs'][0]['results'][1]['baselineState'] = 'absent'
    result = preview('sarif', json.dumps(document))
    assert result['counts']['valid'] == 1 and result['counts']['excluded'] == 1
    assert not result['rows'][0]['diagnostics']
    detail = result['rows'][1]['diagnostics'][0]
    assert detail['code'] == 'import.sarif.excluded'
    assert detail['location']['record'] == 2 and detail['location']['result_index'] == 1


def test_worker_diagnostic_sanitization_limits_and_rejects_content_coordinates():
    values = [{'code': 'export.invalid', 'message': 'x' * 1500, 'location': {
        'format': 'docx', 'operation': 'export', 'finding_id': 'F01', 'finding_uid': '0a123bc456',
        'field': 'tables', 'row': 2, 'cell': 3, 'table': True, 'line': -1,
        'path': '/private/secret.txt', 'value': 'SECRET', 'evidence_index': 0, 5: 'bad key'}}] * 80
    result = sanitize_diagnostics(values)
    assert len(result) == 64 and len(result[0]['message']) == 1200
    assert result[0]['location'] == {'format': 'docx', 'operation': 'export', 'finding_id': 'F01',
        'finding_uid': '0a123bc456', 'field': 'tables', 'row': 2, 'cell': 3, 'evidence_index': 0}
    assert error_diagnostics(ValueError('unstructured')) == []
    assert sanitize_diagnostics([None, {'code': '<script>', 'message': 'bad', 'location': {}}]) == []


@pytest.fixture
def html_report(tmp_path):
    data = project()
    data['report'] = {'sections': [{'key': 'findings_summary'}, {'key': 'findings'}]}
    data['findings'] = [{'id': 'F01', 'title': 'Synthetic financial control', 'mode': 'vuln',
        'severity': 'info', 'cvss': 0,
        'description_md': ('Distinct prose paragraph.\n\n| Phase | Approval |\n| --- | --- |\n'
                           '| Intake | Pending |\n| Release | Required |\n\n'
                           '![Evidence alpha](img/alpha.png)\n\n![Evidence beta](img/beta.png)'),
        'impact_md': 'Fictional impact only.', 'remediation_md': 'Review the proposed control.'}]
    workflows.normalize(data)
    (tmp_path / 'img').mkdir()
    for name, color in [('alpha', 'red'), ('beta', 'blue')]:
        Image.new('RGB', (30, 30), color).save(tmp_path / 'img' / (name + '.png'))
    dump_yaml(data, tmp_path / 'engagement.yaml')
    captured = publication.snapshot(tmp_path, tmp_path / 'snapshot')
    output = export.export(tmp_path / 'engagement.yaml', 'html', tmp_path / 'original.html')
    assert delivery.inspect_export(output, 'html', captured)['finding_association_checked']
    return tmp_path, output, captured


@pytest.mark.parametrize('mutation', ['cell', 'paragraph', 'evidence'])
def test_real_export_mutations_have_precise_private_diagnostics(html_report, mutation):
    directory, original, captured = html_report
    tree = html.document_fromstring(original.read_text())
    if mutation == 'cell':
        table = tree.xpath('//*[@id="F01"]//table[thead/tr/th[normalize-space(.)="Phase"]]')[0]
        table.xpath('./tbody/tr[2]/td[2]')[0].text = 'Tampered approval'
    elif mutation == 'paragraph':
        tree.xpath('//*[@id="F01"]//p[normalize-space(.)="Distinct prose paragraph."]')[0].text = 'Tampered prose'
    else:
        images = tree.xpath('//*[@id="F01"]//figure/img')
        assert len(images) == 2
        a, b = images[0].get('src'), images[1].get('src')
        images[0].set('src', b)
        images[1].set('src', a)
    altered = directory / 'altered.html'
    altered.write_text(html.tostring(tree, encoding='unicode'))
    with pytest.raises(DiagnosticError) as failure:
        delivery.inspect_export(altered, 'html', captured)
    location = error_diagnostics(failure.value)[0]['location']
    assert location['operation'] == 'export' and location['format'] == 'html' and location['finding_id'] == 'F01'
    assert 'finding_uid' not in location  # The published contract has no private UID.
    if mutation == 'cell':
        assert (location['table'], location['row'], location['cell']) == (1, 3, 2)
    elif mutation == 'paragraph':
        assert location['field'] == 'paragraphs' and 'cell' not in location
    else:
        assert location['field'] == 'images' and location['evidence_index'] == 0
    assert 'Tampered' not in json.dumps(error_diagnostics(failure.value))
    # Public contract and accepted verification receipts remain content/format
    # records; private diagnostics appear only on failure, not in deliveries.
    assert 'diagnostics' not in json.dumps(captured)


@pytest.mark.parametrize('fmt', ['docx', 'md'])
def test_word_and_markdown_changed_cell_retains_authored_table_coordinates(html_report, fmt):
    directory, _, captured = html_report
    source = export.export(directory / 'engagement.yaml', fmt, directory / ('original.' + fmt))
    assert delivery.inspect_export(source, fmt, captured)['finding_association_checked']
    with zipfile.ZipFile(source) as package:
        members = {name: package.read(name) for name in package.namelist()}
    if fmt == 'docx':
        namespaces = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        tree = etree.fromstring(members['word/document.xml'])
        table = tree.xpath('//w:tbl[w:tr[1]/w:tc[1]//w:t[text()="Phase"]]', namespaces=namespaces)[0]
        texts = table.xpath('./w:tr[3]/w:tc[2]//w:t', namespaces=namespaces)
        assert len(texts) == 1 and texts[0].text == 'Required'
        texts[0].text = 'Tampered approval'
        members['word/document.xml'] = etree.tostring(tree)
    else:
        before = members['report.md']
        assert before.count(b'| Release | Required |') == 1
        members['report.md'] = before.replace(b'| Release | Required |', b'| Release | Tampered approval |')
    altered = directory / ('altered.' + ('zip' if fmt == 'md' else fmt))
    with zipfile.ZipFile(altered, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, content in members.items():
            package.writestr(name, content)
    with pytest.raises(DiagnosticError) as failure:
        delivery.inspect_export(altered, fmt, captured)
    assert error_diagnostics(failure.value)[0]['location'] == {
        'operation': 'export', 'format': fmt, 'finding_id': 'F01',
        'field': 'tables', 'table': 1, 'row': 3, 'cell': 2}


def test_ambiguous_observed_tables_do_not_invent_cell_coordinate(html_report):
    directory, original, captured = html_report
    tree = html.document_fromstring(original.read_text())
    table = tree.xpath('//*[@id="F01"]//table[thead/tr/th[normalize-space(.)="Phase"]]')[0]
    table.xpath('./tbody/tr[2]/td[2]')[0].text = 'Tampered approval'
    table.addnext(deepcopy(table))
    altered = directory / 'ambiguous.html'
    altered.write_text(html.tostring(tree, encoding='unicode'))
    with pytest.raises(DiagnosticError) as failure:
        delivery.inspect_export(altered, 'html', captured)
    location = error_diagnostics(failure.value)[0]['location']
    assert location['table'] == 1 and location['row'] == 3
    assert 'cell' not in location


def test_missing_table_with_similar_expected_header_does_not_claim_a_cell(html_report):
    directory, _, _ = html_report
    import engine
    data = engine.load_engagement(directory / 'engagement.yaml')
    data['findings'][0]['description_md'] = (
        '| H | V |\n| --- | --- |\n| A | B |\n\n'
        '| H | V |\n| --- | --- |\n| A | C |\n')
    dump_yaml(data, directory / 'engagement.yaml')
    captured = publication.snapshot(directory, directory / 'similar-snapshot')
    original = export.export(directory / 'engagement.yaml', 'html', directory / 'similar.html')
    assert delivery.inspect_export(original, 'html', captured)['finding_association_checked']
    tree = html.document_fromstring(original.read_text())
    tables = tree.xpath('//*[@id="F01"]//table[thead/tr/th[normalize-space(.)="H"]]')
    assert len(tables) == 2
    tables[0].getparent().remove(tables[0])
    altered = directory / 'missing-table.html'
    altered.write_text(html.tostring(tree, encoding='unicode'))
    with pytest.raises(DiagnosticError) as failure:
        delivery.inspect_export(altered, 'html', captured)
    location = error_diagnostics(failure.value)[0]['location']
    assert location['table'] == 1 and location['row'] == 2
    assert 'cell' not in location
