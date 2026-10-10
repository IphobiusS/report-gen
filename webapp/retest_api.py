"""Read-only, revision-bound retest views using existing private project guards."""
from error_messages import message as backend_message
from flask import abort, jsonify, request, Response
import engine
import project_history as history
import report_compare
import retest_compare
from input_guard import load_yaml
from storage import revision


def register(api):
    def project(slug, required=False):
        directory = api.proj_dir(slug)
        current = revision(directory / 'engagement.yaml')
        wanted = request.args.get('revision')
        if required and not wanted:
            abort(428, backend_message('Falta la revisión guardada / Saved revision is required'))
        if wanted is not None and wanted != current:
            abort(409, backend_message('El proyecto cambió; vuelve a comparar / Project changed; compare again'))
        return directory, current

    def options(allowed):
        if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
            abort(422, backend_message('Opciones de comparación inválidas / Invalid comparison options'))
        lang = request.args.get('lang', 'es')
        if lang not in ('es', 'en'):
            abort(422, backend_message('Idioma inválido / Invalid language'))
        return lang

    @api.app.get('/api/projects/<slug>/retest-diff')
    @api.project_lock
    def retest_diff(slug):
        options({'revision', 'baseline', 'lang'})
        directory, current = project(slug)
        result = retest_compare.read(directory, engine.load_engagement(directory / 'engagement.yaml'),
                                    request.args.get('baseline'))
        result['project_slug'] = directory.name
        response = jsonify(result)
        response.set_etag(current)
        return response

    @api.app.get('/api/projects/<slug>/retest-diff/visual')
    @api.project_lock
    def retest_diff_visual(slug):
        lang = options({'revision', 'baseline', 'baseline_sha256', 'lang', 'privacy', 'ack_private', 'download'})
        directory, current = project(slug, required=True)
        baseline = request.args.get('baseline')
        wanted = request.args.get('baseline_sha256')
        if not baseline or not wanted:
            abort(428, backend_message('Elige y confirma la versión base / Choose and confirm a baseline'))
        chosen, _, _ = retest_compare.select_baseline(retest_compare.candidates(directory), baseline)
        if wanted != chosen['snapshot_sha256']:
            abort(409, backend_message('La versión base cambió; vuelve a comparar / Baseline changed; compare again'))
        privacy = request.args.get('privacy', 'shareable')
        if privacy not in ('shareable', 'private'):
            abort(422, backend_message('Visibilidad inválida / Invalid visibility'))
        internal = privacy == 'private'
        if request.args.get('download', '0') not in ('0', '1') or request.args.get('ack_private', '0') not in ('0', '1'):
            abort(422, backend_message('Confirmación inválida / Invalid acknowledgement'))
        if internal and request.args.get('ack_private') != '1':
            abort(422, backend_message('Confirma el acceso a datos privados / Acknowledge access to private data'))
        old = dict(history.snapshot_blobs(directory, history.get_snapshot(directory, baseline)))
        new = dict(history.project_files(directory))
        before, after = load_yaml(old['engagement.yaml']), load_yaml(new['engagement.yaml'])
        # Validate identities and the project shape without assigning any new UID.
        retest_compare.comparison(before, after)
        for name, blob in new.items():
            if name.startswith('attachments/'):
                __import__('attachments').validate_blob(name, blob)
            elif name != 'engagement.yaml':
                history.validate_image_blob(name, blob)
        # Snapshot labels can contain internal client data. Shareable captions use
        # documentary identifiers and dates, never an unprojected private label.
        label = ('Versión / Version ' + baseline + ' / ' + chosen['created'])
        markup = report_compare.render(before, after, old, new, label,
                                       'Actual / Current / ' + current[:12], lang, internal=internal)
        response = Response(markup, mimetype='text/html')
        response.set_etag(current)
        response.headers['X-Report-Gen-Baseline'] = chosen['snapshot_sha256']
        if request.args.get('download') == '1':
            response.headers['Content-Disposition'] = ('attachment; filename="retest-comparison-private.html"'
                if internal else 'attachment; filename="retest-comparison-shareable.html"')
        return response

    @api.app.get('/api/projects/<slug>/retest-matrix')
    @api.project_lock
    def retest_matrix(slug):
        lang = options({'revision', 'lang'})
        directory, current = project(slug)
        from retest_summary import summarize
        result = dict(project_slug=directory.name, revision=current,
                      matrix=summarize(engine.load_engagement(directory / 'engagement.yaml'), lang=lang))
        response = jsonify(result)
        response.set_etag(current)
        return response
