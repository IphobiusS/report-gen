"""Bounded local diagnostics. Invoked in a disposable subprocess by the editor."""
import json
from pathlib import Path
import tempfile


def run(lang="es"):
    w=lambda es,en:en if lang=="en" else es
    results = []
    with tempfile.TemporaryDirectory(prefix='report-gen-doctor-') as directory:
        root = Path(directory)
        for name, label, action in [
            ('weasyprint', 'PDF / WeasyPrint', lambda: weasy(root)),
            ('chromium', w('PDF / Chromium (alternativa)','PDF / Chromium (alternative)'), lambda: chromium(root)),
            ('docx', w('Word editable','Editable Word'), lambda: word(root)),
        ]:
            try:
                action()
                results.append({'id': name, 'label': label, 'ready': True, 'detail': w('Prueba de exportación correcta','Export test passed')})
            except Exception as exc:
                instructions = {'weasyprint': w('Revisa las bibliotecas de WeasyPrint indicadas en README.md.','Check the WeasyPrint libraries listed in README.en.md.'),
                                'chromium': w('Instala playwright y ejecuta: python -m playwright install chromium','Install playwright and run: python -m playwright install chromium'),
                                'docx': w('Reinstala las dependencias del proyecto con pip install -e .','Reinstall project dependencies with pip install -e .')}
                results.append({'id': name, 'label': label, 'ready': False,
                                'detail': type(exc).__name__+'. '+instructions[name]})
    return {'checks': results, 'pdf_ready': any(r['ready'] for r in results[:2]),
            'note': w('Se prueban los motores instalados. Las fuentes de Word dependen del equipo que abra el DOCX.','Tests cover installed engines. Word fonts depend on the computer opening the DOCX.')}


def weasy(root):
    from weasyprint import HTML
    from pypdf import PdfReader
    path = root/'test.pdf'
    HTML(string='<p>report-gen: ÁÉÍÓÚ ñ 0123456789</p>').write_pdf(path)
    assert 'report-gen' in PdfReader(path).pages[0].extract_text()


def chromium(root):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(timeout=8000)
        try:
            page = browser.new_page()
            page.set_content('<p>report-gen</p>')
            assert page.pdf(path=str(root/'chromium.pdf')).startswith(b'%PDF-')
        finally:
            browser.close()


def word(root):
    from docx import Document
    path = root/'test.docx'
    doc = Document(); doc.add_paragraph('report-gen'); doc.save(path)
    assert Document(path).paragraphs[0].text == 'report-gen'


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--lang',choices=['es','en'],default='es')
    print(json.dumps(run(parser.parse_args().lang), ensure_ascii=False))
