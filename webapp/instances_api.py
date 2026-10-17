"""Revision-bound affected instance changes and independent retest records."""
from copy import deepcopy
from functools import wraps

from flask import abort, jsonify, request

import engine
import finding_instances as instances
from error_messages import message
import project_history as history
from storage import revision


def register(api):
    def errors(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            try: return fn(*args, **kwargs)
            except ValueError as exc: abort(422, str(exc))
        return wrapped

    def read(slug, finding_uid, instance_uid=None, mutate=False):
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        if mutate:
            api.require_revision(path)
            if request.args:
                abort(422, message('Opciones de instancia inválidas', en='Invalid instance options', pt='Opções de instância inválidas'))
        data = engine.load_engagement(path)
        finding = next((row for row in data.get('findings', []) if row.get('uid') == finding_uid), None)
        if finding is None: abort(404)
        instance = None
        if instance_uid is not None:
            instance = next((row for row in finding.get('instances', []) if row.get('uid') == instance_uid), None)
            if instance is None: abort(404)
        return directory, data, finding, instance

    def response(directory, data, finding, save=False, **extra):
        instances.validate(data)
        if save:
            history.save(directory, api.checked_data(data))
        result = jsonify(data=data, instances=finding.get('instances', []), summary=instances.summary(finding, api.current_language()), **extra)
        result.set_etag(revision(directory/'engagement.yaml'))
        return result

    @api.app.get('/api/projects/<slug>/findings/<finding_uid>/instances')
    @api.project_lock
    @errors
    def instance_list(slug, finding_uid):
        directory, data, finding, _ = read(slug, finding_uid)
        return response(directory, data, finding)

    @api.app.get('/api/projects/<slug>/findings/<finding_uid>/instances/<instance_uid>')
    @api.project_lock
    @errors
    def instance_get(slug, finding_uid, instance_uid):
        directory, data, finding, instance = read(slug, finding_uid, instance_uid)
        return response(directory, data, finding, instance=instance)

    @api.app.post('/api/projects/<slug>/findings/<finding_uid>/instances')
    @api.project_lock
    @errors
    def instance_create(slug, finding_uid):
        directory, data, finding, _ = read(slug, finding_uid, mutate=True)
        instance = instances.new_instance(api._json_dict())
        finding.setdefault('instances', []).append(instance)
        instances.update_aggregate(finding)
        return response(directory, data, finding, save=True, instance=instance)

    @api.app.put('/api/projects/<slug>/findings/<finding_uid>/instances/<instance_uid>')
    @api.project_lock
    @errors
    def instance_update(slug, finding_uid, instance_uid):
        directory, data, finding, instance = read(slug, finding_uid, instance_uid, mutate=True)
        body = api._json_dict()
        if not body or set(body) - instances.FIELDS:
            abort(422, message('Campos de instancia inválidos', en='Invalid instance fields', pt='Campos de instância inválidos'))
        instance.update(deepcopy(body))
        instances.update_aggregate(finding)
        return response(directory, data, finding, save=True, instance=instance)

    @api.app.delete('/api/projects/<slug>/findings/<finding_uid>/instances/<instance_uid>')
    @api.project_lock
    @errors
    def instance_delete(slug, finding_uid, instance_uid):
        directory, data, finding, instance = read(slug, finding_uid, instance_uid, mutate=True)
        if api._json_dict() != {'ack_delete': True}:
            abort(422, message('Confirma la eliminación de la instancia y sus retests', en='Confirm removal of the instance and its retests', pt='Confirme a remoção da instância e seus retestes'))
        finding['instances'].remove(instance)
        instances.update_aggregate(finding)
        return response(directory, data, finding, save=True)

    @api.app.post('/api/projects/<slug>/findings/<finding_uid>/instances/<instance_uid>/retests')
    @api.project_lock
    @errors
    def instance_retest(slug, finding_uid, instance_uid):
        directory, data, finding, _ = read(slug, finding_uid, instance_uid, mutate=True)
        record = instances.record_retest(data, finding, instance_uid, api._json_dict(), history.now())
        return response(directory, data, finding, save=True, retest=record)
