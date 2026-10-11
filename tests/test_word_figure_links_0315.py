"""A block figure may split one hyperlink, without weakening its semantics."""
from copy import deepcopy
import zipfile

from lxml import etree
from PIL import Image
import pytest

import delivery
import export
import export_contract
import export_semantics
from wizard import dump_yaml


URL = 'https://example.test/evidence'
W = export_contract.W
R = export_semantics.R
NS = export_contract.NS


def fixture(tmp_path, body=None):
    Image.new('RGB', (1000, 1500), 'white').save(tmp_path / 'decision.png')
    if body is None:
        body = ('Unlinked before [Linked before ![CAPTION](decision.png){width=50mm} '
                f'linked after]({URL}) unlinked after.\n\n'
                f'[Repeated]({URL}) and [Repeated]({URL}).')
    data = dict(meta=dict(lang='en', theme='corporativo', report_title='Linked evidence verification'),
                report=dict(sections=[dict(key='qa_links', title='Linked evidence', body=body)]), findings=[])
    dump_yaml(data, tmp_path / 'engagement.yaml')
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    path = export.export(tmp_path / 'engagement.yaml', 'docx', tmp_path / 'linked.docx')
    return path, captured


def test_linked_prose_figure_and_following_prose_preserve_three_authored_links(tmp_path):
    path, captured = fixture(tmp_path)
    checked = delivery.inspect_export(path, 'docx', captured)
    assert checked['link_targets_checked'] == 3
    assert checked['evidence_associations_checked'] == 1
    actual = export_contract.profile(path, 'docx', captured['contract'])['']['semantic']
    assert actual['links'] == [[label, URL] for label in
                               ['Linked before', 'CAPTION', 'linked after', 'Repeated', 'Repeated']]


@pytest.mark.parametrize('separator', ['', ' '])
def test_one_authored_link_preserves_source_boundaries_around_its_figure(tmp_path, separator):
    body = f'[Before{separator}![CAPTION](decision.png){separator}After]({URL})'
    path, captured = fixture(tmp_path, body)
    assert delivery.inspect_export(path, 'docx', captured)['link_targets_checked'] == 1


@pytest.mark.parametrize('mutation', ['missing_fragment', 'changed_label', 'reordered', 'wrong_destination',
                                    'repeated_fragment', 'missing_repeated_link', 'interposed_prose',
                                    'wrong_picture_destination'])
def test_fragment_reconstruction_rejects_semantic_or_physical_changes(tmp_path, mutation):
    path, captured = fixture(tmp_path)
    with zipfile.ZipFile(path) as archive:
        blobs = {name: archive.read(name) for name in archive.namelist()}
    tree = etree.fromstring(blobs['word/document.xml'])
    links = [node for node in tree.xpath('//w:hyperlink', namespaces=NS) if node.get(R+'id')]
    first, caption, after = links[:3]
    if mutation == 'missing_fragment': first.getparent().remove(first)
    elif mutation == 'changed_label': caption.find('.//'+W+'t').text = 'Different caption label'
    elif mutation == 'reordered':
        first.find('.//'+W+'t').text = 'CAPTION'
        caption.find('.//'+W+'t').text = 'Linked before'
    elif mutation == 'repeated_fragment': first.addnext(deepcopy(first))
    elif mutation == 'missing_repeated_link': links[-1].getparent().remove(links[-1])
    elif mutation == 'interposed_prose':
        paragraph = etree.Element(W+'p'); run = etree.SubElement(paragraph, W+'r')
        etree.SubElement(run, W+'t').text = 'Interposed unrelated instruction'
        caption.getparent().addprevious(paragraph)
    else:
        rels = etree.fromstring(blobs['word/_rels/document.xml.rels'])
        relationship = etree.SubElement(rels, '{http://schemas.openxmlformats.org/package/2006/relationships}Relationship')
        relationship.set('Id', 'rIdMutated'); relationship.set('Target', 'https://example.test/other')
        relationship.set('Type', R[1:-1] + '/hyperlink'); relationship.set('TargetMode', 'External')
        blobs['word/_rels/document.xml.rels'] = etree.tostring(rels)
        if mutation == 'wrong_destination': after.set(R+'id', 'rIdMutated')
        else:
            tree.xpath('//*[local-name()="hlinkClick"]')[0].set(R+'id', 'rIdMutated')
    blobs['word/document.xml'] = etree.tostring(tree)
    changed = tmp_path / 'changed.docx'
    with zipfile.ZipFile(changed, 'w') as archive:
        for name, blob in blobs.items(): archive.writestr(name, blob)
    actual = export_contract.profile(changed, 'docx', captured['contract'])['']['semantic']
    scope = next(s for s in captured['contract']['scopes'] if s['id'] == '')
    with pytest.raises(ValueError, match='Links changed|Evidence placement changed'):
        export_semantics.check(scope, actual, 'docx')


def test_picture_only_link_checks_its_graphic_destination_too(tmp_path):
    path, captured = fixture(tmp_path, f'[![CAPTION](decision.png)]({URL})')
    actual = export_contract.profile(path, 'docx', captured['contract'])['']['semantic']
    scope = next(s for s in captured['contract']['scopes'] if s['id'] == '')
    actual['images'][0]['link_target'] = 'https://example.test/other'
    with pytest.raises(ValueError, match='Evidence placement changed'):
        export_semantics.check(scope, actual, 'docx')


@pytest.mark.parametrize('fmt', ['html', 'md', 'pdf'])
def test_other_formats_keep_exact_link_equality(fmt):
    scope = dict(id='', semantic=dict(fields=[], severity='', images=[], links=[['First caption last', URL]]))
    actual = dict(fields=[], severity='', images=[], links=[['First', URL], ['caption', URL], ['last', URL]],
                  link_gaps=[[], [['image', URL]], []])
    with pytest.raises(ValueError, match='Links changed'):
        export_semantics.check(scope, actual, fmt)


def test_ordinary_links_cannot_be_rejoined_without_a_linked_figure():
    assert not export_semantics._word_links_match([['First last', URL]],
        dict(links=[['First', URL], ['last', URL]], link_gaps=[[], []]))
