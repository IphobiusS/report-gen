#!/usr/bin/env python3
"""Exercise the fictional Horizonte case through report-gen's public exporters.

No document is composed by this harness. It supplies native project inputs to
delivery.capture/build and export.export, then runs delivery.inspect_export.
The optional LibreOffice pass renders the resulting DOCX for inspection only.
"""
import argparse
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import audience
import delivery
import design_library
import engine
import export
from export_formats import get
from report_designs import THEMES
from version import __version__
from wizard import dump_yaml


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def hashes(folder):
    return {path.relative_to(folder).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in sorted(folder.rglob('*')) if path.is_file()}


def identity(inventory):
    return sha256(json.dumps(inventory, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def producer_identity():
    """Bind artifacts to actual working-tree code/assets, including uncommitted fixes."""
    paths = set(ROOT.glob('*.py'))
    for folder in ('exporters', 'templates', 'themes', 'lang', 'designs', 'cvss'):
        paths.update(path for path in (ROOT / folder).rglob('*')
                     if path.is_file() and '__pycache__' not in path.parts)
    inventory = {path.relative_to(ROOT).as_posix(): sha256(path.read_bytes()).hexdigest()
                 for path in sorted(paths)}
    return {'tool_version': __version__, 'code_assets_sha256': identity(inventory), 'files': inventory}


def load_verifier():
    spec = importlib.util.spec_from_file_location('horizonte_native_verifier', ROOT / 'scripts/verify-libreoffice.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render_pages(path, destination):
    import fitz
    destination.mkdir(parents=True, exist_ok=False)
    rows = []
    with fitz.open(path) as document:
        if not len(document):
            raise ValueError(f'Empty PDF: {path}')
        for index, page in enumerate(document, 1):
            target = destination / f'page-{index:03}.png'
            page.get_pixmap(dpi=110, alpha=False).save(target)
            rows.append({'page': index, 'file': target.name, 'sha256': sha256(target.read_bytes()).hexdigest()})
    return rows


def native_checks(source, outputs, destination, executable, require_stable):
    """Reuse the established native content/TOC/geometry/link verifier."""
    verifier = load_verifier()
    version = subprocess.run([executable, '--version'], capture_output=True, text=True,
                             check=True, timeout=30).stdout.strip()
    stable = verifier.stable_version(version)
    source_before, outputs_before = hashes(source), hashes(outputs)
    result = {'renderer': version, 'stable_renderer': stable, 'acceptance_eligible': stable,
              'run_kind': 'acceptance' if stable else 'development_renderer_diagnostic',
              'visual_review': 'pending_manual_review', 'microsoft_word': 'not_run',
              'checks': {}, 'errors': [], 'producer': producer_identity(),
              'verifier_sha256': sha256((ROOT / 'scripts/verify-libreoffice.py').read_bytes()).hexdigest()}
    destination.mkdir(parents=True, exist_ok=False)
    if require_stable and not stable:
        result['errors'].append({'check': 'renderer', 'error': 'Stable LibreOffice is required'})
    else:
        original = outputs / 'informe.docx'
        try:
            captured = delivery.capture(source, destination / 'snapshot')
            rendered = verifier.convert(executable, original.resolve(), destination / 'libreoffice', timeout=180)
            result['source_docx_sha256'] = sha256(original.read_bytes()).hexdigest()
            result['rendered_pdf_sha256'] = sha256(rendered.read_bytes()).hexdigest()
            result['checks']['native_pages'] = render_pages(rendered, destination / 'native-pages')
            result['checks']['direct_pdf_pages'] = render_pages(outputs / 'informe.pdf', destination / 'direct-pdf-pages')
            for name, check in (
                ('native_content', lambda: verifier.inspect_native_content(original, rendered, captured)),
                ('contents', lambda: verifier.inspect_contents(original, rendered)),
                ('geometry', lambda: verifier.inspect_geometry(rendered, destination / 'geometry-pages')),
                ('direct_pdf_geometry', lambda: verifier.inspect_geometry(outputs / 'informe.pdf', destination / 'direct-geometry-pages')),
            ):
                try:
                    result['checks'][name] = check()
                except Exception as exc:
                    result['errors'].append({'check': name, 'error': f'{type(exc).__name__}: {exc}'})
            if 'geometry' in result['checks']:
                try:
                    result['checks']['links'] = verifier.inspect_links(original, rendered, result['checks']['geometry'])
                except Exception as exc:
                    result['errors'].append({'check': 'links', 'error': f'{type(exc).__name__}: {exc}'})
        except Exception as exc:
            result['errors'].append({'check': 'conversion', 'error': f'{type(exc).__name__}: {exc}'})
    result['source_bytes_unchanged'] = hashes(source) == source_before
    result['export_bytes_unchanged'] = hashes(outputs) == outputs_before
    result['producer_bytes_unchanged'] = producer_identity() == result['producer']
    if not all(result[key] for key in ('source_bytes_unchanged', 'export_bytes_unchanged', 'producer_bytes_unchanged')):
        result['errors'].append({'check': 'invariance', 'error': 'Inputs, outputs or production code changed'})
    result['status'] = 'failed' if result['errors'] else 'passed'
    write_json(destination / 'results.json', result)
    return result


def export_job(source, destination, formats, *, complete_delivery=False,
               case_title='Banco Horizonte — escenario ficticio'):
    """Fail visibly and retain failed artifacts for diagnosis; never label them passed."""
    before = hashes(source)
    producer_before = producer_identity()
    started = time.monotonic()
    result = {'source': str(source), 'source_revision': identity(before),
              'formats': list(formats), 'checks': {}, 'errors': [], 'stage': 'capture',
              'producer': producer_before}
    destination.mkdir(parents=True, exist_ok=False)
    snapshot = destination / 'snapshot'
    output = destination / 'outputs'
    try:
        document = engine.load_engagement(source / 'engagement.yaml')
        result['source_summary'] = {
            'language': engine.report_language(document), 'theme': document.get('meta', {}).get('theme'),
            'specialized_design': document.get('meta', {}).get('design'),
            'findings': len(document.get('findings', [])), 'evidence': len(document.get('evidence', [])),
            'assets': len(document.get('assets', [])), 'coverage': len(document.get('coverage', [])),
            'sections': len(document.get('report', {}).get('sections', [])),
        }
        captured = delivery.capture(source, snapshot)
        snapshot_before = hashes(snapshot)
        result['warnings'] = captured['issues']
        result['expected_images'] = captured['image_placements']
        if complete_delivery:
            result['stage'] = 'delivery_build'
            def progress(stage):
                result['stage'] = stage
                print(json.dumps({'job': str(destination), 'stage': stage}), flush=True)
            blob = delivery.build(snapshot, list(formats), identity(before),
                                  case_title, captured, output, progress)
            (destination / 'delivery.zip').write_bytes(blob)
            with zipfile.ZipFile(BytesIO(blob)) as archive:
                manifest = json.loads(archive.read('verificacion.json'))
            write_json(destination / 'verificacion.json', manifest)
            result['checks'] = manifest['files']
            result['delivery_sha256'] = sha256(blob).hexdigest()
        else:
            output.mkdir()
            for fmt in formats:
                result['stage'] = 'export_' + fmt
                try:
                    path = export.export(snapshot / 'engagement.yaml', fmt, output / get(fmt).filename)
                    checks = delivery.inspect_export(path, fmt, captured)
                    result['checks'][path.name] = {'bytes': path.stat().st_size,
                                                 'sha256': sha256(path.read_bytes()).hexdigest(), 'checks': checks}
                except Exception as exc:
                    result['errors'].append({'stage': result['stage'], 'error': f'{type(exc).__name__}: {exc}',
                                             'traceback': traceback.format_exc()})
        result['snapshot_bytes_unchanged'] = hashes(snapshot) == snapshot_before
        if not result['snapshot_bytes_unchanged']:
            raise ValueError('A public exporter modified its immutable capture')
    except Exception as exc:
        result['errors'].append({'stage': result['stage'], 'error': f'{type(exc).__name__}: {exc}',
                                 'traceback': traceback.format_exc()})
    result['source_bytes_unchanged'] = hashes(source) == before
    result['producer_bytes_unchanged'] = producer_identity() == producer_before
    if not result['producer_bytes_unchanged']:
        result['errors'].append({'stage': 'producer_invariance', 'error': 'Producer code or assets changed during export'})
    if not result['source_bytes_unchanged']:
        result['errors'].append({'stage': 'invariance', 'error': 'Original project files changed'})
    result['seconds'] = round(time.monotonic() - started, 3)
    result['status'] = 'failed' if result['errors'] else 'passed'
    write_json(destination / 'source-sha256.json', before)
    write_json(destination / 'results.json', result)
    print(json.dumps({'job': str(destination), 'status': result['status'], 'seconds': result['seconds'],
                      'errors': [{k: v for k, v in row.items() if k != 'traceback'} for row in result['errors']]},
                     ensure_ascii=False), flush=True)
    return result


def technical_excerpt(data, source):
    """Select native findings without rewriting prose or dropping broken links."""
    findings = data.get('findings', [])
    if not findings:
        raise ValueError('Horizonte requires authored findings')
    selected = [findings[0]]
    # Include the linked-image regression and a machine narrative when present.
    linked = next((row for row in findings if '](' in json.dumps(row) and '[![' in json.dumps(row)), None)
    machine = next((row for row in findings if row.get('mode') == 'machine'), None)
    for row in (linked, machine):
        if row is not None and row not in selected:
            selected.append(row)
    # Keep the authored destination closure instead of silently removing links.
    import re
    selected_ids = {row['id'] for row in selected}
    by_id = {row['id']: row for row in findings}
    while True:
        targets = set(re.findall(r'\]\(#([^\s)]+)\)', json.dumps(selected, ensure_ascii=False)))
        extra = [by_id[key] for key in targets & by_id.keys() - selected_ids]
        if not extra:
            break
        selected.extend(extra)
        selected_ids.update(row['id'] for row in extra)
    options = {'profile': 'technical', 'finding_uids': [row['uid'] for row in selected],
               'section_keys': ['findings']}
    result = audience.preview(data, source, options)
    errors = [issue['message'] for issue in result['issues'] if issue['level'] == 'error']
    if errors:
        raise ValueError('Specialized sample has invalid native selection: ' + '; '.join(errors))
    return result['data'], result['plan']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--projects', type=Path, required=True, help='Native project folders es/en/pt')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('principal', 'general', 'specialized', 'native', 'all'), default='principal')
    parser.add_argument('--native-executable', help='Optional native DOCX diagnostic renderer')
    parser.add_argument('--require-stable', action='store_true')
    parser.add_argument('--only', nargs='*', help='Restrict general theme or specialized profile IDs')
    parser.add_argument('--resume', action='store_true', help='Reuse passed jobs only when source revision and output hashes match')
    args = parser.parse_args()
    if args.require_stable and not args.native_executable:
        parser.error('--require-stable requires --native-executable')
    source_root, output_root = args.projects.resolve(), args.output.resolve()
    if output_root == source_root or output_root.is_relative_to(source_root):
        parser.error('Output must be outside the immutable project source')
    output_root.mkdir(parents=True, exist_ok=True)
    source_before = hashes(source_root)
    producer_before = producer_identity()
    report = {'schema': 'report-gen-horizonte-exports/1', 'tool_version': __version__,
              'created_utc': datetime.now(timezone.utc).isoformat(), 'mode': args.mode,
              'generation': 'report-gen delivery.build and export.export only',
              'inspection': 'report-gen delivery.inspect_export',
              'visual_review': 'pending_manual_review', 'microsoft_word': 'not_run', 'jobs': [],
              'producer': producer_before,
              'harness_sha256': sha256(Path(__file__).read_bytes()).hexdigest()}
    report_path = output_root / ('matrix-' + args.mode + '.json')

    def run(key, source, formats, complete=False):
        if producer_identity() != producer_before:
            report['status'] = 'failed'
            report['errors'] = ['Production code changed since this Python process started; restart with a fresh output directory']
            write_json(report_path, report)
            raise ValueError(report['errors'][0])
        dest = output_root / key
        receipt = dest / 'results.json'
        if receipt.exists() and args.resume:
            previous = json.loads(receipt.read_text())
            if (previous['status'] == 'passed' and previous['source_revision'] == identity(hashes(source))
                    and previous.get('producer') == producer_identity()
                    and previous.get('formats') == list(formats)):
                for name, expected in previous['checks'].items():
                    actual = dest / 'outputs' / name
                    if not actual.is_file() or sha256(actual.read_bytes()).hexdigest() != expected['sha256']:
                        raise ValueError(f'Resume output changed: {actual}')
                if complete and (not (dest / 'delivery.zip').is_file() or
                                 sha256((dest / 'delivery.zip').read_bytes()).hexdigest() != previous['delivery_sha256']):
                    raise ValueError(f'Resume delivery changed: {dest}')
                row = dict(previous, reused_verified_job=True)
            else:
                raise ValueError(f'Existing job is failed or stale; preserve it then use a fresh output directory: {dest}')
        else:
            row = export_job(source, dest, formats, complete_delivery=complete)
        row['key'] = key
        report['jobs'].append(row)
        write_json(report_path, report)
        return row

    def variant_source(key, data):
        source = output_root / 'variant-sources' / key
        receipt_path = output_root / 'variant-origins' / (key + '.json')
        expected = {'base_revision': identity(hashes(source_root / 'es')), 'configuration': data}
        if source.exists():
            if not args.resume or not receipt_path.is_file():
                raise ValueError(f'Existing variant has no authorized resumable provenance: {source}')
            receipt = json.loads(receipt_path.read_text())
            if receipt.get('origin') != expected or receipt.get('source_sha256') != hashes(source):
                raise ValueError(f'Variant project changed or derives from stale input: {source}')
        else:
            shutil.copytree(source_root / 'es', source)
            dump_yaml(data, source / 'engagement.yaml')
            write_json(receipt_path, {'origin': expected, 'source_sha256': hashes(source)})
        return source

    if args.mode in ('principal', 'all'):
        for language in ('es', 'en', 'pt'):
            document = engine.load_engagement(source_root / language / 'engagement.yaml')
            if document.get('meta', {}).get('theme') != 'corporativo' or document.get('meta', {}).get('design'):
                raise ValueError('The principal matrix requires the unmodified corporate Horizonte project')
            run('principal/' + language, source_root / language, delivery.FORMATS, True)
    if args.mode in ('general', 'all'):
        for theme in sorted(THEMES - {'corporativo'}):
            if args.only and theme not in args.only:
                continue
            data = engine.load_engagement(source_root / 'es/engagement.yaml')
            data['meta'].pop('design', None)
            data['meta']['theme'] = theme
            source = variant_source('general/' + theme, data)
            run('general/' + theme, source, delivery.FORMATS)
    if args.mode in ('specialized', 'all'):
        data = engine.load_engagement(source_root / 'es/engagement.yaml')
        excerpt, plan = technical_excerpt(data, source_root / 'es')
        report['specialized_excerpt'] = plan
        for profile in design_library.catalog()['profiles']:
            if args.only and profile['id'] not in args.only:
                continue
            for variant in design_library.VARIANTS:
                key = profile['id'] + '/' + variant
                applied = design_library.apply(deepcopy(excerpt), profile, variant)
                source = variant_source('specialized/' + key, applied)
                run('specialized/' + key, source, ('pdf', 'docx'))
    if args.native_executable:
        for language in ('es', 'en', 'pt'):
            if producer_identity() != producer_before:
                raise ValueError('Production code changed since this Python process started; restart native inspection')
            dest = output_root / 'native' / language
            row = native_checks(source_root / language, output_root / 'principal' / language / 'outputs',
                                dest, args.native_executable, args.require_stable)
            row['key'] = 'native/' + language
            report['jobs'].append(row)
            write_json(report_path, report)
    report['source_bytes_unchanged'] = hashes(source_root) == source_before
    report['producer_bytes_unchanged'] = producer_identity() == producer_before
    report['status'] = ('passed' if report['jobs'] and report['source_bytes_unchanged'] and report['producer_bytes_unchanged']
                        and all(row['status'] == 'passed' for row in report['jobs']) else 'failed')
    report['exported_formats'] = sum(len(row.get('formats', [])) for row in report['jobs'])
    write_json(output_root / ('source-sha256-' + args.mode + '.json'), source_before)
    write_json(report_path, report)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
