#!/usr/bin/env python3
"""Render R16 DOCX in native LibreOffice and keep reproducible review evidence.

The PDF image set is evidence for a separate human visual review. Generating it
does not claim that Microsoft Word or a person has reviewed the pages.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import fitz

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import delivery


def load_verifier():
    spec = importlib.util.spec_from_file_location('r16_native_verifier', ROOT / 'scripts/verify-libreoffice.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def hashes(folder):
    return {path.relative_to(folder).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sorted(folder.rglob('*')) if path.is_file()}


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def render_pages(path, destination):
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    with fitz.open(path) as document:
        if not len(document):
            raise ValueError(f'PDF has no pages: {path}')
        for index, page in enumerate(document, 1):
            image = destination / f'page-{index:03}.png'
            page.get_pixmap(dpi=110, alpha=False).save(image)
            rows.append({'page': index, 'file': image.name, 'sha256': sha256(image.read_bytes()).hexdigest()})
    return rows


def audit(inputs, output, executable, *, allow_development=False):
    output.mkdir(parents=True, exist_ok=False)
    verifier = load_verifier()
    source = ROOT / 'qa/r16-recovery/projects'
    original_sources, original_inputs = hashes(source), hashes(inputs)
    version = subprocess.run([executable, '--version'], capture_output=True, text=True,
                             check=True, timeout=30).stdout.strip()
    stable = verifier.stable_version(version)
    report = {'created_utc': datetime.now(timezone.utc).isoformat(),
              'renderer': version, 'stable_renderer': stable,
              'acceptance_eligible': stable,
              'run_kind': 'acceptance' if stable else 'development_renderer_diagnostic',
              'visual_review': 'pending_manual_review',
              'microsoft_word': 'not_run', 'results': []}
    write_json(output / 'results.json', report)
    if not stable and not allow_development:
        raise ValueError(f'A stable LibreOffice release is required: {version}')
    for language in ('es', 'en', 'pt'):
        item = {'language': language, 'checks': {}, 'errors': []}
        destination = output / language
        destination.mkdir()
        original_docx = inputs / language / 'informe.docx'
        original_pdf = inputs / language / 'informe.pdf'
        stage = 'source_docx'
        try:
            captured = delivery.capture(source / language, destination / 'snapshot')
            item['checks']['source_docx'] = delivery.inspect_export(original_docx, 'docx', captured)
            stage = 'render'
            rendered = verifier.convert(executable, original_docx.resolve(), destination / 'libreoffice')
            item['checks']['source_sha256'] = sha256(original_docx.read_bytes()).hexdigest()
            item['checks']['rendered_pdf_sha256'] = sha256(rendered.read_bytes()).hexdigest()
            # Save every native page before inspection, including pages from a
            # failing conversion, so diagnostics do not hide the offending ink.
            item['checks']['native_pages'] = render_pages(rendered, destination / 'native-pages')
            item['checks']['direct_pdf_pages'] = render_pages(original_pdf, destination / 'direct-pdf-pages')
            for name, check in (
                ('native_content', lambda: verifier.inspect_native_content(original_docx, rendered, captured)),
                ('contents', lambda: verifier.inspect_contents(original_docx, rendered)),
                ('geometry', lambda: verifier.inspect_geometry(rendered, destination / 'geometry-pages')),
            ):
                try:
                    item['checks'][name] = check()
                except Exception as exc:
                    item['errors'].append({'check': name, 'error': f'{type(exc).__name__}: {exc}'})
            if 'geometry' in item['checks']:
                try:
                    item['checks']['links'] = verifier.inspect_links(original_docx, rendered, item['checks']['geometry'])
                except Exception as exc:
                    item['errors'].append({'check': 'links', 'error': f'{type(exc).__name__}: {exc}'})
        except Exception as exc:
            item['errors'].append({'check': stage, 'error': f'{type(exc).__name__}: {exc}'})
        item['status'] = 'failed' if item['errors'] else 'passed'
        report['results'].append(item)
        write_json(output / 'results.json', report)
        print(json.dumps({'language': language, 'status': item['status'], 'errors': item['errors']},
                         ensure_ascii=False), flush=True)
    report['source_bytes_unchanged'] = original_sources == hashes(source)
    report['export_bytes_unchanged'] = original_inputs == hashes(inputs)
    report['status'] = ('passed' if report['source_bytes_unchanged'] and report['export_bytes_unchanged']
                        and all(item['status'] == 'passed' for item in report['results']) else 'failed')
    write_json(output / 'results.json', report)
    write_json(output / 'project-source-sha256.json', original_sources)
    write_json(output / 'export-source-sha256.json', original_inputs)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True, type=Path, help='Output of audit-estuario-r16.py')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--executable', default=shutil.which('libreoffice') or shutil.which('soffice'))
    parser.add_argument('--allow-development', action='store_true',
                        help='Diagnostic only: record development renderer results without stable acceptance')
    args = parser.parse_args()
    if not args.executable:
        parser.error('LibreOffice is unavailable; pass --executable')
    sys.exit(audit(args.input.resolve(), args.output.resolve(), args.executable,
                   allow_development=args.allow_development))
