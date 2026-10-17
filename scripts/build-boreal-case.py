#!/usr/bin/env python3
"""Author deterministic Boreal input projects; never generate report documents.

Seventy-two fictional observations across twelve energy/operations domains.
All narrative, synthetic evidence and annexes are localized in ES/EN/pt-BR.
Only the report-gen acceptance runner may produce the actual reports.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import importlib.util
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
from PIL import Image, ImageDraw, PngImagePlugin

CASE = 'BOREAL-REDES-ENERGIA-2026'
DATE = '2026-10-17'
CONTENT = ROOT / 'scripts/boreal-case-content'
NAMESPACE = uuid.UUID('db0844ae-2cf9-57bc-b1ea-891e5badce80')
LANGUAGES = ('es', 'en', 'pt')
PRIVATE_MARKER = 'BOREAL_PRIVATE_INBOX_DO_NOT_PUBLISH_2026'
METADATA_MARKER = 'BOREAL_PRIVATE_IMAGE_METADATA_2026'
REDACTION_MARKER = 'BOREAL_SYNTHETIC_REDACTION_CANARY_2026'
LONG_URL = ('https://docs.boreal.example/operation/reopening-and-revision-reconciliation/'
            'version-2026-10-17/record-0123456789abcdef0123456789abcdef0123456789abcdef'
            '?contract=BOREAL%2D42&unit=MWh&language=pt-BR#revisão-açaí-ñ')
# Deliberately exercise several authoring fields, retaining all table rows.
LONG_TABLES = (
    dict(finding='F01', field='description_md', rows=120),
    dict(finding='F14', field='walkthrough', rows=108),
    dict(finding='F27', field='impact_md', rows=96),
    dict(finding='F40', field='remediation_md', rows=90),
    dict(finding='F53', field='walkthrough', rows=84),
    dict(finding='F66', field='description_md', rows=80),
)


def shared_helpers():
    """Reuse input-only image/table primitives, not an existing case narrative."""
    spec = importlib.util.spec_from_file_location('boreal_input_primitives', ROOT / 'scripts/build-atlas-case.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SHARED = shared_helpers()
table, csv_bytes, json_bytes, write = SHARED.table, SHARED.csv_bytes, SHARED.json_bytes, SHARED.write


def uid(value):
    return str(uuid.uuid5(NAMESPACE, value))


def load_content(language):
    if language not in LANGUAGES:
        raise ValueError('Unsupported Boreal language: ' + language)
    content = json.loads((CONTENT / (language + '.json')).read_text(encoding='utf-8'))
    if (content.get('language') != language or len(content.get('domains', [])) != 12
            or len(content.get('controls', [])) != 6 or not content.get('strings')):
        raise ValueError('Incomplete localized Boreal content: ' + language)
    for row in content['domains']:
        if any(not row.get(k) for k in ('name', 'process', 'owner')):
            raise ValueError('Incomplete Boreal domain: ' + language)
    for row in content['controls']:
        if any(not row.get(k) for k in ('title', 'severity', 'cwe', 'condition', 'impact', 'remediation', 'root')):
            raise ValueError('Incomplete Boreal control: ' + language)
    return content


def assets(content):
    s = content['strings']
    return [dict(uid=uid(f'asset-{d * 3 + r}'), name=domain['name'] + ' / ' + s['asset_roles'][r],
                 host=f'd{d + 1:02d}-r{r + 1}.boreal.example', ip=f'{("192.0.2", "198.51.100", "203.0.113")[r]}.{d + 20}',
                 owner=domain['owner'], kind=('application', 'service', 'database')[r])
            for d, domain in enumerate(content['domains']) for r in range(3)]


def long_table(content, spec, number):
    s = content['strings']
    token = f'BRL-T{number:02d}'
    rows = [[f'{token}-R{n:03d}', f'D{(n - 1) % 12 + 1:02d} / BOREAL-R{n % 3 + 1}',
             s['row_template'].format(n=n) + (' ação / revisión / São Paulo / ñ / A&B' if n % 13 == 0 else ''),
             s['row_result']] for n in range(1, spec['rows'] + 1)]
    # Preserve one long URI inside a real cell, not merely a nearby paragraph.
    rows[spec['rows'] // 2][2] += ' [' + token + '-URL](' + LONG_URL + ')'
    return s['table_intro'] + '\n\n' + table(s['headers'], rows) + '\n\n' + s['table_outro']


def findings(content):
    s, asset_rows = content['strings'], assets(content)
    results = []
    for d, domain in enumerate(content['domains']):
        for c, control in enumerate(content['controls']):
            n = d * 6 + c + 1
            asset_index = d * 3 + c % 3
            asset = asset_rows[asset_index]
            values = dict(domain=domain['name'], process=domain['process'], host=asset['host'], **control)
            vector = SHARED.VECTORS[control['severity']]
            # Both supported scoring families appear without changing severity.
            if n == 25:
                vector = SHARED.V4[25]
            if n == 30:
                vector = SHARED.V4[30]
            rating = cvss.score(vector)
            if rating['severity'] != control['severity']:
                raise ValueError('Scenario severity mismatch: ' + str(n))
            status = ('open', 'in_progress', 'reported_fixed', 'verified_fixed', 'accepted', 'not_verified')[c]
            row = dict(id=f'F{n:02d}', uid=uid(f'F{n:02d}'), mode='vuln',
                       title=control['title'] + ' / ' + domain['name'] + ' ' + s['simulated'],
                       severity=control['severity'], cvss=rating['score'], cvss_vector=vector,
                       cvss_version=vector.split('/')[0].split(':')[1], cwe=control['cwe'],
                       description_md=s['description_template'].format(**values),
                       impact_md=s['impact_template'].format(**values),
                       remediation_md=s['remediation_template'].format(**values),
                       affected='https://' + asset['host'] + '/scenario/' + f'f{n:02d}',
                       owner=asset['owner'] + ' / ' + s['role'], due_date=f'2026-11-{(n - 1) % 28 + 1:02d}',
                       status=status, verification='inconclusive' if status == 'not_verified' else 'confirmed',
                       asset_uids=[asset['uid']], evidence_uids=[uid(f'evidence-{n}')],
                       root_cause_uid=uid(f'root-{c}'), closure_criteria_md=s['closure'],
                       walkthrough=[dict(lead='BOREAL / ' + f'F{n:02d}', text_md=s['scenario_template'].format(**values)),
                                    dict(lead=s['evidence'], text_md=table(s['contract_headers'], zip(s['paths'], s['contract_values'], s['contract_results'])))],
                       references=['https://docs.boreal.example/controls/' + f'f{n:02d}' + '#revision'])
            if n <= 12:
                row['evidence_uids'].append(uid(f'evidence-{72 + n}'))
            if n % 3 == 1:
                row['walkthrough'].append(dict(lead=s['image_labels'][3], command=f'CASE={CASE}\nFINDING=F{n:02d}\nREVISION=BOREAL-R3\nMODEL_ONLY=true\nNETWORK_EXECUTION=NONE'))
            if status in ('reported_fixed', 'accepted'):
                row['reported_remediation'] = s['reported']
            if n % 2 == 0:
                row['retests'] = [dict(uid=uid(f'retest-{n}'), tested_on='2026-10-16', assessor=s['team'],
                                      result='fixed' if status == 'verified_fixed' else ('open', 'partial', 'not_verified')[(n // 2) % 3],
                                      notes_md=s['retest'], evidence_uids=[uid(f'evidence-{n}')])]
            if n == 12:
                row['walkthrough'].append(dict(lead=s['evidence'], text_md=table(s['contract_headers'][:2], [
                    [s['evidence'], '[![' + s['evidence'] + '](img/evidence-12.png)](https://docs.boreal.example/figures#e12)'],
                    [s['evidence'], '![' + s['evidence'] + '](img/evidence-73.png)![' + s['evidence'] + '](img/evidence-74.png)']])))
            if n == 42:
                row['references'].append(LONG_URL)
            if n == 50:
                row['description_md'] += '\n\n' + REDACTION_MARKER
            results.append(row)
    for number, spec in enumerate(LONG_TABLES, 1):
        row = next(f for f in results if f['id'] == spec['finding'])
        rendered = long_table(content, spec, number)
        if spec['field'] == 'walkthrough':
            row['walkthrough'].append(dict(lead=f'BRL-T{number:02d}', text_md=rendered))
        else:
            row[spec['field']] += '\n\n' + rendered
    return results


def machine_notebooks(content):
    s, asset_rows = content['strings'], assets(content)
    result = []
    for n in range(1, 7):
        asset = asset_rows[(n - 1) * 3]
        result.append(dict(id=f'M{n:02d}', uid=uid(f'M{n:02d}'), mode='machine',
                           title=asset['name'] + ' — ' + s['machine_title'],
                           host=dict(name=asset['host'], ip=asset['ip'], os='Synthetic OS / model only'),
                           open_ports='443/tcp open https [SYNTHETIC / MODEL ONLY]',
                           summary_md=s['fictional'] + '\n\n' + s['machine_summary'],
                           status='not_verified', verification='unverified', owner=asset['owner'] + ' / ' + s['role'],
                           asset_uids=[asset['uid']], evidence_uids=[uid(f'evidence-{(n - 1) * 6 + 1}')],
                           phases=[dict(name=title, steps=[dict(lead=f'M{n:02d}.{k}', text_md=text,
                                   command=f'MODEL_ONLY=true\nMACHINE=M{n:02d}\nPHASE={k}\nNETWORK_EXECUTION=NONE')])
                                   for k, (title, text) in enumerate(zip(s['phases'], s['phase_text']), 1)],
                           proof=[dict(name=f'model-M{n:02d}.txt', value=f'BOREAL_SYNTHETIC_PROOF_{n}', notes=s['proof'])]))
    return result


def sections(content):
    s = content['strings']
    controls = [[f'BRL-{n:02d}-{suffix}', f'[F{n:02d}](#F{n:02d})', label, s['simulated']]
                for n in range(1, 73) for suffix, label in zip(('P', 'N', 'R'), s['paths'])]
    rows = [dict(key='confidentiality', body=s['fictional'] + '\n\n' + s['limitation']),
            dict(key='document_control', version_history=[dict(version='BOREAL 1.0', date=DATE, author=s['team'], notes=s['version_notes'])], distribution=s['confidential']),
            dict(key='contacts'), dict(key='executive_summary', summary=s['summary'] + '\n\n' + s['boundary']),
            dict(key='risk_posture', posture=s['boundary']),
            dict(key='strategic_recommendations', recommendations='\n\n'.join(s[k] for k in ('short_term', 'medium_term', 'long_term'))),
            dict(key='scope', objectives=s['boundary'], assumptions=s['limitation']),
            dict(key='methodology', approach=s['limitation']), dict(key='findings'),
            dict(key='remediation_plan', overview=s['closure'], short_term=s['short_term'], medium_term=s['medium_term'], long_term=s['long_term'])]
    for key in ('governance', 'continuity', 'evidence'):
        rows.append(dict(key='boreal-' + key, title=s['sections'][key], body=s[{'governance': 'boundary', 'continuity': 'continuity', 'evidence': 'evidence_text'}[key]]))
    rows.extend([
        dict(key='boreal-contracts', title=s['sections']['contracts'], body=s['coverage_note'] + '\n\n' + table(s['control_headers'], controls)),
        dict(key='boreal-literals', title=s['sections']['literals'], body=s['literal_text'] + '\n\n[' + s['image_labels'][1] + '](' + LONG_URL + ')\n\n' + table(['ID', 'Literal'], [['UNICODE', 'acción / revisão / açaí / São Paulo / ñ / Überprüfung'], ['ESCAPES', 'A&B <demo> [test] %2D %3A']]) + '\n\n```text\nBOREAL_LITERAL_SENTINEL\nMODEL_ONLY=true\nNETWORK_EXECUTION=NONE\n```'),
        dict(key='boreal-annexes', title=s['sections']['annexes'], body=s['annex_text'])])
    return rows


def make_project(language):
    content = load_content(language)
    s, asset_rows = content['strings'], assets(content)
    raw = PRIVATE_MARKER + '\n' + s['private']
    doc = dict(schema_version=2, finding_sequence=72,
               meta=dict(lang=language, theme='corporativo', report_density='compact', report_title=s['title'], report_subtitle=s['subtitle'], client=s['name'],
                         assessor=s['team'], assessor_title=s['role'], date=DATE, version='BOREAL 1.0',
                         branding=dict(wordmark=s['name'], byline=s['byline'], confidential_text=s['confidential'], accent='#235e61', logo='img/logo.png', cover_image='img/cover.png'),
                         contacts=dict(client=[dict(name=s['role'], title=s['name'], email='operations@boreal.example')], assessor=[dict(name=s['team'], title=s['role'], email='review@boreal.example')]),
                         scope=[dict(target=a['host'], description=a['name'] + ' / ' + a['ip']) for a in asset_rows]),
               report=dict(sections=sections(content), workflow=dict(include_assets=True, include_coverage=True, include_retest=True, include_root_causes=True)),
               findings=findings(content) + machine_notebooks(content),
               assets=[dict(uid=a['uid'], name=a['name'], target=a['host'] + ' / ' + a['ip'], kind=a['kind'], notes=a['owner'] + '; ' + s['asset_note']) for a in asset_rows],
               evidence=[dict(uid=uid(f'evidence-{n}'), title=f'BOREAL-E{n:02d} / ' + s['evidence'], src=f'img/evidence-{n:02d}.png', caption=f'BOREAL-E{n:02d} — ' + s['evidence_caption']) for n in range(1, 85)],
               coverage=[dict(uid=uid(f'coverage-{n}-{suffix}'), asset_uid=asset_rows[((n-1)//6)*3 + ((n-1)%6)%3]['uid'],
                              test=f'BRL-{n:02d}-{suffix} / ' + label, status=state, notes=s['coverage_note'])
                         for n in range(1, 73) for suffix, label, state in zip(('P','N','R'), s['paths'], ('done', ('done','pending','blocked','not_applicable')[(n-1)%4], ('done','pending')[(n-1)%2]))],
               root_cause_groups=[dict(uid=uid(f'root-{n}'), name=c['root'], cause_md=c['condition'] + ' ' + s['root_note'], remediation_md=c['remediation']) for n,c in enumerate(content['controls'])],
               limitations_md=s['fictional'] + '\n\n' + s['limitation'],
               publication=dict(redactions=[dict(needle=REDACTION_MARKER, replacement=s['redacted'])], exceptions=[]),
               capture_inbox=[dict(uid=uid('private-note'), kind='note', title=s['private'], raw_text=raw, note=s['private'], created=DATE+'T12:00:00Z', sha256=sha256(raw.encode()).hexdigest())],
               project_management=dict(archived=False, delivery_date='2026-12-15'))
    doc['evidence'][0]['original'] = 'originals/evidence-01.png'
    return doc


def draw_assets(directory, content):
    s, asset_rows = content['strings'], assets(content)
    directory.mkdir(parents=True)
    for n in range(1, 85):
        source_n = n if n <= 72 else n - 72
        d, c = divmod(source_n - 1, 6)
        asset = asset_rows[d * 3 + c % 3]
        portrait = n in (6, 18, 31, 48, 73, 80)
        width, height = (820, 1040) if portrait else (1440, 660)
        img = Image.new('RGB', (width, height), '#edf3f1')
        draw = ImageDraw.Draw(img)
        draw.rectangle((0, 0, width, 76), fill='#17383c')
        SHARED.draw_wrapped(draw, f'BOREAL / E{n:02d} / ' + s['simulated'], (28, 24), width=width-56, size=24, fill='white')
        title = content['controls'][c]['title'] + ' / ' + content['domains'][d]['name']
        y = SHARED.draw_wrapped(draw, title, (28, 103), width=width-56, size=25) + 28
        values = [asset['host'], 'BOREAL-R3 / ' + f'F{source_n:02d}', s['image_decision'], s['image_execution']]
        for i, (label, value) in enumerate(zip(s['image_labels'], values)):
            row_height = 125 if portrait else 83
            draw.rounded_rectangle((24, y, width-24, y+row_height-5), radius=6, fill='white' if i % 2 == 0 else '#dce7e3')
            SHARED.draw_wrapped(draw, label, (40, y+10), width=width-80, size=16, fill='#426168')
            end = SHARED.draw_wrapped(draw, value, (40, y+38), width=width-80, size=19)
            if end > y+row_height:
                raise ValueError('Synthetic evidence row overflow: ' + str(n))
            y += row_height
        if y > height-70:
            raise ValueError('Synthetic evidence image overflow: ' + str(n))
        SHARED.draw_wrapped(draw, s['image_footer'], (28, height-50), width=width-56, size=15)
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text('Description', METADATA_MARKER)
        img.save(directory / f'evidence-{n:02d}.png', pnginfo=metadata)
    for name, height in (('logo', 210), ('cover', 380)):
        img = Image.new('RGB', (1440, height), '#17383c')
        draw = ImageDraw.Draw(img)
        draw.polygon([(38,160),(88,40),(140,160)], outline='#88ceb6', width=6)
        SHARED.draw_wrapped(draw, s['name'], (182, 42), width=1220, size=45, fill='white')
        SHARED.draw_wrapped(draw, s['byline'], (185, 118), width=1210, size=24, fill='#b8dbd0')
        if name == 'cover':
            SHARED.draw_wrapped(draw, s['fictional'], (42, 230), width=1356, size=23, fill='white')
        img.save(directory / (name + '.png'))


def add_annexes(directory, doc, content):
    s = content['strings']
    records = [[f'BRL-{n:02d}-{suffix}', f'F{n:02d}', label, s['simulated']] for n in range(1, 73) for suffix, label in zip(('P','N','R'), s['paths'])]
    payloads = [csv_bytes(s['annex_headers'], [[f'A{n:02d}', a['name'], a['target'], a['notes']] for n,a in enumerate(doc['assets'],1)]),
                csv_bytes(s['control_headers'], records), json_bytes(dict(case=CASE, fictional=True, prose_language=doc['meta']['lang'], vulnerabilities=72, machines=6, long_tables=list(LONG_TABLES))),
                s['annex_acceptance'].encode(), (PRIVATE_MARKER+'\n'+s['private']).encode(),
                csv_bytes(s['dependency_headers'], [[f'D{n:02d}-R1', f'D{n:02d}-R2', s['dependency']] for n in range(1,13)])]
    doc['attachments'] = []
    for n, (name, blob) in enumerate(zip(s['annex_names'], payloads)):
        member = 'attachments/' + uuid.UUID(uid(f'annex-{n}')).hex + Path(name).suffix
        write(directory/member, blob)
        doc['attachments'].append(dict(uid=uid(f'annex-{n}'), name=name, member=member, sha256=sha256(blob).hexdigest(), include=n!=4, reviewed=n!=4, required=n!=4))


def import_inputs(directory):
    """Reuse existing inert parser fixtures while assigning independent provenance."""
    previews = SHARED.import_inputs(directory)
    result = {}
    for name, record in previews.items():
        path = directory/name
        text = path.read_text().replace('ATLAS', 'BOREAL').replace('Atlas', 'Boreal').replace('atlas', 'boreal')
        write(path, text)
        preview = finding_imports.preview(dict(format=record['format'], text=text), dict(meta=dict(lang='en'), findings=[], assets=[], coverage=[]))
        if any(row.get('errors') for row in preview['rows']):
            raise ValueError('Invalid Boreal scanner fixture: ' + name)
        result[name] = dict(format=record['format'], counts=preview['counts'], sha256=sha256(path.read_bytes()).hexdigest(), prose_language='en', scope='inert_parser_input_not_report_narrative')
    return result


def build_case(output, languages=LANGUAGES):
    output, languages = Path(output).resolve(), tuple(languages)
    if output.exists():
        raise FileExistsError('Output already exists: ' + str(output))
    if not languages or len(set(languages)) != len(languages) or any(lang not in LANGUAGES for lang in languages):
        raise ValueError('Choose unique languages from es, en, pt')
    localized = {lang: load_content(lang) for lang in languages}
    output.mkdir(parents=True)
    projects = {}
    for lang, content in localized.items():
        project = output/'projects'/lang
        draw_assets(project/'img', content)
        write(project/'originals/evidence-01.png', (project/'img/evidence-01.png').read_bytes())
        write(project/'private/unlinked.txt', PRIVATE_MARKER+'\n'+content['strings']['private'])
        doc = make_project(lang)
        add_annexes(project, doc, content)
        validate.require_valid(doc, final=True)
        errors = workflows.structure_errors(doc)
        if errors:
            raise ValueError(errors)
        capture_inbox.validate_rows(doc['capture_inbox'])
        inventory = attachments.inventory(doc, project)
        if any(row['status'] not in ('included', 'excluded') for row in inventory):
            raise ValueError('Invalid Boreal annex inventory')
        write(project/'engagement.yaml', yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=110))
        if engine.load_engagement(project/'engagement.yaml') != doc:
            raise ValueError('Boreal YAML roundtrip changed authored content')
        issues = workflows.preflight(doc, project, lang)
        if any(row['level'] == 'error' for row in issues):
            raise ValueError(issues)
        projects[lang] = dict(project='projects/'+lang, vulnerabilities=72, machines=6, assets=36, evidence=84, coverage=216, root_cause_groups=6,
                              sections=len(doc['report']['sections']), retest_records=sum(len(f.get('retests', [])) for f in doc['findings']),
                              long_tables=[dict(spec, token=f'BRL-T{n:02d}', first=f'BRL-T{n:02d}-R001', last=f'BRL-T{n:02d}-R{spec["rows"]:03d}') for n,spec in enumerate(LONG_TABLES,1)],
                              severity_counts=dict(Counter(f['severity'] for f in doc['findings'] if f['mode']=='vuln')),
                              validation_errors=0, validation_warnings=validate.validate(doc), preflight_issues=issues)
    imports = import_inputs(output/'inputs')
    files = {p.relative_to(output).as_posix():dict(bytes=p.stat().st_size, sha256=sha256(p.read_bytes()).hexdigest()) for p in sorted(output.rglob('*')) if p.is_file()}
    manifest = dict(schema='report-gen-boreal-source/1', case=CASE, date=DATE, fictional=True,
                    source_generator='scripts/build-boreal-case.py', prose_languages=list(languages),
                    variants_note='All report prose, evidence images, captions and human annex text localized; identifiers and interoperability literals stable. Inert importer inputs are English and are not inserted into the reports.',
                    reports_generated_by_builder=False, network_to_scenario_targets=False, projects=projects, import_previews=imports,
                    content_sha256={lang:sha256((CONTENT/(lang+'.json')).read_bytes()).hexdigest() for lang in languages}, files=files)
    write(output/'manifest.json', json_bytes(manifest))
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--languages', nargs='+', choices=LANGUAGES, default=LANGUAGES)
    args = parser.parse_args()
    result = build_case(args.output, args.languages)
    print(json.dumps({key:value for key,value in result.items() if key != 'files'}, ensure_ascii=False, indent=2))
