"""Reviewed, revision-bound bulk assignments; never technical verification."""
from copy import deepcopy
from datetime import date
import hashlib
import hmac
import json
import re

from flask import abort, jsonify, request

import engine
from error_messages import message
import project_history
from root_cause import UID, resolved_action
from storage import revision

FIELDS = {'owner', 'due_date', 'root_cause_uid'}
MAX_FINDINGS = 500
UNSAFE = re.compile(r'[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]')


def plan(data, selected, values):
    if (not isinstance(selected, list) or not 1 <= len(selected) <= MAX_FINDINGS
            or any(not isinstance(uid, str) for uid in selected) or len(set(selected)) != len(selected)):
        raise ValueError(message('Selecciona entre 1 y 500 hallazgos distintos', en='Select 1 to 500 distinct findings'))
    if not isinstance(values, dict) or not values or set(values) - FIELDS:
        raise ValueError(message('Selecciona solo responsable, fecha o grupo', en='Select only owner, date or group'))
    for field, value in values.items():
        if not isinstance(value, str) or len(value) > (200 if field == 'owner' else 36) or UNSAFE.search(value):
            raise ValueError(message('Valor de asignación inválido', en='Invalid assignment value'))
        if value and not value.strip():
            raise ValueError(message('Usa un valor o déjalo vacío para retirarlo', en='Use a value or leave it empty to clear'))
        try:
            value.encode('utf-8')
        except UnicodeEncodeError:
            raise ValueError(message('Texto de asignación inválido', en='Invalid assignment text')) from None
    if values.get('due_date'):
        try:
            if date.fromisoformat(values['due_date']).isoformat() != values['due_date']:
                raise ValueError
        except ValueError:
            raise ValueError(message('Fecha inválida: usa AAAA-MM-DD', en='Invalid date: use YYYY-MM-DD')) from None
    if values.get('root_cause_uid') and values['root_cause_uid'] not in {g['uid'] for g in data.get('root_cause_groups', [])}:
        raise ValueError(message('El grupo ya no existe', en='The group no longer exists'))
    rows = data.get('findings', [])
    if (any(not isinstance(f, dict) or not isinstance(f.get('uid'), str) or not UID.fullmatch(f['uid']) for f in rows)
            or len({f['uid'] for f in rows}) != len(rows)):
        raise ValueError(message('Abre y guarda el proyecto para asignar identidades permanentes antes de editar por lotes',
                                 en='Open and save the project to assign permanent identities before bulk editing'))
    findings = {f['uid']: f for f in rows}
    if any(uid not in findings for uid in selected):
        raise ValueError(message('Un hallazgo seleccionado ya no existe', en='A selected finding no longer exists'))
    changes = []
    for uid in selected:
        finding = findings[uid]
        for field, after in values.items():
            before = finding.get(field, '')
            if before != after:
                change = dict(finding_uid=uid, id=finding.get('id', ''), title=finding.get('title', ''),
                              field=field, before=before, after=after)
                if field == 'root_cause_uid':
                    change['effective_action_before'] = resolved_action(data, finding)
                    change['effective_action_after'] = resolved_action(data, {**finding, field: after})
                changes.append(change)
    return changes


def register(api):
    def read(slug, applying=False):
        directory = api.proj_dir(slug)
        path = directory / 'engagement.yaml'
        api.require_revision(path)
        body = api._json_dict()
        expected = {'finding_uids', 'values'} | ({'preview_token', 'ack_reviewed'} if applying else set())
        if set(body) != expected or request.args:
            abort(422, message('Opciones de edición por lotes inválidas', en='Invalid bulk edit options'))
        data = engine.load_engagement(path)
        changes = plan(data, body['finding_uids'], body['values'])
        current = revision(path)
        payload = json.dumps([api.browser_workspace_id(), slug, current, body['finding_uids'], body['values'], changes],
                             sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode()
        secret = api.app.secret_key
        if isinstance(secret, str):
            secret = secret.encode()
        token = hmac.new(secret, b'bulk-edit-v1\x00' + payload, hashlib.sha256).hexdigest()
        if applying:
            if body['ack_reviewed'] is not True:
                abort(422, message('Confirma los cambios revisados', en='Confirm the reviewed changes'))
            supplied = body['preview_token']
            if not isinstance(supplied, str) or not hmac.compare_digest(token.encode('ascii'), supplied.encode('utf-8')):
                abort(409, message('Vuelve a comparar estos cambios con la revisión actual', en='Compare these changes again against the current revision'))
            if not changes:
                abort(422, message('No hay cambios para guardar', en='There are no changes to save'))
        return directory, path, body, data, changes, current, token

    @api.app.post('/api/projects/<slug>/bulk-edit/preview')
    @api.project_lock
    def bulk_edit_preview(slug):
        _, _, _, _, changes, current, token = read(slug)
        response = jsonify(changes=changes, preview_token=token, revision=current)
        response.set_etag(current)
        return response

    @api.app.post('/api/projects/<slug>/bulk-edit/apply')
    @api.project_lock
    def bulk_edit_apply(slug):
        directory, path, _, data, changes, _, _ = read(slug, applying=True)
        updated = deepcopy(data)
        findings = {f['uid']: f for f in updated['findings']}
        for change in changes:
            if change['after'] == '':
                findings[change['finding_uid']].pop(change['field'], None)
            else:
                findings[change['finding_uid']][change['field']] = change['after']
        project_history.save(directory, api.checked_data(updated))
        response = jsonify(data=updated, applied=len(changes))
        response.set_etag(revision(path))
        return response
