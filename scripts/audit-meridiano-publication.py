#!/usr/bin/env python3
"""Inspect completed Meridiano outputs for four named synthetic privacy controls.

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
    spec = importlib.util.spec_from_file_location('meridiano_publication_scan_api', ROOT / 'scripts/audit-meridiano-api.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    matrix_path = args.exports / 'matrix-all.json'
    matrix = json.loads(matrix_path.read_text())
    if matrix['status'] != 'passed' or matrix['exported_formats'] != 40:
        raise ValueError('Only the completed forty-format matrix can be inspected as final')
    before = module.exports.hashes(args.case)
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
    if len(selected) != 31:
        raise ValueError('Expected three complete delivery ZIPs and twenty-eight sample outputs')
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
    result = dict(schema='report-gen-meridiano-publication-scan/1', status='passed' if outputs_unchanged and source_unchanged and not any(row['scan']['matches'] for row in rows) else 'failed',
                  scope='Four named synthetic controls only; no universal privacy or secret-detection claim',
                  inspected_outputs=31, covered_report_formats=40, complete_deliveries=3, sample_formats=28,
                  source_files=len(before), source_bytes_unchanged=source_unchanged, output_bytes_unchanged=outputs_unchanged,
                  matrix_sha256=sha256(matrix_path.read_bytes()).hexdigest(), producer=matrix['producer'],
                  harnesses={p.name: sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), ROOT / 'scripts/audit-meridiano-api.py']},
                  totals=counts, outputs=rows,
                  excluded_native_inspections=native_inspections,
                  excluded='Editable source, originals, private notes, backups and diagnostic workspaces intentionally contain synthetic controls and are not client publication.')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({key: result[key] for key in ('status', 'inspected_outputs', 'covered_report_formats', 'source_files', 'source_bytes_unchanged', 'output_bytes_unchanged', 'totals')}))
    return 0 if result['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
