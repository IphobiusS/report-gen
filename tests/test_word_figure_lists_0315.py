"""Source-defined figure lists retain their numbered item and physical fragments."""
from copy import deepcopy
import zipfile

from lxml import etree
from PIL import Image
import pytest

import delivery
import export
import export_contract
from wizard import dump_yaml

W, NS = export_contract.W, export_contract.NS
URL = 'https://example.test/evidence'


def fixture(tmp_path, separator=''):
    for name, color in [('first', 'navy'), ('second', 'gray')]:
        Image.new('RGB', (400, 180), color).save(tmp_path / (name + '.png'))
    body = (f'1. [Before{separator}![CAP A](first.png){separator}Middle'
            f'{separator}![CAP B](second.png){separator}After]({URL})\n'
            '2. Tail item')
    data = dict(meta=dict(lang='en', theme='corporativo', report_title='Figure list verification'),
                report=dict(sections=[dict(key='list_figures', title='Figure list', body=body)]), findings=[])
    dump_yaml(data, tmp_path / 'engagement.yaml')
    captured = delivery.capture(tmp_path, tmp_path / 'snapshot')
    path = export.export(tmp_path / 'engagement.yaml', 'docx', tmp_path / 'figures.docx')
    return path, captured


@pytest.mark.parametrize('separator', ['', ' '])
def test_two_figures_keep_one_numbered_item_and_exact_source_boundaries(tmp_path, separator):
    path, captured = fixture(tmp_path, separator)
    checks = delivery.inspect_export(path, 'docx', captured)
    assert checks['authored_list_items_order_checked'] == 2
    scope = captured['contract']['scopes'][0]
    actual = export_contract.profile(path, 'docx', captured['contract'])['']
    assert export_contract._word_list_items(scope, actual) == scope['list_sequence']
    # The old representation rejected this valid list, not lost figure text.
    assert actual['list_items'] != scope['list_sequence']


@pytest.mark.parametrize('mutation', ['missing_number', 'numbered_caption', 'caption_changed',
                                     'caption_reordered', 'interposed_text', 'interposed_table',
                                     'moved_to_next_item', 'fragment_changed'])
def test_figure_list_cannot_cross_changed_fragments_or_physical_boundaries(tmp_path, mutation):
    path, captured = fixture(tmp_path)
    with zipfile.ZipFile(path) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    tree = etree.fromstring(files['word/document.xml'])
    numbered = tree.xpath('//w:p[w:pPr/w:numPr]', namespaces=NS)
    first, next_item = numbered
    captions = tree.xpath('//w:p[w:pPr/w:pStyle[@w:val="Caption"]]', namespaces=NS)
    caption = captions[0]
    image = caption.getprevious()
    if mutation == 'missing_number':
        pr = first.find(W+'pPr'); pr.remove(pr.find(W+'numPr'))
    elif mutation == 'numbered_caption':
        caption.find(W+'pPr').append(deepcopy(first.find(W+'pPr/'+W+'numPr')))
    elif mutation == 'caption_changed':
        caption.find('.//'+W+'t').text = 'CAP CHANGED'
    elif mutation == 'caption_reordered':
        a, b = [node.find('.//'+W+'t') for node in captions]
        a.text, b.text = b.text, a.text
    elif mutation == 'interposed_text':
        p = etree.Element(W+'p'); r = etree.SubElement(p, W+'r')
        etree.SubElement(r, W+'t').text = 'An unrelated instruction'
        caption.addprevious(p)
    elif mutation == 'interposed_table':
        table = etree.Element(W+'tbl'); row = etree.SubElement(table, W+'tr')
        cell = etree.SubElement(row, W+'tc'); etree.SubElement(cell, W+'p')
        caption.addprevious(table)
    elif mutation == 'moved_to_next_item':
        next_item.addnext(image); image.addnext(caption)
    else:
        caption.getnext().find('.//'+W+'t').text = 'Different middle'
    files['word/document.xml'] = etree.tostring(tree)
    changed = tmp_path / 'changed.docx'
    with zipfile.ZipFile(changed, 'w') as archive:
        for name, value in files.items(): archive.writestr(name, value)
    actual = export_contract.profile(changed, 'docx', captured['contract'])['']
    scope = captured['contract']['scopes'][0]
    assert scope['list_sequence'][0] not in export_contract._word_list_items(scope, actual)
    with pytest.raises(ValueError):
        delivery.inspect_export(changed, 'docx', captured)


def test_matching_plain_list_text_cannot_substitute_for_a_figure_item(tmp_path, monkeypatch):
    path, captured = fixture(tmp_path)
    observed = export_contract.profile(path, 'docx', captured['contract'])
    scope = captured['contract']['scopes'][0]
    # Isolate the list guard with an otherwise valid observed profile. A
    # caption copied into a plain numbered paragraph is not proof that the
    # authored figures belong to that numbered item.
    observed['']['list_items'][0] = scope['list_sequence'][0]
    observed['']['list_flows'][0] = [dict(text=scope['list_sequence'][0], style='', images=0)]
    monkeypatch.setattr(export_contract, 'profile', lambda *_: observed)
    with pytest.raises(ValueError, match='Lista alterada|List changed'):
        export_contract.inspect(path, 'docx', captured['contract'])
