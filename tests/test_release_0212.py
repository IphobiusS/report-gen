"""Ladera audit regressions: references, metadata, images and visibility."""
from copy import deepcopy
import zipfile

from lxml import html, etree
from PIL import Image
import pytest
import delivery
import export
import export_contract
import workflows
from wizard import dump_yaml
from test_release_0211 import edit_zip


def fixture(root):
    (root/'img').mkdir(exist_ok=True)
    for number,color in [(1,'blue'),(2,'green')]:Image.new('RGB',(50,30),color).save(root/f'img/e{number}.png')
    return workflows.normalize({'meta':{'report_title':'Informe ficticio 0212','lang':'es','theme':'serio','client':'Cliente sintético','assessor':'Autor de ensayo','date':'2026-10-05','version':'0212','scope':[{'target':'https://scope.example','description':'Alcance SCOPE_UNICO'}]},
      'report':{'sections':[{'key':'document_control','version_history':[{'version':'HISTORY_UNICO','date':'2026-10-05','author':'Revisor','changes':'Validación'}]},{'key':'scope'},{'key':'findings_summary'},{'key':'findings'}]},
      'findings':[{'id':'F01','title':'Primero','severity':'high','cvss':7.5,'cvss_vector':'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N','cwe':'CWE-200','affected':'https://activo-unico.example',
        'description_md':'Descripción completa uno.\n\n[Consultar segundo](#F02).','impact_md':'Impacto uno','remediation_md':'Corregir uno',
        'walkthrough':[{'command':'  printf uno\n','figure':{'src':'img/e1.png','caption':'Evidencia A'}}]},
        {'id':'F02','title':'Segundo','severity':'low','description_md':'Descripción completa dos.','impact_md':'Impacto dos','remediation_md':'Corregir dos',
        'walkthrough':[{'command':'  printf dos\n','figure':{'src':'img/e2.png','caption':'Evidencia B'}}]},
        {'id':'M01','mode':'machine','title':'Ficha de máquina','host':{'name':'host-sintetico','ip':'192.0.2.12','os':'OS_UNICO'},'open_ports':'443/TCP','summary_md':'Contexto de máquina.'}]})


def prepare(root,fmt,data=None):
    data=data or fixture(root);dump_yaml(data,root/'engagement.yaml')
    captured=delivery.capture(root,root/'snapshot')
    out=export.export(root/'engagement.yaml',fmt,root/('report.'+delivery.get(fmt).extension))
    return out,captured


def alter(path,fmt,old,new):
    def change(blob):
        source,target=old,new
        if source.encode() not in blob and fmt=='md':
            from workflows import md_text
            source,target=md_text(old),md_text(new)
        assert source.encode() in blob,source
        return blob.replace(source.encode(),target.encode(),1)
    if fmt=='html':path.write_bytes(change(path.read_bytes()))
    else:edit_zip(path,'report.md' if fmt=='md' else 'word/document.xml',change)


@pytest.mark.parametrize('fmt',['html','docx','md'])
def test_original_covers_typed_fields_images_links_and_manual_review(tmp_path,fmt):
    out,c=prepare(tmp_path,fmt);check=delivery.inspect_export(out,fmt,c)
    assert check['metadata_values_checked']>=13
    assert check['link_targets_checked']>=4
    assert check['evidence_associations_checked']==2
    assert check['manual_review_required'] is True


@pytest.mark.parametrize('fmt',['html','docx','md'])
@pytest.mark.parametrize('old,new',[
 ('https://activo-unico.example','https://equivocado.example'),('HISTORY_UNICO','HISTORY_ALTERADO'),
 ('Autor de ensayo','Autor equivocado'),('Cliente sintético','Cliente equivocado'),
 ('2026-10-05','2027-10-05'),('https://scope.example','https://scope-altered.example'),
 ('CWE-200','CWE-999'),('C:H/I:N/A:N','C:L/I:N/A:N'),('OS_UNICO','OS_ALTERADO')])
def test_altered_metadata_and_native_tables_fail(tmp_path,fmt,old,new):
    out,c=prepare(tmp_path,fmt);delivery.inspect_export(out,fmt,c);alter(out,fmt,old,new)
    with pytest.raises(ValueError):delivery.inspect_export(out,fmt,c)


@pytest.mark.parametrize('fmt',['html','docx','md'])
def test_link_redirect_to_existing_wrong_target_fails(tmp_path,fmt):
    out,c=prepare(tmp_path,fmt)
    if fmt=='docx':
        from exporters.navigation import reference_name
        alter(out,fmt,reference_name('F02'),reference_name('F01'))
    else:alter(out,fmt,'(#F02)' if fmt=='md' else 'href="#F02"','(#F01)' if fmt=='md' else 'href="#F01"')
    with pytest.raises(ValueError):delivery.inspect_export(out,fmt,c)


@pytest.mark.parametrize('kind',['hidden','display','visibility','stylesheet','opacity','parent'])
def test_hidden_content_is_not_certified(tmp_path,kind):
    out,c=prepare(tmp_path,'html');tree=html.document_fromstring(out.read_text())
    p=tree.get_element_by_id('F01').xpath('.//p')[0]
    if kind=='hidden':p.set('hidden','')
    elif kind=='parent':p.getparent().set('hidden','')
    elif kind=='stylesheet':
        p.set('class','altered-hidden');tree.xpath('//style')[0].text+='\n#F01 .altered-hidden{display:none!important}'
    else:p.set('style',{'display':'display:none','visibility':'visibility:hidden','opacity':'opacity:0'}[kind])
    out.write_text(html.tostring(tree,encoding='unicode'))
    with pytest.raises(ValueError):delivery.inspect_export(out,'html',c)


@pytest.mark.parametrize('fmt',['html','docx','md'])
@pytest.mark.parametrize('mutation',['swap','duplicate','replace','caption','move_past_code'])
def test_evidence_placement_mutations_fail_with_same_count(tmp_path,fmt,mutation):
    out,c=prepare(tmp_path,fmt);delivery.inspect_export(out,fmt,c)
    if fmt=='html':
        tree=html.document_fromstring(out.read_text());a=tree.get_element_by_id('F01').xpath('.//img')[0];b=tree.get_element_by_id('F02').xpath('.//img')[0]
        if mutation=='caption':a.getparent().find('figcaption').text='Alterado'
        elif mutation=='move_past_code':tree.get_element_by_id('F01').xpath('.//pre')[0].addprevious(a.getparent())
        else:
            av,bv=a.get('src'),b.get('src');a.set('src',bv)
            if mutation=='swap':b.set('src',av)
        out.write_text(html.tostring(tree,encoding='unicode'))
    elif fmt=='md':
        if mutation=='caption':alter(out,fmt,'Evidencia A','Evidencia incorrecta')
        elif mutation=='move_past_code':
            def move(blob):
                text=blob.decode();start=text.index('![Evidencia A]');end=text.index('\n',start);image=text[start:end];text=text[:start]+text[end:];text=text.replace('```\n  printf uno',image+'\n\n```\n  printf uno',1);return text.encode()
            edit_zip(out,'report.md',move)
        else:
            def swap(blob):
                text=blob.decode().replace('img/e1.png','img/TEMP.png',1).replace('img/e2.png','img/e1.png',1) if mutation=='swap' else blob.decode().replace('img/e1.png','img/TEMP.png',1)
                return text.replace('img/TEMP.png','img/e2.png',1).encode()
            edit_zip(out,'report.md',swap)
    else:
        def change(blob):
            tree=etree.fromstring(blob);ns=export_contract.NS
            blips=tree.xpath('//*[local-name()="blip"]');a,b=blips[-2:];key='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed'
            if mutation=='caption':a.xpath('ancestor::*[local-name()="inline"]')[0].xpath('./*[local-name()="docPr"]')[0].set('descr','Incorrecta')
            elif mutation=='move_past_code':
                p=a.xpath('ancestor::w:p',namespaces=ns)[0];code=tree.xpath('//w:p[w:pPr/w:pStyle[@w:val="ReportGenCode"]]',namespaces=ns)[0];code.addprevious(p)
            else:
                av,bv=a.get(key),b.get(key);a.set(key,bv)
                if mutation=='swap':b.set(key,av)
            return etree.tostring(tree)
        edit_zip(out,'word/document.xml',change)
    with pytest.raises(ValueError):delivery.inspect_export(out,fmt,c)


def test_same_image_legitimately_reused_is_counted_twice(tmp_path):
    data=fixture(tmp_path);data['findings'][1]['walkthrough'][0]['figure']['src']='img/e1.png'
    out,c=prepare(tmp_path,'docx',data);assert delivery.inspect_export(out,'docx',c)['evidence_associations_checked']==2


def test_id_allocation_preserves_imports_and_reserves_deleted_ids(tmp_path):
    data=fixture(tmp_path);workflows.normalize(data)
    before=deepcopy(data['findings']);assert workflows.allocate_finding_id(data)=='F3'
    data['findings'].pop();data['findings'].pop();assert workflows.allocate_finding_id(data)=='F4'
    assert data['findings'][0]['id']==before[0]['id'] and data['findings'][0]['uid']==before[0]['uid']
    data['findings'][0]['description_md']='[Destino borrado](#F90)';assert workflows.allocate_finding_id(data)=='F91'


@pytest.mark.parametrize('fmt',['html','md','docx','pdf'])
def test_deleted_reference_is_blocked_before_export(tmp_path,fmt):
    data=fixture(tmp_path);data['findings'].pop(1);dump_yaml(data,tmp_path/'engagement.yaml')
    with pytest.raises(ValueError,match='sin destino'):export.export(tmp_path/'engagement.yaml',fmt,tmp_path/('bad.'+fmt))


def test_word_intro_chain_has_no_table_boundary_or_forced_page(tmp_path):
    out,c=prepare(tmp_path,'docx')
    with zipfile.ZipFile(out) as z:tree=etree.fromstring(z.read('word/document.xml'))
    ns=export_contract.NS
    for p in tree.xpath('//w:p[w:pPr/w:pStyle[@w:val="ReportGenMeta"]]',namespaces=ns):
        assert p.xpath('./w:pPr/w:keepNext[not(@w:val="0")]',namespaces=ns)
        assert not p.xpath('./w:pPr/w:pageBreakBefore',namespaces=ns)
        assert p.getparent().tag==export_contract.W+'body'


@pytest.mark.parametrize('fmt',['html','docx','md'])
def test_cover_images_and_escaped_image_paths_do_not_break_association(tmp_path,fmt):
    data=fixture(tmp_path)
    (tmp_path/'img/e1.png').rename(tmp_path/'img/evidence [1].png')
    data['findings'][0]['walkthrough'][0]['figure']['src']='img/evidence [1].png'
    data['meta']['branding']={'logo':'img/evidence [1].png','client_logo':'img/e2.png'}
    out,c=prepare(tmp_path,fmt,data)
    assert delivery.inspect_export(out,fmt,c)['evidence_associations_checked']==2


@pytest.mark.parametrize('fmt',['html','docx','md'])
def test_moving_image_between_steps_without_commands_is_detected(tmp_path,fmt):
    data=fixture(tmp_path)
    data['findings'][0]['walkthrough']=[{'text_md':'Contexto del paso alfa.', 'figure':{'src':'img/e1.png','caption':'Primera captura'}}, {'text_md':'Contexto del paso beta.', 'figure':{'src':'img/e2.png','caption':'Segunda captura'}}]
    data['findings'][1]['walkthrough']=[]
    out,c=prepare(tmp_path,fmt,data);delivery.inspect_export(out,fmt,c)
    if fmt=='html':
        tree=html.document_fromstring(out.read_text());figs=tree.get_element_by_id('F01').xpath('.//figure');figs[1].addprevious(figs[0]);out.write_text(html.tostring(tree,encoding='unicode'))
    elif fmt=='md':
        def change(blob):
            text=blob.decode();start=text.index('![Primera captura]');end=text.index('\n',start);image=text[start:end];text=text[:start]+text[end:];return text.replace('![Segunda captura]',image+'\n\n![Segunda captura]',1).encode()
        edit_zip(out,'report.md',change)
    else:
        def change(blob):
            tree=etree.fromstring(blob);paras=tree.xpath('//w:p[w:r/w:drawing]',namespaces=export_contract.NS);paras[-1].addprevious(paras[-2]);return etree.tostring(tree)
        edit_zip(out,'word/document.xml',change)
    with pytest.raises(ValueError,match='evidencia'):delivery.inspect_export(out,fmt,c)
