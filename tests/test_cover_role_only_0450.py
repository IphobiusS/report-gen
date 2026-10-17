"""A valid assessor role without a name stays visible in every public format."""
import zipfile

from lxml import etree, html
import pytest

import delivery
import engine
import export
from export_contract import NS
from exporters.markdown import parse_exported
from wizard import dump_yaml


@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_role_only_cover_has_consistent_real_metadata(tmp_path, language, fmt):
    role = 'Rol sintético / Security assessor / Avaliador técnico'
    source = tmp_path / 'engagement.yaml'
    dump_yaml({'meta': {'report_title': 'Fictional role-only cover', 'lang': language,
                        'assessor_title': role}, 'findings': []}, source)
    before = source.read_bytes()
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    assert any(role in unit for unit in captured['contract']['cover_units'])
    output = export.export(source, fmt, tmp_path / ('report.' + fmt))
    delivery.inspect_export(output, fmt, captured)
    assert source.read_bytes() == before
    if fmt == 'html':
        tree = html.document_fromstring(output.read_bytes())
        text = tree.xpath('string(//section[contains(@class,"cover")])')
    elif fmt == 'md':
        with zipfile.ZipFile(output) as archive:
            tree = parse_exported(archive.read('report.md').decode('utf-8'))
        text = tree.text_content()
    elif fmt == 'docx':
        with zipfile.ZipFile(output) as archive:
            tree = etree.fromstring(archive.read('word/document.xml'))
        text = ''.join(tree.xpath('//w:body/w:tbl[1]//w:t/text()', namespaces=NS))
    else:
        from export_contract import pdf_text_pages
        text = pdf_text_pages(output)[0]
    assert role in text
    assert '· ' + role not in text  # No invented separator for an absent name.


@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_permitted_numeric_zero_metadata_is_not_missing(tmp_path, language, fmt):
    from export_contract import normal
    source = tmp_path / 'engagement.yaml'
    dump_yaml({'meta': {'report_title': 'Fictional zero metadata', 'lang': language,
                        'version': 0, 'date': 0, 'osid': 0, 'email': 0},
               'findings': []}, source)
    before = source.read_bytes()
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    labels = engine.load_lang(language)['labels']
    for name in ('cover_version', 'cover_date', 'cover_osid', 'cover_email'):
        assert normal(labels[name] + ' 0') in captured['contract']['cover_units']
    output = export.export(source, fmt, tmp_path / ('report.' + fmt))
    delivery.inspect_export(output, fmt, captured)
    assert source.read_bytes() == before
    if fmt == 'docx':
        with zipfile.ZipFile(output) as archive:
            headers = [etree.fromstring(archive.read(name)) for name in archive.namelist()
                       if name.startswith('word/header') and name.endswith('.xml')]
        assert any('v0' in ''.join(tree.itertext()) for tree in headers)
    elif fmt == 'html':
        assert 'v0' in output.read_text(encoding='utf-8')
    elif fmt == 'pdf':
        from export_contract import pdf_text_pages
        assert 'v0' in '\n'.join(pdf_text_pages(output)[1:])
