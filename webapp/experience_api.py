"""Demo, diagnostics and immutable client delivery endpoints."""
from languages import normalize_language, language_index
from error_messages import message as backend_message
from pathlib import Path
from io import BytesIO
import json
import subprocess
import sys
import tempfile
import uuid
from flask import jsonify, abort, send_file, Response

import delivery
import support_report
import project_history
from storage import revision


def register(api):
    app = api.app

    @app.post('/api/demo')
    @api.project_lock
    def demo():
        body = api._json_dict()
        lang = normalize_language(body.get('lang', 'es'), None)
        if lang is None or set(body) - {'lang'}:
            abort(422, backend_message('Idioma de demostración inválido',
                                      en='Invalid demo language', pt='Idioma de demonstração inválido'))
        # Every click creates a separate copy; no existing project is reset.
        slug = 'nimbus-demo-' + uuid.uuid4().hex[:12]
        suffix = '' if lang == 'es' else '-' + lang
        source = api.REPORT_ROOT / f'examples/nimbus-demo-project{suffix}.zip'
        project_history.import_bundle(source.read_bytes(), api.PROJECTS/slug)
        return jsonify({'slug': slug})

    @app.post('/api/diagnostics')
    def diagnostics():
        body=api._json_dict();lang=normalize_language(body.get('lang','es'), None)
        if lang is None: abort(422,backend_message('Idioma inválido / Invalid language'))
        try:
            result = subprocess.run([sys.executable, str(api.REPORT_ROOT/'diagnostics.py'),'--lang',lang],
                                    capture_output=True, text=True, timeout=40, cwd=api.REPORT_ROOT)
            if result.returncode:
                abort(503, backend_message('El diagnóstico no pudo terminar. Revisa la instalación según README.md.'))
            report = json.loads(result.stdout)
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            abort(503, backend_message('El diagnóstico tardó demasiado. Revisa los motores PDF de la instalación.'))
        with api._PROJECT_LOCK:
            try:
                with tempfile.TemporaryFile(dir=api.PROJECTS) as probe:
                    probe.write(b'report-gen'); probe.flush()
                writable = True
            except OSError:
                writable = False
        report['checks'].append({'id':'storage', 'label':(('Carpeta de proyectos', 'Project directory', 'Diretório de projetos')[language_index(lang)]), 'ready':writable,
                                 'detail':(('Escritura disponible' if writable else 'Revisa los permisos de la carpeta de proyectos', 'Writable' if writable else 'Check project directory permissions', 'Gravação disponível' if writable else 'Verifique as permissões do diretório de projetos')[language_index(lang)])})
        report['support_report'] = support_report.project(report)
        report['support_token'] = support_report.token(report['support_report'], api.app.secret_key)
        return jsonify(report)

    @app.post('/api/diagnostics/download')
    def download_diagnostics():
        body = api._json_dict()
        if set(body) != {'report', 'preview_token'} or not support_report.verified(body.get('report'), body.get('preview_token'), api.app.secret_key):
            abort(409, backend_message('Vuelve a previsualizar el diagnóstico antes de descargar', en='Preview the diagnostic report again before downloading'))
        response = Response(support_report.encode(body['report']), mimetype='application/json')
        response.headers['Content-Disposition'] = 'attachment; filename="report-gen-support.json"'
        return response

    @app.post('/api/projects/<slug>/delivery')
    def prepare_delivery(slug):
        body = api._json_dict()
        formats = body.get('formats')
        label = body.get('label')
        if set(body)-{'formats', 'label', 'acknowledge_warnings'}:
            abort(422, backend_message('Campos de entrega desconocidos'))
        if body.get('acknowledge_warnings', False) not in (True, False) or not isinstance(body.get('acknowledge_warnings', False), bool):
            abort(422, backend_message('Revisión de avisos inválida'))
        with tempfile.TemporaryDirectory(prefix='report-gen-delivery-') as temporary:
            root = Path(temporary)
            with api._PROJECT_LOCK:
                project_history.recover_transactions(api.PROJECTS)
                directory = api.proj_dir(slug)
                api.require_revision(directory/'engagement.yaml')
                identity = revision(directory/'engagement.yaml')
                captured = delivery.capture(directory, root/'source')
            if captured['issues'] and not body.get('acknowledge_warnings'):
                abort(422, backend_message('Revisa los avisos de entrega antes de generar el paquete'))
            try:
                payload = delivery.build(root/'source', formats, identity, label, captured, root/'outputs')
            except subprocess.SubprocessError:
                abort(422, backend_message('Falló una exportación. No se ha creado una entrega parcial.'))
        return send_file(BytesIO(payload), mimetype='application/zip', as_attachment=True,
                         download_name=api.slugify(slug)+'-entrega.zip')
