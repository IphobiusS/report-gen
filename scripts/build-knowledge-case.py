#!/usr/bin/env python3
"""Prepare VEGA inputs through the bundled catalog; never render reports here.

Every finding remains an unverified, unrated hypothesis. Synthetic diagrams
illustrate the proposed laboratory, not successful security tests.
"""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import engine
from knowledge import catalog
import test_plans
import validate
import workflows
import yaml
from PIL import Image, ImageDraw, ImageFont

CASE = 'VEGA-KNOWLEDGE-LAB-2026'
LANGUAGES = ('es', 'en', 'pt')
CATEGORIES = ('web', 'api', 'identity', 'infrastructure', 'cloud', 'mobile', 'ai')
NAMESPACE = uuid.UUID('3f9dc971-cff3-55a5-bdad-df76aba839a4')
EXPECTED_IDS = {f'RG-{prefix}-{number:03d}' for prefix, count in
                [('WEB', 18), ('API', 12), ('ID', 8), ('INF', 8), ('CLD', 8), ('MOB', 6), ('AI', 30)]
                for number in range(1, count + 1)}
WARNING = {
    'es': 'VEGA es una empresa ficticia. Este documento contiene hipótesis pendientes, no vulnerabilidades demostradas. No se contactaron sistemas ni se ejecutaron pruebas de seguridad.',
    'en': 'VEGA is a fictional company. This document contains pending hypotheses, not demonstrated vulnerabilities. No systems were contacted and no security tests were executed.',
    'pt': 'VEGA é uma empresa fictícia. Este documento contém hipóteses pendentes, não vulnerabilidades demonstradas. Nenhum sistema foi contatado e nenhum teste de segurança foi executado.'}
TABLE_HEADERS = {'es': ['Control', 'ID', 'Catálogo', 'Estado', 'Contrato'],
                 'en': ['Control', 'ID', 'Catalog', 'Status', 'Contract'],
                 'pt': ['Controle', 'ID', 'Catálogo', 'Status', 'Contrato']}


def uid(label):
    return str(uuid.uuid5(NAMESPACE, label))


def tr(lang, es, en, pt):
    return (es, en, pt)[LANGUAGES.index(lang)]


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value if isinstance(value, bytes) else value.encode('utf-8'))


def table(headers, rows):
    def cell(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(map(cell, headers)) + ' |',
                      '| ' + ' | '.join('---' for _ in headers) + ' |',
                      *['| ' + ' | '.join(map(cell, row)) + ' |' for row in rows]])


def entries(lang):
    first = catalog.search(lang=lang, limit=24)
    rows = first['entries']
    for offset in range(24, first['total'], 24):
        rows += catalog.search(lang=lang, offset=offset, limit=24)['entries']
    if len(rows) != 90 or {row['id'] for row in rows} != EXPECTED_IDS:
        raise ValueError('VEGA requires exactly the agreed 90 stable catalog identities')
    return [catalog.entry(row['id'], lang) for row in sorted(rows, key=lambda row: row['id'])]


def diagrams(project, lang):
    """Plain labeled synthetic source images; report-gen performs all placement."""
    result = []
    font = ImageFont.truetype(str(ROOT / 'exporters/fonts/DejaVuSans.ttf'), 18)
    heading = ImageFont.truetype(str(ROOT / 'exporters/fonts/DejaVuSans.ttf'), 24)
    for n in range(1, 15):
        picture = Image.new('RGB', (1000, 430), '#10202c')
        draw = ImageDraw.Draw(picture)
        draw.text((32, 24), f'VEGA LAB / {lang.upper()} / {n:02d} / ' + tr(lang, 'MODELO SINTETICO', 'SYNTHETIC MODEL', 'MODELO SINTETICO'), fill='#bdebe5', font=heading)
        labels = tr(lang, ('IDENTIDAD DE PRUEBA', 'FRONTERA DE POLITICA', 'RECURSO RESERVADO'),
                    ('TEST IDENTITY', 'POLICY BOUNDARY', 'RESERVED RESOURCE'),
                    ('IDENTIDADE DE TESTE', 'LIMITE DA POLITICA', 'RECURSO RESERVADO'))
        for index, label in enumerate(labels):
            left = 32 + index * 325
            draw.rectangle((left, 112, left + 280, 250), outline='#4cbcae', width=3)
            draw.text((left + 15, 142), label, fill='white', font=font)
            if index < 2:
                draw.line((left + 280, 182, left + 325, 182), fill='#4cbcae', width=3)
        draw.text((32, 310), tr(lang, 'SIN RESULTADO OBSERVADO / SIN EJECUCION DE RED / SIN APROBACION',
                               'NO OBSERVED RESULT / NO NETWORK EXECUTION / NO APPROVAL',
                               'SEM RESULTADO OBSERVADO / SEM EXECUCAO DE REDE / SEM APROVACAO'), fill='#ffc980', font=font)
        target = project / 'img' / f'model-{n:02d}.png'
        target.parent.mkdir(parents=True, exist_ok=True)
        picture.save(target)
        result.append(dict(uid=uid(f'evidence-{n}'), title=f'VEGA-MODEL-{n:02d}',
                           src=f'img/model-{n:02d}.png', caption=WARNING[lang]))
    return result


def make_project(lang, project):
    rows = entries(lang)
    assets = [dict(uid=uid('asset-' + category), name='VEGA / ' + category,
                   target=f'https://{category}.vega.example', kind=category, notes=WARNING[lang])
              for category in CATEGORIES]
    evidence = diagrams(project, lang)
    findings, plans, matrix = [], [], []
    for n, item in enumerate(rows, 1):
        target = f'https://{item["category"]}.vega.example/lab/{item["id"]}'
        finding = catalog.instantiate(item['id'], {'objetivo': target}, lang)
        if finding.get('verification') != 'unverified' or finding.get('severity') is not None or finding.get('cvss') is not None:
            raise ValueError('Catalog insertion assigned a technical conclusion')
        finding.update(id=f'F{n:03d}', uid=uid(item['id']), asset_uids=[uid('asset-' + item['category'])],
                       evidence_uids=[evidence[(n - 1) % 14]['uid']], status='open',
                       closure_criteria_md=item['retest'])
        finding['description_md'] += '\n\n' + WARNING[lang] + f'\n\nVEGA-ENTRY-{item["id"]}'
        # These are proposed documentary steps, not promoted observed results.
        finding['walkthrough'] = [dict(lead=tr(lang, 'Preparación y evidencia necesaria', 'Preparation and required evidence', 'Preparação e evidências necessárias'),
                                      text_md=item['prerequisites'] + '\n\n' + item['required_evidence']),
                                  dict(lead=tr(lang, 'Descartar falsos positivos', 'Exclude false positives', 'Descartar falsos positivos'),
                                       text_md=item['false_positives'] + '\n\n' + item['assessment_notes'])]
        findings.append(finding)
        specialty = {'identity': 'ad', 'infrastructure': 'custom'}.get(item['category'], item['category'])
        plans.append(test_plans.create(dict(test_id='VEGA-TC-' + item['id'], title=item['title'],
                    specialty=specialty, methodology='report-gen curated knowledge', methodology_version='2026.10',
                    prerequisites=item['prerequisites'], expected=item['retest'], notes=WARNING[lang],
                    finding_uids=[finding['uid']], asset_uids=finding['asset_uids']), uid=uid('test-' + item['id'])))
        for suffix in ('POS', 'NEG'):
            matrix.append([f'VEGA-ROW-{n:03d}-{suffix}', f'[{finding["id"]}](#{finding["id"]})',
                           item['id'], tr(lang, 'Pendiente', 'Pending', 'Pendente'),
                           tr(lang, 'Control autorizado' if suffix == 'POS' else 'Rechazo esperado',
                              'Authorized control' if suffix == 'POS' else 'Expected denial',
                              'Controle autorizado' if suffix == 'POS' else 'Negação esperada')])
    sections = [
        dict(key='confidentiality', body=WARNING[lang]),
        dict(key='executive_summary', summary=WARNING[lang] + '\n\n' + tr(lang,
             'La empresa inventada opera servicios web, API, identidad, infraestructura, nube, móvil e IA. Las 90 fichas, incluidas 30 de IA, definen un programa documental de evaluación. Todas mantienen severidad pendiente y verificación sin realizar.',
             'The invented company operates web, API, identity, infrastructure, cloud, mobile and AI services. The 90 patterns, including 30 AI patterns, define a documentary assessment program. Every finding remains unrated and unverified.',
             'A empresa inventada opera serviços web, API, identidade, infraestrutura, nuvem, móvel e IA. As 90 fichas, incluindo 30 de IA, definem um programa documental de avaliação. Todos os achados permanecem sem severidade e não verificados.')),
        dict(key='scope', objectives=WARNING[lang], assumptions=tr(lang,
             'Los dominios .example son identificadores reservados. Los diagramas describen un laboratorio propuesto y no acreditan ejecución. No se evalúa una entidad bancaria real.',
             'The .example domains are reserved identifiers. Diagrams describe a proposed laboratory and do not prove execution. No real banking institution is assessed.',
             'Os domínios .example são identificadores reservados. Os diagramas descrevem um laboratório proposto e não comprovam execução. Nenhuma instituição bancária real é avaliada.')),
        dict(key='methodology', approach=tr(lang,
             'Seleccionar condiciones aplicables, preparar controles positivos y negativos, registrar evidencias y evaluar impacto antes de confirmar una hipótesis. Las referencias orientan la evaluación y no acreditan cumplimiento.',
             'Select applicable conditions, prepare positive and negative controls, preserve evidence and assess impact before confirming a hypothesis. References guide the assessment and do not attest compliance.',
             'Selecionar condições aplicáveis, preparar controles positivos e negativos, preservar evidências e avaliar impacto antes de confirmar uma hipótese. As referências orientam a avaliação e não comprovam conformidade.')),
        dict(key='findings_summary'), dict(key='findings'),
        dict(key='vega-control-matrix', title=tr(lang, 'Matriz de evaluación pendiente', 'Pending assessment matrix', 'Matriz de avaliação pendente'),
             body=WARNING[lang] + '\n\n' + table(TABLE_HEADERS[lang], matrix)),
    ]
    return dict(schema_version=2, finding_sequence=90,
                meta=dict(lang=lang, theme='corporativo', report_density='compact', report_title=tr(lang,
                          'VEGA — evaluación integral ficticia', 'VEGA — fictional comprehensive assessment', 'VEGA — avaliação abrangente fictícia'),
                          report_subtitle=tr(lang, '90 fichas / 30 de IA / ES-EN-PT', '90 patterns / 30 AI / ES-EN-PT', '90 fichas / 30 de IA / ES-EN-PT'),
                          client=tr(lang, 'VEGA [FICTICIA]', 'VEGA [FICTIONAL]', 'VEGA [FICTÍCIA]'),
                          assessor=tr(lang, 'Laboratorio sintético VEGA', 'VEGA synthetic laboratory', 'Laboratório sintético VEGA'), date='2026-10-17', version='VEGA 1.0',
                          scope=[dict(target=asset['target'], description=asset['name']) for asset in assets]),
                report=dict(sections=sections, workflow=dict(include_assets=True, include_coverage=True, include_retest=True)),
                findings=findings, assets=assets, evidence=evidence, test_cases=plans,
                coverage=[dict(uid=uid('coverage-' + category), asset_uid=uid('asset-' + category),
                               test='VEGA / ' + category, status='pending', notes=WARNING[lang]) for category in CATEGORIES],
                limitations_md=WARNING[lang])


def build_case(output, languages=LANGUAGES):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Preserve earlier inputs; choose a fresh output directory')
    if not languages or len(set(languages)) != len(languages) or any(lang not in LANGUAGES for lang in languages):
        raise ValueError('Choose unique languages from es, en, pt')
    output.mkdir(parents=True)
    projects = {}
    for lang in languages:
        project = output / 'projects' / lang
        doc = make_project(lang, project)
        validate.require_valid(doc, final=True)
        errors = workflows.structure_errors(doc)
        if errors:
            raise ValueError(errors)
        write(project / 'engagement.yaml', yaml.safe_dump(doc, allow_unicode=True, sort_keys=False, width=110))
        if engine.load_engagement(project / 'engagement.yaml') != doc:
            raise ValueError('VEGA YAML roundtrip changed source data')
        projects[lang] = dict(findings=90, ai_patterns=30, assets=7, synthetic_figures=14, pending_tests=90,
                              pending_coverage=7, long_table_rows=180,
                              categories=dict(Counter(item['category'] for item in entries(lang))),
                              validation_warnings=validate.validate(doc), preflight=workflows.preflight(doc, project, lang))
        if any(issue['level'] == 'error' for issue in projects[lang]['preflight']):
            raise ValueError('VEGA contains a preflight error')
    manifest = dict(schema='report-gen-knowledge-source/1', case=CASE, fictional=True, languages=list(languages),
                    generation='catalog.instantiate plus documentary input composition; no report rendering',
                    security_tests_executed=False, reports_generated_by_builder=False, projects=projects,
                    catalog={p.relative_to(ROOT).as_posix(): sha256(p.read_bytes()).hexdigest()
                             for p in sorted((ROOT / 'knowledge/data').glob('*.json'))},
                    files={p.relative_to(output).as_posix(): dict(bytes=p.stat().st_size, sha256=sha256(p.read_bytes()).hexdigest())
                           for p in sorted(output.rglob('*')) if p.is_file()})
    write(output / 'manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--languages', nargs='+', choices=LANGUAGES, default=LANGUAGES)
    args = parser.parse_args()
    result = build_case(args.output, args.languages)
    print(json.dumps({key: result[key] for key in ('case', 'fictional', 'languages', 'projects')}, ensure_ascii=False, indent=2))
