"""Local HTTP intake, always behind the application's CSRF and origin guard."""
import base64
from hashlib import sha256
import json
import secrets
import time

from flask import jsonify, request, abort

import engine
from error_messages import message
import http_evidence as evidence
import project_history
from storage import revision


def register(api):
    tokens = api.app.extensions.setdefault('report_gen_http_pairings', {})

    def load(slug, mutate=False):
        directory = api.proj_dir(slug)
        if mutate:
            api.require_revision(directory / 'engagement.yaml')
        return directory, engine.load_engagement(directory / 'engagement.yaml')

    def saved(directory, data, **extra):
        project_history.save(directory, api.checked_data(data))
        response = jsonify(data=data, **extra)
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    def fields(body, allowed):
        if set(body) - set(allowed):
            abort(422, message('HTTP: campos desconocidos', en='HTTP: unknown fields', pt='HTTP: campos desconhecidos'))

    @api.app.get('/api/projects/<slug>/http-evidence')
    @api.project_lock
    def http_list(slug):
        directory, data = load(slug)
        response = jsonify(records=data.get('http_evidence', []))
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @api.app.post('/api/projects/<slug>/http-evidence')
    @api.project_lock
    def http_add(slug):
        directory, data = load(slug, True)
        body = api._json_dict()
        fields(body, ('records', 'finding_uids', 'asset_uids'))
        data, added = evidence.add(data, body.get('records'), body.get('finding_uids', []), body.get('asset_uids', []))
        return saved(directory, data, added=added)

    @api.app.post('/api/projects/<slug>/http-evidence/har-preview')
    @api.project_lock
    def http_har_preview(slug):
        directory, _ = load(slug, True)
        body = api._json_dict()
        fields(body, ('har',))
        records = evidence.from_har(body.get('har'))
        # No content changes and no automatic publication. Display enough to
        # choose the captured pairs; the whole HAR remains in the local form.
        rows = [dict(index=i, method=r['original']['request']['method'], url=r['original']['request']['url'],
                     status=(r['original']['response'] or {}).get('status'), captured_at=r['original']['captured_at'])
                for i, r in enumerate(records)]
        response = jsonify(entries=rows)
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @api.app.post('/api/projects/<slug>/http-evidence/har')
    @api.project_lock
    def http_har(slug):
        directory, data = load(slug, True)
        body = api._json_dict()
        fields(body, ('har', 'indices', 'finding_uids', 'asset_uids'))
        # Unlike previews, import always requires explicit selected indices.
        if 'indices' not in body:
            abort(422, message('Selecciona las entradas HAR', en='Select HAR entries', pt='Selecione as entradas HAR'))
        records = evidence.from_har(body.get('har'), body['indices'])
        data, added = evidence.add(data, records, body.get('finding_uids', []), body.get('asset_uids', []))
        return saved(directory, data, added=added)

    @api.app.post('/api/projects/<slug>/http-evidence/<uid>/edit')
    @api.project_lock
    def http_edit(slug, uid):
        directory, data = load(slug, True)
        return saved(directory, evidence.update(data, uid, api._json_dict()))

    @api.app.get('/api/projects/<slug>/http-evidence/compare')
    @api.project_lock
    def http_compare(slug):
        directory, data = load(slug)
        tag = request.args.get('revision')
        if not tag or tag.strip('"') != revision(directory / 'engagement.yaml'):
            abort(409, message('HTTP: vuelve a abrir la comparación', en='HTTP: reopen the comparison', pt='HTTP: reabra a comparação'))
        response = jsonify(evidence.comparison(data, request.args.get('left'), request.args.get('right')))
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @api.app.post('/api/projects/<slug>/http-evidence/pairing')
    @api.project_lock
    def http_pairing(slug):
        directory, data = load(slug, True)
        body = api._json_dict()
        fields(body, ('finding_uids', 'asset_uids'))
        findings = evidence.refs(body.get('finding_uids', []), {f.get('uid') for f in data.get('findings', [])}, 'finding_uids')
        assets = evidence.refs(body.get('asset_uids', []), {a.get('uid') for a in data.get('assets', [])}, 'asset_uids')
        now = time.time()
        workspace = api.browser_workspace_id()
        # Rotate a project's prior pairing and bound process memory.
        for key, value in list(tokens.items()):
            if value['expires'] <= now or value['workspace'] == workspace and value['project'] == slug:
                del tokens[key]
        if len(tokens) >= 100:
            abort(429, message('Demasiadas vinculaciones activas', en='Too many active pairings', pt='Muitos pareamentos ativos'))
        token = secrets.token_urlsafe(32)
        record = dict(project=slug, workspace=workspace, revision=revision(directory / 'engagement.yaml'),
                      expires=int(now + 900), finding_uids=findings, asset_uids=assets)
        tokens[sha256(token.encode()).hexdigest()] = record
        config = dict(api=request.host_url.rstrip('/'), project=slug, workspace=workspace,
                      revision=record['revision'], token=token)
        code = 'rg1.' + base64.urlsafe_b64encode(json.dumps(config, separators=(',', ':')).encode()).decode().rstrip('=')
        response = jsonify(code=code, expires=record['expires'], one_use=True,
                           finding_uids=findings, asset_uids=assets)
        response.set_etag(record['revision'])
        return response

    @api.app.post('/api/projects/<slug>/http-evidence/pairing/revoke')
    @api.project_lock
    def http_revoke_pairing(slug):
        directory, _ = load(slug, True)
        workspace = api.browser_workspace_id()
        for key, value in list(tokens.items()):
            if value['project'] == slug and value['workspace'] == workspace:
                del tokens[key]
        response = jsonify(revoked=True)
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @api.app.post('/api/projects/<slug>/http-evidence/bridge')
    @api.project_lock
    def http_bridge(slug):
        # The application before_request still requires local session + CSRF,
        # trusted Host, same Origin (when present), and workspace. Native Burp
        # obtains its own session; pairing does not weaken browser protection.
        supplied = request.headers.get('X-Report-Gen-Pairing', '')
        if not 32 <= len(supplied) <= 100:
            abort(403, message('Vinculación inválida', en='Invalid pairing', pt='Pareamento inválido'))
        key = sha256(supplied.encode('utf-8')).hexdigest()
        record = tokens.get(key)
        if (not record or record['expires'] <= time.time() or record['project'] != slug
                or record['workspace'] != api.browser_workspace_id()):
            tokens.pop(key, None)
            abort(403, message('Vinculación caducada o inválida', en='Expired or invalid pairing', pt='Pareamento expirado ou inválido'))
        directory, data = load(slug, True)
        if record['revision'] != revision(directory / 'engagement.yaml'):
            abort(409, message('El proyecto cambió. Genera otra vinculación.', en='Project changed. Generate a new pairing.',
                               pt='O projeto mudou. Gere outro pareamento.'))
        body = api._json_dict()
        fields(body, ('records',))
        records = body.get('records')
        if isinstance(records, list):
            for row in records:
                if isinstance(row, dict) and isinstance(row.get('original'), dict):
                    row['original']['source'] = 'Burp Montoya selected messages'
        data, added = evidence.add(data, records, record['finding_uids'], record['asset_uids'])
        # Remove token only after a successful atomic save. Failed validation is
        # recoverable; a successful request cannot be replayed.
        response = saved(directory, data, added=added)
        del tokens[key]
        return response
