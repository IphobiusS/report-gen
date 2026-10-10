"""Opt-in public checks and private staging; no in-process code replacement."""
from pathlib import Path
import tempfile
import threading
from flask import abort, jsonify
from itsdangerous import URLSafeTimedSerializer, BadData

from error_messages import current_language, message
import update_helper
import workspace_backup
from version import __version__


def register(api):
    serializer = URLSafeTimedSerializer(api.app.secret_key, salt='report-gen-update-030')
    lock = threading.Lock()

    @api.app.post('/api/update/check')
    def check_update():
        body = api._json_dict()
        if set(body) != {'allow_network'} or body['allow_network'] is not True:
            abort(422, message('Autoriza la consulta pública a GitHub.', en='Allow the public GitHub check.'))
        try:
            inspected = update_helper.inspect_release(__version__)
        except (OSError, ValueError):
            abort(503, message('No se pudo verificar la publicación oficial. Puedes reintentar; la instalación actual se conserva.',
                               en='The official release could not be verified. You can retry; the current installation is preserved.'))
        if isinstance(inspected, dict):
            return jsonify(inspected)
        plan, _ = inspected
        ticket = serializer.dumps({'plan': plan, 'workspace': api.browser_workspace_id()})
        return jsonify({**plan, 'preview_token': ticket})

    @api.app.post('/api/update/prepare')
    def prepare_update():
        body = api._json_dict()
        if (set(body) != {'allow_network', 'ack_private_backup', 'preview_token'}
                or body['allow_network'] is not True or body['ack_private_backup'] is not True
                or not isinstance(body['preview_token'], str) or len(body['preview_token']) > 16000):
            abort(422, message('Revisa la descarga y el respaldo privado antes de preparar.',
                               en='Review the download and private backup before preparing.'))
        try:
            review = serializer.loads(body['preview_token'], max_age=1800)
            if review['workspace'] != api.browser_workspace_id():
                raise ValueError
            plan = review['plan']
        except (BadData, KeyError, TypeError, ValueError):
            abort(409, message('La consulta caducó. Comprueba de nuevo la publicación.',
                               en='The check expired. Check the release again.'))
        if not lock.acquire(blocking=False):
            abort(409, message('Ya hay una preparación en curso. Espera y vuelve a consultar.',
                               en='Preparation is already running. Wait and retry.'))
        try:
            inspected = update_helper.inspect_release(__version__, plan['release_id'])
            if not isinstance(inspected, tuple) or inspected[0] != plan:
                abort(409, message('La publicación cambió. Compruébala de nuevo antes de descargar.',
                                   en='The release changed. Check it again before downloading.'))
            _, manifest = inspected
            payload = update_helper._asset_blob(plan['assets']['zip'], update_helper.MAX_PACKAGE)
            base = Path(api.app.config.get('UPDATE_STAGE_ROOT', Path.home() / 'report-gen-updates'))

            def backup():
                paths = (api.PROJECTS, Path(api.app.config['LIBRARY_PATH']), Path(api.app.config['DESIGN_LIBRARY_PATH']))
                with api._PROJECT_LOCK:
                    blob = workspace_backup.export_workspace(*paths)
                    # A throwaway restore validates nested project hashes, schemas,
                    # evidence and histories before claiming this backup is ready.
                    with tempfile.TemporaryDirectory(prefix='.backup-check-', dir=base) as name:
                        root = Path(name)
                        workspace_backup.restore_workspace(blob, root / 'projects', root / 'library/findings.json', root / 'library/designs.json')
                    return blob

            receipt = update_helper.prepare(plan, manifest, payload, backup, base=base,
                current=api.REPORT_ROOT, workspace=api.app.config['WORKSPACE_ROOT'],
                external=api.app.config['WORKSPACE_EXTERNAL'], scope=review['workspace'], lang=current_language())
            return jsonify(receipt)
        except (OSError, ValueError):
            abort(503, message('No se pudo preparar y verificar el paquete y su respaldo. La instalación actual se conserva. Comprueba espacio libre y permisos; puedes reintentar.',
                               en='The package and backup could not be prepared and verified. The current installation is preserved. Check free space and permissions; you can retry.'))
        finally:
            lock.release()
