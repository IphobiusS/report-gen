"""Visible URL guidance is scoped, nonblocking and never rewrites evidence."""
from copy import deepcopy
from pathlib import Path
import os
import shutil
import subprocess
from zipfile import ZipFile

from docx import Document
from lxml import etree, html
import pytest

import readiness
import workflows
from exporters.richtext import write_markdown
from safe_markup import md

URL = 'https://evidence.example/a(verified)/' + 'segment/' * 12 + '?filter=%2f%5C&case=A_B#part-1'


def report(body):
    return workflows.normalize({'meta': {'report_title': 'Synthetic URL review', 'lang': 'en'},
        'report': {'sections': [{'key': 'findings'}]},
        'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'Synthetic observation',
                      'severity': 'low', 'description_md': body}]})


def test_named_destinations_are_not_mistaken_for_visible_long_urls(tmp_path):
    data = report(f'[Evidence register](<{URL}>)')
    before = deepcopy(data)
    assert readiness.docx_url_compatibility(data, tmp_path)['count'] == 0
    assert 'compatibility' not in readiness.checklist(data, tmp_path, [])
    assert data == before


def test_visible_literal_links_inline_markup_and_commands_keep_exact_locations(tmp_path):
    data = report(f'[{URL}](<{URL}>)\n\n`{URL}`\n\n```text\nGET {URL}\n```')
    before = deepcopy(data)
    result = readiness.docx_url_compatibility(data, tmp_path)
    assert result['count'] == 3
    assert result['heuristic'] is True and result['format'] == 'docx'
    assert result['locations'] == [{'path': 'findings[0].description_md', 'finding_uid': data['findings'][0]['uid'],
                                    'label': 'F01 · Synthetic observation · Description (Incl. Root Cause)', 'count': 3}]
    assert data == before and URL not in str(result)
    checks = readiness.checklist(data, tmp_path, [])
    assert len(checks['checks']) == 5
    assert checks['compatibility'] == result


def test_named_link_label_with_url_is_still_visible_text(tmp_path):
    data = report(f'[See {URL}](https://short.example/)')
    assert readiness.docx_url_compatibility(data, tmp_path)['count'] == 1


def test_redactions_and_disabled_sections_control_the_outgoing_scan(tmp_path):
    data = report(URL)
    data['publication'] = {'redactions': [{'needle': URL, 'replacement': '[REDACTED]'}]}
    assert readiness.docx_url_compatibility(data, tmp_path)['count'] == 0
    data.pop('publication')
    data['report']['sections'] = [{'key': 'executive_summary', 'summary': 'A brief assessment.'}]
    assert readiness.docx_url_compatibility(data, tmp_path)['count'] == 0
    data['report']['sections'][0]['summary'] = URL
    result = readiness.docx_url_compatibility(data, tmp_path, 'en')
    assert result['count'] == 1
    assert result['locations'][0]['path'] == 'report.sections[0]'
    assert result['locations'][0]['section_key'] == 'executive_summary'


def test_nested_lists_are_counted_once_and_short_urls_do_not_add_noise(tmp_path):
    data = report(f'1. [{URL}](<{URL}>)\n\n    - {URL}\n\nhttps://short.example/')
    assert readiness.docx_url_compatibility(data, tmp_path)['count'] == 2


def test_named_link_roundtrips_literal_destination_and_readable_label(tmp_path):
    label = 'Evidence [review] *confirmed*'
    source = r'[Evidence \[review\] \*confirmed\*](<' + URL + '>)'
    parsed = html.fragment_fromstring(str(md(source)), create_parent='div')
    link = parsed.xpath('.//a')[0]
    assert link.text_content() == label and link.get('href') == URL
    document = Document()
    write_markdown(document, source, tmp_path, lambda text: document.add_paragraph(text))
    output = tmp_path / 'named.docx'
    document.save(output)
    with ZipFile(output) as archive:
        tree = etree.fromstring(archive.read('word/document.xml'))
        relationships = etree.fromstring(archive.read('word/_rels/document.xml.rels'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    hyperlinks = tree.xpath('//w:hyperlink', namespaces=ns)
    assert len(hyperlinks) == 1
    assert ''.join(hyperlinks[0].xpath('.//w:t/text()', namespaces=ns)) == label
    assert [r.get('Target') for r in relationships if r.get('Type', '').endswith('/hyperlink')] == [URL]
    assert not tree.xpath('//w:br', namespaces=ns)


def test_link_editor_and_optional_compatibility_browser(tmp_path):
    executable = os.environ.get('REPORT_GEN_CHROMIUM')
    if not executable or not Path(executable).is_file() or not shutil.which('node'):
        pytest.skip('Set REPORT_GEN_CHROMIUM and provide Node + Playwright for browser checks')
    result = subprocess.run(['node', str(Path(__file__).with_name('test_docx_url_guidance_0330.cjs')),
                             '--output', str(tmp_path / 'browser')], capture_output=True, text=True,
                            timeout=120, env=os.environ.copy())
    assert result.returncode == 0, result.stdout + result.stderr
