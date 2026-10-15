"""Read-only, CSRF-protected upload of two PDFs for an isolated comparison."""
from flask import abort, jsonify, request, Response

from error_messages import current_language
from input_guard import ensure_data_tree
from languages import normalize_language
import pdf_compare


def register(api):
    app = api.app

    @app.get('/api/pdf-compare/capabilities')
    def pdf_comparison_capabilities():
        return jsonify(pdf_compare.capabilities())

    @app.post('/api/pdf-compare')
    def pdf_comparison():
        if (request.mimetype != 'multipart/form-data'
                or set(request.files) != {'before', 'after'}
                or any(len(request.files.getlist(key)) != 1 for key in request.files)
                or set(request.form) - {'language'}
                or len(request.form.getlist('language')) > 1):
            abort(415, pdf_compare.error('request'))
        language = normalize_language(request.form.get('language', current_language()), None)
        if language is None:
            raise ValueError(pdf_compare.error('language'))
        ensure_data_tree({'language': language})
        before = request.files['before'].stream.read(pdf_compare.MAX_PDF + 1)
        after = request.files['after'].stream.read(pdf_compare.MAX_PDF + 1)
        content = pdf_compare.compare(before, after, language)
        response = Response(content, mimetype='text/html')
        response.headers['Content-Disposition'] = 'attachment; filename="report-gen-pdf-comparison.html"'
        response.headers['Content-Security-Policy'] = pdf_compare.CSP + "; frame-ancestors 'self'"
        response.headers['Content-Language'] = {'es': 'es', 'en': 'en', 'pt': 'pt-BR'}[language]
        response.headers['Cache-Control'] = 'no-store'
        return response
