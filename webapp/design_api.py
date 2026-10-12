"""Report design routes, with revision checks and portable appearance snapshots."""
from error_messages import message as backend_message
from pathlib import Path
from flask import abort, jsonify, request
import engine
import design_library as lib
import project_history as history
from storage import atomic_write, revision
import json


def register(api):
    app=api.app
    app.config.setdefault('DESIGN_LIBRARY_PATH',str(api.HERE/'library'/'designs.json'))
    def path(): return Path(app.config['DESIGN_LIBRARY_PATH'])
    def personal(): return lib.load_personal(path())
    def get_profile(ident): return lib.profile(ident,personal())
    def json_etag(data):
        response=jsonify(data)
        response.set_etag(revision(path()) if path().exists() else 'empty')
        return response
    def library_revision():
        expected=revision(path()) if path().exists() else 'empty'
        if not request.headers.get('If-Match'): abort(428,backend_message('Recarga la biblioteca antes de modificarla'))
        if not request.if_match.contains(expected): abort(412,backend_message('La biblioteca cambió. Recárgala; tus cambios no se guardaron'))
    def body_profile(body):
        p = get_profile(body.get('id'))
        return p, body.get('variant', p.get('design', {}).get('variant', 'brand'))

    @app.get('/api/design-library')
    @api.project_lock
    def library():
        result=lib.catalog()
        for p in result['profiles']: p['design']=lib.appearance(p)
        result['personal']=personal()['templates']
        result['layouts']=list(lib.LAYOUTS);result['variants']=list(lib.VARIANTS)
        from report_designs import THEMES
        result['general']=sorted(THEMES)
        return json_etag(result)

    @app.post('/api/design-library/personal')
    @api.project_lock
    def save_personal():
        library_revision()
        return json_etag(lib.put_personal(path(),api._json_dict()))

    @app.put('/api/design-library/personal/<ident>')
    @api.project_lock
    def update_personal(ident):
        library_revision()
        return json_etag(lib.put_personal(path(),api._json_dict(),ident))

    @app.delete('/api/design-library/personal/<ident>')
    @api.project_lock
    def delete_personal(ident):
        library_revision(); data=personal()
        if not any(p['id']==ident for p in data['templates']): abort(404,backend_message('Plantilla inexistente'))
        data['templates']=[p for p in data['templates'] if p['id']!=ident]
        atomic_write(path(),(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode(),backup=True)
        return json_etag({'ok':True})

    @app.post('/api/design-library/projects')
    @api.project_lock
    def create():
        body=api._json_dict();slug,d=api.new_project_destination(body)
        p,variant=body_profile(body)
        title=lib.text(body.get('title'),'Título',300)
        data=lib.new_report(p,title,body.get('lang','es'),variant)
        data['meta']['client']=body.get('client') or ''
        data=api.checked_data(data)
        with history.transaction(d) as staged:
            (staged/'img').mkdir(exist_ok=True)
            history.save(staged,data)
        return jsonify({'slug':slug})

    @app.post('/api/projects/<slug>/design')
    @api.project_lock
    def apply(slug):
        d=api.proj_dir(slug);api.require_revision(d/'engagement.yaml')
        data=engine.load_engagement(d/'engagement.yaml');body=api._json_dict()
        if 'general' in body:
            from report_designs import THEMES
            if not isinstance(body['general'], str) or body['general'] not in THEMES:
                abort(422,backend_message('Diseño general desconocido'))
            data['meta']['theme']=body['general'];data['meta'].pop('design',None)
        else:
            p,variant=body_profile(body);data=lib.apply(data,p,variant)
        history.save(d,api.checked_data(data))
        response=jsonify({'data':data});response.set_etag(revision(d/'engagement.yaml'));return response

    @app.post('/api/design-library/preview')
    @api.project_lock
    def preview():
        body=api._json_dict()
        if 'design' in body:
            design=lib.validate_design(body['design']);p=lib.profile(design['guidance_id'])
        else:
            p,variant=body_profile(body);design=lib.appearance(p,variant)
        from design_samples import sample_data
        data=sample_data(p,design['variant'],body.get('lang','es'));data['meta']['design']=design
        return app.response_class(engine.render_html(engine.build_env(),data,api.REPORT_ROOT,{},False,engine.load_lang(data['meta']['lang']),theme_href='/theme/ejecutivo.css',img_base='/'),mimetype='text/html')
