/* Native browser journey for the guided delivery; only normal project APIs. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const root=path.resolve(option('--tool',process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'))),out=path.resolve(option('--output','out/delivery-flow-0410'));
const playwright=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]})),engine=option('--browser','chromium');
assert.ok(['chromium','firefox'].includes(engine));fs.mkdirSync(out,{recursive:true});
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-delivery-0410-'));fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const hash=file=>crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const sourcePaths=['webapp/static/delivery-flow.js','webapp/static/delivery-flow.css','webapp/static/insights.js','webapp/static/experience.js','webapp/static/studio.js','webapp/static/app.js','webapp/audience_api.py','webapp/progress_api.py'];
const sourceHashes=()=>Object.fromEntries(sourcePaths.map(file=>[file,hash(path.join(root,file))]));
const results={schema:'report-gen-guided-delivery-browser/1',browserEngine:engine,checks:[],screenshots:[],downloads:[],pageErrors:[],consoleErrors:[],externalRequests:[],sourceHashes:sourceHashes()};
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
const check=(name,passed,detail)=>{results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name);console.log('PASS '+name);};
let browser,timer;
const server=spawn(process.env.RG_PYTHON||'python',[root+'/scripts/browser-server-0211.py','--workspace',workspace],{cwd:root,env:{...process.env,PYTHONPATH:root}});server.stderr.on('data',bytes=>fs.appendFileSync(path.join(out,'server.log'),bytes));
(async()=>{try{
  const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server startup timeout')),30000);server.stdout.on('data',bytes=>{text+=bytes;for(const line of text.split('\n'))try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});server.on('exit',code=>reject(Error('Server exited '+code)));});
  browser=await playwright[engine].launch({headless:process.env.RG_HEADLESS!=='0',...(engine==='chromium'?{executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']}: {})});results.browserVersion=browser.version();
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
  await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){results.externalRequests.push(url);return route.abort();}return route.continue();});
  const page=await context.newPage();page.on('pageerror',error=>results.pageErrors.push(String(error)));page.on('console',message=>{if(message.type()==='error')results.consoleErrors.push(message.text());});page.on('dialog',dialog=>dialog.accept());
  await page.goto(base);await page.waitForFunction(()=>typeof DeliveryFlowUI!=='undefined'&&!document.getElementById('splash'));
  async function screenshot(name){const file=path.join(out,name+'.png');await page.screenshot({path:file,fullPage:true});results.screenshots.push({file:path.basename(file),sha256:hash(file),bytes:fs.statSync(file).size});save();}
  async function geometry(label){check(label,await page.evaluate(()=>{const box=document.querySelector('[data-delivery-flow]'),nav=box?.querySelector('nav');return !!box&&document.documentElement.scrollWidth<=innerWidth+1&&nav.getBoundingClientRect().right<=innerWidth+1&&[...nav.querySelectorAll('button')].every(node=>node.getBoundingClientRect().height>=44);}));}
  const action=name=>page.locator('[data-delivery-action="'+name+'"]');
  for(const lang of ['es','en','pt']){
    await page.evaluate(async language=>{setUiLang(language);const response=await requireOk(await api.post('/api/demo',{lang:language})),data=await response.json();await refreshProjects();await loadProject(data.slug);select('studio','deliver');},lang);
    await page.waitForFunction(()=>document.querySelector('[data-delivery-flow]')?.dataset.deliveryCurrent==='true');
    const initial=await page.evaluate(()=>({etag:projectStore.etag,data:JSON.stringify(S.data)}));
    check(lang+': review separates blocking errors and recommendations',await page.locator('[data-delivery-issues="error"]').count()===1&&await page.locator('[data-delivery-issues="warning"]').count()===1&&await action('step-3').isDisabled());
    const issues=page.locator('[data-delivery-issues="warning"]');await issues.locator('summary').click();
    await issues.locator('[data-delivery-action="issue"]').first().click();await page.waitForFunction(()=>S.sel.type!=='studio');
    check(lang+': a known observation opens its editor location without changing content',await page.evaluate(before=>JSON.stringify(S.data)===before.data&&projectStore.etag===before.etag,initial));
    await page.locator('[data-studio-nav="deliver"]').click();await page.waitForFunction(()=>document.querySelector('[data-delivery-flow]')?.dataset.deliveryCurrent==='true');
    for(const [label,size]of [['desktop',{width:1440,height:1000}],['mobile',{width:390,height:844}]]){
      await page.setViewportSize(size);await geometry(lang+': '+label+' step navigation stays inside viewport with touch-sized controls');await screenshot(lang+'-'+label+'-review');
    }
    await page.setViewportSize({width:1440,height:1000});await action('review-next').focus();await page.keyboard.press('Space');
    check(lang+': native keyboard changes the step and focuses its heading',await page.evaluate(()=>document.activeElement.id==='deliveryStep1'&&!document.querySelector('[data-delivery-step="1"]').hidden));
    await screenshot(lang+'-desktop-audience');await page.setViewportSize({width:390,height:844});await screenshot(lang+'-mobile-audience');
    await action('audience-next').click();await action('preview').click();await page.waitForFunction(()=>document.querySelector('[data-delivery-flow]').dataset.deliveryPreviewCurrent==='true');
    check(lang+': preview is the saved revision and requires explicit acknowledgement',await page.locator('[data-delivery-publication]').innerText().then(text=>text.includes(initial.etag.replaceAll('"','')))&&!await page.locator('[data-delivery-preview-confirm]').isChecked()&&await action('step-3').isDisabled());
    await geometry(lang+': long publication text stays inside the narrow viewport');await screenshot(lang+'-mobile-preview');await page.setViewportSize({width:1440,height:1000});await screenshot(lang+'-desktop-preview');
    await page.locator('[data-delivery-preview-confirm]').check();await action('preview-next').click();
    await page.locator('[data-flow-delivery-format="pdf"]').uncheck();await page.locator('[data-flow-delivery-format="docx"]').uncheck();await page.locator('[data-flow-delivery-format="md"]').check();await page.locator('[data-flow-delivery-format="html"]').check();
    await page.locator('[data-flow-delivery="label"]').fill('Guided '+lang+' delivery');if(await page.locator('[data-flow-delivery="ack"]').isVisible())await page.locator('[data-flow-delivery="ack"]').check();
    await screenshot(lang+'-desktop-export');await page.setViewportSize({width:390,height:844});await geometry(lang+': final export controls reflow on mobile');await screenshot(lang+'-mobile-export');
    if(lang==='es'){
      await page.waitForFunction(()=>{const pending=PendingUI.active.get(S.slug+'|delivery:settings');return pending?.revision>0&&pending.persisted===pending.revision;});
      const record=await page.evaluate(async()=>({slug:S.slug,row:(await PendingUI.list(S.slug)).find(row=>row.key==='delivery:settings')}));
      check('Saved delivery settings exclude preview and publication consents',Object.keys(record.row.data).sort().join()==='formats,kind,label');
      await page.reload();await page.waitForFunction(()=>typeof DeliveryFlowUI!=='undefined'&&!document.getElementById('splash'));
      await page.evaluate(async slug=>{await loadProject(slug);await StudioUI.recovery();},record.slug);
      await page.locator('[data-pending-record="'+record.row.id+'"]').getByRole('button',{name:'Recuperar formulario',exact:true}).click();
      await page.waitForFunction(()=>document.querySelector('[data-delivery-flow]')?.dataset.deliveryCurrent==='true');
      check('Reload recovery preserves delivery settings while requiring a new preview',await page.locator('[data-flow-delivery="label"]').inputValue()==='Guided es delivery'&&await page.locator('[data-flow-delivery-format="md"]').isChecked()&&await page.locator('[data-flow-delivery-format="html"]').isChecked()&&!await page.locator('[data-flow-delivery-format="pdf"]').isChecked()&&!await page.locator('[data-delivery-preview-confirm]').isChecked()&&await action('step-3').isDisabled());
      await action('review-next').click();await action('audience-next').click();await action('preview').click();await page.waitForFunction(()=>document.querySelector('[data-delivery-flow]').dataset.deliveryPreviewCurrent==='true');await page.locator('[data-delivery-preview-confirm]').check();await action('preview-next').click();if(await page.locator('[data-flow-delivery="ack"]').isVisible())await page.locator('[data-flow-delivery="ack"]').check();
    }
    const queuedPromise=page.waitForResponse(response=>response.request().method()==='POST'&&/\/projects\/[^/]+\/jobs$/.test(new URL(response.url()).pathname));await action('generate').click();const queued=await queuedPromise,job=await queued.json();
    check(lang+': complete delivery enqueues the exact reviewed revision',queued.status()===202&&queued.request().headers()['if-match']===initial.etag);
    await page.waitForFunction(async id=>{const job=await api.get('/api/jobs/'+id);if(job.stage==='error')throw Error(job.error);return job.stage==='done';},job.id,{timeout:120000});
    const verification=await page.evaluate(id=>api.get('/api/jobs/'+id+'/verification'),job.id);
    const verifiedFiles=Object.entries(verification.files||{});
    check(lang+': queued Markdown and HTML files pass production export verification',verifiedFiles.length===2&&verifiedFiles.every(([,file])=>file.sha256&&file.bytes>0),verifiedFiles.map(([name,file])=>({name,bytes:file.bytes,sha256:file.sha256})));
    const zip=await page.request.get(base+'/api/jobs/'+job.id+'/download');assert.equal(zip.status(),200);const file=path.join(out,lang+'-complete-delivery.zip');fs.writeFileSync(file,await zip.body());results.downloads.push({file:path.basename(file),sha256:hash(file),bytes:fs.statSync(file).size,revision:initial.etag});
    await page.keyboard.press('Escape');
    await page.setViewportSize({width:1440,height:1000});await action('step-1').click();await page.locator('input[name="delivery-destination"][value="audience"]').check();await page.locator('[data-insights-field="profile"]').waitFor();
    await page.locator('[data-insights-field="profile"]').selectOption('executive');await action('audience-next').click();await page.locator('[data-insights-action="preview-audience"]').click();await page.waitForFunction(()=>document.querySelector('[data-delivery-flow]').dataset.deliveryPreviewCurrent==='true');
    check(lang+': executive plan shows real outgoing text without approving it',await page.locator('.insights-context').innerText().then(text=>text.length>100)&&!await page.locator('[data-delivery-preview-confirm]').isChecked());await screenshot(lang+'-desktop-executive-preview');
    await action('step-1').click();await page.locator('[data-insights-field="title"]').fill('Revised '+lang+' audience');
    check(lang+': editing audience options invalidates preview and export',await page.evaluate(()=>document.querySelector('[data-delivery-flow]').dataset.deliveryPreviewCurrent==='false')&&await page.locator('[data-insights-action="export-audience"]').isDisabled());
    await page.evaluate(()=>{S.data.meta.title+=' changed';scheduleSave();projectStore.timers.clearTimeout(projectStore.timer);projectStore.timer=null;});
    check(lang+': a dirty project cannot continue with a previous revision',await action('step-2').isDisabled()&&await action('step-3').isDisabled());
    await action('step-0').click();await action('check').click();await page.waitForFunction(()=>document.querySelector('[data-delivery-flow]').dataset.deliveryCurrent==='true');
    check(lang+': explicit recheck saves changed content and keeps the old preview invalid',await page.evaluate(previous=>!projectStore.dirty&&projectStore.etag!==previous&&document.querySelector('[data-delivery-flow]').dataset.deliveryPreviewCurrent==='false',initial.etag));
  }
  results.finalSourceHashes=sourceHashes();check('Source bytes remain unchanged through the browser journey',JSON.stringify(results.sourceHashes)===JSON.stringify(results.finalSourceHashes));
  check('No JavaScript, console, or external-request errors',!results.pageErrors.length&&!results.consoleErrors.length&&!results.externalRequests.length,{pageErrors:results.pageErrors,consoleErrors:results.consoleErrors,externalRequests:results.externalRequests});
  results.status='passed';results.scope='Actual browser keyboard, layout and screenshot journey in ES/EN/PT at desktop/mobile sizes; real queued Markdown/HTML ZIP exports; publication review is explicitly human and Word is outside this test.';save();
}finally{clearTimeout(timer);await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{results.status='failed';results.error=String(error.stack||error);save();console.error(error);process.exitCode=1;});
