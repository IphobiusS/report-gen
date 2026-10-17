/* Read-only, real Chromium acceptance of the complete trilingual Aster fixture.
 * Screenshots are produced only by an actual browser. No synthetic UI images.
 */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {spawn}=require('node:child_process'),{createHash}=require('node:crypto');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2);
const option=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const workspaceArg=option('--workspace');
if(!workspaceArg)throw Error('Usage: node scripts/audit-aster-browser-0420.cjs --workspace ASTER_ROOT --output OUTPUT [--executable CHROMIUM]');
const workspace=path.resolve(workspaceArg),output=path.resolve(option('--output','out/aster-browser-0420'));
for(const lang of ['es','en','pt'])if(!fs.existsSync(path.join(workspace,'projects',lang,'engagement.yaml')))throw Error('Missing Aster project: '+lang);
const fixture=JSON.parse(fs.readFileSync(path.join(workspace,'manifest.json'),'utf8'));
assert.equal(fixture.schema,'report-gen-aster-source/1','Aster source manifest');
fs.mkdirSync(output,{recursive:true});
const results={schema:'report-gen-aster-browser/1',execution:'pending',fixture:workspace,fictional:true,
 checks:[],screens:[],pageErrors:[],consoleErrors:[],externalRequests:[],mutationAttempts:[],httpErrors:[],failedRequests:[],projects:{},
 scope:'Read-only interface and screenshots of the complete synthetic Aster case; no scanner, connector, model, export or technical verification is executed.'};
const save=()=>fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));
const check=(name,value,details)=>{results.checks.push({name,passed:!!value,...(details===undefined?{}:{details})});save();assert.ok(value,name);console.log('PASS '+name);};
function treeHashes(directory){
 const output={};function visit(current){for(const entry of fs.readdirSync(current,{withFileTypes:true})){const file=path.join(current,entry.name);if(entry.isSymbolicLink())throw Error('Fixture symlink not allowed: '+file);if(entry.isDirectory())visit(file);else if(entry.isFile())output[path.relative(directory,file).split(path.sep).join('/')]=createHash('sha256').update(fs.readFileSync(file)).digest('hex');}}visit(directory);return output;
}
const sourceHashes=treeHashes(path.join(workspace,'projects'));
const serverCode=String.raw`
from pathlib import Path
import tempfile, sys, os, signal, json, shutil
installation=Path(sys.argv[1]).resolve()
source=Path(sys.argv[2]).resolve()
sys.path[:0]=[str(installation),str(installation/'webapp')]
with tempfile.TemporaryDirectory(prefix='report-gen-aster-browser-') as temporary:
    destination=Path(temporary).resolve()
    shutil.copytree(source/'projects',destination/'projects')
    if (source/'library').is_dir():
        shutil.copytree(source/'library',destination/'library')
    os.environ['REPORT_GEN_WORKSPACE']=str(destination)
    import app as api
    server=api.create_local_server(0)
    def stop(*args):raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop)
    try:
        print(json.dumps({'url':f'http://127.0.0.1:{server.effective_port}'}),flush=True)
        server.run()
    finally:
        if 'export_queue' in api.app.extensions:api.app.extensions['export_queue'].close()
        server.close()
`;
let server,browser,activePage;
async function idle(page,slug){
 await page.waitForFunction(slug=>typeof S!=='undefined'&&typeof projectStore!=='undefined'&&!document.querySelector('#splash')&&
  !document.querySelector('.topbar[inert],.layout[inert]')&&!projectBusyCount&&!projectStore.loading&&!!S.data&&(!slug||S.slug===slug),slug,{timeout:60000});
 await page.evaluate(()=>document.fonts.ready);
}
async function stableImages(page,scope='body'){
 await page.locator(scope).first().evaluate(async root=>{await Promise.all([...root.querySelectorAll('img')].filter(image=>image.getClientRects().length&&image.loading!=='lazy').map(image=>image.complete?(image.naturalWidth?Promise.resolve():Promise.reject(Error('Visible image failed: '+image.getAttribute('src')))):new Promise((resolve,reject)=>{image.addEventListener('load',resolve,{once:true});image.addEventListener('error',()=>reject(Error('Visible image failed: '+image.getAttribute('src'))),{once:true});})));});
}
async function capture(page,lang,name,scope='body'){
 await idle(page,lang);await stableImages(page,scope);
 await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
 const file=path.join(output,lang+'-'+name+'.png');await page.screenshot({path:file,fullPage:false,animations:'disabled'});
 const state=await page.evaluate(()=>({slug:S.slug,lang:S.uiLang,selection:S.sel,etag:projectStore.etag,dirty:projectStore.dirty,
  viewport:{width:innerWidth,height:innerHeight},scrollWidth:document.documentElement.scrollWidth}));
 results.screens.push({name,language:lang,path:file,sha256:createHash('sha256').update(fs.readFileSync(file)).digest('hex'),...state});save();
 check(lang+' '+name+' screenshot has current clean project',state.slug===lang&&state.lang===lang&&!state.dirty);
}
async function workflow(page,lang,kind){
 await idle(page,lang);await page.evaluate(kind=>{WorkbenchUI.closeInspector();select('workflow',kind);document.querySelector('#editor').scrollTop=0;},kind);
 await page.locator('[data-workflow-view="'+kind+'"]').waitFor();await idle(page,lang);
}
async function geometry(page,name){
 const box=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
 check(name+' page fits viewport',box.scrollWidth<=box.width+1,box);
}
(async()=>{try{
 server=spawn(process.env.RG_PYTHON||'python3',['-c',serverCode,root,workspace],{cwd:root,env:process.env});
 server.stderr.on('data',part=>fs.appendFileSync(path.join(output,'server.log'),part));
 const base=await new Promise((resolve,reject)=>{let text='',settled=false;const timeout=setTimeout(()=>{settled=true;reject(Error('Aster server startup timeout'));},60000);
  server.stdout.on('data',part=>{text+=part;if(!settled&&text.includes('\n')){settled=true;clearTimeout(timeout);try{resolve(JSON.parse(text.split('\n')[0]).url);}catch(error){reject(error);}}});
  server.once('error',error=>{clearTimeout(timeout);reject(error);});server.once('exit',code=>{if(!settled){clearTimeout(timeout);reject(Error('Aster server exited '+code));}});
 });
 const executable=option('--executable',process.env.RG_CHROMIUM_EXECUTABLE||process.env.REPORT_GEN_CHROMIUM);
 browser=await chromium.launch({headless:true,...(executable?{executablePath:executable}:{})});results.execution='running';results.browser=browser.version();save();
 for(const lang of ['es','en','pt']){
  const expected=fixture.projects[lang],context=await browser.newContext({viewport:{width:1600,height:1050},reducedMotion:'reduce'}),page=await context.newPage();activePage=page;
  await context.addInitScript(lang=>{if(window!==window.top)return;localStorage.setItem('rg.uiLang',lang);localStorage.setItem('rg.previewVisible','0');localStorage.setItem('rg.uiTheme','dark');},lang);
  await context.route('**/*',route=>{const request=route.request(),url=request.url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){results.externalRequests.push({lang,url});save();return route.abort();}
   if(/^https?:/.test(url)&&!['GET','HEAD','OPTIONS'].includes(request.method())){results.mutationAttempts.push({lang,url,method:request.method()});save();return route.abort();}return route.continue();});
  page.on('pageerror',error=>results.pageErrors.push({lang,error:String(error)}));
  page.on('console',message=>{if(message.type()==='error')results.consoleErrors.push({lang,text:message.text()});});
  page.on('response',response=>{if(response.status()>=400)results.httpErrors.push({lang,status:response.status(),url:response.url()});});
  page.on('requestfailed',request=>{const error=request.failure()?.errorText||'';if(!error.includes('ERR_ABORTED'))results.failedRequests.push({lang,url:request.url(),error});});
  await page.goto(base,{waitUntil:'domcontentloaded'});await idle(page);
  // Startup opens the first existing project asynchronously; wait for it before
  // selecting a different fixture language, preventing overlapping loads.
  await page.evaluate(async lang=>{if(S.slug!==lang)await loadProject(lang);},lang);await idle(page,lang);
  const initial=await page.evaluate(()=>({etag:projectStore.etag,json:JSON.stringify(S.data),findings:S.data.findings.length,assets:S.data.assets.length,evidence:S.data.evidence.length,
   coverage:S.data.coverage.length,http:S.data.http_evidence.length,tests:S.data.test_cases.length,paths:S.data.attack_paths.length,
   instances:S.data.findings[0].instances.length,instanceResults:S.data.findings[0].instances.reduce((out,row)=>(out[row.status]=(out[row.status]||0)+1,out),{}),
   firstFinding:S.data.findings[0].uid,firstEvidence:S.data.findings[0].evidence_uids[0],firstHttp:S.data.http_evidence.find(row=>row.finding_uids.includes(S.data.findings[0].uid)).uid,
   firstCase:S.data.test_cases[0].uid,firstPath:S.data.attack_paths[0].uid,profile:S.data.client_profile.version}));
  results.projects[lang]={...initial,json:undefined};
  check(lang+' complete complex fixture loaded',initial.findings===expected.vulnerabilities+expected.machines&&initial.assets===expected.assets&&initial.evidence===expected.evidence&&initial.coverage===expected.coverage&&initial.http===expected.http_pairs&&initial.tests===expected.test_cases&&initial.paths===expected.attack_paths&&initial.instances===18,results.projects[lang]);
  check(lang+' independent instance outcomes remain visible',initial.instanceResults.verified_fixed===15&&initial.instanceResults.open===2&&initial.instanceResults.blocked===1,initial.instanceResults);

  await page.evaluate(()=>{select('findings',-1);document.querySelector('#editor').scrollTop=0;});await page.locator('.finding-row-open').first().waitFor();
  check(lang+' grouped navigation present',await page.locator('[data-sidebar-group]').count()===5);
  await capture(page,lang,'01-findings-workspace');await geometry(page,lang+' desktop');

  await page.evaluate(({evidence})=>{select('finding',0);WorkbenchUI.inspectEvidence('image:'+evidence);document.querySelector('#editor').scrollTop=0;},{evidence:initial.firstEvidence});
  await page.locator('[data-finding-context-uid="'+initial.firstFinding+'"]').waitFor();await page.locator('#pinnedEvidence img').waitFor();
  check(lang+' pinned image corresponds to selected finding',await page.locator('[data-pinned-evidence-content="image:'+initial.firstEvidence+'"]').count()===1);
  await capture(page,lang,'02-editor-pinned-image','#pinnedEvidence');
  await page.evaluate(uid=>WorkbenchUI.inspectEvidence('http:'+uid),initial.firstHttp);await page.locator('#pinnedEvidence pre').first().waitFor();
  check(lang+' native HTTP evidence can be pinned',await page.locator('[data-pinned-evidence-content="http:'+initial.firstHttp+'"] pre').count()===2);
  await capture(page,lang,'03-editor-pinned-http');

  await page.evaluate(()=>{WorkbenchUI.closeInspector();WorkbenchUI.revealFindingPart('instances');});
  await page.locator('[data-instances-finding="'+initial.firstFinding+'"]').evaluate(element=>element.scrollIntoView({block:'start'}));
  check(lang+' all 18 instances rendered independently',await page.locator('[data-instance-uid]').count()===18);
  await capture(page,lang,'04-instance-retest-status');

  await workflow(page,lang,'http_evidence');await page.locator('[data-http-record]').first().waitFor();
  check(lang+' all HTTP pairs listed',await page.locator('[data-http-record]').count()===expected.http_pairs);
  await capture(page,lang,'05-http-library');
  await page.locator('[data-http-record]').first().getByRole('button').click();await page.locator('[data-http-editor]').waitFor();
  check(lang+' publication copy remains separately reviewed',await page.locator('[data-http-publish]').isChecked()&&!await page.locator('[data-http-reviewed]').isChecked());
  await capture(page,lang,'06-http-reviewed-copy');await page.locator('[data-http-editor]').evaluate(dialog=>dialog.close());

  await workflow(page,lang,'assessment_cases');await page.locator('[data-assessment-list]').waitFor();
  check(lang+' test plan list paginated',await page.locator('[data-assessment-action^="edit-"]').count()===Math.min(25,expected.test_cases));
  await page.locator('[data-assessment-action="edit-'+initial.firstCase+'"]').click();await page.locator('[data-assessment-form="case"]').waitFor();
  await page.locator('[data-assessment-form="case"]').evaluate(element=>element.scrollIntoView({block:'start'}));
  check(lang+' test plan context and evidence fields available',await page.locator('[data-assessment-form="case"] [data-assessment-field="expected"]').count()===1&&await page.locator('[data-assessment-form="case"] [data-assessment-refs="http_evidence_uids"]').count()===1);
  await capture(page,lang,'07-versioned-test-case');

  await workflow(page,lang,'assessment_paths');await page.locator('[data-assessment-list] details').first().locator('summary').click();
  const graph=page.locator('[data-assessment-list] .assessment-graph').first();await graph.waitFor();await graph.evaluate(image=>image.complete&&image.naturalWidth?true:new Promise((resolve,reject)=>{image.addEventListener('load',()=>resolve(true),{once:true});image.addEventListener('error',()=>reject(Error('Saved attack graph failed')),{once:true});}));
  await graph.evaluate(image=>image.closest('.card').scrollIntoView({block:'start'}));check(lang+' saved causal graph rendered',await graph.evaluate(image=>image.naturalWidth>0&&image.naturalHeight>0));
  await capture(page,lang,'08-saved-attack-path');

  await workflow(page,lang,'review_exchange');await page.locator('[data-review-exchange="profile-save"]').waitFor();
  const requirements=page.getByRole('heading',{name:{es:'Requisitos del perfil aplicado',en:'Applied profile requirements',pt:'Requisitos do perfil aplicado'}[lang],exact:true});await requirements.waitFor();
  check(lang+' editorial return and client profile controls present',await page.locator('[data-review-exchange="return-preview"]').count()===1&&await page.locator('[data-review-exchange="profile-save"]').count()===1);
  await capture(page,lang,'09-review-exchange');
  await requirements.evaluate(element=>element.closest('.rt-card').scrollIntoView({block:'start'}));await capture(page,lang,'10-client-profile');

  await workflow(page,lang,'tickets');await page.locator('[data-ticket-field="provider"]').waitFor();
  check(lang+' optional connectors displayed without connecting',await page.locator('[data-ticket-field="provider"] option').count()===2);
  await capture(page,lang,'11-optional-connectors');

  await page.evaluate(()=>{select('studio','deliver');document.querySelector('#editor').scrollTop=0;});await page.locator('[data-delivery-flow][data-delivery-current="true"]').waitFor({timeout:60000});
  check(lang+' saved delivery review has no blockers',await page.locator('[data-delivery-issues="error"] .delivery-flow-issue').count()===0);
  // The preparation card independently reads the saved review. Waiting only
  // for the main flow can capture its still-pending secondary request.
  await page.waitForFunction(()=>{
   const card=document.querySelector('[data-delivery-readiness]');
   return card?.dataset.readinessCurrent==='true'&&card.dataset.readinessRevision===projectStore.etag;
  },null,{timeout:60000});
  check(lang+' delivery preparation finished for the current revision',await page.locator('[data-delivery-readiness]').evaluate(card=>card.dataset.readinessCurrent==='true'&&card.dataset.readinessRevision===projectStore.etag));
  await capture(page,lang,'12-reviewed-delivery');

  await page.setViewportSize({width:430,height:932});await page.evaluate(()=>{select('finding',0);WorkbenchUI.closeInspector();document.querySelector('#editor').scrollTop=0;window.scrollTo(0,0);});await idle(page,lang);
  await page.locator('#sidebarToggle').click();await page.waitForFunction(()=>document.querySelector('#sidebarToggle')?.getAttribute('aria-expanded')==='true');
  await capture(page,lang,'13-narrow-navigation');await geometry(page,lang+' narrow navigation');
  await page.locator('#sidebarToggle').click();await page.waitForFunction(()=>document.querySelector('#sidebarToggle')?.getAttribute('aria-expanded')==='false');
  await capture(page,lang,'14-narrow-finding');await geometry(page,lang+' narrow finding');

  const final=await page.evaluate(async()=>({etag:projectStore.etag,json:JSON.stringify(S.data),dirty:projectStore.dirty,remoteEtag:(await appFetch('/api/projects/'+encodeURIComponent(S.slug))).headers.get('ETag')}));
  check(lang+' views do not mutate project or revision',final.etag===initial.etag&&final.remoteEtag===initial.etag&&final.json===initial.json&&!final.dirty);
  check(lang+' at least eight desktop and narrow screenshots',results.screens.filter(screen=>screen.language===lang).length>=8&&results.screens.some(screen=>screen.language===lang&&screen.viewport.width<600));
  await context.close();activePage=null;save();
 }
 check('No script exceptions',results.pageErrors.length===0,results.pageErrors);
 check('No browser console errors',results.consoleErrors.length===0,results.consoleErrors);
 check('No failed HTTP responses',results.httpErrors.length===0,results.httpErrors);
 check('No failed resource requests',results.failedRequests.length===0,results.failedRequests);
 check('No external target, connector or model requests',results.externalRequests.length===0,results.externalRequests);
 check('No attempted project mutations',results.mutationAttempts.length===0,results.mutationAttempts);
 check('Source Aster fixture byte-for-byte unchanged',JSON.stringify(treeHashes(path.join(workspace,'projects')))===JSON.stringify(sourceHashes));
 results.execution='passed';save();
}catch(error){
 results.execution=results.execution==='pending'?'unavailable_or_startup_failed':'failed';results.error=String(error.stack||error);save();
 if(activePage)try{await activePage.screenshot({path:path.join(output,'failure.png'),fullPage:true});}catch(_){}
 console.error(error);process.exitCode=1;
}finally{await browser?.close();server?.kill('SIGTERM');}})();
