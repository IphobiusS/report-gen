"""Independent draft creation; never mutate a selected customer project."""
import uuid

from flask import abort, jsonify, request

from knowledge import catalog, work_packages
from languages import language_tag
import project_history


def register(api):
    def response(value):
        result = jsonify(value)
        result.headers['Content-Language'] = language_tag(value['lang'])
        return result

    def known(identity, lang):
        try:
            return work_packages.package(identity, lang)
        except KeyError:
            abort(404, catalog.tr('Paquete de trabajo inexistente', 'Work package not found', 'Pacote de trabalho inexistente'))

    @api.app.get('/api/work-packages')
    def package_index():
        return response(work_packages.packages(request.args.get('lang', 'es')))

    @api.app.get('/api/work-packages/example')
    def annotated_example():
        return response(work_packages.example(request.args.get('lang', 'es')))

    @api.app.get('/api/work-packages/<identity>')
    def package_detail(identity):
        return response(known(identity, request.args.get('lang', 'es')))

    @api.app.post('/api/work-packages/<identity>/projects')
    @api.project_lock
    def package_create(identity):
        body = api._json_dict()
        if set(body) - {'lang', 'title', 'client', 'finding_ids'}:
            abort(422, catalog.tr('Opciones de paquete inválidas', 'Invalid package options', 'Opções de pacote inválidas'))
        lang = catalog.language(body.get('lang', 'es'))
        known(identity, lang)
        data = api.checked_data(work_packages.project(identity, **body))
        # UUID identity is allocated server-side and never supplied by a caller.
        slug, directory = api.new_project_destination({'slug': 'work-' + identity + '-' + uuid.uuid4().hex[:12]})
        with project_history.transaction(directory) as staged:
            (staged / 'img').mkdir(exist_ok=True)
            project_history.save(staged, data)
        return response(dict(slug=slug, lang=lang, package=identity, test_count=len(data['test_cases']),
                             finding_count=len(data['findings'])))
