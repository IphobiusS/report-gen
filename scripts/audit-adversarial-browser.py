#!/usr/bin/env python3
"""Real UI redaction and rejection of adversarial inputs; disposable data only."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import zipfile

from PIL import Image
from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'webapp')]
import app as webapp  # noqa: E402
import engine  # noqa: E402
import project_history  # noqa: E402
import workflows  # noqa: E402

out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
checks = []; errors = []; external = []
result = {'passed': False}


def check(name, condition):
    checks.append({'check': name, 'passed': bool(condition)})
    if not condition:
        raise AssertionError(name)


def wait(page, condition):
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if page.evaluate('() => (' + condition + ')'):
            return
        page.wait_for_timeout(60)
    raise AssertionError('Timeout: ' + condition)


with tempfile.TemporaryDirectory(prefix='report-gen-security-') as temporary:
    root = Path(temporary)
    source = root/'source'; (source/'img').mkdir(parents=True)
    Image.new('RGB', (80, 50), 'red').save(source/'img/proof space.png')
    Image.new('RGB', (40, 40), 'blue').save(source/'cover space.png')
    uid = workflows.new_uid()
    doc = {'meta': {'report_title': 'Controlled security audit', 'lang': 'es', 'theme': 'corporativo',
                    'branding': {'logo': 'cover%20space.png'}},
           'report': {'sections': [{'key': 'findings'}]},
           'evidence': [{'uid': uid, 'title': 'Synthetic sensitive evidence', 'src': 'img/proof%20space.png'}],
           'findings': [{'id': 'F1', 'title': 'Synthetic finding', 'severity': 'info', 'cvss': 0,
                         'description_md': '![Alternate URI](./img/proof%20space.png)',
                         'walkthrough': [{'figure': {'src': 'img/proof space.png'}}]}]}
    project_history.save(source, doc)
    bundle = root/'source.zip'; bundle.write_bytes(project_history.export_bundle(source))
    webapp.PROJECTS = root/'projects'; webapp.PROJECTS.mkdir()
    webapp.app.config['LIBRARY_PATH'] = str(root/'library.json')
    server = webapp.create_local_server(0)
    thread = threading.Thread(target=server.run, daemon=True); thread.start()
    base = f'http://127.0.0.1:{server.effective_port}'
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={'width': 1366, 'height': 1000}, accept_downloads=True)
            context.on('request', lambda req: external.append(req.url)
                       if not req.url.startswith((base+'/', 'blob:', 'data:', 'about:')) else None)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('dialog', lambda dialog: dialog.accept('security-audit') if dialog.type == 'prompt' else dialog.dismiss())
            response = page.goto(base)
            check('Production WSGI server remains bound to loopback', server.socket.getsockname()[0] == '127.0.0.1')
            check('CSP remains enabled', "script-src 'self'" in response.headers.get('content-security-policy', ''))
            page.locator('#splash').wait_for(state='hidden')
            with page.expect_file_chooser() as choose:
                page.locator('#importProjectBtn').click()
            choose.value.set_files(bundle)
            wait(page, "S.slug === 'security-audit' && !projectStore.loading")
            directory = webapp.PROJECTS/'security-audit'
            check('Backup imported through native UI', directory.exists())
            check('Backup preserves root-level logo bytes', (directory/'cover space.png').read_bytes() == (source/'cover space.png').read_bytes())
            wait(page, "document.querySelector('#pdfPreview').contentDocument?.images.length > 1 && "
                 "[...document.querySelector('#pdfPreview').contentDocument.images].every(i=>i.complete && i.naturalWidth>0)")
            check('Root logo and all aliases load in preview', True)
            page.locator('[data-workflow="evidence"]').click()
            page.get_by_role('button', name='Anotar / censurar', exact=True).click()
            page.get_by_role('button', name='Añadir zona con coordenadas', exact=True).click()
            for key, value in [('x', '0'), ('y', '0'), ('w', '100'), ('h', '100')]:
                field = page.locator('[aria-label="'+key+' %"]')
                field.fill(value); field.press('Tab')
            page.screenshot(path=str(out/'redaction-selected.png'), full_page=True)
            page.get_by_role('button', name='Aplicar y guardar copia', exact=True).click()
            page.get_by_role('dialog', name='Anotar y censurar evidencia').wait_for(state='detached')
            current = engine.load_engagement(directory/'engagement.yaml')
            masked = current['evidence'][0]['src']
            check('Native UI produced a fresh evidence image', masked.startswith('img/evidence-'))
            check('Raw-path reference now uses the censored copy', current['findings'][0]['walkthrough'][0]['figure']['src'] == masked)
            check('Encoded Markdown alias now uses the censored copy', masked in current['findings'][0]['description_md'])
            check('Old delivery image is removed', not (directory/'img/proof space.png').exists())
            with Image.open(directory/masked) as image:
                check('Redaction covers the full saved bitmap', image.getextrema() == ((0, 0), (0, 0), (0, 0)))
            page.locator('#exportFormat').select_option('md')
            with page.expect_download() as promise:
                page.locator('#downloadBtn').click()
            target = out/'redacted-delivery.zip'; promise.value.save_as(target)
            with zipfile.ZipFile(target) as z:
                check('Export contains no old uncensored filename', 'img/proof space.png' not in z.namelist())
                check('Export contains the fresh censored image', masked in z.namelist())
                with Image.open(BytesIO(z.read(masked))) as image:
                    check('Exported bitmap remains entirely black', image.getextrema() == ((0, 0), (0, 0), (0, 0)))
                check('Client delivery excludes internal originals and history', not any(n.startswith(('history/', 'originals/')) for n in z.namelist()))
            before = hashlib.sha256((directory/'engagement.yaml').read_bytes()).hexdigest()
            for name, payload in [
                ('NaN', '{"meta": {"version": NaN}}'),
                ('duplicate keys', '{"meta": {}, "findings": [{"id":"F1"}], "findings": []}'),
                ('deep JSON', '{"meta":{},"extra":'+ '['*90+'0'+']'*90+'}')]:
                status = page.evaluate('''async body => {
                    const token = (await (await fetch('/api/session')).json()).csrf;
                    return (await fetch('/api/projects/security-audit', {method:'PUT', headers:{
                        'Content-Type':'application/json', 'X-CSRF-Token':token, 'If-Match':projectStore.etag}, body})).status;
                }''', payload)
                check('HTTP rejects '+name, status == 422)
            check('Rejected requests preserve the complete saved YAML', hashlib.sha256((directory/'engagement.yaml').read_bytes()).hexdigest() == before)
            page.reload()
            wait(page, "S.slug === 'security-audit' && !projectStore.loading")
            check('Project still opens normally after rejected requests', page.locator('#findingList > li').count() == 1)
            check('No browser JavaScript errors', not errors)
            check('No requests to external resources', not external)
            result = {'browser': browser.version, 'passed': True}
            context.close(); browser.close()
    finally:
        server.close(); thread.join(timeout=3)
        result.update(checks=checks, errors=errors, external=external)
        (out/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
print(json.dumps({'checks': len(checks), 'passed': result['passed']}))
