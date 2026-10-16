#!/usr/bin/env python3
"""Exercise Atlas through real report-gen API handlers in an isolated copy.

The Flask test client is not a browser or an HTTP server. Every report, audience
delivery and native DOCX preview is produced by the application itself.
"""
from __future__ import annotations

import argparse
import csv
from io import StringIO
import secrets
import shutil
import tempfile
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


shared = load('atlas_shared_lifecycle', 'audit-horizonte-lifecycle.py')
builder = load('atlas_case_inputs', 'build-atlas-case.py')
exports = load('atlas_shared_exports_api', 'audit-horizonte-exports.py')
atlas_exports = load('atlas_exports_contract_api', 'audit-atlas-exports.py')
api = shared.api
delivery_signature = shared.delivery_signature
design_library = shared.design_library
project_history = shared.project_history
remediation_tasks = shared.remediation_tasks
atomic_write = shared.atomic_write
digest = shared.digest


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
    def __init__(self, source, output, ui_bundle=None, pdf=None):
        # The host synchronizes scratch artifacts between tool calls. Keep
        # mutable rename/journal transactions outside that mirrored tree; only
        # immutable evidence and native backups are copied into the output.
        temporary = Path(tempfile.mkdtemp(prefix='report-gen-atlas-api-'))
        super().__init__(source, temporary, ui_bundle, pdf)
        self.out = output.resolve()
        self.out.mkdir(parents=True, exist_ok=False)
        self.limits.append('The disposable API workspace remains in the recorded system temporary directory for diagnosis; it is not part of the delivery or upload. Portable backups and immutable receipts are exported separately.')

    def t(self, es, en, pt):
        return {'es': es, 'en': en, 'pt': pt}[self.language]

    def configure(self, directory):
        super().configure(directory)
        self.slug = 'grupo-atlas-acceptance'

    def flush(self, complete=False):
        value = dict(schema='report-gen-atlas-api/1', version=shared.__version__,
                     method='Flask test client against actual API handlers; no HTTP or browser claims',
                     source=str(self.source), source_sha256=shared.digest(self.source / 'engagement.yaml'),
                     workspace=str(self.workspace), workspace_scope='isolated system temporary directory; no scratch mirror',
                     case_language=getattr(self, 'language', None), phases=getattr(self, 'phases', []), failure=getattr(self, 'failure', None),
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
                   dict(profile='executive', finding_uids=selected, title=self.t('Grupo Atlas — resumen ejecutivo ficticio', 'Atlas Group — fictional executive summary', 'Grupo Atlas — resumo executivo fictício')),
                   dict(profile='public', finding_uids=selected, title=self.t('Servicios financieros ficticios — lecciones de control', 'Fictional financial services — control lessons', 'Serviços financeiros fictícios — lições de controle'), client_alias=self.t('Organización financiera ficticia', 'Fictional financial organization', 'Organização financeira fictícia'),
                        aliases=[dict(needle='Atlas', replacement=self.t('Organización de simulación', 'Simulation organization', 'Organização de simulação'))], review_confirmed=True,
                        publish_consent=True, provenance_label='simulation', approved_content=[dict(finding_uid=row['uid'], title=self.t('Lección ficticia ', 'Fictional lesson ', 'Lição fictícia ') + str(n),
                            summary=self.t('Modelo inventado que relaciona autorización, expediente y versión. No hubo contacto con una empresa.', 'Invented model connecting authorization, case records and versions. No company was contacted.', 'Modelo inventado que relaciona autorização, registros e versões. Nenhuma empresa foi contatada.'),
                            impact=self.t('El escenario podría producir una decisión incoherente; no acredita una vulnerabilidad real.', 'The scenario could produce an inconsistent decision; it does not establish a real vulnerability.', 'O cenário poderia produzir uma decisão incoerente; ele não comprova uma vulnerabilidade real.'),
                            remediation=self.t('Definir una decisión explícita y conservar pruebas positivas, negativas y límites.', 'Define an explicit decision and retain positive and negative tests and limitations.', 'Defina uma decisão explícita e preserve testes positivos, negativos e limitações.')) for n, row in enumerate(baseline['findings'][:3], 1)])]
        before = (self.project / 'engagement.yaml').read_bytes()
        for options_row in options:
            profile = options_row['profile']
            preview = self.project_call('POST', '/audiences/preview', body=options_row).get_json()
            self.write_json('audiences/' + profile + '-preview.json', preview)
            self.check(profile + ' audience has no structural errors', not any(row['level'] == 'error' for row in preview['issues']))
            if profile == 'public':
                self.project_call('POST', '/audiences/export', body={**options_row, 'publish_consent': False, 'formats': ['pdf'], 'label': self.t('Publicación bloqueada', 'Publication blocked', 'Publicação bloqueada'), 'acknowledge_warnings': True}, expected=422)
                self.check('Withheld public consent preserves source', before == (self.project / 'engagement.yaml').read_bytes())
            response = self.project_call('POST', '/audiences/export', body={**options_row, 'formats': ['pdf', 'docx', 'html', 'md'], 'label': self.t('Grupo Atlas — ', 'Atlas Group — ', 'Grupo Atlas — ') + profile, 'acknowledge_warnings': True})
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
            if profile == 'public':
                self.signed_delivery(path)
        self.visual(self.out / 'audiences/executive.pdf')

    def imports_and_locations(self, inputs):
        # Scanner fixtures intentionally retain their authored Spanish. Apply
        # them to a disposable project so later localized owner deliveries do
        # not inherit untranslated scanner prose.
        original_slug = self.slug
        original_project = self.project
        self.slug = 'atlas-scanner-fixtures-' + self.language
        shutil.copytree(original_project, self.project)
        try:
            self._imports_and_locations(inputs)
            self.write('imports/applied-fixtures-project.zip', self.project_call('GET', '/bundle').data)
        finally:
            self.slug = original_slug
        self.limits.append('Synthetic scanner inputs retain their authored Spanish in a separate disposable project; they are not part of localized report or owner deliveries.')

    def _imports_and_locations(self, inputs):
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
            ('nuclei', json.dumps({'template-id': 'gml', 'matched-at': 'https://edi.atlas.example', 'info': {'name': 'Primero', 'severity': 'low'}}) + '\n\n' + json.dumps({'template-id': 'gml2', 'matched-at': 'https://edi.atlas.example', 'info': {'name': 'Segundo', 'severity': {'credential': 'ATLAS_PRIVATE_DIAGNOSTIC_CANARY'}}}), dict(operation='import', format='nuclei', record=2, line=3, field='info.severity')),
            ('nmap', '<nmaprun>\n<host><address addr="192.0.2.1" addrtype="ipv4"/></host>\n<host><address addr="192.0.2.2" addrtype="ipv4"/>\n<ports>\n<port portid="65536" protocol="tcp"><state state="open"/></port>\n</ports></host></nmaprun>', dict(operation='import', format='nmap', record=2, line=5, field='ports.port')),
        ]
        sarif = json.loads((inputs / 'sarif.json').read_text())
        sarif['runs'][0]['results'].append(deepcopy(sarif['runs'][0]['results'][0]))
        sarif['runs'][0]['results'][1]['locations'][0]['physicalLocation']['region']['endLine'] = 3
        negatives.append(('sarif', json.dumps(sarif), dict(operation='import', format='sarif', record=2, run_index=0, result_index=1, field='region.endLine')))
        for kind, raw, location in negatives:
            result = self.project_call('POST', '/intake/preview', body=dict(format=kind, text=raw), expected=422).get_json()
            self.check(kind + ' parser returns exact structural location', result['diagnostics'][0]['location'] == location, result['diagnostics'])
            self.check(kind + ' diagnostic excludes supplied private values', 'ATLAS_PRIVATE_DIAGNOSTIC_CANARY' not in json.dumps(result['diagnostics']))
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
                self.check('Burp CDATA reference survives application and reload', 'https://docs.atlas.example/import/burp#revisión' in row['references'])

    def pdf_annex(self, pdf):
        raw = pdf.read_bytes()
        original_hash = sha256(raw).hexdigest()
        name = 'atlas-informe-nativo-para-inspeccion.pdf'
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
        job = self.project_call('POST', '/jobs', body=dict(kind='export', formats=['docx'], label=self.t('Atlas — DOCX de vista nativa', 'Atlas — native DOCX preview', 'Atlas — prévia nativa do DOCX'), acknowledge_warnings=True), expected=202).get_json()
        status = self.wait_status('/api/jobs/' + job['id'], {'done', 'error', 'cancelled'})
        self.check('Native DOCX export completes', status['stage'] == 'done', status)
        raw = self.call('GET', '/api/jobs/' + job['id'] + '/download').data
        self.write('docx/atlas-queued.docx', raw)
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


    def source_and_history(self):
        data = self.load()
        self.check('Broad input has at least 20 findings', len(data['findings']) >= 20,
                   len(data['findings']))
        self.initial = deepcopy(data)
        if self.ui_bundle:
            self.ui_bundle.parent.mkdir(parents=True, exist_ok=True)
            self.ui_bundle.write_bytes(self.project_call('GET', '/bundle').data)
        self.project_call('POST', '/management', body={'archived': True, 'delivery_date': '2026-12-31'})
        self.project_call('POST', '/management', body={'archived': False})
        self.save(data)
        self.baseline = self.project_call('POST', '/history', body={
            'label': self.t('Grupo Atlas · entrega ficticia inicial', 'Atlas Group · initial fictional delivery', 'Grupo Atlas · entrega fictícia inicial'), 'stage': 'delivered'}).get_json()
        self.write_json('source-summary.json', {key: len(data.get(key, [])) for key in
                        ('findings', 'assets', 'coverage', 'evidence', 'root_cause_groups', 'attachments')})
        changed = deepcopy(data)
        changed['meta']['report_subtitle'] = self.t('Ciclo de vida ficticio · revisión de aceptación API', 'Fictional lifecycle · API acceptance review', 'Ciclo de vida fictício · revisão de aceitação da API')
        self.save(changed)
        compared = self.project_call('GET', '/history/' + self.baseline['id'] + '/compare').get_json()
        self.write_json('history-diff.json', compared)
        self.project_call('POST', '/history/' + self.baseline['id'] + '/restore', body={})
        self.check('Restoring delivered checkpoint restores document exactly', self.load() == data)
        before = (self.project / 'engagement.yaml').read_bytes()
        try:
            with project_history.transaction(self.project) as staged:
                atomic_write(staged / 'engagement.yaml', b'interrupted synthetic staging')
                raise RuntimeError('intentional precommit interruption')
        except RuntimeError:
            pass
        project_history.recover_transactions(api.PROJECTS)
        self.check('Interrupted staging rollback preserves exact saved project',
                   (self.project / 'engagement.yaml').read_bytes() == before)
        self.project_call('POST', '/draft-check', body=data)


    def evidence_and_inbox(self):
        from PIL import Image
        data = self.load()
        source = self.project / data['evidence'][0]['src']
        upload = self.project_call('POST', '/image', data={'file': (BytesIO(source.read_bytes()), 'atlas-annotation.png')}).get_json()
        self.project_call('POST', '/evidence', body={'src': upload['src'], 'title': self.t('Copia sintética para anotación y censura', 'Synthetic copy for annotation and redaction', 'Cópia sintética para anotação e ocultação')})
        entry = next(row for row in self.load()['evidence'] if row['src'] == upload['src'])
        original = self.project_call('GET', '/evidence/' + entry['uid'] + '/original').data
        operations = [dict(type='box', x=.05, y=.05, w=.8, h=.6),
                      dict(type='arrow', x=.05, y=.05, w=.3, h=.3),
                      dict(type='text', x=.1, y=.7, w=.7, h=.15, text=self.t('SIMULACION · EVIDENCIA FICTICIA', 'SIMULATION · FICTIONAL EVIDENCE', 'SIMULAÇÃO · EVIDÊNCIA FICTÍCIA')),
                      dict(type='redact', x=.2, y=.2, w=.2, h=.2)]
        edited = self.project_call('POST', '/evidence/' + entry['uid'] + '/edit', body={'operations': operations}).get_json()['data']
        entry = next(row for row in edited['evidence'] if row['uid'] == entry['uid'])
        with Image.open(self.project / entry['src']) as pixels:
            self.check('Redaction produces opaque black pixels', pixels.convert('RGB').getpixel((int(pixels.width*.3), int(pixels.height*.3))) == (0, 0, 0))
            self.check('Annotated derivative drops source metadata', not pixels.info)
        self.check('Original evidence remains exact after four annotation kinds',
                   self.project_call('GET', '/evidence/' + entry['uid'] + '/original').data == original)
        finding = edited['findings'][0]
        for kind, content in [('note', self.t('Nota de simulación: autorización revisada para el escenario ficticio.', 'Simulation note: authorization reviewed for the fictional scenario.', 'Nota de simulação: autorização revisada para o cenário fictício.')),
                              ('command', 'printf "%s\\n" "SIMULACION ATLAS"'),
                              ('http', 'GET /synthetic HTTP/1.1\r\nHost: banco.atlas.test\r\n\r\n'),
                              ('image', '')]:
            body = dict(kind=kind, title=self.t('Captura ficticia ', 'Fictional capture ', 'Captura fictícia ') + kind, note=self.t('Entrada de aceptación, sin datos reales.', 'Acceptance input with no real data.', 'Entrada de aceitação sem dados reais.'))
            body['src' if kind == 'image' else 'raw_text'] = entry['src'] if kind == 'image' else content
            captured = self.project_call('POST', '/captures', body=body).get_json()
            self.project_call('POST', '/captures/' + captured['capture_uid'] + '/link', body={'finding_uid': finding['uid']})
        self.check('All four captured kinds linked explicitly',
                   {row['kind'] for row in self.load()['capture_inbox'] if row.get('finding_uid') == finding['uid']} >= {'note', 'command', 'http', 'image'})
        self.project_call('POST', '/captures', body={'kind': 'note', 'title': self.t('Nota privada no incorporada', 'Private note not included', 'Nota privada não incorporada'),
            'note': self.t('Sólo para comprobar exclusión', 'Only to check exclusion', 'Somente para verificar a exclusão'), 'raw_text': builder.UNLINKED_MARKER})
        publication = self.project_call('GET', '/publication').get_json()
        self.write_json('publication-inspector.json', publication)
        ocr = self.project_call('POST', '/privacy/ocr', body={'name': entry['src']}).get_json()
        self.write_json('ocr-result.json', ocr)
        self.check('OCR binds current derivative and exposes no extracted text', 'text' not in ocr and ocr['manual_review_required'] is True)
        if ocr['status'] != 'completed':
            self.limits.append('OCR engine did not complete: ' + ocr['status'])
        inventory = self.project_call('GET', '/privacy').get_json()
        self.write_json('private-retention-inventory.json', inventory)
        annex = b'control,result\nsynthetic-review,documented\n'
        self.project_call('POST', '/attachments/declare', body={'name': 'atlas-lifecycle-evidence.csv', 'required': True})
        pending = self.project_call('GET', '/attachments').get_json()['files']
        self.check('Required annex is explicitly missing before upload', any(row['name'] == 'atlas-lifecycle-evidence.csv' and row['status'] == 'declared' and row['required'] for row in pending))
        uploaded = self.project_call('POST', '/attachments/upload', data={
            'file': (BytesIO(annex), 'atlas-lifecycle-evidence.csv')}).get_json()['data']
        row = next(item for item in uploaded['attachments'] if item['name'] == 'atlas-lifecycle-evidence.csv')
        self.check('Uploaded annex is private and unreviewed by default', row['include'] is False and row['reviewed'] is False)
        self.write_json('annex-scan.json', self.project_call('GET', '/attachments/scan?uid=' + row['uid']).get_json())
        row.update(include=True, reviewed=True)
        self.save(uploaded)
        self.project_call('GET', '/attachments')


    def libraries(self):
        data = self.load()
        tag = self.call('GET', '/api/library').headers['ETag']
        content = self.call('POST', '/api/library/sanitize', body={'finding': data['findings'][0], 'context': {}}).get_json()['content']
        template = self.call('POST', '/api/library', body={'name': self.t('Grupo Atlas · patrón ficticio reutilizable', 'Atlas Group · reusable fictional pattern', 'Grupo Atlas · padrão fictício reutilizável'), 'content': content},
                             headers={'If-Match': tag}).get_json()
        instance = self.call('POST', '/api/library/' + template['uid'] + '/instantiate', body={'values': {}}).get_json()
        self.check('Reusable finding strips project-owned evidence links', not instance.get('evidence_uids'))
        self.call('PUT', '/api/library/' + template['uid'], body={'name': self.t('Grupo Atlas · patrón revisado', 'Atlas Group · revised pattern', 'Grupo Atlas · padrão revisado'), 'content': content},
                  headers={'If-Match': self.call('GET', '/api/library').headers['ETag']})
        exported = self.call('GET', '/api/library')
        self.call('POST', '/api/library/import', body=exported.get_json(), headers={'If-Match': exported.headers['ETag']})
        candidates = self.call('GET', '/api/library')
        extra = next(row for row in candidates.get_json()['templates'] if row['uid'] != template['uid'])
        self.call('DELETE', '/api/library/' + extra['uid'], headers={'If-Match': candidates.headers['ETag']})
        catalog = self.call('GET', '/api/design-library')
        profile = design_library.profile('htb-cpts')
        personal = self.call('POST', '/api/design-library/personal', body={
            'name': self.t('Atlas · diseño personal ficticio', 'Atlas · fictional personal design', 'Atlas · design pessoal fictício'), 'design': design_library.appearance(profile, 'quiet'),
            'sections': profile['sections']}, headers={'If-Match': catalog.headers['ETag']}).get_json()
        before = deepcopy(self.load())
        changed = self.project_call('POST', '/design', body={'id': personal['id']}).get_json()['data']
        self.check('Personal design changes preserve all findings', changed['findings'] == before['findings'])
        self.save(before)
        catalog = self.call('GET', '/api/design-library')
        revised = self.call('PUT', '/api/design-library/personal/' + personal['id'], body={
            'name': self.t('Atlas · diseño personal revisado', 'Atlas · revised personal design', 'Atlas · design pessoal revisado'), 'design': personal['design'], 'sections': personal['sections']},
            headers={'If-Match': catalog.headers['ETag']}).get_json()
        self.check('Personal template edit increments its revision', revised['revision'] == personal['revision'] + 1)
        catalog = self.call('GET', '/api/design-library')
        disposable = self.call('POST', '/api/design-library/personal', body={
            'name': self.t('Atlas · plantilla desechable', 'Atlas · disposable template', 'Atlas · modelo descartável'), 'design': personal['design'], 'sections': personal['sections']},
            headers={'If-Match': catalog.headers['ETag']})
        self.call('DELETE', '/api/design-library/personal/' + disposable.get_json()['id'],
                  headers={'If-Match': disposable.headers['ETag']})
        self.write_json('personal-design.json', personal)
        self.write_json('reusable-finding.json', template)


    def insights_and_remediation(self):
        data = self.load()
        uid = data['findings'][0]['uid']
        evidence_uid = data['evidence'][0]['uid']
        self.project_call('POST', '/insights', body={'action': 'set_claim', 'finding_uid': uid,
            'statement': self.t('La evidencia sintética permite reproducir el escenario descrito.', 'The synthetic evidence supports reproduction of the described scenario.', 'A evidência sintética permite reproduzir o cenário descrito.'), 'kind': 'observed',
            'demonstrates': self.t('Comportamiento modelado dentro del ejercicio ficticio.', 'Behavior modeled within the fictional exercise.', 'Comportamento modelado no exercício fictício.'),
            'does_not_demonstrate': self.t('No demuestra una vulnerabilidad real ni compromiso de una entidad bancaria.', 'It does not establish a real vulnerability or compromise of a banking entity.', 'Não comprova uma vulnerabilidade real nem o comprometimento de uma entidade bancária.'),
            'evidence_uids': [evidence_uid]})
        risk = next((row for row in data.get('insights', {}).get('risks', []) if row['finding_uid'] == uid), None)
        risk_body = dict(action='set_risk', finding_uid=uid, service=self.t('Banca digital ficticia', 'Fictional digital banking', 'Serviços bancários digitais fictícios'),
            objective=self.t('Integridad de operaciones del escenario', 'Integrity of scenario operations', 'Integridade das operações do cenário'), consequence=self.t('Pérdida de trazabilidad simulada', 'Simulated loss of traceability', 'Perda simulada de rastreabilidade'),
            tolerance=self.t('No acordado', 'Not agreed', 'Não acordado'), source=self.t('Criterio ficticio del ejercicio de aceptación', 'Fictional criterion of the acceptance exercise', 'Critério fictício do exercício de aceitação'),
            assumptions=self.t('No se evaluó ninguna entidad real', 'No real entity was assessed', 'Nenhuma entidade real foi avaliada'), priority='P1',
            rationale=self.t('El ejercicio modela un proceso crítico y reversibilidad limitada', 'The exercise models a critical process with limited reversibility', 'O exercício modela um processo crítico com reversibilidade limitada'), owner=self.t('Comité ficticio de riesgo', 'Fictional risk committee', 'Comitê fictício de risco'))
        if risk:
            risk_body['uid'] = risk['uid']
        self.project_call('POST', '/insights', body=risk_body)
        comment = self.project_call('POST', '/insights', body={'action': 'add_comment', 'finding_uid': uid,
            'field': 'description_md', 'body': self.t('Confirmar que la naturaleza ficticia siga visible.', 'Confirm that the fictional nature remains visible.', 'Confirme que a natureza fictícia continue visível.'),
            'author': self.t('Revisor sintético de aceptación', 'Synthetic acceptance reviewer', 'Revisor sintético de aceitação'), 'visibility': 'private'}).get_json()['data']['insights']['comments'][-1]
        self.project_call('POST', '/insights', body={'action': 'resolve_comment', 'uid': comment['uid'],
            'resolution': self.t('Contexto de simulación presente en portada, resumen y hallazgos.', 'Simulation context appears on the cover, summary and findings.', 'O contexto de simulação está presente na capa, no resumo e nos achados.'), 'author': self.t('Revisor sintético de aceptación', 'Synthetic acceptance reviewer', 'Revisor sintético de aceitação')})
        self.project_call('POST', '/insights', body={'action': 'review', 'decision': 'changes_requested',
            'author': self.t('RECORRIDO AUTOMATIZADO DE PRUEBA', 'AUTOMATED TEST JOURNEY', 'PERCURSO DE TESTE AUTOMATIZADO'), 'notes': self.t('Registro de prueba de la API; no es una aprobación humana del informe.', 'API test record; this is not human approval of the report.', 'Registro de teste da API; isto não é uma aprovação humana do relatório.')})
        self.write_json('insights.json', self.project_call('GET', '/insights').get_json())
        self.project_call('GET', '/insights/editorial')
        data = self.load()
        selected = [row['uid'] for row in data['findings'][:3]]
        values = {'owner': self.t('Equipo ficticio de remediación transversal', 'Fictional cross-functional remediation team', 'Equipe fictícia de correção transversal'), 'due_date': '2026-12-18'}
        if data.get('root_cause_groups'):
            values['root_cause_uid'] = data['root_cause_groups'][0]['uid']
        body = dict(finding_uids=selected, values=values)
        preview = self.project_call('POST', '/bulk-edit/preview', body=body).get_json()
        self.project_call('POST', '/bulk-edit/apply', body={**body, 'preview_token': preview['preview_token'], 'ack_reviewed': True})
        self.project_call('POST', '/bulk-edit/apply', body={**body, 'preview_token': preview['preview_token'], 'ack_reviewed': True}, expected=409)
        data = self.load()
        data['findings'][2]['owner'] = '=SYNTHETIC_FORMULA(1)'
        self.save(data)
        options = dict(fields=list(remediation_tasks.FIELDS), lang=self.language, ack_private=True)
        preview = self.project_call('POST', '/remediation-tasks/preview', body=options).get_json()
        self.check('Task projection retains one row per finding', len(preview['rows']) == len(self.load()['findings']))
        for fmt in ('csv', 'cards'):
            response = self.project_call('POST', '/remediation-tasks/export', body={**options, 'format': fmt, 'preview_token': preview['preview_token']})
            self.write('remediation-tasks.' + ('csv' if fmt == 'csv' else 'zip'), response.data)
        issued = self.project_call('POST', '/remediation-tasks/return-template', body={
            'finding_uids': selected, 'ack_private': True, 'ack_retention': True})
        self.write('remediation-return-issued.csv', issued.data)
        rows = list(csv.reader(StringIO(issued.data.decode('utf-8-sig'))))
        rows[1][rows[0].index('owner')] = self.t("'Responsable ficticio actualizado", "'Updated fictional owner", "'Responsável fictício atualizado")
        rows[1][rows[0].index('reported_remediation')] = self.t("'Ajuste comunicado en simulación; falta verificación independiente.", "'Change reported in simulation; independent verification is still required.", "'Ajuste comunicado na simulação; ainda é necessária verificação independente.")
        stream = StringIO(newline='')
        csv.writer(stream, quoting=csv.QUOTE_ALL, lineterminator='\r\n').writerows(rows)
        text = '\ufeff' + stream.getvalue()
        self.write('remediation-return-proposal.csv', text.encode())
        before = deepcopy(self.load()['findings'][0])
        proposal = self.project_call('POST', '/remediation-tasks/return-preview', body={'text': text}).get_json()
        self.project_call('POST', '/remediation-tasks/return-receive', body={
            'text': text, 'preview_token': proposal['preview_token'], 'ack_reviewed': True})
        proposal = self.project_call('POST', '/remediation-tasks/return-preview', body={'text': text}).get_json()
        self.project_call('POST', '/remediation-tasks/return-apply', body={
            'text': text, 'preview_token': proposal['preview_token'],
            'selected': [row['key'] for row in proposal['changes']], 'ack_reviewed': True})
        after = self.load()['findings'][0]
        self.check('Owner return does not assert a fix or modify technical verification',
                   after.get('status') == before.get('status') and after.get('verification') == before.get('verification'))
        batch = rows[1][rows[0].index('batch_uid')]
        self.project_call('POST', '/remediation-tasks/return-revoke', body={'batch_uid': batch, 'ack_reviewed': True})
        self.project_call('POST', '/remediation-tasks/return-preview', body={'text': text}, expected=422)
        delivery_options = dict(finding_uids=selected, **options, ack_retention=True)
        preview = self.project_call('POST', '/remediation-tasks/delivery-preview', body=delivery_options).get_json()
        self.write('remediation-owner-delivery.zip', self.project_call('POST', '/remediation-tasks/delivery-export',
                   body={**delivery_options, 'preview_token': preview['preview_token']}).data)
        self.project_call('POST', '/retest', body={'finding_uid': uid, 'tested_on': '2026-10-16',
            'assessor': self.t('Evaluador ficticio de aceptación', 'Fictional acceptance assessor', 'Avaliador fictício de aceitação'), 'result': 'not_verified',
            'notes_md': self.t('Registro de prueba documental; no se ejecutó un pentest ni se acredita corrección real.', 'Documentary test record; no pentest was performed and no real remediation is certified.', 'Registro de teste documental; nenhum pentest foi executado e nenhuma correção real é certificada.'),
            'evidence_uids': [evidence_uid]})
        for finding, outcome in zip(self.load()['findings'][1:4], ('fixed', 'open', 'partial')):
            self.project_call('POST', '/retest', body={'finding_uid': finding['uid'], 'tested_on': '2026-10-16',
                'assessor': self.t('PERSONAJE FICTICIO DEL ESCENARIO', 'FICTIONAL SCENARIO CHARACTER', 'PERSONAGEM FICTÍCIO DO CENÁRIO'), 'result': outcome,
                'notes_md': self.t('Estado perteneciente exclusivamente al guion sintético. No acredita evaluación de una entidad real.', 'Status belonging exclusively to the synthetic scenario. It does not establish assessment of a real entity.', 'Estado pertencente exclusivamente ao roteiro sintético. Não comprova avaliação de uma entidade real.'),
                'evidence_uids': [evidence_uid]})
        self.write_json('retest-matrix.json', self.project_call('GET', '/retest-matrix').get_json())
        self.write_json('retest-diff.json', self.project_call('GET', '/retest-diff').get_json())
        self.write('history-comparison.html', self.project_call('GET', '/history/' + self.baseline['id'] + '/visual').data)
        self.check('Content edits mark the earlier editorial decision stale', self.project_call('GET', '/insights').get_json()['review_status']['state'] == 'stale')


    def signed_delivery(self, source):
        public = self.out / 'audiences/acceptance-public.pem'
        signature = self.out / 'audiences/public-delivery.signature.json'
        # CI writes receipts inside the checkout. Signing keys must instead live
        # outside both report-gen and all project/output trees, even on failure.
        with tempfile.TemporaryDirectory(prefix='report-gen-atlas-signing-') as directory:
            private = Path(directory).resolve() / 'acceptance-private.pem'
            self.check('Private signing key location is outside checkout, project workspace and outputs',
                       not any(private.is_relative_to(base.resolve()) for base in (ROOT, self.workspace, self.out))
                       and not any((parent / 'engagement.yaml').exists() for parent in private.parents))
            delivery_signature.generate_keypair(private, public)
            delivery_signature.sign_delivery(source, private, signature)
            for path in (public, signature):
                self.artifacts.append(dict(name=path.relative_to(self.out).as_posix(), bytes=path.stat().st_size,
                                           sha256=digest(path)))
            verified = delivery_signature.verify_delivery(source, signature, public)
            self.check('Real Ed25519 signature verifies exact emitted ZIP and manifest', verified['verified'])
            self.write_json('audiences/signature-verification.json', verified)
            tampered = self.workspace / 'tampered.zip'
            tampered.write_bytes(source.read_bytes() + b'altered')
            rejected = False
            try:
                delivery_signature.verify_delivery(tampered, signature, public)
            except ValueError:
                rejected = True
            self.check('Detached signature rejects an appended archive suffix', rejected)
            private_bytes = private.read_bytes()
            with zipfile.ZipFile(source) as package:
                absent = all(private_bytes not in package.read(entry)
                             and 'PRIVATE KEY' not in entry.filename for entry in package.infolist())
            self.check('Private signing key is mode 0600 and never enters public deliverables',
                       private.stat().st_mode & 0o777 == 0o600 and absent
                       and all(private_bytes not in path.read_bytes() for path in (public, signature)))
        self.check('Temporary signing key is deleted after verification', not private.exists() and not Path(directory).exists())


    def visual(self, path):
        response = self.project_call('POST', '/visual', data={'file': (BytesIO(path.read_bytes()), path.name)})
        metadata = response.get_json()
        self.write_json('visual-metadata.json', metadata)
        key = metadata['id']
        self.check('PDF visual preview binds exact emitted bytes', metadata['pdf_sha256'] == digest(path))
        self.write('visual-first-page.png', self.call('GET', '/api/visual/' + key + '/page/1').data)
        # Automated API traversal must not create a purported human approval.
        self.check('Automated traversal leaves manual visual review unclaimed', metadata['review'] is None)
        self.call('DELETE', '/api/visual/' + key, body={})
        self.limits.append('PDF thumbnail/API traversal completed; no human review was fabricated by this script.')


    def backups(self):
        self.project_call('POST', '/history', body={'label': self.t('Grupo Atlas · ciclo de vida completo', 'Atlas Group · complete lifecycle', 'Grupo Atlas · ciclo de vida completo'), 'stage': 'retest'})
        bundle = self.project_call('GET', '/bundle').data
        self.write('grupo-atlas-lifecycle-project.zip', bundle)
        expected = deepcopy(self.load())
        imported = self.call('POST', '/api/projects/import', data={
            'file': (BytesIO(bundle), 'atlas-project.zip'), 'slug': 'atlas-reimported'}).get_json()
        self.check('Native project ZIP restores exact document', self.call('GET', '/api/projects/' + imported['slug']).get_json() == expected)
        plain = self.call('POST', '/api/workspace/backup', body={}).data
        self.write('workspace-plain.zip', plain)
        password = secrets.token_urlsafe(32)
        encrypted = self.call('POST', '/api/workspace/backup/encrypted', body={'password': password}).data
        self.write('workspace-encrypted.rgbackup', encrypted)
        backup_dir = self.workspace.parent / 'scheduled-backups'
        backup_dir.mkdir(exist_ok=True)
        self.call('PUT', '/api/workspace/backup-routine', body={'enabled': True, 'destination': str(backup_dir),
            'interval_seconds': 3600, 'retention': 2, 'ack_unencrypted': True})
        run = self.call('POST', '/api/workspace/backup-routine/run', body={}).get_json()
        first_archive = Path(run['directory']) / run['latest_name']
        self.call('POST', '/api/workspace/backup-routine/run', body={})
        latest = self.call('POST', '/api/workspace/backup-routine/run', body={}).get_json()
        self.check('Routine rotation retains two owned backups', latest['copies'] == 2 and not first_archive.exists())
        verified = self.call('POST', '/api/workspace/backup-routine/verify', body={}).get_json()
        self.check('Scheduled backup verifies latest exact archive digest', latest['latest_sha256'] == verified['latest_sha256'])
        self.call('POST', '/api/workspace/backup-routine/disable', body={})
        for archive in sorted(Path(latest['directory']).glob('*.zip')):
            self.write('scheduled-backups/' + archive.name, archive.read_bytes())
        self.write_json('scheduled-backups/rotation-and-verification.json', dict(rotation=latest, verification=verified))
        self.configure(self.workspace / 'wrong-password-restore')
        self.call('POST', '/api/workspace/restore', data={'file': (BytesIO(encrypted), 'workspace.rgbackup'),
            'password': 'intentionally-incorrect-synthetic-password'}, expected=422)
        self.check('Wrong backup password leaves target workspace empty', not list(api.PROJECTS.iterdir()))
        for label, blob, secret in [('plain', plain, ''), ('encrypted', encrypted, password)]:
            destination = self.workspace / ('restore-' + label)
            self.configure(destination)
            form = {'file': (BytesIO(blob), 'workspace.' + ('rgbackup' if secret else 'zip'))}
            if secret:
                form['password'] = secret
            result = self.call('POST', '/api/workspace/restore', data=form).get_json()
            self.check(label + ' workspace backup restores project exactly', self.load() == expected)
            self.check(label + ' workspace backup restores both personal libraries',
                       len(self.call('GET', '/api/library').get_json()['templates']) >= 1 and
                       len(self.call('GET', '/api/design-library').get_json()['personal']) >= 1)
            self.write_json('restore-' + label + '.json', result)
        self.configure(self.workspace)
        # Pruning is exercised only after making/restoring portable backups and in a disposable copy.
        original_slug = self.slug
        self.slug = 'atlas-pruning-copy'
        shutil.copytree(api.PROJECTS / original_slug, self.project)
        inventory = self.project_call('GET', '/privacy').get_json()
        self.project_call('POST', '/privacy/prune', body={'categories': ['history'],
            'inventory_revision': inventory['inventory_revision'], 'confirm_project': self.slug})
        self.check('Pruning a throwaway history preserves current report', self.load() == expected)
        self.slug = original_slug
        self.limits.append('Encrypted backup used an ephemeral test password; the plain backup is the portable recovery artifact.')
        self.limits.append('Backup routine enabled/run/rotation/verify/disable exercised; one-hour wall-clock scheduling was not waited out.')


    def diagnostics(self):
        report = self.call('POST', '/api/diagnostics', body={'lang': self.language}).get_json()
        safe = self.call('POST', '/api/diagnostics/download', body={'report': report['support_report'], 'preview_token': report['support_token']})
        self.write('diagnostics-sanitized.json', safe.data)
        content = safe.data.decode()
        self.check('Support diagnostic excludes case identity and private paths',
                   'Atlas' not in content and str(self.workspace) not in content and str(self.source) not in content)
        capabilities = self.call('GET', '/api/assistant/capabilities').get_json()
        self.check('Optional assistant does not auto-send case content', capabilities['auto_send'] is False and capabilities['connected'] is False)
        self.limits.append('Ollama inference not claimed: this run verifies explicit opt-in capability without sending the banking case to a model.')
        response = self.client.post('/api/assistant/models', json={})
        self.check('Real local model probe returns a bounded response', response.status_code in (200, 422), response.get_json())
        self.write_json('assistant-model-probe.json', {'status': response.status_code, 'body': response.get_json()})
        self.call('POST', '/api/update/check', body={'allow_network': False}, expected=422)
        self.limits.append('Updater opt-in guard checked; preparing a newer published version is outside this unpublished-candidate acceptance run.')


    def catalogs_and_scores(self):
        from sections import load_presets
        for route in ('/api/sections/catalog', '/api/designs', '/api/export-formats', '/api/cwe', '/api/presets',
                      '/api/owasp/web', '/api/owasp/llm', '/api/visual/capabilities', '/api/pdf-compare/capabilities'):
            response = self.call('GET', route)
            self.write_json('catalogs/' + route.strip('/').replace('/', '-') + '.json', response.get_json())
        for version, vector in (
            ('3.1', 'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'),
            ('4.0', 'CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:H/SI:H/SA:H')):
            value = self.call('POST', '/api/cvss', body=dict(version=version, vector=vector)).get_json()
            self.check('CVSS ' + version + ' calculates a bounded score', 0 <= value['score'] <= 10, value)
            self.write_json('catalogs/cvss-' + version + '.json', value)
        self.call('POST', '/api/cvss', body=dict(version='3.1', vector='CVSS:4.0/AV:N'), expected=400)
        for preset in load_presets():
            slug = 'atlas-preset-' + self.language + '-' + preset['id']
            created = self.call('POST', '/api/projects', body=dict(slug=slug, title='Atlas preset probe',
                preset=preset['id'], model='corporativo-' + self.language)).get_json()
            data = self.call('GET', '/api/projects/' + created['slug']).get_json()
            self.check('Preset ' + preset['id'] + ' creates a reloadable localized project', data['meta']['lang'] == self.language)
        self.limits.append('Preset starting points were created and reloaded; authoring placeholders are not counted as completed reports.')

    def comparison(self):
        import pdf_compare
        raw = (self.out / 'audiences/executive.pdf').read_bytes()
        before = (self.project / 'engagement.yaml').read_bytes()
        def request(extra=None):
            return dict(before=(BytesIO(raw), 'atlas-before.pdf'), after=(BytesIO(raw), 'atlas-after.pdf'),
                        language=self.language, **(extra or {}))
        metadata = self.call('POST', '/api/pdf-compare/metadata', data=request()).get_json()
        self.write_json('comparison/metadata.json', metadata)
        positional_response = self.call('POST', '/api/pdf-compare', data=request())
        positional = positional_response.data
        self.write('comparison/identical-positional.html', positional)
        receipt = pdf_compare.comparison_manifest(positional)
        self.check('Identical report-gen PDF comparison binds exact bytes and no semantic approval',
                   receipt['identical_pdf_bytes'] and receipt['before_sha256'] == sha256(raw).hexdigest()
                   and receipt['semantic_equivalence_verified'] is False)
        self.check('Identical PDF has no pixel differences', all(row['changed_pixels'] == 0 for row in receipt['pages']))
        count = metadata['before']['page_count'] if 'page_count' in metadata['before'] else len(metadata['before']['pages'])
        pairs = [dict(before=n, after=n) for n in range(1, count + 1)]
        manual = self.call('POST', '/api/pdf-compare', data=request(dict(page_pairs=json.dumps(pairs),
                          expected_before_sha256=sha256(raw).hexdigest(), expected_after_sha256=sha256(raw).hexdigest()))).data
        self.write('comparison/identical-manual.html', manual)
        manual_receipt = pdf_compare.comparison_manifest(manual)
        self.check('Explicit pairing covers every source page exactly once', manual_receipt['pairing_mode'] == 'manual'
                   and len(manual_receipt['pages']) == count)
        self.call('POST', '/api/pdf-compare', data=request(dict(page_pairs=json.dumps(pairs),
                  expected_before_sha256='0' * 64, expected_after_sha256=sha256(raw).hexdigest())), expected=422)
        self.check('PDF comparisons preserve project and uploaded bytes', before == (self.project / 'engagement.yaml').read_bytes()
                   and (self.out / 'audiences/executive.pdf').read_bytes() == raw)
        comparison_id = positional_response.headers.get('X-Report-Gen-Comparison-Id')
        self.check('Comparison yields a session-owned metadata receipt', bool(comparison_id))
        temporary = self.call('GET', '/api/pdf-compare/receipts/' + comparison_id).get_json()
        self.write_json('comparison/temporary-receipt.json', temporary)
        saved = self.project_call('POST', '/pdf-comparisons', body=dict(comparison_id=comparison_id,
            author=self.t('RECORRIDO AUTOMATIZADO DE PRUEBA', 'AUTOMATED TEST JOURNEY', 'PERCURSO DE TESTE AUTOMATIZADO'),
            decision='issues', note=self.t('Registro sintético para probar persistencia; requiere revisión humana y no acredita un defecto visual.',
                'Synthetic persistence test record; human review is required and no visual defect is established.',
                'Registro sintético para testar a persistência; exige revisão humana e não comprova um defeito visual.')), expected=201).get_json()
        record = saved['record']
        self.check('Saved comparison is explicitly not a Word or semantic approval', record['decision'] == 'issues'
                   and record['original_word_verified'] is False and record['semantic_equivalence_verified'] is False)
        annex = next(row for row in saved['data']['attachments'] if row['uid'] == record['uid'])
        self.check('Saved comparison metadata remains private and unreviewed', annex['include'] is False and annex['reviewed'] is False)
        self.project_call('GET', '/pdf-comparisons')
        downloaded = self.project_call('GET', '/pdf-comparisons/' + record['uid']).data
        self.write('comparison/saved-test-record.json', downloaded)
        self.check('Saved comparison downloads the exact record', json.loads(downloaded) == record)
        self.call('DELETE', '/api/pdf-compare/receipts/' + comparison_id, expected=204)
        self.call('GET', '/api/pdf-compare/receipts/' + comparison_id, expected=404)
        self.limits.append('PDF comparison uses the native executive excerpt under the 80-page limit; it is not a full-report comparison or human approval.')


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
    journey.producer['scripts/audit-atlas-api.py'] = shared.digest(Path(__file__))
    journey.producer['scripts/audit-atlas-exports.py'] = shared.digest(ROOT / 'scripts/audit-atlas-exports.py')
    journey.phases = []
    try:
        baseline = journey.load()
        journey.language = baseline['meta']['lang']
        journey.client.environ_base['HTTP_X_UI_LANGUAGE'] = {'es': 'es', 'en': 'en', 'pt': 'pt-BR'}[journey.language]
        facts = atlas_exports.validate_atlas_case(baseline, journey.language)
        journey.check('Complete Atlas contract: 60 vulnerabilities, 7 machines, 28 assets and 84 evidence images', True, facts)
        phases = [
            ('catalogs_and_scores', journey.catalogs_and_scores),
            ('source_and_history', journey.source_and_history),
            ('audience_deliveries', lambda: journey.audience_deliveries(baseline)),
            ('docx_preview', lambda: journey.docx_preview(args.require_native or args.require_stable_native, args.require_stable_native)),
            ('pdf_annex', lambda: journey.pdf_annex(args.pdf)),
            ('imports_and_locations', lambda: journey.imports_and_locations(args.inputs)),
            ('evidence_and_inbox', journey.evidence_and_inbox),
            ('libraries', journey.libraries),
            ('insights_and_remediation', journey.insights_and_remediation),
            ('comparison', journey.comparison),
            ('backups', journey.backups),
            ('diagnostics', journey.diagnostics),
        ]
        for name, operation in phases:
            journey.phases.append(dict(name=name, status='running'))
            journey.flush()
            print(json.dumps(dict(phase=name, language=journey.language, status='running')), flush=True)
            operation()
            journey.phases[-1]['status'] = 'passed'
            journey.flush()
        journey.check('Original case files remain byte-identical', source_before == exports.hashes(args.case))
        journey.check('Report producer remains unchanged', producer == exports.producer_identity())
        journey.check('API sources remain unchanged', all((ROOT / name).is_file() and shared.digest(ROOT / name) == digest
                                                        for name, digest in journey.producer.items()))
        journey.flush(complete=True)
        print(json.dumps(dict(complete=True, language=journey.language, checks=len(journey.records))), flush=True)
        return 0
    except Exception as exc:
        if journey.phases and journey.phases[-1]['status'] == 'running':
            journey.phases[-1]['status'] = 'failed'
        journey.failure = dict(type=type(exc).__name__, message=str(exc))
        journey.flush(complete=False)
        raise
    finally:
        queue = shared.api.app.extensions.get('export_queue')
        if queue:
            queue.close()
        store = shared.api.app.extensions.get('docx_previews')
        if store:
            store.close()


if __name__ == '__main__':
    sys.exit(main())
