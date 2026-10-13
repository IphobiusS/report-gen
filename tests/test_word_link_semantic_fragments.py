"""Public delivery checks reconstruct only physically adjacent link fragments."""
from copy import deepcopy
from zipfile import ZipFile

from lxml import etree
import pytest

import delivery
import export
import export_contract
import export_semantics
from wizard import dump_yaml

URL='https://archive.albor.example/café/東京?label=Δ&revision=ALB%2D015#revisión'
W=export_contract.W
R=export_semantics.R
NS=export_contract.NS


def fixture(tmp_path, language='en', body=None):
    body=body if body is not None else (f'Before [{URL}]({URL}) after.\n\n'
          f'[First **middle** last]({URL})\n\n'
          f'[e**́**東京]({URL})\n\n'
          f'[Repeated]({URL})[Repeated]({URL})')
    data=dict(meta=dict(lang=language,theme='corporativo',report_title='Native fragment semantics'),
              report=dict(sections=[dict(key='qa',title='Reference checks',body=body)]),findings=[])
    dump_yaml(data,tmp_path/'engagement.yaml')
    captured=delivery.capture(tmp_path,tmp_path/'snapshot')
    path=export.export(tmp_path/'engagement.yaml','docx',tmp_path/'source.docx')
    return path,captured


@pytest.mark.parametrize('language',['es','en'])
def test_public_inspect_export_accepts_native_script_style_and_combining_fragments(tmp_path,language):
    path,captured=fixture(tmp_path,language)
    result=delivery.inspect_export(path,'docx',captured)
    assert result['link_targets_checked']==5
    actual=export_contract.profile(path,'docx',captured['contract'])['']['semantic']
    assert len(actual['links'])>5
    assert any(actual['link_adjacent'])
    assert 'First ' in actual['link_raw_labels']
    assert ' last' in actual['link_raw_labels']


@pytest.mark.parametrize('mutation',['unlink_middle','wrong_destination','reorder','duplicate',
    'remove_repeated_link','unlinked_space','unlinked_tab','unlinked_break','unlinked_drawing',
    'paragraph_boundary','remove_authored_space','change_combining_mark'])
def test_fragment_semantic_guard_rejects_real_changes_and_unlinked_boundaries(tmp_path,mutation):
    source,captured=fixture(tmp_path)
    with ZipFile(source) as archive:blobs={name:archive.read(name) for name in archive.namelist()}
    tree=etree.fromstring(blobs['word/document.xml'])
    links=[node for node in tree.xpath('//w:hyperlink',namespaces=NS) if node.get(R+'id')]
    first,middle,last=links[:3]
    if mutation=='unlink_middle':
        p=middle.getparent();i=p.index(middle)
        for child in list(middle):p.insert(i,child);i+=1
        p.remove(middle)
    elif mutation=='wrong_destination':
        rels=etree.fromstring(blobs['word/_rels/document.xml.rels'])
        rel=deepcopy(next(n for n in rels if n.get('Id')==middle.get(R+'id')))
        rel.set('Id','rIdChanged');rel.set('Target',rel.get('Target').replace('%2D','-'))
        rels.append(rel);middle.set(R+'id','rIdChanged')
        blobs['word/_rels/document.xml.rels']=etree.tostring(rels)
    elif mutation=='reorder':first.addprevious(middle)
    elif mutation=='duplicate':middle.addnext(deepcopy(middle))
    elif mutation=='remove_repeated_link':
        link=links[-1];p=link.getparent();i=p.index(link)
        for child in list(link):p.insert(i,child);i+=1
        p.remove(link)
    elif mutation.startswith('unlinked_'):
        kind=mutation.removeprefix('unlinked_');run=etree.Element(W+'r')
        item=etree.SubElement(run,W+{'space':'t','tab':'tab','break':'br','drawing':'drawing'}[kind])
        if kind=='space':item.text=' '
        middle.addprevious(run)
    elif mutation=='paragraph_boundary':
        p=middle.getparent();following=etree.Element(W+'p');p.addnext(following)
        for node in list(p)[p.index(middle):]:following.append(node)
    elif mutation=='remove_authored_space':
        node=next(n for n in tree.xpath('//w:t',namespaces=NS) if n.text=='First ');node.text='First'
    elif mutation=='change_combining_mark':
        node=next(n for n in tree.xpath('//w:t',namespaces=NS) if n.text=='́');node.text='̀'
    blobs['word/document.xml']=etree.tostring(tree)
    changed=tmp_path/'changed.docx'
    with ZipFile(changed,'w') as archive:
        for name,data in blobs.items():archive.writestr(name,data)
    actual=export_contract.profile(changed,'docx',captured['contract'])['']['semantic']
    scope=next(s for s in captured['contract']['scopes'] if s['id']=='')
    with pytest.raises(ValueError,match='Links changed'):
        export_semantics.check(scope,actual,'docx')
    with pytest.raises(ValueError):delivery.inspect_export(changed,'docx',captured)


def test_adjacent_author_links_are_consumed_individually_and_never_deduplicated():
    expected=[['a','https://example.test/#f'],['b','https://example.test/#f']]
    actual=dict(links=expected,link_raw_labels=['a','b'],link_adjacent=[False,True])
    assert export_semantics._word_links_match(expected,actual)
    assert not export_semantics._word_links_match(expected,dict(
        links=[['ab','https://example.test/#f']],link_raw_labels=['ab'],link_adjacent=[False]))


def test_linked_figure_source_proof_still_accepts_inline_script_fragments(tmp_path):
    from PIL import Image
    Image.new('RGB',(80,120),'white').save(tmp_path/'evidence.png')
    body=f'[Before東京 ![CAPTION東京](evidence.png) last東京]({URL})'
    path,captured=fixture(tmp_path,body=body)
    checked=delivery.inspect_export(path,'docx',captured)
    assert checked['link_targets_checked']==1
    assert checked['evidence_associations_checked']==1
