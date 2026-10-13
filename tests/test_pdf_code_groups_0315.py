"""Short code groups stay readable while long blocks still flow across pages."""
from html import escape
from math import ceil

from lxml import html
import pytest

import engine
import export_contract


def render_code(tmp_path, monkeypatch, lines, *, filler=0, height=500):
    captured = []
    verify = engine._verify_pdf_code_lines

    def record(document):
        verify(document)
        captured.append(document)

    monkeypatch.setattr(engine, '_verify_pdf_code_lines', record)
    literal = '\n'.join(lines) + '\n'
    markup = (
        '<!DOCTYPE html><html><head><style>'
        f'@page{{size:380px {height}px;margin:20px}}'
        'body{margin:0}pre{margin:0;padding:0;white-space:pre-wrap;'
        'overflow-wrap:anywhere;font:10px/20px monospace}'
        '</style></head><body>'
        f'<div style="height:{filler}px"></div><pre><code>'
        + escape(literal) + '</code></pre></body></html>')
    transformed = html.document_fromstring(engine._pdf_code_layout(markup))
    assert transformed.xpath('//pre')[0].text_content() == literal
    target = tmp_path / 'code.pdf'
    engine.render_pdf_weasyprint(markup, target, tmp_path)
    return captured[0], export_contract.pdf_text_pages(target)


def line_boxes(document):
    pages = []
    for page in document.pages:
        root = page._page_box
        boxes = [box for box in root.descendants()
                 if type(box).__name__ == 'InlineBlockBox'
                 and box.element is not None
                 and 'rg-pdf-code-line' in box.element.get('class', '').split()]
        top = root.content_box_y()
        bottom = top + root.height
        for box in boxes:
            assert box.position_y >= top - 0.1
            assert box.position_y + box.height <= bottom + 0.1
        pages.append(boxes)
    return pages


@pytest.mark.parametrize('filler,expected_pages', [(0, 1), (220, 2)])
def test_four_short_lines_remain_on_one_page(tmp_path, monkeypatch, filler, expected_pages):
    lines = ['SYNTHETIC_ONLY', 'record=example', 'state=unverified', 'network=none']
    document, text_pages = render_code(tmp_path, monkeypatch, lines, filler=filler, height=300)
    boxes = line_boxes(document)
    assert len(boxes) == expected_pages
    assert [len(page) for page in boxes if page] == [4]
    assert len(text_pages) == expected_pages
    for line in lines:
        assert sum(line in page for page in text_pages) == 1
    if filler:
        assert boxes[-1][0].position_y == pytest.approx(20)


def test_hundred_wrapped_lines_flow_without_blank_or_heading_only_pages(tmp_path, monkeypatch):
    lines = [f'RECORD_{index:03d}=' + '0123456789abcdef' * 10 for index in range(100)]
    document, text_pages = render_code(tmp_path, monkeypatch, lines)
    pages = line_boxes(document)
    capacity = int(document.pages[0]._page_box.height / pages[0][0].height)
    assert len(pages) == ceil(len(lines) / capacity)
    assert all(len(boxes) >= 4 for boxes in pages)
    assert [''.join(box.element.itertext()) for boxes in pages for box in boxes] == lines
    for page, boxes in zip(document.pages, pages):
        assert boxes[0].position_y == pytest.approx(page._page_box.content_box_y())
    # Every authored line's visual wraps remain together and extract once.
    for line in lines:
        matching_pages = 0
        for text in text_pages:
            try:
                export_contract._pdf_code_lines(line, text)
                matching_pages += 1
            except ValueError:
                pass
        assert matching_pages == 1
