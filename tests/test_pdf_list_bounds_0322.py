"""Large authored list counters stay exact and inside printable margins."""
from io import BytesIO
from pathlib import Path

from lxml import html
import pdfplumber
import pytest
from weasyprint import HTML

import engine
from safe_markup import md


THEMES = ['serio', 'corporativo', 'htb', 'offsec', 'ejecutivo', 'laboratorio']


def source(markdown, theme):
    sheet = (Path(engine.THEMES) / f'{theme}.css').as_uri()
    return (f'<html><head><link rel="stylesheet" href="{sheet}"></head><body>'
            f'<section class="frontsec">{md(markdown)}</section></body></html>')


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('start', [5, 9999, 1234567890, 2147483646])
def test_authored_counter_and_next_item_stay_exact_inside_printable_margin(tmp_path, theme, start):
    markdown = f'{start}. First acceptance criterion.\n{start + 1}. Second acceptance criterion.'
    original = source(markdown, theme)
    layout = engine._pdf_code_layout(original)
    before, after = html.document_fromstring(original), html.document_fromstring(layout)
    assert before.text_content() == after.text_content()
    assert before.xpath('//ol/@start') == after.xpath('//ol/@start')
    if start == 5:
        assert 'padding-left' not in after.xpath('//ol')[0].get('style', '')
    document = HTML(string=layout).render()
    assert len(document.pages) == 1
    with pdfplumber.open(BytesIO(document.write_pdf())) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ''
        assert f'{start}.' in text and f'{start + 1}.' in text
        assert 'First acceptance criterion.' in text and 'Second acceptance criterion.' in text
        # PDF coordinates are points; the template's 16mm page inset is exact.
        assert min(char['x0'] for char in page.chars) >= 16 * 72 / 25.4 - .1


@pytest.mark.parametrize('theme', THEMES)
def test_nested_counter_has_its_own_inset_and_keeps_parent_sequence_and_link(theme):
    markdown = ('5. Parent criterion.\n\n'
                '    1234567890. Nested evidence.\n'
                '    1234567891. [Reference](https://bank.example/evidence#receipt)\n\n'
                '6. Parent continuation.')
    original = source(markdown, theme)
    layout = engine._pdf_code_layout(original)
    before, after = html.document_fromstring(original), html.document_fromstring(layout)
    assert before.text_content() == after.text_content()
    assert before.xpath('//a/@href') == after.xpath('//a/@href')
    ordered = after.xpath('//ol')
    assert len(ordered) == 2
    assert 'padding-left' not in ordered[0].get('style', '')
    assert 'padding-left:13ch' in ordered[1].get('style', '')
    with pdfplumber.open(BytesIO(HTML(string=layout).write_pdf())) as pdf:
        page = pdf.pages[0]
        text = page.extract_text() or ''
        for number in ['5.', '6.', '1234567890.', '1234567891.']:
            assert number in text
        assert min(char['x0'] for char in page.chars) >= 16 * 72 / 25.4 - .1
        assert {link['uri'] for link in page.hyperlinks} == {'https://bank.example/evidence#receipt'}
