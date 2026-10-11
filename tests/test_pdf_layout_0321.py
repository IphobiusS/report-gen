"""Measured heading, image-frame and URI flow regressions in every base theme."""
from io import BytesIO
from pathlib import Path
from html import escape

from lxml import html
from PIL import Image
import pdfplumber
import pytest
from weasyprint import HTML

import engine


THEMES = ['serio', 'corporativo', 'htb', 'offsec', 'ejecutivo', 'laboratorio']
URL = 'https://bank.example/' + '0123456789abcdef' * 16 + '?status=pending&scope=report'


def document(body, theme):
    sheet = (Path(engine.THEMES) / f'{theme}.css').as_uri()
    source = f'<html><head><link rel="stylesheet" href="{sheet}"></head><body>{body}</body></html>'
    return HTML(string=engine._pdf_code_layout(source)).render()


@pytest.mark.parametrize('theme', THEMES)
def test_section_heading_does_not_add_a_blank_text_line(theme):
    doc = document('<section class="frontsec"><h2 class="sec-title">Assessment summary</h2>'
                   '<p>First visible narrative line.</p></section>', theme)
    lines = [b for b in doc.pages[0]._page_box.descendants() if type(b).__name__ == 'TextBox']
    title, paragraph = lines
    gap = paragraph.position_y - title.position_y - title.height
    assert 8 <= gap <= 22  # px; one deliberate gap, without a spare body line.


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('level', [1, 2, 3, 4, 5, 6])
def test_authored_markdown_headings_have_a_consistent_body_gap(theme, level):
    doc = document(f'<section class="frontsec"><h{level}>Authored heading</h{level}>'
                   '<p>First visible narrative line.</p></section>', theme)
    title, paragraph = [b for b in doc.pages[0]._page_box.descendants()
                        if type(b).__name__ == 'TextBox']
    gap = paragraph.position_y - title.position_y - title.height
    assert 3 <= gap <= 15


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('size', [(1200, 550), (1600, 800)])
def test_landscape_frame_follows_the_unchanged_image(tmp_path, theme, size):
    path = tmp_path / 'landscape.png'
    Image.new('RGB', size, '#182b3b').save(path)
    original = path.read_bytes()
    doc = document(f'<figure><img src="{path.as_uri()}"><figcaption>Evidence</figcaption></figure>', theme)
    box = next(b for b in doc.pages[0]._page_box.descendants()
               if type(b).__name__ == 'BlockReplacedBox')
    # The border encloses the actual aspect ratio, not a wider empty box around
    # an object-fit image. The existing maximum printed height is preserved.
    assert box.width / box.height == pytest.approx(size[0] / size[1], abs=.0001)
    assert box.height == pytest.approx(62 * 96 / 25.4, abs=.1)
    assert box.width <= 178 * 96 / 25.4
    assert path.read_bytes() == original


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('prefix,suffix', [('', ''), ('curl --silent "', '" --output report.json')])
def test_uri_uses_available_code_width_without_changing_text(theme, prefix, suffix):
    source = prefix + URL + suffix
    doc = document('<pre>' + escape(source) + '</pre>', theme)
    box = next(b for b in doc.pages[0]._page_box.descendants()
               if type(b).__name__ == 'InlineBlockBox'
               and 'rg-pdf-code-line' in b.element.get('class', ''))
    rows = [b for b in box.children if type(b).__name__ == 'LineBox']
    assert len(rows) >= 3
    for row in rows[:-1]:
        # A few monospaced glyphs allow for rounding and the final shell arg;
        # the old slash-preferring first line left most of the box empty.
        assert row.width >= box.width - 2 * 12
        assert row.width <= box.width + .1
    payload = doc.write_pdf()
    with pdfplumber.open(BytesIO(payload)) as pdf:
        extracted = '\n'.join(page.extract_text() or '' for page in pdf.pages)
    assert '\u200b' not in extracted
    assert extracted.replace('\n', '') == source


def test_pdf_optional_breaks_preserve_tabs_hard_lines_and_unicode_clusters():
    source = '\tGET ' + URL + '\nX-Trace: alpha\n\nhttps://example.test/cafe\u0301/\U0001f469\u200d\U0001f4bb/fin'
    markup = '<pre><code>' + escape(source) + '</code></pre>'
    tree = html.document_fromstring(engine._pdf_code_layout(markup))
    code = tree.xpath('//pre/code')[0]
    assert code.text_content() == source
    assert len(code.xpath('./span')) == len(source.split('\n'))
    assert any('e\u0301/' in value for value in code.xpath('.//text()'))
    assert any('\U0001f469\u200d\U0001f4bb/' in value for value in code.xpath('.//text()'))
    assert all('\u200b' not in value for value in code.xpath('.//text()'))


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('context', ['code', 'anchor', 'reference', 'table'])
def test_literal_uris_fill_inline_and_reference_lines_without_changing_labels(theme, context):
    target = escape(URL, quote=True)
    body = {'code': f'<p>Inline: <code>{target}</code></p>',
            'anchor': f'<p><a href="{target}">{target}</a></p>',
            'reference': f'<ul class="refs"><li>{target}</li></ul>',
            'table': f'<table><tr><td><code>{target}</code></td></tr></table>'}[context]
    doc = document(body, theme)
    rows = [b for b in doc.pages[0]._page_box.descendants() if type(b).__name__ == 'LineBox'
            and URL[:8] in ''.join(getattr(c, 'text', '') for c in b.descendants()).replace('\u200b', '')]
    assert len(rows) == 1
    first = rows[0]
    root = doc.pages[0]._page_box
    assert first.width > root.width * .85
    with pdfplumber.open(BytesIO(doc.write_pdf())) as pdf:
        text = '\n'.join(p.extract_text() or '' for p in pdf.pages)
    assert '\u200b' not in text
    assert text.lstrip('• ').replace('\n', '') == ('Inline: ' + URL if context == 'code' else URL)
    if context == 'code':
        first_text = ''.join(getattr(c, 'text', '') for c in first.descendants()).replace('\u200b', '')
        assert first_text.startswith('Inline: https://')
        assert first.width <= root.width + .1


def test_human_link_labels_are_not_fragmented_or_replaced_by_the_destination():
    source = ('<p><a href="' + URL + '">Read the assessment evidence</a></p>'
              '<p><a href="' + URL + '">' + URL + '</a></p>'
              '<ul class="refs"><li>Read ' + URL + ' for context</li></ul>')
    before = html.document_fromstring(source)
    after = html.document_fromstring(engine._pdf_code_layout(source))
    assert before.text_content() == after.text_content()
    assert before.xpath('//a/@href') == after.xpath('//a/@href')
    assert not after.xpath('//a')[0].xpath('.//wbr')
    assert after.xpath('//a')[1].xpath('.//wbr')
    assert not after.xpath('//li//wbr')


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('context', ['table', 'reference', 'inline-command', 'list-inline', 'narrow-table'])
def test_uri_with_surrounding_text_does_not_strand_its_prefix(theme, context):
    target = escape(URL, quote=True)
    if context == 'table':
        body = f'<table><tr><td>Target: <code>{target}</code> retained.</td></tr></table>'
        expected = 'Target: ' + URL + ' retained.'
    elif context == 'narrow-table':
        body = f'<table style="width:50%;table-layout:fixed"><tr><td>Target: <code>{target}</code> retained.</td></tr></table>'
        expected = 'Target: ' + URL + ' retained.'
    elif context == 'list-inline':
        body = f'<ol><li>Inline: <code>{target}</code> retained.</li></ol>'
        expected = '1. Inline: ' + URL + ' retained.'
    elif context == 'reference':
        body = f'<ul class="refs"><li>Reference: <a href="{target}">{target}</a> retained.</li></ul>'
        expected = 'Reference: ' + URL + ' retained.'
    else:
        body = f'<p>Command: <code>curl --silent {target} -o report.json</code> retained.</p>'
        expected = 'Command: curl --silent ' + URL + ' -o report.json retained.'
    doc = document(body, theme)
    lines = [b for b in doc.pages[0]._page_box.descendants() if type(b).__name__ == 'LineBox']
    first = next(b for b in lines if 'https://' in ''.join(getattr(c, 'text', '')
                 for c in b.descendants()).replace('\u200b', ''))
    first_text = ''.join(getattr(c, 'text', '') for c in first.descendants()).replace('\u200b', '')
    assert expected.split('https://')[0].removeprefix('1. ') in first_text
    assert first.width <= doc.pages[0]._page_box.width * (.5 if context == 'narrow-table' else 1) + .1
    with pdfplumber.open(BytesIO(doc.write_pdf())) as pdf:
        text = '\n'.join(p.extract_text() or '' for p in pdf.pages)
    assert '\u200b' not in text
    assert text.lstrip('• ').replace('\n', '') == expected
