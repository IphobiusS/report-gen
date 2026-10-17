/* Real Chromium acceptance: report-gen generates every source PDF itself. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {spawn}=require('node:child_process'),{createHash}=require('node:crypto');
const {clickNavigationControl,exposeNavigationControl}=require('../tests/browser-navigation.cjs');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2);
const out=path.resolve(args.includes('--output')?args[args.indexOf('--output')+1]:'out/visual-persistence-0410');
const {chromium}=require(require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
const hash=value=>createHash('sha256').update(value).digest('hex');
const sources=['scripts/audit-visual-persistence-0410.cjs','visual_review.py','webapp/visual_api.py','webapp/static/visual-review.js','webapp/static/insights.js','webapp/static/insights.css','webapp/static/index.html','project_history.py','attachments.py'];
const hashes=()=>Object.fromEntries(sources.map(name=>[name,hash(fs.readFileSync(path.join(root,name)))]));
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-visual-persistence-'));
fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');fs.mkdirSync(out,{recursive:true});
const result={schema:'report-gen-visual-persistence/1',complete:false,sourceStart:hashes(),checks:[],screens:[],pdfs:[],pageErrors:[],unexpectedApiErrors:[],expectedApiErrors:[],externalRequests:[],limits:['Automated Chromium acceptance; screenshots do not certify human review, identity, report content or Microsoft Word compatibility.','Fixture PDFs are generated through report-gen; one appended PDF comment is an intentional byte-mismatch control, not a report export.']};
const write=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2)+'\n');
function check(name,passed,detail){result.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});write();assert.ok(passed,name+': '+JSON.stringify(detail));console.log('PASS '+name);}
let server,browser,base,port;
async function start(){
  server=spawn(process.env.RG_PYTHON||'python3',[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace,...(port?['--port',String(port)]:[])],{cwd:root,env:{...process.env,PYTHONPATH:root+path.delimiter+path.join(root,'webapp')}});
  server.stderr.on('data',data=>fs.appendFileSync(path.join(out,'server.log'),data));
  base=await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Server startup timeout')),30000);server.once('exit',code=>{clearTimeout(timer);reject(Error('Server exited '+code));});server.stdout.on('data',chunk=>{text+=chunk;for(const line of text.split('\n'))try{const value=JSON.parse(line);if(value.url){port=value.port;clearTimeout(timer);resolve(value.url);}}catch{}});});
}
async function stop(){if(!server||server.exitCode!==null)return;await new Promise(resolve=>{server.once('exit',resolve);server.kill('SIGTERM');});}
async function ready(page){await page.waitForFunction(()=>typeof S!=='undefined'&&!document.querySelector('#splash')&&!projectBusyCount&&!projectStore.loading,null,{timeout:60000});}
async function screen(page,name,locator){if(locator)await locator.scrollIntoViewIfNeeded();await page.evaluate(()=>document.fonts.ready);const file=path.join(out,name+'.png');await page.screenshot({path:file});result.screens.push({file:path.basename(file),sha256:hash(fs.readFileSync(file)),viewport:page.viewportSize()});write();}
async function visual(page,slug){
  await ready(page);
  if(await page.evaluate(()=>S.slug)!==slug)await(await exposeNavigationControl(page,'#projectSelect')).selectOption(slug);
  await page.waitForFunction(slug=>S.slug===slug&&!projectStore.loading&&!projectBusyCount,slug);
  await clickNavigationControl(page,'#insightsBtn');await page.locator('[data-insights-tab="visual"]').click();
  await page.locator('[data-visual-library]').waitFor();await page.locator('[data-visual-saved-list]').waitFor();
}
async function upload(page,file){
  const input=page.locator('[data-insights-field="visual-file"]');const details=input.locator('xpath=ancestor::details');
  if(await details.getAttribute('open')===null)await details.locator('summary').click();
  await input.setInputFiles(file);const waiting=page.waitForResponse(response=>response.request().method()==='POST'&&new URL(response.url()).pathname.endsWith('/visual'));
  await page.locator('[data-insights-action="visual-upload"]').click();const response=await waiting;assert.equal(response.status(),200,await response.text());
  await page.locator('.insights-pdf-preview img').evaluate(node=>node.decode());return response.json();
}
async function save(page,slug){
  const waiting=page.waitForResponse(response=>response.request().method()==='POST'&&new URL(response.url()).pathname==='/api/projects/'+slug+'/visual-reviews');
  await page.locator('[data-visual-action="save-progress"]').click();const response=await waiting;assert.ok([200,201].includes(response.status()),await response.text());
  await page.waitForFunction(()=>!projectBusyCount);const body=await response.json();await page.locator('[data-visual-saved-id="'+body.record.uid+'"]').waitFor();await page.waitForFunction(()=>document.querySelector('[data-visual-action=save-progress]')?.disabled===false);return body.record;
}
(async()=>{try{
  await start();browser=await chromium.launch({headless:process.env.RG_HEADED!=='1',executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined});result.browser=browser.version();
  for(const lang of ['es','en','pt']){
    const slug='visual-retention-'+lang,context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
    await context.addInitScript(language=>{localStorage.setItem('rg.uiLang',language);localStorage.setItem('rg.previewVisible','0');},lang);
    await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){result.externalRequests.push(url);return route.abort();}return route.continue();});
    const page=await context.newPage();page.on('pageerror',error=>result.pageErrors.push(String(error)));page.on('dialog',dialog=>dialog.accept());
    page.on('response',response=>{if(response.url().startsWith(base+'/api/')&&response.status()>=400){const row={path:new URL(response.url()).pathname,status:response.status()};(response.status()===409&&row.path.endsWith('/open')?result.expectedApiErrors:result.unexpectedApiErrors).push(row);}});
    await page.goto(base);await ready(page);
    const source=await page.evaluate(async({slug,lang})=>{
      await requireOk(await api.post('/api/projects',{slug,title:'Visual retention synthetic '+lang,client:'Fictional review laboratory',model:'corporativo-'+lang}));
      const response=await requireOk(await appFetch('/api/projects/'+slug)),data=await response.json();data.meta.lang=lang;data.meta.assessor='Automated fixture';data.meta.date='2026-01-01';
      data.findings=Array.from({length:4},(_,index)=>({uid:WorkflowUI.uid(),id:'V-'+(index+1),title:'Synthetic finding '+(index+1),severity:'info',description_md:('Fictional visual persistence control. No real organization or vulnerability is represented.\n\n').repeat(8),impact_md:'Functional testing only.',recommendation_md:'Review the rendered report.'}));
      await requireOk(await appFetch('/api/projects/'+slug,{method:'PUT',headers:{'Content-Type':'application/json','If-Match':response.headers.get('ETag')},body:JSON.stringify(data)}));
      const pdf=await requireOk(await appFetch('/api/projects/'+slug+'/export/pdf',{method:'POST'}));
      const bytes=Array.from(new Uint8Array(await pdf.arrayBuffer()));await refreshProjects();return bytes;
    },{slug,lang});
    const file=path.join(out,'report-gen-fixture-'+lang+'.pdf'),mismatch=path.join(out,'mismatch-'+lang+'.pdf');fs.writeFileSync(file,Buffer.from(source));fs.writeFileSync(mismatch,Buffer.concat([Buffer.from(source),Buffer.from('\n% synthetic exact-byte mismatch\n')]));
    result.pdfs.push({lang,file:path.basename(file),sha256:hash(Buffer.from(source)),bytes:source.length,producer:'report-gen /export/pdf'});write();
    await visual(page,slug);const metadata=await upload(page,file);check(lang+' report-gen PDF opens with at least two actual pages',metadata.pages.length>=2&&metadata.pdf_sha256===hash(Buffer.from(source)));
    await page.locator('[data-insights-action="visual-next"]').click();await page.locator('.insights-pdf-preview img').evaluate(node=>node.decode());
    const notes=page.locator('[data-insights-field="note"]');await notes.nth(0).fill('Pending synthetic observation '+lang);await page.locator('[data-insights-action="add-visual-issue"]').click();
    await notes.nth(0).fill('Unfinished annotation '+lang);await notes.nth(1).fill('Private general note '+lang);await page.locator('[data-insights-field="author"]').fill('Automated fixture '+lang);await page.locator('[data-insights-field="decision"]').selectOption('pending');
    check(lang+' PDF copy starts unchecked',!await page.locator('[data-visual-keep-pdf]').isChecked());
    const first=await save(page,slug);check(lang+' explicit metadata save retains page notes and unfinished draft without copying PDF',first.progress.page===2&&first.progress.pages.length===1&&first.progress.draft.note==='Unfinished annotation '+lang&&first.pdf_attachment_uid===null);
    await screen(page,lang+'-01-saved-progress',page.locator('[data-visual-save-panel]'));
    await stop();await start();await page.goto(base);await visual(page,slug);
    check(lang+' saved review survives a real server restart',await page.locator('[data-visual-saved-id="'+first.uid+'"]').count()===1);
    await upload(page,mismatch);const denied=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/'+first.uid+'/open'));
    await page.locator('[data-visual-saved-id="'+first.uid+'"] [data-visual-action="resume-file"]').click();check(lang+' same-content PDF with different bytes cannot adopt saved progress',(await denied).status()===409);
    await upload(page,file);const resumed=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/'+first.uid+'/open'));
    await page.locator('[data-visual-saved-id="'+first.uid+'"] [data-visual-action="resume-file"]').click();check(lang+' original bytes reopen the historical linked revision',(await resumed).status()===200);
    await page.waitForFunction(()=>document.querySelector('.insights-pdf-preview img')?.src.includes('/page/2'));
    await page.locator('.insights-pdf-preview img').evaluate(node=>node.decode());
    check(lang+' controls restore page two draft author notes and pending issue',await page.locator('.insights-pdf-preview img').getAttribute('alt')===({es:'Página real 2',en:'Actual page 2',pt:'Página real 2'})[lang]&&await notes.nth(0).inputValue()==='Unfinished annotation '+lang&&await notes.nth(1).inputValue()==='Private general note '+lang&&await page.locator('[data-insights-action="remove-visual-issue"]').count()===1);
    await page.locator('[data-visual-keep-pdf]').check();const withCopy=await save(page,slug);check(lang+' private PDF copy requires the explicit checkbox',Boolean(withCopy.pdf_attachment_uid)&&withCopy.uid===first.uid&&withCopy.revision===first.revision);
    await stop();await start();await page.goto(base);await visual(page,slug);
    const copied=page.waitForResponse(response=>new URL(response.url()).pathname.endsWith('/'+first.uid+'/open'));
    await page.locator('[data-visual-saved-id="'+first.uid+'"] [data-visual-action="resume-copy"]').click();check(lang+' private copy reopens after server restart without a user file',(await copied).status()===200);
    await page.locator('.insights-pdf-preview img').evaluate(node=>node.decode());await screen(page,lang+'-02-resumed-copy',page.locator('.insights-pdf-preview'));
    await page.locator('[data-insights-check="visual-resolved"]').check();await notes.nth(0).fill('');await page.locator('[data-insights-field="decision"]').selectOption('accepted');
    const resolved=await save(page,slug);check(lang+' resolving pending issue permits a self-declared decision without certification',resolved.progress.pages[0].resolved&&resolved.progress.decision==='accepted'&&resolved.author_identity==='local_self_declaration'&&resolved.automated_layout_verification===false&&resolved.original_word_verified===false);
    await page.setViewportSize({width:390,height:844});await screen(page,lang+'-03-mobile-saved',page.locator('[data-visual-save-panel]'));
    check(lang+' mobile saved controls fit without horizontal page overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    await page.locator('[data-visual-keep-pdf]').uncheck();const withoutCopy=await save(page,slug);check(lang+' unchecking removes current PDF copy while retaining progress',withoutCopy.pdf_attachment_uid===null&&withoutCopy.progress.page===2);
    const deleted=page.waitForResponse(response=>response.request().method()==='DELETE'&&new URL(response.url()).pathname.endsWith('/'+first.uid));
    await page.locator('[data-visual-saved-id="'+first.uid+'"] [data-visual-action="delete-saved"]').click();const deletion=await deleted;check(lang+' explicit delete removes current saved review',deletion.status()===200&&(await deletion.json()).records.length===0);
    await page.locator('[data-visual-saved-id="'+first.uid+'"]').waitFor({state:'detached'});
    const history=fs.readdirSync(path.join(workspace,'projects',slug,'history','snapshots'));check(lang+' prior versions remain recoverable after current-state cleanup',history.length>=4);
    await context.close();
  }
  check('Three exact-byte mismatch rejections are expected and bounded',result.expectedApiErrors.length===3,result.expectedApiErrors);
  check('No unexpected API errors',result.unexpectedApiErrors.length===0,result.unexpectedApiErrors);check('No JavaScript page errors',result.pageErrors.length===0,result.pageErrors);check('No external requests',result.externalRequests.length===0,result.externalRequests);
  result.sourceEnd=hashes();check('Acceptance source is unchanged throughout the run',JSON.stringify(result.sourceStart)===JSON.stringify(result.sourceEnd));result.complete=true;write();
}catch(error){result.failure=String(error.stack||error);write();process.exitCode=1;}finally{if(browser)await browser.close();await stop();}})();
