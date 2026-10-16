/* Real local browser acceptance against a disposable Ladera project copy. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),opt=(n,d)=>args.includes(n)?args[args.indexOf(n)+1]:d;
const out=path.resolve(opt('--output','out/browser-0212')),fixture=path.resolve(opt('--project-zip',''));
if(!fs.statSync(fixture).isFile())throw Error('--project-zip is required');
const {chromium}=require(require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
fs.mkdirSync(out,{recursive:true});const checks=[],errors=[],screens=[],external=[];let browser,page,server,base,slug='ladera-prueba';
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({version:'0.21.2',browser:browser?.version(),checks,errors,screens,external},null,2));
const check=(name,passed,detail)=>{checks.push({name,passed:!!passed,detail});save();assert.ok(passed,name);console.log('PASS '+name);};
async function ready(){await page.waitForFunction(()=>S.slug&&!projectStore.loading&&projectBusyCount===0);}
async function saved(){await page.waitForFunction(()=>!projectStore.dirty&&!projectStore.saving&&!projectStore.lastError);}
async function more(){if(await page.locator('#studioMore').getAttribute('open')===null)await page.locator('#studioMore>summary').click();}
async function closeMore(){if(await page.locator('#studioMore').getAttribute('open')!==null)await page.locator('#studioMore>summary').click();}
async function shot(name,p=page){await p.screenshot({path:path.join(out,name+'.png'),fullPage:false});screens.push({file:name+'.png',url:p.url(),viewport:p.viewportSize(),time:new Date().toISOString()});save();}
async function importProject(first=false){
 if(!first){await more();if(await page.locator('#projectActions').getAttribute('open')===null)await page.locator('#projectActions>summary').click();}
 page.once('dialog',d=>d.accept(slug));const chooser=page.waitForEvent('filechooser');
 await (first?page.getByRole('button',{name:'Abrir respaldo de proyecto',exact:true}):page.locator('#importProjectBtn')).click();
 await (await chooser).setFiles(fixture);await page.waitForFunction(s=>S.slug===s&&!projectStore.loading&&projectBusyCount===0,slug);await closeMore();
}
async function selectFinding(id){
 const title=await page.evaluate(id=>S.data.findings.find(f=>f.id===id).title,id);
 await page.locator('#globalSearch').fill(title);await page.locator('.search-item').filter({hasText:title}).waitFor();await page.locator('.search-item').filter({hasText:title}).click();
 await page.waitForFunction(id=>S.sel.type==='finding'&&S.data.findings[S.sel.idx].id===id,id);
}
async function api(uri){return page.evaluate(async u=>{const r=await appFetch(u);if(!r.ok)throw Error(await r.text());return await r.json();},uri);}
async function waitJob(id){for(let i=0;i<600;i++){const j=(await api('/api/jobs')).find(j=>j.id===id);if(j&&['done','error','cancelled'].includes(j.stage))return j;await new Promise(r=>setTimeout(r,300));}throw Error('Job timeout');}
async function exportOne(fmt,dest){
 await more();if(await page.locator('#exportMenu').getAttribute('open')===null)await page.locator('#exportMenu>summary').click();await page.locator('#exportFormat').selectOption(fmt);
 const res=page.waitForResponse(r=>r.url().endsWith('/'+slug+'/jobs')&&r.request().method()==='POST');await page.locator('#downloadBtn').click();const r=await res;const sub=await r.json();check('Solicitud '+slug+' '+fmt,r.status()===202,sub);
 const job=await waitJob(sub.id);check('Exportación '+slug+' '+fmt,job.stage==='done',job);
 const row=page.locator('[data-job="'+job.id+'"]');await row.getByRole('button',{name:'Descargar',exact:true}).waitFor();const dl=page.waitForEvent('download');await row.getByRole('button',{name:'Descargar',exact:true}).click();await(await dl).saveAs(path.join(out,dest));
 const verification=await api('/api/jobs/'+job.id+'/verification');fs.writeFileSync(path.join(out,dest+'.verification.json'),JSON.stringify(verification,null,2));
 await row.getByRole('button',{name:'Ver comprobaciones',exact:true}).click();const dialog=page.getByRole('dialog',{name:'Comprobaciones de la exportación',exact:true});await dialog.waitFor();
 check('Revisión visual explícita '+fmt,(await dialog.innerText()).includes('Revisión manual requerida'));
 if(fmt==='html'&&slug==='ladera-final')await shot('03-comprobaciones-html');
 await dialog.getByRole('button',{name:'Cerrar',exact:true}).click();
 const jobs=page.getByRole('dialog').filter({has:page.locator('[data-job="'+job.id+'"]')});if(await jobs.count())await jobs.getByRole('button',{name:'Cerrar',exact:true}).click();await closeMore();return job;
}
(async()=>{
 server=spawn(process.env.RG_PYTHON||'python3',[path.join(root,'scripts/browser-server-0212.py')],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});server.stderr.pipe(fs.createWriteStream(path.join(out,'server.log')));
 const info=await new Promise((resolve,reject)=>{let s='';const timer=setTimeout(()=>reject(Error('Server timeout')),20000);server.stdout.on('data',b=>{s+=b;if(s.includes('\n')){clearTimeout(timer);resolve(JSON.parse(s.split('\n')[0]));}});server.once('exit',c=>reject(Error('Server exit '+c)));});base=info.url;
 browser=await chromium.launch({headless:true,...(process.env.RG_CHROMIUM_EXECUTABLE?{executablePath:process.env.RG_CHROMIUM_EXECUTABLE}:{})});const context=await browser.newContext({viewport:{width:1512,height:1100},acceptDownloads:true,reducedMotion:'reduce'});
 context.on('page',p=>p.on('pageerror',e=>errors.push(String(e))));await context.route('**/*',route=>{const u=route.request().url();if(/^https?:/.test(u)&&!u.startsWith(base+'/')){external.push(u);return route.abort();}return route.continue();});
 page=await context.newPage();await page.goto(base);await importProject(true);check('Importación completa',await page.evaluate(()=>S.data.findings.length===26&&S.data.assets.length===12));
 const identities=await page.evaluate(()=>Object.fromEntries(S.data.findings.map(f=>[f.id,f.uid])));
 await selectFinding('F02');const desc=await page.locator('[data-field="description_md"]').inputValue();await page.locator('[data-field="description_md"]').fill(desc+'\n\n[Referencia a redirección](#F10).');await saved();
 await selectFinding('F01');page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Eliminar hallazgo',exact:true}).click();await saved();
 check('Borrar F01 conserva F10 y máquinas',await page.evaluate(ids=>S.data.findings.find(f=>f.id==='F10').uid===ids.F10&&S.data.findings.find(f=>f.id==='M01').uid===ids.M01,identities));
 // Reorder via real drag/drop in the manual dashboard.
 await page.locator('#workspaceSidebar').getByRole('button',{name:'Hallazgos',exact:true}).click();await page.getByRole('button',{name:'Manual',exact:true}).click();
 const rows=page.locator('.dash-row');await rows.nth(0).locator('.drag').dragTo(rows.nth(2));await saved();
 check('Reordenar conserva IDs y UUIDs',await page.evaluate(ids=>S.data.findings.every(f=>ids[f.id]===f.uid),identities));
 await selectFinding('F02');await page.getByRole('button',{name:'Duplicar',exact:true}).click();await saved();
 check('Duplicar asigna ID nuevo sin renumerar',await page.evaluate(ids=>{const original=S.data.findings.filter(f=>ids[f.id]);return original.length===25&&original.every(f=>ids[f.id]===f.uid)&&new Set(S.data.findings.map(f=>f.id)).size===26;},identities));
 await exportOne('html','referencias-estables.html');
 const report=await context.newPage();await report.goto('file://'+path.join(out,'referencias-estables.html'));await report.locator('#F02 a[href="#F10"]').click();check('El enlace abre la ficha original',await report.locator('#F10 .f-title').innerText().then(t=>t.includes('Redirección de salida')));await shot('01-referencia-correcta',report);await report.close();
 await selectFinding('F10');page.once('dialog',d=>d.accept());await page.getByRole('button',{name:'Eliminar hallazgo',exact:true}).click();await saved();
 const blocked=await page.evaluate(async()=>{const r=await appFetch('/api/projects/'+S.slug+'/jobs',{method:'POST',headers:{'Content-Type':'application/json','If-Match':projectStore.etag},body:JSON.stringify({kind:'export',formats:['html'],label:'Referencia borrada',acknowledge_warnings:true})});return {status:r.status,text:await r.text()};});
 check('Destino eliminado bloquea exportación',blocked.status===422&&blocked.text.includes('sin destino'),blocked);
 await page.locator('#undoNotice').getByRole('button',{name:'Deshacer acción',exact:true}).click();await saved();check('Deshacer restaura la identidad original',await page.evaluate(ids=>S.data.findings.find(f=>f.id==='F10').uid===ids.F10,identities));
 // Fresh import guarantees the published long report has no mutation-test edits.
 slug='ladera-final';await importProject();await page.locator('#workspaceSidebar').getByRole('button',{name:'Hallazgos',exact:true}).click();await shot('02-hallazgos');
 for(const fmt of ['html','md','docx','pdf'])await exportOne(fmt,'informe.'+(fmt==='md'?'zip':fmt));
 await page.locator('[data-studio-nav="deliver"]').click();await page.getByRole('button',{name:'Elegir formatos',exact:true}).click();for(const fmt of ['html','md','docx','pdf'])await page.locator('[data-delivery-format="'+fmt+'"]').check();if(await page.locator('[data-delivery="ack"]').count())await page.locator('[data-delivery="ack"]').check();
 const sub=page.waitForResponse(r=>r.url().endsWith('/'+slug+'/jobs')&&r.request().method()==='POST');await page.getByRole('button',{name:'Generar paquete',exact:true}).click();const j=await(await sub).json();const job=await waitJob(j.id);check('Entrega conjunta',job.stage==='done',job);const dl=page.waitForEvent('download');await page.locator('[data-job="'+job.id+'"]').getByRole('button',{name:'Descargar',exact:true}).click();await(await dl).saveAs(path.join(out,'entrega-completa.zip'));
 await shot('04-entrega');const jd=page.getByRole('dialog').filter({has:page.locator('[data-job="'+job.id+'"]')});if(await jd.count())await jd.getByRole('button',{name:'Cerrar',exact:true}).click();
 await selectFinding('F01');await page.setViewportSize({width:390,height:844});await shot('05-editor-movil');check('Sin desbordamiento horizontal móvil',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 check('Sin errores JavaScript',errors.length===0,errors);check('Sin peticiones externas',external.length===0,external);
})().catch(async e=>{errors.push(e.stack||String(e));console.error(e);try{await shot('fallo');fs.writeFileSync(path.join(out,'fallo.html'),await page.content());}catch(_){}process.exitCode=1;}).finally(async()=>{await browser?.close();if(server?.exitCode===null){server.kill('SIGTERM');await new Promise(r=>{server.once('exit',r);setTimeout(r,3000);});}save();});
