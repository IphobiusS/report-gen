"""Session-owned, opt-in native pagination of completed export-job DOCX only."""
from io import BytesIO
import json

from flask import abort, jsonify, send_file, session

import docx_preview
from error_messages import message


def register(api):
    app = api.app
    app.extensions['docx_previews'] = docx_preview.Store()

    def store():
        return app.extensions['docx_previews']

    def owner():
        token = session.get('csrf')
        if not token:
            abort(403, message('Abre una sesión local.', en='Open a local session.', pt='Abra uma sessão local.'))
        return token

    def empty_body():
        if api._json_dict():
            abort(422, message('La vista DOCX no admite archivos, rutas ni opciones del cliente.',
                               en='DOCX preview accepts no client files, paths or options.',
                               pt='A visualização DOCX não aceita arquivos, caminhos ou opções do cliente.'))

    def missing():
        abort(404, message('Vista DOCX o exportación inexistente.', en='DOCX preview or export not found.',
                           pt='Visualização DOCX ou exportação não encontrada.'))

    @app.get('/api/docx-preview/capabilities')
    def docx_preview_capabilities():
        return jsonify(docx_preview.capabilities())

    @app.post('/api/jobs/<key>/docx-preview')
    def create_docx_preview(key):
        empty_body()
        identity = owner()
        queue = app.extensions.get('export_queue')
        if queue is None:
            missing()
        try:
            # Freeze bytes, revision and receipt under the same ownership lock;
            # deleting the source job afterwards cannot substitute its document.
            with queue.lock:
                status = queue.status(identity, key)
                if status['stage'] != 'done':
                    abort(409, docx_preview.error('pending'))
                raw, filename = queue.result(identity, key)
                verification = queue.verification(identity, key)
                document = docx_preview.extract_docx(raw, filename, verification, status['revision'])
            return jsonify(store().start(identity, document, status['revision'], key)), 202
        except KeyError:
            missing()

    @app.get('/api/docx-preview/<key>')
    def docx_preview_status(key):
        try:
            return jsonify(store().status(owner(), key))
        except KeyError:
            missing()

    @app.post('/api/docx-preview/<key>/cancel')
    def cancel_docx_preview(key):
        empty_body()
        try:
            return jsonify(store().cancel(owner(), key))
        except KeyError:
            missing()

    @app.delete('/api/docx-preview/<key>')
    def discard_docx_preview(key):
        empty_body()
        try:
            store().discard(owner(), key)
        except KeyError:
            missing()
        return jsonify(ok=True)

    @app.get('/api/docx-preview/<key>/pdf')
    def download_docx_preview(key):
        try:
            raw = store().result(owner(), key)
        except KeyError:
            missing()
        return send_file(BytesIO(raw), mimetype='application/pdf', as_attachment=True,
                         download_name='docx-libreoffice-preview.pdf')

    @app.get('/api/docx-preview/<key>/receipt')
    def download_docx_preview_receipt(key):
        try:
            status = store().status(owner(), key)
        except KeyError:
            missing()
        if status['stage'] != 'done':
            abort(409, docx_preview.error('pending'))
        raw = json.dumps(status['receipt'], ensure_ascii=False, indent=2).encode('utf-8')
        return send_file(BytesIO(raw), mimetype='application/json', as_attachment=True,
                         download_name='docx-libreoffice-preview.json')
