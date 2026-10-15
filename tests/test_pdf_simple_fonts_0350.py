"""Simple-font hard hyphens need explicit source, font and geometry evidence."""
from pathlib import Path

from fontTools.ttLib import TTFont
from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject, DecodedStreamObject, DictionaryObject, FloatObject, NameObject, NumberObject,
)
import pypdfium2
import pypdfium2.raw as raw
import pytest

import export_contract as contract


ROOT = Path(__file__).resolve().parents[1]


def fixture(tmp_path, *, simple_type='/TrueType', incomplete=False, mutation=None):
    writer = PdfWriter()
    page = writer.add_blank_page(300, 200)
    codes = sorted(set(b'recovery-assurance X'))
    if incomplete:
        codes.remove(ord('X'))
    if mutation == 'missing-hyphen':
        codes.remove(ord('-'))
    pairs = [f'<{code:02x}> <{code:04x}>'.encode() for code in codes]
    if mutation == 'duplicate':
        pairs.append(b'<2d> <002d>')
    if mutation == 'soft-hyphen':
        pairs = [pair.replace(b'<2d> <002d>', b'<2d> <00ad>') for pair in pairs]
    count = len(pairs) + (mutation == 'incorrect-count')
    codespace = (b'2 begincodespacerange <00> <ff> <0100> <01ff> endcodespacerange'
                 if mutation == 'variable-width' else b'1 begincodespacerange <00> <ff> endcodespacerange')
    cmap = DecodedStreamObject()
    cmap.set_data(codespace + b'\n' + str(count).encode() + b' beginbfchar\n'
                  + b'\n'.join(pairs) + b'\nendbfchar')
    if mutation == 'inherited':
        cmap[NameObject('/UseCMap')] = NameObject('/Identity-H')
    font = DictionaryObject({
        NameObject('/Type'): NameObject('/Font'),
        NameObject('/Subtype'): NameObject(simple_type),
        NameObject('/BaseFont'): NameObject('/Carlito' if simple_type == '/TrueType' else '/Helvetica'),
        NameObject('/Encoding'): NameObject('/WinAnsiEncoding'),
        NameObject('/ToUnicode'): writer._add_object(cmap),
    })
    if simple_type == '/TrueType':
        font_path = ROOT / 'themes/fonts/Carlito-Regular.ttf'
        font_file = DecodedStreamObject()
        font_file.set_data(b'invalid embedded font' if mutation == 'different-font-bytes' else font_path.read_bytes())
        with TTFont(font_path, recalcTimestamp=False) as source:
            units = source['head'].unitsPerEm
            codepoints = source.getBestCmap()
            widths = [source['hmtx'][codepoints[code]][0] * 1000 / units for code in range(32, 127)]
        descriptor = DictionaryObject({
            NameObject('/Type'): NameObject('/FontDescriptor'),
            NameObject('/FontName'): NameObject('/Carlito'),
            NameObject('/Flags'): NumberObject(32),
            NameObject('/FontBBox'): ArrayObject([NumberObject(value) for value in (0, -200, 1000, 1000)]),
            NameObject('/Ascent'): NumberObject(1000),
            NameObject('/Descent'): NumberObject(3000 if mutation == 'wrong-position' else -200),
            NameObject('/CapHeight'): NumberObject(700),
            NameObject('/ItalicAngle'): NumberObject(0),
            NameObject('/StemV'): NumberObject(80),
            NameObject('/FontFile2'): writer._add_object(font_file),
        })
        font.update({
            NameObject('/FirstChar'): NumberObject(32), NameObject('/LastChar'): NumberObject(126),
            NameObject('/Widths'): ArrayObject([FloatObject(width) for width in widths]),
            NameObject('/FontDescriptor'): writer._add_object(descriptor),
        })
    fonts = DictionaryObject({NameObject('/F1'): writer._add_object(font)})
    if mutation == 'ambiguous-font':
        fonts[NameObject('/F2')] = writer._add_object(DictionaryObject(font))
    resources = DictionaryObject({NameObject('/Font'): fonts})
    content = b'BT /F1 12 Tf 36 150 Td (recovery-) Tj 0 -15 Td (assurance X) Tj ET'
    if mutation == 'executed-form':
        form = DecodedStreamObject()
        form.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Form'),
                     NameObject('/BBox'): ArrayObject(page.mediabox), NameObject('/Resources'): resources})
        form.set_data(b'')
        resources[NameObject('/XObject')] = DictionaryObject({NameObject('/Form'): writer._add_object(form)})
        content += b' /Form Do'
    page[NameObject('/Resources')] = resources
    stream = DecodedStreamObject()
    stream.set_data(content)
    page[NameObject('/Contents')] = writer._add_object(stream)
    path = tmp_path / 'simple.pdf'
    writer.write(path)
    return path


def native_marker(path):
    with pypdfium2.PdfDocument(path) as document:
        page = document[0]
        textpage = page.get_textpage()
        try:
            text = textpage.get_text_bounded(errors='strict')
            markers = [index for index in range(textpage.count_chars())
                       if raw.FPDFText_GetUnicode(textpage, index) == 2]
            assert markers
            assert all(raw.FPDFText_IsHyphen(textpage, index) == 1 for index in markers)
            assert all(raw.FPDFText_HasUnicodeMapError(textpage, index) == 0 for index in markers)
            return text
        finally:
            textpage.close()
            page.close()


@pytest.mark.parametrize('simple_type', ['/TrueType', '/Type1'])
def test_fixed_one_byte_font_proves_whole_page_without_altering_encoding(tmp_path, simple_type):
    path = fixture(tmp_path, simple_type=simple_type)
    original = path.read_bytes()
    reader = PdfReader(path)
    font = reader.pages[0]['/Resources']['/Font']['/F1']
    assert '\x02' in native_marker(path)
    assert 'recovery-' in contract._pdf_hyphen_donor(reader.pages[0], reader)
    assert font['/Encoding'] == '/WinAnsiEncoding'
    assert contract.pdf_text_pages(path, geometry_pages=(0,)) == ['recovery-assurance X']
    assert path.read_bytes() == original


def test_unrelated_missing_mapping_does_not_prevent_independently_proved_simple_hyphen(tmp_path):
    path = fixture(tmp_path, incomplete=True)
    original = path.read_bytes()
    reader = PdfReader(path)
    with pytest.raises(ValueError, match='Unicode'):
        contract._pdf_hyphen_donor(reader.pages[0], reader)
    assert native_marker(path) == 'recovery\x02assurance X'
    assert contract.pdf_text_pages(path, geometry_pages=(0,)) == ['recovery-assurance X']
    assert path.read_bytes() == original


@pytest.mark.parametrize('mutation', [
    'missing-hyphen', 'soft-hyphen', 'inherited', 'variable-width', 'incorrect-count', 'duplicate',
    'different-font-bytes', 'ambiguous-font', 'wrong-position', 'executed-form',
])
def test_partial_proof_never_accepts_unproved_mapping_font_or_position(tmp_path, mutation):
    path = fixture(tmp_path, incomplete=True, mutation=mutation)
    original = path.read_bytes()
    assert '\x02' in native_marker(path)
    with pytest.raises(ValueError, match='[Aa]mbigu'):
        contract.pdf_text_pages(path, geometry_pages=(0,))
    assert path.read_bytes() == original
