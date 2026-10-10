"""An explicitly selected summary is a valid extract, with no invented detail body."""
from copy import deepcopy
from urllib.parse import unquote
from lxml import html
import pytest

import delivery
import export
import export_contract
import publication
import validate
from wizard import dump_yaml


def document(details=False):
    data = {'meta': {'lang': 'en', 'theme': 'serio', 'report_title': 'Summary-only extract'},
            'report': {'sections': [{'key': 'findings_summary'}]},
            'findings': [{'id': 'F%41', 'mode': 'vuln', 'title': 'SELECTED_SUMMARY_CANARY',
                          'severity': 'info', 'cvss': 0,
                          'description_md': 'DETAIL_BODY_UNSELECTED_CANARY'}]}
    if details: data['report']['sections'].append({'key': 'findings'})
    return data


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_explicit_summary_only_exports_without_broken_generated_links_or_invented_body(fmt, tmp_path):
    data = document()
    before = deepcopy(data)
    assert not [m for lev, m in validate.validate(data) if lev == 'error']
    dump_yaml(data, tmp_path / 'engagement.yaml')
    source = (tmp_path / 'engagement.yaml').read_bytes()
    captured = delivery.capture(tmp_path, tmp_path / 'captured')
    artifact = export.export(tmp_path / 'engagement.yaml', fmt, tmp_path / ('summary.' + ('zip' if fmt == 'md' else fmt)))
    profile = export_contract.profile(artifact, fmt)
    assert 'SELECTED_SUMMARY_CANARY' in profile['text']
    assert 'DETAIL_BODY_UNSELECTED_CANARY' not in profile['text']
    scopes = export_contract.profile(artifact, fmt, captured['contract'])
    assert set(scopes) == {''}
    if fmt != 'pdf':
        assert not [target for label, target in scopes['']['semantic']['links'] if target == '#F%41']
    if fmt == 'html':
        tree = html.document_fromstring(artifact.read_text())
        assert not tree.xpath('//*[contains(@class,"report-toolbar")]|//*[@id="results"]')
    delivery.inspect_export(artifact, fmt, captured)
    assert data == before
    assert (tmp_path / 'engagement.yaml').read_bytes() == source


@pytest.mark.parametrize('details', [False, True])
def test_summary_navigation_has_real_destinations_only_when_detail_body_is_selected(details, tmp_path):
    data = document(details)
    before = deepcopy(data)
    tree = publication.render(data, tmp_path)
    links = tree.xpath('//table[contains(@class,"sumtable")]//a/@href')
    if details:
        assert links == ['#F%2541']
        assert tree.xpath('//*[@id=$identity]', identity=unquote(links[0][1:]))
        assert 'DETAIL_BODY_UNSELECTED_CANARY' in tree.text_content()
    else:
        assert not links
        assert not tree.xpath('//*[@id="F%41"]')
        assert 'DETAIL_BODY_UNSELECTED_CANARY' not in tree.text_content()
        assert 'SELECTED_SUMMARY_CANARY' in tree.text_content()
        assert not tree.xpath('//table[contains(@class,"sumtable")]//*[contains(@class,"c-pg")]')
    assert data == before
