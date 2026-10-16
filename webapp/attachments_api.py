"""Revision-bound upload of explicit annexes, excluded from delivery by default."""
from error_messages import message as backend_message
from flask import request, jsonify, abort
from pathlib import Path
from hashlib import sha256
import uuid
import attachments
import engine
import project_history
from storage import revision, atomic_write


def register(api):
    @api.app.post('/api/projects/<slug>/attachments/declare')
    @api.project_lock
    def annex_declare(slug):
        directory=api.proj_dir(slug);api.require_revision(directory/'engagement.yaml')
        payload=api._json_dict()
        if not isinstance(payload,dict) or set(payload)-{'name','required'} or 'name' not in payload or type(payload.get('required',False)) is not bool: abort(422,backend_message('Nombre de anexo requerido / Annex filename required'))
        data=engine.load_engagement(directory/'engagement.yaml')
        data.setdefault('attachments',[]).append(dict(uid=str(uuid.uuid4()),name=payload['name'],required=payload.get('required',False),include=False,reviewed=False))
        data=api.checked_data(data)
        with project_history.transaction(directory) as stage:
            project_history.save(stage,data)
        response=jsonify(data=data)
        response.set_etag(revision(directory/'engagement.yaml'))
        return response

    @api.app.get('/api/projects/<slug>/attachments')
    @api.project_lock
    def annex_inventory(slug):
        directory=api.proj_dir(slug)
        data=engine.load_engagement(directory/'engagement.yaml')
        response=jsonify(files=attachments.inventory(data,directory))
        response.set_etag(revision(directory/'engagement.yaml'))
        return response

    @api.app.post('/api/projects/<slug>/attachments/upload')
    @api.project_lock
    def annex_upload(slug):
        directory=api.proj_dir(slug);api.require_revision(directory/'engagement.yaml')
        upload=request.files.get('file')
        if not upload or not attachments.valid_name(upload.filename): abort(422,backend_message('Nombre o tipo de anexo no permitido / Unsupported annex filename or type'))
        data=engine.load_engagement(directory/'engagement.yaml')
        states=attachments.inventory(data,directory)
        if len(states)>=100 and not any(x['name'].casefold()==upload.filename.casefold() for x in states): abort(422,backend_message('Máximo 100 anexos / Maximum 100 annexes'))
        if any(x['name'].casefold()==upload.filename.casefold() and x['status'] not in ('declared','missing') for x in states):
            abort(422,backend_message('Ya existe un anexo con ese nombre / Annex name already exists'))
        blob=upload.stream.read(attachments.MAX_FILE+1)
        member='attachments/'+uuid.uuid4().hex+Path(upload.filename).suffix.lower()
        attachments.validate_blob(member,blob)
        if sum(x['bytes'] for x in states)+len(blob)>attachments.MAX_TOTAL: abort(422,backend_message('Anexos mayores que 64 MiB / Annexes exceed 64 MiB'))
        row=next((x for x in data.get('attachments',[]) if x['name'].casefold()==upload.filename.casefold()),None)
        if row is None:
            row={'uid':str(uuid.uuid4()),'name':upload.filename};data.setdefault('attachments',[]).append(row)
        row.update(member=member,sha256=sha256(blob).hexdigest(),include=False,reviewed=False)
        with project_history.transaction(directory) as stage:
            atomic_write(stage/member,blob)
            project_history.save(stage,api.checked_data(data))
        response=jsonify(data=data)
        response.set_etag(revision(directory/'engagement.yaml'))
        return response

    @api.app.get('/api/projects/<slug>/attachments/scan')
    @api.project_lock
    def annex_scan(slug):
        directory=api.proj_dir(slug)
        data=engine.load_engagement(directory/'engagement.yaml')
        attachments.validate_rows(data.get('attachments',[]))
        row=next((x for x in data.get('attachments',[]) if x['uid']==request.args.get('uid')),None)
        if row is None:abort(404,backend_message('Anexo inexistente / Annex not found'))
        response=jsonify(dict(attachments.scan(directory,row), uid=row['uid']))
        response.set_etag(revision(directory/'engagement.yaml'))
        response.headers['Cache-Control']='no-store'
        return response
