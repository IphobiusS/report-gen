"""Wrapped hard hyphens are proved from PDF bytes, never reconstructed from expected text."""
import re

from lxml import html
from pypdf import PdfWriter
from pypdf.generic import (
    ArrayObject, ByteStringObject, ContentStream, DecodedStreamObject,
    NameObject, TextStringObject,
)
import pypdfium2
import pypdfium2.raw as pdfium_raw
import pytest
from weasyprint import HTML

import engine
import export_contract
from error_messages import language_scope


MARKUP = '''<html lang="en"><body><h1>Arabic and Latin observations</h1>
<p>Latin prefix العربية Latin suffix.</p>
<p style="width:65px;font-family:DejaVu Sans;font-size:12px">recovery-assurance</p>
<p>Second العربية with a normal intra-word hyphen, office and affinity.</p>
<p style="width:70px;font-family:DejaVu Sans;font-size:12px">cross-border</p>
<p>Third note العربية then café, café, 42 and end.</p></body></html>'''


def _cmap_pdf(source, target, *, offset=0, hyphen_unicode=None, unsupported=None):
    """Change source codes and both actual CMaps while retaining visible glyphs.

    A nonzero offset proves that source code, CID and Unicode are distinct.
    WeasyPrint's explicit bfchar map permits a small deterministic fixture.
    """
    writer = PdfWriter(clone_from=source)
    for page in writer.pages:
        for ref in page['/Resources']['/Font'].values():
            font = ref.get_object()
            assert font['/Subtype'] == '/Type0'
            original = font['/ToUnicode'].get_data()

            def remap_block(match):
                def remap_pair(pair):
                    code, dest = pair.groups()
                    if dest.lower() == b'002d' and hyphen_unicode is not None:
                        dest = hyphen_unicode.encode('utf-16-be').hex().encode()
                    return b'<' + f'{int(code, 16) + offset:04x}'.encode() + b'> <' + dest + b'>'
                return b'beginbfchar\n' + re.sub(
                    rb'<([\da-fA-F]{4})>\s*<([\da-fA-F]+)>', remap_pair, match[1]) + b'\nendbfchar'

            unicode_map = DecodedStreamObject()
            unicode_map.set_data(re.sub(
                rb'beginbfchar\s*(.*?)\s*endbfchar', remap_block, original, flags=re.S))
            font[NameObject('/ToUnicode')] = writer._add_object(unicode_map)
            encoding = DecodedStreamObject()
            encoding.set_data(f'''/CIDInit /ProcSet findresource begin
12 dict begin begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> def
/CMapName /Shifted-Codes def /CMapType 1 def /WMode 0 def
1 begincodespacerange <{offset:04x}> <ffff> endcodespacerange
1 begincidrange <{offset:04x}> <ffff> 0 endcidrange
endcmap CMapName currentdict /CMap defineresource pop end end'''.encode())
            if unsupported == 'inherited':
                encoding[NameObject('/UseCMap')] = NameObject('/Identity-H')
            elif unsupported == 'variable-width':
                encoding.set_data(encoding.get_data().replace(
                    b'1 begincodespacerange', b'2 begincodespacerange').replace(
                    b'endcodespacerange', b'<010000> <01ffff> endcodespacerange'))
            font[NameObject('/Encoding')] = writer._add_object(encoding)
        stream = ContentStream(page.get_contents(), writer)

        def remap_text(value):
            if not isinstance(value, (TextStringObject, ByteStringObject)):
                return value
            raw = value.original_bytes if isinstance(value, TextStringObject) else bytes(value)
            assert len(raw) % 2 == 0
            return ByteStringObject(b''.join(
                (int.from_bytes(raw[i:i + 2], 'big') + offset).to_bytes(2, 'big')
                for i in range(0, len(raw), 2)))

        for operands, operator in stream.operations:
            if operator == b'TJ':
                operands[0] = ArrayObject([remap_text(item) for item in operands[0]])
            elif operator in (b'Tj', b"'", b'"'):
                operands[-1] = remap_text(operands[-1])
        page[NameObject('/Contents')] = writer._add_object(stream)
    writer.write(target)


def _fixture(tmp_path, *, markup=MARKUP, encoding='shifted', **kwargs):
    plain, target = tmp_path / 'plain.pdf', tmp_path / 'mapped.pdf'
    # A real backend PDF before the product's extraction preflight.
    HTML(string=markup).write_pdf(plain)
    if encoding == 'identity':
        return plain
    _cmap_pdf(plain, target, offset=0 if encoding == 'custom' else 0x1000, **kwargs)
    return target


def _native_text(path):
    with pypdfium2.PdfDocument(path) as document:
        page = document[0]
        try:
            textpage = page.get_textpage()
            try:
                return textpage.get_text_bounded(errors='strict')
            finally:
                textpage.close()
        finally:
            page.close()


@pytest.mark.parametrize('encoding', ['identity', 'custom', 'shifted'])
def test_hard_hyphens_and_multiple_rtl_blocks_preserve_strong_contract(tmp_path, encoding):
    path = _fixture(tmp_path, encoding=encoding)
    original = path.read_bytes()
    expected = export_contract.from_tree(html.document_fromstring(MARKUP))
    # The fixture exercises the real native dehyphenation ambiguity.
    assert _native_text(path).count('\x02') == 2
    pages = export_contract.pdf_text_pages(path)
    assert 'recovery-assurance' in pages[0]
    assert 'cross-border' in pages[0]
    assert 'العربية Latin suffix.' in pages[0]
    assert 'office and affinity' in pages[0]
    export_contract.inspect(path, 'pdf', expected)
    assert export_contract.pdf_text_pages(original) == pages
    assert path.read_bytes() == original


def test_nonidentity_fixture_retains_original_rendered_pixels(tmp_path):
    path = _fixture(tmp_path)
    rendered = []
    for candidate in (tmp_path / 'plain.pdf', path):
        with pypdfium2.PdfDocument(candidate) as document:
            page = document[0]
            try:
                bitmap = page.render(scale=1)
                try:
                    rendered.append(bitmap.to_pil().tobytes())
                finally:
                    bitmap.close()
            finally:
                page.close()
    assert rendered[0] == rendered[1]


def test_soft_hyphen_mapping_cannot_be_guessed_as_a_hard_hyphen(tmp_path):
    path = _fixture(tmp_path, hyphen_unicode='\u00ad')
    original = path.read_bytes()
    assert _native_text(path).count('\x02') == 2
    with pytest.raises(ValueError, match='[Aa]mbigu'):
        export_contract.pdf_text_pages(path)
    assert path.read_bytes() == original


def test_changed_hyphen_unicode_mapping_still_fails_original_contract(tmp_path):
    path = _fixture(tmp_path, hyphen_unicode='_')
    expected = export_contract.from_tree(html.document_fromstring(MARKUP))
    assert 'recovery_' in export_contract.pdf_text_pages(path)[0]
    with pytest.raises(ValueError):
        export_contract.inspect(path, 'pdf', expected)


@pytest.mark.parametrize('before,after', [
    ('assurance', 'assurancX'),
    ('recovery-assurance', 'recoveryassurance'),
    ('العربية', 'العريية'),
    ('office and affinity', 'office and affinitX'),
])
def test_recovered_hyphen_does_not_hide_other_changed_content(tmp_path, before, after):
    path = _fixture(tmp_path, markup=MARKUP.replace(before, after))
    expected = export_contract.from_tree(html.document_fromstring(MARKUP))
    with pytest.raises(ValueError):
        export_contract.inspect(path, 'pdf', expected)


@pytest.mark.parametrize('unsupported', ['inherited', 'variable-width'])
def test_unsupported_cmap_hyphen_proof_remains_rejected(tmp_path, unsupported):
    path = _fixture(tmp_path, unsupported=unsupported)
    original = path.read_bytes()
    assert '\x02' in _native_text(path)
    with pytest.raises(ValueError, match='[Aa]mbigu'):
        export_contract.pdf_text_pages(path)
    assert path.read_bytes() == original


@pytest.mark.parametrize('language', ['en', 'es'])
def test_ambiguous_backend_payload_preserves_previous_export(tmp_path, monkeypatch, language):
    from weasyprint.document import Document

    path = _fixture(tmp_path, hyphen_unicode='\u00ad')
    payload = path.read_bytes()
    target = tmp_path / 'previous.pdf'
    target.write_bytes(b'previous verified export')
    # Isolate the real backend-byte acceptance boundary: the payload is a
    # genuine rendered PDF whose actual ToUnicode marks a soft hyphen.
    monkeypatch.setattr(Document, 'write_pdf', lambda _self: payload)
    with language_scope(language), pytest.raises(ValueError, match='[Aa]mbigu'):
        engine.render_pdf_weasyprint(MARKUP, target, tmp_path)
    assert target.read_bytes() == b'previous verified export'


def test_native_character_list_disagreement_is_not_reconciled(tmp_path, monkeypatch):
    path = _fixture(tmp_path)
    original_get_unicode = pdfium_raw.FPDFText_GetUnicode

    def changed_unicode(page, index):
        return ord('!') if index == 0 else original_get_unicode(page, index)

    monkeypatch.setattr(pdfium_raw, 'FPDFText_GetUnicode', changed_unicode)
    with pytest.raises(ValueError, match='[Aa]mbigu'):
        export_contract.pdf_text_pages(path)


@pytest.mark.parametrize('api,return_value', [('FPDFText_IsHyphen', 0), ('FPDFText_HasUnicodeMapError', 1)])
def test_native_marker_requires_positive_hyphen_and_mapping_proof(tmp_path, monkeypatch, api, return_value):
    path = _fixture(tmp_path)
    monkeypatch.setattr(pdfium_raw, api, lambda _page, _index: return_value)
    with pytest.raises(ValueError, match='[Aa]mbigu'):
        export_contract.pdf_text_pages(path)


@pytest.mark.parametrize('mutation', ['changed-character', 'extra-character'])
def test_actual_pdf_donor_disagreement_is_rejected(tmp_path, monkeypatch, mutation):
    from pypdf._page import PageObject

    path = _fixture(tmp_path)
    original_extract = PageObject.extract_text

    def changed_donor(page, *args, **kwargs):
        text = original_extract(page, *args, **kwargs)
        # The primary custom-CMap page uses PDFium. The donor is the only
        # pypdf reader after its validated two-byte decoding adjustment.
        return text.replace('Second', 'SeconX') if mutation == 'changed-character' else text + 'X'

    monkeypatch.setattr(PageObject, 'extract_text', changed_donor)
    with pytest.raises(ValueError, match='[Aa]mbigu'):
        export_contract.pdf_text_pages(path)
