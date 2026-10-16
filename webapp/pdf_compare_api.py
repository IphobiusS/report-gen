"""Read-only, CSRF-protected upload of two PDFs for an isolated comparison."""
from hashlib import sha256
import re

from flask import abort, jsonify, request, Response, session

from error_messages import current_language
from input_guard import ensure_data_tree, load_json
from languages import normalize_language
import pdf_compare


def register(api):
    app = api.app

    @app.get('/api/pdf-compare/capabilities')
    def pdf_comparison_capabilities():
        return jsonify(pdf_compare.capabilities())

    def inputs(inspect=False):
        allowed = {'language'} if inspect else {'language', 'page_pairs', 'expected_before_sha256', 'expected_after_sha256'}
        if (request.mimetype != 'multipart/form-data'
                or set(request.files) != {'before', 'after'}
                or any(len(request.files.getlist(key)) != 1 for key in request.files)
                or set(request.form) - allowed
                or any(len(request.form.getlist(key)) != 1 for key in request.form)):
            abort(415, pdf_compare.error('request'))
        language = normalize_language(request.form.get('language', current_language()), None)
        if language is None:
            raise ValueError(pdf_compare.error('language'))
        ensure_data_tree({'language': language})
        pairs = None
        if 'page_pairs' in request.form:
            raw = request.form['page_pairs'].encode('utf-8')
            if len(raw) > pdf_compare.MAX_PAIR_JSON:
                raise ValueError(pdf_compare.error('pairing_json', language))
            pairs = load_json(raw)
            pdf_compare.validate_page_pairs(pairs, language=language)
        hashes = [request.form.get('expected_' + side + '_sha256') for side in ('before', 'after')]
        if any(value is not None for value in hashes):
            if pairs is None or any(value is None or re.fullmatch('[0-9a-f]{64}', value) is None for value in hashes):
                abort(415, pdf_compare.error('request', language))
        before = request.files['before'].stream.read(pdf_compare.MAX_PDF + 1)
        after = request.files['after'].stream.read(pdf_compare.MAX_PDF + 1)
        if hashes[0] is not None and hashes != [sha256(before).hexdigest(), sha256(after).hexdigest()]:
            raise ValueError(pdf_compare.error('source_changed', language))
        return before, after, language, pairs

    @app.post('/api/pdf-compare/metadata')
    def pdf_comparison_metadata():
        before, after, language, _ = inputs(inspect=True)
        return jsonify(pdf_compare.metadata(before, after, language))

    @app.post('/api/pdf-compare')
    def pdf_comparison():
        before, after, language, pairs = inputs()
        content = pdf_compare.compare(before, after, language, page_pairs=pairs)
        response = Response(content, mimetype='text/html')
        response.headers['Content-Disposition'] = 'attachment; filename="report-gen-pdf-comparison.html"'
        response.headers['Content-Security-Policy'] = pdf_compare.CSP + "; frame-ancestors 'self'"
        response.headers['Content-Language'] = {'es': 'es', 'en': 'en', 'pt': 'pt-BR'}[language]
        response.headers['Cache-Control'] = 'no-store'
        store = app.extensions.get('pdf_comparison_receipts')
        if store is not None:
            from pdf_comparison_reviews import ReceiptLimitError
            try:
                key = store.add(session['csrf'], content)
            except ReceiptLimitError:
                pass  # Comparison download remains useful when receipt storage is full.
            else:
                response.headers['X-Report-Gen-Comparison-Id'] = key
        return response
