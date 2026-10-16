#!/usr/bin/env python3
"""Export the complete Atlas case and a catalog-derived, multilingual sample matrix.

Only report-gen's native snapshot, audience projection, export and verification
APIs produce reports. Full reports and excerpts are counted separately. The
selected combinations exercise every current catalog value without claiming
that every possible cross-product was tested.
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
from languages import LANGUAGES
from report_designs import THEMES
from version import __version__
from wizard import dump_yaml


def helpers():
    spec = importlib.util.spec_from_file_location('atlas_shared_exports', ROOT / 'scripts/audit-horizonte-exports.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_atlas_case(data, language=None):
    """Enforce the authored case contract before any output is counted."""
    findings = data.get('findings', [])
    facts = dict(vulnerabilities=sum(row.get('mode') != 'machine' for row in findings),
                 machines=sum(row.get('mode') == 'machine' for row in findings),
                 assets=len(data.get('assets', [])), evidence=len(data.get('evidence', [])))
    expected = dict(vulnerabilities=60, machines=7, assets=28, evidence=84)
    if facts != expected:
        raise ValueError('Atlas fixture contract mismatch: ' + json.dumps(dict(expected=expected, actual=facts)))
    ids = [row.get('id') for row in findings]
    expected_ids = {f'F{number:02d}' for number in range(1, 61)} | {f'M{number:02d}' for number in range(1, 8)}
    if len(ids) != len(set(ids)) or set(ids) != expected_ids:
        raise ValueError('Atlas finding/machine identities differ from its authored contract')
    if language is not None and engine.report_language(data) != language:
        raise ValueError('Atlas source declares the wrong report language')
    return facts


def catalog_plan():
    """Freeze explicit combinations; derive coverage from actual current catalogs."""
    profiles = design_library.catalog()['profiles']
    if len({p['id'] for p in profiles}) != len(profiles):
        raise ValueError('Duplicate profile identity in catalog')
    rows = []
    for language in LANGUAGES:
        rows.append(dict(key=f'principal/{language}', language=language, scope='complete_case',
                         theme='corporativo', formats=list(delivery.FORMATS)))
        for theme in sorted(THEMES - {'corporativo'}):
            rows.append(dict(key=f'samples/general/{language}/{theme}', language=language,
                             scope='targeted_excerpt', theme=theme, formats=list(delivery.FORMATS)))
        choices = {}
        for index, profile in enumerate(profiles):
            variant = design_library.VARIANTS[index % len(design_library.VARIANTS)]
            choices[profile['id']] = variant
            rows.append(dict(key=f"samples/specialized/{language}/{profile['id']}/{variant}", language=language,
                             scope='targeted_excerpt', profile=profile['id'], variant=variant,
                             layout=profile['layout'], motif=profile['motif'], provider=profile['provider'],
                             formats=['pdf', 'docx']))
        # One profile in each layout gets every remaining appearance. This is
        # an explicit subset, not a claim of both variants for every profile.
        for layout in design_library.LAYOUTS:
            profile = next((p for p in profiles if p['layout'] == layout), None)
            if profile is None:
                raise ValueError('Layout lacks an exercisable catalog profile: ' + layout)
            for variant in design_library.VARIANTS:
                if variant == choices[profile['id']]:
                    continue
                rows.append(dict(key=f"samples/specialized/{language}/{profile['id']}/{variant}", language=language,
                                 scope='targeted_excerpt', profile=profile['id'], variant=variant,
                                 layout=layout, motif=profile['motif'], provider=profile['provider'],
                                 variant_control=True, formats=['pdf', 'docx']))
    return [row for row in rows if row['scope'] == 'complete_case'] + [row for row in rows if row['scope'] != 'complete_case']


def catalog_inventory():
    profiles = design_library.catalog()['profiles']
    return dict(languages=list(LANGUAGES), formats=list(delivery.FORMATS), themes=sorted(THEMES),
                profiles=[p['id'] for p in profiles], layouts=list(design_library.LAYOUTS),
                motifs=list(design_library.MOTIFS), variants=list(design_library.VARIANTS),
                providers=sorted({p['provider'] for p in profiles}))


def verified_coverage(plan, jobs):
    """A requested or partial failed job does not count as a verified format."""
    completed = {row['key'] for row in jobs if row.get('status') == 'passed'}
    chosen = [row for row in plan if row['key'] in completed]
    dimensions = {'languages': 'language', 'themes': 'theme', 'profiles': 'profile',
                  'layouts': 'layout', 'motifs': 'motif', 'variants': 'variant', 'providers': 'provider'}
    inventory = catalog_inventory()
    covered = {name: sorted({row[field] for row in chosen if field in row}) for name, field in dimensions.items()}
    covered['formats'] = sorted({fmt for row in chosen for fmt in row['formats']})
    missing = {name: sorted(set(values) - set(covered[name])) for name, values in inventory.items()}
    by_language = {}
    for language in LANGUAGES:
        language_rows = [row for row in chosen if row['language'] == language]
        by_language[language] = {name: sorted(set(inventory[name]) - {row[field] for row in language_rows if field in row})
                                for name, field in dimensions.items() if name != 'languages'}
        by_language[language]['formats'] = sorted(set(delivery.FORMATS) - {fmt for row in language_rows for fmt in row['formats']})
    return dict(catalog=inventory, verified_values=covered, missing_values=missing,
                missing_per_language=by_language,
                planned_jobs=len(plan), completed_jobs=len(chosen),
                missing_jobs=[row['key'] for row in plan if row['key'] not in completed])


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
    plan = catalog_plan()
    selected = [row for row in plan if args.mode == 'all' or (args.mode == 'principal' and row['scope'] == 'complete_case')
                or (args.mode == 'styles' and row['scope'] == 'targeted_excerpt')]
    before, producer = shared.hashes(source), shared.producer_identity()
    receipt = dict(schema='report-gen-atlas-exports/1', case='ATLAS-SERVICIOS-FINANCIEROS-2026', version=__version__,
                   mode=args.mode, created_utc=datetime.now(timezone.utc).isoformat(), producer=producer,
                   generation='report-gen delivery.build and export.export only', inspection='delivery.inspect_export',
                   visual_review='not_performed_by_this_runner', microsoft_word='not_run', jobs=[], plan=selected,
                   catalog=catalog_inventory(), expected_formats=sum(len(row['formats']) for row in selected),
                   combinations_scope='Every language, general style and catalog profile; both variants per layout. Not every possible combination.',
                   harnesses={p.name: sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), ROOT / 'scripts/audit-horizonte-exports.py']})

    def record():
        shared.write_json(receipt_path, receipt)

    def invariant():
        if shared.producer_identity() != producer:
            raise ValueError('Production code changed during execution; preserve this run and use a fresh process/output.')

    excerpts = {}
    try:
        documents = {language: engine.load_engagement(source / language / 'engagement.yaml') for language in LANGUAGES}
        identity_sets = [{row['uid'] for row in data['findings']} for data in documents.values()]
        if not all(value == identity_sets[0] for value in identity_sets):
            raise ValueError('Localized source identity sets differ')
        for language, data in documents.items():
            if engine.report_language(data) != language or data['meta'].get('theme') != 'corporativo' or data['meta'].get('design'):
                raise ValueError('Principal sources must use their declared language and original corporate layout')
            receipt.setdefault('fixture_contract', {})[language] = validate_atlas_case(data, language)
        for row in selected:
            invariant()
            language, key = row['language'], row['key']
            project = source / language
            if row['scope'] == 'targeted_excerpt':
                if language not in excerpts:
                    excerpts[language], selection = shared.technical_excerpt(documents[language], project)
                    receipt.setdefault('excerpt_selection', {})[language] = selection
                data = deepcopy(excerpts[language])
                if row.get('profile'):
                    data = design_library.apply(data, design_library.profile(row['profile']), row['variant'])
                else:
                    data['meta'].pop('design', None)
                    data['meta']['theme'] = row['theme']
                project = out / 'variant-sources' / key
                shutil.copytree(source / language, project)
                dump_yaml(data, project / 'engagement.yaml')
                origin_yaml = out / 'variant-origins' / (key + '.yaml')
                origin_yaml.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(project / 'engagement.yaml', origin_yaml)
                shared.write_json(out / 'variant-origins' / (key + '.json'),
                                  dict(base_revision=shared.identity(shared.hashes(source / language)),
                                       source_sha256=shared.hashes(project)))
            job = shared.export_job(project, out / key, row['formats'], complete_delivery=row['scope'] == 'complete_case',
                                    case_title=documents[language]['meta']['report_title'])
            job.update(key=key, document_scope=row['scope'], combination=row)
            receipt['jobs'].append(job)
            record()
            if job['status'] != 'passed':
                raise ValueError('Native export or fidelity check failed: ' + key)
        if args.native_executable:
            for language in LANGUAGES:
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
    receipt['coverage'] = verified_coverage(selected, receipt['jobs'])
    receipt['status'] = ('passed' if receipt['jobs'] and not receipt.get('errors') and receipt['source_bytes_unchanged']
                         and receipt['producer_bytes_unchanged'] and not receipt['coverage']['missing_jobs']
                         and all(row['status'] == 'passed' for row in receipt['jobs']) else 'failed')
    shared.write_json(out / ('source-sha256-' + args.mode + '.json'), before)
    record()
    print(json.dumps({key: receipt[key] for key in ('status', 'exported_formats', 'complete_case_formats', 'excerpt_formats')}, ensure_ascii=False))
    return 0 if receipt['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
