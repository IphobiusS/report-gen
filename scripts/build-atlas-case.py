#!/usr/bin/env python3
"""Author ATLAS 1.0 source data; report-gen alone must generate all report outputs.

Creates deterministic localized YAML, synthetic PNGs and inert annex/scanner
inputs. The builder performs schema, link, annex and preflight validation. It
never produces PDF, DOCX, HTML or Markdown report outputs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from hashlib import sha256
from io import StringIO
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import attachments
import capture_inbox
import cvss
import engine
import finding_imports
import validate
import workflows
import yaml
from PIL import Image, ImageDraw, ImageFont, PngImagePlugin

CASE = 'ATLAS-SERVICIOS-FINANCIEROS-2026'
DATE = '2026-10-16'
NAMESPACE = uuid.UUID('8a46cc89-9324-54d1-9394-a7c4d6381773')
CONTENT = ROOT / 'scripts/atlas-case-content'
PRIVATE_MARKER = 'ATLAS_PRIVATE_INBOX_DO_NOT_PUBLISH_2026'
REDACTION_MARKER = 'ATLAS_SYNTHETIC_REDACTION_CANARY_2026'
METADATA_MARKER = 'ATLAS_PRIVATE_IMAGE_METADATA_2026'
UNLINKED_MARKER = 'ATLAS_PRIVATE_UNLINKED_8F21'
LONG_URL = ('https://docs.atlas.example/continuity/settlement-and-policy-reconciliation/'
            'version-2026-10-16/record-0123456789abcdef0123456789abcdef0123456789abcdef'
            '?contract=ATLAS%2D42&currency=XCU&language=pt-BR#revisão-açaí-ñ')
VECTORS = {
    'critical': 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H',
    'high': 'CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N',
    'medium': 'CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N',
    'low': 'CVSS:3.1/AV:N/AC:H/PR:L/UI:R/S:U/C:L/I:N/A:N',
    'info': 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:N/I:N/A:N',
}
V4 = {25: 'CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N',
      30: 'CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N'}


def uid(label):
    return str(uuid.uuid5(NAMESPACE, label))


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()


def write(path, blob):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(blob if isinstance(blob, bytes) else blob.encode('utf-8'))


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                     ['| ' + ' | '.join(str(v).replace('|', '\\|').replace('\n', '<br>') for v in row) + ' |' for row in rows])


def csv_bytes(headers, rows):
    stream = StringIO(newline='')
    writer = csv.writer(stream, lineterminator='\n')
    writer.writerow(headers)
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8')


def load_content(language):
    if language not in ('es', 'en', 'pt'):
        raise ValueError('Supported languages: es, en, pt')
    data = json.loads((CONTENT / (language + '.json')).read_text(encoding='utf-8'))
    if (data.get('case') != CASE or len(data.get('findings', [])) != 60 or len(data.get('assets', [])) != 28
            or len(data.get('root_groups', [])) != 10 or len(data.get('machine_specs', [])) != 7
            or len(data.get('sections', [])) != 23 or not data.get('strings') or not data.get('meta')):
        raise ValueError('Incomplete localized Atlas content: ' + language)
    return data


def font(size, mono=False):
    return ImageFont.truetype(str(ROOT / ('themes/fonts/DejaVuSansMono.ttf' if mono else 'exporters/fonts/DejaVuSans.ttf')), size)


def draw_wrapped(draw, value, xy, *, width, size=21, fill='#152c48', mono=False, line_height=None):
    """Wrap using measured glyph widths, preserving all words in localized PNGs."""
    selected = font(size, mono)
    words, lines, current = value.split(), [], ''
    for word in words:
        candidate = (current + ' ' + word).strip()
        if current and draw.textlength(candidate, font=selected) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    line_height = line_height or int(size * 1.35)
    x, y = xy
    for line in lines:
        if draw.textlength(line, font=selected) > width:
            raise ValueError('Unbreakable synthetic image text exceeds layout width: ' + line)
        draw.text((x, y), line, font=selected, fill=fill)
        y += line_height
    return y


def evidence_image(path, number, content):
    s = content['strings']
    index = number - 1 if number <= 60 else number - 61
    spec = content['findings'][index]
    asset = content['assets'][spec['asset']]
    portrait = number in (6, 18, 31, 48, 61, 73)
    detail = number > 60
    width, height = (820, 1060) if portrait else ((1440, 640) if detail else (1440, 540))
    img = Image.new('RGB', (width, height), '#f2f5f6')
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, width, 76), fill='#152c48')
    draw_wrapped(draw, f'ATLAS / E{number:02d} / ' + s['image_model'], (28, 23), width=width-56, size=22, fill='white')
    y = draw_wrapped(draw, spec['title'], (28, 102), width=width-56, size=25) + 20
    rows = [(s['image_asset'], asset['host']),
            (s['image_record'], f'ATLAS-EXP-{index + 1:02d} / ' + s['image_organization']),
            (s['image_decision'], s['image_decision_value']),
            (s['image_classification'], s['severity_labels'][spec['severity']].upper() + ' / ' + s['image_classification_suffix']),
            (s['image_execution'], s['image_execution_value'])]
    for i, (label, value) in enumerate(rows):
        row_height = 112 if portrait else 53
        draw.rounded_rectangle((24, y, width-24, y+row_height-5), radius=5, fill='white' if i%2 == 0 else '#e3eaee')
        if portrait:
            draw_wrapped(draw, label.upper(), (40, y+10), width=width-80, size=17, fill='#536875')
            end = draw_wrapped(draw, value, (40, y+40), width=width-80, size=18, mono=True)
        else:
            draw_wrapped(draw, label, (40, y+13), width=230, size=18, fill='#536875')
            end = draw_wrapped(draw, value, (290, y+13), width=width-330, size=18, mono=True)
        if end > y + row_height:
            raise ValueError('Synthetic evidence row overflow: ' + str(number))
        y += row_height
    if detail:
        y += 14
        y = draw_wrapped(draw, s['image_detail_title'], (28, y), width=width-56, size=18, fill='#225e83')
        for line in s['image_detail_rows']:
            y = draw_wrapped(draw, line, (28, y+3), width=width-56, size=17)
    if y > height-58:
        raise ValueError('Synthetic evidence image overflow: ' + str(number))
    draw_wrapped(draw, f'ATLAS / {DATE} / ' + s['image_footer'], (28, height-36), width=width-56, size=14, fill='#536875')
    metadata = PngImagePlugin.PngInfo()
    metadata.add_text('Description', METADATA_MARKER)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, format='PNG', pnginfo=metadata, optimize=False)


def branding(directory, content):
    meta, s = content['meta'], content['strings']
    logo = Image.new('RGB', (1400, 190), '#152c48')
    draw = ImageDraw.Draw(logo)
    draw.polygon([(40,145),(95,35),(150,145)], outline='#6ec3cf', width=7)
    draw.line((65,106,125,106), fill='#6ec3cf', width=5)
    draw_wrapped(draw, meta['wordmark'], (195,35), width=1165, size=48, fill='white')
    draw_wrapped(draw, meta['byline'], (198,110), width=1155, size=23, fill='#c1d4e2')
    logo.save(directory / 'logo.png')
    cover = Image.new('RGB', (1440, 390), '#152c48')
    draw = ImageDraw.Draw(cover)
    for n, label in enumerate(s['cover_labels']):
        x = 30 + n*355
        draw.rounded_rectangle((x,58,x+315,270), radius=8, outline='#6ec3cf', width=3)
        draw.text((x+22,83), f'0{n+1}', font=font(50), fill='#6ec3cf')
        draw_wrapped(draw, label, (x+22,203), width=271, size=21, fill='white')
    draw_wrapped(draw, s['cover_summary'], (32,322), width=1376, size=23, fill='#c1d4e2')
    cover.save(directory / 'cover.png')


def findings(content):
    s, assets = content['strings'], content['assets']
    result = []
    for n, spec in enumerate(content['findings'], 1):
        fid, vector = f'F{n:02d}', V4.get(n, VECTORS[spec['severity']])
        rating = cvss.score(vector)
        if rating['severity'] != spec['severity']:
            raise ValueError('Inconsistent scenario vector: ' + fid)
        group = content['root_groups'][spec['group']]
        asset = assets[spec['asset']]
        status = ('open', 'in_progress', 'reported_fixed', 'verified_fixed', 'accepted', 'not_verified')[(n-1)%6]
        matrix = table(s['contract_headers'], [
            [s['allowed'], group['allowed'], s['allowed_evidence']],
            [s['rejected'], group['rejected'], s['rejected_evidence']],
            [s['recovery'], group['recovery'], s['recovery_evidence']],
        ])
        row = dict(id=fid, uid=uid(fid), mode='vuln', title=spec['title']+' '+s['simulated'], severity=spec['severity'],
            cvss=rating['score'], cvss_vector=vector, cvss_version=vector.split('/')[0].split(':')[1], cwe=spec['cwe'],
            description_md=spec['condition']+'\n\n'+s['description_limit'], impact_md=spec['consequence'], remediation_md=spec['correction'],
            affected='https://'+asset['host']+'/scenario/'+fid.lower(), owner=asset['owner']+' '+s['fictional_role'],
            due_date=f'2026-11-{(n-1)%28+1:02d}', status=status, verification='inconclusive' if status=='not_verified' else 'confirmed',
            asset_uids=[uid('asset-'+str(spec['asset']))], evidence_uids=[uid('evidence-'+str(n))], root_cause_uid=uid('root-'+str(spec['group'])),
            closure_criteria_md=s['closure'], walkthrough=[dict(lead=s['walkthrough_scenario'],text_md=spec['scenario']),dict(lead=s['walkthrough_contract'],text_md=matrix)],
            references=['https://docs.atlas.example/controls/'+fid.lower()+'#acceptance'])
        if n <= 24:
            row['evidence_uids'].append(uid('evidence-'+str(60+n)))
        if n % 3 == 1:
            row['walkthrough'].append(dict(lead=s['walkthrough_record'],command=f'CASE={CASE}\nFINDING={fid}\nSUBJECT=SYNTHETIC-ORGANIZATION-A\nOBLIGATION=ATLAS-EXP-{n:02d}\nREVISION=3\nNETWORK_EXECUTION=NONE'))
        if n == 12:
            row['walkthrough'].extend([
                dict(lead=s['image_tables_1'],text_md=table(s['image_table_headers'],[
                    [s['image_pattern_external'],'[!['+s['image_alt_prefix']+' 12](img/evidence-12.png)](https://docs.atlas.example/identity#contract)'],
                    [s['image_pattern_pair'],'[!['+s['image_alt_prefix']+' 11](img/evidence-11.png) !['+s['image_alt_prefix']+' 12](img/evidence-12.png)](https://docs.atlas.example/identity#multiple)']])),
                dict(lead=s['image_tables_2'],text_md=table(s['image_table_headers'],[
                    [s['image_pattern_adjacent'],'['+s['image_before']+'!['+s['image_alt_prefix']+' 12](img/evidence-12.png)'+s['image_after']+'](#F12)'],
                    [s['image_pattern_portrait'],'!['+s['image_alt_prefix']+' 61](img/evidence-61.png)!['+s['image_alt_prefix']+' 62](img/evidence-62.png)']]))])
        if n == 50:
            row['description_md'] += '\n\n'+s['redaction_intro']+' '+REDACTION_MARKER+'.'
        if n == 42:
            row['references'].append(LONG_URL)
            row['description_md'] += '\n\n['+s['long_reference']+']('+LONG_URL+')'
        if status in ('reported_fixed','accepted'):
            row['reported_remediation'] = s['reported_remediation']
        if n % 2 == 0:
            outcome = 'fixed' if status == 'verified_fixed' else ('open','partial','not_verified')[(n//2)%3]
            row['retests'] = [dict(uid=uid('retest-'+str(n)),tested_on='2026-10-15',assessor=s['retest_assessor'],result=outcome,
                notes_md=s['retest_notes']+'\n\n'+table(s['retest_headers'],[[s['allowed'],s['retest_allowed']],[s['rejected'],s['retest_rejected']],[s['recovery'],s['retest_scope']]]),evidence_uids=[uid('evidence-'+str(n))])]
        if n == 54:
            row['retests'].append(dict(uid=uid('retest-undated'),tested_on='',assessor=s['retest_undated_assessor'],result='not_verified',notes_md=s['retest_undated_notes'],evidence_uids=[]))
        result.append(row)
    return result


def machines(content):
    s = content['strings']
    result = []
    for n, spec in enumerate(content['machine_specs'],1):
        asset=content['assets'][spec['asset']]
        # Every primary evidence image depicts its corresponding finding's
        # asset. Select by that relationship, never by notebook position.
        evidence_number = next((index for index, finding in enumerate(content['findings'], 1)
                                if finding['asset'] == spec['asset']), None)
        if evidence_number is None:
            raise ValueError(f'Machine asset has no matching evidence: M{n:02d}')
        phases=[dict(name=p['name'],steps=[dict(lead=f'M{n:02d}.{k}',text_md=p['narrative'],command=f'MODEL_ONLY=true\nMACHINE=M{n:02d}\nPHASE={k}\nNETWORK_EXECUTION=NONE')]) for k,p in enumerate(spec['phases'],1)]
        result.append(dict(id=f'M{n:02d}',uid=uid(f'M{n:02d}'),mode='machine',title=asset['name']+' — '+s['machine_title_suffix'],
            host=dict(name=asset['host'],ip=asset['ip'],os=s['machine_os']),open_ports=s['machine_ports'],summary_md=s['warning']+' '+spec['summary']+' '+s['machine_summary_limit'],
            status='not_verified',verification='unverified',owner=asset['owner']+' '+s['fictional_role'],due_date='2026-12-15',
            asset_uids=[uid('asset-'+str(spec['asset']))],evidence_uids=[uid('evidence-'+str(evidence_number))],phases=phases,
            proof=[dict(name=f'model-M{n:02d}.txt',value=f'ATLAS_SYNTHETIC_PROOF_{n}_NOT_A_CAPTURED_FLAG',notes=s['proof_notes'])]))
    return result


def sections(content):
    s=content['strings']
    controls=[[f'ATLAS-{n:02d}-{suffix}',f'[F{n:02d}](#F{n:02d})',label,s['contract_limit']] for n in range(1,61) for suffix,label in [('P',s['coverage_allowed']),('N',s['coverage_rejected']),('R',s['coverage_recovery'])]]
    replacements={
        '{LONG_URL}':LONG_URL,
        '{CONTRACT_TABLE}':table(s['contract_table_headers'],controls),
        '{LITERAL_TABLE}':table(s['literal_table_headers'],[['REF-LONG',LONG_URL,s['literal_contract_url']],['UNICODE','acción / revisão / açaí / São Paulo / ñ / Überprüfung',s['literal_contract_unicode']],['ESCAPES','A&B <demo> [test] %2D %3A',s['literal_contract_escapes']]]),
        '{ANNEX_TABLE}':table(s['annex_table_headers'],[[name,s['annex_excluded'] if i==4 else s['annex_included'],s['annex_descriptions'][i]] for i,name in enumerate(s['annex_names'])]),
    }
    def render(value):
        if isinstance(value,str):
            for key,replacement in replacements.items():value=value.replace(key,replacement)
        elif isinstance(value,list):value=[render(x) for x in value]
        elif isinstance(value,dict):value={k:render(v) for k,v in value.items()}
        return value
    return render(content['sections'])


def make_project(language='es'):
    content=load_content(language)
    s,m=content['strings'],content['meta']
    raw=PRIVATE_MARKER+'\n'+s['private_raw']
    data=dict(schema_version=2,finding_sequence=60,
        meta=dict(lang=language,theme='corporativo',report_density='compact',report_title=m['report_title'],report_subtitle=m['report_subtitle'],client=m['client'],
            assessor=m['assessor'],assessor_title=m['assessor_title'],date=DATE,version='ATLAS 1.0',
            branding=dict(wordmark=m['wordmark'],byline=m['byline'],confidential_text=m['confidential_text'],accent='#225e83',logo='img/logo.png',cover_image='img/cover.png'),
            contacts=dict(client=[dict(name=m['client_contact'],title=m['client_contact_title'],email='technology@atlas.example'),dict(name=m['operations_contact'],title=m['operations_contact_title'],email='operations@atlas.example')],assessor=[dict(name=m['assessor_contact'],title=m['assessor_contact_title'],email='review@atlas.example')]),
            scope=[dict(target=a['host'],description=a['name']+' / '+a['ip']+' / '+s['fictional']) for a in content['assets']]),
        report=dict(sections=sections(content),workflow=dict(include_assets=True,include_coverage=True,include_retest=True,include_root_causes=True)),
        findings=findings(content)+machines(content),
        assets=[dict(uid=uid('asset-'+str(n)),name=a['name'],target=a['host']+' / '+a['ip'],kind=a['kind'],notes=a['owner']+'; '+s['asset_note']) for n,a in enumerate(content['assets'])],
        evidence=[dict(uid=uid('evidence-'+str(n)),title=f'ATLAS-E{n:02d} / '+s['evidence_title'],src=f'img/evidence-{n:02d}.png',caption=f'ATLAS-E{n:02d} — '+s['evidence_caption']) for n in range(1,85)],
        coverage=[dict(uid=uid(f'coverage-{n}-{suffix}'),asset_uid=uid('asset-'+str(spec['asset'])),test=f'ATLAS-{n:02d}-{suffix} / '+label,status=state,notes=s['coverage_notes']) for n,spec in enumerate(content['findings'],1) for suffix,label,state in [('P',s['coverage_allowed'],'done'),('N',s['coverage_rejected'],('done','pending','blocked','not_applicable')[(n-1)%4]),('R',s['coverage_recovery'],('done','pending')[(n-1)%2])]],
        root_cause_groups=[dict(uid=uid('root-'+str(n)),name=g['name'],cause_md=g['cause']+' '+s['root_note'],remediation_md=g['action']) for n,g in enumerate(content['root_groups'])],
        limitations_md=s['warning']+' '+s['limitations'],publication=dict(redactions=[dict(needle=REDACTION_MARKER,replacement=s['redaction_replacement'])],exceptions=[]),
        capture_inbox=[dict(uid=uid('private-note'),kind='note',title=s['private_title'],raw_text=raw,note=s['private_note'],created=DATE+'T12:00:00Z',sha256=sha256(raw.encode()).hexdigest())],
        project_management=dict(archived=False,delivery_date='2026-12-15'))
    data['evidence'][0]['original']='originals/evidence-01.png'
    return data


def add_annexes(directory,data,content):
    s=content['strings'];language=data['meta']['lang']
    manifest=dict(schema='report-gen-atlas-case/1',case=CASE,date=DATE,fictional=True,vulnerabilities=60,machines=7,assets=28,evidence_images=84,coverage_rows=180,root_cause_groups=10,source_sections=23,
        severity_counts=dict(Counter(f['severity'] for f in data['findings'] if f['mode']=='vuln')),prose_language=language,presentation_language=language)
    controls=[[f'ATLAS-{n:02d}-{suffix}',f'F{n:02d}',label,s['annex_simulated']] for n in range(1,61) for suffix,label in [('P',s['allowed']),('N',s['rejected']),('R',s['recovery'])]]
    contents=[csv_bytes(s['annex_asset_headers'],[[a[k] for k in ('name','host','ip','kind','owner')] for a in content['assets']]),
        csv_bytes(s['annex_control_headers'],controls),json_bytes(manifest),s['annex_acceptance'],PRIVATE_MARKER+'\n'+s['annex_private']+'\n',
        csv_bytes(s['annex_retention_headers'],s['annex_retention_rows']),s['annex_dependencies']]
    data['attachments']=[]
    for n,(name,blob) in enumerate(zip(s['annex_names'],contents)):
        blob=blob if isinstance(blob,bytes) else blob.encode()
        member='attachments/'+uuid.UUID(uid('annex-'+str(n))).hex+Path(name).suffix
        write(directory/member,blob)
        included=n!=4
        data['attachments'].append(dict(uid=uid('annex-'+str(n)),name=name,member=member,sha256=sha256(blob).hexdigest(),include=included,reviewed=included,required=included))


def import_inputs(directory):
    """Five inert independent scanner fixtures, validated by the actual importers."""
    directory.mkdir(parents=True)
    burp='''<?xml version="1.0" encoding="UTF-8"?><issues burpVersion="synthetic"><issue><serialNumber>ATLAS-BURP-01</serialNumber><name>Third-party mandate [SIMULATED]</name><host>https://terceros.atlas.example</host><path>/document</path><severity>Information</severity><confidence>Tentative</confidence><issueBackground>Fabricated input; no scan.</issueBackground><issueDetail>Documentary mandate contract.</issueDetail><remediationBackground>Fictional review.</remediationBackground><references><![CDATA[<a href="https://docs.atlas.example/import/burp#revisión">Synthetic reference</a>]]></references><requestresponse><request>GET /document HTTP/1.1
Host: terceros.atlas.example
X-Synthetic: true</request><response>HTTP/1.1 200 OK

SYNTHETIC_ONLY</response></requestresponse></issue></issues>'''
    nuclei={'template-id':'atlas-synthetic-contract','matched-at':'https://open-finance.atlas.example/contract','type':'http','timestamp':DATE+'T12:00:00Z','matcher-status':True,
        'info':dict(name='Consent contract [SIMULATED]',severity='info',description='Fabricated result; no scanner was executed.',remediation='Review the fictional contract.',reference=['https://docs.atlas.example/import/nuclei']),'extracted-results':['ATLAS_SYNTHETIC_NUCLEI']}
    nmap='''<?xml version="1.0" encoding="UTF-8"?><nmaprun scanner="nmap" version="synthetic"><host><status state="up" reason="user-set"/><address addr="192.0.2.90" addrtype="ipv4"/><hostnames><hostname name="inventario.atlas.example" type="user"/></hostnames><ports><port protocol="tcp" portid="443"><state state="open" reason="synthetic"/><service name="https" product="Synthetic gateway" version="1.0" method="table" conf="3"/></port><port protocol="tcp" portid="8443"><state state="closed" reason="synthetic"/><service name="https-alt" method="table" conf="3"/></port></ports></host><runstats><finished elapsed="1.00" exit="success"/><hosts up="1" down="0" total="1"/></runstats></nmaprun>'''
    sarif=dict(version='2.1.0',runs=[dict(tool=dict(driver=dict(name='Atlas synthetic scanner',version='1.0',rules=[dict(id='ATLAS-CONTRACT',name='ContractIdentity',shortDescription=dict(text='Fictional identity contract'))])),results=[dict(ruleId='ATLAS-CONTRACT',ruleIndex=0,level='note',message=dict(text='Fabricated result, not a scan.'),locations=[dict(physicalLocation=dict(artifactLocation=dict(uri='https://code.atlas.example/contract.py'),region=dict(startLine=17,startColumn=3)))],partialFingerprints={'primaryLocationLineHash':'atlas-synthetic-contract'})])])
    csv_input=csv_bytes(['title','severity','affected','description_md','impact_md','remediation_md','external_id'],[['Obligation contract [SIMULATED]','low','https://pagos.atlas.example/csv','Text with comma, revisão and synthetic\nline break.','No real exposure.','Review contract.','ATLAS-CSV-01'],['Obligation contract [SIMULATED]','low','https://pagos.atlas.example/csv','Deliberate duplicate identity.','No real exposure.','Review contract.','ATLAS-CSV-DUP']])
    entries=[('findings.csv','csv',csv_input),('burp.xml','burp',burp.encode()),('nuclei.jsonl','nuclei',(json.dumps(nuclei,ensure_ascii=False)+'\n').encode()),('nmap.xml','nmap',nmap.encode()),('sarif.json','sarif',json_bytes(sarif))]
    result={}
    for name,kind,blob in entries:
        write(directory/name,blob)
        preview=finding_imports.preview(dict(format=kind,text=blob.decode()),dict(meta=dict(lang='en'),findings=[],assets=[],coverage=[]))
        if any(row.get('errors') for row in preview['rows']):raise ValueError('Invalid scanner fixture: '+name)
        result[name]=dict(format=kind,counts=preview['counts'],sha256=sha256(blob).hexdigest())
    return result


def build_case(output,languages=('es','en','pt')):
    output=Path(output).resolve();languages=tuple(languages)
    if output.exists():raise FileExistsError('Output already exists: '+str(output))
    if not languages or len(set(languages))!=len(languages) or any(x not in ('es','en','pt') for x in languages):raise ValueError('Choose unique languages from es, en, pt')
    # Fail before creating the target if a translation is still incomplete.
    localized={language:load_content(language) for language in languages}
    output.mkdir(parents=True)
    projects={}
    for language,content in localized.items():
        project=output/'projects'/language
        (project/'img').mkdir(parents=True)
        for n in range(1,85):evidence_image(project/'img'/f'evidence-{n:02d}.png',n,content)
        branding(project/'img',content)
        write(project/'originals/evidence-01.png',(project/'img/evidence-01.png').read_bytes())
        write(project/'private/unlinked.txt',UNLINKED_MARKER+'\n'+content['strings']['private_unlinked']+'\n')
        data=make_project(language)
        add_annexes(project,data,content)
        validate.require_valid(data,final=True)
        if workflows.structure_errors(data):raise ValueError(workflows.structure_errors(data))
        capture_inbox.validate_rows(data['capture_inbox'])
        inventory=attachments.inventory(data,project)
        if any(item['status'] not in ('included','excluded') for item in inventory):raise ValueError('Invalid annex inventory')
        write(project/'engagement.yaml',yaml.safe_dump(data,allow_unicode=True,sort_keys=False,width=110))
        if engine.load_engagement(project/'engagement.yaml')!=data:raise ValueError('YAML roundtrip altered the fixture')
        issues=workflows.preflight(data,project,language)
        if any(issue['level']=='error' for issue in issues):raise ValueError(issues)
        projects[language]=dict(project='projects/'+language,vulnerabilities=60,machines=7,assets=len(data['assets']),evidence=len(data['evidence']),coverage=len(data['coverage']),sections=len(data['report']['sections']),root_cause_groups=len(data['root_cause_groups']),retest_records=sum(len(f.get('retests',[])) for f in data['findings']),severity_counts=engine.severity_counts(data['findings']),source_bytes=(project/'engagement.yaml').stat().st_size,annexes=[dict(name=a['name'],status=a['status'],bytes=a['bytes']) for a in inventory],validation_errors=0,validation_warnings=validate.validate(data),preflight_issues=issues)
    imports=import_inputs(output/'inputs')
    files={path.relative_to(output).as_posix():dict(bytes=path.stat().st_size,sha256=sha256(path.read_bytes()).hexdigest()) for path in sorted(output.rglob('*')) if path.is_file()}
    manifest=dict(schema='report-gen-atlas-source/1',case=CASE,date=DATE,fictional=True,source_generator='scripts/build-atlas-case.py',prose_languages=list(languages),variants_note='Complete authored narrative, images, captions and annexes are localized; technical identifiers and interoperability literals remain stable.',network_to_scenario_targets=False,reports_generated_by_builder=False,projects=projects,import_previews=imports,content_sha256={language:sha256((CONTENT/(language+'.json')).read_bytes()).hexdigest() for language in languages},files=files)
    write(output/'manifest.json',json_bytes(manifest))
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--languages',nargs='+',choices=('es','en','pt'),default=['es','en','pt'])
    args=parser.parse_args()
    result=build_case(args.output,args.languages)
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False,indent=2))
