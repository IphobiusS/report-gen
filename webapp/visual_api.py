"""Session-private thumbnails and manual review of immutable, actual PDF bytes."""
from error_messages import message as backend_message
from io import BytesIO
import json
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import uuid
from flask import abort, jsonify, request, send_file, session
from storage import revision, atomic_write
import attachments
import engine
import project_history
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

    def selected_record(directory, data, uid):
        row = next((row for row in data.get('attachments', []) if row['uid'] == uid), None)
        if row is None:
            abort(404, visual_review.invalid_saved())
        try:
            return visual_review.read_saved(directory, row), row
        except (ValueError, OSError):
            abort(422, visual_review.invalid_saved())

    def saved_response(directory, data, record=None, status=200):
        response = jsonify(records=visual_review.saved_records(data, directory), record=record, data=data)
        response.status_code = status
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @app.get('/api/projects/<slug>/visual-reviews')
    @api.project_lock
    def list_saved(slug):
        owner()
        directory = api.proj_dir(slug)
        data = engine.load_engagement(directory / 'engagement.yaml')
        response = jsonify(records=visual_review.saved_records(data, directory),
                           max_records=visual_review.MAX_SAVED, max_metadata_bytes=visual_review.MAX_METADATA,
                           private_by_default=True, historical_copies_retained=True)
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @app.post('/api/projects/<slug>/visual-reviews')
    @api.project_lock
    def save_progress(slug):
        directory = api.proj_dir(slug)
        api.require_revision(directory / 'engagement.yaml')
        body = api._json_dict()
        if (set(body) != {'visual_id', 'uid', 'progress', 'keep_pdf'}
                or not isinstance(body['visual_id'], str) or type(body['keep_pdf']) is not bool
                or (body['uid'] is not None and not visual_review._uid(body['uid']))):
            abort(422, visual_review.invalid_saved())
        try:
            source = store.get(owner(), body['visual_id'])
        except KeyError:
            abort(404, backend_message('Vista temporal caducada; vuelve a abrir el PDF.',
                                      en='Temporary preview expired; reopen the PDF.',
                                      pt='Prévia temporária expirada; abra o PDF novamente.'))
        if source.get('saved_project') not in (None, slug):
            abort(409, visual_review.invalid_saved())
        progress = deepcopy(visual_review.validate_progress(body['progress'], len(source['pages'])))
        data = engine.load_engagement(directory / 'engagement.yaml')
        states = attachments.inventory(data, directory)
        records = visual_review.saved_records(data, directory)
        previous, previous_row = selected_record(directory, data, body['uid']) if body['uid'] else (None, None)
        if previous is not None and (previous['pdf_sha256'] != source['pdf_sha256'] or previous['revision'] != source['revision']):
            abort(409, visual_review.invalid_saved())
        if previous is None and len(records) >= visual_review.MAX_SAVED:
            abort(422, backend_message('Máximo 20 revisiones guardadas; elimina una antes de guardar otra.',
                                      en='Maximum 20 saved reviews; remove one before saving another.',
                                      pt='Máximo de 20 revisões salvas; remova uma antes de salvar outra.'))
        uid = previous['uid'] if previous else str(uuid.uuid4())
        pdf_uid = (previous or {}).get('pdf_attachment_uid')
        old_pdf_row = next((row for row in data.get('attachments', []) if row['uid'] == pdf_uid), None)
        # Only an exact owned PDF member may be replaced/removed. Never delete a
        # generic attachment supplied through a forged imported JSON reference.
        owned_pdf = old_pdf_row is not None and all(old_pdf_row.get(key) == visual_review.private_row(pdf_uid, 'pdf', source['pdf_sha256'])[key]
                                                 for key in ('name', 'member', 'sha256'))
        if old_pdf_row is not None and not owned_pdf:
            abort(422, visual_review.invalid_saved())
        if owned_pdf and any(item['uid'] != uid and item['pdf_attachment_uid'] == pdf_uid for item in records):
            abort(409, visual_review.invalid_saved())
        if body['keep_pdf'] and pdf_uid is None:
            pdf_uid = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat(timespec='microseconds')
        record = dict(schema=visual_review.SCHEMA, uid=uid, created=previous['created'] if previous else timestamp,
                      updated=timestamp, revision=source['revision'], pdf_sha256=source['pdf_sha256'],
                      page_count=len(source['pages']), origin=(source.get('saved') or source)['origin'],
                      progress=progress, pdf_attachment_uid=pdf_uid if body['keep_pdf'] else None,
                      author_identity='local_self_declaration', original_word_verified=False,
                      automated_layout_verification=False)
        visual_review.validate_saved(record)
        blob = visual_review.dumps(record)
        row = visual_review.private_row(uid, 'json', sha256(blob).hexdigest())
        replaced = {uid, old_pdf_row['uid'] if owned_pdf else None}
        remaining = [item for item in data.get('attachments', []) if item['uid'] not in replaced]
        writes = [(row, blob)]
        if body['keep_pdf']:
            writes.append((visual_review.private_row(pdf_uid, 'pdf', source['pdf_sha256']), source['payload']))
        # Do not overwrite undeclared files, member aliases or unrelated IDs.
        for item, _ in writes:
            authorized = previous_row if item['uid'] == uid else old_pdf_row
            if (any(existing['uid'] == item['uid'] or existing.get('member') == item['member'] for existing in remaining)
                    or ((directory / item['member']).exists() and (authorized is None or authorized.get('member') != item['member']))):
                abort(409, visual_review.invalid_saved())
        if sum(item['bytes'] for item in states if item['uid'] not in replaced) + sum(len(value) for _, value in writes) > attachments.MAX_TOTAL:
            abort(422, backend_message('Anexos mayores que 64 MiB / Annexes exceed 64 MiB'))
        data['attachments'] = remaining + [item for item, _ in writes]
        data = api.checked_data(data)
        with project_history.transaction(directory) as stage:
            project_history.checkpoint(stage)  # Retain the coherent old metadata/PDF before replacement.
            for item, value in writes:
                atomic_write(stage / item['member'], value)
            if owned_pdf and not body['keep_pdf'] and not any(item.get('member') == old_pdf_row['member'] for item in remaining):
                (stage / old_pdf_row['member']).unlink(missing_ok=True)
            project_history.save(stage, data, checkpoint_current=False)
        # Saving an unbound session PDF must not mutate its metadata with a
        # project-specific UID: the same explicit upload can be saved elsewhere.
        # Only the dedicated resume route creates a project-owned progress view.
        return saved_response(directory, data, record, 200 if previous else 201)

    @app.post('/api/projects/<slug>/visual-reviews/<uid>/open')
    @api.project_lock
    def open_saved(slug, uid):
        directory = api.proj_dir(slug)
        api.require_revision(directory / 'engagement.yaml')
        body = api._json_dict()
        if set(body) != {'visual_id'} or (body['visual_id'] is not None and not isinstance(body['visual_id'], str)):
            abort(422, visual_review.invalid_saved())
        data = engine.load_engagement(directory / 'engagement.yaml')
        record, _ = selected_record(directory, data, uid)
        if body['visual_id'] is not None:
            try:
                candidate = store.get(owner(), body['visual_id'])
            except KeyError:
                abort(404, visual_review.invalid_saved())
            if candidate['pdf_sha256'] != record['pdf_sha256'] or len(candidate['pages']) != record['page_count']:
                abort(409, backend_message('El PDF no coincide con el SHA-256 de la revisión guardada.',
                                          en='The PDF does not match the saved review SHA-256.',
                                          pt='O PDF não corresponde ao SHA-256 da revisão salva.'))
            payload = candidate['payload']
        else:
            payload = visual_review.saved_pdf(data, directory, record)
        key = store.add(owner(), payload, record['revision'], 'review-' + record['pdf_sha256'][:12] + '.pdf',
                        record['origin'], 'saved:' + slug + ':' + uid)
        with store.lock:
            target = store.get(owner(), key)
            if len(target['pages']) != record['page_count']:
                abort(422, visual_review.invalid_saved())
            target['saved'] = deepcopy(record)
            target['saved_project'] = slug
        return metadata(key)

    @app.delete('/api/projects/<slug>/visual-reviews/<uid>')
    @api.project_lock
    def delete_saved(slug, uid):
        owner()
        directory = api.proj_dir(slug)
        api.require_revision(directory / 'engagement.yaml')
        if api._json_dict():
            abort(422, visual_review.invalid_saved())
        data = engine.load_engagement(directory / 'engagement.yaml')
        record, row = selected_record(directory, data, uid)
        removed = [row]
        pdf_uid = record['pdf_attachment_uid']
        if pdf_uid:
            expected = visual_review.private_row(pdf_uid, 'pdf', record['pdf_sha256'])
            copy_row = next((item for item in data.get('attachments', []) if item['uid'] == pdf_uid), None)
            if copy_row and all(copy_row.get(key) == expected[key] for key in ('name', 'member', 'sha256')):
                # Shared or forged imported references cannot erase another review's PDF.
                if not any(item['uid'] != uid and item['pdf_attachment_uid'] == pdf_uid for item in visual_review.saved_records(data, directory)):
                    removed.append(copy_row)
        data['attachments'] = [item for item in data['attachments'] if item['uid'] not in {row['uid'] for row in removed}]
        with project_history.transaction(directory) as stage:
            project_history.checkpoint(stage)
            for item in removed:
                # Alias safety: another declared attachment can never lose its file.
                if not any(other.get('member') == item['member'] for other in data['attachments']):
                    (stage / item['member']).unlink(missing_ok=True)
            project_history.save(stage, api.checked_data(data), checkpoint_current=False)
        return saved_response(directory, data)

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
