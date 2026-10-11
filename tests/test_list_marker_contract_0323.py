"""A procedure cannot pass verification after its visible ordinals change."""
from hashlib import sha256
from copy import deepcopy
import zipfile

from lxml import etree, html
import pytest

import delivery
import export
import export_contract
from wizard import dump_yaml

W = export_contract.W
NS = export_contract.NS


def prepare(root, fmt, start=65536):
    data = {'meta': {'report_title': 'Synthetic ordinal contract', 'lang': 'en'},
            'report': {'sections': [{'key': 'findings'}]},
            'findings': [{'id': 'F01', 'mode': 'vuln', 'title': 'Numbered procedure',
                          'description_md': (f'{start}. Approve the transaction.\n'
                                             '    7. Record the nested decision.\n'
                                             '    8. Verify the nested log.\n'
                                             f'{start + 1}. Retain the approval.\n\n'
                                             '- Ordinary bullet.\n- Another bullet.')} ]}
    dump_yaml(data, root / 'engagement.yaml')
    captured = delivery.capture(root, root / 'snapshot')
    output = export.export(root / 'engagement.yaml', fmt,
                           root / ('report.' + delivery.get(fmt).extension))
    assert delivery.inspect_export(output, fmt, captured)['authored_list_markers_checked'] == 6
    return output, captured


def alter_member(path, member, change):
    with zipfile.ZipFile(path) as archive:
        members = {name: archive.read(name) for name in archive.namelist()}
    members[member] = change(members[member])
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, blob in members.items():
            archive.writestr(name, blob)


@pytest.mark.parametrize('fmt', ['html', 'md', 'docx'])
@pytest.mark.parametrize('start', [0, 42, 65535, 65536, 1234567890])
def test_supported_markers_match_source_without_modifying_the_artifact(tmp_path, fmt, start):
    output, captured = prepare(tmp_path, fmt, start)
    before = sha256(output.read_bytes()).hexdigest()
    assert delivery.inspect_export(output, fmt, captured)['authored_list_markers_checked'] == 6
    assert sha256(output.read_bytes()).hexdigest() == before


@pytest.mark.parametrize('mutation', ['start', 'value', 'reversed', 'type', 'bullet'])
def test_html_counter_changes_fail_with_the_same_item_text(tmp_path, mutation):
    output, captured = prepare(tmp_path, 'html')
    tree = html.document_fromstring(output.read_text())
    group = tree.get_element_by_id('F01').xpath('.//ol')[0]
    if mutation == 'start': group.set('start', '722')
    elif mutation == 'value': group[1].set('value', '42')
    elif mutation == 'reversed': group.set('reversed', '')
    elif mutation == 'type': group.set('type', 'a')
    else: group.tag = 'ul'
    output.write_text(html.tostring(tree, encoding='unicode'))
    with pytest.raises(ValueError, match='Lista|List'):
        delivery.inspect_export(output, 'html', captured)


def test_markdown_counter_change_fails_with_the_same_item_text(tmp_path):
    output, captured = prepare(tmp_path, 'md')
    alter_member(output, 'report.md', lambda blob: blob.replace(b'65536. Approve', b'722. Approve'))
    with pytest.raises(ValueError, match='Lista|List'):
        delivery.inspect_export(output, 'md', captured)


@pytest.mark.parametrize('mutation', ['start', 'format', 'template'])
def test_native_word_counter_changes_fail_with_the_same_item_text(tmp_path, mutation):
    output, captured = prepare(tmp_path, 'docx', 42)
    def change(blob):
        tree = etree.fromstring(blob)
        level = tree.xpath('//w:lvl[w:start[@w:val="42"]]', namespaces=NS)[0]
        tag, value = {'start': ('start', '43'), 'format': ('numFmt', 'bullet'),
                      'template': ('lvlText', 'removed')}[mutation]
        level.find(W+tag).set(W+'val', value)
        return etree.tostring(tree)
    alter_member(output, 'word/numbering.xml', change)
    with pytest.raises(ValueError, match='Lista|List'):
        delivery.inspect_export(output, 'docx', captured)


@pytest.mark.parametrize('mutation', ['cache', 'reset', 'advance', 'sequence', 'delimiter', 'hidden', 'inject', 'num_id', 'level'])
def test_word_sequence_field_changes_cannot_hide_behind_identical_prose(tmp_path, mutation):
    output, captured = prepare(tmp_path, 'docx')
    def change(blob):
        tree = etree.fromstring(blob)
        fields = tree.findall('.//'+W+'fldSimple')
        if mutation == 'cache': fields[0].find('.//'+W+'t').text = '0'
        elif mutation == 'reset': fields[0].set(W+'instr', fields[0].get(W+'instr').replace('65536', '65537'))
        elif mutation == 'advance': fields[1].set(W+'instr', fields[1].get(W+'instr').replace('\\n', '\\r 65537'))
        elif mutation == 'sequence': fields[1].set(W+'instr', fields[1].get(W+'instr').replace('RGList', 'OtherList'))
        elif mutation == 'delimiter': fields[0].getnext().find(W+'t').text = 'malicious extra text.'
        elif mutation == 'hidden':
            props = etree.SubElement(fields[0][0], W+'rPr')
            etree.SubElement(props, W+'vanish')
        elif mutation == 'inject': etree.SubElement(fields[0][0], W+'t').text = 'malicious extra text'
        elif mutation == 'num_id':
            fields[0].getparent().find(W+'pPr/'+W+'numPr/'+W+'numId').set(W+'val', '999999')
        else: fields[0].getparent().find(W+'pPr/'+W+'numPr/'+W+'ilvl').set(W+'val', '7')
        return etree.tostring(tree)
    alter_member(output, 'word/document.xml', change)
    with pytest.raises(ValueError, match='Numeración|numbering'):
        delivery.inspect_export(output, 'docx', captured)


def test_consistently_shifted_word_sequence_still_must_match_authored_start(tmp_path):
    output, captured = prepare(tmp_path, 'docx')
    def change(blob):
        tree = etree.fromstring(blob)
        fields = tree.findall('.//'+W+'fldSimple')
        fields[0].set(W+'instr', fields[0].get(W+'instr').replace('65536', '65540'))
        for index, field in enumerate(fields):
            field.find('.//'+W+'t').text = str(65540 + index)
        return etree.tostring(tree)
    alter_member(output, 'word/document.xml', change)
    with pytest.raises(ValueError, match='Lista|List'):
        delivery.inspect_export(output, 'docx', captured)


@pytest.mark.parametrize('kind', ['num', 'abstract', 'level', 'override', 'numeric-alias', 'start-property'])
def test_ambiguous_word_numbering_identities_fail_closed(tmp_path, kind):
    output, captured = prepare(tmp_path, 'docx', 42)
    def change(blob):
        tree = etree.fromstring(blob)
        abstract = tree.xpath('//w:abstractNum[w:lvl/w:start[@w:val="42"]]', namespaces=NS)[0]
        abstract_id = abstract.get(W+'abstractNumId')
        num = tree.xpath('//w:num[w:abstractNumId[@w:val="'+abstract_id+'"]]', namespaces=NS)[0]
        if kind in ('num', 'numeric-alias'):
            duplicate = deepcopy(num)
            if kind == 'numeric-alias': duplicate.set(W+'numId', '0'+duplicate.get(W+'numId'))
            tree.append(duplicate)
        elif kind == 'abstract': tree.append(deepcopy(abstract))
        elif kind == 'level': abstract.append(deepcopy(abstract.find(W+'lvl')))
        elif kind == 'start-property':
            level = abstract.find(W+'lvl')
            level.append(deepcopy(level.find(W+'start')))
        else:
            override = etree.SubElement(num, W+'lvlOverride', {W+'ilvl': '0'})
            etree.SubElement(override, W+'startOverride', {W+'val': '42'})
            num.append(deepcopy(override))
        return etree.tostring(tree)
    alter_member(output, 'word/numbering.xml', change)
    with pytest.raises(ValueError, match='Numeración|numbering'):
        delivery.inspect_export(output, 'docx', captured)
