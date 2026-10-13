"""Generated charts are public, deterministic and separate from authored evidence."""
from io import BytesIO
import zipfile

from PIL import Image
import pytest

import delivery
import export
import engine
import workflows
from wizard import dump_yaml
from exporters.charts import summary_asset
from exporters.markdown import parse_exported


def project(tmp_path, lang='en', layout='sections', severities=('high','high','medium',None)):
    data={'meta':{'report_title':'Chart contract','theme':'corporativo','lang':lang},
          'findings':[{'id':f'F{i+1:02}','mode':'vuln','title':f'Recorded hypothesis {i}',
                       'severity':severity,'description_md':'Synthetic only; not observed.'}
                      for i,severity in enumerate(severities)]}
    if layout=='sections':data['report']={'sections':[{'key':'findings_summary'},{'key':'findings'}]}
    elif layout=='excluded':data['report']={'sections':[{'key':'findings'}]}
    workflows.normalize(data)
    if layout=='legacy':data.pop('report',None)
    root=tmp_path/'project';root.mkdir()
    dump_yaml(data,root/'engagement.yaml')
    before=(root/'engagement.yaml').read_bytes()
    captured=delivery.capture(root,tmp_path/'snapshot')
    output=export.export(root/'engagement.yaml','md',tmp_path/'report.zip')
    assert (root/'engagement.yaml').read_bytes()==before
    return data,captured,output


@pytest.mark.parametrize('lang',['es','en'])
@pytest.mark.parametrize('layout',['sections','legacy'])
def test_chart_is_real_deterministic_safe_and_counted_separately(tmp_path,lang,layout):
    data,captured,out=project(tmp_path,lang,layout)
    checks=delivery.inspect_export(out,'md',captured)
    assert checks['images_verified']==checks['evidence_associations_checked']==0
    assert checks['generated_charts_verified']==1
    chart=captured['contract']['generated_charts'][0]
    assert chart['counts']=={'critical':0,'high':2,'medium':1,'low':0,'info':0}
    with zipfile.ZipFile(out)as z:
        assert set(z.namelist())=={'report.md',chart['path']}
        tree=parse_exported(z.read('report.md').decode())
        node=tree.xpath('.//img')[0]
        assert node.get('alt')==chart['alt']
        assert node.getparent().getnext().text_content()==chart['caption']
        blob=z.read(chart['path'])
        with Image.open(BytesIO(blob))as im:
            assert im.format=='PNG' and im.size==(900,300)
            assert not im.info
            assert len(im.getcolors(im.width*im.height))>50
        asset=summary_asset(data,engine.load_lang(lang))
        assert blob==asset['blob'] and chart['sha256']==asset['sha256']


@pytest.mark.parametrize('severities,layout',[((),'sections'),((None,None),'sections'),(('high',),'excluded')])
def test_no_chart_for_empty_pending_only_or_excluded_summary(tmp_path,severities,layout):
    _,captured,out=project(tmp_path,severities=severities,layout=layout)
    assert captured['contract']['generated_charts']==[]
    delivery.inspect_export(out,'md',captured)
    with zipfile.ZipFile(out)as z:assert z.namelist()==['report.md']


@pytest.mark.parametrize('mutation',['missing_image','wrong_pixels','wrong_alt','wrong_caption','wrong_count','reordered','duplicate','missing_reference'])
def test_chart_tampering_is_rejected(tmp_path,mutation):
    _,captured,out=project(tmp_path)
    chart=captured['contract']['generated_charts'][0]
    with zipfile.ZipFile(out)as z:files={n:z.read(n)for n in z.namelist()}
    source=files['report.md'].decode()
    image_line=next(line for line in source.splitlines()if chart['path']in line)
    if mutation=='missing_image':del files[chart['path']]
    elif mutation=='wrong_pixels':
        changed=BytesIO();Image.new('RGB',(900,300),'white').save(changed,format='PNG');files[chart['path']]=changed.getvalue()
    elif mutation=='wrong_alt':source=source.replace(image_line,image_line.replace('2','9',1))
    elif mutation=='wrong_caption':source=source.replace('\n'+chart['caption']+'\n','\nAltered caption\n')
    elif mutation=='wrong_count':
        # A different source chart cannot approve the original pixels.
        data={'meta':{'lang':'en','theme':'corporativo'},'findings':[{'severity':'high'}]*9}
        asset=summary_asset(data,engine.load_lang('en'))
        files[chart['path']]=asset['blob']
    elif mutation=='reordered':source=source.replace(image_line+'\n','')+'\n'+image_line+'\n'
    elif mutation=='duplicate':source+='\n'+image_line+'\n'
    elif mutation=='missing_reference':source=source.replace(image_line+'\n','')
    files['report.md']=source.encode()
    bad=tmp_path/(mutation+'.zip')
    with zipfile.ZipFile(bad,'w')as z:
        for name,blob in files.items():z.writestr(name,blob)
    with pytest.raises((ValueError,KeyError)):delivery.inspect_export(bad,'md',captured)


@pytest.mark.parametrize('theme',['serio','corporativo','ejecutivo','offsec','htb','laboratorio'])
def test_markdown_chart_matches_canonical_summary_for_every_theme(tmp_path,theme):
    import publication
    from exporters.charts import contracts_from_tree
    data={'meta':{'report_title':'All chart palettes','theme':theme,'lang':'es'},
          'report':{'sections':[{'key':'findings_summary'},{'key':'findings'}]},
          'findings':[{'id':'F01','mode':'vuln','title':'Synthetic','severity':'high'},
                      {'id':'F02','mode':'vuln','title':'Pending evidence','severity':'medium'}]}
    workflows.normalize(data)
    expected=contracts_from_tree(publication.render(data,tmp_path))[0]
    actual=summary_asset(data,engine.load_lang('es'))
    for key in ['path','sha256','alt','caption','counts']:
        assert expected[key]==actual[key]
