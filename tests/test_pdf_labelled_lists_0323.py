"""Brief asset lists stay together without turning long lists into page blocks."""
from io import BytesIO

from lxml import html
import pdfplumber
import pytest
from weasyprint import HTML

import engine
from pdf_pagination import keep_short_labelled_lists


IPS = ['192.0.2.80', '198.51.100.81', '198.51.100.83']
LINK = 'https://bank.example/evidence?scope=assets&state=pending#receipt'


def source(items, *, nested=True, kind='ul', label='<strong>Affected assets</strong>'):
    group = f'<p>{label}</p><{kind}>' + ''.join(f'<li>{item}</li>' for item in items) + f'</{kind}>'
    if nested:
        group = '<ol start="4" style="counter-reset:list-item 3"><li>' + group + '</li></ol>'
    return ('''<html><head><style>@page{size:380px 300px;margin:20px}
        body{margin:0;font:10px/20px sans-serif}p,ul,ol{margin:0}
        li{padding:0}p{orphans:1;widows:1}</style></head><body>
        <div style="height:210px">Before</div>''' + group + '<p>After</p></body></html>')


def pages(payload):
    with pdfplumber.open(BytesIO(payload)) as document:
        return [page.extract_text() or '' for page in document.pages]


@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('kind', ['ul', 'ol'])
def test_short_label_and_all_assets_move_together_at_real_page_boundary(tmp_path, nested, kind):
    original = source(IPS, nested=nested, kind=kind)
    baseline = pages(HTML(string=original).write_pdf())
    assert len(baseline) == 2
    assert IPS[0] in baseline[0] and all(ip in baseline[1] for ip in IPS[1:])
    output = tmp_path / 'assets.pdf'
    engine.render_pdf_weasyprint(original, output, tmp_path)
    final = pages(output.read_bytes())
    assert len(final) == 2
    assert 'Before' in final[0] and 'Affected assets' not in final[0]
    assert all(text in final[1] for text in ['Affected assets', *IPS, 'After'])
    assert all(sum(page.count(text) for page in final) == 1
               for text in ['Before', 'Affected assets', *IPS, 'After'])
    if nested:
        assert '4.' in final[1] and '4.' not in final[0]


@pytest.mark.parametrize('count', [5, 40])
def test_long_asset_lists_still_paginate_with_all_items_once(tmp_path, count):
    values = [f'ASSET_{i:03d}' for i in range(count)]
    original = source(values)
    assert keep_short_labelled_lists(original) == original
    output = tmp_path / 'long-assets.pdf'
    engine.render_pdf_weasyprint(original, output, tmp_path)
    final = pages(output.read_bytes())
    assert len(final) >= 2
    assert values[0] in final[0] and any(values[-1] in page for page in final[1:])
    assert all(sum(page.count(value) for page in final) == 1 for value in values)


@pytest.mark.parametrize('items,label', [
    (['Long evidence ' * 30], '<strong>Affected assets</strong>'),
    (['Parent<ul><li>Child</li></ul>'], '<strong>Affected assets</strong>'),
    (['<blockquote>Quoted detail</blockquote>'], '<strong>Affected assets</strong>'),
    (['<table><tr><td>Cell</td></tr></table>'], '<strong>Affected assets</strong>'),
    (['<pre>Transcript</pre>'], '<strong>Affected assets</strong>'),
    (['<img src="evidence.png">'], '<strong>Affected assets</strong>'),
    (['<p>First paragraph</p><p>Second paragraph</p>'], '<strong>Affected assets</strong>'),
    (['One<br>Two<br>Three<br>Four<br>Five<br>Six'], '<strong>Affected assets</strong>'),
    (IPS, 'Narrative <strong>with emphasis</strong>'),
    (IPS, '<strong></strong>'),
    (IPS, '<strong>' + 'Long label ' * 20 + '</strong>'),
])
def test_only_bounded_inline_lists_with_a_standalone_label_receive_keep_hint(items, label):
    original = source(items, label=label)
    assert keep_short_labelled_lists(original) == original


def test_layout_hint_preserves_text_native_counters_links_and_existing_styles():
    original = ('<p id="label" style="color:blue"><b>Assets</b></p>'
                '<ol id="assets" start="65536" style="color:green"><li>'
                '<a href="' + LINK.replace('&', '&amp;') + '"><code>192.0.2.80</code></a>'
                '</li><li>198.51.100.81</li></ol><p>Following narrative</p>')
    before = html.document_fromstring(original)
    after = html.document_fromstring(keep_short_labelled_lists(original))
    assert before.text_content() == after.text_content()
    assert before.xpath('//a/@href') == after.xpath('//a/@href') == [LINK]
    assert before.xpath('//ol/@start') == after.xpath('//ol/@start') == ['65536']
    assert before.xpath('//@id') == after.xpath('//@id')
    assert 'color:blue' in after.xpath('//p')[0].get('style')
    assert 'color:green' in after.xpath('//ol')[0].get('style')
    assert not after.xpath('//p')[1].get('style')
