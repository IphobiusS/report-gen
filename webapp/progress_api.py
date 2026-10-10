"""Release 0.17 workflows: queued exports, assisted intake and visual comparisons."""
from error_messages import message as backend_message
from io import BytesIO
from flask import request, jsonify, abort, send_file, session, Response
import delivery
import engine
import finding_imports
import project_history
import report_compare
from export_jobs import ExportQueue
from storage import revision


def register(api):
    app = api.app

    def queue():
        with api._PROJECT_LOCK:
            if 'export_queue' not in app.extensions:
                app.extensions['export_queue'] = ExportQueue()
            return app.extensions['export_queue']

    def owner():
        token = session.get('csrf')
        if not token: abort(403, backend_message('Abre una sesión local'))
        return token

    @app.post('/api/projects/<slug>/jobs')
    def enqueue(slug):
        body = api._json_dict()
        if set(body) - {'kind', 'formats', 'label', 'acknowledge_warnings'}:
            abort(422, backend_message('Campos de exportación desconocidos'))
        kind, formats, label = body.get('kind'), body.get('formats'), body.get('label')
        if not isinstance(kind, str) or kind not in ('export', 'delivery'):
            abort(422, backend_message('Tipo de exportación inválido'))
        if not isinstance(formats, list) or not formats or len(formats) > len(delivery.FORMATS) or any(
                not isinstance(f, str) or f not in delivery.FORMATS for f in formats) or len(set(formats)) != len(formats):
            abort(422, backend_message('Selecciona PDF, Word, Markdown o HTML sin duplicados'))
        if kind == 'export' and len(formats) != 1: abort(422, backend_message('La exportación individual requiere un formato'))
        if not isinstance(label, str) or not label.strip() or len(label) > 120: abort(422, backend_message('Nombre inválido'))
        if type(body.get('acknowledge_warnings', False)) is not bool: abort(422, backend_message('Confirmación inválida'))
        with api._PROJECT_LOCK:
            project_history.recover_transactions(api.PROJECTS)
            directory = api.proj_dir(slug)
            api.require_revision(directory / 'engagement.yaml')
            identity = revision(directory / 'engagement.yaml')
            def prepare(target):
                captured = delivery.capture(directory, target)
                if kind == 'delivery' and captured['issues'] and not body.get('acknowledge_warnings'):
                    abort(422, backend_message('Revisa los avisos antes de preparar la entrega'))
                return captured
            suffix = 'zip' if kind == 'delivery' else delivery.get(formats[0]).extension
            specification = dict(kind=kind, formats=formats, label=label.strip(), revision=identity,
                                 filename=api.slugify(slug) + ('-entrega' if kind == 'delivery' else '') + '.' + suffix)
            response = queue().submit(owner(), prepare, specification)
        return jsonify(response), 202

    @app.get('/api/jobs')
    def jobs(): return jsonify(queue().list(owner()))

    @app.route('/api/jobs/<key>', methods=['GET', 'DELETE'])
    def job(key):
        try:
            if request.method == 'DELETE':
                queue().discard(owner(), key)
                return jsonify(ok=True)
            return jsonify(queue().status(owner(), key))
        except KeyError: abort(404, backend_message('Exportación inexistente'))

    @app.get('/api/jobs/<key>/verification')
    def job_verification(key):
        try: return jsonify(queue().verification(owner(), key))
        except KeyError: abort(404, backend_message('Exportación inexistente'))

    @app.post('/api/jobs/<key>/cancel')
    def cancel_job(key):
        api._json_dict()
        try: return jsonify(queue().cancel(owner(), key))
        except KeyError: abort(404, backend_message('Exportación inexistente'))

    @app.get('/api/jobs/<key>/download')
    def download_job(key):
        try: payload, filename = queue().result(owner(), key)
        except KeyError: abort(404, backend_message('Exportación inexistente'))
        return send_file(BytesIO(payload), as_attachment=True, download_name=filename)

    @app.post('/api/projects/<slug>/intake/<action>')
    @api.project_lock
    def intake(slug, action):
        if action not in ('preview', 'apply'): abort(404)
        body = api._json_dict()
        if set(body) - {'format', 'text', 'bytes_base64', 'mapping', 'selected'}: abort(422, backend_message('Campos de importación desconocidos'))
        directory = api.proj_dir(slug)
        api.require_revision(directory / 'engagement.yaml')
        data = engine.load_engagement(directory / 'engagement.yaml')
        if action == 'preview':
            result = finding_imports.preview(body, data)
        else:
            data, count = finding_imports.apply(body, data)
            project_history.save(directory, api.checked_data(data))
            result = dict(data=data, imported=count, import_kind='inventory' if body.get('format') == 'nmap' else 'findings')
        response = jsonify(result)
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @app.get('/api/projects/<slug>/history/<sid>/visual')
    @api.project_lock
    def comparison(slug, sid):
        directory = api.proj_dir(slug)
        record = project_history.get_snapshot(directory, sid)
        old = dict(project_history.snapshot_blobs(directory, record))
        other = request.args.get('to')
        if other:
            record2 = project_history.get_snapshot(directory, other)
            new = dict(project_history.snapshot_blobs(directory, record2))
            label = record2['label'] + ' / ' + record2['created']
        else:
            new = dict(project_history.project_files(directory))
            label = 'Current / Actual / ' + revision(directory / 'engagement.yaml')[:12]
            for name, blob in new.items():
                if name.startswith('attachments/'):
                    __import__('attachments').validate_blob(name,blob)
                elif name != 'engagement.yaml': project_history.validate_image_blob(name, blob)
        from input_guard import load_yaml
        internal=request.args.get('internal')=='1'
        if internal and request.args.get('download')=='1' and request.args.get('ack_private')!='1': abort(422,backend_message('Confirma la descarga privada / Acknowledge the private download'))
        markup = report_compare.render(load_yaml(old['engagement.yaml']), load_yaml(new['engagement.yaml']), old, new,
                                       record['label'] + ' / ' + record['created'], label, request.args.get('lang', 'es'), internal=internal)
        response = Response(markup, mimetype='text/html')
        if request.args.get('download') == '1':
            response.headers['Content-Disposition'] = 'attachment; filename="comparison.html"'
        return response
