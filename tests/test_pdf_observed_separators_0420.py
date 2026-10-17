"""Positioned PDF spaces must be observed, never inferred from source text."""
from io import BytesIO

from lxml import html
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject
import pytest

import export_contract as contract


UNIT = 'Label: https://bank.example/'


def positioned_pdf(gap=277.78, target='https://bank.example/'):
    """A font switch plus initial TJ displacement exposes the extractor bug."""
    writer = PdfWriter()
    page = writer.add_blank_page(width=400, height=150)

    def font(name):
        return DictionaryObject({NameObject('/Type'): NameObject('/Font'),
                                 NameObject('/Subtype'): NameObject('/Type1'),
                                 NameObject('/BaseFont'): NameObject(name)})

    page[NameObject('/Resources')] = DictionaryObject({
        NameObject('/Font'): DictionaryObject({NameObject('/F1'): font('/Helvetica-Bold'),
                                              NameObject('/F2'): font('/Helvetica')})})
    stream = DecodedStreamObject()
    stream.set_data(('BT /F1 12 Tf 20 100 Td (Label:) Tj /F2 12 Tf '
                     f'[-{gap} ({target})] TJ ET').encode('ascii'))
    page[NameObject('/Contents')] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def test_real_positioned_separator_survives_font_change(tmp_path):
    blob = positioned_pdf()
    # This independent reader omits the positioning gap, although it preserves
    # every other character. No expected text is passed to pdf_text_pages.
    assert PdfReader(BytesIO(blob)).pages[0].extract_text() == UNIT.replace(': ', ':')
    assert contract.normal(contract.pdf_text_pages(blob)[0]) == UNIT
    path = tmp_path / 'positioned.pdf'
    path.write_bytes(blob)
    expected = contract.from_tree(html.document_fromstring('<p>' + UNIT + '</p>'))
    assert contract.inspect(path, 'pdf', expected)['paragraphs_checked'] == 1


@pytest.mark.parametrize('kind', ['no-gap', 'changed-target', 'missing-target', 'reused-label'])
def test_reconciliation_cannot_create_missing_text_or_duplicate_occurrences(tmp_path, kind):
    target = 'https://bank.example/'
    gap = 277.78
    if kind == 'no-gap':
        gap = 0
    elif kind == 'changed-target':
        target = 'https://other.example/'
    elif kind == 'missing-target':
        target = ''
    path = tmp_path / 'changed.pdf'
    blob = positioned_pdf(gap, target)
    path.write_bytes(blob)
    if kind == 'no-gap':
        assert contract.normal(contract.pdf_text_pages(blob)[0]) == UNIT.replace(': ', ':')
    markup = '<p>' + UNIT + '</p>' + ('<p>Label:</p>' if kind == 'reused-label' else '')
    expected = contract.from_tree(html.document_fromstring(markup))
    with pytest.raises(ValueError, match='PDF'):
        contract.inspect(path, 'pdf', expected)


@pytest.mark.parametrize('native', ['Label: https://evil.example/', 'Label: https://bank.example',
                                  'https://bank.example/ Label:', 'Label: Xhttps://bank.example/'])
def test_whole_page_character_disagreement_keeps_primary_text(native):
    primary = UNIT.replace(': ', ':')
    assert contract._pdf_observed_separators(primary, native) == primary


def test_reconciled_offsets_retain_observed_physical_line_boundaries():
    primary = 'Label:https://bank.example/\nNext line'
    native = 'Label: https://bank.example/\r\nNext line'
    reconciled = contract._pdf_observed_separators(primary, native)
    assert reconciled == UNIT + '\nNext line'
    assert contract._pdf_line_edges(reconciled) == {
        'starts': {0, len(UNIT) + 1}, 'ends': {len(UNIT), len(UNIT) + len(' Next line')}}
    # A native geometric line break is not transplanted into a primary line.
    assert contract._pdf_observed_separators('Label:URL', 'Label:\nURL') == 'Label: URL'


def test_native_mapping_errors_cannot_supply_separators(monkeypatch):
    import pypdfium2.raw as raw
    monkeypatch.setattr(raw, 'FPDFText_HasUnicodeMapError', lambda _page, _index: 1)
    assert contract.normal(contract.pdf_text_pages(positioned_pdf())[0]) == UNIT.replace(': ', ':')
