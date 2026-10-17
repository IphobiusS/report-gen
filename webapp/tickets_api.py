"""Revision-bound, explicitly reviewed exchanges with configured ticket servers."""
from datetime import datetime, timezone
from functools import wraps
import hmac
import hashlib
import json

from flask import abort, jsonify

import engine
import project_history
from error_messages import message
from storage import revision
import ticket_connectors as tickets


def register(api):
    def guarded(fn):
        @wraps(fn)
        def run(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except (ValueError, TypeError, KeyError) as exc:
                abort(422, str(exc))
        return run

    def load(slug):
        directory = api.proj_dir(slug)
        api.require_revision(directory / 'engagement.yaml')
        return directory, engine.load_engagement(directory / 'engagement.yaml'), api._json_dict()

    def signed(slug, rev, value):
        secret = api.app.secret_key
        if isinstance(secret, str):
            secret = secret.encode()
        raw = json.dumps([api.browser_workspace_id(), slug, rev, value], sort_keys=True,
                         ensure_ascii=True, separators=(',', ':')).encode()
        return hmac.new(secret, b'ticket-exchange-v1\x00' + raw, hashlib.sha256).hexdigest()

    def verify(body, token):
        supplied = body.get('preview_token')
        if body.get('ack_reviewed') is not True or not isinstance(supplied, str) or not hmac.compare_digest(supplied.encode(), token.encode()):
            abort(409, message('Revisa de nuevo la comparación antes de aplicar',
                               en='Review the comparison again before applying',
                               pt='Revise novamente a comparação antes de aplicar'))

    def find(data, uid):
        link = next((r for r in data.get('external_tickets', []) if r['uid'] == uid), None)
        if not link:
            abort(404)
        return link

    def response(directory, **body):
        result = jsonify(body)
        result.set_etag(revision(directory / 'engagement.yaml'))
        return result

    def save(directory, data):
        project_history.save(directory, api.checked_data(data))
        return response(directory, data=data)

    @api.app.post('/api/projects/<slug>/tickets')
    @api.project_lock
    @guarded
    def link_ticket(slug):
        directory, data, body = load(slug)
        data, _ = tickets.create_link(data, body)
        return save(directory, data)

    @api.app.delete('/api/projects/<slug>/tickets/<uid>')
    @api.project_lock
    @guarded
    def unlink_ticket(slug, uid):
        directory = api.proj_dir(slug)
        api.require_revision(directory / 'engagement.yaml')
        data = engine.load_engagement(directory / 'engagement.yaml')
        find(data, uid)
        data['external_tickets'] = [r for r in data['external_tickets'] if r['uid'] != uid]
        return save(directory, data)

    @api.app.post('/api/projects/<slug>/tickets/<uid>/pull-preview')
    @api.project_lock
    @guarded
    def pull_preview(slug, uid):
        directory, data, body = load(slug)
        if set(body) != {'credentials'}:
            abort(422)
        link = find(data, uid)
        state = tickets.remote_state(link, tickets.remote_request(link, body['credentials']))
        value = dict(direction='pull', uid=uid, state=state)
        token = signed(slug, revision(directory / 'engagement.yaml'), value)
        return response(directory, remote_state=state, changes=tickets.pull_plan(data, link, state), preview_token=token)

    @api.app.post('/api/projects/<slug>/tickets/<uid>/pull-apply')
    @api.project_lock
    @guarded
    def pull_apply(slug, uid):
        directory, data, body = load(slug)
        if set(body) != {'remote_state', 'accepted', 'preview_token', 'ack_reviewed'}:
            abort(422)
        value = dict(direction='pull', uid=uid, state=body['remote_state'])
        verify(body, signed(slug, revision(directory / 'engagement.yaml'), value))
        candidate = tickets.apply_pull(data, uid, body['remote_state'], body['accepted'])
        find(candidate, uid)['last_exchange'] = datetime.now(timezone.utc).isoformat()
        return save(directory, candidate)

    @api.app.post('/api/projects/<slug>/tickets/<uid>/push-preview')
    @api.project_lock
    @guarded
    def push_preview(slug, uid):
        directory, data, body = load(slug)
        if set(body) != {'fields', 'credentials'}:
            abort(422)
        link = find(data, uid)
        finding = next(f for f in data['findings'] if f['uid'] == link['finding_uid'])
        payload = tickets.push_payload(finding, link['provider'], body['fields'])
        remote = tickets.remote_request(link, body['credentials'])
        remote_hash = tickets.digest(remote)
        value = dict(direction='push', uid=uid, payload=payload, remote_hash=remote_hash)
        return response(directory, payload=payload, changes=tickets.push_changes(link, remote, payload), remote_hash=remote_hash,
                        preview_token=signed(slug, revision(directory / 'engagement.yaml'), value))

    @api.app.post('/api/projects/<slug>/tickets/<uid>/push-apply')
    @api.project_lock
    @guarded
    def push_apply(slug, uid):
        directory, data, body = load(slug)
        if set(body) != {'fields', 'credentials', 'remote_hash', 'preview_token', 'ack_reviewed'}:
            abort(422)
        link = find(data, uid)
        finding = next(f for f in data['findings'] if f['uid'] == link['finding_uid'])
        payload = tickets.push_payload(finding, link['provider'], body['fields'])
        value = dict(direction='push', uid=uid, payload=payload, remote_hash=body['remote_hash'])
        verify(body, signed(slug, revision(directory / 'engagement.yaml'), value))
        # Re-read immediately before writing. Remote APIs don't offer a shared
        # transaction with our local project; this is not an atomic remote CAS.
        before = tickets.remote_request(link, body['credentials'])
        if tickets.digest(before) != body['remote_hash']:
            abort(409, message('El ticket cambió; vuelve a compararlo', en='The ticket changed; compare it again',
                               pt='O ticket mudou; compare-o novamente'))
        tickets.remote_request(link, body['credentials'], 'PUT' if link['provider'] == 'jira' else 'PATCH', payload)
        link['last_exchange'] = datetime.now(timezone.utc).isoformat()
        return save(directory, data)
