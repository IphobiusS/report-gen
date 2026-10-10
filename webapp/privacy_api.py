"""Retention inventory for the active project; same origin, session and revision guards."""
from error_messages import message as backend_message
from flask import jsonify,abort
import private_data
import privacy_ocr
import engine
import publication
from storage import revision


def register(api):
    @api.app.post('/api/projects/<slug>/privacy/ocr')
    @api.project_lock
    def privacy_ocr_image(slug):
        directory = api.proj_dir(slug)
        api.require_revision(directory/'engagement.yaml')
        body = api._json_dict()
        if set(body) != {'name'} or not isinstance(body['name'], str):
            abort(422, backend_message('Selecciona una imagen publicada. / Select a published image.'))
        data = engine.load_engagement(directory/'engagement.yaml')
        images = publication.images(publication.render(data, directory), directory)
        if body['name'] not in images:
            abort(404)
        image = images[body['name']]
        if image.stat().st_size > privacy_ocr.MAX_IMAGE_BYTES:
            abort(413, backend_message('OCR: imagen mayor que 12 MiB. / OCR: image exceeds 12 MiB.'))
        result = privacy_ocr.inspect_publication_image(image.read_bytes())
        result.update(name=body['name'], revision=revision(directory/'engagement.yaml'), language='eng')
        response = jsonify(result)
        response.set_etag(result['revision'])
        return response

    @api.app.get('/api/projects/<slug>/privacy')
    @api.project_lock
    def privacy_inventory(slug):
        directory=api.proj_dir(slug)
        response=jsonify(private_data.public_inventory(directory))
        response.set_etag(revision(directory/'engagement.yaml'))
        return response

    @api.app.post('/api/projects/<slug>/privacy/prune')
    @api.project_lock
    def privacy_prune(slug):
        directory=api.proj_dir(slug);api.require_revision(directory/'engagement.yaml')
        body=api._json_dict()
        if set(body)!={'categories','inventory_revision','confirm_project'} or body['confirm_project']!=directory.name:
            abort(422,backend_message('Escribe el identificador del proyecto para confirmar / Type project ID to confirm'))
        response=jsonify(private_data.prune(directory,body['categories'],body['inventory_revision']))
        response.set_etag(revision(directory/'engagement.yaml'))
        return response
