#!/usr/bin/env python3
"""Focused layout check and clean screenshots for the 0.18 workbench."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'webapp')]
import app as api  # noqa: E402

p = argparse.ArgumentParser()
p.add_argument('--output', type=Path, required=True)
out = p.parse_args().output.resolve(); out.mkdir(parents=True, exist_ok=True)
checks, errors = [], []
with tempfile.TemporaryDirectory(prefix='report-gen-appearance-') as temporary:
    api.PROJECTS = Path(temporary) / 'projects'; api.PROJECTS.mkdir()
    api.app.config['LIBRARY_PATH'] = str(Path(temporary) / 'findings.json')
    api.app.config['DESIGN_LIBRARY_PATH'] = str(Path(temporary) / 'designs.json')
    server = api.create_local_server(0)
    threading.Thread(target=server.run, daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=os.environ.get('RG_BROWSER_PATH'))
            page = browser.new_page(viewport={'width':1440,'height':1000},reduced_motion='reduce')
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.effective_port}')
            page.get_by_role('button',name='Probar demo Nimbus',exact=True).click()
            page.wait_for_function('()=>S.slug&&!projectStore.loading&&projectBusyCount===0')
            page.wait_for_function("()=>document.querySelector('.workspace-next [role=status]')?.textContent.startsWith('Pendientes')")
            page.get_by_role('button',name='Ocultar guía',exact=True).click()
            page.evaluate('document.fonts.ready')
            page.locator('.toast').wait_for(state='hidden')
            for lang in ('es','en'):
                page.evaluate('(l)=>setUiLang(l)',lang)
                for width in (360,390,768,1366):
                    page.set_viewport_size({'width':width,'height':1000})
                    result=page.locator('#densityBtn').evaluate('''b=>{const range=document.createRange();range.selectNodeContents(b);const t=range.getBoundingClientRect(),r=b.getBoundingClientRect();return {textFits:t.left>=r.left&&t.right<=r.right,hasLabel:!!b.getAttribute('aria-label'),pageFits:document.documentElement.scrollWidth<=innerWidth+1}}''')
                    checks.append(dict(check=f'Density label and viewport {lang} {width}',passed=all(result.values()),detail=result))
                    assert all(result.values()),checks[-1]
                page.set_viewport_size({'width':1440,'height':1000})
                page.wait_for_function("()=>!document.querySelector('.workspace-next [role=status]').textContent.match(/Comprobando|Checking/)")
                page.evaluate('document.querySelector("#editor").scrollTop=0;window.scrollTo(0,0)')
                if lang=='es':page.screenshot(path=str(out/'dashboard.png'),full_page=True)
                else:
                    page.evaluate('applyUiTheme("light")');page.screenshot(path=str(out/'dashboard-en.png'),full_page=True)
            page.evaluate('setUiLang("es");applyUiTheme("dark")')
            page.set_viewport_size({'width':390,'height':1000})
            page.wait_for_function("()=>!document.querySelector('.workspace-next [role=status]').textContent.includes('Comprobando')")
            page.evaluate('document.querySelector("#editor").scrollTop=0;window.scrollTo(0,0)')
            page.screenshot(path=str(out/'mobile.png'),full_page=True)
            page.set_viewport_size({'width':1440,'height':1000})
            page.evaluate('select("finding",0)')
            page.wait_for_function("()=>document.querySelector('#pdfPreview').contentDocument?.getElementById(S.data.findings[0].id)")
            page.screenshot(path=str(out/'editor.png'),full_page=True)
            checks.append(dict(check='No browser exceptions',passed=not errors,detail=errors))
            assert not errors,errors
            browser.close()
    finally:server.close()
result=dict(checks=checks)
partial=out/'appearance.json.partial';partial.write_text(json.dumps(result,indent=2),encoding='utf-8');partial.replace(out/'appearance.json')
print(json.dumps({'passed':len(checks),'output':str(out)}))
