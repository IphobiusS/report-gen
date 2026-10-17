"""Oversized narrative rows keep headers, titles and all original cell text."""
from io import BytesIO
from pathlib import Path
import re

import pdfplumber
import pytest
from weasyprint import HTML

import engine
from pdf_pagination import relax_oversized_rows


THEMES = ['serio', 'corporativo', 'htb', 'offsec', 'ejecutivo', 'laboratorio']


def source(body, theme='serio'):
    sheet = (Path(engine.THEMES) / f'{theme}.css').as_uri()
    return f'<html><head><link rel="stylesheet" href="{sheet}"></head><body>{body}</body></html>'


def long_table(kind='md-table'):
    cells = ''.join(f'<p>ROW-{i:03d} measured evidence, mitigation and acceptance.</p>'
                    for i in range(100))
    return ('<section class="frontsec"><h2 class="sec-title">Assessment decisions</h2>'
            f'<table class="{kind}"><thead><tr><th>Control label</th><th>Decision evidence</th>'
            '</tr></thead><tbody><tr><td>Approved with conditions</td>'
            f'<td>{cells}</td></tr></tbody></table></section>')


@pytest.mark.parametrize('theme', THEMES)
def test_tall_row_retains_title_headers_order_and_printable_bounds(tmp_path, monkeypatch, theme):
    original = HTML.render
    layouts = []

    def render(self, *args, **kwargs):
        document = original(self, *args, **kwargs)
        layouts.append(document)
        return document

    monkeypatch.setattr(HTML, 'render', render)
    output = tmp_path / 'narrative.pdf'
    engine.render_pdf_weasyprint(source(long_table(), theme), output, tmp_path)
    assert len(layouts) == 2  # The fallback is bounded to one additional layout.
    with pdfplumber.open(BytesIO(output.read_bytes())) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages]
        assert len(pages) >= 2
        assert 'Assessment decisions' in pages[0]
        assert 'ROW-000' in pages[0]  # No heading-only first page.
        for text in pages:
            assert text.count('Control label') == 1
            assert text.count('Decision evidence') == 1
        assert re.findall(r'ROW-\d{3}', '\n'.join(pages)) == [f'ROW-{i:03d}' for i in range(100)]
        assert '\n'.join(pages).count('Approved with conditions') == 1
    for page in layouts[-1].pages:
        root = page._page_box
        bottom = root.content_box_y() + root.height
        for box in root.descendants():
            if type(box).__name__ in {'TableBox', 'TableRowBox', 'TextBox'}:
                assert box.position_y + box.height <= bottom + 2


@pytest.mark.parametrize('kind', ['md-table', 'scope', 'contacts'])
def test_only_fragmented_body_rows_are_relaxed(kind):
    renderer = HTML(string=source(long_table(kind)))
    first = renderer.render()
    assert relax_oversized_rows(first)
    changed = [element for element in renderer.etree_element.iter('tr') if element.get('style')]
    assert len(changed) == 1
    assert changed[0].find('td') is not None
    assert all(not row.get('style') for head in renderer.etree_element.iter('thead') for row in head.iter('tr'))


def test_normal_rows_remain_whole_and_need_no_retry():
    rows = ''.join('<tr><td>' + ''.join(f'<p>ROW-{i:02d}-{j} normal content.</p>'
                                      for j in range(4)) + '</td></tr>' for i in range(24))
    renderer = HTML(string=source('<section class="frontsec"><table class="md-table">'
                                 '<thead><tr><th>Ordinary rows</th></tr></thead>'
                                 f'<tbody>{rows}</tbody></table></section>'))
    document = renderer.render()
    assert not relax_oversized_rows(document)
    locations = {}
    for index, page in enumerate(document.pages):
        for box in page._page_box.descendants():
            if type(box).__name__ == 'TextBox':
                for row in re.findall(r'ROW-(\d{2})-\d', box.text):
                    locations.setdefault(row, set()).add(index)
    assert len(locations) == 24
    assert all(len(pages) == 1 for pages in locations.values())


def test_already_splittable_rows_need_no_extra_layout():
    body = long_table().replace('<tbody><tr>', '<tbody><tr style="break-inside:auto">')
    renderer = HTML(string=source(body))
    document = renderer.render()
    assert not relax_oversized_rows(document)


def test_long_finding_row_flows_after_one_retry_without_losing_header(tmp_path, monkeypatch):
    original = HTML.render
    calls = []

    def render(self, *args, **kwargs):
        calls.append(True)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(HTML, 'render', render)
    output = tmp_path / 'protected.pdf'
    output.write_bytes(b'previous verified output')
    body = long_table().replace('class="frontsec"', 'class="finding" id="F-001"')
    engine.render_pdf_weasyprint(source(body), output, tmp_path)
    assert len(calls) == 2
    with pdfplumber.open(output) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages]
    assert re.findall(r'ROW-\d{3}', '\n'.join(pages)) == [f'ROW-{i:03d}' for i in range(100)]
    assert all('Control label' in page and 'Decision evidence' in page for page in pages)


def test_two_long_cells_and_similar_values_are_not_lost_or_duplicated(tmp_path):
    left = ''.join(f'<p>LEFT-{i:03d} Approved</p>' for i in range(82))
    right = ''.join(f'<p>RIGHT-{i:03d} Approved with conditions</p>' for i in range(93))
    body = ('<section class="frontsec"><h2 class="sec-title">Parallel narratives</h2>'
            '<table class="md-table"><thead><tr><th>First evidence</th><th>Second evidence</th></tr>'
            f'</thead><tbody><tr><td>{left}</td><td>{right}</td></tr></tbody></table></section>')
    output = tmp_path / 'parallel.pdf'
    engine.render_pdf_weasyprint(source(body), output, tmp_path)
    with pdfplumber.open(output) as pdf:
        pages = [page.extract_text() or '' for page in pdf.pages]
    text = '\n'.join(pages)
    assert re.findall(r'LEFT-\d{3}', text) == [f'LEFT-{i:03d}' for i in range(82)]
    assert re.findall(r'RIGHT-\d{3}', text) == [f'RIGHT-{i:03d}' for i in range(93)]
    assert text.count('Approved') == 175
    assert text.count('Approved with conditions') == 93
    assert all('First evidence' in page and 'Second evidence' in page for page in pages)
