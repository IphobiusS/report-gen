"""URI wrap hints preserve pixels and useful link regions without empty annotations."""
import hashlib

import fitz
from PIL import Image
from weasyprint import HTML

import engine
from pdf_pagination import prune_pdf_uri_break_links
from resources import restricted_fetcher


URL = ('https://api.example/identity/' + 'authorization-scope_' * 9
       + '?name=two%20words&next=%2Fadmin%3Fmode%3Dreview#entry%2Dend')
OTHER = 'https://review.example/%CE%B1?case=two%20words#second'


def source(tmp_path):
    Image.new('RGB', (60, 30), '#217b6b').save(tmp_path / 'proof.png')
    rows = ''.join(f'<tr><td>Row {i}</td><td><a href="{URL}">{URL}</a></td></tr>'
                   for i in range(8))
    return ('<html><head><style>@page {size:A4;margin:20mm} '
            'body{font-family:DejaVu Sans;font-size:11px} '
            'table{width:100%;border-collapse:collapse} td{padding:4px} '
            'a,code{overflow-wrap:anywhere} </style></head><body>'
            '<h1 id="target">Synthetic URI review</h1>'
            f'<p><a href="{OTHER}">Separate first link</a> ordinary prose '
            f'<a href="{OTHER}"><strong>Separate second link</strong></a></p>'
            '<p><a href="#target">Internal destination</a></p>'
            f'<p><a href="{OTHER}"><img src="proof.png" alt="Synthetic image"></a></p>'
            f'<p>Literal code, not a hyperlink: <code>{URL}</code></p>'
            f'<table>{rows}</table></body></html>')


def test_real_pdf_retains_pixels_targets_and_visible_link_areas(tmp_path):
    original = source(tmp_path)
    transformed = engine._pdf_code_layout(original)
    assert 'data-rg-pdf-uri-break="true"' in transformed
    document = HTML(string=transformed, base_url=str(tmp_path),
                    url_fetcher=restricted_fetcher(tmp_path, engine.THEMES)).render()
    unfiltered = document.write_pdf()
    before = [list(page.links) for page in document.pages]
    removed = prune_pdf_uri_break_links(document)
    assert removed > 4000
    for old, page in zip(before, document.pages):
        useful = [link for link in old
                  if link[2][0] != link[2][2] and link[2][1] != link[2][3]]
        assert all(link in page.links for link in useful)
    output = tmp_path / 'filtered.pdf'
    engine.render_pdf_weasyprint(original, output, tmp_path)
    with fitz.open(stream=unfiltered, filetype='pdf') as baseline, fitz.open(output) as fixed:
        assert len(baseline) == len(fixed)
        filtered_links = []
        baseline_visible_links = []
        for old, new in zip(baseline, fixed):
            assert old.get_text() == new.get_text()
            assert hashlib.sha256(old.get_pixmap().samples).digest() == hashlib.sha256(new.get_pixmap().samples).digest()
            for link in old.get_links():
                if not link['from'].is_empty:
                    baseline_visible_links.append((link.get('uri'), link.get('page'), tuple(link['from'])))
            for link in new.get_links():
                filtered_links.append((link.get('uri'), link.get('page'), tuple(link['from'])))
        assert filtered_links == baseline_visible_links
        assert 8 < len(filtered_links) < 100
        targets = {link[0] for link in filtered_links}
        assert URL in targets and OTHER in targets
        assert any(page == 0 for _, page, _ in filtered_links)


def test_filter_preserves_unmarked_breaks_positive_boxes_and_attachments():
    html = ('<html><body><p>'
            '<a href="https://one.example">Unmarked<wbr>break</a> '
            '<a href="https://two.example">Marked'
            '<wbr data-rg-pdf-uri-break="true">break</a> '
            '<a href="https://three.example">Positive'
            '<wbr data-rg-pdf-uri-break="true" style="display:inline-block;width:4px">box</a>'
            '</p></body></html>')
    document = HTML(string=html).render()
    page = document.pages[0]
    original = list(page.links)
    marked = next(link for link in original
                  if link[1] == 'https://two.example' and link[3].element_tag == 'wbr')
    attachment = ('attachment', marked[1], marked[2], marked[3])
    page.links.append(attachment)
    prune_pdf_uri_break_links(document)
    assert attachment in page.links
    assert all(link in page.links for link in original if link[1] == 'https://one.example')
    assert all(link in page.links for link in original
               if link[2][0] != link[2][2] and link[2][1] != link[2][3])
    assert marked not in page.links
