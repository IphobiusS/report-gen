#!/usr/bin/env python3
"""Dashboard, bilingual library and complete backup acceptance in real Chromium."""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import zipfile
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'webapp')]
import app as webapp  # noqa: E402

parser=argparse.ArgumentParser()
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];outside=[]


def check(name,value,detail=None):
    checks.append({'check':name,'passed':bool(value),'detail':detail})
    (out/'checks.json').write_text(json.dumps({'checks':checks,'errors':errors,'external_requests':outside},indent=2)+'\n')
    assert value,(name,detail)


def wait(page,condition):
    page.wait_for_function('()=>('+condition+')')


def ready(page):
    wait(page,'S.slug&&!projectStore.loading&&projectBusyCount===0')


def start(root):
    webapp.PROJECTS=root/'projects';webapp.PROJECTS.mkdir(parents=True)
    webapp.app.config['LIBRARY_PATH']=str(root/'library'/'findings.json')
    webapp.app.config['DESIGN_LIBRARY_PATH']=str(root/'library'/'designs.json')
    server=webapp.create_local_server(0)
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    return server,f'http://127.0.0.1:{server.effective_port}'


with tempfile.TemporaryDirectory(prefix='workspace-browser-') as temp:
    root=Path(temp);server,base=start(root/'source')
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(executable_path=os.environ.get('RG_BROWSER_PATH'))
            context=browser.new_context(viewport={'width':1440,'height':1040},reduced_motion='reduce',accept_downloads=True)
            context.on('request',lambda r:outside.append(r.url) if not r.url.startswith((base+'/', 'blob:', 'data:', 'about:')) else None)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base);page.locator('.workspace-dashboard').wait_for()
            wait(page,"document.querySelector('.workspace-mascots img').complete")
            page.screenshot(path=str(out/'welcome-es.png'),full_page=True)
            check('Welcome offers project and template actions',page.get_by_role('button',name='Crear proyecto',exact=True).is_visible() and page.get_by_role('button',name='Explorar plantillas',exact=True).is_visible())
            page.get_by_role('button',name='Probar demo Nimbus',exact=True).click();ready(page)
            snapshot=page.evaluate('structuredClone(S.data)');demo=page.evaluate('S.slug')
            page.locator('.toast').wait_for(state='detached')
            check('Overview uses actual Nimbus counts',page.locator('.workspace-stat strong').all_text_contents()==['12','8','18','15/22'])
            for width in (390,768,1366,1440):
                page.set_viewport_size({'width':width,'height':1000})
                for theme in ('dark','light'):
                    if page.locator('html').get_attribute('data-theme')!=theme:page.locator('#themeToggle').click()
                    wait(page,"[...document.images].filter(i=>i.getClientRects().length).every(i=>i.complete&&i.naturalWidth>0)")
                    measure=page.evaluate('''() => ({body:document.documentElement.scrollWidth,width:innerWidth,editor:document.querySelector('#editor').scrollWidth,box:document.querySelector('#editor').clientWidth})''')
                    check(f'Overview does not overflow at {width} / {theme}',measure['body']<=width+1 and measure['editor']<=measure['box']+1,measure)
                    check(f'Primary dashboard action visible at {width} / {theme}',page.get_by_role('button',name='Continuar informe',exact=True).is_visible())
                    bad=page.locator('.workspace-topline button,.workspace-toolbar button,.workspace-hero-actions button').evaluate_all('(es)=>es.filter(e=>e.getClientRects().length&&!e.disabled).filter(e=>e.getBoundingClientRect().height<39).map(e=>e.id||e.textContent)')
                    check(f'Action targets at {width} / {theme}',not bad,bad)
                    if width in (390,1440):page.screenshot(path=str(out/f'dashboard-{theme}-{width}.png'),full_page=True)
            page.set_viewport_size({'width':1366,'height':1000})
            page.locator('#langToggle').click()
            check('Interface switch preserves full report',page.evaluate('S.data')==snapshot)
            check('Interface switch leaves revision clean',page.evaluate('!projectStore.dirty'))
            check('English overview labels',page.get_by_role('button',name='Continue report',exact=True).is_visible())
            page.locator('#themeToggle').click()
            page.screenshot(path=str(out/'dashboard-en.png'),full_page=True)
            page.locator('#navHome').focus();page.keyboard.press('Enter')
            focused=page.locator('#editor').evaluate('e=>({focused:e===document.activeElement,top:e.getBoundingClientRect().top})')
            check('Overview keyboard navigation focuses content below header',focused['focused'] and focused['top']>0,focused)
            page.locator('.workspace-finding').first.focus();page.keyboard.press('Enter')
            check('Finding opens by keyboard',page.evaluate("S.sel.type==='finding'&&S.sel.idx===0"))
            for width in (390,768,1366):
                page.set_viewport_size({'width':width,'height':1000})
                check(f'Finding editor does not overflow at {width}',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
            page.set_viewport_size({'width':1366,'height':1000})
            page.locator('#navReport').click()
            page.locator('#designLibraryBtn').click()
            gal=page.get_by_role('dialog',name='Report design library',exact=True)
            gal.wait_for(state='visible')
            check('English gallery has 14 OffSec profiles',gal.locator('[data-design]').count()==14)
            gal.locator('[data-design="offsec-oscp"]').click()
            wait(page,"[...document.querySelectorAll('.design-preview img')].every(i=>i.complete&&i.naturalWidth>0)")
            check('English cover is rendered English asset','/en/brand-cover.webp' in gal.locator('.design-preview img').get_attribute('src'))
            gal.get_by_label('Design variant').select_option('quiet')
            gal.get_by_role('button',name='Technical',exact=True).click()
            check('English quiet technical page exists','/en/quiet-technical.webp' in gal.locator('.design-preview img').get_attribute('src'))
            gal.get_by_role('button',name='Cover',exact=True).click()
            gal.get_by_label('Design variant').select_option('brand')
            page.screenshot(path=str(out/'gallery-en.png'))
            gal.get_by_role('button',name='Duplicate and customize',exact=True).click()
            custom=page.get_by_role('dialog',name='Customize design',exact=True)
            english=custom.locator('[data-section-lang="en"]').first
            spanish=custom.locator('[data-section-lang="es"]').first.input_value()
            english.fill('Executive overview')
            custom.get_by_role('button',name='Save design',exact=True).click()
            custom.wait_for(state='detached')
            gal.locator('[data-design^="custom-"]').click()
            gal.locator('.design-live-page iframe').wait_for()
            gal.get_by_role('button',name='Create project',exact=True).click()
            new=page.get_by_role('dialog',name='New project from design',exact=True)
            new.locator('[data-design-field="project-title"]').fill('English security assessment')
            check('New project defaults to English',new.locator('[data-design-field="lang"]').input_value()=='en')
            new.get_by_role('button',name='Create project',exact=True).click()
            wait(page,"S.data.meta.report_title==='English security assessment'&&!projectStore.loading")
            check('English personal title survives save and create',page.evaluate("S.data.report.sections[0].title==='Executive overview'"))
            catalog=page.evaluate("async()=>await api.get('/api/design-library')")
            check('Spanish personal title remains unchanged',catalog['personal'][0]['sections'][0]['title']['es']==spanish)
            page.locator('#workspaceBackupBtn').click()
            dialog=page.get_by_role('dialog',name='Workspace backup',exact=True)
            with page.expect_download(timeout=120000) as downloading:dialog.get_by_role('button',name='Download workspace',exact=True).click()
            archive=out/'workspace-test.zip';downloading.value.save_as(archive)
            with zipfile.ZipFile(archive) as z:check('Complete ZIP contains both projects and libraries',len([n for n in z.namelist() if n.startswith('projects/')])==2 and {'libraries/findings.json','libraries/designs.json'}<=set(z.namelist()))
            dialog.get_by_role('button',name='Close',exact=True).click()
            dialog.wait_for(state='detached')
            wait(page,"document.activeElement.id==='workspaceBackupBtn'")
            check('Backup dialog returns focus',page.locator('#workspaceBackupBtn').evaluate('e=>e===document.activeElement'))
            page.locator('#projectSelect').select_option(demo);ready(page)
            check('Creating an English report preserves Nimbus',page.evaluate('S.data')==snapshot)
            page.locator('#exportMenu summary').click()
            for fmt in ('pdf','docx'):
                page.locator('#exportFormat').select_option(fmt)
                with page.expect_download(timeout=120000) as export_download:
                    page.locator('#downloadBtn').click()
                exported=out/('nimbus-ui.'+fmt);export_download.value.save_as(exported)
                if fmt=='pdf':
                    import fitz
                    document=fitz.open(exported);text='\n'.join(p.get_text() for p in document)
                else:
                    from docx import Document
                    text=' '.join(Document(exported).element.xpath('//w:t/text()'))
                missing=[f['id'] for f in snapshot['findings'] if f['title'] not in text]
                check('Header exports complete Nimbus '+fmt,not missing,missing)
            page.locator('#exportMenu summary').click()
            check('No browser JavaScript errors',not errors,errors)
            check('No external requests while using the dashboard',not outside,outside)
            context.close();server.close()
            server,base=start(root/'destination')
            context=browser.new_context(viewport={'width':1366,'height':1000})
            page=context.new_page();page.goto(base);page.locator('.workspace-dashboard').wait_for()
            page.locator('#workspaceBackupBtn').click()
            dialog=page.get_by_role('dialog',name='Respaldo integral',exact=True)
            dialog.locator('[data-workspace-file]').set_input_files(archive)
            dialog.get_by_role('button',name='Restaurar espacio de trabajo',exact=True).click();ready(page)
            check('Fresh installation restores projects',page.locator('#projectSelect option').count()==2)
            page.locator('#projectSelect').select_option(demo);ready(page)
            check('Restored Nimbus matches source content',page.evaluate('S.data')==snapshot)
            check('Restored personal library retains both languages',page.evaluate("async()=>(await api.get('/api/design-library')).personal[0].sections[0].title.en")=='Executive overview')
            context.close();browser.close()
    finally:
        server.close()
print(json.dumps({'passed':len(checks),'chromium':'141','checks':checks},indent=2))
