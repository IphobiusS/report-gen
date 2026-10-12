"""Painted header rules leave a real gutter above paginated report content."""
from html import escape
from io import BytesIO
from pathlib import Path

from PIL import Image
import pdfplumber
import pytest
from weasyprint import HTML

import engine


THEMES = ('serio', 'corporativo', 'offsec', 'htb', 'ejecutivo', 'laboratorio')


def continuation_document(tmp_path, theme, kind):
    if kind == 'code':
        body = '<p>First page.</p><pre id="probe">' + escape('\n'.join(
            f'RECORD_{n:03d}=synthetic' for n in range(150))) + '</pre>'
    elif kind == 'table':
        rows = ''.join(f'<tr><td>ROW-{n:03d}</td><td>Preserved evidence</td></tr>'
                       for n in range(100))
        body = ('<p>First page.</p><table id="probe" class="md-table"><thead>'
                '<tr><th>Record</th><th>Meaning</th></tr></thead><tbody>'
                + rows + '</tbody></table>')
    else:
        image = tmp_path / 'figure.png'
        Image.new('RGB', (1200, 550), '#18384a').save(image)
        body = ('<div style="height:230mm">First page.</div><figure id="probe">'
                f'<img src="{image.as_uri()}"><figcaption>Complete figure</figcaption></figure>')
    stylesheet = (Path(engine.THEMES) / f'{theme}.css').as_uri()
    source = (f'<html><head><link rel="stylesheet" href="{stylesheet}">'
              '<style>@page{@top-left{content:"LAB"}'
              '@top-center{content:"Continuation clearance"}'
              '@top-right{content:"SIMULATION"}}</style></head>'
              f'<body>{body}</body></html>')
    return HTML(string=engine._pdf_code_layout(source)).render()


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('kind', ['code', 'table', 'figure'])
def test_header_rule_clears_continuation_code_tables_and_figures(tmp_path, theme, kind):
    document = continuation_document(tmp_path, theme, kind)
    assert len(document.pages) >= 2
    mm = 96 / 25.4
    continuations = 0
    with pdfplumber.open(BytesIO(document.write_pdf())) as pdf:
        for page_number, page in enumerate(document.pages[1:], 1):
            root = page._page_box
            body = next(box for box in root.children if box.element_tag == 'html')
            assert body.position_x == pytest.approx(16 * mm)
            assert body.position_y == pytest.approx(20 * mm)
            assert body.width == pytest.approx(178 * mm)
            content = [box for box in body.descendants()
                       if box.element is not None and box.element.get('id') == 'probe'
                       and type(box).__name__ in {'BlockBox', 'TableBox'}]
            if not content:
                continue
            content_top = min(box.border_box_y() for box in content)
            # This exercises an actual page-boundary fragment/moved figure,
            # rather than a block separated from the header by prose or margins.
            assert content_top == pytest.approx(body.position_y, abs=1)
            continuations += 1
            columns = [box for box in root.children
                       if getattr(box, 'at_keyword', '').startswith('@top-')]
            assert len(columns) == 3
            for column in columns:
                rule_bottom = column.border_box_y() + column.border_height()
                assert content_top - rule_bottom >= 3 * mm - .1
            # Verify the emitted vector borders too; declared padding alone
            # left these rules touching top-of-page code, tables and figures.
            # WeasyPrint paints each rule as an even-odd pair of nested
            # rectangles, not as a standalone half-point rectangle.
            edges = [rect for rect in pdf.pages[page_number].rects
                     if rect['width'] > 25 and abs(rect['top']) < .1
                     and rect['bottom'] < 20 * 72 / 25.4 + .1
                     and rect['fill'] and rect['evenodd']]
            columns = {}
            for edge in edges:
                key = (round(edge['x0'], 3), round(edge['x1'], 3))
                columns.setdefault(key, []).append(edge['bottom'])
            assert len(columns) == 3
            for bottoms in columns.values():
                assert len(bottoms) == 2
                assert max(bottoms) - min(bottoms) == pytest.approx(.5, abs=.01)
                assert content_top * .75 - max(bottoms) >= 3 * 72 / 25.4 - .1
    assert continuations
