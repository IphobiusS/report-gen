"""Release acceptance: export contracts, annex boundaries and verified downloads."""
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import json
import uuid
import zipfile

from docx import Document
from lxml import html
import pytest

import app as api
import attachments
import delivery
import export
import export_contract
import export_formats
import project_history
import validate
import workflows
from storage import revision
from wizard import dump_yaml
from _support import auth_client


def sample():
    return workflows.normalize({'meta': {'report_title':'Prueba de integridad', 'lang':'es','theme':'corporativo'},
      'report':{'sections':[{'key':'findings_summary'},{'key':'findings'}]},
      'findings':[{'id':'F01','mode':'vuln','title':'Hallazgo sintético',
      'description_md':'| Campo | Valor |\n| --- | --- |\n| prueba | valor |\n\n1. PRIMER_PASO\n2. SEGUNDO_PASO\n\n```text\nCODIGO_LITERAL <ejemplo> & ñ\n```',
      'impact_md':'Impacto de prueba','remediation_md':'Corrección de prueba'}]})


def annex(data, directory, name='evidencia.json', included=True):
    member='attachments/'+uuid.uuid4().hex+'.json';blob=b'{"synthetic":true}\n'
    path=directory/member;path.parent.mkdir(exist_ok=True);path.write_bytes(blob)
    row=dict(uid=str(uuid.uuid4()),name=name,member=member,sha256=sha256(blob).hexdigest(),include=included,reviewed=included)
    data.setdefault('attachments',[]).append(row)
    return row,blob


@pytest.mark.parametrize('fmt',list(export_formats.REGISTRY))
def test_public_formats_use_same_registry_and_content_contract(tmp_path,fmt):
    data=sample();dump_yaml(data,tmp_path/'engagement.yaml')
    captured=delivery.capture(tmp_path,tmp_path/'capture')
    out=export.export(tmp_path/'engagement.yaml',fmt,tmp_path/('report.'+export_formats.get(fmt).extension))
    checks=delivery.inspect_export(out,fmt,captured)
    assert checks['content_units_checked']>=2
    assert checks['structure_units_checked']>=4 if fmt!='pdf' else checks['structure_units_checked']==0
    assert api.MIMES[fmt]==export_formats.get(fmt).mime


@pytest.mark.parametrize('key',[None,[],{},'exe','HTML','../pdf'])
def test_registry_rejects_unknown_types(key):
    with pytest.raises(ValueError): export_formats.get(key)


def test_semantic_inspection_detects_missing_table_and_list_order(tmp_path):
    data=sample();dump_yaml(data,tmp_path/'engagement.yaml');captured=delivery.capture(tmp_path,tmp_path/'capture')
    out=export.export(tmp_path/'engagement.yaml','html',tmp_path/'report.html')
    tree=html.document_fromstring(out.read_text());row=tree.xpath('//table[contains(@class,"md-table")]//tr')[1];row.getparent().remove(row)
    out.write_text(html.tostring(tree,encoding='unicode'))
    with pytest.raises(ValueError,match='Tabla'): delivery.inspect_export(out,'html',captured)
    out=export.export(tmp_path/'engagement.yaml','html',tmp_path/'report.html')
    markup=out.read_text().replace('PRIMER_PASO','TMP_SENTINEL').replace('SEGUNDO_PASO','PRIMER_PASO').replace('TMP_SENTINEL','SEGUNDO_PASO');out.write_text(markup)
    with pytest.raises(ValueError,match='Lista'): delivery.inspect_export(out,'html',captured)


def test_word_inspection_rejects_dangling_internal_link(tmp_path):
    data=sample();data['findings'][0]['description_md']='[Roto](#inexistente)';dump_yaml(data,tmp_path/'engagement.yaml')
    with pytest.raises(ValueError,match='sin destino'):
        export.export(tmp_path/'engagement.yaml','docx',tmp_path/'report.docx')


def test_compact_density_and_word_intro_keep_with_content(tmp_path):
    data=sample();data['meta']['report_density']='compact';data['findings'][0]['cwe']='CWE-200';dump_yaml(data,tmp_path/'engagement.yaml')
    out=export.export(tmp_path/'engagement.yaml','docx',tmp_path/'report.docx');doc=Document(out)
    assert doc.styles['Normal'].paragraph_format.space_after.pt==4
    meta=[p for p in doc.paragraphs if p.style.name=='ReportGenMeta']
    assert any('CWE-200' in p.text for p in meta)
    assert all(p.paragraph_format.keep_with_next and p.paragraph_format.keep_together for p in meta)
    data['meta']['report_density']='tiny'
    assert validate.structure_issues(data)


@pytest.mark.parametrize('name',['../secret.txt','CON.txt','a\\b.txt','a?.txt','a.exe','a.txt.','a\x00.txt','factura\u202egnp.pdf','oculto\u200b.txt','roto\ud800.txt'])
def test_annex_names_cannot_escape_or_create_nonportable_paths(name):
    assert not attachments.valid_name(name)


def test_annex_requires_review_and_sha256(tmp_path):
    data=sample();row,blob=annex(data,tmp_path);row['reviewed']=False
    with pytest.raises(ValueError,match='Revisa'):attachments.inventory(data,tmp_path)
    row['reviewed']=True;(tmp_path/row['member']).write_bytes(b'changed')
    assert attachments.inventory(data,tmp_path)[0]['status']=='missing'
    with pytest.raises(ValueError): attachments.capture(data,tmp_path,tmp_path/'out')


def test_annex_selection_survives_snapshot_backup_and_restore(tmp_path):
    source=tmp_path/'project';source.mkdir();data=sample();row,blob=annex(data,source);dump_yaml(data,source/'engagement.yaml')
    project_history.save(source,data)
    backup=project_history.export_bundle(source);restored=tmp_path/'restored';project_history.import_bundle(backup,restored)
    assert attachments.read(restored,row)==blob
    captured=delivery.capture(restored,tmp_path/'capture')
    assert (tmp_path/'capture'/'anexos'/row['name']).read_bytes()==blob
    bundle=delivery.build(tmp_path/'capture',['html'],'revision','Entrega',captured,tmp_path/'outputs')
    with zipfile.ZipFile(BytesIO(bundle)) as z:
        manifest=json.loads(z.read('verificacion.json'))
        assert z.read('anexos/'+row['name'])==blob
        assert manifest['files']['anexos/'+row['name']]['sha256']==sha256(blob).hexdigest()
    data['attachments'][0]['include']=False;data['attachments'][0]['reviewed']=False;dump_yaml(data,restored/'engagement.yaml')
    assert not delivery.capture(restored,tmp_path/'excluded')['attachments']


def test_declared_missing_annex_is_visible_in_review(tmp_path):
    data=sample();data['attachments']=[dict(uid=str(uuid.uuid4()),name='pendiente.json',include=False,reviewed=False)]
    assert any(i['path']=='attachments' and i['level']=='warning' for i in workflows.review(data,tmp_path))


def test_annex_upload_is_revision_bound_and_excluded_by_default(tmp_path,monkeypatch):
    projects=tmp_path/'projects';project=projects/'audit';project.mkdir(parents=True);dump_yaml(sample(),project/'engagement.yaml');monkeypatch.setattr(api,'PROJECTS',projects)
    client=auth_client(api.app);before=revision(project/'engagement.yaml')
    response=client.post('/api/projects/audit/attachments/upload',data={'file':(BytesIO(b'{"ok":true}'),'evidence.json')},headers={'If-Match':before},content_type='multipart/form-data')
    assert response.status_code==200,response.get_data(as_text=True)
    row=response.json['data']['attachments'][0];assert row['include'] is False and row['reviewed'] is False
    stale=client.post('/api/projects/audit/attachments/upload',data={'file':(BytesIO(b'x'),'second.txt')},headers={'If-Match':before},content_type='multipart/form-data')
    assert stale.status_code==409
    assert len(list((project/'attachments').iterdir()))==1


def test_large_report_validation_is_bounded_and_preserves_unique_ids():
    data=sample();data['findings']=[dict(deepcopy(data['findings'][0]),id=f'F{i:04}',uid=str(uuid.uuid4())) for i in range(1000)]
    assert not [x for x in validate.validate(data) if x[0]=='error']
    data['findings'][-1]['id']=data['findings'][0]['id']
    assert any('duplicad' in message for level,message in validate.validate(data) if level=='error')


def test_literal_commands_not_executed_by_contract(tmp_path):
    marker=tmp_path/'SHOULD_NOT_RUN_0210'
    data=sample();data['findings'][0]['description_md']=f'```sh\ntouch {marker}; $(id); `whoami`\n```';dump_yaml(data,tmp_path/'engagement.yaml')
    captured=delivery.capture(tmp_path,tmp_path/'capture');out=export.export(tmp_path/'engagement.yaml','html',tmp_path/'report.html')
    assert export_contract.inspect(out,'html',captured['contract'])['content_units_checked']==2
    assert not marker.exists()


def test_annex_declaration_rejects_bad_names_without_editing_project(tmp_path,monkeypatch):
    projects=tmp_path/'projects';project=projects/'audit';project.mkdir(parents=True);dump_yaml(sample(),project/'engagement.yaml');monkeypatch.setattr(api,'PROJECTS',projects)
    client=auth_client(api.app);before=revision(project/'engagement.yaml')
    response=client.post('/api/projects/audit/attachments/declare',json={'name':'../error.txt'},headers={'If-Match':before})
    assert response.status_code==422
    assert revision(project/'engagement.yaml')==before
    assert not (project/'.history').exists()
    response=client.post('/api/projects/audit/attachments/declare',json={'name':'pendiente.txt'},headers={'If-Match':before})
    assert response.status_code==200
    assert client.get('/api/projects/audit/attachments').json['files'][0]['status']=='declared'


def test_word_inspection_checks_expected_image_placements(tmp_path):
    data=sample();dump_yaml(data,tmp_path/'engagement.yaml')
    out=export.export(tmp_path/'engagement.yaml','docx',tmp_path/'report.docx')
    with pytest.raises(ValueError,match='imágenes'):delivery.inspect_archive(out,'docx',{},1)
    with pytest.raises(ValueError,match='imagen publicada'):delivery.inspect_archive(out,'docx',{'img/missing.png':'0'*64},0)


def test_annex_unicode_aliases_cannot_collide_on_normalizing_filesystems():
    rows=[dict(uid=str(uuid.uuid4()),name=name) for name in ('café.txt','cafe\u0301.txt')]
    with pytest.raises(ValueError,match='duplicado'):attachments.validate_rows(rows)


def test_annex_does_not_break_visual_history_or_leak_into_comparison(tmp_path,monkeypatch):
    projects=tmp_path/'projects';project=projects/'audit';project.mkdir(parents=True)
    data=sample();row,_=annex(data,project);project_history.save(project,data)
    sid=project_history.checkpoint(project)['id'];monkeypatch.setattr(api,'PROJECTS',projects)
    client=auth_client(api.app)
    response=client.get(f'/api/projects/audit/history/{sid}/visual')
    assert response.status_code==200,response.get_data(as_text=True)
    assert row['name'] not in response.get_data(as_text=True)
    assert '{"synthetic":true}' not in response.get_data(as_text=True)


def test_launcher_updates_seeded_pip_before_installing_project(tmp_path,monkeypatch):
    import start
    import sys
    calls=[];monkeypatch.setattr(start,'ROOT',tmp_path)
    monkeypatch.setattr(start.venv.EnvBuilder,'create',lambda self,p:None)
    monkeypatch.setattr(start.subprocess,'run',lambda cmd,**kwargs:calls.append(cmd))
    monkeypatch.setattr(sys,'argv',['start.py','--setup'])
    assert start.main()==0
    assert calls[0][1:]==['-m','pip','install','--upgrade','pip>=26.2,<27']
    assert calls[1][1:5]==['-m','pip','install','-e']
