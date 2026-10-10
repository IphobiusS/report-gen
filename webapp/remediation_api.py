"""Revision-bound local exports; signed previews prevent silent field expansion."""
import hashlib
import hmac
import json

from flask import Response, abort, jsonify, request

import engine
import remediation_tasks as tasks
from error_messages import message
from storage import revision


def register(api):
    def read(slug, exporting=False):
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        api.require_revision(path)
        body = api._json_dict()
        allowed = {'fields', 'lang', 'ack_private'} | ({'format', 'preview_token'} if exporting else set())
        if set(body) - allowed or request.args:
            abort(422, message('Opciones de tareas inválidas', en='Invalid task options'))
        fields, lang = tasks.options(body)
        current = revision(path)
        payload = json.dumps([directory.name, current, fields, lang, body.get('ack_private', False)],
                             ensure_ascii=True, separators=(',', ':')).encode('utf-8')
        secret = api.app.secret_key
        if isinstance(secret, str):
            secret = secret.encode('utf-8')
        token = hmac.new(secret, b'remediation-preview-v1\x00' + payload, hashlib.sha256).hexdigest()
        if exporting:
            supplied = body.get('preview_token')
            if not isinstance(supplied, str) or not hmac.compare_digest(token.encode('ascii'), supplied.encode('utf-8')):
                abort(409, message('Vuelve a previsualizar exactamente estos campos antes de descargar', en='Preview these exact fields again before downloading'))
        project_rows = tasks.rows(engine.load_engagement(path), fields, lang)
        return body, fields, lang, current, token, project_rows

    @api.app.post('/api/projects/<slug>/remediation-tasks/preview')
    @api.project_lock
    def remediation_preview(slug):
        _, fields, lang, current, token, project_rows = read(slug)
        response = jsonify(version=1, source='saved_project', project_slug=slug, revision=current,
                           fields=fields, labels=tasks.labels(fields, lang), rows=project_rows,
                           preview_token=token)
        response.set_etag(current)
        return response

    @api.app.post('/api/projects/<slug>/remediation-tasks/export')
    @api.project_lock
    def remediation_export(slug):
        body, fields, lang, current, _, project_rows = read(slug, exporting=True)
        kind = body.get('format')
        if kind not in ('csv', 'cards'):
            abort(422, message('Formato de tareas inválido', en='Invalid task format'))
        if not project_rows:
            abort(422, message('No hay hallazgos para exportar', en='No findings to export'))
        blob = tasks.csv_bytes(project_rows, fields, lang) if kind == 'csv' else tasks.cards_zip(project_rows, fields, lang)
        response = Response(blob, mimetype='text/csv' if kind == 'csv' else 'application/zip')
        suffix = 'csv' if kind == 'csv' else 'zip'
        response.headers['Content-Disposition'] = 'attachment; filename="remediation-tasks.' + suffix + '"'
        response.set_etag(current)
        return response
