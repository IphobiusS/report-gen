"""Unicode stays visible; PDF verification reads actual CMaps and logical text."""
from copy import deepcopy

from lxml import html
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, StreamObject
import pytest

import engine
import export_contract
from error_messages import language_scope


def source(language='en', text='Original café observation.'):
    return {'meta': {'lang': language, 'theme': 'corporativo',
                     'report_title': 'Original cover', 'report_subtitle': 'Cover subtitle',
                     'client': 'Synthetic client'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F01', 'title': 'Unicode observation',
                          'description_md': text,
                          'walkthrough': [{'lead': 'Compare', 'command': 'ORIGINAL_CODE=42'}]}]}


def markup(data, tmp_path):
    return engine.render_html(engine.build_env(), data, tmp_path, {}, False,
                              engine.load_lang(data['meta']['lang']))


@pytest.mark.parametrize('language', ['es', 'en'])
def test_missing_glyph_rejects_before_overwriting_output(tmp_path, language):
    # Plane 16 private-use character: no bundled/system font supplies this
    # deliberately unsupported fixture. No dependency on emoji fonts on CI.
    original = b'previous verified output'
    target = tmp_path / 'report.pdf'
    target.write_bytes(original)
    data = source(language, 'Unsupported \U0010fffd marker.')
    before = deepcopy(data)
    with language_scope(language), pytest.raises(ValueError, match=r'U\+10FFFD') as caught:
        engine.render_pdf_weasyprint(markup(data, tmp_path), target, tmp_path)
    assert ('font' if language == 'en' else 'fuente') in str(caught.value).lower()
    assert target.read_bytes() == original
    assert data == before
    # Failed rendering must not poison the next job or leave a partial output.
    valid = source(language)
    engine.render_pdf_weasyprint(markup(valid, tmp_path), target, tmp_path)
    assert target.read_bytes().startswith(b'%PDF')


@pytest.mark.parametrize('language', ['en', 'es'])
@pytest.mark.parametrize('body', ['NFC café; NFD cafe\u0301. Remediación.',
                                 'Latin prefix العربية Latin suffix.'])
def test_supported_unicode_preserves_contract(tmp_path, language, body):
    data = source(language, body)
    document = markup(data, tmp_path)
    expected = export_contract.from_tree(html.document_fromstring(document))
    target = tmp_path / 'unicode.pdf'
    engine.render_pdf_weasyprint(document, target, tmp_path)
    checks = export_contract.inspect(target, 'pdf', expected)
    assert checks['paragraphs_checked'] >= 1
    assert export_contract.normal(body) in export_contract.profile(target, 'pdf', expected)['']['text']


def explicit_identity_cmap(source_path, target_path):
    """Use a valid custom Encoding without changing rendered glyphs/ToUnicode."""
    writer = PdfWriter(clone_from=source_path)
    encoding = DecodedStreamObject()
    encoding.set_data(b'''/CIDInit /ProcSet findresource begin
12 dict begin begincmap
/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> def
/CMapName /RG-Identity def /CMapType 1 def /WMode 0 def
1 begincodespacerange <0000> <ffff> endcodespacerange
1 begincidrange <0000> <ffff> 0 endcidrange
endcmap CMapName currentdict /CMap defineresource pop end end''')
    ref = writer._add_object(encoding)
    changed = 0
    for page in writer.pages:
        for value in page['/Resources']['/Font'].values():
            font = value.get_object()
            if font.get('/Encoding') == '/Identity-H':
                font[NameObject('/Encoding')] = ref
                changed += 1
    assert changed
    writer.write(target_path)


def test_custom_cmap_visible_content_passes_strong_contract(tmp_path):
    data = source()
    document = markup(data, tmp_path)
    expected = export_contract.from_tree(html.document_fromstring(document))
    initial, target = tmp_path / 'plain.pdf', tmp_path / 'cmap.pdf'
    engine.render_pdf_weasyprint(document, initial, tmp_path)
    explicit_identity_cmap(initial, target)
    # Verify the actual custom Encoding fixture, without requiring an older
    # extractor's bug to remain present after a dependency update.
    encodings = [font.get_object().get('/Encoding').get_object()
                 for page in PdfReader(target).pages
                 for font in page['/Resources']['/Font'].values()]
    assert any(isinstance(encoding, StreamObject) and b'begincidrange' in encoding.get_data()
               for encoding in encodings)
    checks = export_contract.inspect(target, 'pdf', expected)
    assert checks['metadata_values_checked'] >= 1
    assert '\x00' not in export_contract.profile(target, 'pdf', expected)['']['text']


@pytest.mark.parametrize('mutation', ['cover', 'paragraph', 'code', 'arabic'])
def test_custom_cmap_does_not_hide_changed_content(tmp_path, mutation):
    data = source(text='Latin prefix العربية Latin suffix.')
    expected = export_contract.from_tree(html.document_fromstring(markup(data, tmp_path)))
    changed = deepcopy(data)
    if mutation == 'cover':
        changed['meta']['report_title'] = 'Changed cover'
    elif mutation == 'paragraph':
        changed['findings'][0]['description_md'] = 'Paragraph replaced.'
    elif mutation == 'arabic':
        changed['findings'][0]['description_md'] = 'Latin prefix العريية Latin suffix.'
    else:
        changed['findings'][0]['walkthrough'][0]['command'] = 'CHANGED_CODE=42'
    initial, target = tmp_path / 'changed.pdf', tmp_path / 'changed-cmap.pdf'
    engine.render_pdf_weasyprint(markup(changed, tmp_path), initial, tmp_path)
    explicit_identity_cmap(initial, target)
    with pytest.raises(ValueError):
        export_contract.inspect(target, 'pdf', expected)


def narrow_text(text, extra=''):
    return ('<html lang="en"><body><p style="width:65px;font-family:DejaVu Sans;'
            'font-size:12px">' + text + '</p>' + extra + '</body></html>')


def test_wrapped_literal_hyphen_is_preserved_without_guessing(tmp_path):
    document = narrow_text('recovery-assurance')
    expected = export_contract.from_tree(html.document_fromstring(document))
    target = tmp_path / 'hyphen.pdf'
    engine.render_pdf_weasyprint(document, target, tmp_path)
    assert 'recovery-\nassurance' in export_contract.pdf_text_pages(target)[0]
    export_contract.inspect(target, 'pdf', expected)
    # Dropping a real hyphen must still fail, including when it was wrapped.
    engine.render_pdf_weasyprint(narrow_text('recoveryassurance'), target, tmp_path)
    with pytest.raises(ValueError):
        export_contract.inspect(target, 'pdf', expected)


def test_soft_hyphen_does_not_authorize_removing_a_visible_hyphen(tmp_path):
    document = '<html lang="en"><body><p>recovery\u00adassurance</p></body></html>'
    expected = export_contract.from_tree(html.document_fromstring(document))
    target = tmp_path / 'soft.pdf'
    engine.render_pdf_weasyprint(document, target, tmp_path)
    export_contract.inspect(target, 'pdf', expected)
    # When a discretionary hyphen is drawn as U+2010, the existing strict
    # contract cannot prove its source. Keep the rejection, never delete a
    # visible hyphen globally or make literal word mutations pass.
    engine.render_pdf_weasyprint(narrow_text('recovery\u00adassurance'), target, tmp_path)
    assert '\u2010' in export_contract.pdf_text_pages(target)[0]
    with pytest.raises(ValueError):
        export_contract.inspect(target, 'pdf', expected)


def test_custom_cmap_wrapped_hyphen_is_proved_from_pdf_text(tmp_path):
    initial, target = tmp_path / 'plain.pdf', tmp_path / 'cmap.pdf'
    engine.render_pdf_weasyprint(narrow_text('recovery-assurance'), initial, tmp_path)
    explicit_identity_cmap(initial, target)
    before = target.read_bytes()
    expected = export_contract.from_tree(html.document_fromstring(narrow_text('recovery-assurance')))
    assert 'recovery-assurance' in export_contract.pdf_text_pages(target)[0]
    export_contract.inspect(target, 'pdf', expected)
    assert target.read_bytes() == before


@pytest.mark.parametrize('language', ['en', 'es'])
def test_rtl_wrapped_hyphen_preserves_supported_content(tmp_path, language):
    target = tmp_path / 'prior.pdf'
    target.write_bytes(b'previous verified output')
    document = narrow_text('recovery-assurance', '<p>Latin العربية suffix.</p>')
    expected = export_contract.from_tree(html.document_fromstring(document))
    with language_scope(language):
        engine.render_pdf_weasyprint(document, target, tmp_path)
    export_contract.inspect(target, 'pdf', expected)
    assert 'recovery-assurance' in export_contract.pdf_text_pages(target)[0]


def test_blank_page_without_resources_is_valid(tmp_path):
    target = tmp_path / 'blank.pdf'
    writer = PdfWriter()
    page = writer.add_blank_page(width=595, height=842)
    page.pop('/Resources', None)
    writer.write(target)
    assert export_contract.pdf_text_pages(target) == ['']


def test_indirect_font_and_xobject_resource_dictionaries(tmp_path):
    data = source()
    document = markup(data, tmp_path)
    expected = export_contract.from_tree(html.document_fromstring(document))
    initial, cmap, target = (tmp_path / name for name in ('plain.pdf', 'cmap.pdf', 'indirect.pdf'))
    engine.render_pdf_weasyprint(document, initial, tmp_path)
    explicit_identity_cmap(initial, cmap)
    writer = PdfWriter(clone_from=cmap)
    for page in writer.pages:
        resources = page['/Resources']
        fonts = resources['/Font']
        resources[NameObject('/Font')] = writer._add_object(fonts)
        resources[NameObject('/XObject')] = writer._add_object(DictionaryObject())
        page[NameObject('/Resources')] = writer._add_object(resources)
    writer.write(target)
    export_contract.inspect(target, 'pdf', expected)
