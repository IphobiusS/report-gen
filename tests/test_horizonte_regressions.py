"""Complex banking report: linked evidence inside editable Word table cells."""
import zipfile

from lxml import etree
from PIL import Image
import pytest

import delivery
import export
from export_contract import NS, W
from wizard import dump_yaml


def table_report(tmp_path, target, surrounding=False, language='es', label=None, fmt='docx'):
    Image.new('RGB', (48, 32), 'navy').save(tmp_path / 'proof.png')
    if label is None:
        label = '**Antes** ![Conciliación](proof.png) _Después_' if surrounding else '![Conciliación](proof.png)'
    cell = f'[{label}]({target})' if target else label
    source = ('| Evidencia | Resultado |\n|---|---|\n'
              f'| {cell} | Conforme |\n\n'
              '[Registro siguiente](https://example.invalid/register#next)')
    data = {'meta': {'lang': language, 'report_title': 'Banco sintético'},
            'findings': [{'id': 'F1', 'title': 'Conciliación', 'description_md': source}]}
    dump_yaml(data, tmp_path / 'engagement.yaml')
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    output = export.export(tmp_path / 'engagement.yaml', fmt, tmp_path / ('report.' + delivery.get(fmt).extension))
    return output, captured


@pytest.mark.parametrize('label', ['Antes![UNO](proof.png)Después',
                                 '![UNO](proof.png)![DOS](proof.png)',
                                 '**![UNO](proof.png)** ![DOS](proof.png)'])
@pytest.mark.parametrize('target', ['', 'https://example.invalid/control#evidence'])
@pytest.mark.parametrize('fmt', ['html', 'md', 'docx', 'pdf'])
def test_table_figures_keep_block_boundaries_with_adjacent_prose_and_other_figures(tmp_path, label, target, fmt):
    output, captured = table_report(tmp_path, target, label=label, fmt=fmt)
    checks = delivery.inspect_export(output, fmt, captured)
    if fmt != 'pdf':
        assert checks['evidence_associations_checked'] == label.count('![')


@pytest.mark.parametrize('target', ['https://example.invalid/control',
                                  'https://example.invalid/control#evidence', '#F1'])
@pytest.mark.parametrize('surrounding', [False, True])
@pytest.mark.parametrize('language', ['es', 'en', 'pt'])
def test_linked_table_evidence_keeps_labels_destinations_and_surrounding_prose(tmp_path, target, surrounding, language):
    output, captured = table_report(tmp_path, target, surrounding, language)
    checks = delivery.inspect_export(output, 'docx', captured)
    assert checks['evidence_associations_checked'] == 1
    with zipfile.ZipFile(output) as package:
        tree = etree.fromstring(package.read('word/document.xml'))
    # Layout breaks are outside the authored hyperlink text; the image itself
    # remains clickable without generating empty image/break hyperlinks.
    assert not tree.xpath('//w:hyperlink[.//w:br or .//w:drawing]', namespaces=NS)
    assert tree.xpath('count(//*[local-name()="docPr"]/*[local-name()="hlinkClick"])') == 1
    assert not tree.xpath('//w:hyperlink[not(.//w:t)]', namespaces=NS)
    if surrounding:
        assert tree.xpath('//w:hyperlink/w:r[w:t="Antes"]/w:rPr/w:b', namespaces=NS)
        assert tree.xpath('//w:hyperlink/w:r[w:t="Después"]/w:rPr/w:i', namespaces=NS)


@pytest.mark.parametrize('mutation', ['picture_target', 'caption_target', 'caption_text', 'remove_picture',
                                     'remove_prose', 'swap_captions', 'remove_caption_link'])
def test_linked_table_evidence_integrity_checks_still_reject_artifact_changes(tmp_path, mutation):
    label = ('Antes![UNO](proof.png) ![DOS](proof.png)Después'
             if mutation in {'remove_prose', 'swap_captions', 'remove_caption_link'} else None)
    output, captured = table_report(tmp_path, 'https://example.invalid/control#evidence', label=label)
    delivery.inspect_export(output, 'docx', captured)
    with zipfile.ZipFile(output) as package:
        files = {name: package.read(name) for name in package.namelist()}
    tree = etree.fromstring(files['word/document.xml'])
    rels = etree.fromstring(files['word/_rels/document.xml.rels'])
    if mutation.endswith('_target'):
        relationship = etree.SubElement(rels, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')
        relationship.attrib.update({'Id': 'rIdChangedEvidence',
            'Type': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink',
            'Target': 'https://example.invalid/wrong-control', 'TargetMode': 'External'})
        node = (tree.xpath('//*[local-name()="docPr"]/*[local-name()="hlinkClick"]')[0]
                if mutation == 'picture_target' else
                tree.xpath('//w:hyperlink[.//w:t="Conciliación"][not(@w:anchor)]', namespaces=NS)[0])
        node.set('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id', 'rIdChangedEvidence')
    elif mutation == 'caption_text':
        tree.xpath('//w:hyperlink[not(@w:anchor)]//w:t[text()="Conciliación"]', namespaces=NS)[0].text = 'Otro control'
    elif mutation == 'remove_prose':
        node = tree.xpath('//w:hyperlink//w:t[text()="Antes"]', namespaces=NS)[0]
        node.getparent().remove(node)
    elif mutation == 'swap_captions':
        first = tree.xpath('//w:hyperlink//w:t[normalize-space(.)="UNO"]', namespaces=NS)[0]
        second = tree.xpath('//w:hyperlink//w:t[text()="DOS"]', namespaces=NS)[0]
        first.text, second.text = first.text.replace('UNO', 'DOS'), 'UNO'
    elif mutation == 'remove_caption_link':
        node = tree.xpath('//w:hyperlink[.//w:t="DOS"]', namespaces=NS)[0]
        node.getparent().remove(node)
    else:
        drawing = tree.find('.//' + W + 'drawing')
        drawing.getparent().remove(drawing)
    files['word/document.xml'] = etree.tostring(tree)
    files['word/_rels/document.xml.rels'] = etree.tostring(rels)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, blob in files.items():
            package.writestr(name, blob)
    with pytest.raises(ValueError):
        delivery.inspect_export(output, 'docx', captured)


def test_unlinked_table_caption_is_checked_as_exact_cell_content(tmp_path):
    output, captured = table_report(tmp_path, '', label='Antes![UNO](proof.png)Después')
    delivery.inspect_export(output, 'docx', captured)
    with zipfile.ZipFile(output) as package:
        files = {name: package.read(name) for name in package.namelist()}
    tree = etree.fromstring(files['word/document.xml'])
    # Keep the graphic's unchanged alt text. The visible cell caption still
    # cannot disappear or be substituted by that hidden accessibility value.
    tree.xpath('//w:tc//w:t[text()="UNO"]', namespaces=NS)[0].text = ''
    files['word/document.xml'] = etree.tostring(tree)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as package:
        for name, blob in files.items():
            package.writestr(name, blob)
    with pytest.raises(ValueError, match='Tabla alterada'):
        delivery.inspect_export(output, 'docx', captured)
