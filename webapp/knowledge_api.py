"""Read-only knowledge and explicit, optimistic-concurrency guarded copies."""
from pathlib import Path

from flask import abort, jsonify, request

import engine
import finding_library
from knowledge import catalog
from languages import language_tag
import project_history
from storage import revision
import workflows


def register(api):
    app = api.app

    def localized(value, lang):
        response = jsonify(value)
        response.headers['Content-Language'] = language_tag(lang)
        return response

    def body(allowed):
        value = api._json_dict()
        if set(value) - allowed:
            abort(422, catalog.tr('Opciones del catálogo inválidas', 'Invalid catalog options', 'Opções do catálogo inválidas'))
        return value

    def known(identity, lang):
        try:
            return catalog.entry(identity, lang)
        except KeyError:
            abort(404, catalog.tr('Ficha del catálogo inexistente', 'Catalog entry not found', 'Ficha do catálogo inexistente'))

    @app.get('/api/knowledge')
    def knowledge_index():
        try:
            offset = int(request.args.get('offset', '0'))
            limit = int(request.args.get('limit', '24'))
        except ValueError:
            abort(422, catalog.tr('Paginación inválida', 'Invalid pagination', 'Paginação inválida'))
        lang = catalog.language(request.args.get('lang', 'es'))
        return localized(catalog.search(lang=lang, q=request.args.get('q', ''),
                                        category=request.args.get('category', ''), tag=request.args.get('tag', ''),
                                        offset=offset, limit=limit), lang)

    @app.get('/api/knowledge/<identity>')
    def knowledge_entry(identity):
        lang = catalog.language(request.args.get('lang', 'es'))
        return localized(known(identity, lang), lang)

    @app.post('/api/knowledge/<identity>/copy')
    @api.project_lock
    def knowledge_copy(identity):
        value = body({'lang'})
        lang = catalog.language(value.get('lang', 'es'))
        known(identity, lang)
        path = Path(app.config['LIBRARY_PATH'])
        tag = request.headers.get('If-Match', '').strip('"')
        if not tag:
            abort(428, catalog.tr('Falta la revisión de la biblioteca', 'Library revision is required', 'Falta a revisão da biblioteca'))
        if tag != (revision(path) if path.exists() else 'empty'):
            abort(409, catalog.tr('La biblioteca cambió. Vuelve a abrirla antes de guardar',
                                  'The library changed. Reopen it before saving',
                                  'A biblioteca mudou. Abra-a novamente antes de salvar'))
        row = finding_library.put(path, catalog.template(identity, lang))
        response = localized(row, lang)
        response.set_etag(revision(path))
        return response

    @app.post('/api/projects/<slug>/knowledge/<identity>')
    @api.project_lock
    def knowledge_insert(slug, identity):
        directory = api.proj_dir(slug)
        api.require_revision(directory / 'engagement.yaml')
        data = engine.load_engagement(directory / 'engagement.yaml')
        value = body({'lang', 'values'})
        lang = catalog.language(value.get('lang', engine.report_language(data)))
        known(identity, lang)
        finding = catalog.instantiate(identity, value.get('values', {}), lang)
        finding['id'] = workflows.allocate_finding_id(data)
        data.setdefault('findings', []).append(finding)
        project_history.save(directory, api.checked_data(data))
        response = localized({'data': data, 'uid': finding['uid'], 'catalog_id': identity, 'lang': lang}, lang)
        response.set_etag(revision(directory / 'engagement.yaml'))
        return response
