#!/usr/bin/env python3
"""Inspect completed Atlas outputs for four named synthetic privacy controls.

No output is generated or rewritten. ZIP/DOCX, PDF text/objects/streams and image
metadata are decoded by the same bounded inspector used in API acceptance.
"""
import argparse
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from export_formats import get


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--exports', required=True, type=Path)
    parser.add_argument('--case', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Preserve existing inspection receipts; choose a fresh output path')
    try:
        return inspect(args)
    except Exception as exc:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(dict(schema='report-gen-atlas-publication-scan/1', status='failed',
            error=dict(type=type(exc).__name__, message=str(exc)),
            covered_report_formats=0, scope='Inspection failed; no publication acceptance is claimed'),
            ensure_ascii=False, indent=2) + '\n')
        raise


def inspect(args):
    spec = importlib.util.spec_from_file_location('atlas_publication_scan_api', ROOT / 'scripts/audit-atlas-api.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    matrix_paths = [args.exports / 'matrix-all.json']
    if not matrix_paths[0].is_file():
        matrix_paths = [args.exports / 'matrix-principal.json', args.exports / 'matrix-styles.json']
    matrices = [json.loads(path.read_text()) for path in matrix_paths]
    if any(value['status'] != 'passed' for value in matrices):
        raise ValueError('Only completed matrices can be inspected as final')
    producers = [value['producer'] for value in matrices]
    if any(value != producers[0] for value in producers):
        raise ValueError('Split matrices have different report producers')
    jobs = [row for matrix in matrices for row in matrix['jobs']]
    if len({row['key'] for row in jobs}) != len(jobs):
        raise ValueError('Split matrices repeat a job identity')
    export_spec = importlib.util.spec_from_file_location('atlas_publication_export_plan', ROOT / 'scripts/audit-atlas-exports.py')
    export_module = importlib.util.module_from_spec(export_spec)
    export_spec.loader.exec_module(export_module)
    plan = export_module.catalog_plan()
    coverage = export_module.verified_coverage(plan, jobs)
    if coverage['missing_jobs'] or any(coverage['missing_values'].values()):
        raise ValueError('Completed outputs do not cover the current planned catalog')
    expected_formats = sum(len(row['formats']) for row in plan)
    actual_formats = sum(matrix['exported_formats'] for matrix in matrices)
    if expected_formats != actual_formats:
        raise ValueError('Verified count differs from the current catalog plan')
    matrix = dict(jobs=jobs, producer=producers[0])
    before = module.exports.hashes(args.case)
    expected_sources = [json.loads((args.exports / ('source-sha256-' + value['mode'] + '.json')).read_text()) for value in matrices]
    if any(value != before for value in expected_sources):
        raise ValueError('Current source tree differs from the source used to generate a matrix')
    selected, native_inspections = [], []
    for job in matrix['jobs']:
        directory = args.exports / job['key']
        if job['document_scope'] == 'complete_case':
            selected.append((directory / 'delivery.zip', job['delivery_sha256'], job['key'], 'complete_delivery'))
        elif job['document_scope'] == 'targeted_excerpt':
            for fmt in job['formats']:
                name = get(fmt).filename
                selected.append((directory / 'outputs' / name, job['checks'][name]['sha256'], job['key'], fmt))
        elif job['document_scope'] == 'complete_case_native_inspection':
            native_inspections.append(job['key'])
        else:
            raise ValueError('Unknown matrix job scope: ' + str(job.get('document_scope')))
    complete_count = sum(row[3] == 'complete_delivery' for row in selected)
    samples = len(selected) - complete_count
    if complete_count != len(export_module.LANGUAGES) or samples + complete_count * len(export_module.delivery.FORMATS) != actual_formats:
        raise ValueError('Selected artifacts do not account for every verified format')
    rows = []
    counts = {key: 0 for key in ('zip_containers', 'leaf_files', 'pdf_pages', 'pdf_objects', 'pdf_streams', 'image_metadata_records')}
    for path, expected, job, kind in selected:
        raw = path.read_bytes()
        actual = sha256(raw).hexdigest()
        if actual != expected:
            raise ValueError('Output differs from native receipt: ' + str(path))
        scan = module.publication_marker_scan(raw)
        for key in counts:
            counts[key] += scan[key]
        rows.append(dict(file=path.relative_to(args.exports).as_posix(), job=job, kind=kind,
                         bytes=len(raw), sha256=actual, scan=scan))
    outputs_unchanged = all(sha256(path.read_bytes()).hexdigest() == expected for path, expected, _, _ in selected)
    source_unchanged = before == module.exports.hashes(args.case)
    result = dict(schema='report-gen-atlas-publication-scan/1', status='passed' if outputs_unchanged and source_unchanged and not any(row['scan']['matches'] for row in rows) else 'failed',
                  scope='Four named synthetic controls only; no universal privacy or secret-detection claim',
                  inspected_outputs=len(selected), covered_report_formats=actual_formats, complete_deliveries=complete_count, sample_formats=samples,
                  source_files=len(before), source_bytes_unchanged=source_unchanged, output_bytes_unchanged=outputs_unchanged,
                  matrix_sha256={path.name: sha256(path.read_bytes()).hexdigest() for path in matrix_paths}, producer=matrix['producer'], coverage=coverage,
                  harnesses={p.name: sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), ROOT / 'scripts/audit-atlas-api.py']},
                  totals=counts, outputs=rows,
                  excluded_native_inspections=native_inspections,
                  excluded='Editable source, originals, private notes, backups and diagnostic workspaces intentionally contain synthetic controls and are not client publication.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'inspected_outputs', 'covered_report_formats', 'source_files', 'source_bytes_unchanged', 'output_bytes_unchanged', 'totals')}))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
