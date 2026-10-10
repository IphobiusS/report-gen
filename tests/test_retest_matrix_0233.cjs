/* Portable Chromium acceptance of a read-only, stale-guarded retest matrix. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const root=path.resolve(option('--tool',process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'))),out=path.resolve(option('--output','out/retest-matrix-0233'));
const {chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
const axe=option('--axe',process.env.AXE_CORE_PATH);
fs.mkdirSync(out,{recursive:true});
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-matrix-'));fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const results={checks:[],pageErrors:[],externalRequests:[]},save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
function check(name,passed,detail){results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name);console.log('PASS '+name);}
const server=spawn(process.env.RG_PYTHON||'python',[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:{...process.env,PYTHONPATH:root+path.delimiter+path.join(root,'webapp')}});
server.stderr.on('data',value=>fs.appendFileSync(path.join(out,'server.log'),value));
let timer,browser,page;
(async()=>{try{
 const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server timeout')),20000);server.stdout.on('data',value=>{text+=value;for(const line of text.split('\n'))try{const parsed=JSON.parse(line);if(parsed.url){clearTimeout(timer);resolve(parsed.url);}}catch{}});server.on('exit',code=>reject(Error('Server exited '+code)));});
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']});results.browser=browser.version();
 const context=await browser.newContext({viewport:{width:1366,height:1000},reducedMotion:'reduce'});
 await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){results.externalRequests.push(url);return route.abort();}return route.continue();});
 page=await context.newPage();page.on('pageerror',error=>results.pageErrors.push(String(error)));page.on('dialog',dialog=>dialog.dismiss());let writes=0,matrixReads=0;
 // The existing live preview uses a read-only POST. Project mutations retain
 // their full count; rendering a draft is not a persistence operation.
 page.on('request',request=>{if(!['GET','HEAD'].includes(request.method())&&!/\/api\/projects\/[^/]+\/preview$/.test(request.url()))writes++;if(request.url().includes('/retest-matrix?'))matrixReads++;});
 await page.goto(base);await page.waitForFunction(()=>typeof RetestMatrixUI!=='undefined'&&!document.getElementById('splash'));
 await page.evaluate(async()=>{
   await requireOk(await api.post('/api/projects',{slug:'matrix-fixture',title:'Synthetic matrix',client:'Synthetic entity'}));
   await requireOk(await api.post('/api/projects',{slug:'matrix-other',title:'Other synthetic project',client:'Synthetic entity'}));
   await refreshProjects();await loadProject('matrix-fixture');
   S.data.report.sections=[];S.data.report.workflow={include_retest:false};
   const assetA={uid:WorkflowUI.uid(),name:'Synthetic asset A '+('LongName'.repeat(20)),target:'https://synthetic.invalid/a',kind:'URL',notes:''},assetB={uid:WorkflowUI.uid(),name:'Synthetic asset B',target:'https://synthetic.invalid/b',kind:'URL',notes:''};
   S.data.assets=[assetA,assetB];S.data.evidence=[];
   const finding=(index,status,verification,severity,assets,retests)=>({id:'F0'+(index+1),uid:WorkflowUI.uid(),mode:'vuln',title:'Synthetic matrix finding '+index,severity,description_md:'Synthetic observation.',impact_md:'Synthetic impact.',remediation_md:'Synthetic remediation.',status,...(verification?{verification}:{}),asset_uids:assets,evidence_uids:[],retests});
   const observation=(result,date)=>({uid:WorkflowUI.uid(),tested_on:date,result,assessor:'Synthetic assessor',notes_md:'Synthetic recorded procedure.',evidence_uids:[]});
   S.data.findings=[finding(0,'reported_fixed','unverified','high',[assetA.uid],[]),finding(1,'verified_fixed','confirmed','high',[assetB.uid],[observation('fixed','2026-10-08'),observation('open','2026-10-09')]),finding(2,'in_progress','inconclusive','medium',[assetA.uid],[observation('fixed','2026-10-09'),observation('partial','2026-10-09')]),finding(3,'accepted','not_reproduced','low',[],[observation('fixed','2026-10-08')]),finding(4,'not_verified',null,'info',[],[observation('fixed','')])];
   S.data.coverage=[{uid:WorkflowUI.uid(),test:'Synthetic blocked coverage',status:'blocked',notes:'Synthetic blocker'}];S.data.finding_sequence=5;
   scheduleSave();await doSave();select('findings');
 });
 await page.locator('#workspaceFollowup > summary').click();
 await page.locator('[data-workflow="retest_matrix"]').click();
 check('Sidebar opens the retest matrix through a visible user control',await page.locator('[data-workflow-view="retest_matrix"]').count()===1&&await page.locator('[data-studio-nav="review"]').getAttribute('aria-current')==='page'&&await page.evaluate(()=>document.documentElement.dataset.studio==='review'));
 await page.locator('[data-retest-matrix]').waitFor();await page.waitForFunction(()=>!projectStore.loading&&!projectStore.dirty&&!projectBusyCount);
 const original=await page.evaluate(()=>({json:JSON.stringify(S.data),revision:projectStore.revision,etag:projectStore.etag})),beforeWrites=writes;
 check('Matrix shows five source findings with independent status, verification and outcome',await page.locator('[data-retest-row]').count()===5&&await page.evaluate(()=>{const rows=[...document.querySelectorAll('[data-retest-row]')];return rows[0].textContent.includes('Corrección comunicada')&&rows[0].textContent.includes('Sin verificar')&&rows[0].textContent.includes('Sin observaciones registradas')&&rows[1].dataset.retestOutcome==='open'&&rows[2].dataset.retestOutcome==='partial'&&rows[4].textContent.includes('Sin verificación registrada');}));
 check('Executive graph has complete numeric text for every outcome including zero counts',await page.locator('[data-retest-chart]').count()===1&&await page.locator('[data-retest-result-count]').count()===7&&await page.locator('[data-retest-result-count="fixed"]').textContent()==='Corregido: 1'&&await page.locator('[data-retest-result-count="not_run"]').textContent()==='Sin observaciones registradas: 1');
 check('Matrix is a semantic table with caption and six scoped column headers',await page.locator('.rm-table caption').textContent()==='Matriz de retest del proyecto guardado'&&await page.locator('.rm-table thead th[scope="col"]').count()===6&&await page.locator('.rm-table tbody th[scope="row"]').count()===5);
 check('Verified-fixed contradiction and fixed-without-evidence remain visible',await page.locator('[data-retest-row="finding:1"]').textContent().then(text=>text.includes('último resultado fechado no es'))&&await page.locator('[data-retest-row="finding:3"]').textContent().then(text=>text.includes('sin evidencia del retest vinculada')));
 await page.locator('[data-retest-filter="status"]').selectOption('reported_fixed');check('Tracking-status filter does not turn a reported fix into a fixed observation',await page.locator('[data-retest-row]').count()===1&&await page.locator('[data-retest-result-count="fixed"]').textContent()==='Corregido: 0');
 await page.locator('[data-retest-filter="status"]').selectOption('');await page.locator('[data-retest-filter="severity"]').selectOption('high');check('Severity filter counts actual source severities',await page.locator('[data-retest-row]').count()===2);
 await page.locator('[data-retest-filter="severity"]').selectOption('');const asset=await page.evaluate(()=>S.data.assets[0].uid);await page.locator('[data-retest-filter="asset"]').selectOption(asset);check('Asset filter follows explicit linked UID instead of affected prose',await page.locator('[data-retest-row]').count()===2);
 await page.locator('[data-retest-filter="outcome"]').selectOption('open');check('Combined filters have an honest empty state',await page.locator('[data-retest-row]').count()===0&&await page.locator('[data-retest-empty]').count()===1);
 await page.locator('[data-retest-filter="asset"]').selectOption('');await page.locator('[data-retest-filter="outcome"]').selectOption('');
 await page.getByText('Cobertura registrada y límites de esta vista',{exact:true}).click();check('Coverage displays blocked records without a completion percentage or certification',await page.locator('.rm-scope').textContent().then(text=>text.includes('Bloqueada: 1')&&text.includes('Realizada: 0')&&text.includes('no certifica')&&text.includes('no se añade a PDF')&&!text.includes('%')));
 check('Reading and filtering never issue writes or change report inclusion, saved data or revision',writes===beforeWrites&&await page.evaluate(before=>JSON.stringify(S.data)===before.json&&projectStore.revision===before.revision&&projectStore.etag===before.etag&&S.data.report.workflow.include_retest===false,original));
 const chosen=await page.locator('[data-retest-row="finding:2"] [data-retest-finding-uid]').getAttribute('data-retest-finding-uid');await page.locator('[data-retest-row="finding:2"] [data-retest-finding-uid]').click();check('Opening a source UID selects its finding and moves focus to the editor title',await page.evaluate(uid=>S.data.findings[S.sel.idx].uid===uid&&document.activeElement===document.querySelector('.finding-context-title strong'),chosen));
 await page.evaluate(()=>select('workflow','retest_matrix'));await page.locator('[data-retest-matrix]').waitFor();
 const readBeforeDirty=matrixReads,writesBeforeDirty=writes;await page.evaluate(()=>{S.data.findings[0].title='Synthetic unsaved draft';scheduleSave();projectStore.timers.clearTimeout(projectStore.timer);projectStore.timer=null;});
 await page.locator('[data-retest-stale]').waitFor({state:'visible'});check('An existing snapshot is marked stale immediately and disables finding destinations',await page.locator('[data-retest-finding-uid]:disabled').count()===5);
 await page.evaluate(()=>select('workflow','retest_matrix'));await page.locator('[data-retest-stale]').waitFor({state:'visible'});const dirtyState=await page.evaluate(()=>({dirty:projectStore.dirty,title:S.data.findings[0].title}));check('Opening the matrix with a dirty draft makes no GET or PUT and preserves the draft',matrixReads===readBeforeDirty&&writes===writesBeforeDirty&&dirtyState.dirty&&dirtyState.title==='Synthetic unsaved draft',{matrixReads,readBeforeDirty,writes,writesBeforeDirty,dirtyState});
 await page.evaluate(async()=>{await doSave();select('workflow','retest_matrix');});await page.locator('[data-retest-matrix]').waitFor();
 let release,received=false;const pending=new Promise(resolve=>release=resolve);
 await context.route(base+'/api/projects/matrix-fixture/retest-matrix?*',async route=>{received=true;const response=await route.fetch();await pending;await route.fulfill({response});});
 await page.locator('[data-retest-refresh]').click();await page.waitForFunction(()=>!!document.querySelector('[data-retest-loading]'));
 for(let n=0;!received&&n<200;n++)await page.waitForTimeout(10);assert.ok(received,'Delayed matrix request received');
 const delayedWrites=writes;await page.evaluate(()=>{S.data.findings[1].title='Synthetic changed during fetch';scheduleSave();projectStore.timers.clearTimeout(projectStore.timer);projectStore.timer=null;});release();
 await page.locator('[data-retest-stale]').waitFor({state:'visible'});check('Delayed results cannot replace a newer draft or install stale matrix rows',await page.locator('[data-retest-matrix]').count()===0&&writes===delayedWrites&&await page.evaluate(()=>projectStore.dirty&&S.data.findings[1].title==='Synthetic changed during fetch'));
 await context.unroute(base+'/api/projects/matrix-fixture/retest-matrix?*');await page.evaluate(async()=>{await doSave();select('workflow','retest_matrix');});await page.locator('[data-retest-matrix]').waitFor();
 let releaseProject,receivedProject=false;const projectPending=new Promise(resolve=>releaseProject=resolve);
 await context.route(base+'/api/projects/matrix-fixture/retest-matrix?*',async route=>{receivedProject=true;const response=await route.fetch();await projectPending;await route.fulfill({response});});
 await page.locator('[data-retest-refresh]').click();for(let n=0;!receivedProject&&n<200;n++)await page.waitForTimeout(10);assert.ok(receivedProject,'Project-switch delayed request received');
 await page.evaluate(async()=>loadProject('matrix-other'));releaseProject();await page.waitForFunction(()=>S.slug==='matrix-other'&&!projectStore.loading);await page.waitForTimeout(100);
 check('Late matrix replies for a previous project cannot populate the new project',await page.locator('[data-retest-matrix]').count()===0&&await page.evaluate(()=>S.slug==='matrix-other'&&!JSON.stringify(S.data).includes('Synthetic changed during fetch')));
 await context.unroute(base+'/api/projects/matrix-fixture/retest-matrix?*');await page.evaluate(async()=>{await loadProject('matrix-fixture');select('workflow','retest_matrix');});await page.locator('[data-retest-matrix]').waitFor();
 await context.route(base+'/api/projects/matrix-fixture/retest-matrix?*',async route=>{const response=await route.fetch(),headers={...response.headers(),etag:'"'+'0'.repeat(64)+'"'};await route.fulfill({response,headers});});
 await page.locator('[data-retest-refresh]').click();await page.locator('[data-retest-stale]').waitFor({state:'visible'});check('A mismatching response ETag is rejected even when body and local data look current',await page.locator('[data-retest-matrix]').count()===0);
 await context.unroute(base+'/api/projects/matrix-fixture/retest-matrix?*');
 const busyReads=matrixReads,busyWrites=writes;await page.evaluate(()=>{busyProject(true);select('workflow','retest_matrix');});
 await page.locator('[data-retest-stale]').waitFor({state:'visible'});check('A busy project cannot request or install a matrix snapshot',matrixReads===busyReads&&writes===busyWrites&&await page.locator('[data-retest-matrix]').count()===0);await page.evaluate(()=>busyProject(false));
 const matrixStates=[];
 for(const lang of ['es','en'])for(const theme of ['dark','light'])for(const width of [320,1366])for(const growth of [1,2]){
   await page.setViewportSize({width,height:1000});await page.evaluate(({lang,theme})=>{document.querySelectorAll('[data-matrix-test-growth]').forEach(element=>{element.style.removeProperty('font-size');element.removeAttribute('data-matrix-test-growth');});setUiLang(lang);applyUiTheme(theme);select('workflow','retest_matrix');},{lang,theme});
   await page.locator('[data-retest-matrix]').waitFor();
   const sizes=await page.evaluate(growth=>{const node=document.querySelector('[data-retest-matrix]'),before=parseFloat(getComputedStyle(node).fontSize);if(growth===2){const elements=[...document.querySelectorAll('*')].filter(element=>element instanceof HTMLElement).map(element=>[element,parseFloat(getComputedStyle(element).fontSize)]);for(const [element,size]of elements){element.style.fontSize=size*2+'px';element.setAttribute('data-matrix-test-growth','');}}return {before,after:parseFloat(getComputedStyle(node).fontSize)};},growth);
   const layout=await page.evaluate(()=>({viewport:innerWidth,page:document.documentElement.scrollWidth,controls:[...document.querySelectorAll('[data-retest-filter]')].map(element=>({width:element.getBoundingClientRect().width,left:element.getBoundingClientRect().left,right:element.getBoundingClientRect().right})),rows:document.querySelectorAll('[data-retest-row]').length,caption:document.querySelector('.rm-table caption').textContent,captionWidth:document.querySelector('.rm-table caption').getBoundingClientRect().width,tableWidth:document.querySelector('.rm-table').getBoundingClientRect().width}));
   // DevTools audit instrumentation preserves the app's real CSP; it does not
   // add a prohibited inline script element to the product document.
   let violations=[];if(axe){await page.evaluate(fs.readFileSync(axe,'utf8'));violations=await page.evaluate(async()=>{const result=await axe.run(document.querySelector('[data-retest-matrix]'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return result.violations.map(item=>({id:item.id,nodes:item.nodes.map(node=>node.target)}));});}
   const state={lang,theme,width,growth,sizes,layout,violations};matrixStates.push(state);
   check('Language/theme/reflow/axe '+[lang,theme,width,growth*100+'%'].join('/'),sizes.after===sizes.before*growth&&layout.page<=layout.viewport+1&&layout.controls.length===4&&layout.controls.every(control=>control.width>20&&control.left>=-1&&control.right<=layout.viewport+1)&&layout.rows===5&&layout.captionWidth>=layout.tableWidth*.8&&violations.length===0,state);
   if(width===320&&growth===2)await page.screenshot({path:path.join(out,'matrix-'+lang+'-'+theme+'-mobile-200.png'),fullPage:true});
 }
 results.matrixStates=matrixStates;results.axeExecuted=!!axe;
 check('UI language does not change the authored report language or retest inclusion',await page.evaluate(()=>S.data.meta.lang==='es'&&S.data.report.workflow.include_retest===false));
 check('No browser errors or external requests',results.pageErrors.length===0&&results.externalRequests.length===0,{pageErrors:results.pageErrors,externalRequests:results.externalRequests});save();
 }catch(error){if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw error;}finally{clearTimeout(timer);await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{results.error=String(error.stack||error);save();console.error(error);process.exitCode=1;});
