"""Source identities must address one destination in every public report format."""
from collections import Counter
from copy import deepcopy

from lxml import html
import pytest

import export
import portable_report
import validate
from wizard import dump_yaml


def document(layout='sections'):
    data = {'meta': {'lang': 'es', 'theme': 'serio', 'report_title': 'Anchor contract'},
            'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'Synthetic anchor finding',
                          'severity': 'info', 'cvss': 0, 'description_md': 'Documentary control.'}]}
    if layout == 'sections':
        data['report'] = {'sections': [{'key': 'findings_summary'}, {'key': 'findings'}]}
    return data


def invalid_document(case):
    data = document()
    if case == 'toolbar':
        data['findings'][0]['id'] = 'query'
    elif case == 'finding_section':
        data['findings'][0]['id'] = 'findings'
    elif case == 'duplicate_section':
        data['report']['sections'].append({'key': 'findings_summary'})
    elif case == 'toc':
        data['report']['sections'].append({'key': 'sec-toc', 'title': 'Synthetic appendix'})
    elif case == 'workflow':
        data['report']['sections'].append({'key': 'rg_assets', 'title': 'Synthetic appendix'})
        data['assets'] = [{'uid': '12345678-1234-1234-1234-123456789abc',
                          'name': 'Synthetic asset', 'target': 'https://audit.example'}]
    elif case == 'legacy':
        data.pop('report')
        data['findings'][0]['id'] = 'sec-summary'
    elif case == 'anonymous_sections':
        data['report']['sections'] += [{'title': 'First appendix'}, {'title': 'Second appendix'}]
    elif case == 'duplicate_findings_section':
        data['report']['sections'].append({'key': 'findings'})
    else:
        raise AssertionError(case)
    return data


@pytest.mark.parametrize('case', ['toolbar', 'finding_section', 'duplicate_section', 'toc',
                                'workflow', 'legacy', 'anonymous_sections', 'duplicate_findings_section'])
@pytest.mark.parametrize('language', ['es', 'en'])
def test_validation_rejects_ambiguous_report_destinations(case, language):
    data = invalid_document(case)
    before = deepcopy(data)
    errors = [message for level, message in validate.validate(data, lang=language) if level == 'error']
    assert any(('anclas' if language == 'es' else 'anchor') in message.lower() for message in errors)
    assert data == before, 'Validation must preserve the author identities and content.'


@pytest.mark.parametrize('case', ['toolbar', 'finding_section', 'duplicate_section', 'toc', 'workflow'])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_every_export_rejects_collision_before_replacing_existing_output(tmp_path, case, fmt):
    data = invalid_document(case)
    dump_yaml(data, tmp_path / 'engagement.yaml')
    output = tmp_path / ('existing.' + ('zip' if fmt == 'md' else fmt))
    output.write_bytes(b'EXISTING_ARTIFACT_CANARY')
    source = (tmp_path / 'engagement.yaml').read_bytes()
    with pytest.raises(ValueError, match='[Aa]ncla'):
        export.export(tmp_path / 'engagement.yaml', fmt, output)
    assert output.read_bytes() == b'EXISTING_ARTIFACT_CANARY'
    assert (tmp_path / 'engagement.yaml').read_bytes() == source


@pytest.mark.parametrize('layout', ['sections', 'legacy', 'custom', 'anonymous'])
def test_valid_existing_ids_and_unique_custom_sections_stay_exact(tmp_path, layout):
    data = document('legacy' if layout == 'legacy' else 'sections')
    data['findings'][0]['id'] = 'M-Café:01'
    if layout == 'custom':
        data['report']['sections'].append({'key': 'custom-001', 'title': 'Custom appendix', 'body': 'Control text.'})
    elif layout == 'anonymous':
        data['report']['sections'].append({'title': 'Unique unnamed appendix', 'body': 'Control text.'})
    assert not [message for level, message in validate.validate(data) if level == 'error']
    dump_yaml(data, tmp_path / 'engagement.yaml')
    source = (tmp_path / 'engagement.yaml').read_bytes()
    path = export.export(tmp_path / 'engagement.yaml', 'html', tmp_path / 'report.html')
    tree = html.document_fromstring(path.read_text())
    assert len(tree.xpath('//*[@id=$identity]', identity='M-Café:01')) == 1
    assert max(Counter(tree.xpath('//*[@id]/@id')).values()) == 1
    assert (tmp_path / 'engagement.yaml').read_bytes() == source


def test_only_real_rendered_workflow_and_legacy_anchors_are_reserved(tmp_path):
    data = document()
    # These are legitimate custom keys while their generated block is absent.
    data['report']['sections'] += [{'key': 'rg_assets', 'title': 'Custom asset narrative'},
                                  {'key': 'sec-summary', 'title': 'Custom summary'}]
    assert not [message for level, message in validate.validate(data) if level == 'error']
    dump_yaml(data, tmp_path / 'engagement.yaml')
    tree = html.document_fromstring(portable_report.build(tmp_path))
    assert max(Counter(tree.xpath('//*[@id]/@id')).values()) == 1


def test_reading_notes_are_in_main_without_changing_report_geometry(tmp_path):
    data = document()
    dump_yaml(data, tmp_path / 'engagement.yaml')
    tree = html.document_fromstring(portable_report.build(tmp_path))
    assert tree.xpath('//main/p[@class="report-note"]')
    assert tree.xpath('//main/p[@id="empty-results"]')
    assert tree.xpath('//main/div[@class="report-content"]//*[@id="F01"]')
    assert not tree.xpath('//body/p[not(@role)]')
    stylesheet = ''.join(tree.xpath('//style/text()'))
    assert '.report-content{max-width:1060px;margin:auto;padding:32px;overflow-wrap:anywhere}' in stylesheet
    assert '.report-content{padding:12px}' in stylesheet
    assert '.report-content{padding:0;max-width:none}' in stylesheet
    assert '@media print{@page{size:A4;margin:16mm}' in stylesheet


def test_reserved_portable_ids_match_the_actual_shell(tmp_path):
    data = document()
    dump_yaml(data, tmp_path / 'engagement.yaml')
    tree = html.document_fromstring(portable_report.build(tmp_path))
    shell = set(tree.xpath('//nav[@class="report-toolbar"]//*[@id]/@id')) | {'empty-results'}
    assert validate.PORTABLE_CONTROL_IDS == shell
