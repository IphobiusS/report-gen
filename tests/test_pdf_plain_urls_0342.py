"""A visible URI must fit even when Markdown did not turn it into a link."""
from html import escape
from pathlib import Path
import unicodedata

import fitz
from lxml import html
import pytest
from weasyprint import HTML

import engine
from export_contract import pdf_text_pages
from pdf_pagination import compact_pdf_uri_breaks

THEMES = ['serio', 'corporativo', 'htb', 'offsec', 'ejecutivo', 'laboratorio']
URL = 'https://bank.example/' + '0123456789abcdef' * 35 + '?state=pending&next=%2Fqueue#literal'


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('context', ['paragraph', 'inline-tail', 'list', 'table'])
def test_plain_url_stays_inside_its_container_with_exact_copy_text(tmp_path, theme, context):
    literal = escape(URL)
    if context == 'paragraph':
        body = f'<p>Destination: {literal} retained.</p>'
    elif context == 'inline-tail':
        body = f'<p><strong>Destination:</strong> {literal} <em>retained.</em></p>'
    elif context == 'list':
        body = f'<ul><li>Destination: {literal} retained.</li></ul>'
    else:
        body = f'<table style="width:55%;table-layout:fixed"><tr><td>Destination: {literal} retained.</td></tr></table>'
    sheet = (Path(engine.THEMES) / f'{theme}.css').as_uri()
    source = f'<html><head><link rel="stylesheet" href="{sheet}"></head><body>{body}</body></html>'
    layout = compact_pdf_uri_breaks(engine._pdf_code_layout(source))
    document = HTML(string=layout).render()
    assert len(document.pages) == 1
    root = document.pages[0]._page_box
    container_tag = 'td' if context == 'table' else 'li' if context == 'list' else 'p'
    container = next(b for b in root.descendants() if type(b).__name__ in {'BlockBox', 'TableCellBox'}
                     and b.element.tag == container_tag
                     and any(type(child).__name__ == 'LineBox' for child in b.children))
    left, right = container.content_box_x(), container.content_box_x() + container.width
    lines = [b for b in container.children if type(b).__name__ == 'LineBox']
    assert len(lines) > 3
    for box in container.descendants():
        if type(box).__name__ == 'TextBox':
            assert left - .1 <= box.position_x <= box.position_x + box.width <= right + .1
    # A long first segment must fill the line instead of stranding the scheme.
    assert lines[0].width > container.width - 20
    output = tmp_path / f'{theme}-{context}.pdf'
    engine.render_pdf_weasyprint(source, output, tmp_path)
    with fitz.open(output) as pdf:
        independent = ''.join(page.get_text() for page in pdf)
    for text in (independent, ''.join(pdf_text_pages(output))):
        assert URL in text.replace('\n', '').replace('\r', '')
        assert 'Destination:' in text and 'retained.' in text
        assert not any(c in text for c in ('\u200b', '\u2060', '\ufeff', '\u00ad'))


def test_plain_url_hints_preserve_mixed_markup_unicode_and_non_url_typography():
    unicode_url = 'https://example.test/cafe\u0301/αβγ?return=%2Fqueue'
    source = ('<html><head><style>/* https://example.test/style */</style></head><body>'
              '<p>Office staff <strong>label</strong>: ' + escape(unicode_url) +
              ' <em>ordinary words and office ligatures</em>.</p><p>Unchanged ordinary paragraph.</p>'
              '<script>const url="https://example.test/script"</script></body></html>')
    before = html.document_fromstring(source)
    transformed = engine._pdf_code_layout(source)
    after = html.document_fromstring(transformed)
    assert before.text_content() == after.text_content()
    assert after.xpath('//strong')[0].text == 'label'
    assert after.xpath('//em')[0].text == 'ordinary words and office ligatures'
    assert not after.xpath('//style//wbr|//script//wbr')
    assert not after.xpath('//p')[1].xpath('.//wbr|.//span')
    compact = html.document_fromstring(compact_pdf_uri_breaks(transformed))
    assert unicodedata.normalize('NFC', compact.text_content().replace('\u200b', '')) == unicodedata.normalize('NFC', before.text_content())
    assert 'e\u0301/' in compact.text_content()
    assert compact.xpath('//em')[0].get('style') is None
