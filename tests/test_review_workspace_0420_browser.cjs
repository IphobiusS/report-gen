/* Native browser acceptance: filtered review/resume, pinned evidence, responsive
   geometry, localized UI and selected-row bulk assignment. Uses fictional data. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const {clickNavigationControl}=require('./browser-navigation.cjs');
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const root=path.resolve(option('--tool',process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'))),out=path.resolve(option('--output','out/review-workspace-0420'));
const {chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
fs.mkdirSync(out,{recursive:true});
const temporary=()=>{const directory=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-review-'));fs.writeFileSync(path.join(directory,'.test-only'),'synthetic acceptance workspace');return directory;};
const workspaceA=temporary(),results={checks:[],pageErrors:[],externalRequests:[]};
const save=()=>fs.writeFileSync(out+'/results.json',JSON.stringify(results,null,2));
const check=(name,value,detail)=>{results.checks.push({name,passed:!!value,...(detail===undefined?{}:{detail})});save();assert.ok(value,name);console.log('PASS '+name);};
let server,browser,page;
async function start(workspace,port=0){
 server=spawn(process.env.RG_PYTHON||'python',[root+'/scripts/browser-server-0211.py','--workspace',workspace,'--port',String(port)],{cwd:root,env:{...process.env,REPORT_GEN_UI_LANG:'en',PYTHONPATH:root+path.delimiter+root+'/webapp'}});
 server.stderr.on('data',b=>fs.appendFileSync(out+'/server.log',b));
 return new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Server startup timeout')),20000);server.stdout.on('data',b=>{text+=b;for(const line of text.split('\n'))try{const result=JSON.parse(line);if(result.url){clearTimeout(timer);resolve(result);}}catch{}});server.on('exit',code=>{clearTimeout(timer);reject(Error('Server exited '+code));});});
}
async function stop(){if(!server||server.exitCode!==null)return;const stopped=new Promise(resolve=>server.once('exit',resolve));server.kill('SIGTERM');await stopped;}
async function ready(){await page.waitForFunction(()=>typeof BulkUI!=='undefined'&&!document.getElementById('splash')&&!projectBusyCount&&!projectStore.loading);}

(async()=>{try{
 const address=await start(workspaceA),base=address.url;
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']});results.browser=browser.version();
 const context=await browser.newContext({viewport:{width:1440,height:1080},reducedMotion:'reduce'});
 await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){results.externalRequests.push(url);return route.abort();}return route.continue();});
 page=await context.newPage();page.on('pageerror',e=>{results.pageErrors.push(String(e));save();});page.on('dialog',d=>d.accept());
 await page.addInitScript(()=>localStorage.setItem('rg.previewVisible','0'));await page.goto(base);await ready();
 await page.evaluate(async()=>{
   await requireOk(await api.post('/api/projects',{slug:'atlas-review',title:'Atlas · API security review'}));await refreshProjects();await loadProject('atlas-review');
   S.data.assets=[{uid:WorkflowUI.uid(),name:'Atlas Payments API',target:'https://api.atlas.example.test',kind:'API',notes:'Synthetic authorized fixture'}];
   S.data.findings=Array.from({length:8},(_,i)=>({uid:WorkflowUI.uid(),id:'F'+(i+1),mode:'vuln',title:['Authorization across organizations','Session revocation','Payment export access','Role boundary validation'][i%4]+' · '+(i+1),owner:i%2?'API team':'Platform',asset_uids:[S.data.assets[0].uid],severity:i%2?'high':'low',verification:'confirmed',status:'open',description_md:'Synthetic assessment of authorization controls in the Atlas payment service. Two explicitly separated organizations were used to compare access.',impact_md:'A user can access a synthetic payment record belonging to another test organization.',remediation_md:'Enforce organization membership and object authorization at the service boundary; add regression coverage for each role.'}));
   S.data.finding_sequence=8;scheduleSave();await doSave();
   const canvas=document.createElement('canvas');canvas.width=960;canvas.height=420;const ctx=canvas.getContext('2d');ctx.fillStyle='#111b24';ctx.fillRect(0,0,960,420);ctx.fillStyle='#5ee7ad';ctx.font='28px monospace';ctx.fillText('ATLAS / AUTHORIZATION COMPARISON',36,60);ctx.fillStyle='#e0eaf2';ctx.font='20px monospace';['GET /payments/synthetic-204 · User: reviewer-a','Expected: 403 for organization B','Observed: HTTP/1.1 200 OK','{"payment":"synthetic-204","organization":"B"}','Fictional data · no production system contacted'].forEach((line,i)=>ctx.fillText(line,36,130+i*50));
   const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png')),upload=await sendImage(new File([blob],'atlas-proof.png',{type:'image/png'}));
   const response=await requireOk(await appFetch('/api/projects/'+S.slug+'/evidence',{method:'POST',headers:{'Content-Type':'application/json','If-Match':projectStore.etag},body:JSON.stringify({src:upload.src,title:'Role comparison · synthetic evidence',caption:'The response body contains a fictional record from the second organization.'})}));
   const result=await response.json();await adoptSavedProject(result.data,response.headers.get('ETag'));S.data.findings.forEach(f=>f.evidence_uids=[S.data.evidence[0].uid]);scheduleSave();await doSave();S.dashFilter='high';select('findings');
 });await ready();
 const expected=await page.locator('.dash-row').evaluateAll(rows=>rows.map(row=>row.dataset.findingUid));check('Filtered review has four high findings',expected.length===4);
 await page.locator('.finding-row-open').first().click();await page.locator('[data-inspector-toggle]').click();await page.locator('#pinnedEvidence img').waitFor();
 check('Filtered context list matches the review queue',JSON.stringify(await page.locator('#findingList li[data-finding-uid]').evaluateAll(rows=>rows.map(row=>row.dataset.findingUid)))===JSON.stringify(expected));
 for(const language of ['es','en','pt']){
   await page.evaluate(language=>setUiLang(language),language);await page.locator('#pinnedEvidence img').waitFor();
   const geometry=await page.evaluate(()=>{const e=document.getElementById('editor').getBoundingClientRect(),p=document.getElementById('pinnedEvidence').getBoundingClientRect();return {editor:e.toJSON(),panel:p.toJSON(),viewport:innerWidth,overflow:document.documentElement.scrollWidth>innerWidth+1};});
   check(language+' evidence is beside the editor with no page overflow',geometry.panel.left>=geometry.editor.right-2&&geometry.editor.width>=280&&!geometry.overflow,geometry);
   await page.screenshot({path:out+'/review-'+language+'-desktop.png',fullPage:true});
 }
 await page.locator('[data-finding-save-next]').click();await page.waitForFunction(uid=>S.data.findings[S.sel.idx].uid===uid,expected[1]);check('Save and next stays inside the queue',await page.locator('[data-finding-position-label]').innerText().then(text=>text.includes('2 de 4')));
 await page.reload();await ready();await page.evaluate(async()=>{await loadProject('atlas-review');WorkbenchUI.resumeQueue();});await page.locator('[data-finding-position-label]').waitFor();check('Reload resumes the exact queue item',await page.evaluate(uid=>S.data.findings[S.sel.idx].uid===uid,expected[1]));
 for(const width of [1101,1024,760,390]){
   await page.setViewportSize({width,height:900});await page.evaluate(()=>WorkbenchUI.inspectEvidence());await page.locator('#pinnedEvidence').waitFor();
   const geometry=await page.evaluate(()=>({overflow:document.documentElement.scrollWidth>innerWidth+1,panel:document.getElementById('pinnedEvidence').getBoundingClientRect().toJSON()}));check(width+' px keeps the evidence panel within the viewport',!geometry.overflow&&geometry.panel.width<=width+1,geometry);await page.screenshot({path:out+'/review-'+width+'.png',fullPage:true});
 }
 await page.setViewportSize({width:1440,height:1080});await page.evaluate(()=>select('findings'));await page.locator('[data-board-select]').first().check();await page.locator('[data-board-select]').nth(1).check();await page.locator('[data-board-bulk]').click();check('Table selection feeds exactly two findings into guarded bulk assignments',await page.locator('[data-bulk-finding]:checked').count()===2&&await page.locator('[data-bulk-apply]').isDisabled());await page.screenshot({path:out+'/review-bulk-selection.png',fullPage:true});
 check('No JavaScript page errors',results.pageErrors.length===0,results.pageErrors);check('No external network requests',results.externalRequests.length===0,results.externalRequests);results.status='passed';save();
} catch(error){results.status='failed';results.error=String(error.stack||error);save();throw error;}finally{await browser?.close();await stop();fs.rmSync(workspaceA,{recursive:true,force:true});}})().catch(error=>{console.error(error);process.exitCode=1;});
