#!/usr/bin/env python3
"""Author trilingual Aster banking input projects, never report documents.

The previous long-table corpus supplies input composition primitives. Aster has
new business domains, narrative, independent identities and 0.42 workflow data.
Only report-gen's own publication and export paths may render the reports.
"""
from __future__ import annotations

import argparse
import base64
from collections import Counter
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys
import uuid
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import attack_paths
import attachments
import client_profiles
import engine
import finding_imports
import finding_instances
import http_evidence
import review_exchange
import test_plans
import validate
import workflows
import yaml
from PIL import Image, ImageDraw, PngImagePlugin

CASE = 'ASTER-FINANCIAL-GROUP-2026'
DATE = '2026-10-17'
TIMESTAMP = DATE + 'T12:00:00Z'
LANGUAGES = ('es', 'en', 'pt')
CONTENT = ROOT/'scripts/aster-case-content'
PRIVATE_MARKER = 'ASTER_PRIVATE_INBOX_DO_NOT_PUBLISH_2026'
HTTP_PRIVATE_MARKER = 'ASTER_PRIVATE_HTTP_DO_NOT_PUBLISH_2026'
METADATA_MARKER = 'ASTER_PRIVATE_IMAGE_METADATA_2026'
REDACTION_MARKER = 'ASTER_SYNTHETIC_REDACTION_CANARY_2026'
NAMESPACE = uuid.UUID('6a466407-b0f6-5739-b4e1-e14e49ed394e')
LONG_URL = ('https://docs.aster.example/banking/tenant-authorization-and-reconciliation/'
            'version-2026-10-17/record-0123456789abcdef0123456789abcdef0123456789abcdef'
            '?contract=ASTER%2D42&unit=synthetic&language=pt-BR#revisão-açaí-ñ')

spec = importlib.util.spec_from_file_location('aster_long_table_primitives', ROOT/'scripts/build-boreal-case.py')
BASE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(BASE)
BASE.CONTENT, BASE.NAMESPACE, BASE.CASE = CONTENT, NAMESPACE, CASE
BASE.PRIVATE_MARKER, BASE.METADATA_MARKER, BASE.REDACTION_MARKER = PRIVATE_MARKER, METADATA_MARKER, REDACTION_MARKER
BASE.LONG_URL = LONG_URL
LONG_TABLES = BASE.LONG_TABLES
write, table, csv_bytes, json_bytes = BASE.write, BASE.table, BASE.csv_bytes, BASE.json_bytes


def uid(value):
    return str(uuid.uuid5(NAMESPACE, value))


def local(lang, es, en, pt):
    return (es, en, pt)[LANGUAGES.index(lang)]


def renamed(value):
    if isinstance(value, dict): return {key: renamed(child) for key, child in value.items()}
    if isinstance(value, list): return [renamed(child) for child in value]
    if isinstance(value, str):
        for before, after in [('BOREAL', 'ASTER'), ('Boreal', 'Aster'), ('boreal', 'aster'), ('BRL-', 'AST-')]:
            value = value.replace(before, after)
        return value
    return value


def load_content(lang):
    return BASE.load_content(lang)


def add_instances(doc, lang):
    finding = doc['findings'][0]
    finding['instances'] = []
    for n in range(18):
        row = dict(uid=uid(f'authorization-instance-{n+1}'), asset_uid=doc['assets'][n % 3]['uid'],
                   endpoint=f'https://api.aster.example/v2/organizations/TENANT-{n%2+1}/accounts/SYNTH-{n+1:03d}',
                   parameter='account_id', identity=local(lang, 'Operador', 'Operator', 'Operador')+' '+str(n%4+1),
                   environment='ASTER-SYNTHETIC-R4', owner=doc['assets'][n%3]['notes'].split(';')[0], due_date='2026-11-15',
                   status='blocked' if n == 17 else 'open', evidence_uids=[doc['evidence'][n]['uid']], retests=[],
                   notes_md=local(lang, 'Instancia inventada; la corrección de otros destinos no cierra este registro.',
                                  'Invented instance; fixes to other targets do not close this record.',
                                  'Instância inventada; correções de outros destinos não encerram este registro.'))
        if n == 17:
            row['notes_md'] += ' '+local(lang, 'Bloqueada: falta una identidad delegada de prueba.',
                'Blocked: a delegated test identity is missing.', 'Bloqueada: falta uma identidade delegada de teste.')
        finding['instances'].append(row)
    for n in range(15):
        with patch.object(workflows, 'new_uid', return_value=uid(f'instance-retest-{n+1}')):
            finding_instances.record_retest(doc, finding, finding['instances'][n]['uid'],
                dict(tested_on='2026-10-17', assessor=doc['meta']['assessor'], result='fixed', evidence_uids=[doc['evidence'][n+18]['uid']],
                     notes_md=local(lang, 'Retest sintético: el destino devuelve la denegación prevista para el rol ajeno; el rol propietario conserva acceso. No se ejecutó tráfico.',
                        'Synthetic retest: the target returns the expected denial for the unrelated role; the owner role retains access. No traffic was executed.',
                        'Reteste sintético: o destino retorna a negação prevista para o papel alheio; o papel proprietário mantém acesso. Nenhum tráfego foi executado.')), TIMESTAMP)
    finding_instances.update_aggregate(finding)
    return doc


def add_http(doc, lang):
    for n in range(1, 9):
        record = dict(title=HTTP_PRIVATE_MARKER+f' / {n}', notes=HTTP_PRIVATE_MARKER,
            original=dict(request=dict(method='GET' if n%2 else 'POST',
                url=f'https://api.aster.example/v2/accounts/SYNTH-{n:03d}?session='+HTTP_PRIVATE_MARKER,
                http_version='HTTP/1.1', headers=[dict(name='Authorization', value='Bearer '+HTTP_PRIVATE_MARKER), dict(name='X-Synthetic-Tenant', value='TENANT-'+str(n%2+1))],
                body='' if n%2 else json.dumps({'intent': 'SYNTHETIC-'+str(n), 'private': HTTP_PRIVATE_MARKER}), body_encoding='utf-8'),
                response=None if n==7 else dict(status=403 if n in (3,4,6) else 200, http_version='HTTP/1.1',
                    headers=[dict(name='Content-Type', value='application/json'), dict(name='Set-Cookie', value='session='+HTTP_PRIVATE_MARKER)],
                    body=base64.b64encode(HTTP_PRIVATE_MARKER.encode()).decode() if n==6 else json.dumps({'synthetic': True, 'private': HTTP_PRIVATE_MARKER}),
                    body_encoding='base64' if n==6 else 'utf-8'), captured_at=TIMESTAMP, identity=HTTP_PRIVATE_MARKER, source='synthetic-model'))
        with patch.object(workflows, 'new_uid', return_value=uid(f'http-{n}')), patch('project_history.now', return_value=TIMESTAMP):
            doc, added = http_evidence.add(doc, [record], finding_uids=[doc['findings'][(n-1)%3]['uid']], asset_uids=[doc['assets'][(n-1)%3]['uid']])
            if n < 8:
                doc = http_evidence.update(doc, added[0], dict(ack_reviewed=True, publication=dict(
                    request_text=f'{record["original"]["request"]["method"]} https://api.aster.example/v2/accounts/SYNTH-{n:03d} HTTP/1.1\nAuthorization: [REDACTED]\nX-Synthetic: true',
                    response_text=(f'HTTP/1.1 {record["original"]["response"]["status"]}\nContent-Type: application/json\n\n'+json.dumps({'synthetic': True, 'case': f'ASTER-HTTP-{n:02d}'})) if n!=7 else local(lang, 'Sin respuesta HTTP capturada; no se inventa un cuerpo.', 'No HTTP response captured; no body is invented.', 'Nenhuma resposta HTTP capturada; nenhum corpo é inventado.'),
                    caption=f'ASTER-HTTP-{n:02d} / '+local(lang, 'Copia sintética revisada; comparación entre roles y revisiones.', 'Reviewed synthetic copy; comparison across roles and revisions.', 'Cópia sintética revisada; comparação entre papéis e revisões.'))))
    return doc


def add_tests(doc, lang):
    names = local(lang, ['Lector', 'Operador', 'Supervisor', 'Administrador'], ['Reader', 'Operator', 'Supervisor', 'Administrator'], ['Leitor', 'Operador', 'Supervisor', 'Administrador'])
    rows = test_plans.matrix(dict(roles=names, tenants=['TENANT-A', 'TENANT-B'], operations=[f'GET /v2/accounts/SYNTH-{n:03d}' for n in range(1,13)],
        base=dict(title=local(lang, 'Separación por rol, organización y objeto', 'Role, tenant and object separation', 'Separação por papel, organização e objeto'),
            specialty='api', methodology='ASTER synthetic acceptance plan', methodology_version='1.0',
            expected=local(lang, 'El acceso ajeno se rechaza; el acceso autorizado mantiene la misma revisión.', 'Unrelated access is denied; authorized access retains the same revision.', 'O acesso alheio é negado; o acesso autorizado mantém a mesma revisão.'), asset_uids=[doc['assets'][0]['uid']])))
    for specialty in ('web', 'ad', 'cloud', 'mobile', 'ai', 'custom'):
        for n in range(1,4):
            rows.append(test_plans.create(dict(title=local(lang, 'Contrato especializado', 'Specialty contract', 'Contrato especializado')+f' / {specialty.upper()} / {n}',
                specialty=specialty, methodology='ASTER synthetic acceptance plan', methodology_version='1.0',
                expected=local(lang, 'Preservar identidad, contexto y límites entre componentes.', 'Preserve identity, context and boundaries across components.', 'Preservar identidade, contexto e limites entre componentes.'), asset_uids=[doc['assets'][(len(rows)*3)%36]['uid']])))
    states = ('passed', 'failed', 'pending', 'blocked', 'not_applicable')
    outcomes = local(lang,
        {'passed':'El modelo sintético conserva el rechazo previsto; no se observó un fallo en esta representación.', 'failed':'El modelo sintético expone una diferencia de autorización vinculada al hallazgo indicado.', 'pending':'', 'blocked':'La identidad o dependencia de prueba no está disponible en el escenario.', 'not_applicable':'La operación no existe para esta combinación documentada de rol y organización.'},
        {'passed':'The synthetic model retains the expected denial; no failure was observed in this representation.', 'failed':'The synthetic model exposes an authorization difference linked to the referenced finding.', 'pending':'', 'blocked':'The required test identity or dependency is unavailable in the scenario.', 'not_applicable':'The operation does not exist for this documented role and tenant combination.'},
        {'passed':'O modelo sintético preserva a negação prevista; nenhuma falha foi observada nesta representação.', 'failed':'O modelo sintético expõe uma diferença de autorização vinculada ao achado indicado.', 'pending':'', 'blocked':'A identidade ou dependência de teste necessária não está disponível no cenário.', 'not_applicable':'A operação não existe para esta combinação documentada de papel e organização.'})
    for n,row in enumerate(rows,1):
        state = states[(n-1)%5]
        row.update(uid=uid(f'test-case-{n}'), test_id=f'ASTER-TC-{n:03d}', status=state, observed=outcomes[state],
                   prerequisites=local(lang, 'Datos sintéticos y permiso documental para el caso; no se realizaron conexiones.', 'Synthetic data and documentary permission for this case; no connections were made.', 'Dados sintéticos e permissão documental para o caso; nenhuma conexão foi realizada.'),
                   notes=local(lang, 'Resultado inventado para verificar report-gen; no acredita cumplimiento.', 'Invented result to verify report-gen; does not establish compliance.', 'Resultado inventado para verificar report-gen; não comprova conformidade.'))
        if state in ('passed','failed'):
            row['evidence_uids']=[doc['evidence'][(n-1)%84]['uid']]
            row['http_evidence_uids']=[uid('http-'+str((n-1)%7+1))]
        if state=='failed': row['finding_uids']=[doc['findings'][(n-1)%72]['uid']]
    doc['test_cases']=rows
    return doc


def add_paths(doc, lang):
    titles = local(lang, ['Delegación y consulta entre organizaciones', 'Recuperación y reapertura de permisos', 'Contexto de IA y publicación revisada'],
                   ['Delegation and cross-tenant query', 'Recovery and permission reopening', 'AI context and reviewed publication'],
                   ['Delegação e consulta entre organizações', 'Recuperação e reabertura de permissões', 'Contexto de IA e publicação revisada'])
    stages = local(lang, ['Identidad inicial', 'Servicio delegado', 'Objeto de otra organización', 'Consecuencia condicionada'],
                   ['Initial identity', 'Delegated service', 'Other tenant object', 'Conditional consequence'],
                   ['Identidade inicial', 'Serviço delegado', 'Objeto de outra organização', 'Consequência condicionada'])
    doc['attack_paths']=[]
    for n,title in enumerate(titles,1):
        nodes=[dict(uid=uid(f'path-{n}-node-{k}'), title=label, privilege=local(lang,'Permiso ficticio y limitado','Fictional limited permission','Permissão fictícia e limitada'), asset_uids=[doc['assets'][(n*3+k)%36]['uid']], finding_uids=[doc['findings'][(n*6+k)%72]['uid']]) for k,label in enumerate(stages)]
        edges=[]
        for k,state in enumerate(('observed','inferred','blocked')):
            edges.append(dict(uid=uid(f'path-{n}-edge-{k}'),source_uid=nodes[k]['uid'],target_uid=nodes[k+1]['uid'],state=state,
                preconditions=local(lang,'Sujetos y objetos ficticios; misma revisión del modelo.','Fictional subjects and objects; same model revision.','Sujeitos e objetos fictícios; mesma revisão do modelo.'),
                observation=local(lang,'Transición representada en el modelo sintético; las inferencias y el bloqueo no equivalen a una explotación demostrada.','Transition represented in the synthetic model; inferences and the blocked step are not demonstrated exploitation.','Transição representada no modelo sintético; inferências e a etapa bloqueada não equivalem a exploração demonstrada.'),
                mitigation=local(lang,'Validar la autorización en cada frontera y conservar la revocación durante la recuperación.','Validate authorization at each boundary and preserve revocation during recovery.','Validar a autorização em cada limite e preservar a revogação durante a recuperação.'),
                evidence_uids=[doc['evidence'][(n*7+k)%84]['uid']] if state=='observed' else [],http_evidence_uids=[uid(f'http-{n}') ] if state=='observed' else []))
        doc['attack_paths'].append(attack_paths.create(dict(title=title+' / '+local(lang,'SIMULADO','SIMULATED','SIMULADO'),
            description=local(lang,'Ruta declarada para el escenario documental; cada transición conserva su grado de certeza.','Declared path for the documentary scenario; each transition retains its certainty level.','Caminho declarado para o cenário documental; cada transição mantém seu nível de certeza.'),
            consequence=local(lang,'Impacto hipotético sujeto a condiciones no demostradas en sistemas reales.','Hypothetical impact subject to conditions not demonstrated on real systems.','Impacto hipotético sujeito a condições não demonstradas em sistemas reais.'),nodes=nodes,edges=edges),uid=uid(f'path-{n}')))
    return doc


def add_client_review(doc, lang):
    profile=dict(uid=uid('client-profile'),version=1,name=doc['meta']['client'],client=doc['meta']['client'],
        terms=[dict(term=local(lang,'hackeo','hack','invasão'),preferred=local(lang,'evaluación autorizada','authorized assessment','avaliação autorizada'))],
        required_sections=['executive_summary','risk_posture','methodology','remediation_plan'],
        acceptance_criteria=[local(lang,'Cada instancia conserva estado, evidencia y retest.','Each instance retains status, evidence and retest.','Cada instância mantém status, evidência e reteste.'),
            local(lang,'Publicar únicamente copias HTTP revisadas.','Publish only reviewed HTTP copies.','Publicar somente cópias HTTP revisadas.')],
        delivery=dict(formats=['pdf','docx','md','html'],audience='technical',language=lang))
    proposal=client_profiles.preview(doc,profile)
    doc=client_profiles.apply(doc,proposal,[row['key'] for row in proposal['changes']])
    finding=doc['findings'][1]
    with patch.object(workflows,'new_uid',return_value=uid('review-package')):
        doc,package=review_exchange.issue(doc,'aster-'+lang,sha256(json_bytes(doc)).hexdigest(),[finding['uid']],['description_md','impact_md'])
    finding=doc['findings'][1]
    note=local(lang,'Revisión sintética aceptada: el impacto es condicional y no implica pérdidas reales.','Accepted synthetic review: impact is conditional and does not imply real losses.','Revisão sintética aceita: o impacto é condicional e não implica perdas reais.')
    returned=dict(package=package,reviewer=doc['meta']['assessor'],changes=[dict(finding_uid=finding['uid'],field='impact_md',after=finding['impact_md']+'\n\n'+note,note=note)])
    proposal=review_exchange.preview(doc,'aster-'+lang,returned)
    doc=review_exchange.apply(doc,proposal,[proposal['changes'][0]['key']])
    return doc,returned


def make_project(lang):
    doc=renamed(BASE.make_project(lang))
    doc['meta']['version']='ASTER 1.0'
    doc['report']['workflow'].update(include_instances=True,include_test_cases=True,include_attack_paths=True)
    doc=add_instances(doc,lang)
    doc=add_http(doc,lang)
    doc=add_tests(doc,lang)
    doc=add_paths(doc,lang)
    return add_client_review(doc,lang)


def draw_assets(directory, content):
    """Draw labeled synthetic evidence inputs, never screenshots of real systems."""
    directory.mkdir(parents=True)
    s=content['strings']
    for n in range(1,85):
        domain=content['domains'][((n-1)%72)//6]['name']
        control=content['controls'][(n-1)%6]['title']
        portrait=n in (6,18,31,48,73,80)
        width,height=(820,1040) if portrait else (1440,660)
        image=Image.new('RGB',(width,height),'#edf3f1');draw=ImageDraw.Draw(image)
        draw.rectangle((0,0,width,76),fill='#17383c')
        BASE.SHARED.draw_wrapped(draw,'ASTER / '+f'E{n:02d} / '+s['simulated'],(28,24),width=width-56,size=24,fill='white')
        y=BASE.SHARED.draw_wrapped(draw,control+' / '+domain,(28,103),width=width-56,size=25)+25
        values=[f'd{((n-1)%72)//6+1:02d}.aster.example','ASTER-R4 / '+f'F{(n-1)%72+1:02d}',s['image_decision'],s['image_execution']]
        for i,(label,value) in enumerate(zip(s['image_labels'],values)):
            rh=125 if portrait else 83
            draw.rounded_rectangle((24,y,width-24,y+rh-5),radius=6,fill='white' if i%2==0 else '#dce7e3')
            BASE.SHARED.draw_wrapped(draw,label,(40,y+10),width=width-80,size=16,fill='#426168')
            end=BASE.SHARED.draw_wrapped(draw,value,(40,y+38),width=width-80,size=19)
            if end>y+rh: raise ValueError('Aster evidence text overflow: '+str(n))
            y+=rh
        if y>height-65: raise ValueError('Aster evidence image overflow: '+str(n))
        BASE.SHARED.draw_wrapped(draw,s['image_footer'],(28,height-50),width=width-56,size=15)
        metadata=PngImagePlugin.PngInfo();metadata.add_text('Description',METADATA_MARKER)
        image.save(directory/f'evidence-{n:02d}.png',pnginfo=metadata)
    for name,height in [('logo',210),('cover',380)]:
        image=Image.new('RGB',(1440,height),'#17383c');draw=ImageDraw.Draw(image)
        draw.polygon([(40,160),(90,40),(140,160)],outline='#88ceb6',width=6)
        BASE.SHARED.draw_wrapped(draw,s['name'],(182,42),width=1220,size=44,fill='white')
        BASE.SHARED.draw_wrapped(draw,s['byline'],(185,118),width=1210,size=24,fill='#b8dbd0')
        if name=='cover':BASE.SHARED.draw_wrapped(draw,s['fictional'],(42,230),width=1356,size=23,fill='white')
        image.save(directory/(name+'.png'))


def add_annexes(directory,doc,content):
    BASE.add_annexes(directory,doc,content)
    for row in doc['attachments']:
        path=directory/row['member']
        blob=renamed(path.read_text()).encode('utf-8')
        write(path,blob);row['sha256']=sha256(blob).hexdigest()


def build_case(output,languages=LANGUAGES):
    output,languages=Path(output).resolve(),tuple(languages)
    if output.exists():raise FileExistsError('Output already exists: '+str(output))
    if not languages or len(set(languages))!=len(languages) or any(lang not in LANGUAGES for lang in languages):raise ValueError('Choose unique languages from es, en, pt')
    output.mkdir(parents=True)
    projects={}
    for lang in languages:
        content=load_content(lang);project=output/'projects'/lang
        draw_assets(project/'img',content)
        write(project/'originals/evidence-01.png',(project/'img/evidence-01.png').read_bytes())
        write(project/'private/unlinked.txt',PRIVATE_MARKER+'\n'+content['strings']['private'])
        doc,returned=make_project(lang)
        add_annexes(project,doc,content)
        validate.require_valid(doc,final=True)
        errors=workflows.structure_errors(doc)
        if errors:raise ValueError(errors)
        inventory=attachments.inventory(doc,project)
        if any(row['status'] not in ('included','excluded') for row in inventory):raise ValueError('Invalid Aster annex inventory')
        write(project/'engagement.yaml',yaml.safe_dump(doc,allow_unicode=True,sort_keys=False,width=110))
        if engine.load_engagement(project/'engagement.yaml')!=doc:raise ValueError('Aster YAML roundtrip changed input')
        write(output/'inputs'/lang/'review-return.json',json_bytes(returned))
        issues=workflows.preflight(doc,project,lang)
        if any(row['level']=='error' for row in issues):raise ValueError(issues)
        projects[lang]=dict(project='projects/'+lang,vulnerabilities=72,machines=6,assets=36,evidence=84,coverage=216,root_cause_groups=6,
            instances=finding_instances.summary(doc['findings'][0],lang),test_cases=len(doc['test_cases']),
            test_status_counts=dict(Counter(row['status'] for row in doc['test_cases'])),specialties=sorted({row['specialty'] for row in doc['test_cases']}),
            http_pairs=len(doc['http_evidence']),reviewed_http_pairs=sum(row['publication'] is not None for row in doc['http_evidence']),attack_paths=len(doc['attack_paths']),
            client_profile_version=doc['client_profile']['version'],external_review_packages=len(doc['review_exchange']['packages']),
            long_tables=[dict(spec,token=f'AST-T{n:02d}',first=f'AST-T{n:02d}-R001',last=f'AST-T{n:02d}-R{spec["rows"]:03d}') for n,spec in enumerate(LONG_TABLES,1)],
            validation_errors=0,validation_warnings=validate.validate(doc),preflight_issues=issues)
    imported=BASE.import_inputs(output/'inputs'/'scanners')
    for name,row in imported.items():
        path=output/'inputs'/'scanners'/name;write(path,renamed(path.read_text()))
        preview=finding_imports.preview(dict(format=row['format'],text=path.read_text()),dict(meta=dict(lang='en'),findings=[],assets=[],coverage=[]))
        if any(item.get('errors') for item in preview['rows']):raise ValueError('Invalid Aster inert import')
        row['sha256']=sha256(path.read_bytes()).hexdigest()
    files={path.relative_to(output).as_posix():dict(bytes=path.stat().st_size,sha256=sha256(path.read_bytes()).hexdigest()) for path in sorted(output.rglob('*')) if path.is_file()}
    manifest=dict(schema='report-gen-aster-source/1',case=CASE,date=DATE,fictional=True,source_generator='scripts/build-aster-case.py',
        source_composition_primitives='scripts/build-boreal-case.py',prose_languages=list(languages),reports_generated_by_builder=False,network_to_scenario_targets=False,
        projects=projects,import_previews=imported,private_markers=[PRIVATE_MARKER,HTTP_PRIVATE_MARKER,METADATA_MARKER,REDACTION_MARKER],
        content_sha256={lang:sha256((CONTENT/(lang+'.json')).read_bytes()).hexdigest() for lang in languages},files=files)
    write(output/'manifest.json',json_bytes(manifest));return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--languages',nargs='+',choices=LANGUAGES,default=LANGUAGES)
    args=parser.parse_args()
    result=build_case(args.output,args.languages)
    print(json.dumps({key:value for key,value in result.items() if key!='files'},ensure_ascii=False,indent=2))
