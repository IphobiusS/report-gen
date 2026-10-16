#!/usr/bin/env python3
"""Exercise Meridiano through real report-gen API handlers in an isolated copy.

The Flask test client is not a browser or an HTTP server. Every report, audience
delivery and native DOCX preview is produced by the application itself.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
from hashlib import sha256
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'webapp')]


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


shared = load('meridiano_shared_lifecycle', 'audit-horizonte-lifecycle.py')
builder = load('meridiano_case_inputs', 'build-meridiano-case.py')
exports = load('meridiano_shared_exports_api', 'audit-horizonte-exports.py')


def publication_marker_scan(blob):
    """Decode native containers; inspect only four named synthetic controls.

    This is a bounded regression check, never a claim of exhaustive privacy.
    PDFs are checked as raw bytes, extracted text and decoded object/stream data;
    DOCX and nested Markdown ZIP members are recursively inspected.
    """
    import fitz
    from PIL import Image
    markers = (builder.PRIVATE_MARKER, builder.REDACTION_MARKER, builder.METADATA_MARKER, builder.UNLINKED_MARKER)
    result = dict(scope='Four named synthetic fixture markers; not a general privacy guarantee',
                  zip_containers=0, leaf_files=0, pdf_pages=0, pdf_objects=0,
                  pdf_streams=0, image_metadata_records=0, matches=[])

    def inspect(raw, location):
        text = raw if isinstance(raw, str) else raw.decode('utf-8', errors='replace')
        for index, marker in enumerate(markers, 1):
            if marker in text:
                result['matches'].append(dict(marker=index, location=location))

    def walk(raw, name, depth=0):
        if depth > 8:
            raise ValueError('Unexpected native-container depth')
        inspect(raw, name + ':raw')
        if zipfile.is_zipfile(BytesIO(raw)):
            result['zip_containers'] += 1
            with zipfile.ZipFile(BytesIO(raw)) as archive:
                for member in archive.infolist():
                    if not member.is_dir():
                        walk(archive.read(member), name + '/' + member.filename, depth + 1)
            return
        result['leaf_files'] += 1
        if raw.startswith(b'%PDF-'):
            with fitz.open(stream=raw, filetype='pdf') as document:
                inspect(json.dumps(document.metadata, ensure_ascii=False), name + ':metadata')
                inspect(document.get_xml_metadata(), name + ':xml-metadata')
                for page in document:
                    result['pdf_pages'] += 1
                    inspect(page.get_text(), name + f':page:{page.number + 1}')
                    inspect(json.dumps(page.get_links(), ensure_ascii=False, default=str), name + f':links:{page.number + 1}')
                    for annotation in page.annots() or []:
                        inspect(json.dumps(annotation.info, ensure_ascii=False), name + f':annotation:{annotation.xref}')
                    for widget in page.widgets() or []:
                        inspect(str(widget.field_value), name + f':field:{widget.xref}')
                for xref in range(1, document.xref_length()):
                    result['pdf_objects'] += 1
                    inspect(document.xref_object(xref, compressed=False), name + f':object:{xref}')
                    if document.xref_is_stream(xref):
                        result['pdf_streams'] += 1
                        inspect(document.xref_stream(xref), name + f':stream:{xref}')
        if raw.startswith((b'\x89PNG', b'\xff\xd8', b'RIFF')):
            with Image.open(BytesIO(raw)) as image:
                result['image_metadata_records'] += 1
                inspect(json.dumps(image.info, ensure_ascii=False, default=str), name + ':image-info')
                inspect(str(dict(image.getexif())), name + ':image-exif')

    walk(blob, 'delivery')
    return result


class Journey(shared.Journey):
    def configure(self, directory):
        super().configure(directory)
        self.slug = 'grupo-meridiano-acceptance'

    def flush(self, complete=False):
        value = dict(schema='report-gen-meridiano-api/1', version=shared.__version__,
                     method='Flask test client against actual API handlers; no HTTP or browser claims',
                     source=str(self.source), source_sha256=shared.digest(self.source / 'engagement.yaml'),
                     complete=complete, producer=self.producer, elapsed_seconds=round(time.time() - self.started, 3),
                     checks=self.records, limitations=self.limits, artifacts=self.artifacts)
        self.write_json('results.json', value, register=False)

    def wait_status(self, path, terminal):
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            response = self.client.get(path)
            if response.status_code != 200:
                raise AssertionError(f'{path}: unexpected polling HTTP {response.status_code}')
            status = response.get_json()
            if status['stage'] in terminal:
                return status
            time.sleep(.1)
        raise TimeoutError(path)

    def audience_deliveries(self, baseline):
        selected = [row['uid'] for row in baseline['findings'][:3]]
        options = [dict(profile='technical', finding_uids=[row['uid'] for row in baseline['findings'] if row['id'] in ('F01', 'F12', 'M01')], section_keys=['findings']),
                   dict(profile='executive', finding_uids=selected, title='Grupo Meridiano — resumen ejecutivo ficticio'),
                   dict(profile='public', finding_uids=selected, title='Logística ficticia — lecciones de control', client_alias='Organización logística ficticia',
                        aliases=[dict(needle='Meridiano', replacement='Organización de simulación')], review_confirmed=True,
                        publish_consent=True, provenance_label='simulation', approved_content=[dict(finding_uid=row['uid'], title=f'Lección ficticia {n}',
                            summary='Modelo inventado que relaciona autorización, expediente y versión. No hubo contacto con una empresa.',
                            impact='El escenario podría producir una decisión incoherente; no acredita una vulnerabilidad real.',
                            remediation='Definir una decisión explícita y conservar pruebas positivas, negativas y límites.') for n, row in enumerate(baseline['findings'][:3], 1)])]
        before = (self.project / 'engagement.yaml').read_bytes()
        for options_row in options:
            profile = options_row['profile']
            preview = self.project_call('POST', '/audiences/preview', body=options_row).get_json()
            self.write_json('audiences/' + profile + '-preview.json', preview)
            self.check(profile + ' audience has no structural errors', not any(row['level'] == 'error' for row in preview['issues']))
            if profile == 'public':
                self.project_call('POST', '/audiences/export', body={**options_row, 'publish_consent': False, 'formats': ['pdf'], 'label': 'Publicación bloqueada', 'acknowledge_warnings': True}, expected=422)
                self.check('Withheld public consent preserves source', before == (self.project / 'engagement.yaml').read_bytes())
            response = self.project_call('POST', '/audiences/export', body={**options_row, 'formats': ['pdf', 'docx', 'html', 'md'], 'label': 'Grupo Meridiano — ' + profile, 'acknowledge_warnings': True})
            path = self.write('audiences/' + profile + '-delivery.zip', response.data)
            scan = publication_marker_scan(response.data)
            self.write_json('audiences/' + profile + '-synthetic-marker-scan.json', scan)
            self.check(profile + ' decoded delivery excludes the four private fixture markers', not scan['matches'], scan)
            with zipfile.ZipFile(path) as archive:
                manifest = json.loads(archive.read('verificacion.json'))
                self.check(profile + ' manifest identifies its audience', manifest['audience']['profile'] == profile)
                if profile != 'technical':
                    self.check(profile + ' omits originals and annexes', not manifest['audience']['plan']['originals'] and not manifest['audience']['plan']['attachments'])
                for entry in archive.infolist():
                    if entry.filename.endswith('.pdf'):
                        self.write('audiences/' + profile + '.pdf', archive.read(entry))
            self.check(profile + ' audience preserves exact source bytes', before == (self.project / 'engagement.yaml').read_bytes())

    def imports_and_locations(self, inputs):
        before = (self.project / 'engagement.yaml').read_bytes()
        csv_text = 'title,severity,description_md\nPrimera,low,Modelo válido\n\nSegunda,UNKNOWN,"Primera línea\nsegunda línea"\n'
        preview = self.project_call('POST', '/intake/preview', body=dict(format='csv', text=csv_text)).get_json()
        expected = dict(operation='import', format='csv', record=2, line=4, line_end=5, field='severity', column=2)
        self.check('Multiline CSV identifies exact source coordinates', preview['rows'][1]['diagnostics'][0]['location'] == expected, preview['rows'][1]['diagnostics'])
        rejected = self.project_call('POST', '/intake/apply', body=dict(format='csv', text=csv_text, selected=[1]), expected=422).get_json()
        self.check('Invalid selected CSV row retains field diagnostic', rejected['diagnostics'][0]['location'] == expected)
        self.check('Invalid import is nonmutating', before == (self.project / 'engagement.yaml').read_bytes())
        self.write_json('diagnostics/csv-preview.json', preview)
        self.write_json('diagnostics/csv-rejected.json', rejected)
        negatives = [
            ('burp', '<issues>\n<issue><name>Primero</name><severity>Low</severity></issue>\n<issue><name>Segundo</name><severity>Low</severity>\n<requestresponse>\n<request base64="true">invalid@@</request>\n</requestresponse></issue>\n</issues>', dict(operation='import', format='burp', record=2, line=5, field='requestresponse[0].request')),
            ('nuclei', json.dumps({'template-id': 'gml', 'matched-at': 'https://edi.meridiano.example', 'info': {'name': 'Primero', 'severity': 'low'}}) + '\n\n' + json.dumps({'template-id': 'gml2', 'matched-at': 'https://edi.meridiano.example', 'info': {'name': 'Segundo', 'severity': {'credential': 'MERIDIANO_PRIVATE_DIAGNOSTIC_CANARY'}}}), dict(operation='import', format='nuclei', record=2, line=3, field='info.severity')),
            ('nmap', '<nmaprun>\n<host><address addr="192.0.2.1" addrtype="ipv4"/></host>\n<host><address addr="192.0.2.2" addrtype="ipv4"/>\n<ports>\n<port portid="65536" protocol="tcp"><state state="open"/></port>\n</ports></host></nmaprun>', dict(operation='import', format='nmap', record=2, line=5, field='ports.port')),
        ]
        sarif = json.loads((inputs / 'sarif.json').read_text())
        sarif['runs'][0]['results'].append(deepcopy(sarif['runs'][0]['results'][0]))
        sarif['runs'][0]['results'][1]['locations'][0]['physicalLocation']['region']['endLine'] = 3
        negatives.append(('sarif', json.dumps(sarif), dict(operation='import', format='sarif', record=2, run_index=0, result_index=1, field='region.endLine')))
        for kind, raw, location in negatives:
            result = self.project_call('POST', '/intake/preview', body=dict(format=kind, text=raw), expected=422).get_json()
            self.check(kind + ' parser returns exact structural location', result['diagnostics'][0]['location'] == location, result['diagnostics'])
            self.check(kind + ' diagnostic excludes supplied private values', 'MERIDIANO_PRIVATE_DIAGNOSTIC_CANARY' not in json.dumps(result['diagnostics']))
            self.write_json('diagnostics/' + kind + '-rejected.json', result)
        self.check('All rejected previews preserve source bytes', before == (self.project / 'engagement.yaml').read_bytes())
        for name, kind in [('findings.csv', 'csv'), ('burp.xml', 'burp'), ('nuclei.jsonl', 'nuclei'), ('nmap.xml', 'nmap'), ('sarif.json', 'sarif')]:
            raw = (inputs / name).read_text()
            preview = self.project_call('POST', '/intake/preview', body=dict(format=kind, text=raw)).get_json()
            selected = [row['index'] for row in preview['rows'] if not row.get('errors') and not row.get('duplicate') and not row.get('existing_duplicate')]
            response = self.project_call('POST', '/intake/apply', body=dict(format=kind, text=raw, selected=selected)).get_json()
            self.check(kind + ' valid records are really applied', response['imported'] == len(selected) and len(selected) > 0)
            self.write_json('imports/' + kind + '-applied.json', dict(imported=response['imported'], import_kind=response['import_kind'], selected=selected))
            if kind == 'burp':
                reloaded = self.load()
                row = next(row for row in reloaded['findings'] if row.get('import_source', {}).get('format') == 'burp')
                self.check('Burp CDATA reference survives application and reload', 'https://docs.meridiano.example/import/burp#revisión' in row['references'])

    def pdf_annex(self, pdf):
        raw = pdf.read_bytes()
        original_hash = sha256(raw).hexdigest()
        name = 'meridiano-informe-nativo-para-inspeccion.pdf'
        updated = self.project_call('POST', '/attachments/upload', data={'file': (BytesIO(raw), name)}).get_json()['data']
        annex = next(row for row in updated['attachments'] if row['name'] == name)
        before = (self.project / 'engagement.yaml').read_bytes()
        scan = self.project_call('GET', '/attachments/scan?uid=' + annex['uid']).get_json()
        self.write_json('annex/native-pdf-scan.json', scan)
        self.check('PDF scan binds exact native report bytes', scan['sha256'] == original_hash and scan['bytes'] == len(raw))
        self.check('PDF scan states its structural and incomplete scope', scan['scope'] == 'pdf_structural' and scan['complete'] is False and scan['manual_review_required'] is True and scan['bytes_inspected'] == 0)
        self.check('Native PDF has inspectable structure', scan['pdf']['status'] in ('inspected', 'partial') and scan['pdf']['pages_inspected'] > 0)
        self.check('PDF alerts carry only structural locations', all(set(location) <= {'category', 'page', 'object', 'generation'} for alert in scan['alerts'] for location in alert.get('locations', [])))
        self.check('Scan preserves source revision and review decision', before == (self.project / 'engagement.yaml').read_bytes() and annex['reviewed'] is False and annex['include'] is False)
        self.check('PDF scan preserves exact attachment and input bytes', (self.project / annex['member']).read_bytes() == raw and pdf.read_bytes() == raw)

    def docx_preview(self, require_native, require_stable_native=False):
        before = (self.project / 'engagement.yaml').read_bytes()
        capabilities = self.call('GET', '/api/docx-preview/capabilities').get_json()
        self.write_json('docx/capabilities.json', capabilities)
        job = self.project_call('POST', '/jobs', body=dict(kind='export', formats=['docx'], label='Meridiano — DOCX de vista nativa', acknowledge_warnings=True), expected=202).get_json()
        status = self.wait_status('/api/jobs/' + job['id'], {'done', 'error', 'cancelled'})
        self.check('Native DOCX export completes', status['stage'] == 'done', status)
        raw = self.call('GET', '/api/jobs/' + job['id'] + '/download').data
        self.write('docx/meridiano-queued.docx', raw)
        if not capabilities['available']:
            failure = self.call('POST', '/api/jobs/' + job['id'] + '/docx-preview', body={}, expected=422).get_json()
            self.write_json('docx/unavailable.json', failure)
            self.limits.append('Native DOCX preview was unavailable; no native renderer acceptance is claimed.')
            self.check('Unavailable renderer returns actionable error', bool(failure.get('error')))
            if require_native:
                self.check('Native preview required by this run is available', False)
            return
        preview = self.call('POST', '/api/jobs/' + job['id'] + '/docx-preview', body={}, expected=202).get_json()
        finished = self.wait_status('/api/docx-preview/' + preview['id'], {'done', 'error', 'cancelled'})
        self.check('Real native DOCX preview completes', finished['stage'] == 'done', finished)
        receipt = self.call('GET', '/api/docx-preview/' + preview['id'] + '/receipt').get_json()
        pdf = self.call('GET', '/api/docx-preview/' + preview['id'] + '/pdf').data
        self.write('docx/native-preview.pdf', pdf)
        self.write_json('docx/native-preview-receipt.json', receipt)
        self.check('Native receipt binds source, revision and derived PDF', receipt['source_docx_sha256'] == sha256(raw).hexdigest() and receipt['source_revision'] == status['revision'] and receipt['pdf_sha256'] == sha256(pdf).hexdigest())
        self.check('Native receipt distinguishes its engine from Word', receipt['word_verified'] is False and receipt['pages'] > 0 and 'LibreOffice' in receipt['engine']['version'])
        stable = exports.load_verifier().stable_version(receipt['engine']['version'])
        self.write_json('docx/renderer-acceptance-scope.json', dict(renderer=receipt['engine']['version'],
                        stable_renderer=stable, acceptance_eligible=stable,
                        run_kind='stable_renderer_acceptance' if stable else 'development_renderer_diagnostic',
                        microsoft_word='not_run', visual_acceptance='not_assessed_by_this_runner'))
        if not stable:
            self.limits.append('The local native preview used a development LibreOffice renderer; this proves API integration only, not stable-renderer acceptance.')
        if require_stable_native:
            self.check('Native preview uses a stable LibreOffice release', stable, receipt['engine'])
        self.check('Preview leaves source and original DOCX unchanged', before == (self.project / 'engagement.yaml').read_bytes() and self.call('GET', '/api/jobs/' + job['id'] + '/download').data == raw)
        self.call('DELETE', '/api/docx-preview/' + preview['id'], body={})
        self.call('GET', '/api/docx-preview/' + preview['id'], expected=404)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--pdf', type=Path, required=True, help='Existing report-gen PDF, never externally composed.')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ui-bundle', type=Path)
    parser.add_argument('--require-native', action='store_true')
    parser.add_argument('--require-stable-native', action='store_true', help='Require a successful preview from a stable LibreOffice release.')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Use a fresh output directory and retain earlier evidence')
    source_before, producer = exports.hashes(args.case), exports.producer_identity()
    journey = Journey(args.case, args.output, args.ui_bundle, args.pdf)
    journey.producer['scripts/audit-meridiano-api.py'] = shared.digest(Path(__file__))
    try:
        baseline = journey.load()
        journey.check('Complete Meridiano fixture loaded', len(baseline['findings']) == 34 and len(baseline['assets']) == 16 and len(baseline['evidence']) == 32)
        if args.ui_bundle:
            args.ui_bundle.parent.mkdir(parents=True, exist_ok=True)
            args.ui_bundle.write_bytes(journey.project_call('GET', '/bundle').data)
        journey.audience_deliveries(baseline)
        journey.docx_preview(args.require_native or args.require_stable_native, args.require_stable_native)
        journey.pdf_annex(args.pdf)
        journey.imports_and_locations(args.inputs)
        journey.check('Original case files remain byte-identical', source_before == exports.hashes(args.case))
        journey.check('Report producer remains unchanged', producer == exports.producer_identity())
        journey.flush(complete=True)
        return 0
    finally:
        queue = shared.api.app.extensions.get('export_queue')
        if queue:
            queue.close()
        store = shared.api.app.extensions.get('docx_previews')
        if store:
            store.close()


if __name__ == '__main__':
    sys.exit(main())
