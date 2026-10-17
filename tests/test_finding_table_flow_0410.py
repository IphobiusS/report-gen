"""Actual multi-page finding tables retain identity, headings, rows and links."""
from copy import deepcopy
from html import escape
from pathlib import Path
import re
import os

from PIL import Image
import pdfplumber
import pytest
from weasyprint import HTML

import engine
from error_messages import language_scope
from pdf_pagination import mark_finding_tables, verify_table_markers


THEMES = ('serio', 'corporativo', 'htb', 'offsec', 'ejecutivo', 'laboratorio')


def table(prefix, rows=72, image=False):
    content = [f'| {prefix}CONTROL | {prefix}EVIDENCE |', '| --- | --- |']
    for index in range(rows):
        value = f'café ação Ω {prefix}-VALUE-{index:03d}'
        if index in {0, rows - 1}:
            value += f' [Reference](https://bank.example/{prefix}/{index}?audit=a%2Fb&lang=pt)'
        if image and index == rows // 2:
            value += ' ![Synthetic evidence](evidence.png){width=24px}'
        content.append(f'| {prefix}-ROW-{index:03d} | {value} |')
    return '\n'.join(content)


@pytest.mark.parametrize('theme,language', list(zip(THEMES, ['es', 'en', 'pt'] * 2)))
def test_tables_flow_in_every_finding_field_with_stable_index_and_links(tmp_path, theme, language):
    Image.new('RGB', (96, 48), '#224477').save(tmp_path / 'evidence.png')
    findings = []
    for index, field in enumerate(['description_md', 'impact_md', 'remediation_md', 'walkthrough']):
        prefix = f'T{index}'
        finding = {'id': f'F-{index}', 'title': f'FINDING_TITLE_{index}', 'mode': 'vuln',
                   'severity': 'info', 'affected': f'host-{index}.example',
                   'description_md': f'INTRO_{index}', 'remediation_md': f'CLOSE_{index}'}
        content = table(prefix, image=True)
        if field == 'walkthrough':
            # Authored nested Markdown is a table in a quoted procedure, not
            # raw HTML, so this exercises the public parser as well as layout.
            finding[field] = [{'lead': 'Procedure evidence',
                               'text_md': '\n'.join('> ' + row for row in content.splitlines())}]
        else:
            finding[field] = content
        findings.append(finding)
    data = {'meta': {'report_title': 'Fictional extended controls', 'lang': language, 'theme': theme},
            'report': {'sections': [{'key': 'findings'}]}, 'findings': findings}
    original = deepcopy(data)
    markup = engine.render_html(engine.build_env(), data, tmp_path, {}, True, engine.load_lang(language))
    output = tmp_path / 'flow.pdf'
    engine.render_pdf_weasyprint(markup, output, tmp_path)
    assert data == original
    with pdfplumber.open(output) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages]
        links = {link['uri'] for page in pdf.pages for link in page.hyperlinks if link.get('uri')}
        assert sum(len(page.images) for page in pdf.pages) >= 4
    page_map = engine.read_page_map(output, [f'F-{i}' for i in range(4)])
    combined = '\n'.join(pages)
    row_offsets = []
    for index in range(4):
        prefix = f'T{index}'
        rows = re.findall(rf'{prefix}-ROW-\d{{3}}', combined)
        assert rows == [f'{prefix}-ROW-{row:03d}' for row in range(72)]
        occupied = [page for page in pages if prefix + '-ROW-' in page]
        assert len(occupied) >= 2
        assert all(prefix + 'CONTROL' in page and prefix + 'EVIDENCE' in page for page in occupied)
        assert f'FINDING_TITLE_{index}' in pages[page_map[f'F-{index}'] - 1]
        assert all(f'https://bank.example/{prefix}/{row}?audit=a%2Fb&lang=pt' in links for row in (0, 71))
        row_offsets.append((combined.index(prefix + '-ROW-000'), combined.index(prefix + '-ROW-071')))
    assert all(before[1] < after[0] for before, after in zip(row_offsets, row_offsets[1:]))
    assert combined.count('café ação Ω') == 288


def test_nested_table_fragments_keep_both_headers_and_all_original_values(tmp_path):
    inner = ''.join(f'<tr><td>NESTED-{i:03d}</td><td>Nested evidence</td></tr>' for i in range(100))
    body = ('<section class="finding" id="F-NESTED"><h2>Nested finding</h2>'
            '<table class="md-table"><thead><tr><th>Outer context</th></tr></thead><tbody><tr><td>'
            '<table class="md-table"><thead><tr><th>Inner control</th><th>Inner evidence</th></tr></thead>'
            f'<tbody>{inner}</tbody></table></td></tr></tbody></table></section>')
    sheet = (Path(engine.THEMES) / 'serio.css').as_uri()
    source = f'<html><head><link rel="stylesheet" href="{sheet}"></head><body>{body}</body></html>'
    output = tmp_path / 'nested.pdf'
    engine.render_pdf_weasyprint(source, output, tmp_path)
    with pdfplumber.open(output) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages]
    assert len(pages) >= 3
    assert re.findall(r'NESTED-\d{3}', '\n'.join(pages)) == [f'NESTED-{i:03d}' for i in range(100)]
    assert all('Outer context' in page and 'Inner control' in page and 'Inner evidence' in page for page in pages)


@pytest.mark.parametrize('language,word', [('es', 'celda'), ('en', 'cell'), ('pt', 'célula')])
def test_indivisible_middle_cell_retains_previous_output_and_localized_location(tmp_path, language, word):
    body = ('<section class="finding" id="F-IMPOSSIBLE"><table><tbody>'
            '<tr><td>Start</td></tr><tr><td><div style="height:350mm">Indivisible evidence</div></td></tr>'
            '<tr><td>End</td></tr></tbody></table></section>')
    output = tmp_path / 'impossible.pdf'
    output.write_bytes(b'PREVIOUS_VERIFIED_OUTPUT')
    with language_scope(language), pytest.raises(ValueError, match='F-IMPOSSIBLE') as caught:
        engine.render_pdf_weasyprint(body, output, tmp_path)
    assert word in str(caught.value)
    assert caught.value.diagnostics[0]['location']['finding_id'] == 'F-IMPOSSIBLE'
    assert output.read_bytes() == b'PREVIOUS_VERIFIED_OUTPUT'


def test_chromium_preflight_accepts_repeated_headers_and_finds_missing_or_clipped_cell():
    rows = ''.join(f'<tr><td>ROW-{i:03d}</td><td>Evidence</td></tr>' for i in range(100))
    source = ('<section class="finding" id="F-MARKERS"><table><thead>'
              '<tr><th>Control</th><th>Evidence</th></tr></thead><tbody>' + rows + '</tbody></table></section>')
    marked, checks = mark_finding_tables(source)
    assert verify_table_markers(HTML(string=marked).write_pdf(), checks) == [checks[0]['key']]
    # Loss in the middle of a long table is caught even if both ends survive.
    missing = marked.replace(escape(checks[0]['cells'][87]['end']), '')
    with pytest.raises(ValueError, match='F-MARKERS'):
        verify_table_markers(HTML(string=missing).write_pdf(), checks)


@pytest.mark.skipif(os.environ.get('REPORT_GEN_TEST_CHROMIUM_PDF') != '1',
                    reason='Requires the real optional Chromium PDF runtime')
@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
def test_real_chromium_multipage_table_and_impossible_middle_cell(tmp_path, language):
    data = {'meta': {'report_title': 'Chromium finding flow', 'lang': language, 'theme': 'serio'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F-CHROMIUM', 'mode': 'vuln', 'severity': 'info',
                          'title': 'CHROMIUM_FINDING_TITLE',
                          'description_md': table('CHROMIUM', rows=100)}]}
    source = engine.render_html(engine.build_env(), data, tmp_path, {}, False, engine.load_lang(language))
    output = tmp_path / 'chromium.pdf'
    engine.render_pdf_chromium(source, output, {'_resource_root': str(tmp_path)})
    with pdfplumber.open(output) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages]
        links = {link['uri'] for page in pdf.pages for link in page.hyperlinks if link.get('uri')}
    text = '\n'.join(pages)
    assert re.findall(r'CHROMIUM-ROW-\d{3}', text) == [f'CHROMIUM-ROW-{i:03d}' for i in range(100)]
    occupied = [page for page in pages if 'CHROMIUM-ROW-' in page]
    assert len(occupied) >= 3
    assert all('CHROMIUMCONTROL' in page and 'CHROMIUMEVIDENCE' in page for page in occupied)
    assert 'RGTABLE' not in text
    assert all(f'https://bank.example/CHROMIUM/{i}?audit=a%2Fb&lang=pt' in links for i in (0, 99))
    previous = output.read_bytes()
    impossible = source.replace('CHROMIUM-ROW-050', '<div style="height:350mm">Impossible</div>')
    with language_scope(language), pytest.raises(ValueError, match='F-CHROMIUM'):
        engine.render_pdf_chromium(impossible, output, {'_resource_root': str(tmp_path)})
    assert output.read_bytes() == previous


@pytest.mark.parametrize('width', ['350mm', '180mm'])
def test_chromium_cell_boundaries_reject_horizontal_overflow_even_inside_physical_page(width):
    source = ('<html><head><style>@page{size:A4;margin:20mm}table{table-layout:fixed}</style></head><body>'
              '<section class="finding" id="F-WIDE"><table style="width:' + width + '">'
              '<tr><td>Evidence</td><td>Outside printable body</td></tr></table></section></body></html>')
    marked, checks = mark_finding_tables(source)
    with pytest.raises(ValueError, match='F-WIDE'):
        verify_table_markers(HTML(string=marked).write_pdf(), checks,
                             margins=(20 * 72 / 25.4,) * 2, side_margins=(20 * 72 / 25.4,) * 2)


def test_chromium_narrow_columns_ignore_token_width_but_check_real_cell_edges():
    source = ('<html><head><style>@page{size:A4;margin:20mm}body{margin:0}'
              'table{width:100%;table-layout:fixed;border-collapse:collapse}td{padding:0}</style></head><body>'
              '<section class="finding" id="F-NARROW"><table><colgroup><col><col style="width:2mm"></colgroup>'
              '<tr><td>Ordinary content</td><td>1</td></tr></table></section></body></html>')
    marked, checks = mark_finding_tables(source)
    assert not verify_table_markers(HTML(string=marked).write_pdf(), checks,
                                    margins=(20 * 72 / 25.4,) * 2, side_margins=(20 * 72 / 25.4,) * 2)
