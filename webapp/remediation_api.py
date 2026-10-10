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

    # A return template is a deliberately issued assignment. Its portable batch
    # receipt survives restarts and workspace moves; review tokens do not.
    import remediation_return as returns
    import project_history

    def return_body(slug, allowed):
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        api.require_revision(path)
        body = api._json_dict()
        if set(body) != set(allowed) or request.args:
            abort(422, message('Opciones de retorno inválidas', en='Invalid return options'))
        return directory, path, body, engine.load_engagement(path)

    def return_token(slug, current, proposal):
        payload = json.dumps([slug, current, proposal], sort_keys=True, ensure_ascii=True,
                             separators=(',', ':')).encode('utf-8')
        secret = api.app.secret_key
        if isinstance(secret, str):
            secret = secret.encode('utf-8')
        return hmac.new(secret, b'remediation-return-review-v1\x00' + payload, hashlib.sha256).hexdigest()

    @api.app.post('/api/projects/<slug>/remediation-tasks/return-template')
    @api.project_lock
    def remediation_return_template(slug):
        directory, path, body, data = return_body(slug, {'finding_uids', 'ack_private', 'ack_retention'})
        if body['ack_private'] is not True or body['ack_retention'] is not True:
            abort(422, message('Confirma la revisión de datos privados y la retención limitada de lotes', en='Confirm private-data review and limited batch retention'))
        updated, blob = returns.issue(data, slug, body['finding_uids'], source_revision=revision(path))
        project_history.save(directory, api.checked_data(updated))
        response = Response(blob, mimetype='text/csv')
        response.headers['Content-Disposition'] = 'attachment; filename="remediation-return.csv"'
        response.set_etag(revision(path))
        return response

    @api.app.post('/api/projects/<slug>/remediation-tasks/return-preview')
    @api.project_lock
    def remediation_return_preview(slug):
        _, path, body, data = return_body(slug, {'text'})
        current = revision(path)
        proposal = returns.plan(data, slug, body['text'])
        response = jsonify(version=1, source='saved_project', project_slug=slug, revision=current,
                           **proposal, preview_token=return_token(slug, current, proposal))
        response.set_etag(current)
        return response

    @api.app.post('/api/projects/<slug>/remediation-tasks/return-apply')
    @api.project_lock
    def remediation_return_apply(slug):
        directory, path, body, data = return_body(slug, {'text', 'preview_token', 'selected', 'ack_reviewed'})
        if body['ack_reviewed'] is not True:
            abort(422, message('Confirma que revisaste los cambios seleccionados; no acreditan la corrección', en='Confirm review of selected changes; they do not prove remediation'))
        current = revision(path)
        proposal = returns.plan(data, slug, body['text'])
        token = body['preview_token']
        if not isinstance(token, str) or not hmac.compare_digest(return_token(slug, current, proposal).encode('ascii'), token.encode('utf-8')):
            abort(409, message('Vuelve a previsualizar este retorno sobre la revisión actual', en='Preview this return again against the current revision'))
        updated = returns.record(returns.apply(data, proposal, body['selected']), proposal, current, selected=body['selected'])
        project_history.save(directory, api.checked_data(updated))
        response = jsonify(data=updated, applied=len(body['selected']))
        response.set_etag(revision(path))
        return response

    @api.app.post('/api/projects/<slug>/remediation-tasks/return-receive')
    @api.project_lock
    def remediation_return_receive(slug):
        directory, path, body, data = return_body(slug, {'text', 'preview_token', 'ack_reviewed'})
        if body['ack_reviewed'] is not True:
            abort(422, message('Confirma la recepción de este archivo', en='Confirm receipt of this file'))
        current = revision(path)
        proposal = returns.plan(data, slug, body['text'])
        token = body['preview_token']
        if not isinstance(token, str) or not hmac.compare_digest(return_token(slug, current, proposal).encode('ascii'), token.encode('utf-8')):
            abort(409, message('Vuelve a previsualizar este retorno sobre la revisión actual', en='Preview this return again against the current revision'))
        updated = returns.record(data, proposal, current)
        project_history.save(directory, api.checked_data(updated))
        response = jsonify(data=updated)
        response.set_etag(revision(path))
        return response

    @api.app.post('/api/projects/<slug>/remediation-tasks/return-revoke')
    @api.project_lock
    def remediation_return_revoke(slug):
        directory, path, body, data = return_body(slug, {'batch_uid', 'ack_reviewed'})
        if body['ack_reviewed'] is not True or not isinstance(body['batch_uid'], str):
            abort(422, message('Confirma la revocación del lote', en='Confirm batch revocation'))
        updated = returns.revoke(data, body['batch_uid'], revision(path))
        project_history.save(directory, api.checked_data(updated))
        response = jsonify(data=updated)
        response.set_etag(revision(path))
        return response

    def delivery_body(slug, exporting=False):
        allowed = {'finding_uids', 'fields', 'lang', 'ack_private', 'ack_retention'}
        directory, path, body, data = return_body(slug, allowed | ({'preview_token'} if exporting else set()))
        if body['ack_private'] is not True or body['ack_retention'] is not True:
            abort(422, message('Confirma la revisión de datos privados y la retención limitada de lotes', en='Confirm private-data review and limited batch retention'))
        fields, lang = tasks.options(body)
        current = revision(path)
        options = {'finding_uids': body['finding_uids'], 'fields': fields, 'lang': lang,
                   'purpose': 'owner-delivery-1', 'ack_private': True, 'ack_retention': True}
        token = return_token(slug, current, options)
        if exporting:
            supplied = body['preview_token']
            if not isinstance(supplied, str) or not hmac.compare_digest(token.encode('ascii'), supplied.encode('utf-8')):
                abort(409, message('Previsualiza esta selección antes de emitir la entrega', en='Preview this selection before issuing the delivery'))
        return directory, path, data, options, current, token

    @api.app.post('/api/projects/<slug>/remediation-tasks/delivery-preview')
    @api.project_lock
    def remediation_delivery_preview(slug):
        _, _, data, options, current, token = delivery_body(slug)
        rows = returns.delivery_preview(data, slug, options['finding_uids'], options['fields'], options['lang'])
        response = jsonify(version=1, project_slug=slug, revision=current, fields=options['fields'],
                           labels=tasks.labels(options['fields'], options['lang']), rows=rows, preview_token=token)
        response.set_etag(current)
        return response

    @api.app.post('/api/projects/<slug>/remediation-tasks/delivery-export')
    @api.project_lock
    def remediation_delivery_export(slug):
        directory, path, data, options, current, _ = delivery_body(slug, exporting=True)
        updated, blob = returns.delivery(data, slug, options['finding_uids'], options['fields'], options['lang'], current)
        project_history.save(directory, api.checked_data(updated))
        response = Response(blob, mimetype='application/zip')
        response.headers['Content-Disposition'] = 'attachment; filename="remediation-delivery.zip"'
        response.set_etag(revision(path))
        return response
