#!/usr/bin/env python3
"""Generate VEGA with report-gen and inspect all 90 catalog entries in 4 formats.

The acceptance preserves pending technical states. It verifies rendered content,
not a claim of security testing or human usability. Optional native DOCX checks
use the established LibreOffice verifier and never rewrite the delivered DOCX.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import re
import sys
import unicodedata
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import delivery
import engine
from export_formats import get as export_format
from knowledge import catalog
from version import __version__


def module(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


BUILDER = module('knowledge_fixture', 'scripts/build-knowledge-case.py')
SHARED = module('knowledge_exports', 'scripts/audit-horizonte-exports.py')


def compact(value):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', value)).replace('\u200b', '').replace('\u00ad', '')


def producer_identity():
    value = SHARED.producer_identity()
    extra = {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
             for path in sorted((ROOT / 'knowledge').rglob('*'))
             if path.is_file() and '__pycache__' not in path.parts}
    value['files'].update(extra)
    value['code_assets_sha256'] = SHARED.identity(value['files'])
    return value


def fixture_contract(doc, lang):
    findings = doc.get('findings', [])
    identities = {re.search(r'VEGA-ENTRY-(RG-[A-Z]+-\d{3})', row.get('description_md', '')).group(1)
                  for row in findings if re.search(r'VEGA-ENTRY-(RG-[A-Z]+-\d{3})', row.get('description_md', ''))}
    if len(findings) != 90 or identities != BUILDER.EXPECTED_IDS or engine.report_language(doc) != lang:
        raise ValueError('VEGA catalog/language contract mismatch')
    if any(row.get('verification') != 'unverified' or row.get('severity') is not None or row.get('cvss') is not None
           or row.get('cvss_vector') or row.get('status', 'open') != 'open' or row.get('retests') for row in findings):
        raise ValueError('A catalog hypothesis became a technical conclusion')
    tests, evidence, assets = doc.get('test_cases', []), doc.get('evidence', []), doc.get('assets', [])
    if len(tests) != 90 or any(row.get('status') != 'pending' or row.get('observed') or row.get('evidence_uids') for row in tests):
        raise ValueError('The proposed test plan was marked executed')
    if len(evidence) != 14 or len(assets) != 7 or len(doc.get('coverage', [])) != 7:
        raise ValueError('VEGA resource count mismatch')
    if any(row.get('status') != 'pending' for row in doc['coverage']):
        raise ValueError('Pending coverage changed')
    for row in evidence:
        if row.get('approved') or row.get('reviewed'):
            raise ValueError('Synthetic illustration was automatically approved')
    return dict(findings=90, ai_patterns=30, unverified=90, severity_pending=90, pending_tests=90,
                assets=7, synthetic_figures=14, pending_coverage=7, long_table_rows=180,
                catalog_categories=dict(Counter(item['category'] for item in BUILDER.entries(lang))))


def inspect_outputs(outputs, doc, lang):
    import fitz
    from lxml import etree, html
    from exporters.markdown import parse_exported
    with fitz.open(outputs / 'informe.pdf') as pdf:
        pages = [compact(page.get_text()) for page in pdf]
    with zipfile.ZipFile(outputs / 'informe.docx') as archive:
        document = etree.fromstring(archive.read('word/document.xml'))
    ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with zipfile.ZipFile(outputs / export_format('md').filename) as archive:
        markdown = parse_exported(archive.read('report.md').decode('utf-8'))
    texts = dict(pdf=''.join(pages), docx=compact(''.join(document.xpath('//w:t/text()', namespaces=ns))),
                 html=compact(html.fromstring((outputs / 'informe.html').read_bytes()).text_content()),
                 md=compact(markdown.text_content()))
    if len(pages) < 90:
        raise ValueError('VEGA did not exercise a genuinely long report')
    counts = {}
    for kind, text in texts.items():
        if compact(BUILDER.WARNING[lang]) not in text:
            raise ValueError(kind + ': fictional and pending status notice missing')
        for identity in sorted(BUILDER.EXPECTED_IDS):
            marker = 'VEGA-ENTRY-' + identity
            if text.count(marker) != 1:
                raise ValueError(kind + ': catalog body missing or duplicated: ' + identity)
            item = catalog.entry(identity, lang)
            if compact(item['title']) not in text:
                raise ValueError(kind + ': localized catalog title missing: ' + identity)
            finding = next(row for row in doc['findings'] if marker in row['description_md'])
            for field in ('description_md', 'impact_md', 'remediation_md', 'prerequisites', 'required_evidence', 'false_positives', 'retest', 'assessment_notes'):
                authored = item[field].replace('{{objetivo}}', finding['affected'])
                expected = compact(parse_exported(authored).text_content())
                if expected not in text:
                    raise ValueError(kind + ': catalog prose omitted or changed: ' + identity + '/' + field)
        counts[kind] = dict(entries=90, ai_entries=30, authored_fields_checked=720)
    tokens = [f'VEGA-ROW-{n:03d}-{suffix}' for n in range(1, 91) for suffix in ('POS', 'NEG')]
    row_pages = []
    for token in tokens:
        for kind, text in texts.items():
            if text.count(token) != 1:
                raise ValueError(kind + ': control row missing or duplicated: ' + token)
        row_pages.append(next(i + 1 for i, text in enumerate(pages) if token in text))
    if row_pages != sorted(row_pages) or len(set(row_pages)) < 2:
        raise ValueError('Control matrix failed ordered multi-page flow')
    table_pages = sorted(set(row_pages))
    if any(not all(compact(header) in pages[number - 1] for header in BUILDER.TABLE_HEADERS[lang]) for number in table_pages):
        raise ValueError('Continued PDF matrix lost a column header')
    candidates = [table for table in document.xpath('//w:tbl', namespaces=ns)
                  if tokens[0] in ''.join(table.xpath('.//w:t/text()', namespaces=ns))
                  and tokens[-1] in ''.join(table.xpath('.//w:t/text()', namespaces=ns))]
    if not candidates:
        raise ValueError('DOCX matrix is not a structural table')
    matrix = min(candidates, key=lambda table: len(etree.tostring(table)))
    if len(matrix.xpath('./w:tr', namespaces=ns)) != 181 or not matrix.xpath('./w:tr[1]/w:trPr/w:tblHeader', namespaces=ns):
        raise ValueError('DOCX matrix lost rows or continued-header semantics')
    return dict(status='passed', pdf_pages=len(pages), entry_checks=counts, long_table_rows=180,
                table_pdf_pages=table_pages, docx_rows=181, docx_header_repeat=True,
                outputs={path.name: dict(bytes=path.stat().st_size, sha256=sha256(path.read_bytes()).hexdigest())
                         for path in (outputs / export_format(fmt).filename for fmt in delivery.FORMATS)},
                visual_review='not_performed_by_this_runner', microsoft_word='not_run')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projects', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--languages', nargs='+', choices=BUILDER.LANGUAGES, default=BUILDER.LANGUAGES)
    parser.add_argument('--native-executable')
    parser.add_argument('--require-stable', action='store_true')
    args = parser.parse_args()
    source, out = args.projects.resolve(), args.output.resolve()
    if out == source or out.is_relative_to(source) or out.exists():
        parser.error('Use a fresh output directory outside immutable inputs')
    if len(args.languages) != len(set(args.languages)) or args.require_stable and not args.native_executable:
        parser.error('Choose unique languages; stable native checks require an executable')
    out.mkdir(parents=True)
    before, producer = SHARED.hashes(source), producer_identity()
    receipt = dict(schema='report-gen-knowledge-acceptance/1', version=__version__, case=BUILDER.CASE,
                   created_utc=datetime.now(timezone.utc).isoformat(), languages=args.languages, producer=producer,
                   generation='report-gen delivery.capture/build and registered exporters only',
                   security_tests_executed=False, complete_reports=0, jobs=[], errors=[],
                   visual_review='not_performed_by_this_runner', microsoft_word='not_run',
                   harnesses={name: sha256((ROOT / name).read_bytes()).hexdigest() for name in
                              ('scripts/build-knowledge-case.py', 'scripts/audit-knowledge-0440.py', 'scripts/audit-horizonte-exports.py')})
    receipt_path = out / 'matrix.json'
    try:
        for lang in args.languages:
            if producer_identity() != producer:
                raise ValueError('Production code/content changed during acceptance; restart after edits finish')
            project = source / lang
            doc = engine.load_engagement(project / 'engagement.yaml')
            contract = fixture_contract(doc, lang)
            row = SHARED.export_job(project, out / lang, delivery.FORMATS, complete_delivery=True,
                                    case_title=doc['meta']['report_title'])
            row.update(language=lang, fixture_contract=contract)
            receipt['jobs'].append(row)
            SHARED.write_json(receipt_path, receipt)
            if row['status'] != 'passed':
                raise ValueError('VEGA export failed: ' + lang)
            snapshot_doc = engine.load_engagement(out / lang / 'snapshot/engagement.yaml')
            row['pending_states_after_capture'] = fixture_contract(snapshot_doc, lang)
            row['catalog_checks'] = inspect_outputs(out / lang / 'outputs', doc, lang)
            receipt['complete_reports'] += 4
            if args.native_executable:
                row['native'] = SHARED.native_checks(project, out / lang / 'outputs', out / lang / 'native',
                                                     args.native_executable, args.require_stable)
                if row['native']['status'] != 'passed':
                    raise ValueError('VEGA native DOCX inspection failed: ' + lang)
            SHARED.write_json(receipt_path, receipt)
    except Exception as error:
        receipt['errors'].append(type(error).__name__ + ': ' + str(error))
    receipt['source_bytes_unchanged'] = SHARED.hashes(source) == before
    receipt['producer_bytes_unchanged'] = producer_identity() == producer
    receipt['status'] = 'passed' if (not receipt['errors'] and receipt['complete_reports'] == 4 * len(args.languages)
                                    and receipt['source_bytes_unchanged'] and receipt['producer_bytes_unchanged']) else 'failed'
    SHARED.write_json(out / 'source-sha256.json', before)
    SHARED.write_json(receipt_path, receipt)
    print(json.dumps({key: receipt[key] for key in ('status', 'complete_reports', 'errors')}, ensure_ascii=False), flush=True)
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
