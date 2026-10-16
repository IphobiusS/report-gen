#!/usr/bin/env python3
"""Generate Meridiano solely through native report-gen exporters and inspectors.

Twelve complete outputs plus targeted style samples avoid presenting repeated
small extracts as complete reports. Reuses the established export/check code.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import delivery
import design_library
import engine
from report_designs import THEMES
from version import __version__
from wizard import dump_yaml


def helpers():
    spec = importlib.util.spec_from_file_location('meridiano_shared_exports', ROOT / 'scripts/audit-horizonte-exports.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projects', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--mode', choices=('principal', 'styles', 'all', 'native'), default='principal')
    parser.add_argument('--native-executable')
    parser.add_argument('--require-stable', action='store_true')
    args = parser.parse_args()
    if (args.require_stable or args.mode == 'native') and not args.native_executable:
        parser.error('Native inspection requires --native-executable')
    source, out = args.projects.resolve(), args.output.resolve()
    if out == source or out.is_relative_to(source):
        parser.error('Output must remain outside the immutable source')
    shared = helpers()
    out.mkdir(parents=True, exist_ok=True)
    receipt_path = out / ('matrix-' + args.mode + '.json')
    if receipt_path.exists():
        parser.error('Preserve existing receipts; choose a fresh output directory')
    before, producer = shared.hashes(source), shared.producer_identity()
    receipt = dict(schema='report-gen-meridiano-exports/1', case='MERIDIANO-LOGISTICA-2026', version=__version__,
                   mode=args.mode, created_utc=datetime.now(timezone.utc).isoformat(), producer=producer,
                   generation='report-gen delivery.build and export.export only', inspection='delivery.inspect_export',
                   visual_review='not_performed_by_this_runner', microsoft_word='not_run', jobs=[],
                   harnesses={p.name: sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), ROOT / 'scripts/audit-horizonte-exports.py']})

    def record():
        shared.write_json(receipt_path, receipt)

    def invariant():
        if shared.producer_identity() != producer:
            receipt['status'] = 'failed'
            receipt['errors'] = ['Production code changed during execution; preserve this run and use a fresh process/output.']
            record()
            raise ValueError(receipt['errors'][0])

    def run(key, project, formats, full=False):
        invariant()
        job = shared.export_job(project, out / key, formats, complete_delivery=full,
                                case_title='Grupo Meridiano Logística — escenario ficticio')
        job.update(key=key, document_scope='complete_case' if full else 'targeted_excerpt')
        receipt['jobs'].append(job)
        record()
        if job['status'] != 'passed':
            raise ValueError('Native export or fidelity check failed: ' + key)

    def variant(key, data):
        project = out / 'variant-sources' / key
        shutil.copytree(source / 'es', project)
        dump_yaml(data, project / 'engagement.yaml')
        shared.write_json(out / 'variant-origins' / (key + '.json'),
                          dict(base_revision=shared.identity(shared.hashes(source / 'es')),
                               source_sha256=shared.hashes(project)))
        return project

    try:
        if args.mode in ('principal', 'all'):
            for language in ('es', 'en', 'pt'):
                data = engine.load_engagement(source / language / 'engagement.yaml')
                if (data['meta'].get('version') != 'GML 1.0' or data['meta'].get('theme') != 'corporativo'
                        or data['meta'].get('design') or len(data['findings']) != 34):
                    raise ValueError('The principal matrix requires the complete, original Meridiano fixture')
                run('principal/' + language, source / language, delivery.FORMATS, True)
        if args.mode in ('styles', 'all'):
            data = engine.load_engagement(source / 'es/engagement.yaml')
            excerpt, plan = shared.technical_excerpt(data, source / 'es')
            receipt['style_excerpt'] = plan
            receipt['style_rationale'] = ('F01 + F12 + M01 exercise conventional findings, linked/adjacent figures in table cells, '
                                         'and machine phases; all five other general layouts and two structurally distinct '
                                         'specialized profiles in both visual variants. This is not every catalog profile.')
            for theme in sorted(THEMES - {'corporativo'}):
                document = deepcopy(excerpt)
                document['meta'].pop('design', None)
                document['meta']['theme'] = theme
                key = 'general/' + theme
                run(key, variant(key, document), delivery.FORMATS)
            selected = ('enterprise-control-review', 'htb-cpts')
            catalog = {p['id']: p for p in design_library.catalog()['profiles']}
            for profile_id in selected:
                for appearance in design_library.VARIANTS:
                    key = 'specialized/' + profile_id + '/' + appearance
                    document = design_library.apply(deepcopy(excerpt), catalog[profile_id], appearance)
                    run(key, variant(key, document), ('pdf', 'docx'))
        if args.native_executable:
            for language in ('es', 'en', 'pt'):
                invariant()
                row = shared.native_checks(source / language, out / 'principal' / language / 'outputs',
                                           out / 'native' / language, args.native_executable, args.require_stable)
                row.update(key='native/' + language, document_scope='complete_case_native_inspection')
                receipt['jobs'].append(row)
                record()
                if row['status'] != 'passed':
                    raise ValueError('Native inspection failed: ' + language)
    except Exception as exc:
        receipt.setdefault('errors', []).append(f'{type(exc).__name__}: {exc}')
    receipt['source_bytes_unchanged'] = shared.hashes(source) == before
    receipt['producer_bytes_unchanged'] = shared.producer_identity() == producer
    receipt['requested_formats'] = sum(len(row.get('formats', [])) for row in receipt['jobs'])
    receipt['exported_formats'] = sum(len(row.get('formats', [])) for row in receipt['jobs'] if row.get('status') == 'passed')
    receipt['complete_case_formats'] = sum(len(row.get('formats', [])) for row in receipt['jobs'] if row.get('document_scope') == 'complete_case' and row.get('status') == 'passed')
    receipt['excerpt_formats'] = receipt['exported_formats'] - receipt['complete_case_formats']
    receipt['status'] = ('passed' if receipt['jobs'] and not receipt.get('errors') and receipt['source_bytes_unchanged']
                         and receipt['producer_bytes_unchanged'] and all(row['status'] == 'passed' for row in receipt['jobs']) else 'failed')
    shared.write_json(out / ('source-sha256-' + args.mode + '.json'), before)
    record()
    print(json.dumps({key: receipt[key] for key in ('status', 'exported_formats', 'complete_case_formats', 'excerpt_formats')}, ensure_ascii=False))
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
