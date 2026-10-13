"""Body chapters flow without losing navigation or literal identifier text."""
from copy import deepcopy
from html import escape
from pathlib import Path

import fitz
from lxml import html
from pypdf import PdfReader
import pytest
from weasyprint import HTML

import engine
from pdf_pagination import compact_pdf_uri_breaks


THEMES = ('serio', 'corporativo', 'htb', 'offsec', 'ejecutivo', 'laboratorio')
TOKEN = 'ALTAMAR013' + '0123456789ABCDEF' * 24


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('context', ['paragraph', 'inline-tail', 'list', 'table', 'code'])
def test_long_identifier_fills_label_line_and_preserves_copy_text(tmp_path, theme, context):
    content = f'TOKEN: {TOKEN} retained.'
    if context == 'inline-tail':
        body = f'<p><strong>TOKEN:</strong> {TOKEN} <em>retained.</em></p>'
    elif context == 'list':
        body = f'<ul><li>{content}</li></ul>'
    elif context == 'table':
        body = f'<table style="width:55%;table-layout:fixed"><tr><td>{content}</td></tr></table>'
    elif context == 'code':
        body = f'<p>TOKEN: <code>{TOKEN}</code> retained.</p>'
    else:
        body = f'<p>{content}</p>'
    sheet = (Path(engine.THEMES) / f'{theme}.css').as_uri()
    source = f'<html><head><link rel="stylesheet" href="{sheet}"></head><body>{body}</body></html>'
    transient = engine._pdf_code_layout(source)
    assert html.document_fromstring(transient).text_content() == html.document_fromstring(source).text_content()
    assert not html.document_fromstring(transient).xpath('//wbr')
    assert not any(character in transient for character in ('\u200b', '\u2060', '\ufeff', '\u00ad'))
    document = HTML(string=compact_pdf_uri_breaks(transient)).render()
    tag = 'td' if context == 'table' else 'li' if context == 'list' else 'p'
    container = next(box for box in document.pages[0]._page_box.descendants()
                     if type(box).__name__ in {'BlockBox', 'TableCellBox'} and box.element.tag == tag
                     and any(type(child).__name__ == 'LineBox' for child in box.children))
    lines = [box for box in container.children if type(box).__name__ == 'LineBox']
    assert len(lines) > 3
    first_text = ''.join(box.text for box in lines[0].descendants() if type(box).__name__ == 'TextBox')
    assert first_text.startswith('TOKEN: ')
    # Compact break opportunities exist only in the private layout tree;
    # the exported text below must contain none of these control characters.
    assert 'ALTAMAR013' in first_text.replace('\u200b', '')
    assert lines[0].width > container.width - 20
    left, right = container.content_box_x(), container.content_box_x() + container.width
    assert all(left - .1 <= box.position_x <= box.position_x + box.width <= right + .1
               for box in container.descendants() if type(box).__name__ == 'TextBox')
    output = tmp_path / 'identifier.pdf'
    output.write_bytes(document.write_pdf())
    with fitz.open(output) as pdf:
        independent = ''.join(page.get_text() for page in pdf)
    extracted = ''.join(page.extract_text() or '' for page in PdfReader(output).pages)
    for text in (independent, extracted):
        assert TOKEN in text.replace('\n', '').replace('\r', '')
        assert 'TOKEN:' in text and 'retained.' in text
        assert not any(character in text for character in ('\u200b', '\u2060', '\ufeff', '\u00ad'))


def test_identifier_hints_leave_normal_words_unicode_clusters_and_targets_intact():
    target = 'https://bank.example/a%2Fb?locale=es%2Den'
    body = (f'<p>Office staff <strong>LABEL</strong>: {TOKEN} '
            f'<a href="{escape(target, quote=True)}">Human link label</a> '
            'cafe\u0301 東京 LAB office affinity.</p>')
    before = html.document_fromstring(body)
    after = html.document_fromstring(engine._pdf_code_layout(body))
    assert before.text_content() == after.text_content()
    assert before.xpath('//a/@href') == after.xpath('//a/@href')
    assert not after.xpath('//a//wbr|//strong//wbr')
    assert 'cafe\u0301 東京 LAB office affinity.' in after.text_content()


@pytest.mark.parametrize('length', [23, 24, 31, 32, 63, 64, 65])
@pytest.mark.parametrize('kind', ['mixed', 'alphabetic'])
def test_identifier_classifier_boundaries_in_narrow_cell(tmp_path, length, kind):
    token = (('ALT0123456789' if kind == 'mixed' else 'OfficeAffinity') * 8)[:length]
    classified = length >= 32 or (kind == 'mixed' and length >= 24)
    sheet = (Path(engine.THEMES) / 'corporativo.css').as_uri()
    source = (f'<html><head><link rel="stylesheet" href="{sheet}"></head><body>'
              f'<table style="width:25%;table-layout:fixed"><tr><td>TOKEN: {token}</td></tr></table>'
              '<p>Ordinary prose keeps whole words and cafe\u0301 remains authored Unicode.</p></body></html>')
    layout = engine._pdf_code_layout(source)
    tree = html.document_fromstring(layout)
    assert tree.text_content() == html.document_fromstring(source).text_content()
    assert bool(tree.xpath('//*[@data-rg-pdf-identifier]')) is classified
    assert not tree.xpath('//wbr|//p//span')
    document = HTML(string=layout).render()
    cell = next(box for box in document.pages[0]._page_box.descendants() if type(box).__name__ == 'TableCellBox')
    first = next(box for box in cell.children if type(box).__name__ == 'LineBox')
    first_text = ''.join(box.text for box in first.descendants() if type(box).__name__ == 'TextBox')
    if classified:
        assert first_text.startswith('TOKEN: ' + token[:6])
        assert first.width > cell.width - 20
    left, right = cell.content_box_x(), cell.content_box_x() + cell.width
    assert all(left - .1 <= box.position_x <= box.position_x + box.width <= right + .1
               for box in cell.descendants() if type(box).__name__ == 'TextBox')
    output = tmp_path / 'boundary.pdf'
    output.write_bytes(document.write_pdf())
    with fitz.open(output) as pdf:
        independent = ''.join(page.get_text() for page in pdf)
    extracted = ''.join(page.extract_text() or '' for page in PdfReader(output).pages)
    for text in (independent, extracted):
        assert token in text.replace('\n', '')
        assert not any(character in text for character in ('\u200b', '\u2060', '\ufeff', '\u00ad'))


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('language', ['es', 'en'])
def test_short_body_chapters_share_page_but_cover_and_index_remain_separate(tmp_path, theme, language):
    data = {'meta': {'lang': language, 'theme': theme, 'client': 'Fictional bank',
                     'report_title': 'Continuous chapter regression'},
            'report': {'sections': [
                {'key': f'chapter-{number}', 'title': f'CHAPTER_{number}',
                 'body': f'BODY_{number}: preserved paragraph and closing reference.'}
                for number in range(1, 5)]}, 'findings': []}
    original = deepcopy(data)
    markup = engine.render_html(engine.build_env(), data, tmp_path, {}, False, engine.load_lang(language))
    output = tmp_path / 'chapters.pdf'
    engine.render_pdf_weasyprint(markup, output, tmp_path)
    with fitz.open(output) as pdf:
        pages = [page.get_text() for page in pdf]
        assert len(pages) == 3
        assert 'Continuous chapter regression' in ' '.join(pages[0].split())
        assert all(f'CHAPTER_{number}' in pages[1] for number in range(1, 5))
        assert all(f'BODY_{number}' not in pages[1] for number in range(1, 5))
        assert all(f'BODY_{number}' in pages[2] for number in range(1, 5))
        headings = [block for block in pdf[2].get_text('dict')['blocks']
                    if any('CHAPTER_' in span['text'] for line in block.get('lines', []) for span in line['spans'])]
        assert len(headings) == 4
    assert data == original
