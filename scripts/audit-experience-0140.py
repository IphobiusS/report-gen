#!/usr/bin/env python3
"""Real-browser acceptance for first use, finding templates and client delivery.
Runs a disposable loopback server and project directory; never edits user data.
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

from playwright.sync_api import sync_playwright
import yaml

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output',type=Path,required=True)
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'webapp')]
import app as webapp  # noqa: E402

output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];outbound=[]
def check(name,ok,detail=None):
    checks.append(dict(check=name,passed=bool(ok),detail=detail))
    if not ok:raise AssertionError(name+': '+str(detail))
def wait(page,expression,seconds=60):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        if page.evaluate('()=>('+expression+')'):return
        page.wait_for_timeout(70)
    raise AssertionError('Timeout: '+expression)

def field(dialog,key):return dialog.locator('[data-field="'+key+'"]')

with tempfile.TemporaryDirectory(prefix='experience-audit-') as temp:
    webapp.PROJECTS=Path(temp)/'projects';webapp.PROJECTS.mkdir()
    webapp.app.config['LIBRARY_PATH']=str(Path(temp)/'library.json')
    server=webapp.create_local_server(0)
    thread=threading.Thread(target=server.run,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.effective_port}'
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch()
            context=browser.new_context(viewport={'width':1366,'height':1000},reduced_motion='reduce',accept_downloads=True)
            context.on('request',lambda r:outbound.append(r.url) if not r.url.startswith((base+'/', 'blob:', 'data:', 'about:')) else None)
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            response=page.goto(base);page.locator('#splash').wait_for(state='hidden')
            check('CSP remains enabled',bool(response.headers.get('content-security-policy')))
            check('First-use welcome and demo action',page.get_by_role('button',name='Probar Nimbus',exact=True).is_visible())
            page.screenshot(path=str(output/'first-use.png'))
            page.get_by_role('button',name='Probar Nimbus',exact=True).click()
            wait(page,"S.slug?.startsWith('nimbus-demo-') && !projectStore.loading")
            slug=page.evaluate('S.slug');source=webapp.PROJECTS/slug/'engagement.yaml'
            data=yaml.safe_load(source.read_bytes())
            check('One-click Nimbus has 12 findings',len(data['findings'])==12)
            check('Nimbus has 19 evidence files',len(list((source.parent/'img').glob('*')))==19)
            check('Guided walkthrough visible',page.locator('.demo-guide').is_visible())
            page.get_by_role('button',name='1. Editar hallazgo',exact=True).click()
            check('Guide opens first finding',page.evaluate("S.sel.type==='finding'&&S.sel.idx===0"))
            page.get_by_role('button',name='2. Añadir evidencia',exact=True).click()
            page.locator('[data-workflow-view="evidence"] .wf-thumb').first.wait_for(state='visible')
            check('Guide opens evidence gallery',page.locator('[data-workflow-view="evidence"]').is_visible())
            # The local library has visual editing, variables and immutable versions.
            page.locator('#libBtn').click()
            page.get_by_role('button',name='Nueva plantilla',exact=True).click()
            dialog=page.get_by_role('dialog',name='Plantilla reutilizable',exact=True)
            field(dialog,'name').fill('Acceso a objeto ajeno')
            field(dialog,'tagsText').fill('web, authorization')
            field(dialog,'title').fill('Autorización en ')
            dialog.get_by_role('button',name='{{objetivo}}',exact=True).click()
            check('Variable inserted at caret',field(dialog,'title').input_value()=='Autorización en {{objetivo}}')
            field(dialog,'cwe').fill('CWE-639')
            field(dialog,'cvss_vector').fill('CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N')
            dialog.get_by_role('button',name='Calcular desde el vector',exact=True).click()
            wait(page,"document.querySelector('[data-template-editor] [data-field=cvss]').value==='5.4'")
            check('Vector computes score and severity',field(dialog,'severity').input_value()=='medium')
            field(dialog,'description_md').fill('Control de acceso en {{endpoint}} para {{cliente}}.')
            field(dialog,'impact_md').fill('Lectura de un objeto de otra identidad.')
            field(dialog,'remediation_md').fill('Validar pertenencia en el servidor y repetir la prueba.')
            dialog.get_by_role('button',name='Añadir paso',exact=True).click()
            field(dialog,'lead').fill('Comparar dos identidades')
            field(dialog,'text_md').fill('Repetir la solicitud con el segundo usuario autorizado.')
            field(dialog,'command').fill('GET /objects/101 HTTP/1.1')
            field(dialog,'references').fill('https://owasp.org/www-project-web-security-testing-guide/')
            dialog.get_by_role('button',name='Vista previa del texto',exact=True).click()
            dialog.locator('.template-preview').wait_for(state='visible')
            check('Preview renders safely',dialog.locator('.template-preview').inner_text().startswith('Autorización'))
            dialog.locator('summary').filter(has_text='Edición avanzada JSON').click()
            raw=dialog.get_by_role('textbox',name='Contenido avanzado JSON')
            raw.fill('{"walkthrough":123}')
            dialog.get_by_role('button',name='Aplicar JSON al formulario',exact=True).click()
            check('Invalid advanced JSON preserves visual data',field(dialog,'title').input_value()=='Autorización en {{objetivo}}')
            raw.fill(json.dumps({'mode':'vuln','title':field(dialog,'title').input_value(),'severity':'medium','cvss':5.4,'cvss_vector':'CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:L/I:L/A:N','cwe':'CWE-639','description_md':'Control de acceso en {{endpoint}} para {{cliente}}.','impact_md':'Lectura de un objeto de otra identidad.','remediation_md':'Validar pertenencia y repetir la prueba.','walkthrough':[{'lead':'Comparar dos identidades','text_md':'Repetir la solicitud con el segundo usuario autorizado.','command':'GET /objects/101 HTTP/1.1'}],'references':[]}))
            dialog.get_by_role('button',name='Aplicar JSON al formulario',exact=True).click()
            for width in [1366,390]:
                page.set_viewport_size({'width':width,'height':1000})
                rect=dialog.locator('.modal-box').bounding_box()
                check('Template editor fits viewport '+str(width),rect['x']>=0 and rect['y']>=0 and rect['x']+rect['width']<=width+1 and rect['height']<=901,rect)
                check('Template dialog has no horizontal overflow '+str(width),dialog.locator('.modal-box').evaluate('e=>e.scrollWidth<=e.clientWidth+1'))
            page.set_viewport_size({'width':1366,'height':1000})
            dialog.locator('.modal-box').evaluate('e=>e.scrollTop=0')
            page.screenshot(path=str(output/'template-editor.png'))
            dialog.get_by_role('checkbox',name='He revisado que no contenga datos de otro cliente').check()
            dialog.get_by_role('button',name='Guardar versión de plantilla',exact=True).click()
            dialog.wait_for(state='hidden')
            page.get_by_role('heading',name='Acceso a objeto ajeno',exact=True).wait_for()
            library=json.loads((Path(temp)/'library.json').read_text())
            entry=library['templates'][0]
            check('Visual template stored with score and steps',entry['content']['cvss']==5.4 and len(entry['content']['walkthrough'])==1)
            page.get_by_role('button',name='Editar / versiones',exact=True).click()
            field(dialog,'impact_md').fill('Impacto revisado y acotado.')
            dialog.get_by_role('checkbox',name='He revisado que no contenga datos de otro cliente').check()
            dialog.get_by_role('button',name='Guardar versión de plantilla',exact=True).click();dialog.wait_for(state='hidden')
            library=json.loads((Path(temp)/'library.json').read_text());entry=library['templates'][0]
            check('Editing retains previous template version',len(entry['versions'])==2 and entry['versions'][0]['content']['impact_md']!='Impacto revisado y acotado.')
            page.get_by_role('button',name='Insertar',exact=True).click()
            insert=page.get_by_role('dialog',name='Insertar plantilla',exact=True)
            field(insert,'objetivo').fill('API de pruebas')
            field(insert,'endpoint').fill('/objects/101')
            insert.get_by_role('button',name='Insertar en el proyecto',exact=True).click()
            wait(page,'S.data.findings.length===13 && !projectStore.dirty')
            inserted=yaml.safe_load(source.read_bytes())['findings'][-1]
            check('Inserted template resolves variables',inserted['title']=='Autorización en API de pruebas' and '{{' not in inserted['description_md'])
            check('Inserted template has independent identity',inserted.get('id')=='F13' and inserted.get('uid'))
            # Test lab/machine visual mode without mutating the project.
            page.locator('#libBtn').click();page.get_by_role('button',name='Nueva plantilla',exact=True).click()
            field(dialog,'mode').select_option('machine')
            dialog.get_by_role('button',name='Añadir fase',exact=True).click()
            field(dialog,'name').nth(1).fill('Enumeración')
            dialog.get_by_role('button',name='Añadir paso',exact=True).click()
            check('Machine template exposes phases and steps',field(dialog,'command').count()==1)
            page.keyboard.press('Escape');dialog.wait_for(state='hidden')
            check('Escape restores template focus',page.evaluate("document.activeElement.textContent==='Nueva plantilla'"))
            # UI/report themes remain distinct settings and both new report designs render.
            page.locator('#navReport').click()
            for name in ['ejecutivo','laboratorio']:
                page.locator('[data-field="theme"]').select_option(name)
                wait(page,'!projectStore.dirty')
                check('Report design saved '+name,yaml.safe_load(source.read_bytes())['meta']['theme']==name)
            for theme in ['dark','light']:
                if page.locator('html').get_attribute('data-theme')!=theme:page.locator('#themeToggle').click()
                for width in [1366,390]:
                    page.set_viewport_size({'width':width,'height':1000})
                    check(f'Editor no horizontal overflow {theme} {width}',page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'))
                    check(f'Logo single line {theme} {width}',page.locator('.brand-name').evaluate("e=>{let r=document.createRange();r.selectNodeContents(e.firstChild);return Math.abs(r.getBoundingClientRect().top-e.querySelector('span').getBoundingClientRect().top)<2}"))
            page.set_viewport_size({'width':1366,'height':1000})
            # Build from the real saved Nimbus copy, through the normal delivery dialog.
            page.locator('#deliveryBtn').click();delivery=page.get_by_role('dialog',name='Preparar entrega',exact=True)
            delivery.wait_for(state='visible')
            check('Delivery surfaces known coverage warnings',delivery.locator('.wf-warning').count()>=3)
            warning_contrast=delivery.locator('.wf-warning').first.evaluate("""e=>{
                const rgb=s=>s.match(/[\\d.]+/g).slice(0,3).map(Number);
                const lum=a=>a.map(x=>{x/=255;return x<=.04045?x/12.92:((x+.055)/1.055)**2.4})
                    .reduce((v,x,i)=>v+x*[.2126,.7152,.0722][i],0);
                const a=lum(rgb(getComputedStyle(e).color));
                const b=lum(rgb(getComputedStyle(e.closest('dialog')).backgroundColor));
                return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
            }""")
            check('Light delivery warnings have readable contrast',warning_contrast>=4.5,warning_contrast)
            delivery.locator('[data-delivery="ack"]').check()
            page.screenshot(path=str(output/'delivery.png'))
            before=source.read_bytes()
            with page.expect_download(timeout=180000) as download:
                delivery.get_by_role('button',name='Generar paquete',exact=True).click()
            target=output/'nimbus-client-delivery.zip';download.value.save_as(target)
            check('Delivery download succeeds',download.value.failure() is None)
            with zipfile.ZipFile(target) as z:
                record=json.loads(z.read('verificacion.json'))
                check('Delivery contains only selected client outputs and record',set(z.namelist())=={'informe.pdf','informe.docx','markdown.zip','verificacion.json','LEEME.txt'})
                check('Delivery revision matches the saved source',record['source_revision']==hashlib.sha256(before).hexdigest())
                check('Delivery includes all 19 image placements',record['files']['informe.pdf']['checks']['image_placements']>=19)
                check('Every delivery checksum matches',all(hashlib.sha256(z.read(n)).hexdigest()==m['sha256'] for n,m in record['files'].items()))
                check('Delivery passed internal PDF TOC checks',record['files']['informe.pdf']['checks']['toc_references_checked']>0)
            check('Delivery does not change project or status',source.read_bytes()==before)
            page.keyboard.press('Escape');delivery.wait_for(state='hidden')
            check('Native delivery dialog returns focus',page.evaluate("document.activeElement.id==='deliveryBtn'"))
            page.locator('#diagnosticsBtn').click()
            diag=page.get_by_role('dialog',name='Comprobar instalación',exact=True)
            diag.get_by_text('Escritura disponible',exact=True).wait_for(timeout=50000)
            check('Real diagnostics report both PDF engines',diag.inner_text().count('✓')>=4,diag.inner_text())
            page.keyboard.press('Escape')
            check('No browser JavaScript errors',not errors,errors)
            check('No external resource requests',not outbound,outbound)
            result=dict(passed=True,browser=browser.version,checks=checks)
            context.close();browser.close()
    finally:
        server.close();thread.join(timeout=3)
        result=locals().get('result',dict(passed=False,checks=checks,errors=errors))
        (output/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'checks':len(checks),'passed':True}))
