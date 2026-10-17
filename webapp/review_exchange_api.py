"""Saved-revision review exchange and versioned client writing requirements."""
from pathlib import Path
import hashlib
import hmac

from flask import abort, jsonify, request, session

import client_profiles
import engine
import project_history
import review_exchange
from error_messages import message
from storage import revision


def register(api):
    def read(slug, fields):
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        api.require_revision(path)
        body = api._json_dict()
        if set(body) != set(fields) or request.args:
            abort(422, review_exchange.fail().args[0])
        return directory, path, body, engine.load_engagement(path)

    def token(slug, tag, kind, payload):
        secret = api.app.secret_key
        if isinstance(secret, str):
            secret = secret.encode('utf-8')
        value = review_exchange.packed([session.get('csrf'), slug, tag, kind, payload])
        return hmac.new(secret, value, hashlib.sha256).hexdigest()

    def require_token(supplied, expected):
        if not isinstance(supplied, str) or not hmac.compare_digest(supplied.encode('utf-8'), expected.encode('ascii')):
            abort(409, message('La revisión cambió. Vuelve a previsualizar.', en='The review changed. Preview again.', pt='A revisão mudou. Visualize novamente.'))

    def response(value, path):
        result = jsonify(value)
        result.set_etag(revision(path))
        return result

    @api.app.post('/api/projects/<slug>/review-exchange/issue-preview')
    @api.project_lock
    def review_issue_preview(slug):
        _, path, body, data = read(slug, {'finding_uids', 'fields'})
        _, package = review_exchange.issue(data, slug, revision(path), body['finding_uids'], body['fields'])
        return response(dict(rows=package['rows'], revision=revision(path),
                             preview_token=token(slug, revision(path), 'issue', body)), path)

    @api.app.post('/api/projects/<slug>/review-exchange/issue')
    @api.project_lock
    def review_issue(slug):
        directory, path, body, data = read(slug, {'finding_uids', 'fields', 'preview_token', 'ack_private', 'lang'})
        if body['ack_private'] is not True or body['lang'] not in ('es', 'en', 'pt'):
            abort(422, review_exchange.fail().args[0])
        selection = {key: body[key] for key in ('finding_uids', 'fields')}
        require_token(body['preview_token'], token(slug, revision(path), 'issue', selection))
        updated, package = review_exchange.issue(data, slug, revision(path), body['finding_uids'], body['fields'])
        html = review_exchange.editor_html(package, body['lang'])
        checked = api.checked_data(updated)
        project_history.save(directory, checked)
        return response(dict(data=checked, package_uid=package['uid'], editor_html=html), path)

    @api.app.post('/api/projects/<slug>/review-exchange/preview')
    @api.project_lock
    def review_preview(slug):
        _, path, body, data = read(slug, {'text'})
        value = review_exchange.preview(data, slug, body['text'])
        return response(dict(**value, revision=revision(path), preview_token=token(slug, revision(path), 'return', value)), path)

    @api.app.post('/api/projects/<slug>/review-exchange/apply')
    @api.project_lock
    def review_apply(slug):
        directory, path, body, data = read(slug, {'text', 'preview_token', 'selected', 'ack_reviewed'})
        if body['ack_reviewed'] is not True:
            abort(422, review_exchange.fail().args[0])
        value = review_exchange.preview(data, slug, body['text'])
        require_token(body['preview_token'], token(slug, revision(path), 'return', value))
        updated = api.checked_data(review_exchange.apply(data, value, body['selected']))
        # Authorship is a local declaration. No review approval is fabricated.
        project_history.save(directory, updated)
        return response(dict(data=updated, applied=len(body['selected']), reviewer=value['reviewer'], authenticated=False), path)

    @api.app.post('/api/projects/<slug>/review-exchange/forget')
    @api.project_lock
    def review_forget(slug):
        directory, path, body, data = read(slug, {'package_uid', 'ack_forget'})
        if body['ack_forget'] is not True:
            abort(422, review_exchange.fail().args[0])
        updated = api.checked_data(review_exchange.forget(data, body['package_uid']))
        project_history.save(directory, updated)
        return response(dict(data=updated), path)

    def catalog_path():
        return Path(api.app.config.get('CLIENT_PROFILES_PATH', Path(api.app.config['WORKSPACE_ROOT']) / 'client-profiles.json'))

    @api.app.get('/api/client-profiles')
    @api.project_lock
    def list_client_profiles():
        value = client_profiles.load(catalog_path())
        result = jsonify(**value, sections=[dict(key=row['key'], es=row.get('title_es', row['key']),
                                               en=row.get('title_en', row['key']), pt=row.get('title_pt', row['key']))
                                        for row in client_profiles.sections.load_catalog()['sections']])
        return result

    @api.app.post('/api/client-profiles')
    @api.project_lock
    def save_client_profile():
        body = api._json_dict()
        if set(body) != {'profile', 'expected_version'}:
            abort(422, client_profiles.invalid().args[0])
        return jsonify(profile=client_profiles.save(catalog_path(), body['profile'], body['expected_version']))

    @api.app.get('/api/projects/<slug>/client-profile')
    @api.project_lock
    def client_requirements(slug):
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        return response(client_profiles.requirements(engine.load_engagement(path)), path)

    @api.app.post('/api/projects/<slug>/client-profile/preview')
    @api.project_lock
    def preview_client_profile(slug):
        _, path, body, data = read(slug, {'profile_uid', 'version'})
        profile = client_profiles.get(catalog_path(), body['profile_uid'], body['version'])
        value = client_profiles.preview(data, profile)
        return response(dict(**value, revision=revision(path), preview_token=token(slug, revision(path), 'profile', value)), path)

    @api.app.post('/api/projects/<slug>/client-profile/apply')
    @api.project_lock
    def apply_client_profile(slug):
        directory, path, body, data = read(slug, {'profile_uid', 'version', 'selected', 'preview_token'})
        profile = client_profiles.get(catalog_path(), body['profile_uid'], body['version'])
        value = client_profiles.preview(data, profile)
        require_token(body['preview_token'], token(slug, revision(path), 'profile', value))
        updated = api.checked_data(client_profiles.apply(data, value, body['selected']))
        project_history.save(directory, updated)
        return response(dict(data=updated), path)
