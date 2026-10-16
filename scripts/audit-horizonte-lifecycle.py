#!/usr/bin/env python3
"""Real local API acceptance of the fictional Banco Horizonte project.

No report is written by this harness: every HTML, PDF, DOCX, Markdown,
comparison and delivery is emitted by report-gen's existing APIs. Inputs,
receipts and assertions are the only authored material. All destructive
round-trips run in an isolated copy, never in the source project.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from hashlib import sha256
from io import BytesIO, StringIO
import json
from pathlib import Path
import secrets
import shutil
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'webapp')]

import app as api  # noqa: E402
import delivery_signature  # noqa: E402
import design_library  # noqa: E402
import project_history  # noqa: E402
import remediation_tasks  # noqa: E402
from storage import atomic_write, revision  # noqa: E402
from version import __version__  # noqa: E402


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


class Journey:
    def __init__(self, source, output, ui_bundle=None, pdf=None):
        self.source, self.out = source.resolve(), output.resolve()
        self.out.mkdir(parents=True, exist_ok=True)
        self.records, self.limits, self.artifacts = [], [], []
        self.started = time.time()
        self.producer = {p.relative_to(ROOT).as_posix(): digest(p) for p in sorted(ROOT.rglob('*'))
                         if p.is_file() and p.suffix in ('.py', '.html', '.css', '.yaml', '.json')
                         and p.parts[len(ROOT.parts)] in ('webapp', 'exporters', 'templates', 'themes', 'lang', 'designs')}
        self.producer.update({p.name: digest(p) for p in ROOT.glob('*.py')})
        self.producer['scripts/audit-horizonte-lifecycle.py'] = digest(Path(__file__))
        self.workspace = Path(tempfile.mkdtemp(prefix='workspace-', dir=self.out))
        self.slug = 'banco-horizonte-acceptance'
        self.configure(self.workspace)
        shutil.copytree(self.source, self.project)
        self.client = api.app.test_client()
        csrf = self.client.get('/api/session').get_json()['csrf']
        self.client.environ_base['HTTP_X_CSRF_TOKEN'] = csrf
        self.ui_bundle, self.pdf = ui_bundle, pdf

    @property
    def project(self):
        return api.PROJECTS / self.slug

    def configure(self, directory):
        api.PROJECTS = directory / 'projects'
        api.PROJECTS.mkdir(parents=True, exist_ok=True)
        api.app.config['LIBRARY_PATH'] = str(directory / 'library/findings.json')
        api.app.config['DESIGN_LIBRARY_PATH'] = str(directory / 'library/designs.json')

    def flush(self, complete=False):
        value = dict(schema='report-gen-horizonte-lifecycle/1', version=__version__,
                     method='Flask test client against real local API; no HTTP UI claims',
                     source=str(self.source), source_sha256=digest(self.source / 'engagement.yaml'),
                     workspace=str(self.workspace), complete=complete,
                     producer=self.producer,
                     elapsed_seconds=round(time.time() - self.started, 3),
                     checks=self.records, limitations=self.limits, artifacts=self.artifacts)
        self.write_json('results.json', value, register=False)

    def check(self, name, passed, detail=None):
        self.records.append(dict(name=name, passed=bool(passed), detail=detail))
        self.flush()
        if not passed:
            raise AssertionError(f'{name}: {detail}')

    def write(self, name, blob):
        path = self.out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(blob)
        self.artifacts.append(dict(name=name, bytes=len(blob), sha256=sha256(blob).hexdigest()))
        return path

    def write_json(self, name, value, register=True):
        blob = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
        return self.write(name, blob) if register else (self.out / name).write_bytes(blob)

    def call(self, method, path, *, body=None, data=None, expected=200, headers=None):
        headers = dict(headers or {})
        if path.startswith('/api/projects/' + self.slug) and method != 'GET':
            headers.setdefault('If-Match', '"' + revision(self.project / 'engagement.yaml') + '"')
        arguments = dict(method=method, headers=headers)
        if data is not None:
            arguments['data'] = data
        elif body is not None:
            arguments['json'] = body
        audience_source = self.project / 'engagement.yaml' if '/audiences/' in path else None
        audience_before = audience_source.read_bytes() if audience_source else None
        response = self.client.open(path, **arguments)
        self.check(f'{method} {path}', response.status_code == expected,
                   dict(status=response.status_code, expected=expected,
                        error=response.get_json(silent=True)) if response.status_code != expected else None)
        if audience_source and audience_source.read_bytes() != audience_before:
            self.write('audience-source-before.yaml', audience_before)
            self.write('audience-source-after.yaml', audience_source.read_bytes())
            self.check('Audience request preserves exact source bytes: ' + path, False,
                       {'before_sha256': sha256(audience_before).hexdigest(), 'after_sha256': digest(audience_source)})
        return response

    def project_call(self, method, suffix='', **kwargs):
        return self.call(method, '/api/projects/' + self.slug + suffix, **kwargs)

    def load(self):
        return self.project_call('GET').get_json()

    def save(self, value):
        return self.project_call('PUT', body=value)

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
            'label': 'Banco Horizonte · entrega ficticia inicial', 'stage': 'delivered'}).get_json()
        self.write_json('source-summary.json', {key: len(data.get(key, [])) for key in
                        ('findings', 'assets', 'coverage', 'evidence', 'root_cause_groups', 'attachments')})
        changed = deepcopy(data)
        changed['meta']['report_subtitle'] = 'Ciclo de vida ficticio · revisión de aceptación API'
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

    def intake(self):
        # These are explicitly synthetic scanner-shaped observations; no scanner is run.
        nuclei = {'template-id': 'horizonte-synthetic-header', 'matched-at': 'https://intake.horizonte.test/',
                  'info': {'name': 'Observación sintética Nuclei', 'severity': 'info',
                           'description': 'Entrada ficticia para verificar importación, sin evaluación real.'},
                  'request': 'GET /synthetic HTTP/1.1\r\nHost: intake.horizonte.test\r\n\r\n'}
        sarif = {'version': '2.1.0', 'runs': [{'tool': {
            'driver': {'name': 'Horizonte synthetic pipeline'}, 'extensions': [{
                'name': 'Horizonte synthetic policy', 'guid': '11111111-2222-4333-8444-555555555555',
                'rules': [{'id': 'HZ001', 'shortDescription': {'text': 'Observación sintética SARIF'}}]}]},
            'results': [{'rule': {'index': 0, 'toolComponent': {'index': 0}}, 'level': 'warning',
                         'message': {'text': 'Sintético: verificar control de acceso antes de clasificar.'},
                         'locations': [{'physicalLocation': {'artifactLocation': {'uri': 'src/synthetic.py'},
                                                           'region': {'startLine': 12}}}]}]}]}
        fixtures = {
            'csv': 'title,severity,description,remediation\nObservación sintética CSV,info,Entrada de prueba,Cotejar antes de publicar\n',
            'burp': '<issues><issue><serialNumber>HZ-BURP-1</serialNumber><name>Observación sintética Burp</name>'
                    '<severity>Information</severity><confidence>Tentative</confidence><host>https://burp.horizonte.test</host>'
                    '<path>/synthetic</path><issueDetail>Entrada ficticia, no confirma una vulnerabilidad.</issueDetail>'
                    '<remediationDetail>Revisar manualmente.</remediationDetail><requestresponse><request>'
                    'GET /synthetic HTTP/1.1</request></requestresponse></issue></issues>',
            'nuclei': json.dumps(nuclei),
            'nmap': '<nmaprun scanner="nmap" version="synthetic"><host><status state="up"/>'
                    '<address addr="192.0.2.230" addrtype="ipv4"/><ports><port protocol="tcp" portid="443">'
                    '<state state="open"/><service name="https"/></port></ports></host>'
                    '<runstats><finished exit="success"/></runstats></nmaprun>',
            'sarif': json.dumps(sarif),
        }
        # Import candidates remain in their own project, preventing accidental report promotion.
        original_slug = self.slug
        self.slug = 'banco-horizonte-intake'
        shutil.copytree(api.PROJECTS / original_slug, self.project)
        try:
            for kind, text in fixtures.items():
                body = dict(format=kind, text=text)
                before = deepcopy(self.load())
                preview = self.project_call('POST', '/intake/preview', body=body).get_json()
                self.check(kind + ' preview is read-only', self.load() == before)
                self.check(kind + ' preview has exactly one valid observation', preview['counts']['valid'] == 1, preview['counts'])
                self.write_json('intake/' + kind + '-preview.json', preview)
                applied = self.project_call('POST', '/intake/apply', body={**body, 'selected': [0]}).get_json()
                self.check(kind + ' selected observation imported', applied['imported'] == 1)
                duplicate = self.project_call('POST', '/intake/preview', body=body).get_json()
                self.check(kind + ' duplicate reimport recognized', duplicate['rows'][0]['existing_duplicate'])
                if kind != 'nmap':
                    finding = applied['data']['findings'][-1]
                    self.check(kind + ' remains unverified and awaiting review',
                               finding['verification'] == 'unverified' and finding['import_source']['reviewed'] is False)
                else:
                    self.check('Nmap only adds inventory, never findings', applied['data']['findings'] == before['findings'])
            self.write('banco-horizonte-intake-project.zip', self.project_call('GET', '/bundle').data)
        finally:
            self.slug = original_slug

    def evidence_and_inbox(self):
        from PIL import Image
        data = self.load()
        source = self.project / data['evidence'][0]['src']
        upload = self.project_call('POST', '/image', data={'file': (BytesIO(source.read_bytes()), 'horizonte-annotation.png')}).get_json()
        self.project_call('POST', '/evidence', body={'src': upload['src'], 'title': 'Copia sintética para anotación y censura'})
        entry = next(row for row in self.load()['evidence'] if row['src'] == upload['src'])
        original = self.project_call('GET', '/evidence/' + entry['uid'] + '/original').data
        operations = [dict(type='box', x=.05, y=.05, w=.8, h=.6),
                      dict(type='arrow', x=.05, y=.05, w=.3, h=.3),
                      dict(type='text', x=.1, y=.7, w=.7, h=.15, text='SIMULACION · EVIDENCIA FICTICIA'),
                      dict(type='redact', x=.2, y=.2, w=.2, h=.2)]
        edited = self.project_call('POST', '/evidence/' + entry['uid'] + '/edit', body={'operations': operations}).get_json()['data']
        entry = next(row for row in edited['evidence'] if row['uid'] == entry['uid'])
        with Image.open(self.project / entry['src']) as pixels:
            self.check('Redaction produces opaque black pixels', pixels.convert('RGB').getpixel((int(pixels.width*.3), int(pixels.height*.3))) == (0, 0, 0))
            self.check('Annotated derivative drops source metadata', not pixels.info)
        self.check('Original evidence remains exact after four annotation kinds',
                   self.project_call('GET', '/evidence/' + entry['uid'] + '/original').data == original)
        finding = edited['findings'][0]
        for kind, content in [('note', 'Nota de simulación: autorización revisada para el escenario ficticio.'),
                              ('command', 'printf "%s\\n" "SIMULACION HORIZONTE"'),
                              ('http', 'GET /synthetic HTTP/1.1\r\nHost: banco.horizonte.test\r\n\r\n'),
                              ('image', '')]:
            body = dict(kind=kind, title='Captura ficticia ' + kind, note='Entrada de aceptación, sin datos reales.')
            body['src' if kind == 'image' else 'raw_text'] = entry['src'] if kind == 'image' else content
            captured = self.project_call('POST', '/captures', body=body).get_json()
            self.project_call('POST', '/captures/' + captured['capture_uid'] + '/link', body={'finding_uid': finding['uid']})
        self.check('All four captured kinds linked explicitly',
                   {row['kind'] for row in self.load()['capture_inbox'] if row.get('finding_uid') == finding['uid']} >= {'note', 'command', 'http', 'image'})
        self.project_call('POST', '/captures', body={'kind': 'note', 'title': 'Nota privada no incorporada',
            'note': 'Sólo para comprobar exclusión', 'raw_text': 'HORIZONTE_PRIVATE_UNLINKED_9C8A'})
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
        self.project_call('POST', '/attachments/declare', body={'name': 'horizonte-lifecycle-evidence.csv', 'required': True})
        pending = self.project_call('GET', '/attachments').get_json()['files']
        self.check('Required annex is explicitly missing before upload', any(row['name'] == 'horizonte-lifecycle-evidence.csv' and row['status'] == 'declared' and row['required'] for row in pending))
        uploaded = self.project_call('POST', '/attachments/upload', data={
            'file': (BytesIO(annex), 'horizonte-lifecycle-evidence.csv')}).get_json()['data']
        row = next(item for item in uploaded['attachments'] if item['name'] == 'horizonte-lifecycle-evidence.csv')
        self.check('Uploaded annex is private and unreviewed by default', row['include'] is False and row['reviewed'] is False)
        self.write_json('annex-scan.json', self.project_call('GET', '/attachments/scan?uid=' + row['uid']).get_json())
        row.update(include=True, reviewed=True)
        self.save(uploaded)
        self.project_call('GET', '/attachments')

    def libraries(self):
        data = self.load()
        tag = self.call('GET', '/api/library').headers['ETag']
        content = self.call('POST', '/api/library/sanitize', body={'finding': data['findings'][0], 'context': {}}).get_json()['content']
        template = self.call('POST', '/api/library', body={'name': 'Banco Horizonte · patrón ficticio reutilizable', 'content': content},
                             headers={'If-Match': tag}).get_json()
        instance = self.call('POST', '/api/library/' + template['uid'] + '/instantiate', body={'values': {}}).get_json()
        self.check('Reusable finding strips project-owned evidence links', not instance.get('evidence_uids'))
        self.call('PUT', '/api/library/' + template['uid'], body={'name': 'Banco Horizonte · patrón revisado', 'content': content},
                  headers={'If-Match': self.call('GET', '/api/library').headers['ETag']})
        exported = self.call('GET', '/api/library')
        self.call('POST', '/api/library/import', body=exported.get_json(), headers={'If-Match': exported.headers['ETag']})
        candidates = self.call('GET', '/api/library')
        extra = next(row for row in candidates.get_json()['templates'] if row['uid'] != template['uid'])
        self.call('DELETE', '/api/library/' + extra['uid'], headers={'If-Match': candidates.headers['ETag']})
        catalog = self.call('GET', '/api/design-library')
        profile = design_library.profile('htb-cpts')
        personal = self.call('POST', '/api/design-library/personal', body={
            'name': 'Horizonte · diseño personal ficticio', 'design': design_library.appearance(profile, 'quiet'),
            'sections': profile['sections']}, headers={'If-Match': catalog.headers['ETag']}).get_json()
        before = deepcopy(self.load())
        changed = self.project_call('POST', '/design', body={'id': personal['id']}).get_json()['data']
        self.check('Personal design changes preserve all findings', changed['findings'] == before['findings'])
        self.save(before)
        catalog = self.call('GET', '/api/design-library')
        revised = self.call('PUT', '/api/design-library/personal/' + personal['id'], body={
            'name': 'Horizonte · diseño personal revisado', 'design': personal['design'], 'sections': personal['sections']},
            headers={'If-Match': catalog.headers['ETag']}).get_json()
        self.check('Personal template edit increments its revision', revised['revision'] == personal['revision'] + 1)
        catalog = self.call('GET', '/api/design-library')
        disposable = self.call('POST', '/api/design-library/personal', body={
            'name': 'Horizonte · plantilla desechable', 'design': personal['design'], 'sections': personal['sections']},
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
            'statement': 'La evidencia sintética permite reproducir el escenario descrito.', 'kind': 'observed',
            'demonstrates': 'Comportamiento modelado dentro del ejercicio ficticio.',
            'does_not_demonstrate': 'No demuestra una vulnerabilidad real ni compromiso de una entidad bancaria.',
            'evidence_uids': [evidence_uid]})
        risk = next((row for row in data.get('insights', {}).get('risks', []) if row['finding_uid'] == uid), None)
        risk_body = dict(action='set_risk', finding_uid=uid, service='Banca digital ficticia',
            objective='Integridad de operaciones del escenario', consequence='Pérdida de trazabilidad simulada',
            tolerance='No acordado', source='Criterio ficticio del ejercicio de aceptación',
            assumptions='No se evaluó ninguna entidad real', priority='P1',
            rationale='El ejercicio modela un proceso crítico y reversibilidad limitada', owner='Comité ficticio de riesgo')
        if risk:
            risk_body['uid'] = risk['uid']
        self.project_call('POST', '/insights', body=risk_body)
        comment = self.project_call('POST', '/insights', body={'action': 'add_comment', 'finding_uid': uid,
            'field': 'description_md', 'body': 'Confirmar que la naturaleza ficticia siga visible.',
            'author': 'Revisor sintético de aceptación', 'visibility': 'private'}).get_json()['data']['insights']['comments'][-1]
        self.project_call('POST', '/insights', body={'action': 'resolve_comment', 'uid': comment['uid'],
            'resolution': 'Contexto de simulación presente en portada, resumen y hallazgos.', 'author': 'Revisor sintético de aceptación'})
        self.project_call('POST', '/insights', body={'action': 'review', 'decision': 'changes_requested',
            'author': 'RECORRIDO AUTOMATIZADO DE PRUEBA', 'notes': 'Registro de prueba de la API; no es una aprobación humana del informe.'})
        self.write_json('insights.json', self.project_call('GET', '/insights').get_json())
        self.project_call('GET', '/insights/editorial')
        data = self.load()
        selected = [row['uid'] for row in data['findings'][:3]]
        values = {'owner': 'Equipo ficticio de remediación transversal', 'due_date': '2026-12-18'}
        if data.get('root_cause_groups'):
            values['root_cause_uid'] = data['root_cause_groups'][0]['uid']
        body = dict(finding_uids=selected, values=values)
        preview = self.project_call('POST', '/bulk-edit/preview', body=body).get_json()
        self.project_call('POST', '/bulk-edit/apply', body={**body, 'preview_token': preview['preview_token'], 'ack_reviewed': True})
        self.project_call('POST', '/bulk-edit/apply', body={**body, 'preview_token': preview['preview_token'], 'ack_reviewed': True}, expected=409)
        data = self.load()
        data['findings'][2]['owner'] = '=SYNTHETIC_FORMULA(1)'
        self.save(data)
        options = dict(fields=list(remediation_tasks.FIELDS), lang='es', ack_private=True)
        preview = self.project_call('POST', '/remediation-tasks/preview', body=options).get_json()
        self.check('Task projection retains one row per finding', len(preview['rows']) == len(self.load()['findings']))
        for fmt in ('csv', 'cards'):
            response = self.project_call('POST', '/remediation-tasks/export', body={**options, 'format': fmt, 'preview_token': preview['preview_token']})
            self.write('remediation-tasks.' + ('csv' if fmt == 'csv' else 'zip'), response.data)
        issued = self.project_call('POST', '/remediation-tasks/return-template', body={
            'finding_uids': selected, 'ack_private': True, 'ack_retention': True})
        self.write('remediation-return-issued.csv', issued.data)
        rows = list(csv.reader(StringIO(issued.data.decode('utf-8-sig'))))
        rows[1][rows[0].index('owner')] = "'Responsable ficticio actualizado"
        rows[1][rows[0].index('reported_remediation')] = "'Ajuste comunicado en simulación; falta verificación independiente."
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
            'assessor': 'Evaluador ficticio de aceptación', 'result': 'not_verified',
            'notes_md': 'Registro de prueba documental; no se ejecutó un pentest ni se acredita corrección real.',
            'evidence_uids': [evidence_uid]})
        for finding, outcome in zip(self.load()['findings'][1:4], ('fixed', 'open', 'partial')):
            self.project_call('POST', '/retest', body={'finding_uid': finding['uid'], 'tested_on': '2026-10-16',
                'assessor': 'PERSONAJE FICTICIO DEL ESCENARIO', 'result': outcome,
                'notes_md': 'Estado perteneciente exclusivamente al guion sintético. No acredita evaluación de una entidad real.',
                'evidence_uids': [evidence_uid]})
        self.write_json('retest-matrix.json', self.project_call('GET', '/retest-matrix').get_json())
        self.write_json('retest-diff.json', self.project_call('GET', '/retest-diff').get_json())
        self.write('history-comparison.html', self.project_call('GET', '/history/' + self.baseline['id'] + '/visual').data)
        self.check('Content edits mark the earlier editorial decision stale', self.project_call('GET', '/insights').get_json()['review_status']['state'] == 'stale')

    def audiences(self):
        data = self.load()
        selected = [row['uid'] for row in data['findings'][:3]]
        public = dict(profile='public', finding_uids=selected, title='Banco Horizonte · caso ficticio público',
                      client_alias='Banco de simulación', aliases=[{'needle': 'Horizonte', 'replacement': 'Banco de simulación'}],
                      review_confirmed=True, publish_consent=True, provenance_label='simulation',
                      approved_content=[dict(finding_uid=row['uid'], title='Lección ficticia ' + str(index),
                          summary='Escenario de prueba sobre separación de funciones y trazabilidad.',
                          impact='En el escenario ficticio, un control débil podría afectar la integridad del servicio.',
                          remediation='Definir autorización explícita, pruebas negativas y registro de auditoría.')
                                        for index, row in enumerate(data['findings'][:3], 1)])
        technical_selected = [row['uid'] for row in data['findings'] if row.get('id') in ('F01', 'F12', 'M01')]
        self.check('Technical partial audience selects the three documented independent findings', len(technical_selected) == 3)
        profiles = [dict(profile='technical', finding_uids=technical_selected, section_keys=['findings']),
                    dict(profile='executive', finding_uids=selected,
                    title='Banco Horizonte · resumen de dirección ficticio'), public]
        before = (self.project / 'engagement.yaml').read_bytes()
        for options in profiles:
            profile = options['profile']
            preview = self.project_call('POST', '/audiences/preview', body=options).get_json()
            self.write_json('audiences/' + profile + '-preview.json', preview)
            self.check(profile + ' audience preview has no blocking errors', not [row for row in preview['issues'] if row['level'] == 'error'], preview['issues'])
            formats = ['pdf', 'docx', 'html', 'md']
            response = self.project_call('POST', '/audiences/export', body={**options, 'formats': formats,
                'label': 'Banco Horizonte · ' + profile + ' · simulación', 'acknowledge_warnings': True})
            path = self.write('audiences/' + profile + '-delivery.zip', response.data)
            with zipfile.ZipFile(path) as package:
                manifest = json.loads(package.read('verificacion.json'))
                self.check(profile + ' delivery manifest records audience projection', manifest['audience']['profile'] == profile)
                self.check(profile + ' excludes unlinked private capture text',
                           all(b'HORIZONTE_PRIVATE_UNLINKED_9C8A' not in package.read(entry) for entry in package.infolist()))
                if profile != 'technical':
                    self.check(profile + ' excludes originals and attachments', not manifest['audience']['plan']['originals'] and not manifest['audience']['plan']['attachments'])
                for entry in package.infolist():
                    if entry.filename.endswith('.pdf'):
                        self.write('audiences/' + profile + '.pdf', package.read(entry))
            if profile == 'public':
                self.signed_delivery(path)
        self.check('Audience projections never mutate source project bytes', (self.project / 'engagement.yaml').read_bytes() == before)
        # The executive derivative is short and uses the real report-gen PDF engine.
        first = self.out / 'audiences/executive.pdf'
        if first.exists():
            self.visual(first)

    def signed_delivery(self, source):
        public = self.out / 'audiences/acceptance-public.pem'
        signature = self.out / 'audiences/public-delivery.signature.json'
        # CI writes receipts inside the checkout. Signing keys must instead live
        # outside both report-gen and all project/output trees, even on failure.
        with tempfile.TemporaryDirectory(prefix='report-gen-horizonte-signing-') as directory:
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
        self.project_call('POST', '/history', body={'label': 'Banco Horizonte · ciclo de vida completo', 'stage': 'retest'})
        bundle = self.project_call('GET', '/bundle').data
        self.write('banco-horizonte-lifecycle-project.zip', bundle)
        expected = deepcopy(self.load())
        imported = self.call('POST', '/api/projects/import', data={
            'file': (BytesIO(bundle), 'horizonte-project.zip'), 'slug': 'horizonte-reimported'}).get_json()
        self.check('Native project ZIP restores exact document', self.call('GET', '/api/projects/' + imported['slug']).get_json() == expected)
        plain = self.call('POST', '/api/workspace/backup', body={}).data
        self.write('workspace-plain.zip', plain)
        password = secrets.token_urlsafe(32)
        encrypted = self.call('POST', '/api/workspace/backup/encrypted', body={'password': password}).data
        self.write('workspace-encrypted.rgbackup', encrypted)
        backup_dir = self.out / 'scheduled-backups'
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
        self.slug = 'horizonte-pruning-copy'
        shutil.copytree(api.PROJECTS / original_slug, self.project)
        inventory = self.project_call('GET', '/privacy').get_json()
        self.project_call('POST', '/privacy/prune', body={'categories': ['history'],
            'inventory_revision': inventory['inventory_revision'], 'confirm_project': self.slug})
        self.check('Pruning a throwaway history preserves current report', self.load() == expected)
        self.slug = original_slug
        self.limits.append('Encrypted backup used an ephemeral test password; the plain backup is the portable recovery artifact.')
        self.limits.append('Backup routine enabled/run/rotation/verify/disable exercised; one-hour wall-clock scheduling was not waited out.')

    def diagnostics(self):
        report = self.call('POST', '/api/diagnostics', body={'lang': 'es'}).get_json()
        safe = self.call('POST', '/api/diagnostics/download', body={'report': report['support_report'], 'preview_token': report['support_token']})
        self.write('diagnostics-sanitized.json', safe.data)
        content = safe.data.decode()
        self.check('Support diagnostic excludes case identity and private paths',
                   'Horizonte' not in content and str(self.workspace) not in content and str(self.source) not in content)
        capabilities = self.call('GET', '/api/assistant/capabilities').get_json()
        self.check('Optional assistant does not auto-send case content', capabilities['auto_send'] is False and capabilities['connected'] is False)
        self.limits.append('Ollama inference not claimed: this run verifies explicit opt-in capability without sending the banking case to a model.')
        response = self.client.post('/api/assistant/models', json={})
        self.check('Real local model probe returns a bounded response', response.status_code in (200, 422), response.get_json())
        self.write_json('assistant-model-probe.json', {'status': response.status_code, 'body': response.get_json()})
        self.call('POST', '/api/update/check', body={'allow_network': False}, expected=422)
        self.limits.append('Updater opt-in guard checked; preparing a newer published version is outside this unpublished-candidate acceptance run.')

    def run(self):
        for phase in (self.source_and_history, self.intake, self.evidence_and_inbox, self.libraries,
                      self.insights_and_remediation, self.audiences, self.backups, self.diagnostics):
            print(json.dumps({'phase': phase.__name__, 'status': 'running'}), flush=True)
            phase()
            self.flush()
        self.check('Source case remained byte-identical throughout lifecycle acceptance',
                   digest(self.source / 'engagement.yaml') == self.source_initial_hash)
        self.check('Product and acceptance sources remained unchanged during the run',
                   all((ROOT / name).exists() and digest(ROOT / name) == value for name, value in self.producer.items()))
        self.flush(complete=True)
        print(json.dumps({'complete': True, 'checks': len(self.records), 'output': str(self.out)}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--ui-bundle', type=Path)
    parser.add_argument('--pdf', type=Path)
    args = parser.parse_args()
    journey = Journey(args.case, args.output, args.ui_bundle, args.pdf)
    journey.source_initial_hash = digest(args.case / 'engagement.yaml')
    journey.run()


if __name__ == '__main__':
    main()
