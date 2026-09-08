"""Workflow routes registered against the existing app and its project lock."""
from io import BytesIO
from pathlib import Path
import yaml
from flask import request, jsonify, abort, send_file
import engine
import evidence as evidence_lib
import finding_library as lib
import project_history as history
import workflows
from storage import atomic_write, revision


def register(api):
    app = api.app
    app.config.setdefault('LIBRARY_PATH', str(api.HERE / 'library' / 'findings.json'))

    def project(slug, mutate=False):
        d = api.proj_dir(slug)
        if mutate: api.require_revision(d / 'engagement.yaml')
        return d, engine.load_engagement(d / 'engagement.yaml')

    def saved(d, data, **extra):
        history.save(d, api.checked_data(data))
        response = jsonify(dict(data=data, **extra)); response.set_etag(revision(d / 'engagement.yaml'))
        return response

    def json_response(data, d=None):
        response = jsonify(data)
        if d: response.set_etag(revision(d / 'engagement.yaml'))
        return response

    def errors(fn):
        from functools import wraps
        @wraps(fn)
        def wrapped(*args, **kwargs):
            try: return fn(*args, **kwargs)
            except (ValueError, yaml.YAMLError) as exc: abort(422, str(exc))
        return wrapped

    @app.get('/api/projects/<slug>/history')
    @api.project_lock
    @errors
    def versions(slug):
        d, _ = project(slug)
        return jsonify([dict((k, v) for k, v in record.items() if k != 'files') for record in history.history(d)])

    @app.post('/api/projects/<slug>/history')
    @api.project_lock
    @errors
    def checkpoint(slug):
        d, _ = project(slug, True); body = api._json_dict()
        record = history.checkpoint(d, body.get('label', ''), body.get('stage', 'draft'), force=True)
        return json_response(record, d)

    @app.get('/api/projects/<slug>/history/<sid>/compare')
    @api.project_lock
    @errors
    def compare(slug, sid):
        d, data = project(slug)
        other = request.args.get('to')
        if other: data = history.snapshot_data(d, other)
        return jsonify(workflows.compare(history.snapshot_data(d, sid), data))

    @app.post('/api/projects/<slug>/history/<sid>/restore')
    @api.project_lock
    @errors
    def restore(slug, sid):
        d, _ = project(slug, True)
        history.restore(d, sid)
        return json_response({'data': engine.load_engagement(d / 'engagement.yaml')}, d)

    @app.get('/api/projects/<slug>/bundle')
    @api.project_lock
    @errors
    def bundle(slug):
        d, _ = project(slug)
        return send_file(BytesIO(history.export_bundle(d)), mimetype='application/zip', as_attachment=True, download_name=api.slugify(slug) + '-project.zip')

    @app.post('/api/projects/import')
    @api.project_lock
    @errors
    def import_project():
        file = request.files.get('file')
        if not file: abort(400, 'Selecciona un respaldo ZIP de proyecto')
        slug = api.slugify(request.form.get('slug', '') or Path(file.filename or '').stem)
        target = api.PROJECTS / slug
        if target.exists(): abort(409, 'Ese proyecto ya existe. Usa otro nombre para importar una copia')
        history.import_bundle(file.read(history.MAX_ARCHIVE + 1), target)
        return jsonify({'slug': slug})

    @app.get('/api/projects/<slug>/review')
    @api.project_lock
    @errors
    def review(slug):
        d, data = project(slug)
        issues = workflows.review(data, d)
        issues.extend(dict(level=level, message=msg, path='report', finding_uid=None) for level, msg in api.validatelib.validate(data))
        return jsonify({'issues': issues})

    @app.get('/api/projects/<slug>/evidence')
    @api.project_lock
    @errors
    def evidence(slug):
        d, data = project(slug)
        known = {e['src'] for e in data.get('evidence', [])}
        images = [{'src': 'img/' + p.name} for p in sorted((d / 'img').glob('*')) if p.is_file() and not p.is_symlink() and 'img/' + p.name not in known]
        return jsonify({'evidence': data.get('evidence', []), 'unlinked': images})

    @app.post('/api/projects/<slug>/evidence')
    @api.project_lock
    @errors
    def register_evidence(slug):
        d, data = project(slug, True); body = api._json_dict(); source = body.get('src', '')
        from resources import local_image
        if not isinstance(source, str) or not workflows.safe_member(source, 'img/'): raise ValueError('Ruta de evidencia inválida')
        path = local_image(source, d)
        title = body.get('title', path.stem)
        if not isinstance(title, str) or len(title) > 300: raise ValueError('Título inválido')
        if any(e['src'] == source for e in data.get('evidence', [])): raise ValueError('Esta imagen ya está registrada')
        uid = workflows.new_uid(); original = 'originals/' + uid + path.suffix.lower()
        atomic_write(d / original, path.read_bytes())
        data.setdefault('evidence', []).append({'uid': uid, 'title': title, 'caption': '', 'src': source, 'original': original})
        return saved(d, data)

    @app.post('/api/projects/<slug>/evidence/<uid>/edit')
    @api.project_lock
    @errors
    def edit_evidence(slug, uid):
        d, data = project(slug, True); body = api._json_dict()
        entry = next((e for e in data.get('evidence', []) if e['uid'] == uid), None)
        if not entry: abort(404, 'Evidencia inexistente')
        history.checkpoint(d)
        old = entry['src']; new = evidence_lib.edit_image(d, old, body.get('operations'))
        data = evidence_lib.replace_references(data, old, new)
        response = saved(d, data)
        # The original remains in originals/ and historical objects, never as an export candidate.
        (d / old).unlink(missing_ok=True)
        history.checkpoint(d)
        return response

    @app.get('/api/projects/<slug>/evidence/<uid>/original')
    @api.project_lock
    @errors
    def original(slug, uid):
        d, data = project(slug)
        entry = next((e for e in data.get('evidence', []) if e['uid'] == uid), None)
        if not entry or not workflows.safe_member(entry.get('original'), 'originals/'): abort(404)
        path = (d / entry['original']).resolve()
        if not path.is_relative_to((d / 'originals').resolve()) or not path.is_file(): abort(404)
        return send_file(path, as_attachment=True, download_name='original-' + Path(entry['original']).name)

    @app.post('/api/projects/<slug>/retest')
    @api.project_lock
    @errors
    def retest(slug):
        d, data = project(slug, True); body = api._json_dict()
        finding = next((f for f in data['findings'] if f.get('uid') == body.get('finding_uid')), None)
        if not finding: abort(404, 'Hallazgo inexistente')
        if not isinstance(body.get('result'), str) or body['result'] not in workflows.RESULTS: raise ValueError('Resultado de retest inválido')
        record = {k: body.get(k, '') for k in ('tested_on', 'assessor', 'notes_md', 'result')}
        record.update(uid=workflows.new_uid(), created=history.now(), evidence_uids=body.get('evidence_uids', []))
        if not record['tested_on'] or not record['assessor'] or not record['notes_md']: raise ValueError('Completa fecha, evaluador y resultado observado')
        pool = {e['uid'] for e in data.get('evidence', [])}
        if not isinstance(record['evidence_uids'], list) or any(not isinstance(x, str) or x not in pool for x in record['evidence_uids']): raise ValueError('Evidencia de retest inexistente')
        finding.setdefault('retests', []).append(record)
        finding['status'] = {'fixed': 'verified_fixed', 'open': 'open', 'partial': 'in_progress', 'not_verified': 'not_verified'}.get(record['result'], 'open')
        return saved(d, data)

    def library_path(): return Path(app.config['LIBRARY_PATH'])
    def lib_tag():
        path = library_path()
        return revision(path) if path.exists() else 'empty'
    def library_revision():
        tag = request.headers.get('If-Match', '').strip('"')
        if not tag: abort(428, 'Falta la revisión de la biblioteca')
        if tag != lib_tag(): abort(409, 'La biblioteca cambió. Vuelve a abrirla antes de guardar')
    def library_response(value):
        response = jsonify(value); response.set_etag(lib_tag()); return response

    @app.get('/api/library')
    @api.project_lock
    @errors
    def get_library(): return library_response(lib.load(library_path()))

    @app.post('/api/library')
    @api.project_lock
    @errors
    def create_template():
        library_revision(); entry = lib.put(library_path(), api._json_dict()); return library_response(entry)

    @app.put('/api/library/<uid>')
    @api.project_lock
    @errors
    def update_template(uid):
        library_revision(); entry = lib.put(library_path(), api._json_dict(), uid); return library_response(entry)

    @app.delete('/api/library/<uid>')
    @api.project_lock
    @errors
    def delete_template(uid):
        library_revision(); data = lib.load(library_path())
        if not any(e['uid'] == uid for e in data['templates']): abort(404)
        data['templates'] = [e for e in data['templates'] if e['uid'] != uid]
        atomic_write(library_path(), history.dumps(data), backup=True)
        return library_response({'ok': True})

    @app.post('/api/library/sanitize')
    @errors
    def sanitize_template():
        body = api._json_dict()
        if not isinstance(body.get('finding'), dict) or not isinstance(body.get('context', {}), dict): raise ValueError('Plantilla inválida')
        if any(not isinstance(v, str) for v in body.get('context', {}).values()): raise ValueError('Variables inválidas')
        return jsonify({'content': lib.sanitize(body['finding'], body.get('context'))})

    @app.post('/api/library/<uid>/instantiate')
    @api.project_lock
    @errors
    def instantiate(uid):
        row = next((e for e in lib.load(library_path())['templates'] if e['uid'] == uid), None)
        if not row: abort(404)
        return jsonify(lib.instantiate(row, api._json_dict().get('values', {})))

    @app.post('/api/library/import')
    @api.project_lock
    @errors
    def import_library():
        library_revision(); body = api._json_dict()
        if body.get('format') != 'report-gen-library' or body.get('version') != 1 or not isinstance(body.get('templates'), list): raise ValueError('Formato de biblioteca inválido')
        # Validate all versions before any write; import into an isolated temporary file.
        import tempfile
        target = library_path(); target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=target.parent) as tmp:
            staging = Path(tmp) / 'library.json'; atomic_write(staging, history.dumps(lib.load(target)))
            if len(body['templates']) > 500: raise ValueError('Demasiadas plantillas')
            for row in body['templates']:
                if not isinstance(row, dict): raise ValueError('Plantilla inválida')
                versions = row.get('versions') or [row]
                if not isinstance(versions, list) or len(versions) > 200: raise ValueError('Historial de plantilla inválido')
                uid = None
                for entry in versions: uid = lib.put(staging, entry, uid)['uid']
            atomic_write(target, staging.read_bytes(), backup=True)
        return library_response({'ok': True})
