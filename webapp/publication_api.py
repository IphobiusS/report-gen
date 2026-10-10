"""Read-only, revision-bound inspection of the exact publication content."""
from error_messages import message as backend_message
from flask import jsonify, request, send_file, abort
from io import BytesIO
import engine
import publication
from storage import revision

def register(api):
    @api.app.get('/api/projects/<slug>/publication')
    @api.project_lock
    def publication_inspector(slug):
        directory=api.proj_dir(slug)
        data=engine.load_engagement(directory/'engagement.yaml')
        result=publication.inspect(data,directory)
        result['revision']=revision(directory/'engagement.yaml')
        response=jsonify(result);response.set_etag(result['revision']);return response

    @api.app.get('/api/projects/<slug>/publication/image')
    @api.project_lock
    def publication_image(slug):
        directory=api.proj_dir(slug)
        data=engine.load_engagement(directory/'engagement.yaml')
        allowed=publication.images(publication.render(data,directory),directory)
        if request.args.get('revision') and request.args['revision']!=revision(directory/'engagement.yaml'): abort(409,backend_message('La revisión cambió / Revision changed'))
        name=request.args.get('name','')
        if name not in allowed: abort(404)
        return send_file(BytesIO(publication.clean_image(allowed[name].read_bytes())),mimetype=__import__('mimetypes').guess_type(name)[0],max_age=0)
