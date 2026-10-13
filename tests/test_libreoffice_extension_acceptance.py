"""Negative controls for the native OXT acceptance oracle, without pretending UNO ran."""
import importlib.util
import json
from pathlib import Path
import shutil
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


def pdf_fixture(path, shift=0, *, corrupt=False, duplicate=False, split_prefix=False, paint_order=False):
    value = 'A1' * 20
    row = {'name': 'one', 'prefix': 'URL: ', 'value': value, 'literal': 'URL: ' + value,
           'target': None, 'language': VERIFY.TAG, 'table': False}
    document = fitz.open()
    page = document.new_page(width=210 * 72 / 25.4, height=297 * 72 / 25.4)
    right = 18.5 * 72 / 2.54
    if paint_order:
        page.insert_text((right - 150, 100), 'URL', fontname='cour', fontsize=10)
        page.insert_text((right - 120, 100), value[:20], fontname='cour', fontsize=10)
        page.insert_text((right - 132, 100), ':', fontname='cour', fontsize=10)
    elif split_prefix:
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


def test_visual_reading_order_does_not_confuse_late_font_paint_with_changed_text(tmp_path):
    source = tmp_path / 'late-font.pdf'
    rows = pdf_fixture(source, paint_order=True)
    with fitz.open(source) as document:
        assert 'URL:' not in document[0].get_text()
    result = VERIFY.inspect_pdf(source, rows, require_fill=True)
    assert result['literal_checks'][0]['prefix_continues_on_same_line']


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


def test_failed_fallback_oracle_still_collects_enabled_profile_but_fails_gate(tmp_path, monkeypatch):
    monkeypatch.setattr(VERIFY.os, 'geteuid', lambda: 1000, raising=False)
    stages_seen = []
    def command(command, output, **kwargs):
        if command[-1] == '--version':
            return {'stdout': 'LibreOffice 24.2.7.2'}
        if '--worker' in command:
            config = json.loads(Path(command[-1]).read_text())
            if config.get('control'):
                return {'stdout': ''}
            stages_seen.append(config['enabled'])
            stages = ['original', 'reopened', 'reflow', 'reopened-reflow'] if config['enabled'] else ['fallback']
            for stage in stages:
                shutil.copyfile(config['source'], Path(config['output']) / (stage + '.docx'))
        return {'stdout': ''}
    def inspect(path, rows, **kwargs):
        if Path(path).stem == 'fallback':
            raise ValueError('Synthetic negative fallback oracle')
        return {'literal_checks': []}
    monkeypatch.setattr(VERIFY, 'run', command)
    monkeypatch.setattr(VERIFY, 'inspect_pdf', inspect)
    output = tmp_path / 'phases'
    assert VERIFY.main(['--output', str(output)]) == 1
    result = json.loads((output / 'validation.json').read_text())
    assert stages_seen == [False, True]
    assert result['status'] == 'failed'
    assert 'fallback' in result['phase_errors']
    assert set(result['checks']['enabled']) == {'original', 'reopened', 'reflow', 'reopened-reflow'}


def test_native_environment_does_not_inject_foreign_python_or_mutate_parent(monkeypatch):
    for name in VERIFY.NATIVE_ENV_UNSET:
        monkeypatch.setenv(name, '/foreign-python/' + name)
    monkeypatch.setenv('PATH', '/usr/bin:/custom/bin')
    environment = VERIFY.native_environment()
    assert not set(VERIFY.NATIVE_ENV_UNSET).intersection(environment)
    assert environment['PATH'] == '/usr/bin:/custom/bin'
    assert environment['SAL_USE_VCLPLUGIN'] == 'svp'
    for name in VERIFY.NATIVE_ENV_UNSET:
        assert VERIFY.os.environ[name] == '/foreign-python/' + name


def test_installer_control_is_deterministic_and_contains_no_report_adapter(tmp_path):
    first = VERIFY.build_installer_control(tmp_path / 'first.oxt')
    second = VERIFY.build_installer_control(tmp_path / 'second.oxt')
    assert first.read_bytes() == second.read_bytes()
    with zipfile.ZipFile(first) as archive:
        assert set(archive.namelist()) == {'main.py', 'description.xml', 'META-INF/manifest.xml'}
        source = archive.read('main.py').decode()
        compile(source, 'main.py', 'exec')
        assert 'XJobExecutor' in source
        assert 'BreakIterator' not in source
        assert VERIFY.SERVICE not in source
        assert VERIFY.CONTROL_SERVICE in source
