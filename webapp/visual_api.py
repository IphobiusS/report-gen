"""Session-private thumbnails and manual review of immutable, actual PDF bytes."""
from error_messages import message as backend_message
from io import BytesIO
import json
from flask import abort, jsonify, request, send_file, session
from storage import revision
import visual_review


def register(api):
    app = api.app
    store = visual_review.Store()
    app.extensions['visual_reviews'] = store

    def owner():
        token = session.get('csrf')
        if not token:
            abort(403, backend_message('Abre una sesión local / Open a local session'))
        return token

    def job_record(key):
        queue = app.extensions.get('export_queue')
        if queue is None:
            abort(404, backend_message('Resultado inexistente / Result not found'))
        identity = owner()
        try:
            status = queue.status(identity, key)
            if status['stage'] != 'done':
                abort(409, backend_message('El resultado todavía no está listo / Result not ready'))
            payload, filename = queue.result(identity, key)
        except KeyError:
            abort(404, backend_message('Resultado inexistente / Result not found'))
        return store.add(identity, visual_review.extract_pdf(payload, filename), status['revision'],
                         filename, 'generated', key)

    def metadata(key, prefix=None):
        try:
            return jsonify(store.metadata(owner(), key, prefix or '/api/visual/' + key))
        except KeyError:
            abort(404, backend_message('Vista temporal inexistente / Temporary preview not found'))

    def image(key, number):
        try:
            value = store.page(owner(), key, number)
        except KeyError:
            abort(404, backend_message('Página inexistente / Page not found'))
        return send_file(BytesIO(value), mimetype='image/png')

    def review(key):
        try:
            return jsonify(store.review(owner(), key, api._json_dict()))
        except KeyError:
            abort(404, backend_message('Vista temporal inexistente / Temporary preview not found'))

    @app.get('/api/visual/capabilities')
    def visual_capabilities():
        return jsonify(available=visual_review.available(), max_bytes=visual_review.MAX_PDF,
                       max_pages=visual_review.MAX_PAGES, retention_seconds=visual_review.TTL,
                       install='pip install -e ".[previews]"', actual_pdf=True, original_word_verified=False)

    @app.post('/api/projects/<slug>/visual')
    def upload(slug):
        if not request.mimetype == 'multipart/form-data' or set(request.files) != {'file'} or request.form:
            abort(415, backend_message('Sube un único archivo PDF / Upload exactly one PDF file'))
        identity = owner()
        with api._PROJECT_LOCK:
            api.project_history.recover_transactions(api.PROJECTS)
            directory = api.proj_dir(slug)
            path = directory / 'engagement.yaml'
            api.require_revision(path)
            tag = revision(path)
        payload = request.files['file'].stream.read(visual_review.MAX_PDF + 1)
        key = store.add(identity, visual_review.extract_pdf(payload, 'uploaded.pdf'), tag,
                        'uploaded.pdf', 'uploaded')
        return metadata(key)

    @app.get('/api/jobs/<key>/visual')
    def job_metadata(key):
        return metadata(job_record(key), '/api/jobs/' + key + '/visual')

    @app.get('/api/jobs/<key>/visual/page/<int:number>')
    def job_page(key, number):
        return image(job_record(key), number)

    @app.post('/api/jobs/<key>/visual/review')
    def job_review(key):
        return review(job_record(key))

    @app.get('/api/visual/<key>')
    def view_metadata(key):
        return metadata(key)

    @app.get('/api/visual/<key>/page/<int:number>')
    def view_page(key, number):
        return image(key, number)

    @app.post('/api/visual/<key>/review')
    def view_review(key):
        return review(key)

    @app.get('/api/visual/<key>/review/download')
    def download_review(key):
        try:
            record = store.get(owner(), key)
        except KeyError:
            abort(404, backend_message('Vista temporal inexistente / Temporary preview not found'))
        if record['review'] is None:
            abort(404, backend_message('No se ha registrado una revisión / No review recorded'))
        raw = json.dumps(record['review'], ensure_ascii=False, indent=2).encode('utf-8')
        return send_file(BytesIO(raw), mimetype='application/json', as_attachment=True,
                         download_name='visual-review-' + record['pdf_sha256'][:12] + '.json')

    @app.delete('/api/visual/<key>')
    def discard(key):
        api._json_dict()
        try:
            store.discard(owner(), key)
        except KeyError:
            abort(404, backend_message('Vista temporal inexistente / Temporary preview not found'))
        return jsonify(ok=True)
