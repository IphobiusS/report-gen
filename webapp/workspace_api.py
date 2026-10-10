"""Workspace backup endpoints use the same local session and project lock."""
from error_messages import message as backend_message
from io import BytesIO
from flask import request, send_file, jsonify, abort
import workspace_backup


def register(api):
    def paths():
        return (api.PROJECTS, api.app.config['LIBRARY_PATH'], api.app.config['DESIGN_LIBRARY_PATH'])

    @api.app.before_request
    def recover_workspace():
        if request.path.startswith('/api/'):
            with api._PROJECT_LOCK:
                workspace_backup.recover(*paths())

    @api.app.post('/api/workspace/backup')
    @api.project_lock
    def workspace_export():
        api._json_dict()
        payload = workspace_backup.export_workspace(*paths())
        return send_file(BytesIO(payload), mimetype='application/zip', as_attachment=True,
                         download_name='report-gen-workspace.zip')

    @api.app.post('/api/workspace/restore')
    @api.project_lock
    def workspace_restore():
        upload = request.files.get('file')
        if not upload:
            abort(400, backend_message('Selecciona un respaldo integral'))
        blob = upload.stream.read(workspace_backup.MAX_ARCHIVE + 1)
        if len(blob) > workspace_backup.MAX_ARCHIVE:
            abort(413, backend_message('Respaldo integral mayor que 256 MiB'))
        return jsonify(workspace_backup.restore_workspace(blob, *paths()))
