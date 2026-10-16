/* Horizonte catalog and recovery acceptance. Real UI and OS-write fault hook.
 * Every project lives in a disposable test-only workspace; no report is generated here.
 */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process'),{createHash}=require('node:crypto'),{isDeepStrictEqual}=require('node:util');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2);
const opt=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const out=path.resolve(opt('--output','out/horizonte-recovery')),slug=opt('--slug','horizonte-recovery');
const bundle=opt('--bundle'),projectDir=opt('--project-dir'),engine=opt('--browser','chromium');
const python=process.env.RG_PYTHON||'python3';
const playwright=require(require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
assert.ok(bundle&&fs.statSync(bundle).isFile(),'--bundle must identify the native Horizonte project backup');
assert.ok(/^[a-z0-9][a-z0-9_-]*$/.test(slug),'Use a safe disposable project slug');
assert.ok(['chromium','firefox','webkit'].includes(engine),'Use chromium, firefox or webkit');
fs.mkdirSync(out,{recursive:true});
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-horizonte-recovery-'));
fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const hash=buffer=>createHash('sha256').update(buffer).digest('hex');
const sourcePaths=['scripts/audit-horizonte-recovery.cjs','scripts/browser-server-0211.py','storage.py','project_history.py','project_catalog.py','webapp/app.py','webapp/static/app.js','webapp/static/workspace.js','webapp/static/studio.js','webapp/static/drafts.js','webapp/static/save-manager.js'];
const sourceHashes=()=>Object.fromEntries(sourcePaths.map(name=>[name,hash(fs.readFileSync(path.join(root,name)))]));
const results={schema:'report-gen-horizonte-recovery/1',complete:false,started:new Date().toISOString(),engine,
  input:{bundle:path.resolve(bundle),sha256:hash(fs.readFileSync(bundle))},sourceStart:sourceHashes(),
  checks:[],screens:[],downloads:[],expectedApiErrors:[],unexpectedApiErrors:[],pageErrors:[],externalRequests:[],coverage:[],
  limits:['Catalog fixture preparation uses real APIs; catalog filtering, sorting, edits, retries and recovery use visible UI controls.',
    'ENOSPC is injected into the actual atomic OS replace call by the existing test-only server, never by a mocked HTTP response.',
    'Screenshots and DOM assertions record automated browser acceptance, not human visual approval.']};
if(projectDir)results.input.source_yaml_sha256=hash(fs.readFileSync(path.join(projectDir,'engagement.yaml')));
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2)+'\n');
function check(name,passed,detail){results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name+': '+JSON.stringify(detail));console.log('PASS '+name);}
const clean=page=>page.waitForFunction(()=>typeof S!=='undefined'&&!projectStore.loading&&!projectBusyCount&&!projectStore.dirty&&!projectStore.saving&&!projectStore.lastError&&!document.querySelector('#splash'),null,{timeout:60000});
const ready=page=>page.waitForFunction(()=>typeof S!=='undefined'&&S.slug&&!projectStore.loading&&!projectBusyCount&&!document.querySelector('#splash'),null,{timeout:60000});
const data=page=>page.evaluate(()=>JSON.parse(JSON.stringify(S.data)));
const diskBytes=()=>fs.readFileSync(path.join(workspace,'projects',slug,'engagement.yaml'));
async function api(page,method,uri,body){return page.evaluate(async({method,uri,body})=>{
  const response=await appFetch(uri,{method,...(body===undefined?{}:{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)})});
  return {status:response.status,data:await response.json()};
},{method,uri,body});}
async function savedData(page){const value=await api(page,'GET','/api/projects/'+slug);assert.equal(value.status,200);return value.data;}
async function expose(page,selector){const target=page.locator(selector).first();
  const ancestors=await target.evaluate(el=>{let parent=el.parentElement?.closest('details'),ids=[];while(parent){if(!parent.open)ids.unshift(parent.id||null);parent=parent.parentElement?.closest('details');}return ids;});
  for(const id of ancestors){assert.ok(id,'Disclosure ancestor has a stable ID');await page.locator('#'+id+' > summary').click();}return target;
}
async function click(page,selector){await(await expose(page,selector)).click();}
async function closeMore(page){
  const menu=page.locator('#studioMore');
  if(await menu.getAttribute('open')!==null)await page.locator('#studioMore > summary').click();
  assert.equal(await menu.getAttribute('open'),null,'The visible More control closes its overlay');
}
async function screen(page,name){await page.evaluate(async()=>{await document.fonts.ready;window.scrollTo(0,0);});
  const file=path.join(out,name+'.png');await page.screenshot({path:file,fullPage:false});
  results.screens.push({name,path:file,sha256:hash(fs.readFileSync(file)),viewport:page.viewportSize()});save();
}
async function editImpact(page,value){
  // Overview hides the findings sidebar; leave it using the visible report control.
  await click(page,'#navReport');await click(page,'#findingList .finding-nav');
  await page.locator('[data-field="impact_md"]').fill(value);
}
async function reloadBank(page){
  await page.reload();await ready(page);
  // Startup may choose an auxiliary catalog project. Open the intended bank
  // through its visible selector before checking that project's private drafts.
  if(await page.evaluate(()=>S.slug)!==slug)await(await expose(page,'#projectSelect')).selectOption(slug);
  await page.waitForFunction(slug=>S.slug===slug&&!projectStore.loading&&!projectBusyCount,slug,{timeout:60000});
}
async function importBundle(page){page.once('dialog',dialog=>dialog.accept(slug));const choice=page.waitForEvent('filechooser');
  await click(page,'#importProjectBtn');await(await choice).setFiles(bundle);
  await page.waitForFunction(slug=>S.slug===slug&&!projectStore.loading&&!projectBusyCount,slug,{timeout:60000});await clean(page);await closeMore(page);
}
async function cardSlugs(page){return page.locator('[data-project-catalog] [data-project-slug]').evaluateAll(nodes=>nodes.map(node=>node.dataset.projectSlug));}
async function catalog(page){
  // Only auxiliary catalog records use API preparation. The banking project is untouched.
  const fixture=await page.evaluate(async()=>{
    const seeded=[];
    for(let index=0;index<10;index++){
      const slug='horizonte-catalog-'+index;
      await requireOk(await api.post('/api/projects',{slug,title:index===0?'Informe Águila':'Catálogo '+index,client:index%2?'Zeta':'Alfa'}));
      if(index===0){
        const current=await requireOk(await appFetch('/api/projects/'+slug)),value=await current.json();
        value.findings=[{uid:WorkflowUI.uid(),id:'F1',title:'Retest sintético del catálogo',status:'reported_fixed',due_date:'2020-01-01'}];
        await requireOk(await appFetch('/api/projects/'+slug,{method:'PUT',headers:{'Content-Type':'application/json','If-Match':current.headers.get('ETag')},body:JSON.stringify(value)}));
      }
      seeded.push(slug);
    }
    await refreshProjects();return seeded;
  });
  check('Catalog fixture creates exactly ten auxiliary reports through real APIs',fixture.length===10);
  await click(page,'#navHome');
  await page.waitForFunction(()=>document.querySelector('[data-catalog-count]')?.textContent==='11 proyectos encontrados');
  const catalog=page.locator('[data-project-catalog]');
  const first=await cardSlugs(page);check('Catalog paginates the bank and ten auxiliary reports into eight cards',first.length===8);
  await catalog.getByRole('button',{name:'Siguiente',exact:true}).click();const second=await cardSlugs(page);
  check('Second catalog page contains the three remaining unique projects',second.length===3&&new Set([...first,...second]).size===11);
  await page.locator('[data-catalog-search]').fill('aguila');
  check('Accent-insensitive title search resets pagination',isDeepStrictEqual(await cardSlugs(page),['horizonte-catalog-0']));
  await page.locator('[data-catalog-search]').fill('Zeta');const zeta=await cardSlugs(page);
  check('Client search identifies exactly five Zeta reports',zeta.length===5&&zeta.every(value=>/^horizonte-catalog-[13579]$/.test(value)));
  await page.locator('[data-catalog-search]').fill(slug);
  check('Exact banking slug search finds only the imported project',isDeepStrictEqual(await cardSlugs(page),[slug]));
  await page.locator('[data-catalog-search]').fill('');await page.locator('[data-catalog-status]').selectOption('archived');
  check('Archived filter returns no active projects',await catalog.locator('[data-project-slug]').count()===0&&await page.locator('[data-catalog-count]').textContent()==='0 proyectos encontrados');
  const all=(await api(page,'GET','/api/projects')).data;
  await page.locator('[data-catalog-status]').selectOption('retest');const pending=await cardSlugs(page);
  const expected=all.filter(row=>!row.archived&&row.pending_retests>0).map(row=>row.slug).sort();
  check('Retest filter includes every project with a reported fix awaiting verification',expected.includes('horizonte-catalog-0')&&isDeepStrictEqual([...pending].sort(),expected),{expected,pending});
  await screen(page,'catalog-pending-retest');
  await page.locator('[data-catalog-status]').selectOption('all');await page.locator('[data-catalog-order]').selectOption('deadline');
  check('Nearest-date order places the overdue synthetic deadline first',(await cardSlugs(page))[0]==='horizonte-catalog-0');
  await page.locator('[data-catalog-order]').selectOption('client');const byClient=await cardSlugs(page),lookup=new Map(all.map(row=>[row.slug,row]));
  check('Client order places all five Alfa reports before Banco Horizonte and Zeta',byClient.slice(0,5).every(value=>lookup.get(value).client==='Alfa')&&byClient[5]===slug&&byClient.slice(6).every(value=>lookup.get(value).client==='Zeta'));
  await screen(page,'catalog-client-order');
  await page.locator('[data-catalog-order]').selectOption('retest');const counts=(await cardSlugs(page)).map(value=>lookup.get(value).pending_retests);
  check('Retest count order is descending and retains a pending report first',counts[0]>0&&counts.every((value,index)=>index===0||counts[index-1]>=value));
  await page.locator('[data-catalog-order]').selectOption('modified');const modified=(await cardSlugs(page)).map(value=>lookup.get(value).modified_at);
  check('Last-modified order is descending',modified.every((value,index)=>index===0||modified[index-1]>=value));
  results.coverage.push({area:'Project catalog',mode:'UI plus API fixture preparation',details:'11 reports, 8/3 pagination, title/client/slug search, archived and retest filters, and all four sort choices.'});save();
}
let server,browser,page,timer,base,faultMode=null;
const faultRequests=new WeakSet();
async function fault(mode){const response=await api(page,'POST','/api/__test__/fault',{mode,slug});check('Native storage fault '+(mode||'cleared'),response.status===200);faultMode=mode;}
async function failedEdit(expected,previousBytes,label){
  await editImpact(page,expected.findings[0].impact_md);
  await page.getByRole('button',{name:'Reintentar guardado',exact:true}).waitFor();
  await page.waitForFunction(()=>projectStore.dirty&&projectStore.lastError?.status===503&&projectStore.recoverableRevision===projectStore.revision,null,{timeout:60000});
  check(label+': actual failed atomic write preserves the entire saved YAML byte for byte',diskBytes().equals(previousBytes),{before_sha256:hash(previousBytes),after_sha256:hash(diskBytes())});
  check(label+': every in-memory field remains intact in a recoverable draft',isDeepStrictEqual(await data(page),expected));
  check(label+': IndexedDB has persisted the exact current draft revision',await page.evaluate(()=>projectStore.recoverableRevision===projectStore.revision&&projectStore.dirty&&projectStore.lastError.status===503));
}
(async()=>{try{
  save();server=spawn(python,[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:process.env});
  server.stderr.on('data',part=>fs.appendFileSync(path.join(out,'server.log'),part));
  base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server startup timeout')),60000);
    server.stdout.on('data',part=>{text+=part;for(const line of text.split('\n'))try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});
    server.once('error',reject);server.once('exit',code=>reject(Error('Server exited '+code)));
  });
  const executable=opt('--executable',engine==='chromium'?(process.env.RG_CHROMIUM_EXECUTABLE||process.env.REPORT_GEN_CHROMIUM):undefined);
  browser=await playwright[engine].launch({headless:true,...(executable?{executablePath:executable}:{})});results.browser=browser.version();
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
  await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&new URL(url).origin!==base){results.externalRequests.push(url);save();return route.abort();}return route.continue();});
  await context.addInitScript(()=>{localStorage.setItem('rg.uiLang','es');localStorage.setItem('rg.previewVisible','0');});
  page=await context.newPage();page.on('pageerror',error=>{results.pageErrors.push(String(error));save();});
  page.on('request',request=>{if(faultMode==='disk_full'&&request.method()==='PUT'&&new URL(request.url()).pathname==='/api/projects/'+slug)faultRequests.add(request);});
  page.on('response',response=>{if(response.status()<400||!new URL(response.url()).pathname.startsWith('/api/'))return;
    const record={method:response.request().method(),path:new URL(response.url()).pathname,status:response.status()};
    (response.status()===503&&faultRequests.has(response.request())?results.expectedApiErrors:results.unexpectedApiErrors).push(record);save();
  });
  await page.goto(base);await clean(page);await importBundle(page);const original=await data(page),originalBytes=diskBytes();
  page.on('dialog',dialog=>dialog.type()==='beforeunload'?dialog.accept():dialog.dismiss());
  check('Native import loads the full banking case',original.findings.length>=27&&original.assets.length>=12&&original.evidence.length>=24);
  if(projectDir){const expected=JSON.parse(execFileSync(python,['-c','import json,sys,yaml;print(json.dumps(yaml.safe_load(open(sys.argv[1]))))',path.join(projectDir,'engagement.yaml')],{encoding:'utf8',maxBuffer:8*1024*1024}));
    check('Native import exactly matches the frozen authored banking project',isDeepStrictEqual(original,expected));}
  await catalog(page);
  check('Catalog navigation and auxiliary fixtures preserve banking YAML bytes',diskBytes().equals(originalBytes));
  check('Catalog navigation preserves every banking field',isDeepStrictEqual(await savedData(page),original));

  const retry=structuredClone(original);retry.findings[0].impact_md+='\n\nHORIZONTE-RECOVERY: edición sintética conservada tras ENOSPC y reintento.';
  await fault('disk_full');await failedEdit(retry,originalBytes,'Retry cycle');await closeMore(page);await screen(page,'storage-enospc-recoverable');
  await fault(null);await closeMore(page);
  check('Visible retry has an unobstructed pointer target after closing More',await page.getByRole('button',{name:'Reintentar guardado',exact:true}).evaluate(button=>{
    const rect=button.getBoundingClientRect(),target=document.elementFromPoint(rect.x+rect.width/2,rect.y+rect.height/2);
    return !button.disabled&&(target===button||button.contains(target));
  }));
  await page.getByRole('button',{name:'Reintentar guardado',exact:true}).click();await clean(page);
  check('Visible retry saves the full edited report without unrelated changes',isDeepStrictEqual(await savedData(page),retry)&&isDeepStrictEqual(await data(page),retry));
  const retryBytes=diskBytes();check('Successful retry advances the saved bytes',!retryBytes.equals(originalBytes));await screen(page,'storage-retry-saved');

  const recovered=structuredClone(retry);recovered.findings[0].impact_md+='\n\nHORIZONTE-RECOVERY: edición sintética recuperada tras recargar el navegador.';
  await fault('disk_full');await failedEdit(recovered,retryBytes,'Reload recovery cycle');
  const downloading=page.waitForEvent('download');await click(page,'#draftExportBtn');const download=await downloading;
  const draftPath=path.join(out,'horizonte-private-recovery.report-gen-draft.json');await download.saveAs(draftPath);await closeMore(page);
  const draft=JSON.parse(fs.readFileSync(draftPath,'utf8'));
  check('Native emergency draft download contains every unsaved field and its exact saved base',await download.failure()===null&&draft.format==='report-gen-draft'&&draft.version===1&&draft.slug===slug&&isDeepStrictEqual(draft.data,recovered)&&isDeepStrictEqual(draft.base,retry));
  results.downloads.push({name:path.basename(draftPath),private:true,size:fs.statSync(draftPath).size,sha256:hash(fs.readFileSync(draftPath))});save();
  await reloadBank(page);
  const recoveryDialog=page.getByRole('dialog',{name:'Hay borradores recuperables',exact:true});await recoveryDialog.waitFor();
  check('Reload leaves saved YAML untouched until explicit recovery',diskBytes().equals(retryBytes)&&isDeepStrictEqual(await savedData(page),retry));
  const rows=await page.evaluate(()=>projectStore.recovery.map(row=>({slug:row.slug,data:row.data,base:row.base})));
  check('Reload discovers the exact bank draft in real browser storage',rows.some(row=>row.slug===slug&&isDeepStrictEqual(row.data,recovered)&&isDeepStrictEqual(row.base,retry)));
  await screen(page,'draft-found-after-reload');await fault(null);
  await recoveryDialog.getByRole('button',{name:'Comparar y recuperar',exact:true}).first().click();
  const merge=page.getByRole('dialog',{name:'Recuperar y resolver cambios',exact:true});await merge.waitFor();
  check('Recovery comparison does not silently alter the saved report',diskBytes().equals(retryBytes)&&await merge.getByText('No hay campos en conflicto.',{exact:true}).count()===1);
  await screen(page,'draft-comparison-before-apply');await merge.getByRole('button',{name:'Aplicar selección y guardar',exact:true}).click();
  await merge.waitFor({state:'hidden'});await clean(page);
  check('Explicit recovery saves every draft field and retains every other project field',isDeepStrictEqual(await savedData(page),recovered)&&isDeepStrictEqual(await data(page),recovered));
  check('Applied draft is removed from the recovery queue',await page.evaluate(()=>projectStore.recovery.length===0));
  await reloadBank(page);await clean(page);
  check('Recovered report survives a second real browser reload',isDeepStrictEqual(await savedData(page),recovered)&&isDeepStrictEqual(await data(page),recovered));
  check('Successful recovery does not offer a stale draft on the second reload',await page.getByRole('dialog',{name:'Hay borradores recuperables',exact:true}).count()===0);
  await screen(page,'draft-recovered-and-persisted');
  await editImpact(page,original.findings[0].impact_md);await clean(page);
  check('Reversible exercise restores the entire original authored banking report',isDeepStrictEqual(await savedData(page),original)&&isDeepStrictEqual(await data(page),original));
  results.coverage.push({area:'Storage failure and retry',mode:'UI with real test-server ENOSPC hook',details:'HTTP503 from atomic OS replace; original YAML bytes retained; IndexedDB draft protected; visible retry saves the full intended project.'},
    {area:'Browser draft recovery',mode:'UI',details:'Private emergency download, actual reload, IndexedDB recovery discovery, explicit comparison and apply, second reload, and restoration of all original authored fields.'});
  check('Both actual ENOSPC writes are observed as expected HTTP503 errors',results.expectedApiErrors.length===2,results.expectedApiErrors);
  check('No unexpected API errors, page exceptions or external requests occur',results.unexpectedApiErrors.length===0&&results.pageErrors.length===0&&results.externalRequests.length===0,{api:results.unexpectedApiErrors,page:results.pageErrors,external:results.externalRequests});
  results.sourceEnd=sourceHashes();check('Acceptance runner and recorded production sources remain unchanged during the run',isDeepStrictEqual(results.sourceStart,results.sourceEnd));
  check('Native input ZIP is unchanged',results.input.sha256===hash(fs.readFileSync(bundle)));
  if(projectDir)check('Frozen case source remains unchanged',results.input.source_yaml_sha256===hash(fs.readFileSync(path.join(projectDir,'engagement.yaml'))));
  results.complete=true;results.finished=new Date().toISOString();save();
}catch(error){results.error=String(error.stack||error);save();if(page)await screen(page,'failure').catch(()=>{});console.error(error);process.exitCode=1;
}finally{
  clearTimeout(timer);await browser?.close().catch(()=>{});
  if(server&&server.exitCode===null){server.kill('SIGTERM');await new Promise(resolve=>{const stop=setTimeout(resolve,3000);server.once('exit',()=>{clearTimeout(stop);resolve();});});}
  if(fs.existsSync(path.join(workspace,'.test-only'))&&fs.readFileSync(path.join(workspace,'.test-only'),'utf8')==='synthetic acceptance workspace')fs.rmSync(workspace,{recursive:true,force:true});
  save();
}})();
