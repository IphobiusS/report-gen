#!/usr/bin/env python3
"""Generate complete localized Boreal reports using report-gen alone and inspect them.

This bounded acceptance checks all authored long-table row identities, repeated
PDF/DOCX headers, source invariance and the native delivery verifier. It does not
claim visual review, Microsoft Word compatibility or every possible input.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import delivery
import engine
from export_formats import get as export_format
from version import __version__


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT/relative)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


BUILDER = module('boreal_fixture_for_acceptance', 'scripts/build-boreal-case.py')
SHARED = module('boreal_native_exports', 'scripts/audit-horizonte-exports.py')


def compact(value):
    return re.sub(r'\s+', '', value).replace('\u200b', '').replace('\u00ad', '')


def fixture_contract(doc, language):
    facts = dict(vulnerabilities=sum(f.get('mode') != 'machine' for f in doc['findings']),
                 machines=sum(f.get('mode') == 'machine' for f in doc['findings']),
                 assets=len(doc['assets']), evidence=len(doc['evidence']), coverage=len(doc['coverage']))
    expected = dict(vulnerabilities=72, machines=6, assets=36, evidence=84, coverage=216)
    if facts != expected or engine.report_language(doc) != language:
        raise ValueError('Boreal fixture contract mismatch: ' + json.dumps(facts))
    if {f['id'] for f in doc['findings']} != {f'F{n:02d}' for n in range(1,73)} | {f'M{n:02d}' for n in range(1,7)}:
        raise ValueError('Boreal finding identities changed')
    for n, spec in enumerate(BUILDER.LONG_TABLES, 1):
        finding = next(f for f in doc['findings'] if f['id'] == spec['finding'])
        field = json.dumps(finding.get(spec['field']), ensure_ascii=False)
        found = re.findall(fr'BRL-T{n:02d}-R\d{{3}}', field)
        wanted = [f'BRL-T{n:02d}-R{i:03d}' for i in range(1, spec['rows']+1)]
        if found != wanted:
            raise ValueError('Boreal table lost, reordered or duplicated an authored row: ' + spec['finding'])
    return dict(facts, long_tables=len(BUILDER.LONG_TABLES), long_table_rows=sum(s['rows'] for s in BUILDER.LONG_TABLES))


def inspect_long_tables(outputs, language, *, builder=BUILDER, token_prefix='BRL'):
    """Inspect actual generated outputs; fixture text alone never counts as export."""
    if not re.fullmatch(r'[A-Z][A-Z0-9]{1,15}', token_prefix):
        raise ValueError('Invalid long-table token prefix')
    import fitz
    from lxml import etree, html
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    pdf_path = outputs/'informe.pdf'
    with fitz.open(pdf_path) as pdf:
        pages = [compact(page.get_text()) for page in pdf]
    if not pages:
        raise ValueError('Boreal PDF is empty')
    with zipfile.ZipFile(outputs/'informe.docx') as archive:
        document = etree.fromstring(archive.read('word/document.xml'))
    docx_text = compact(''.join(document.xpath('//w:t/text()', namespaces=ns)))
    html_text = compact(html.fromstring((outputs/'informe.html').read_bytes()).text_content())
    with zipfile.ZipFile(outputs/export_format('md').filename) as archive:
        md_text = compact(archive.read('report.md').decode('utf-8'))
    headers = [compact(value) for value in builder.load_content(language)['strings']['headers']]
    tables = []
    for number, spec in enumerate(builder.LONG_TABLES, 1):
        tokens = [f'{token_prefix}-T{number:02d}-R{i:03d}' for i in range(1,spec['rows']+1)]
        row_pages = []
        for token in tokens:
            actual_pages = [i+1 for i,text in enumerate(pages) if token in text]
            if len(actual_pages) != 1 or sum(text.count(token) for text in pages) != 1:
                raise ValueError('PDF table row missing or duplicated: ' + token)
            row_pages.append(actual_pages[0])
            for label, text in (('DOCX',docx_text), ('HTML',html_text), ('Markdown',md_text)):
                if text.count(token) != 1:
                    raise ValueError(label + ' table row missing or duplicated: ' + token)
        if row_pages != sorted(row_pages) or len(set(row_pages)) < 2:
            raise ValueError('Long table does not flow in row order across pages: ' + spec['finding'])
        header_pages = [page for page in sorted(set(row_pages)) if all(header in pages[page-1] for header in headers)]
        if header_pages != sorted(set(row_pages)):
            raise ValueError('PDF continued table is missing a header: ' + spec['finding'])
        candidates = [tbl for tbl in document.xpath('//w:tbl', namespaces=ns)
                      if tokens[0] in compact(''.join(tbl.xpath('.//w:t/text()', namespaces=ns)))
                      and tokens[-1] in compact(''.join(tbl.xpath('.//w:t/text()', namespaces=ns)))]
        if not candidates:
            raise ValueError('DOCX long table was flattened or separated unexpectedly: ' + spec['finding'])
        selected = min(candidates, key=lambda tbl:len(etree.tostring(tbl)))
        if not selected.xpath('./w:tr[1]/w:trPr/w:tblHeader', namespaces=ns):
            raise ValueError('DOCX continued table does not repeat its header: ' + spec['finding'])
        direct_rows = selected.xpath('./w:tr', namespaces=ns)
        if len(direct_rows) != spec['rows']+1:
            raise ValueError('DOCX table row count differs from its authored contract: ' + spec['finding'])
        tables.append(dict(spec, token=f'{token_prefix}-T{number:02d}', pdf_pages=sorted(set(row_pages)),
                           repeated_header_pages=header_pages, row_occurrences_each_format=spec['rows'],
                           docx_header_repeat=True, docx_rows=len(direct_rows), passed=True))
    return dict(status='passed', pdf_pages=len(pages), tables=tables,
                scope='Exact row presence/order and repeated table headers; not a substitute for visual page review.',
                outputs={p.name:dict(bytes=p.stat().st_size,sha256=sha256(p.read_bytes()).hexdigest())
                         for p in (outputs/export_format(fmt).filename for fmt in delivery.FORMATS)})


def main(*, builder=BUILDER, case_key='boreal', contract=fixture_contract, token_prefix='BRL',
         extra_inspection=None, harness_paths=(), description=__doc__):
    """Shared immutable four-format acceptance orchestration; case hooks only inspect."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--projects', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--languages', nargs='+', choices=builder.LANGUAGES, default=builder.LANGUAGES)
    parser.add_argument('--mode', choices=('principal','native'), default='principal')
    parser.add_argument('--native-executable')
    parser.add_argument('--require-stable', action='store_true')
    args = parser.parse_args()
    source, out = args.projects.resolve(), args.output.resolve()
    if out == source or out.is_relative_to(source):
        parser.error('Output must remain outside the immutable source')
    if len(args.languages) != len(set(args.languages)):
        parser.error('Choose unique languages')
    if (args.mode == 'native' or args.require_stable) and not args.native_executable:
        parser.error('Native acceptance requires --native-executable')
    out.mkdir(parents=True, exist_ok=True)
    receipt_path = out/('matrix-'+args.mode+'.json')
    if receipt_path.exists():
        parser.error('Preserve earlier receipts; choose a fresh output or a different mode')
    before, producer = SHARED.hashes(source), SHARED.producer_identity()
    receipt = dict(schema='report-gen-'+case_key+'-acceptance/1', case=builder.CASE, version=__version__,
                   created_utc=datetime.now(timezone.utc).isoformat(), mode=args.mode, languages=args.languages,
                   generation='report-gen delivery.capture/build and registered exporters only',
                   inspection='delivery.inspect_export plus exact long-table row and header checks',
                   producer=producer, visual_review='not_performed_by_this_runner', microsoft_word='not_run',
                   complete_reports=0, sample_reports=0, jobs=[], errors=[],
                   harnesses={path.relative_to(ROOT).as_posix():sha256(path.read_bytes()).hexdigest()
                              for path in {Path(__file__).resolve(), ROOT/'scripts/build-boreal-case.py', ROOT/'scripts/audit-horizonte-exports.py', *harness_paths}})
    try:
        if args.mode == 'native':
            principal_path = out/'matrix-principal.json'
            prior = json.loads(principal_path.read_text(encoding='utf-8'))
            if (prior.get('status') != 'passed' or prior.get('producer') != producer
                    or not set(args.languages) <= set(prior.get('languages', []))):
                raise ValueError('Native review requires a passed principal matrix from the identical producer')
            original_sources = json.loads((out/'source-sha256-principal.json').read_text(encoding='utf-8'))
            if original_sources != before:
                raise ValueError('Native review source differs from its principal export')
            for prior_job in prior['jobs']:
                if prior_job.get('document_scope') != 'complete_case':
                    continue
                language = prior_job['key'].split('/')[-1]
                if language not in args.languages:
                    continue
                for filename, record in prior_job['long_table_checks']['outputs'].items():
                    path = out/'principal'/language/'outputs'/filename
                    if path.stat().st_size != record['bytes'] or sha256(path.read_bytes()).hexdigest() != record['sha256']:
                        raise ValueError('Native review output changed: ' + language + '/' + filename)
                for filename, record in prior_job.get('workflow_checks', {}).get('artifacts', {}).items():
                    path = out/'principal'/language/filename
                    if path.stat().st_size != record['bytes'] or sha256(path.read_bytes()).hexdigest() != record['sha256']:
                        raise ValueError('Native review workflow artifact changed: ' + language + '/' + filename)
            receipt['principal_receipt_sha256'] = sha256(principal_path.read_bytes()).hexdigest()
        for language in args.languages:
            if SHARED.producer_identity() != producer:
                raise ValueError('Production code changed during acceptance; preserve run and restart')
            project = source/language
            doc = engine.load_engagement(project/'engagement.yaml')
            receipt.setdefault('fixture_contracts', {})[language] = contract(doc, language)
            if args.mode == 'principal':
                row = SHARED.export_job(project, out/'principal'/language, delivery.FORMATS,
                                        complete_delivery=True, case_title=doc['meta']['report_title'])
                row.update(key='principal/'+language, document_scope='complete_case')
                receipt['jobs'].append(row)
                if row['status'] != 'passed':
                    raise ValueError(case_key+' native export failed: '+language)
                row['long_table_checks'] = inspect_long_tables(out/'principal'/language/'outputs', language, builder=builder, token_prefix=token_prefix)
                if extra_inspection is not None:
                    row['workflow_checks'] = extra_inspection(out/'principal'/language/'outputs', language, doc,
                                                               out/'principal'/language/'snapshot',
                                                               out/'principal'/language/'delivery.zip')
                receipt['complete_reports'] += len(delivery.FORMATS)
            if args.native_executable:
                row = SHARED.native_checks(project, out/'principal'/language/'outputs', out/'native'/language,
                                           args.native_executable, args.require_stable)
                row.update(key='native/'+language, document_scope='complete_case_native_inspection')
                receipt['jobs'].append(row)
                if row['status'] != 'passed':
                    raise ValueError(case_key+' native DOCX inspection failed: '+language)
            SHARED.write_json(receipt_path, receipt)
    except Exception as exc:
        receipt['errors'].append(type(exc).__name__+': '+str(exc))
    receipt['source_bytes_unchanged'] = SHARED.hashes(source) == before
    receipt['producer_bytes_unchanged'] = SHARED.producer_identity() == producer
    receipt['status'] = ('passed' if receipt['jobs'] and not receipt['errors']
                         and receipt['source_bytes_unchanged'] and receipt['producer_bytes_unchanged']
                         and all(row['status']=='passed' for row in receipt['jobs']) else 'failed')
    SHARED.write_json(out/('source-sha256-'+args.mode+'.json'), before)
    SHARED.write_json(receipt_path, receipt)
    print(json.dumps({key:receipt[key] for key in ('status','complete_reports','sample_reports','errors')}, ensure_ascii=False))
    return 0 if receipt['status']=='passed' else 1


if __name__ == '__main__':
    sys.exit(main())
