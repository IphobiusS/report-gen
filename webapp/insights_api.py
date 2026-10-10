"""Local, revision-guarded analysis/review routes over the existing lock."""
from flask import jsonify, request

import engine
import insights
import project_history
from storage import revision


def register(api):
    app = api.app

    def load(slug):
        directory = api.proj_dir(slug)
        return directory, engine.load_engagement(directory / 'engagement.yaml')

    def language(data):
        return request.args.get('lang') or engine.report_language(data)

    @app.get('/api/projects/<slug>/insights')
    @api.project_lock
    def get_insights(slug):
        directory, data = load(slug)
        response = jsonify(insights.view(data, directory, language(data)))
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @app.get('/api/projects/<slug>/insights/editorial')
    @api.project_lock
    def get_editorial(slug):
        directory, data = load(slug)
        value = insights.view(data, directory, language(data))
        response = jsonify(rules=insights.RULES, issues=value['editorial'], digest=value['digest'])
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response

    @app.post('/api/projects/<slug>/insights')
    @api.project_lock
    def update_insights(slug):
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        api.require_revision(path)
        data = engine.load_engagement(path)
        updated = insights.mutate(data, api._json_dict(), revision(path), directory)
        checked = api.checked_data(updated)
        project_history.save(directory, checked)
        response = jsonify(data=checked, insights=insights.view(checked, directory, language(checked)))
        response.set_etag(revision(path))
        return response
