#!/usr/bin/env python3
"""Persistent browser restart, unavailable storage and incompatible draft safety."""
from pathlib import Path
import sys,tempfile,threading,argparse,json
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'webapp')]
import app as api
import workflows
from wizard import dump_yaml
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);checks=[]
def check(name,value):
 checks.append(dict(name=name,passed=bool(value)));(out/'recovery.json').write_text(json.dumps(checks,indent=2));assert value,name
with tempfile.TemporaryDirectory(prefix='rg-restart-',ignore_cleanup_errors=True) as tmp:
 api.PROJECTS=Path(tmp)/'projects';d=api.PROJECTS/'restart';d.mkdir(parents=True)
 data=workflows.normalize({'meta':{'report_title':'Browser restart','theme':'serio','lang':'es'},'findings':[dict(id='F1',title='Synthetic',mode='vuln',severity='low',description_md='Stored',impact_md='Impact',remediation_md='Fix')]});dump_yaml(data,d/'engagement.yaml')
 server=api.create_local_server(0);threading.Thread(target=server.run,daemon=True).start();base=f'http://127.0.0.1:{server.effective_port}';profile=Path(tmp)/'browser-profile'
 try:
  with sync_playwright() as pw:
   context=pw.chromium.launch_persistent_context(str(profile),viewport={'width':1366,'height':900});pg=context.pages[0];pg.goto(base);pg.wait_for_function('()=>S.slug && !projectStore.loading && projectBusyCount===0')
   pg.route('**/api/projects/restart',lambda r:r.fulfill(status=503,json={'error':'Synthetic offline server'}) if r.request.method=='PUT' else r.continue_())
   pg.evaluate('()=>select("finding",0)');pg.locator('textarea[data-field="description_md"]').fill('BROWSER_RESTART_DRAFT_0200');pg.wait_for_function('()=>projectStore.lastError?.status===503 && projectStore.recoverableRevision===projectStore.revision');check('Draft acknowledged after IndexedDB commit',True);context.close()
   context=pw.chromium.launch_persistent_context(str(profile),viewport={'width':1366,'height':900});pg=context.pages[0];pg.goto(base);pg.get_by_role('button',name='Comparar y recuperar',exact=True).wait_for();check('Draft survives complete Chromium restart',True)
   with pg.expect_download() as dl:pg.get_by_role('button',name='Descargar copia',exact=True).click()
   downloaded=dl.value;downloaded.save_as(out/'emergency-draft.json');copy=json.loads((out/'emergency-draft.json').read_text());check('Emergency file preserves exact pending content',copy['data']['findings'][0]['description_md']=='BROWSER_RESTART_DRAFT_0200')
   pg.get_by_role('button',name='Comparar y recuperar',exact=True).click();pg.get_by_role('button',name='Aplicar selección y guardar',exact=True).click();pg.wait_for_function('()=>!document.querySelector("dialog[open]") && !projectStore.dirty && !projectStore.lastError');check('Recovered draft reaches disk without changing title',pg.evaluate('S.data.findings[0].description_md')=='BROWSER_RESTART_DRAFT_0200' and pg.evaluate('S.data.meta.report_title')=='Browser restart')
   check('Successful recovery retires both browser copies after commit',pg.evaluate('async()=> (await projectStore.journal.list(S.slug)).length')==0)
   # Inject an unsupported draft version into the journal, then use ordinary UI.
   pg.evaluate('async()=>{await projectStore.journal.run("readwrite",s=>s.put({id:"future-format",format:"report-gen-draft",version:999,slug:S.slug,updated:Date.now(),data:S.data,base:S.data}));}')
   pg.reload();pg.get_by_role('button',name='Comparar y recuperar',exact=True).click();check('Unsupported draft cannot replace the project',pg.locator('dialog').count()==1 and pg.evaluate('projectStore.dirty') is False);pg.get_by_role('button',name='Cerrar',exact=True).click();pg.evaluate('async()=>projectStore.journal.remove("future-format")')
   pg.route('**/api/projects/restart',lambda r:r.fulfill(status=503,json={'error':'Synthetic offline server'}) if r.request.method=='PUT' else r.continue_());pg.evaluate('()=>{projectStore.journal.put=async()=>{throw new DOMException("Quota exceeded","QuotaExceededError")};select("finding",0)}');pg.locator('textarea[data-field="description_md"]').fill('ONLY_IN_MEMORY_0200');pg.wait_for_function('()=>projectStore.draftError && projectStore.lastError');check('Failed browser storage is never labelled recoverable',pg.evaluate('projectStore.recoverableRevision')==0 and 'solo en esta pestaña' in pg.locator('#draftStatus').inner_text());check('Emergency download remains available',pg.get_by_role('button',name='Descargar borrador',exact=True).is_enabled());pg.screenshot(path=str(out/'draft-storage-unavailable.png'));context.close()
 finally:
  if 'export_queue' in api.app.extensions:api.app.extensions['export_queue'].close()
  server.close()
print(json.dumps({'checks':len(checks)},indent=2))
