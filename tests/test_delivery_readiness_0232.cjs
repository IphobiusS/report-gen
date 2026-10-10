/* R06 saved preparation facts, privacy, keyboard and stale snapshot negatives. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const root=path.resolve(option('--tool',process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'))),out=path.resolve(option('--output','out/delivery-readiness-0232'));
const {chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
fs.mkdirSync(out,{recursive:true});const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-readiness-'));fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const results={checks:[],pageErrors:[],externalRequests:[]},save=()=>fs.writeFileSync(out+'/results.json',JSON.stringify(results,null,2));
const check=(name,passed,detail)=>{results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name);console.log('PASS '+name);};
const server=spawn(process.env.RG_PYTHON||'python',[root+'/scripts/browser-server-0211.py','--workspace',workspace],{cwd:root,env:{...process.env,PYTHONPATH:root}});server.stderr.on('data',b=>fs.appendFileSync(out+'/server.log',b));let browser,timer;
(async()=>{try{
 const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server timeout')),20000);server.stdout.on('data',b=>{text+=b;for(const line of text.split('\n'))try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});server.on('exit',code=>reject(Error('Server exited '+code)));});
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']});results.browser=browser.version();
 const context=await browser.newContext({viewport:{width:1366,height:1000},reducedMotion:'reduce'});await context.route('**/*',r=>{const url=r.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){results.externalRequests.push(url);return r.abort();}return r.continue();});
 const page=await context.newPage();page.on('pageerror',error=>{results.pageErrors.push(String(error));save();});page.on('dialog',dialog=>dialog.accept());let writes=0,jobs=0;page.on('request',request=>{if(request.method()==='PUT'&&/\/api\/projects\/[^/]+$/.test(request.url()))writes++;if(request.method()==='POST'&&request.url().endsWith('/jobs'))jobs++;});
 await page.goto(base);await page.waitForFunction(()=>typeof ExperienceUI!=='undefined'&&!document.getElementById('splash'));
 await page.evaluate(async()=>{await requireOk(await api.post('/api/projects',{slug:'readiness-fixture',title:'Synthetic delivery readiness',client:'Synthetic entity'}));await refreshProjects();await loadProject('readiness-fixture');S.data.findings=[{id:'F01',uid:WorkflowUI.uid(),mode:'vuln',title:'Synthetic finding',severity:'low',description_md:'password=R06_BROWSER_SYNTHETIC_12345',impact_md:'Synthetic impact.',remediation_md:'Validate authorization.',walkthrough:[{command:'printf synthetic_proof'}],proof:[{name:'Observed output',value:'Synthetic output.'}]}];S.data.finding_sequence=1;scheduleSave();await doSave();});
 await page.waitForFunction(()=>!projectStore.dirty);const before=await page.evaluate(()=>({data:JSON.stringify(S.data),etag:projectStore.etag})),beforeWrites=writes;
 await page.locator('[data-studio-nav="deliver"]').click();await page.waitForFunction(()=>document.querySelector('[data-delivery-readiness]')?.dataset.readinessCurrent==='true');
 check('Deliver shows five preparation checks from the saved revision',await page.locator('[data-readiness-check]').count()===5&&await page.evaluate(()=>$('[data-delivery-readiness]').dataset.readinessRevision===projectStore.etag));
 check('Navigating to Deliver reads without writes or author data changes',writes===beforeWrites&&await page.evaluate(before=>JSON.stringify(S.data)===before.data&&projectStore.etag===before.etag,before));
 check('Secret summary reports an unresolved outgoing match without echoing its value',await page.locator('[data-readiness-check="secrets"]').getAttribute('data-readiness-status')==='attention'&&(await page.locator('[data-readiness-check="secrets"]').innerText()).includes('1 coincidencias')&&!(await page.locator('[data-delivery-readiness]').innerText()).includes('R06_BROWSER_SYNTHETIC'));
 check('Human review always remains required and does not imply technical approval',await page.locator('[data-readiness-check="human_review"]').getAttribute('data-readiness-status')==='manual'&&(await page.locator('[data-readiness-check="human_review"]').innerText()).includes('no valida técnicamente'));
 await page.evaluate(()=>{S.data.findings[0].impact_md='Newer local synthetic draft.';scheduleSave();projectStore.timers.clearTimeout(projectStore.timer);projectStore.timer=null;});
 await page.waitForFunction(()=>document.querySelector('[data-delivery-readiness]')?.dataset.readinessCurrent==='false');
 check('Editing invalidates previously checked preparation before autosave',await page.locator('[data-readiness-check]').count()===0&&(await page.locator('[data-delivery-readiness]').innerText()).includes('otra revisión'));
 await page.getByRole('button',{name:'Guardar y volver a comprobar',exact:true}).focus();await page.keyboard.press('Space');await page.waitForFunction(()=>!projectStore.dirty&&document.querySelector('[data-delivery-readiness]')?.dataset.readinessCurrent==='true');
 check('Native keyboard refresh saves intentionally and recomputes the current revision',writes>beforeWrites&&await page.evaluate(()=>S.data.findings[0].impact_md==='Newer local synthetic draft.'&&$('[data-delivery-readiness]').dataset.readinessRevision===projectStore.etag));
 // A response from a newer disk version must not be accepted against the
 // editor's older ETag, even when its JSON content looks structurally valid.
 const reviewPattern=base+'/api/projects/readiness-fixture/review?lang=es';
 await context.route(reviewPattern,async route=>{const response=await route.fetch();const report=await response.json();report.revision='f'.repeat(64);await route.fulfill({response,json:report});});
 await page.getByRole('button',{name:'Elegir formatos',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.toast')?.textContent.includes('cambió durante'));
 check('Review ETag mismatch refuses the preparation dialog and export queue',await page.locator('dialog[open]').count()===0&&jobs===0);await context.unroute(reviewPattern);
 await page.getByRole('button',{name:'Elegir formatos',exact:true}).click();const dialog=page.locator('dialog[open]');await dialog.waitFor();
 check('Preparation dialog carries the same five scoped facts',await dialog.locator('[data-readiness-check]').count()===5&&await dialog.locator('[data-readiness-check="human_review"]').getAttribute('data-readiness-status')==='manual');
 await page.evaluate(()=>{S.data.findings[0].description_md='Changed synthetic draft during preparation.';scheduleSave();projectStore.timers.clearTimeout(projectStore.timer);projectStore.timer=null;});
 await dialog.getByRole('button',{name:'Generar paquete',exact:true}).click();
 check('A draft edited after preparation cannot enqueue the reviewed snapshot',jobs===0&&(await dialog.innerText()).includes('El proyecto cambió'));
 await dialog.getByRole('button',{name:'Cerrar',exact:true}).click();await page.getByRole('button',{name:'Guardar y volver a comprobar',exact:true}).click();await page.waitForFunction(()=>document.querySelector('[data-delivery-readiness]')?.dataset.readinessCurrent==='true');
 await page.evaluate(()=>setUiLang('en'));await page.waitForFunction(()=>document.querySelector('[data-delivery-readiness]')?.dataset.readinessCurrent==='true');
 check('English preparation uses localized server and interface text',await page.locator('[data-readiness-check="human_review"] strong').innerText()==='Human review · Manual review required'&&(await page.locator('[data-readiness-check="secrets"]').innerText()).includes('Patterns can miss secrets'));
 await page.waitForFunction(()=>!document.querySelector('.toast'),null,{timeout:10000});await page.screenshot({path:out+'/delivery-desktop.png',fullPage:true});
 await page.setViewportSize({width:390,height:844});await page.screenshot({path:out+'/delivery-mobile.png',fullPage:true});
 check('Delivery checklist reflows in a narrow viewport',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth&&[...document.querySelectorAll('[data-delivery-readiness] li')].every(el=>el.getBoundingClientRect().right<=innerWidth+1)));
 // Late response after switching projects cannot paint preparation for A on B.
 await page.evaluate(()=>setUiLang('es'));await page.waitForFunction(()=>document.querySelector('[data-delivery-readiness]')?.dataset.readinessCurrent==='true');
 let release,received=false;const pending=new Promise(resolve=>release=resolve);await context.route(reviewPattern,async route=>{received=true;await pending;await route.continue();});
 const click=page.getByRole('button',{name:'Elegir formatos',exact:true}).click();await page.waitForFunction(()=>true);for(let n=0;!received&&n<100;n++)await page.waitForTimeout(20);assert.ok(received,'Delayed review request received');
 await page.evaluate(async()=>{await requireOk(await api.post('/api/projects',{slug:'readiness-other',title:'Other synthetic report'}));await refreshProjects();await loadProject('readiness-other');select('home');});release();await click;await context.unroute(reviewPattern);await page.waitForTimeout(100);
 check('A delayed review from the previous project cannot open a delivery dialog',await page.locator('dialog[open]').count()===0&&await page.evaluate(()=>S.slug==='readiness-other'));
 check('No browser errors or external requests',results.pageErrors.length===0&&results.externalRequests.length===0,{pageErrors:results.pageErrors,external:results.externalRequests});save();
 }finally{clearTimeout(timer);await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{results.error=String(error.stack||error);save();console.error(error);process.exitCode=1;});
