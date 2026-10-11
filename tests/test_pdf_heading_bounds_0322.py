"""Unbroken hostnames and endpoint titles must not push metadata off the page."""
from io import BytesIO
from pathlib import Path

import pdfplumber
import pytest
from weasyprint import HTML

import engine


THEMES = ['serio', 'corporativo', 'htb', 'offsec', 'ejecutivo', 'laboratorio']
TOKEN = 'artifact-' + '0123456789abcdef' * 12


def render(body, theme):
    sheet = (Path(engine.THEMES) / f'{theme}.css').as_uri()
    source = (f'<html><head><link rel="stylesheet" href="{sheet}"></head>'
              f'<body>{body}</body></html>')
    return HTML(string=engine._pdf_code_layout(source)).render()


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('mode', ['vuln', 'machine'])
def test_unbroken_finding_title_keeps_itself_and_its_chip_inside_page(theme, mode):
    chip = '<span class="sev-chip">High</span>' if mode == 'vuln' else '<span class="host-chip">192.0.2.31</span>'
    body = ('<section class="finding"><div class="finding-intro"><div class="f-head">'
            '<span class="f-id">F-001</span><h2 class="f-title">' + TOKEN + '</h2>' + chip +
            '</div></div><p>Evidence description.</p></section>')
    document = render(body, theme)
    assert len(document.pages) == 1
    root = document.pages[0]._page_box
    boxes = [box for box in root.descendants() if type(box).__name__ == 'TextBox']
    right = root.content_box_x() + root.width
    assert all(box.position_x >= root.content_box_x() - .1 and
               box.position_x + box.width <= right + .1 for box in boxes)
    with pdfplumber.open(BytesIO(document.write_pdf())) as pdf:
        text = pdf.pages[0].extract_text() or ''
    # Column placement of the identifier/chip can affect reading order, so
    # check the title in its layout tree and retain all metadata separately.
    title = ''.join(box.text for box in boxes if box.element.get('class') == 'f-title')
    assert title == TOKEN
    assert 'F-001' in text
    assert ('High' if mode == 'vuln' else '192.0.2.31') in text
    assert 'Evidence description.' in text


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('level', [1, 2, 3, 4, 5, 6])
def test_authored_heading_token_wraps_without_hiding_or_changing_text(theme, level):
    document = render(f'<section class="frontsec"><h{level}>{TOKEN}</h{level}>'
                      '<p>First narrative line.</p></section>', theme)
    root = document.pages[0]._page_box
    boxes = [box for box in root.descendants() if type(box).__name__ == 'TextBox']
    assert all(box.position_x + box.width <= root.content_box_x() + root.width + .1 for box in boxes)
    assert ''.join(box.text for box in boxes if box.element.tag == f'h{level}') == TOKEN
    assert len(document.pages) == 1


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('context', ['finding', 'section'])
@pytest.mark.parametrize('prefix', ['', 'Exposed endpoint: '])
def test_heading_uri_fills_each_line_without_stranding_the_prefix(theme, context, prefix):
    value = prefix + 'https://bank.example/internal/' + '0123456789abcdef' * 12
    if context == 'finding':
        body = ('<section class="finding"><div class="f-head"><span class="f-id">F-001</span>'
                f'<h2 class="f-title">{value}</h2><span class="sev-chip">High</span></div>'
                '<p>First narrative line.</p></section>')
    else:
        body = f'<section class="frontsec"><h2>{value}</h2><p>First narrative line.</p></section>'
    document = render(body, theme)
    boxes = list(document.pages[0]._page_box.descendants())
    heading = next(box for box in boxes if type(box).__name__ == 'BlockBox' and box.element.tag == 'h2')
    lines = [box for box in heading.children if type(box).__name__ == 'LineBox']
    assert len(lines) >= 2
    assert all(heading.width - 25 <= line.width <= heading.width + .1 for line in lines[:-1])
    text = ''.join(box.text for box in heading.descendants() if type(box).__name__ == 'TextBox')
    assert text.replace('\u200b', '') == value
    first = ''.join(box.text for box in lines[0].descendants() if type(box).__name__ == 'TextBox')
    assert first.replace('\u200b', '').startswith(prefix + 'https://')
    with pdfplumber.open(BytesIO(document.write_pdf())) as pdf:
        assert '\u200b' not in (pdf.pages[0].extract_text() or '')
