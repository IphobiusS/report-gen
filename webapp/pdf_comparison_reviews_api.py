"""Explicit saving of session-owned comparison metadata as private attachments."""
from io import BytesIO

from flask import abort, jsonify, send_file, session

import attachments
import engine
from error_messages import message as backend_message
import pdf_comparison_reviews as reviews
import project_history
from storage import atomic_write, revision


def register(api):
    app = api.app
    app.extensions.setdefault('pdf_comparison_receipts', reviews.ReceiptStore())

    def owner():
        token = session.get('csrf')
        if not token:
            abort(403, backend_message('Abre una sesión local.', en='Open a local session.',
                                      pt='Abra uma sessão local.'))
        return token

    def receipt(key):
        try:
            return app.extensions['pdf_comparison_receipts'].get(owner(), key)
        except KeyError:
            abort(404, reviews.missing())

    @app.get('/api/pdf-compare/receipts/<key>')
    def comparison_receipt(key):
        return jsonify(receipt(key))

    @app.delete('/api/pdf-compare/receipts/<key>')
    def discard_comparison_receipt(key):
        if not app.extensions['pdf_comparison_receipts'].discard(owner(), key):
            abort(404, reviews.missing())
        return '', 204

    @app.get('/api/projects/<slug>/pdf-comparisons')
    @api.project_lock
    def comparison_review_list(slug):
        owner()
        directory = api.proj_dir(slug)
        data = engine.load_engagement(directory / 'engagement.yaml')
        response = jsonify(records=reviews.records(data, directory))
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @app.post('/api/projects/<slug>/pdf-comparisons')
    @api.project_lock
    def save_comparison_review(slug):
        directory = api.proj_dir(slug)
        api.require_revision(directory / 'engagement.yaml')
        body = api._json_dict()
        if set(body) != {'comparison_id', 'author', 'decision', 'note'}:
            abort(422, reviews.invalid())
        record = reviews.make_record(receipt(body['comparison_id']), body['author'], body['decision'], body['note'])
        blob = reviews.dumps(record)
        data = engine.load_engagement(directory / 'engagement.yaml')
        states = attachments.inventory(data, directory)
        if len(states) >= 100:
            abort(422, backend_message('Anexos: máximo 100 registros / Annexes: maximum 100 records'))
        if sum(item['bytes'] for item in states) + len(blob) > attachments.MAX_TOTAL:
            abort(422, backend_message('Anexos mayores que 64 MiB / Annexes exceed 64 MiB'))
        row = reviews.attachment_row(record, blob)
        data.setdefault('attachments', []).append(row)
        data = api.checked_data(data)
        with project_history.transaction(directory) as stage:
            atomic_write(stage / row['member'], blob)
            project_history.save(stage, data)
        response = jsonify(record=record, records=reviews.records(data, directory), data=data)
        response.status_code = 201
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @app.get('/api/projects/<slug>/pdf-comparisons/<uid>')
    @api.project_lock
    def download_comparison_review(slug, uid):
        owner()
        directory = api.proj_dir(slug)
        data = engine.load_engagement(directory / 'engagement.yaml')
        attachments.validate_rows(data.get('attachments', []))
        row = next((item for item in data.get('attachments', []) if item['uid'] == uid), None)
        if row is None:
            abort(404, reviews.invalid())
        try:
            _, blob = reviews.read_record(directory, row)
        except (ValueError, OSError):
            abort(404, reviews.invalid())
        response = send_file(BytesIO(blob), mimetype='application/json', as_attachment=True,
                             download_name=row['name'])
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response
