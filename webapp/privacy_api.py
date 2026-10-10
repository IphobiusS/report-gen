"""Retention inventory for the active project; same origin, session and revision guards."""
from error_messages import message as backend_message
from flask import jsonify,abort
import private_data
from storage import revision


def register(api):
    @api.app.get('/api/projects/<slug>/privacy')
    @api.project_lock
    def privacy_inventory(slug):
        directory=api.proj_dir(slug)
        response=jsonify(private_data.public_inventory(directory))
        response.set_etag(revision(directory/'engagement.yaml'))
        return response

    @api.app.post('/api/projects/<slug>/privacy/prune')
    @api.project_lock
    def privacy_prune(slug):
        directory=api.proj_dir(slug);api.require_revision(directory/'engagement.yaml')
        body=api._json_dict()
        if set(body)!={'categories','inventory_revision','confirm_project'} or body['confirm_project']!=directory.name:
            abort(422,backend_message('Escribe el identificador del proyecto para confirmar / Type project ID to confirm'))
        response=jsonify(private_data.prune(directory,body['categories'],body['inventory_revision']))
        response.set_etag(revision(directory/'engagement.yaml'))
        return response
