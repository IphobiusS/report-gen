"""Revision-bound native audience packages, isolated from the author's project."""
from error_messages import message as backend_message
from io import BytesIO
from pathlib import Path
import subprocess
import tempfile

from flask import abort, jsonify, send_file
import audience
import delivery
import engine
import project_history
from storage import revision


def register(api):
    app = api.app

    def options(body, export=False):
        allowed = audience.OPTION_KEYS | (audience.EXPORT_KEYS if export else set())
        if set(body) - allowed:
            abort(422, backend_message('Campos de destinatario desconocidos / Unknown audience fields'))
        return {key: value for key, value in body.items() if key in audience.OPTION_KEYS}

    @app.post('/api/projects/<slug>/audiences/preview')
    @api.project_lock
    def audience_preview(slug):
        directory = api.proj_dir(slug)
        body = api._json_dict()
        api.require_revision(directory / 'engagement.yaml')
        data = engine.load_engagement(directory / 'engagement.yaml')
        result = audience.preview(data, directory, options(body))
        result.pop('data')
        result['revision'] = revision(directory / 'engagement.yaml')
        response = jsonify(result)
        response.set_etag(result['revision'])
        return response

    @app.post('/api/projects/<slug>/audiences/export')
    def audience_export(slug):
        body = api._json_dict()
        selected_options = options(body, True)
        formats, label = body.get('formats'), body.get('label')
        if (not isinstance(formats, list) or not formats or len(formats) > len(delivery.FORMATS)
                or any(not isinstance(fmt, str) or fmt not in delivery.FORMATS for fmt in formats)
                or len(set(formats)) != len(formats)):
            abort(422, backend_message('Selecciona PDF, Word, Markdown o HTML sin duplicados / Select distinct native formats'))
        if not isinstance(label, str) or not label.strip() or len(label) > 120:
            abort(422, backend_message('Nombre de entrega inválido / Invalid delivery name'))
        if type(body.get('acknowledge_warnings', False)) is not bool:
            abort(422, backend_message('Confirmación de avisos inválida / Invalid warning acknowledgement'))
        with tempfile.TemporaryDirectory(prefix='report-gen-audience-') as temporary:
            root = Path(temporary)
            with api._PROJECT_LOCK:
                project_history.recover_transactions(api.PROJECTS)
                directory = api.proj_dir(slug)
                api.require_revision(directory / 'engagement.yaml')
                identity = revision(directory / 'engagement.yaml')
                source = engine.load_engagement(directory / 'engagement.yaml')
                captured = audience.capture(source, directory, root / 'source', selected_options)
            if captured['issues'] and not body.get('acknowledge_warnings'):
                abort(422, backend_message('Revisa los avisos antes de generar el extracto / Review warnings before generating the derivative'))
            try:
                payload = audience.build(root / 'source', formats, identity, label.strip(), captured, root / 'outputs')
            except subprocess.SubprocessError:
                abort(422, backend_message('Falló la exportación; no se ha creado una entrega parcial / Export failed; no partial delivery was created'))
        return send_file(BytesIO(payload), mimetype='application/zip', as_attachment=True,
                         download_name=('caso-publico.zip' if selected_options['profile'] == 'public' else
                                        'resumen-direccion.zip' if selected_options['profile'] == 'executive' else
                                        api.slugify(slug) + '-technical.zip'))
