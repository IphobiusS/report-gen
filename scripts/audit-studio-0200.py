#!/usr/bin/env python3
"""Real Chromium, isolated projects, local server and browser in one process."""
import argparse, json, sys, tempfile, threading, time
from copy import deepcopy
from pathlib import Path
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'webapp')]
import app as api
import workflows
from wizard import dump_yaml
from version import __version__
p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
checks=[];errors=[];external=[];metrics=[]
def record(name,ok,detail=None):
 checks.append(dict(name=name,passed=bool(ok),detail=detail));(out/'checks.json').write_text(json.dumps(dict(version=__version__,checks=checks,errors=errors,metrics=metrics,external=external),ensure_ascii=False,indent=2));assert ok,(name,detail)
def ready(pg):pg.wait_for_function('()=>S.slug && !projectStore.loading && projectBusyCount===0')
def saved(pg):pg.wait_for_function('()=>!projectStore.dirty && !projectStore.lastError')
with tempfile.TemporaryDirectory(prefix='rg-studio-0200-',ignore_cleanup_errors=True) as tmp:
 api.PROJECTS=Path(tmp)/'projects';api.PROJECTS.mkdir();api.app.config['LIBRARY_PATH']=str(Path(tmp)/'library.json');api.app.config['DESIGN_LIBRARY_PATH']=str(Path(tmp)/'designs.json')
 server=api.create_local_server(0);threading.Thread(target=server.run,daemon=True).start();base=f'http://127.0.0.1:{server.effective_port}'
 try:
  with sync_playwright() as pw:
   browser=pw.chromium.launch();context=browser.new_context(viewport={'width':1366,'height':960},accept_downloads=True,reduced_motion='reduce');pg=context.new_page()
   context.on('page',lambda page:page.on('pageerror',lambda e:errors.append(str(e))))
   pg.on('pageerror',lambda e:errors.append(str(e)))
   context.on('request',lambda r:external.append(r.url) if not r.url.startswith((base+'/', 'data:', 'blob:', 'about:', 'file:')) else None)
   pg.goto(base);pg.get_by_role('button',name='Probar demo Nimbus',exact=True).click();ready(pg);pg.wait_for_function('()=>document.querySelector(".attention-task")');pg.wait_for_timeout(300)
   slug=pg.evaluate('S.slug');source=pg.evaluate('structuredClone(S.data)')
   record('Four primary tasks',pg.locator('[data-studio-nav]').count()==4)
   record('Dogs retained',pg.locator('.workspace-mascots img').get_attribute('alt').find('Prometeo')>=0)
   pg.screenshot(path=str(out/'dashboard-es-1366.png'))
   for lang in ('es','en'):
    if pg.evaluate('S.uiLang')!=lang:
     pg.locator('#studioMore').evaluate('(e)=>e.open=true');pg.locator('#studioPreferences').evaluate('(e)=>e.open=true');pg.locator('#langToggle').select_option('en');pg.locator('#studioMore').evaluate('(e)=>e.open=false')
    for theme in ('dark','light'):
     if pg.evaluate('document.documentElement.dataset.theme')!=theme:
      pg.locator('#studioMore').evaluate('(e)=>e.open=true');pg.locator('#studioPreferences').evaluate('(e)=>e.open=true');pg.locator('#themeToggle').click();pg.locator('#studioMore').evaluate('(e)=>e.open=false')
     for width in (360,390,768,1366):
      pg.set_viewport_size({'width':width,'height':900});pg.locator('[data-studio-nav="work"]').click();pg.wait_for_timeout(50)
      dims=pg.evaluate('()=>({header:document.querySelector(".topbar").getBoundingClientRect().height,overflow:document.documentElement.scrollWidth>innerWidth+1,actions:[...document.querySelectorAll(".studio-nav button")].map(e=>e.getBoundingClientRect().height)})')
      record(f'No overflow {lang} {theme} {width}',not dims['overflow'],dims)
      record(f'Touch navigation {lang} {theme} {width}',min(dims['actions'])>=44)
      if width==390:record(f'Mobile header <=160 {lang} {theme}',dims['header']<=160,dims['header'])
      if (width,lang,theme) in [(390,'es','dark'),(1366,'en','light')]:pg.screenshot(path=str(out/f'dashboard-{lang}-{theme}-{width}.png'))
   pg.set_viewport_size({'width':1366,'height':960});pg.evaluate('()=>{S.uiLang="es";localStorage.setItem("rg.uiLang","es");applyStaticI18n();applyUiTheme("dark");select("section","executive");}')
   # Every rendered Markdown area receives its own accessible name.
   fields=pg.locator('textarea').evaluate_all('(els)=>els.map(e=>({key:e.dataset.field,name:e.getAttribute("aria-label")||[...e.labels].map(x=>x.textContent).join("")}))')
   record('Markdown editable fields named',bool(fields) and all(f['name'] for f in fields),fields)
   pg.locator('[data-studio-nav="deliver"]').click();pg.get_by_role('button',name='Abrir inspector',exact=True).click();pg.locator('.publication-text').wait_for();record('Inspector has exact resources',pg.locator('dialog img').count()==19)
   pg.screenshot(path=str(out/'inspector-es.png'));pg.keyboard.press('Escape');record('Inspector returns focus',pg.get_by_role('button',name='Abrir inspector',exact=True).evaluate('(e)=>e===document.activeElement'))
   # Literal redaction is explicit and leaves stored author content intact.
   pg.evaluate('()=>{select("finding",0)}');pg.locator('textarea[data-field="description_md"]').fill('API_KEY=synthetic_secret_to_redact');saved(pg)
   pg.locator('[data-studio-nav="deliver"]').click();pg.get_by_role('button',name='Abrir inspector',exact=True).click();pg.locator('.publication-text').wait_for();record('Secret warning present','credential' in pg.locator('dialog').inner_text())
   pg.get_by_text('Censura de texto para publicar',exact=True).click();pg.get_by_label('Texto literal a censurar',exact=True).fill('synthetic_secret_to_redact');pg.get_by_role('button',name='Aplicar y volver a inspeccionar',exact=True).click();pg.locator('.publication-text').wait_for();pg.wait_for_function('()=>document.querySelector(".publication-text")?.textContent.includes("[REDACTED]")');record('Original retained after publication redaction',pg.evaluate('S.data.findings[0].description_md')=='API_KEY=synthetic_secret_to_redact');pg.keyboard.press('Escape')
   # Saved revision bundle includes portable HTML, using the real worker.
   pg.evaluate('()=>{S.data=structuredClone(projectStore.base);select("studio","deliver")}')
   tag=pg.evaluate('projectStore.etag');csrf=pg.evaluate('csrfToken') if False else context.request.get(base+'/api/session').json()['csrf']
   response=context.request.post(base+f'/api/projects/{slug}/jobs',headers={'X-CSRF-Token':csrf,'If-Match':tag},data={'kind':'delivery','formats':['html','md'],'label':'Browser delivery','acknowledge_warnings':True});record('HTML delivery queued',response.status==202,response.text()[:250]);job=response.json()['id']
   deadline=time.monotonic()+120
   while time.monotonic()<deadline:
    status=context.request.get(base+'/api/jobs/'+job).json()
    if status['stage'] in ('done','error','cancelled'):break
    pg.wait_for_timeout(100)
   record('HTML delivery completed',status['stage']=='done',status)
   payload=context.request.get(base+'/api/jobs/'+job+'/download').body();(out/'browser-delivery.zip').write_bytes(payload)
   import zipfile
   with zipfile.ZipFile(out/'browser-delivery.zip') as z:(out/'report.html').write_bytes(z.read('informe.html'))
   client=browser.new_context(viewport={'width':1366,'height':960});htmlpage=client.new_page();htmlpage.goto((out/'report.html').as_uri());htmlpage.locator('#view').select_option('executive');record('Executive view hides finding detail',htmlpage.locator('.finding:visible').count()==0);htmlpage.locator('#view').select_option('technical');htmlpage.locator('#severity').select_option('critical');record('Portable severity filter',htmlpage.locator('.finding:visible').count()==2);htmlpage.screenshot(path=str(out/'portable-html.png'));record('Portable images loaded',htmlpage.locator('img').evaluate_all('(els)=>els.every(e=>e.complete&&e.naturalWidth>0)'));client.close()
   # Crash recovery: blocked save -> confirmed IndexedDB commit -> close -> new tab.
   pg.route('**/api/projects/'+slug,lambda route:route.fulfill(status=503,json={'error':'Synthetic save outage'}) if route.request.method=='PUT' else route.continue_())
   pg.evaluate('()=>select("finding",0)');pg.locator('textarea[data-field="description_md"]').fill('RECOVERABLE_DRAFT_0200\nLiteral command: printf "%s\\n" "x"')
   pg.wait_for_function('()=>projectStore.dirty && projectStore.recoverableRevision===projectStore.revision && projectStore.lastError?.status===503');record('Draft committed despite failed server save',True);pg.screenshot(path=str(out/'draft-recoverable.png'));pg.close()
   pg=context.new_page();pg.goto(base);ready(pg);pg.get_by_role('button',name='Comparar y recuperar',exact=True).click();pg.get_by_role('button',name='Aplicar selección y guardar',exact=True).click();pg.wait_for_function('()=>!document.querySelector("dialog[open]")');saved(pg);record('Abrupt closure recovered exact text',pg.evaluate('S.data.findings[0].description_md')=='RECOVERABLE_DRAFT_0200\nLiteral command: printf "%s\\n" "x"')
   # Two tabs edit the same field. An explicit choice uses current ETag.
   other=context.new_page();other.goto(base);ready(other);pg.evaluate('()=>select("finding",0)');other.evaluate('()=>select("finding",0)');pg.locator('textarea[data-field="description_md"]').fill('SERVER_CHOICE_0200');saved(pg);other.locator('textarea[data-field="description_md"]').fill('LOCAL_CHOICE_0200');other.wait_for_function('()=>projectStore.lastError?.status===409');other.get_by_role('button',name='Resolver con versión guardada',exact=True).click();other.locator('.merge-field').wait_for();record('Conflict shows both exact texts','SERVER_CHOICE_0200' in other.locator('dialog').inner_text() and 'LOCAL_CHOICE_0200' in other.locator('dialog').inner_text());other.screenshot(path=str(out/'conflict-resolution.png'));other.get_by_label('Mi borrador',exact=True).check();other.get_by_role('button',name='Aplicar selección y guardar',exact=True).click();other.wait_for_function('()=>!document.querySelector("dialog[open]")');saved(other);record('Explicit conflict resolution persisted',context.request.get(base+'/api/projects/'+slug).json()['findings'][0]['description_md']=='LOCAL_CHOICE_0200');other.close()
   pg.reload();ready(pg);pg.evaluate('()=>select("finding",0)');pg.get_by_role('button',name='Duplicar',exact=True).click();record('Duplicate starts unverified',pg.evaluate('S.data.findings[S.sel.idx].verification')=='unverified');saved(pg)
   # Effective 200% CSS zoom with all four primary tasks still reachable.
   pg.evaluate('()=>{document.documentElement.style.zoom="2";select("home")}');dims=pg.evaluate('()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,visible:[...document.querySelectorAll(".studio-nav button")].every(e=>e.getBoundingClientRect().right<=innerWidth+1)})');record('200 percent zoom navigation visible',dims['visible'] and not dims['overflow'],dims);pg.evaluate('()=>document.documentElement.style.zoom=""')
   # Scale test: same photo is referenced, live preview remains enabled.
   for count in (100,500):
    data=deepcopy(source);template=data['findings'][0];data['findings']=[]
    for i in range(count):
     f=deepcopy(template);f.update(id=f'F{i+1}',uid=workflows.new_uid(),title=f'Finding {i+1}');f.pop('retests',None);data['findings'].append(f)
    directory=api.PROJECTS/('scale-'+str(count));import shutil;shutil.copytree(api.PROJECTS/slug,directory,ignore=shutil.ignore_patterns('.history','.transactions','engagement.yaml.bak'));dump_yaml(data,directory/'engagement.yaml')
    start=time.monotonic();pg.evaluate('(slug)=>loadProject(slug)','scale-'+str(count));ready(pg);pg.wait_for_function('()=>S.previewVisible');pg.evaluate('()=>select("findings")');pg.wait_for_function('(n)=>document.querySelector("#pdfPreview").contentDocument?.querySelectorAll(".finding").length===n',arg=count,timeout=60000);elapsed=time.monotonic()-start
    metrics.append({'findings':count,'load_and_board_seconds':round(elapsed,3),'preview_enabled':pg.evaluate('S.previewVisible')});record(f'Scale {count} findings retained',pg.evaluate('S.data.findings.length')==count)
   record('No page JavaScript errors',not errors,errors);record('No external app requests',not external,external);browser.close()
 finally:
  if 'export_queue' in api.app.extensions:api.app.extensions['export_queue'].close()
  server.close()
print(json.dumps({'checks':len(checks),'metrics':metrics},indent=2))
