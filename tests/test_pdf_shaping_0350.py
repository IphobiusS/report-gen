"""Real multilingual glyph shaping must not change authored text or URLs.

The dedicated R16 workflow requires Noto; ordinary installs without those fonts
skip only this font-dependent module rather than silently testing tofu glyphs.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess

from lxml import html
from pypdf import PdfReader, PdfWriter
from pypdf.generic import DecodedStreamObject, NameObject
import pypdfium2
import pypdfium2.raw as raw
import pytest
from weasyprint import HTML

import export_contract as contract
from error_messages import language_scope


URL = 'https://docs.example.invalid/evidence/registro#ação-ñ-über-العربية-हिन्दी-한국어-日本語'
MARKUP = '''<html lang="pt-BR"><head><style>
@page { size:A4; margin:20mm }
body { font-family: "DejaVu Sans", "Noto Sans Devanagari", "Noto Sans CJK JP", sans-serif;
       font-size:12px }
table { width:90%; border-collapse:collapse }
td, th { border:1px solid #777; padding:5px }
.wrapped { width:65px; font-family:"DejaVu Sans" }
</style></head><body><h1>Independent multilingual shaping check</h1>
<p>Registro multilingüe: acción, ação, العربية, हिन्दी, 한국어, 日本語.</p>
<p><a href="''' + URL + '''">''' + URL + '''</a></p>
<p class="wrapped">recovery-assurance</p>
<table><tr><th>Operation</th><th>State</th></tr>
<tr><td>Approved</td><td>Approved with conditions</td></tr>
<tr><td>Pending</td><td>Awaiting evidence</td></tr></table>
<p>End of independently authored source.</p></body></html>'''


@pytest.fixture(scope='module', autouse=True)
def required_fonts():
    missing = []
    for family in ('Noto Sans Devanagari', 'Noto Sans CJK JP'):
        if not shutil.which('fc-match'):
            missing.append(family)
            continue
        result = subprocess.run(['fc-match', '--format=%{family}', family],
                                capture_output=True, text=True, check=True)
        if family not in result.stdout:
            missing.append(family)
    if missing:
        message = 'Multiscript shaping fonts unavailable: ' + ', '.join(missing)
        if os.environ.get('REPORT_GEN_REQUIRE_MULTISCRIPT_FONTS') == '1':
            pytest.fail(message)
        pytest.skip(message)


def render(tmp_path, markup=MARKUP, name='shaping.pdf'):
    path = tmp_path / name
    HTML(string=markup).write_pdf(path)
    return path


def native(path):
    with pypdfium2.PdfDocument(path) as document:
        page = document[0]
        textpage = page.get_textpage()
        try:
            return {'text': textpage.get_text_bounded(errors='strict'),
                    'errors': [(index, raw.FPDFText_GetUnicode(textpage, index))
                               for index in range(textpage.count_chars())
                               if raw.FPDFText_HasUnicodeMapError(textpage, index) == 1]}
        finally:
            textpage.close()
            page.close()


def rewrite_map(source, target, mutate):
    writer = PdfWriter(clone_from=source)
    changed = False
    for page in writer.pages:
        for ref in page['/Resources']['/Font'].values():
            font = ref.get_object()
            original = font['/ToUnicode'].get_data()
            if re.search(rb'<[\da-fA-F]{4}>\s*<>', original):
                replacement = mutate(original)
                stream = DecodedStreamObject()
                stream.set_data(replacement)
                font[NameObject('/ToUnicode')] = writer._add_object(stream)
                changed = True
    assert changed, 'The fixture must contain an explicit empty shaping entry'
    writer.write(target)
    return target


def remove_empty_mapping(data):
    def block(match):
        content, count = re.subn(rb'<[\da-fA-F]{4}>\s*<>\s*', b'', match[2])
        return str(int(match[1]) - count).encode() + b' beginbfchar\n' + content + b'endbfchar'
    return re.sub(rb'(\d+)\s+beginbfchar\s*(.*?)endbfchar', block, data, flags=re.S)


def test_real_shaping_hyphen_table_and_multilingual_url_preserve_contract(tmp_path):
    path = render(tmp_path)
    before = path.read_bytes()
    observed = native(path)
    assert observed['errors'], 'The fixture must exercise a native empty-map error'
    assert '\x02' in observed['text'], 'The fixture must exercise a native wrapped hard hyphen'
    # Current Noto Sans Devanagari emits CID 0x0220 for the empty continuation
    # glyph in हिन्दी. Different Noto revisions may assign a different CID;
    # the required regression is the same explicit empty mapping and proof.
    if any(code == 0x0220 for _, code in observed['errors']):
        assert '\u0220' in observed['text']
    pages = contract.pdf_text_pages(path)
    text = '\n'.join(pages)
    for expected in ('العربية', 'हिन्दी', '한국어', '日本語', 'recovery-assurance'):
        assert expected in text
    assert '\x02' not in text and '\u0220' not in text
    assert 'Approved Approved with conditions' in contract.normal(text)
    expected = contract.from_tree(html.document_fromstring(MARKUP))
    contract.inspect(path, 'pdf', expected)
    assert contract.pdf_text_pages(before) == pages
    assert path.read_bytes() == before


@pytest.mark.parametrize('before,after', [
    ('End of independently authored source.', 'End of independently altered source.'),
    ('#ação-ñ-über-', '#ação-ñ-uber-'),
    ('Approved with conditions', 'Approved without conditions'),
    ('हिन्दी', 'हिन्द'),
])
def test_valid_empty_shaping_does_not_hide_altered_authored_content(tmp_path, before, after):
    path = render(tmp_path, MARKUP.replace(before, after))
    expected = contract.from_tree(html.document_fromstring(MARKUP))
    with pytest.raises(ValueError):
        contract.inspect(path, 'pdf', expected)


def test_absent_mapping_is_not_an_explicit_empty_shaping_mapping(tmp_path):
    source = render(tmp_path)
    target = rewrite_map(source, tmp_path / 'missing-map.pdf', remove_empty_mapping)
    with pytest.raises(ValueError):
        contract.pdf_text_pages(target)


def test_duplicate_empty_mapping_is_not_accepted(tmp_path):
    source = render(tmp_path)

    def duplicate(data):
        entry = re.search(rb'<[\da-fA-F]{4}>\s*<>', data)[0]
        return data.replace(b'endcmap', b'1 beginbfchar\n' + entry + b'\nendbfchar\nendcmap')

    target = rewrite_map(source, tmp_path / 'duplicate-map.pdf', duplicate)
    with pytest.raises(ValueError):
        contract.pdf_text_pages(target)


def test_removing_actual_text_with_empty_mapping_cannot_pass_the_contract(tmp_path):
    source = render(tmp_path)
    target = tmp_path / 'removed-glyph.pdf'
    writer = PdfWriter(clone_from=source)
    changed = False
    for page in writer.pages:
        for ref in page['/Resources']['/Font'].values():
            font = ref.get_object()
            original = font['/ToUnicode'].get_data()
            replacement, count = re.subn(rb'(<[\da-fA-F]{4}>)\s*<0045>', rb'\1 <>', original)
            if count:
                stream = DecodedStreamObject()
                stream.set_data(replacement)
                font[NameObject('/ToUnicode')] = writer._add_object(stream)
                changed = True
    assert changed, 'The capital E in the authored ending must be removed'
    writer.write(target)
    with pytest.raises(ValueError):
        contract.inspect(target, 'pdf', contract.from_tree(html.document_fromstring(MARKUP)))


def test_empty_mapping_requires_independent_position_proof(tmp_path, monkeypatch):
    import pdfplumber.page

    path = render(tmp_path)
    original = pdfplumber.page.Page.chars.fget

    def displaced(page):
        return [dict(char, x0=char['x0'] + 20) if char['text'] == '' else char
                for char in original(page)]

    monkeypatch.setattr(pdfplumber.page.Page, 'chars', property(displaced))
    with pytest.raises(ValueError):
        contract.pdf_text_pages(path)


def test_empty_mapping_does_not_authorize_other_native_map_errors(tmp_path, monkeypatch):
    path = render(tmp_path)
    original = raw.FPDFText_HasUnicodeMapError
    monkeypatch.setattr(raw, 'FPDFText_HasUnicodeMapError',
                        lambda page, index: 1 if index == 0 else original(page, index))
    with pytest.raises(ValueError):
        contract.pdf_text_pages(path)


def test_proof_keeps_original_source_cmaps_unchanged(tmp_path):
    path = render(tmp_path)
    before = path.read_bytes()
    reader = PdfReader(path)
    maps = [ref.get_object()['/ToUnicode'].get_data()
            for ref in reader.pages[0]['/Resources']['/Font'].values()]
    contract.pdf_text_pages(path)
    assert Path(path).read_bytes() == before
    after = PdfReader(path)
    assert maps == [ref.get_object()['/ToUnicode'].get_data()
                    for ref in after.pages[0]['/Resources']['/Font'].values()]


def test_genuine_unicode_character_is_preserved_beside_empty_shaping_glyph(tmp_path):
    markup = MARKUP.replace('End of independently authored source.', 'Genuine authored character: Ǡ.')
    path = render(tmp_path, markup)
    text = '\n'.join(contract.pdf_text_pages(path))
    assert 'Genuine authored character: Ǡ.' in text
    assert text.count('Ǡ') == 1
    contract.inspect(path, 'pdf', contract.from_tree(html.document_fromstring(markup)))


@pytest.mark.parametrize('language,message', [
    ('es', 'Extracción de región PDF ambigua: F01'),
    ('en', 'Ambiguous PDF region extraction: F01'),
    ('pt', 'Extração de região do PDF ambígua: F01'),
])
def test_regional_shaping_failure_uses_requested_backend_language(tmp_path, language, message):
    markup = MARKUP.replace('<body>', '<body><section class="frontsec" id="start">Start</section>'
                            '<section class="finding" id="F01">'
                            '<h2 class="f-title">Shaping finding</h2>').replace('</body>', '</section></body>')
    source = render(tmp_path, markup)
    expected = contract.from_tree(html.document_fromstring(markup))
    assert expected['pdf_regions']
    assert contract.inspect(source, 'pdf', expected)['pdf_finding_regions_checked'] == 1
    target = rewrite_map(source, tmp_path / 'ambiguous-region.pdf', remove_empty_mapping)
    with language_scope(language), pytest.raises(ValueError) as failure:
        contract._pdf_region_profiles(target, expected['pdf_regions'])
    assert str(failure.value) == message
