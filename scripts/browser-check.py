#!/usr/bin/env python3
"""Optional real Chromium acceptance check (local server and disposable project)."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'webapp')]
import app as webapp  # noqa: E402
import engine  # noqa: E402
import project_history  # noqa: E402
from werkzeug.serving import make_server  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'out/browser-check')
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    checks=[]; errors=[]
    def check(name, result, detail=None):
        checks.append(dict(check=name, passed=bool(result), detail=detail))
        if not result: raise AssertionError(name + ': ' + str(detail))
    with tempfile.TemporaryDirectory(prefix='report-gen-browser-') as tmp:
        webapp.PROJECTS = Path(tmp) / 'projects'; webapp.PROJECTS.mkdir()
        webapp.app.config['LIBRARY_PATH'] = str(Path(tmp) / 'library.json')
        project = webapp.PROJECTS / 'demo'
        project_history.import_bundle((ROOT / 'examples/workflow-demo-project.zip').read_bytes(), project)
        server = make_server('127.0.0.1', 0, webapp.app, threaded=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                context = browser.new_context(viewport={'width':1366,'height':900}, reduced_motion='reduce', accept_downloads=True)
                page = context.new_page(); page.on('pageerror', lambda error: errors.append(str(error)))
                def wait(expression):
                    # Keep the real CSP enabled. Playwright's polling helper uses eval.
                    deadline = time.monotonic()+30
                    while time.monotonic() < deadline:
                        if page.evaluate('() => ('+expression+')'): return
                        page.wait_for_timeout(50)
                    raise AssertionError('Timed out: '+expression)
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                wait("typeof S !== 'undefined' && S.slug === 'demo' && !projectStore.loading")
                page.locator('#splash').wait_for(state='hidden')
                page.locator('[data-field="report_title"]').fill('Informe de auditoría de interfaz')
                wait('!projectStore.dirty')
                check('Autosave persisted', engine.load_engagement(project/'engagement.yaml')['meta']['report_title']=='Informe de auditoría de interfaz')
                for lang in ['en','es']:
                    if page.locator('html').get_attribute('lang') != lang:
                        page.locator('#langToggle').click()
                    check('Editor language '+lang, page.locator('html').get_attribute('lang') == lang)
                wait('!projectStore.dirty')
                page.locator('#previewLoading').wait_for(state='hidden')
                cover_mark = page.frame_locator('#pdfPreview').locator('.cv-wordmark')
                cover_mark.wait_for(state='visible')
                cover_mark.evaluate('() => document.fonts.ready.then(() => true)')
                for theme in ['dark','light']:
                    current = page.locator('html').get_attribute('data-theme')
                    if current != theme: page.locator('#themeToggle').click()
                    check('Theme '+theme, page.locator('html').get_attribute('data-theme') == theme)
                    for width in [1366,1024,768,390]:
                        page.set_viewport_size({'width':width,'height':900})
                        measure = page.evaluate('''() => {
                          const brand=document.querySelector('.brand-name');
                          const a=brand.getBoundingClientRect(); const b=brand.querySelector('span').getBoundingClientRect();
                          const letters=document.createRange(); letters.selectNodeContents(brand.firstChild);
                          return {scroll:document.documentElement.scrollWidth, viewport:innerWidth,
                            brandHeight:a.height, suffixTop:b.top, brandTop:letters.getBoundingClientRect().top,
                            offenders:[...document.querySelectorAll('body *')].filter(e=>{
                              const r=e.getBoundingClientRect();return r.width>0 && r.right>innerWidth+1 && getComputedStyle(e).position!=='absolute';
                            }).slice(0,8).map(e=>e.tagName+'.'+e.className)};
                        }''')
                        check(f'No horizontal document overflow {theme} {width}', measure['scroll'] <= width+1, measure)
                        check(f'Unbroken report-gen wordmark {theme} {width}', abs(measure['suffixTop']-measure['brandTop']) < 2, measure)
                        page.locator('#validateBtn').focus()
                        page.keyboard.press('Tab'); page.keyboard.press('Shift+Tab')
                        focus=page.locator('#validateBtn').evaluate('(e)=>({width:getComputedStyle(e).outlineWidth,style:getComputedStyle(e).outlineStyle})')
                        check(f'Visible focus {theme} {width}', focus['width']=='3px' and focus['style']=='solid', focus)
                        if width == 390:
                            mark = page.frame_locator('#pdfPreview').locator('.cv-wordmark').evaluate('''e => {
                                const range=document.createRange();range.selectNodeContents(e);
                                return [...range.getClientRects()].map(r=>r.top);
                            }''')
                            check('Unbroken report cover wordmark '+theme, len(set(mark)) == 1, mark)
                        if width in (1366,390): page.screenshot(path=str(output/f'editor-{theme}-{width}.png'),full_page=True)
                page.set_viewport_size({'width':1366,'height':900})
                for kind in ['assets','coverage','retest','history','evidence','review']:
                    page.locator(f'[data-workflow="{kind}"]').click()
                    page.locator(f'[data-workflow-view="{kind}"]').wait_for()
                    wait(f"document.querySelector('[data-workflow-view=\"{kind}\"]').childNodes.length > 0")
                    check('Workflow view '+kind, page.locator(f'[data-workflow-view="{kind}"]').is_visible())
                page.locator('#navReport').click()
                wait('!projectStore.dirty')
                for fmt in ['md','docx','pdf']:
                    page.locator('#exportFormat').select_option(fmt)
                    with page.expect_download(timeout=120000) as promise:
                        page.locator('#downloadBtn').click()
                    download=promise.value
                    check('Download '+fmt, download.failure() is None)
                    target=output/('browser-demo.'+('zip' if fmt=='md' else fmt))
                    download.save_as(target)
                    check('Nonempty export '+fmt, target.stat().st_size > 1000)
                page.locator('[data-workflow="backup"]').click()
                with page.expect_download() as promise:
                    page.get_by_role('button',name='Descargar respaldo ZIP',exact=True).click()
                target=output/'browser-project.zip';promise.value.save_as(target)
                restored=webapp.PROJECTS/'restored'
                project_history.import_bundle(target.read_bytes(),restored)
                check('Downloaded backup imports with identical data', engine.load_engagement(restored/'engagement.yaml')==engine.load_engagement(project/'engagement.yaml'))
                check('No browser exceptions', not errors, errors)
                result={'browser':browser.version,'checks':checks,'passed':True}
                context.close();browser.close()
        finally:
            server.shutdown();thread.join(timeout=3)
            (output/'browser-results.json').write_text(json.dumps(locals().get('result',{'checks':checks,'errors':errors,'passed':False}),ensure_ascii=False,indent=2))
    print(json.dumps({'checks':len(checks),'passed':True,'output':str(output)}))


if __name__=='__main__': main()
