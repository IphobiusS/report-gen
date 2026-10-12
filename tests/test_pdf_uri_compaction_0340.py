"""Dense literal URI reports retain exact copyable text without per-glyph boxes."""
from html import escape
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import quote

import fitz
from lxml import html
from pypdf import PdfReader
import pytest

import engine
from export_contract import pdf_text_pages
from exporters.pdf import export_pdf
from pdf_pagination import compact_pdf_uri_breaks
from wizard import dump_yaml


THEMES = ('serio', 'corporativo', 'htb', 'offsec', 'ejecutivo', 'laboratorio')
URL = ('https://api.example/v1/identity/' + 'authorization-scope_' * 10
       + '?name=two%20words&next=%2Fcontrol%3Fmode%3Dreview#entry%2Dend')
UNICODE_URL = 'https://example.test/cafe\u0301/αβγ/fin?literal=%CE%B1'


def test_compaction_is_render_only_preserving_authored_breaks_and_unicode():
    original = ('<p>Prose <a href="' + escape(URL, quote=True) + '">Human label</a></p>'
                '<pre><code>' + escape('curl "' + URL + '"\n\t' + UNICODE_URL) + '</code></pre>'
                '<p>Native<wbr>break</p><p>Visible'
                '<wbr data-rg-pdf-uri-break="true" style="display:inline-block;width:4px">box</p>')
    layout = engine._pdf_code_layout(original)
    before = html.document_fromstring(layout)
    after = html.document_fromstring(compact_pdf_uri_breaks(layout))
    assert '\u200b' not in layout  # The common transient HTML representation remains exact.
    assert before.text_content() == after.text_content().replace('\u200b', '')
    assert before.xpath('//a/@href') == after.xpath('//a/@href')
    assert 'e\u0301/' in after.text_content() and 'αβγ/' in after.text_content()
    assert len(after.xpath('//wbr')) == 2
    assert after.xpath('//wbr[not(@data-rg-pdf-uri-break)]')
    assert after.xpath('//wbr[@style]')
    assert html.document_fromstring(original).text_content() == before.text_content()


def test_many_uris_in_one_command_keep_boundaries_and_surrounding_arguments():
    urls = [f'https://api.example/tenant-{i}/office?next=%2Fstaff#fi' for i in range(128)]
    command = 'collect --exact ' + ' ; verify --url '.join(f'"{url}"' for url in urls) + ' --retain'
    source = '<pre><code>' + escape(command) + '</code></pre>'
    layout = engine._pdf_code_layout(source)
    transformed = html.document_fromstring(compact_pdf_uri_breaks(layout))
    runs = transformed.xpath('//span[@data-rg-pdf-uri-run="true"]')
    assert len(runs) == len(urls)
    assert [run.text_content().replace('\u200b', '') for run in runs] == urls
    assert transformed.text_content().replace('\u200b', '') == command
    assert not transformed.xpath('//wbr[@data-rg-pdf-uri-break="true"]')
    assert html.document_fromstring(layout).text_content() == command


@pytest.mark.parametrize('theme', THEMES)
@pytest.mark.parametrize('context', ['anchor-table', 'code'])
def test_real_compact_pdf_preserves_literal_copy_text_targets_and_line_fill(tmp_path, theme, context):
    literal = escape(URL, quote=True)
    if context == 'anchor-table':
        body = f'<table><tr><td><a href="{literal}">{literal}</a></td></tr></table>'
        expected = URL
    else:
        body = f'<pre><code>curl --silent "{literal}" --output evidence.json</code></pre>'
        expected = f'curl --silent "{URL}" --output evidence.json'
    body += ('<p><a href="' + escape(UNICODE_URL, quote=True) + '">'
             + escape(UNICODE_URL) + '</a></p>')
    sheet = (Path(engine.THEMES) / f'{theme}.css').as_uri()
    source = f'<html><head><link rel="stylesheet" href="{sheet}"></head><body>{body}</body></html>'
    output = tmp_path / 'actual.pdf'
    engine.render_pdf_weasyprint(source, output, tmp_path)
    with fitz.open(output) as document:
        independent = '\n'.join(page.get_text() for page in document)
    raw = '\n'.join(page.extract_text() or '' for page in PdfReader(output).pages)
    for extracted in ('\n'.join(pdf_text_pages(output)), raw, independent):
        assert not any(char in extracted for char in ('\u200b', '\u00ad', '\u2060', '\ufeff'))
        assert unicodedata.normalize('NFC', expected) in unicodedata.normalize('NFC', extracted.replace('\n', ''))
        assert unicodedata.normalize('NFC', UNICODE_URL) in unicodedata.normalize('NFC', extracted.replace('\n', ''))
    with fitz.open(output) as document:
        assert len(document) == 1
        page = document[0]
        links = [link for link in page.get_links() if link.get('uri') == URL]
        unicode_target = quote(UNICODE_URL, safe=":/?#[]@!$&'()*+,;=%")
        assert any(link.get('uri') == unicode_target for link in page.get_links())
        if context == 'anchor-table':
            assert len(links) >= 3 and {link['uri'] for link in links} == {URL}
            assert all(not link['from'].is_empty for link in links)
            # All complete URI lines fill the same cell to within two glyphs.
            widths = [link['from'].width for link in links[:-1]]
            assert max(widths) - min(widths) < 16
            assert min(widths) > 450
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines', []):
                x0, y0, x1, y1 = line['bbox']
                assert 0 <= x0 <= x1 <= page.rect.width
                assert 0 <= y0 <= y1 <= page.rect.height


@pytest.mark.parametrize('tag', ['h2', 'code', 'a', 'pre'])
def test_pdf_uri_ligatures_preserve_every_letter_and_prose_typography(tmp_path, tag):
    url = ('https://tt-fi-fl-st-ffi-ffl.example/identity/office/staff/'
           'ttfi%2Dfl?literal=fi%20fl&next=%2Fstaff#ffi')
    prefix = 'Office staff: ' if tag != 'a' else ''
    suffix = ' proof retained.' if tag != 'a' else ''
    attrs = f' href="{escape(url, quote=True)}"' if tag == 'a' else ''
    expected = prefix + url + suffix
    source = ('<html><style>@page{size:A4;margin:20mm} '
              'body{font-family:DejaVu Sans;font-size:11px} '
              'h2,pre,code,a{display:block;width:280px;white-space:pre-wrap}</style><body>'
              f'<{tag}{attrs}>' + escape(expected) + f'</{tag}></body></html>')
    transformed = html.document_fromstring(compact_pdf_uri_breaks(engine._pdf_code_layout(source)))
    if tag == 'h2':
        heading = transformed.xpath('//h2')[0]
        assert heading.get('style') is None
        assert heading.text == prefix
        run = heading.xpath('./span[@data-rg-pdf-uri-run="true"]')[0]
        assert run.tail == suffix
    output = tmp_path / 'ligatures.pdf'
    engine.render_pdf_weasyprint(source, output, tmp_path)
    with fitz.open(output) as document:
        independent = '\n'.join(page.get_text() for page in document)
    raw = '\n'.join(page.extract_text() or '' for page in PdfReader(output).pages)
    for extracted in (raw, independent):
        assert ''.join(extracted.split()) == ''.join(expected.split())
        assert not any(char in extracted for char in ('\u200b', '\u00ad', '\u2060', '\ufeff'))


@pytest.mark.parametrize('lang', ['es', 'en'])
def test_real_72_literal_uri_rows_export_within_existing_timeout(tmp_path, lang, monkeypatch):
    monkeypatch.setenv('REPORT_GEN_PDF_TIMEOUT', '120')
    urls = [(f'https://api.example/v1/tenants/tenant%2D{i:02d}/identity/'
             + 'authorization-scope_' * 10
             + '?a=one%20two&next=%2Fcontrol%3Fmode%3Dreview&z=1#request%2Dend')
            for i in range(1, 73)]
    assert all(len(url) >= 300 for url in urls)
    rows = [f'| TBL-{i:03d} | [{url}](<{url}>) | Pending: criteria {i:03d}; preserve entire row. |'
            for i, url in enumerate(urls, 1)]
    summary = '# TABLE_BEGIN\n\n| Row | Destination and exact label | Review |\n|---:|---|---|\n' + '\n'.join(rows) + '\n\nTABLE_END'
    source = tmp_path / 'engagement.yaml'
    dump_yaml({'meta': {'lang': lang, 'theme': 'serio', 'report_title': 'Synthetic dense URI regression',
                        'client': 'Fictional bank', 'assessor': 'Synthetic QA'},
               'report': {'sections': [{'key': 'executive_summary', 'summary': summary}, {'key': 'findings'}]},
               'findings': []}, source)
    original = source.read_bytes()
    output = tmp_path / 'report.pdf'
    start = time.monotonic()
    export_pdf(source, output)  # Actual child, both layout passes and the unchanged 120s bound.
    assert time.monotonic() - start < 120
    assert source.read_bytes() == original
    assert {path.name for path in tmp_path.iterdir()} == {'engagement.yaml', 'report.pdf'}
    extracted = '\n'.join(pdf_text_pages(output))
    assert not any(char in extracted for char in ('\u200b', '\u00ad', '\u2060', '\ufeff'))
    # Independent geometric extraction also proves every full literal URL;
    # prose in neighbouring columns must not be interleaved into its text.
    with fitz.open(output) as document:
        links = [link for page in document for link in page.get_links() if link.get('uri') in urls]
        assert {link['uri'] for link in links} == set(urls)
        assert all(not link['from'].is_empty for link in links)
        recovered = {url: '' for url in urls}
        for page in document:
            textpage = page.get_textpage()
            for link in page.get_links():
                if link.get('uri') in recovered:
                    recovered[link['uri']] += ''.join(page.get_textbox(link['from'], textpage=textpage).split())
        assert recovered == {url: url for url in urls}
        compact = re.sub(r'\s+', '', extracted)
        assert 'TABLE_BEGIN' in compact and 'TABLE_END' in compact
        assert all(f'TBL-{i:03d}' in compact for i in range(1, 73))
