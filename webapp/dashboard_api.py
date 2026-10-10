"""Portable project organization with the same revision guard as report edits."""
from flask import jsonify, abort

import engine
import project_catalog
import project_history
from error_messages import message
from storage import revision


def register(api):
    @api.app.post('/api/projects/<slug>/management')
    @api.project_lock
    def update_management(slug):
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        api.require_revision(path)
        body = api._json_dict()
        try:
            project_catalog.validate_metadata(body)
        except ValueError as exc:
            abort(422, str(exc))
        if not body:
            abort(422, message('No hay cambios de gestión', en='No project management changes'))
        data = engine.load_engagement(path)
        data.setdefault('project_management', {}).update(body)
        project_history.save(directory, data)
        response = jsonify(ok=True, project_management=data['project_management'])
        response.set_etag(revision(path))
        return response
