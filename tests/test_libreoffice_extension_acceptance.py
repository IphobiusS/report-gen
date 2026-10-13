"""Negative controls for the native OXT acceptance oracle, without pretending UNO ran."""
import importlib.util
import json
from pathlib import Path
import zipfile

import fitz
from lxml import etree
import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('verify_lo_extension', ROOT / 'scripts/verify-libreoffice-extension.py')
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)


@pytest.mark.parametrize(('version', 'expected'), [
    ('LibreOffice 24.2.7.2 420(Build:2)', True),
    ('LibreOffice 26.2.6.3', True),
    ('LibreOfficeDev 26.8.0.0.alpha1', False),
    ('LibreOffice 26.2.0.0.beta1', False),
    ('LibreOffice 26.2.0.0.rc1', False),
    ('unavailable', False),
])
def test_stable_version_requires_real_release(version, expected):
    assert VERIFY.stable_version(version) is expected


def test_fixture_covers_editable_contexts_and_unicode(tmp_path):
    source = tmp_path / 'fixture.docx'
    rows = VERIFY.fixture(source)
    result = VERIFY.inspect_docx(source, rows)
    assert len(result['exact_literals']) == 8
    assert sum(row['table'] for row in rows) == 2
    assert sum(bool(row['target']) for row in rows) == 3
    assert '\U0001f642' in next(row['prefix'] for row in rows if row['name'] == 'rgUnicode')
    with zipfile.ZipFile(source) as archive:
        xml = etree.fromstring(archive.read('word/document.xml'))
    assert xml.xpath('count(//w:pStyle[@w:val="ListNumber"])', namespaces=VERIFY.NS) == 1
    assert not any(character in row['literal'] for row in rows for character in ('\u200b', '\u00ad', '\ufeff'))


@pytest.mark.parametrize('mutation', ['literal', 'language', 'language_expanded_to_prefix', 'hyperlink', 'bookmark'])
def test_docx_oracle_rejects_changed_native_content(tmp_path, mutation):
    source = tmp_path / 'fixture.docx'
    rows = VERIFY.fixture(source)
    with zipfile.ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    xml = etree.fromstring(files['word/document.xml'])
    if mutation == 'literal':
        node = xml.xpath('//w:p[w:bookmarkStart[@w:name="rgPlainUrl"]]//w:t', namespaces=VERIFY.NS)[-1]
        node.text = node.text.replace('batches', 'bat\u200bches')
    elif mutation == 'language':
        node = xml.xpath('//w:p[w:bookmarkStart[@w:name="rgPlainUrl"]]//w:lang', namespaces=VERIFY.NS)[0]
        node.set('{'+VERIFY.NS['w']+'}val', 'en-US')
    elif mutation == 'language_expanded_to_prefix':
        node = xml.xpath('//w:p[w:bookmarkStart[@w:name="rgPlainUrl"]]/w:r', namespaces=VERIFY.NS)[0]
        properties = etree.Element('{'+VERIFY.NS['w']+'}rPr')
        language = etree.SubElement(properties, '{'+VERIFY.NS['w']+'}lang')
        language.set('{'+VERIFY.NS['w']+'}val', VERIFY.TAG)
        node.insert(0, properties)
    elif mutation == 'bookmark':
        node = xml.xpath('//w:bookmarkStart[@w:name="rgPlainUrl"]', namespaces=VERIFY.NS)[0]
        node.getparent().remove(node)
    else:
        relations = etree.fromstring(files['word/_rels/document.xml.rels'])
        for node in relations:
            if node.get('Type', '').endswith('/hyperlink'):
                node.set('Target', 'https://wrong.example/')
        files['word/_rels/document.xml.rels'] = etree.tostring(relations)
    files['word/document.xml'] = etree.tostring(xml)
    with zipfile.ZipFile(source, 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    with pytest.raises(ValueError, match='(changed|lost|bookmark)'):
        VERIFY.inspect_docx(source, rows)


def pdf_fixture(path, shift=0, *, corrupt=False, duplicate=False, split_prefix=False):
    value = 'A1' * 20
    row = {'name': 'one', 'prefix': 'URL: ', 'value': value, 'literal': 'URL: ' + value,
           'target': None, 'language': VERIFY.TAG, 'table': False}
    document = fitz.open()
    page = document.new_page(width=210 * 72 / 25.4, height=297 * 72 / 25.4)
    right = 18.5 * 72 / 2.54
    if split_prefix:
        page.insert_text((70.866, 88), 'URL:', fontname='cour', fontsize=10)
        page.insert_text((right - 120, 100), value[:20], fontname='cour', fontsize=10)
    else:
        page.insert_text((right - 150 + shift, 100), 'URL: ' + value[:20], fontname='cour', fontsize=10)
    page.insert_text((70.866, 112), ('X' if corrupt else value[20]) + value[21:], fontname='cour', fontsize=10)
    if duplicate:
        page.insert_text((70.866, 140), row['literal'], fontname='cour', fontsize=10)
    document.save(path); document.close()
    return [row]


def test_line_fill_accepts_full_lines_and_records_actual_geometry(tmp_path):
    source = tmp_path / 'filled.pdf'
    rows = pdf_fixture(source)
    result = VERIFY.inspect_pdf(source, rows, require_fill=True)
    assert result['literal_checks'][0]['lines'] == 2
    assert abs(result['literal_checks'][0]['nonfinal_line_fill'][0]['gap_pt']) < .01


@pytest.mark.parametrize('shift', [-90, 18])
def test_line_fill_rejects_premature_wrap_and_overflow(tmp_path, shift):
    source = tmp_path / 'bad-fill.pdf'
    rows = pdf_fixture(source, shift)
    with pytest.raises(ValueError, match='Premature/overflow'):
        VERIFY.inspect_pdf(source, rows, require_fill=True)


@pytest.mark.parametrize('mutation', ['corrupt', 'duplicate'])
def test_pdf_requires_exact_unique_literals(tmp_path, mutation):
    source = tmp_path / 'bad-content.pdf'
    rows = pdf_fixture(source, **{mutation: True})
    with pytest.raises(ValueError, match='lost or duplicated exact literal'):
        VERIFY.inspect_pdf(source, rows, require_fill=True)


def test_line_fill_rejects_prefix_only_line_even_when_literal_fills(tmp_path):
    source = tmp_path / 'orphan-prefix.pdf'
    rows = pdf_fixture(source, split_prefix=True)
    with pytest.raises(ValueError, match='between prefix and literal'):
        VERIFY.inspect_pdf(source, rows, require_fill=True)


@pytest.mark.parametrize('changed', [None, 'destination', 'fragment'])
def test_native_hyperlink_field_retains_exact_uri_and_fragment(tmp_path, changed):
    source = tmp_path / 'fixture.docx'
    rows = VERIFY.fixture(source)
    with zipfile.ZipFile(source) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    xml = etree.fromstring(files['word/document.xml'])
    for row in rows:
        if not row['target']:
            continue
        paragraph = xml.xpath('//w:p[w:bookmarkStart[@w:name=$name]]', namespaces=VERIFY.NS, name=row['name'])[0]
        link = paragraph.find('w:hyperlink', namespaces=VERIFY.NS)
        base, fragment = row['target'].split('#')
        if changed == 'destination':
            base += 'wrong'
        if changed == 'fragment':
            fragment += 'wrong'
        index = paragraph.index(link)
        field = etree.Element('{'+VERIFY.NS['w']+'}r')
        instruction = etree.SubElement(field, '{'+VERIFY.NS['w']+'}instrText')
        instruction.text = f' HYPERLINK "{base}" \\l "{fragment}"'
        paragraph.insert(index, field)
        for run in list(link):
            index += 1; paragraph.insert(index, run)
        paragraph.remove(link)
    files['word/document.xml'] = etree.tostring(xml)
    with zipfile.ZipFile(source, 'w') as archive:
        for name, data in files.items():
            archive.writestr(name, data)
    if changed:
        with pytest.raises(ValueError, match='changed exact hyperlink'):
            VERIFY.inspect_docx(source, rows)
    else:
        assert len(VERIFY.inspect_docx(source, rows)['exact_literals']) == 8


def test_root_is_blocked_before_unopkg_and_produces_failure_receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(VERIFY.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setattr(VERIFY, 'run', lambda *a, **k: pytest.fail('Must not launch any installer as root'))
    output = tmp_path / 'root-guard'
    assert VERIFY.main(['--output', str(output)]) == 1
    result = json.loads((output / 'validation.json').read_text())
    assert result['status'] == 'failed'
    assert 'non-root' in result['error']
    assert not result['checks']
