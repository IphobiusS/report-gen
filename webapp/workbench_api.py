"""Capture intake shares the project revision, transaction and history boundary."""
from error_messages import message as backend_message
from flask import jsonify
import capture_inbox
import engine
import project_history
from storage import revision


def register(api):
    @api.app.post('/api/projects/<slug>/captures')
    @api.project_lock
    def add_capture(slug):
        directory = api.proj_dir(slug)
        api.require_revision(directory / 'engagement.yaml')
        data = engine.load_engagement(directory / 'engagement.yaml')
        with project_history.transaction(directory) as staged:
            data, capture = capture_inbox.create(data, staged, api._json_dict())
            project_history.save(staged, api.checked_data(data))
        response = jsonify(data=data, capture_uid=capture['uid'])
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @api.app.post('/api/projects/<slug>/captures/<uid>/link')
    @api.project_lock
    def link_capture(slug, uid):
        directory = api.proj_dir(slug)
        api.require_revision(directory / 'engagement.yaml')
        body = api._json_dict()
        if set(body) != {'finding_uid'} or not isinstance(body['finding_uid'], str):
            raise ValueError(backend_message('Selecciona un hallazgo / Select a finding'))
        data = capture_inbox.link(engine.load_engagement(directory / 'engagement.yaml'), directory, uid, body['finding_uid'])
        project_history.save(directory, api.checked_data(data))
        response = jsonify(data=data)
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @api.app.post('/api/projects/<slug>/draft-check')
    @api.project_lock
    def check_recovered_draft(slug):
        directory=api.proj_dir(slug)
        api.require_revision(directory/'engagement.yaml')
        # Structural validation only: unfinished wording is allowed in a draft.
        data=api.checked_data(api._json_dict())
        return jsonify(data=data)
