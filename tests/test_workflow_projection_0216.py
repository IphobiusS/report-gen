"""Legacy nullable/unnormalized rows remain documentary data, not merge keys."""
from copy import deepcopy

from lxml import html
import pytest

import delivery
import export
import export_contract
import validate
import workflows
from wizard import dump_yaml


def document(sections=True):
    data = {'meta': {'lang': 'es', 'theme': 'serio', 'report_title': 'Synthetic legacy projection'},
            'assets': [{'name': 'Activo Uno', 'target': 'https://first.example'},
                       {'name': 'Activo Dos', 'target': 'https://second.example'}],
            'findings': [{'id': 'F01', 'mode': 'vuln', 'title': None, 'severity': 'info', 'cvss': 0,
                          'owner': 'Synthetic team', 'description_md': 'Documentary control.'}]}
    if sections:
        data['report'] = {'sections': [{'key': 'findings_summary'}, {'key': 'findings'}]}
    return data


@pytest.mark.parametrize('sections', [True, False])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_null_title_and_uidless_assets_export_in_all_formats_without_source_changes(tmp_path, sections, fmt):
    data = document(sections)
    before = deepcopy(data)
    assert not [message for level, message in validate.validate(data) if level == 'error']
    assert any('titulo' in message for level, message in validate.validate(data) if level == 'warning')
    dump_yaml(data, tmp_path / 'engagement.yaml')
    source = (tmp_path / 'engagement.yaml').read_bytes()
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    output = export.export(tmp_path / 'engagement.yaml', fmt, tmp_path / ('report.' + delivery.get(fmt).extension))
    content = export_contract.profile(output, fmt)['text']
    assert 'Activo Uno' in content
    assert 'Activo Dos' in content
    assert 'None' not in content, 'A null source title is absent text, not the word None.'
    delivery.inspect_export(output, fmt, captured)
    assert data == before
    assert (tmp_path / 'engagement.yaml').read_bytes() == source


@pytest.mark.parametrize('identities', [False, True])
def test_asset_inventory_keeps_every_row_in_original_order_with_or_without_uids(identities):
    data = document()
    if identities:
        for index, asset in enumerate(data['assets'], 1):
            asset['uid'] = f'12345678-1234-1234-1234-{index:012d}'
    data['findings'] = []
    before = deepcopy(data)
    body = next(section['body'] for section in workflows.report_sections(data) if section['key'] == 'rg_assets')
    assert body.index('Activo Uno') < body.index('Activo Dos')
    assert data == before


def test_coverage_without_uid_does_not_inherit_an_unidentified_asset_target():
    data = document()
    data['findings'] = []
    data['coverage'] = [{'test': 'UNCORRELATED_TEST_CANARY', 'status': 'pending', 'notes': 'Unassigned synthetic test.'}]
    section = next(section for section in workflows.report_sections(data) if section['key'] == 'rg_coverage')
    tree = html.fragment_fromstring(str(__import__('safe_markup').md(section['body'])), create_parent='div')
    cells = tree.xpath('.//tbody/tr/td')
    assert cells[0].text_content() == 'UNCORRELATED_TEST_CANARY'
    assert not cells[1].text_content().strip(), 'An unassigned test has no inferred target.'


def test_nullable_title_is_only_normalized_in_the_transient_report_copy():
    data = document()
    before = deepcopy(data)
    projected = workflows.project_report(data)
    assert projected['findings'][0]['title'] == ''
    assert data == before
    tracking = next(section for section in workflows.report_sections(data) if section['key'] == 'rg_retest')
    assert 'Synthetic team' in tracking['body']
    assert 'None' not in tracking['body']
