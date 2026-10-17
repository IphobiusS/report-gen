"""Local scanner reconciliation, tied to source bytes and current revision."""
import hashlib
import hmac
import json

from flask import abort, jsonify, request
import engine
from error_messages import message
import import_reconciliation
import project_history
from storage import revision

SOURCE_FIELDS = {'format', 'text', 'bytes_base64', 'mapping'}


def register(api):
    @api.app.post('/api/projects/<slug>/imports/reconcile/<action>')
    @api.project_lock
    def reconcile_import(slug, action):
        if action not in ('preview', 'apply'):
            abort(404)
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        api.require_revision(path)
        body = api._json_dict()
        permitted = SOURCE_FIELDS | ({'decisions', 'preview_token', 'ack_reviewed'} if action == 'apply' else set())
        if set(body) - permitted or request.args:
            abort(422, message('Opciones de conciliación inválidas', en='Invalid reconciliation options', pt='Opções de conciliação inválidas'))
        data = engine.load_engagement(path)
        current = revision(path)
        source = {key: value for key, value in body.items() if key in SOURCE_FIELDS}
        payload = json.dumps([api.browser_workspace_id(), slug, current, source], sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()
        secret = api.app.secret_key
        if isinstance(secret, str):
            secret = secret.encode()
        token = hmac.new(secret, b'scanner-reconcile-v1\0' + payload, hashlib.sha256).hexdigest()
        if action == 'preview':
            result = import_reconciliation.preview(source, data)
            result['preview_token'] = token
        else:
            supplied = body.get('preview_token')
            if not isinstance(supplied, str) or not hmac.compare_digest(token.encode(), supplied.encode('utf-8')):
                abort(409, message('Analiza nuevamente el archivo y sus coincidencias', en='Analyze the file and its matches again', pt='Analise o arquivo e suas correspondências novamente'))
            if body.get('ack_reviewed') is not True:
                abort(422, message('Confirma las decisiones revisadas', en='Confirm the reviewed decisions', pt='Confirme as decisões revisadas'))
            updated, count = import_reconciliation.apply(body, data)
            project_history.save(directory, api.checked_data(updated))
            result = dict(data=updated, applied=count)
        response = jsonify(result)
        response.set_etag(revision(path))
        return response
