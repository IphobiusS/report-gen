"""Visual bullet order cannot invalidate independently proved hard hyphens.

Boreal PT exposed a real one-page combination: a wrapped hard hyphen and a
reference whose bullet is painted after its text but geometrically precedes it.
"""
from collections import Counter
import re

from lxml import html
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
import pypdfium2
import pytest
from weasyprint import HTML

import export_contract as contract


MARKUP = '''<html><head><style>
@page {size:A4;margin:20mm}
body {font-family:DejaVu Sans;font-size:12px}
.wrapped {width:65px}
</style></head><body><section class="frontsec" id="start">Start</section>
<section class="finding" id="F01"><h2 class="f-title">First title</h2>
<p class="wrapped">recovery-assurance</p><p>ação / revisión / São Paulo / ñ</p>
<h3>References</h3><ul><li>https://docs.boreal.example/controls/f27#revision</li></ul>
</section></body></html>'''


def rendered(tmp_path, markup=MARKUP, name='paint-order.pdf'):
    target = tmp_path/name
    HTML(string=markup).write_pdf(target)
    return target


def read_native(path):
    with pypdfium2.PdfDocument(path) as doc:
        page = doc[0]
        text = page.get_textpage()
        try:
            return text.get_text_bounded(errors='strict')
        finally:
            text.close()
            page.close()


def test_real_paint_order_difference_keeps_every_character_and_region(tmp_path):
    path = rendered(tmp_path)
    before = path.read_bytes()
    reader = PdfReader(path)
    primary = read_native(path)
    donor = contract._pdf_hyphen_donor(reader.pages[0], reader)
    assert '\x02' in primary
    assert primary.index('•') < primary.index('https://')
    assert donor.index('•') > donor.index('https://')
    normalized = lambda value: ''.join(c for c in value if not c.isspace()).replace('\x02','-')
    assert normalized(primary) != normalized(donor)
    assert Counter(normalized(primary)) == Counter(normalized(donor))
    pages = contract.pdf_text_pages(path, geometry_pages=(0,))
    assert pages == [primary.replace('\x02','-')]
    expected = contract.from_tree(html.document_fromstring(MARKUP))
    assert contract.inspect(path,'pdf',expected)['pdf_finding_regions_checked'] == 1
    assert path.read_bytes() == before


@pytest.mark.parametrize('original,changed', [
    ('assurance','assurancX'), ('assurance','assruance'), ('São Paulo','Sao Paulo'),
    ('#revision','#revisioX'), ('First title','Wrong title'),
])
def test_positioned_hyphen_proof_does_not_hide_changed_authored_content(tmp_path, original, changed):
    path = rendered(tmp_path, MARKUP.replace(original,changed))
    with pytest.raises(ValueError):
        contract.inspect(path,'pdf',contract.from_tree(html.document_fromstring(MARKUP)))


def test_positioned_hyphen_requires_independent_geometry(tmp_path, monkeypatch):
    from pdfminer.converter import PDFPageAggregator
    original = PDFPageAggregator.render_char

    def displaced(self, *args, **kwargs):
        advance = original(self,*args,**kwargs)
        char = self.cur_item._objs[-1]
        if char.get_text() == '-':
            x0,y0,x1,y1 = char.bbox
            char.set_bbox((x0+20,y0,x1+20,y1))
        return advance

    path = rendered(tmp_path)
    monkeypatch.setattr(PDFPageAggregator,'render_char',displaced)
    with pytest.raises(ValueError,match='[Aa]mbigu'):
        contract.pdf_text_pages(path,geometry_pages=(0,))


def test_positioned_hyphen_rejects_ambiguous_embedded_font_identity(tmp_path):
    source = rendered(tmp_path)
    writer = PdfWriter(clone_from=source)
    fonts = writer.pages[0]['/Resources']['/Font']
    selected = next(ref.get_object() for ref in fonts.values()
                    if ref.get_object().get('/Subtype') == '/Type0')
    fonts[NameObject('/AmbiguousCopy')] = writer._add_object(DictionaryObject(selected))
    target = tmp_path/'ambiguous-font.pdf'
    writer.write(target)
    with pytest.raises(ValueError,match='[Aa]mbigu'):
        contract.pdf_text_pages(target,geometry_pages=(0,))


@pytest.mark.parametrize('mutation',['missing','substituted','duplicated'])
def test_order_fallback_cannot_accept_a_different_character_inventory(tmp_path, monkeypatch, mutation):
    path = rendered(tmp_path)
    original = contract._pdf_hyphen_donor

    def altered(page,reader):
        donor = original(page,reader)
        if mutation == 'missing':
            return donor.replace('References','',1)
        if mutation == 'substituted':
            return donor.replace('References','ReferencXs',1)
        return donor + 'References'

    monkeypatch.setattr(contract,'_pdf_hyphen_donor',altered)
    with pytest.raises(ValueError,match='[Aa]mbigu'):
        contract.pdf_text_pages(path,geometry_pages=(0,))


def test_cid_hyphen_cannot_bypass_invalid_source_proof_in_another_font(tmp_path):
    source = rendered(tmp_path)
    writer = PdfWriter(clone_from=source)
    fonts = writer.pages[0]['/Resources']['/Font']
    font = next(ref.get_object() for ref in fonts.values()
                if 'Bold' in str(ref.get_object().get('/BaseFont')))
    data = font['/ToUnicode'].get_data()
    entry = re.search(rb'beginbfchar\s*(<[\da-fA-F]{4}>\s*<[\da-fA-F]*>)',data)[1]
    replacement = data.replace(b'endcmap', b'1 beginbfchar\n'+entry+b'\nendbfchar\nendcmap')
    cmap = DecodedStreamObject()
    cmap.set_data(replacement)
    font[NameObject('/ToUnicode')] = writer._add_object(cmap)
    target = tmp_path/'invalid-unrelated-map.pdf'
    writer.write(target)
    assert '\x02' in read_native(target)
    # The hyphen's own regular font is intact. Invalid mapping elsewhere must
    # not be silently bypassed by the newly supported CID position proof.
    with pytest.raises(ValueError,match='[Aa]mbigu'):
        contract.pdf_text_pages(target,geometry_pages=(0,))
