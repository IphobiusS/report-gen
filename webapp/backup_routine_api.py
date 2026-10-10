"""Private local controls for opt-in periodic workspace backups."""
from pathlib import Path
import threading
from flask import jsonify
from error_messages import message
from backup_routine import BackupRoutine


def register(api):
    services = {}
    service_lock = threading.Lock()

    def routine():
        paths = (api.PROJECTS, Path(api.app.config['LIBRARY_PATH']), Path(api.app.config['DESIGN_LIBRARY_PATH']))
        key = tuple(str(Path(path).absolute()) for path in paths)
        with service_lock:
            if key not in services:
                services[key] = BackupRoutine(*paths, api.REPORT_ROOT, api._PROJECT_LOCK)
            return services[key]

    @api.app.get('/api/workspace/backup-routine')
    def routine_status():
        return jsonify(routine().status())

    @api.app.put('/api/workspace/backup-routine')
    def routine_configure():
        return jsonify(routine().configure(api._json_dict()))

    @api.app.post('/api/workspace/backup-routine/disable')
    def routine_disable():
        body = api._json_dict()
        if body:
            raise ValueError(message('Se esperaba un objeto vacío.', en='Expected an empty object.'))
        return jsonify(routine().disable())

    @api.app.post('/api/workspace/backup-routine/run')
    def routine_run():
        body = api._json_dict()
        if body:
            raise ValueError(message('Se esperaba un objeto vacío.', en='Expected an empty object.'))
        return jsonify(routine().run())

    @api.app.post('/api/workspace/backup-routine/verify')
    def routine_verify():
        body = api._json_dict()
        if body:
            raise ValueError(message('Se esperaba un objeto vacío.', en='Expected an empty object.'))
        return jsonify(routine().verify_latest())

    return routine
