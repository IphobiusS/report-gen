#!/usr/bin/env python3
"""Exercise the complete Nimbus project through the real report-gen editor.

The server, project directory and library are disposable. No user project changes.
Requires Playwright/Chromium and the same dependencies as report-gen.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import zipfile

import fitz
from playwright.sync_api import sync_playwright
import yaml

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--tool', type=Path, required=True)
parser.add_argument('--project', type=Path, required=True)
parser.add_argument('--bundle', type=Path, required=True)
parser.add_argument('--reference-outputs', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path[:0] = [str(args.tool.resolve()), str(args.tool.resolve() / 'webapp')]
import app as webapp  # noqa: E402
import project_history  # noqa: E402
import delivery  # noqa: E402
import export as report_export  # noqa: E402
from safe_markup import md  # noqa: E402
from lxml import html  # noqa: E402
from lxml import etree  # noqa: E402

output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
expected = yaml.safe_load((args.project / 'engagement.yaml').read_bytes())
checks = []; errors = []; outbound = []; dialogs = []; responses = []


def check(name, ok, detail=None):
    checks.append(dict(check=name, passed=bool(ok), detail=detail))
    if not ok:
        raise AssertionError(name + ': ' + str(detail))


def wait(page, expression, seconds=45):
    # Poll without Playwright's eval-based wait_for_function: keep the CSP active.
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if page.evaluate('() => (' + expression + ')'):
            return
        page.wait_for_timeout(70)
    raise AssertionError('Timed out: ' + expression)


def image_hashes(path):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (path / 'img').iterdir() if p.is_file()}


def read_data(path):
    return yaml.safe_load((path / 'engagement.yaml').read_bytes())


def word_parts(archive):
    parts = {n: archive.read(n) for n in archive.namelist() if n.startswith('word/')}
    doc = etree.fromstring(parts['word/document.xml'])
    # python-docx uses the chart's random temporary basename as image metadata.
    # It does not alter text, image content, placement, style or relationships.
    ns = {'pic': 'http://schemas.openxmlformats.org/drawingml/2006/picture'}
    for item in doc.findall('.//pic:cNvPr', ns):
        if (item.get('name') or '').startswith('tmp'):
            item.set('name', 'temporary-chart.png')
    parts['word/document.xml'] = etree.tostring(doc)
    return parts


with tempfile.TemporaryDirectory(prefix='nimbus-browser-') as temp:
    webapp.PROJECTS = Path(temp) / 'projects'; webapp.PROJECTS.mkdir()
    webapp.app.config['LIBRARY_PATH'] = str(Path(temp) / 'library.json')
    server = webapp.create_local_server(0)
    thread = threading.Thread(target=server.run, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.effective_port}'
    project = webapp.PROJECTS / 'nimbus-audit'
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            context = browser.new_context(viewport={'width': 1366, 'height': 1000},
                                          reduced_motion='reduce', accept_downloads=True)
            context.on('request', lambda req: outbound.append(req.url)
                       if not req.url.startswith((base + '/', 'blob:', 'data:', 'about:')) else None)
            def configure(page):
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.on('response', lambda r: responses.append((r.request.method, r.url, r.status)))
                def dialog(d):
                    dialogs.append((d.type, d.message))
                    d.accept('nimbus-audit') if d.type == 'prompt' else d.dismiss()
                page.on('dialog', dialog)
            page = context.new_page(); configure(page)
            response = page.goto(base)
            check('Editor delivered with a CSP', bool(response.headers.get('content-security-policy')))
            page.locator('#splash').wait_for(state='hidden')
            with page.expect_file_chooser() as chooser:
                page.locator('#importProjectBtn').click()
            chooser.value.set_files(args.bundle.resolve())
            wait(page, "typeof S !== 'undefined' && S.slug === 'nimbus-audit' && !projectStore.loading")
            check('Native backup imported through the editor', project.exists())
            check('Import preserves the complete project data', read_data(project) == expected)
            check('Import preserves all 19 image files', image_hashes(project) == image_hashes(args.project))
            check('Editor exposes all 12 findings', page.locator('#findingList > li').count() == 12)
            frame = page.frame_locator('#pdfPreview')
            frame.locator('.cv-wordmark').wait_for(state='visible')
            wait(page, "document.querySelector('#pdfPreview').contentDocument?.images.length === 19 && "
                 "[...document.querySelector('#pdfPreview').contentDocument.images].every(i => i.complete && i.naturalWidth > 0)")
            check('Live preview renders all 19 images', frame.locator('img').count() == 19)
            check('Preview retains its script restriction', page.locator('#pdfPreview').get_attribute('sandbox') == 'allow-same-origin')
            check('Preview has all finding IDs', all(frame.locator('#' + f['id']).count() == 1 for f in expected['findings']))

            # Real two-tab optimistic concurrency: retain the rejected buffer.
            second = context.new_page(); configure(second); second.goto(base)
            wait(second, "typeof S !== 'undefined' && S.slug === 'nimbus-audit' && !projectStore.loading")
            second.locator('#splash').wait_for(state='hidden')
            title = expected['meta']['report_title']
            page.locator('[data-field="report_title"]').fill(title + ' QA')
            wait(page, '!projectStore.dirty')
            check('Autosave commits the edited report', read_data(project)['meta']['report_title'] == title + ' QA')
            second.locator('[data-field="report_title"]').fill('Borrador de la segunda pestaña')
            wait(second, "document.querySelector('#saveState').textContent.toLowerCase().includes('error')")
            check('Stale tab receives HTTP 409', any(method == 'PUT' and status == 409 for method, url, status in responses))
            check('Conflict retains unsaved text in the stale tab', second.evaluate("() => projectStore.dirty && S.data.meta.report_title === 'Borrador de la segunda pestaña'"))
            check('Conflict preserves the saved project', read_data(project)['meta']['report_title'] == title + ' QA')
            second.close()
            page.locator('[data-field="report_title"]').fill(title)
            wait(page, '!projectStore.dirty')
            check('Restoring the edited field returns identical project data', read_data(project) == expected)

            for kind in ['assets', 'coverage', 'retest', 'history', 'evidence', 'review']:
                page.locator(f'[data-workflow="{kind}"]').click()
                view = page.locator(f'[data-workflow-view="{kind}"]')
                view.wait_for(state='visible')
                wait(page, f"document.querySelector('[data-workflow-view=\"{kind}\"]').childNodes.length > 0")
                check('Complete-project view ' + kind, view.is_visible())
            page.locator('#navReport').click()
            for theme in ['dark', 'light']:
                if page.locator('html').get_attribute('data-theme') != theme:
                    page.locator('#themeToggle').click()
                check('Editor theme ' + theme, page.locator('html').get_attribute('data-theme') == theme)
                for width in [1366, 390]:
                    page.set_viewport_size({'width': width, 'height': 1000})
                    measure = page.evaluate('''() => {
                        const b=document.querySelector('.brand-name');
                        const first=document.createRange(); first.selectNodeContents(b.firstChild);
                        return {scroll:document.documentElement.scrollWidth, viewport:innerWidth,
                            first:first.getBoundingClientRect().top,
                            suffix:b.querySelector('span').getBoundingClientRect().top};
                    }''')
                    check(f'No document overflow {theme} {width}', measure['scroll'] <= width + 1, measure)
                    check(f'Logo remains on one line {theme} {width}', abs(measure['first'] - measure['suffix']) < 2, measure)
                    page.locator('#validateBtn').focus()
                    page.keyboard.press('Tab'); page.keyboard.press('Shift+Tab')
                    focus = page.locator('#validateBtn').evaluate('(e)=>({width:getComputedStyle(e).outlineWidth,style:getComputedStyle(e).outlineStyle})')
                    check(f'Keyboard focus visible {theme} {width}', focus['width'] == '3px' and focus['style'] == 'solid', focus)
                    page.screenshot(path=str(output / f'nimbus-editor-{theme}-{width}.png'), full_page=True)
            page.set_viewport_size({'width': 1366, 'height': 1000})
            snapshot = Path(temp) / 'export-capture'
            captured = delivery.capture(project, snapshot)
            for fmt in ['md', 'docx', 'pdf']:
                page.locator('#exportFormat').select_option(fmt)
                with page.expect_download(timeout=150000) as promise:
                    page.locator('#downloadBtn').click()
                download = promise.value
                check('Native editor download ' + fmt, download.failure() is None)
                target = output / ('nimbus-ui.' + ('zip' if fmt == 'md' else fmt))
                download.save_as(target)
                if fmt == 'pdf':
                    # Bind the expected pagination to this source and engine,
                    # rather than the page count of a historical Nimbus build.
                    reference_pdf = output / 'nimbus-cli-reference.pdf'
                    report_export.export(snapshot / 'engagement.yaml', 'pdf', reference_pdf)
                    check('Equivalent CLI PDF exists', reference_pdf.is_file())
                    reference_checks = delivery.inspect_export(reference_pdf, 'pdf', captured)
                    with fitz.open(target) as doc, fitz.open(reference_pdf) as reference:
                        text = ''.join(p.get_text() for p in doc)
                        check('Editor PDF matches the verified CLI page count and retains every finding',
                              len(reference) > 0 and len(doc) == len(reference)
                              and all(f['title'] in ' '.join(text.split()) for f in expected['findings']),
                              {'editor_pages': len(doc), 'cli_pages': len(reference), 'cli_checks': reference_checks})
                else:
                    with zipfile.ZipFile(target) as z:
                        check('Editor archive integrity ' + fmt, z.testzip() is None)
                        if fmt == 'md':
                            rendered = html.fragment_fromstring(str(md(z.read('report.md').decode())), create_parent='div')
                            check('Editor Markdown includes assessor role', expected['meta']['assessor_title'] in rendered.text_content())
                            inspection = delivery.inspect_export(target, 'md', captured)
                            check('Editor Markdown preserves all 19 authored images and its source-bound summary chart',
                                  inspection['images_verified'] == 19 and inspection.get('generated_charts_verified') == 1,
                                  inspection)
                            with zipfile.ZipFile(args.reference_outputs / 'nimbus-markdown.zip') as reference:
                                check('Editor and CLI Markdown contain identical files',
                                      {n: z.read(n) for n in z.namelist()} == {n: reference.read(n) for n in reference.namelist()})
                        else:
                            with zipfile.ZipFile(args.reference_outputs / 'nimbus.docx') as reference:
                                check('Editor and CLI Word contain identical body, styles and media',
                                      word_parts(z) == word_parts(reference))
            page.locator('[data-workflow="backup"]').click()
            with page.expect_download() as promise:
                page.get_by_role('button', name='Descargar respaldo ZIP', exact=True).click()
            target = output / 'nimbus-ui-project.zip'; promise.value.save_as(target)
            restored = webapp.PROJECTS / 'restored'
            project_history.import_bundle(target.read_bytes(), restored)
            check('Downloaded backup reimports identical data', read_data(restored) == expected)
            check('Downloaded backup reimports identical images', image_hashes(restored) == image_hashes(args.project))
            check('No external resource requests', not outbound, outbound)
            check('No browser JavaScript errors', not errors, errors)
            result = dict(browser=browser.version, checks=checks, passed=True)
            context.close(); browser.close()
    finally:
        server.close(); thread.join(timeout=3)
        result = locals().get('result', dict(checks=checks, errors=errors, passed=False))
        (output / 'browser-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'checks': len(checks), 'passed': True}))
