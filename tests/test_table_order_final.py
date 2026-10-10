"""Real public exports retain the sequence of authored table rows."""
import re
import zipfile

from lxml import etree, html
import pytest

import delivery
import export
import publication
import workflows
from wizard import dump_yaml


@pytest.fixture(params=['sections', 'legacy'])
def report(tmp_path, request):
    data={'meta':{'report_title':'Table sequence export contract','lang':'en','theme':'corporativo'},
          'findings':[{'id':'F01','mode':'vuln','title':'Synthetic procedure sequence',
                       'severity':'info','cvss':0,'description_md':
                       '| Sequence | Decision |\n| --- | --- |\n'
                       '| 01 | Contain exposure first |\n'
                       '| 02 | Validate the correction second |\n'
                       '| 03 | Reassess residual risk third |\n\n'
                       '| Phase | Action |\n| --- | --- |\n| Prepare | Check |\n\n'
                       '| Phase | Action |\n| --- | --- |\n| Prepare | Check |\n'
                       '| Phase | Action |\n| Prepare | Check |\n',
                       'impact_md':'Public synthetic case no test executed.',
                       'remediation_md':'Keep the proposed sequence unchanged.'}]}
    if request.param=='sections':
        data['report']={'sections':[{'key':'findings_summary'},{'key':'findings'}]}
    workflows.normalize(data)
    if request.param=='legacy':data.pop('report',None)
    dump_yaml(data,tmp_path/'engagement.yaml')
    captured=publication.snapshot(tmp_path,tmp_path/'snapshot')
    return tmp_path,captured


def reverse_rows(source, target, fmt):
    if fmt=='html':
        tree=html.document_fromstring(source.read_text())
        table=tree.xpath('//*[@id="F01"]//table[thead/tr/th[normalize-space(.)="Sequence"]]')[0]
        body=table.find('tbody')
        for row in list(body):body.remove(row);body.insert(0,row)
        target.write_text(html.tostring(tree,encoding='unicode'))
        return
    with zipfile.ZipFile(source) as package:
        blobs={name:package.read(name) for name in package.namelist()}
    if fmt=='md':
        lines=blobs['report.md'].decode().splitlines(keepends=True)
        indices=[i for i,line in enumerate(lines) if re.match(r'^\| 0[123] \|',line)]
        assert len(indices)==3
        rows=[lines[i] for i in indices]
        for i,row in zip(indices,reversed(rows)):lines[i]=row
        blobs['report.md']=''.join(lines).encode()
    else:
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        tree=etree.fromstring(blobs['word/document.xml'])
        table=next(t for t in tree.xpath('//w:tbl',namespaces=ns)
                   if t.xpath('./w:tr[1]/w:tc[1]//w:t[text()="Sequence"]',namespaces=ns))
        rows=table.xpath('./w:tr',namespaces=ns)[1:]
        assert len(rows)==3
        for row in rows:table.remove(row)
        for row in reversed(rows):table.append(row)
        blobs['word/document.xml']=etree.tostring(tree)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as package:
        for name,blob in blobs.items():package.writestr(name,blob)


def swap_similar_tables(source,target,fmt):
    if fmt=='html':
        tree=html.document_fromstring(source.read_text())
        tables=tree.xpath('//*[@id="F01"]//table[thead/tr/th[normalize-space(.)="Phase"]]')
        assert len(tables)==2
        first,second=tables
        a,b=first.getparent(),second.getparent()
        ai,bi=a.index(first),b.index(second)
        a.remove(first);b.remove(second);a.insert(ai,second);b.insert(bi,first)
        target.write_text(html.tostring(tree,encoding='unicode'))
        return
    with zipfile.ZipFile(source) as package:blobs={name:package.read(name) for name in package.namelist()}
    if fmt=='md':
        text=blobs['report.md'].decode()
        first='| Phase | Action |\n| --- | --- |\n| Prepare | Check |'
        second=first+'\n| Phase | Action |\n| Prepare | Check |'
        assert text.count(first)==2 and text.count(second)==1
        start=text.index(first);end=start+len(first)
        later=text.index(second,end)
        text=text[:start]+second+text[end:later]+first+text[later+len(second):]
        blobs['report.md']=text.encode()
    else:
        ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
        tree=etree.fromstring(blobs['word/document.xml'])
        tables=[t for t in tree.xpath('//w:tbl',namespaces=ns)
                if t.xpath('./w:tr[1]/w:tc[1]//w:t[text()="Phase"]',namespaces=ns)]
        assert len(tables)==2
        first,second=tables;parent=first.getparent();ai,bi=parent.index(first),parent.index(second)
        parent.remove(first);parent.remove(second);parent.insert(ai,second);parent.insert(bi,first)
        blobs['word/document.xml']=etree.tostring(tree)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as package:
        for name,blob in blobs.items():package.writestr(name,blob)


@pytest.mark.parametrize('fmt',['html','docx','md'])
@pytest.mark.parametrize('mutation',[reverse_rows,swap_similar_tables])
def test_inspection_rejects_reordered_rows_without_changing_values(report,fmt,mutation):
    directory,captured=report
    extension='zip' if fmt=='md' else fmt
    original=directory/f'original.{extension}'
    export.export(directory/'engagement.yaml',fmt,original)
    assert delivery.inspect_export(original,fmt,captured)['structure_units_checked']>=4
    altered=directory/f'altered.{extension}'
    mutation(original,altered,fmt)
    with pytest.raises(ValueError,match='Tabla alterada|Table changed'):
        delivery.inspect_export(altered,fmt,captured)
