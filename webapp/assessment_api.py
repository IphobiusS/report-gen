"""Revision-guarded assessment plans and explicitly authored causal routes."""
from functools import wraps
from flask import abort, jsonify, request, Response
import engine
import project_history as history
import test_plans
import attack_paths
from storage import revision


def register(api):
    app = api.app

    def errors(fn):
        @wraps(fn)
        def call(*args, **kwargs):
            try: return fn(*args, **kwargs)
            except ValueError as exc: abort(422, str(exc))
        return call

    def project(slug, mutate=False):
        directory = api.proj_dir(slug)
        if mutate: api.require_revision(directory / 'engagement.yaml')
        return directory, engine.load_engagement(directory / 'engagement.yaml')

    def checked(data):
        occupied = set()
        for group in ('findings', 'assets', 'evidence', 'coverage', 'root_cause_groups', 'http_evidence'):
            for row in data.get(group, []):
                if isinstance(row, dict) and isinstance(row.get('uid'), str): occupied.add(row['uid'])
        issues = test_plans.structure_errors(data, occupied) + attack_paths.structure_errors(data, occupied)
        if issues: raise ValueError('; '.join(message for _, message in issues))
        return api.checked_data(data)

    def saved(directory, data, **extra):
        history.save(directory, checked(data))
        result = jsonify({'data': data, **extra}); result.set_etag(revision(directory / 'engagement.yaml'))
        return result

    def index(rows, uid):
        result = next((i for i, row in enumerate(rows) if row.get('uid') == uid), None)
        if result is None: abort(404, test_plans.tr('Registro inexistente', 'Record not found', 'Registro inexistente'))
        return result

    @app.get('/api/projects/<slug>/assessment/catalog')
    @api.project_lock
    @errors
    def assessment_catalog(slug):
        directory, _ = project(slug)
        result = jsonify(test_plans.catalog(request.args.get('lang', 'es')))
        result.set_etag(revision(directory / 'engagement.yaml')); return result

    @app.post('/api/projects/<slug>/assessment/test-cases')
    @api.project_lock
    @errors
    def assessment_case_create(slug):
        directory, data = project(slug, True)
        row = test_plans.create(api._json_dict())
        data.setdefault('test_cases', []).append(row)
        return saved(directory, data, uid=row['uid'])

    @app.post('/api/projects/<slug>/assessment/test-cases/batch')
    @api.project_lock
    @errors
    def assessment_case_batch(slug):
        directory, data = project(slug, True); body = api._json_dict()
        if set(body) != {'cases'} or not isinstance(body['cases'], list) or not 1 <= len(body['cases']) <= 100:
            raise ValueError(test_plans.tr('Selecciona entre 1 y 100 casos iniciales', 'Select 1 to 100 starter cases', 'Selecione de 1 a 100 casos iniciais'))
        rows = [test_plans.create(row) for row in body['cases']]
        data.setdefault('test_cases', []).extend(rows)
        return saved(directory, data, added=len(rows))

    @app.route('/api/projects/<slug>/assessment/test-cases/<uid>', methods=['PUT', 'DELETE'])
    @api.project_lock
    @errors
    def assessment_case_edit(slug, uid):
        directory, data = project(slug, True); rows = data.setdefault('test_cases', [])
        i = index(rows, uid)
        if request.method == 'DELETE': rows.pop(i)
        else: rows[i] = test_plans.create(api._json_dict(), uid)
        return saved(directory, data)

    @app.post('/api/projects/<slug>/assessment/matrix')
    @api.project_lock
    @errors
    def assessment_matrix(slug):
        directory, data = project(slug, True); body = api._json_dict()
        preview = body.pop('preview', False)
        if type(preview) is not bool: raise ValueError(test_plans.tr('Vista previa inválida', 'Invalid preview flag', 'Opção de prévia inválida'))
        rows = test_plans.matrix(body)
        data.setdefault('test_cases', []).extend(rows)
        checked(data)
        if preview:
            result = jsonify({'cases': rows, 'count': len(rows)}); result.set_etag(revision(directory / 'engagement.yaml')); return result
        return saved(directory, data, added=len(rows))

    @app.post('/api/projects/<slug>/assessment/attack-paths')
    @api.project_lock
    @errors
    def assessment_path_create(slug):
        directory, data = project(slug, True); row = attack_paths.create(api._json_dict())
        data.setdefault('attack_paths', []).append(row)
        return saved(directory, data, uid=row['uid'])

    @app.route('/api/projects/<slug>/assessment/attack-paths/<uid>', methods=['PUT', 'DELETE'])
    @api.project_lock
    @errors
    def assessment_path_edit(slug, uid):
        directory, data = project(slug, True); rows = data.setdefault('attack_paths', [])
        i = index(rows, uid)
        if request.method == 'DELETE': rows.pop(i)
        else: rows[i] = attack_paths.create(api._json_dict(), uid)
        return saved(directory, data)

    @app.get('/api/projects/<slug>/assessment/attack-paths/<uid>/graph.svg')
    @api.project_lock
    @errors
    def assessment_path_graph(slug, uid):
        directory, data = project(slug); rows = data.get('attack_paths', []); path = rows[index(rows, uid)]
        checked(data)
        result = Response(attack_paths.graph_svg(path, request.args.get('lang', 'es')), mimetype='image/svg+xml')
        result.headers['Content-Security-Policy'] = "default-src 'none'; style-src 'none'; sandbox"
        result.headers['Cache-Control'] = 'no-store'; result.set_etag(revision(directory / 'engagement.yaml'))
        return result
