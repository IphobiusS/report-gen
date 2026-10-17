"""Explicit local-only assistance; proposals are ephemeral and revision bound."""
from error_messages import message as backend_message
import secrets
import threading
import time
from flask import abort, jsonify, session

import editorial_assistant as assistant
import engine
import project_history
from storage import revision


def register(api):
    app, lock, proposals = api.app, threading.RLock(), {}
    inference = threading.Lock()

    def owner():
        token = session.get('csrf')
        if not token:
            abort(403, backend_message('Abre una sesión local / Open a local session'))
        return token

    def prune():
        for key in list(proposals):
            if proposals[key]['expires'] < time.monotonic():
                del proposals[key]

    @app.get('/api/assistant/capabilities')
    def capabilities():
        return jsonify(available=True, optional=True, endpoint=assistant.ENDPOINT, fields=assistant.FIELDS,
                       cloud_warning=assistant.cloud_warning(), connected=False,
                       requires='Ollama + downloaded GGUF + cloud disabled', auto_send=False)

    @app.post('/api/assistant/models')
    def local_models():
        body = api._json_dict()
        if body:
            abort(422, backend_message('No se admiten URLs ni opciones de red / Network options are not accepted'))
        return jsonify(models=assistant.models(deadline=time.monotonic() + 10), endpoint=assistant.ENDPOINT, cloud_warning=assistant.cloud_warning())

    @app.post('/api/projects/<slug>/assistant')
    def proposal(slug):
        body, identity = api._json_dict(), owner()
        with api._PROJECT_LOCK:
            project_history.recover_transactions(api.PROJECTS)
            directory = api.proj_dir(slug)
            path = directory / 'engagement.yaml'
            api.require_revision(path)
            source = engine.load_engagement(path)
            assistant.selection(source, body)
            tag = revision(path)
        if not inference.acquire(blocking=False):
            abort(429, backend_message('Hay una propuesta local en curso; espera a que termine / A local proposal is running'))
        key = None
        try:
            with lock:
                prune()
                if len(proposals) >= 64 or sum(row['owner'] == identity for row in proposals.values()) >= 8:
                    abort(429, backend_message('Demasiadas propuestas temporales / Too many temporary proposals'))
                key = secrets.token_urlsafe(24)
                proposals[key] = dict(owner=identity, slug=slug, value=None, expires=time.monotonic() + 1800)
            result = assistant.propose(source, body)  # Network must not hold the project lock.
            result['revision'] = tag
            with lock:
                proposals[key]['value'] = result
        except Exception:
            with lock:
                if key:
                    proposals.pop(key, None)
            raise
        finally:
            inference.release()
        response = jsonify(**result, proposal_id=key)
        response.set_etag(tag)
        return response

    @app.post('/api/projects/<slug>/assistant/apply')
    @api.project_lock
    def accept(slug):
        body = api._json_dict()
        if set(body) != {'proposal_id', 'fields'} or not isinstance(body.get('proposal_id'), str):
            abort(422, backend_message('Selección editorial inválida / Invalid editorial selection'))
        identity = owner()
        with lock:
            prune()
            record = proposals.get(body['proposal_id'])
            if not record or record['owner'] != identity or record['slug'] != slug:
                abort(404, backend_message('Propuesta temporal inexistente / Temporary proposal not found'))
            proposal = record['value']
            if proposal is None:
                abort(409, backend_message('La propuesta todavía está en curso / Proposal is still running'))
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        api.require_revision(path)
        if proposal['revision'] != revision(path):
            abort(409, backend_message('La revisión cambió; pide una nueva propuesta / Revision changed'))
        updated = api.checked_data(assistant.apply(engine.load_engagement(path), proposal, body['fields']))
        project_history.save(directory, updated)
        with lock:
            proposals.pop(body['proposal_id'], None)
        response = jsonify(data=updated)
        response.set_etag(revision(path))
        return response

    @app.post('/api/projects/<slug>/assistant/discard')
    def discard_assistant(slug):
        body = api._json_dict()
        if set(body) != {'proposal_id'} or not isinstance(body.get('proposal_id'), str):
            abort(422, backend_message('Identificador de propuesta inválido / Invalid proposal identifier'))
        identity = owner()
        with lock:
            prune()
            record = proposals.get(body['proposal_id'])
            if not record or record['owner'] != identity or record['slug'] != slug:
                abort(404, backend_message('Propuesta temporal inexistente / Temporary proposal not found'))
            if record['value'] is None:
                abort(409, backend_message('La propuesta todavía está en curso / Proposal is still running'))
            proposals.pop(body['proposal_id'])
        # Only an ephemeral session-owned suggestion changes, never the project.
        return jsonify(discarded=True)


    @app.post('/api/projects/<slug>/assistant/precheck')
    @api.project_lock
    def editorial_precheck(slug):
        body = api._json_dict()
        if set(body) != {'finding_uids'}:
            abort(422, backend_message('Selección de revisión inválida.', en='Invalid review selection.', pt='Seleção de revisão inválida.'))
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        api.require_revision(path)
        response = jsonify(assistant.editorial_precheck(engine.load_engagement(path), body['finding_uids']))
        response.set_etag(revision(path))
        return response

    @app.post('/api/projects/<slug>/assistant/critique-preview')
    @api.project_lock
    def editorial_critique_preview(slug):
        body = api._json_dict()
        if set(body) != {'finding_uid', 'fields', 'evidence_uids'}:
            abort(422, backend_message('Selección de revisión inválida.', en='Invalid review selection.', pt='Seleção de revisão inválida.'))
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        api.require_revision(path)
        response = jsonify(assistant.critique_context(engine.load_engagement(path), body))
        response.set_etag(revision(path))
        return response

    @app.post('/api/projects/<slug>/assistant/critique')
    def editorial_critique(slug):
        body = api._json_dict()
        with api._PROJECT_LOCK:
            project_history.recover_transactions(api.PROJECTS)
            path = api.proj_dir(slug) / 'engagement.yaml'
            api.require_revision(path)
            source = engine.load_engagement(path)
            assistant.critique_context(source, body)
            tag = revision(path)
        if not inference.acquire(blocking=False):
            abort(429, backend_message('Hay una propuesta local en curso; espera a que termine / A local proposal is running'))
        try:
            value = assistant.critique(source, body)
        finally:
            inference.release()
        value['revision'] = tag
        # Read-only suggestions have no apply token and cannot edit any field.
        response = jsonify(value)
        response.set_etag(tag)
        return response
