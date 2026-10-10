/* Real owner delivery, stale-preview replacement, bounded ledger and recovery. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn,execFileSync}=require('node:child_process');
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const root=path.resolve(option('--tool',process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'))),out=path.resolve(option('--output','out/remediation-delivery-0300'));
const python=process.env.RG_PYTHON||'python';
const {chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
fs.mkdirSync(out,{recursive:true});
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-remediation-return-'));fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const results={checks:[],pageErrors:[],externalRequests:[]},save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
function check(name,passed,detail){results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name);console.log('PASS '+name);}
const server=spawn(python,[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:{...process.env,PYTHONPATH:root+path.delimiter+path.join(root,'webapp')}});
server.stderr.on('data',value=>fs.appendFileSync(path.join(out,'server.log'),value));
let timer,browser,page;
(async()=>{try{
 const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server timeout')),20000);server.stdout.on('data',value=>{text+=value;for(const line of text.split('\n'))try{const parsed=JSON.parse(line);if(parsed.url){clearTimeout(timer);resolve(parsed.url);}}catch{}});server.on('exit',code=>reject(Error('Server exited '+code)));});
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||undefined,args:['--no-sandbox']});results.browser=browser.version();
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
 await context.route('**/*',route=>{if(/^https?:/.test(route.request().url())&&!route.request().url().startsWith(base+'/')){results.externalRequests.push(route.request().url());return route.abort();}return route.continue();});
 page=await context.newPage();page.on('pageerror',error=>results.pageErrors.push(String(error)));
 await page.goto(base);await page.waitForFunction(()=>typeof RemediationUI!=='undefined'&&!document.getElementById('splash'));
 await page.evaluate(async()=>{
  await requireOk(await api.post('/api/projects',{slug:'return-fixture',title:'Synthetic return'}));await refreshProjects();await loadProject('return-fixture');
  S.data.finding_sequence=2;
  S.data.findings=[{uid:WorkflowUI.uid(),id:'F1',mode:'vuln',title:'Synthetic finding',severity:'high',description_md:'Original description',owner:'Initial owner',due_date:'2026-11-20',status:'open',verification:'confirmed',retests:[{uid:WorkflowUI.uid(),tested_on:'2026-10-01',assessor:'Evaluator',result:'open',notes_md:'Original retest'}]},
    {uid:WorkflowUI.uid(),id:'F2',mode:'vuln',title:'Unassigned finding',severity:'low'}];
  scheduleSave();await doSave();select('workflow','remediation_tasks');
 });
 await page.evaluate(async()=>{S.data.findings[1].owner='Second owner';S.data.findings[0].reported_remediation='Private communication shown for review';scheduleSave();await doSave();select('workflow','remediation_tasks');setPreviewVisible(true);setPreviewMode('live');});
 await page.waitForFunction(()=>WorkbenchUI.hasLivePreview()&&document.getElementById('pdfPreview').contentDocument?.body.textContent.includes('Initial owner'));
 await page.locator('[data-remediation-return] > details > summary').first().click();
 await page.locator('[data-return-finding]').first().check();await page.locator('[data-return-private]').check();await page.locator('[data-return-retention]').check();
 check('Owner ZIP remains disabled until an exact preview',await page.locator('[data-return-delivery-export]').isDisabled());
 const unchanged=await page.evaluate(()=>JSON.stringify(S.data));
 await page.locator('[data-return-delivery-preview]').click();await page.waitForFunction(()=>!document.querySelector('[data-return-delivery-export]').disabled);
 check('Owner preview exposes every editable CSV value but excludes unselected card title',await page.locator('[data-return-delivery-rows]').textContent().then(text=>text.includes('Private communication shown for review')&&text.includes('Initial owner')&&!text.includes('Synthetic finding'))&&await page.evaluate(v=>JSON.stringify(S.data)===v,unchanged));
 await page.locator('[data-remediation-field="title"]').check();
 check('Changing included card fields invalidates owner ZIP preview',await page.locator('[data-return-delivery-export]').isDisabled()&&await page.locator('[data-return-delivery-rows] .rt-card').count()===0);
 await page.locator('[data-return-finding]').nth(1).check();await page.locator('[data-return-delivery-preview]').click();await page.waitForFunction(()=>!document.querySelector('[data-return-delivery-export]').disabled);
 check('Both selected owners are represented in the exact preview',await page.locator('[data-return-delivery-rows] .rt-card').count()===2);
 await context.route(base+'/api/projects/return-fixture/remediation-tasks/delivery-export',route=>route.fulfill({status:503,contentType:'application/json',body:'{"error":"temporary"}'}));
 await page.locator('[data-return-delivery-export]').click();await page.waitForFunction(()=>projectBusyCount===0&&document.querySelector('[data-return-status]').textContent.includes('error sin verificar'));
 check('Failed ZIP issuance keeps findings selected and preview available for retry',await page.locator('[data-return-finding]:checked').count()===2&&await page.locator('[data-return-delivery-export]').isEnabled()&&await page.evaluate(()=>!S.data.remediation_exchanges?.length));
 await context.unroute(base+'/api/projects/return-fixture/remediation-tasks/delivery-export');
 const downloading=page.waitForEvent('download');await page.locator('[data-return-delivery-export]').click();const download=await downloading;const archive=path.join(out,'delivery.zip');await download.saveAs(archive);
 await page.waitForFunction(()=>projectBusyCount===0&&S.data.remediation_exchanges?.length===1);
 const csvFile=path.join(out,'returned.csv');
 const archiveProof=JSON.parse(execFileSync(python,['-c',`import csv,hashlib,io,json,sys,zipfile
with zipfile.ZipFile(sys.argv[1]) as z:
 m=json.loads(z.read('manifest.json'));assert len(m['owners'])==2
 assert all(hashlib.sha256(z.read(k)).hexdigest()==v for k,v in m['files'].items())
 rows=list(csv.reader(io.StringIO(z.read('owner-001/return.csv').decode('utf-8-sig'))));rows[1][4]="'New reviewed owner"
 with open(sys.argv[2],'w',encoding='utf-8-sig',newline='') as f:csv.writer(f,quoting=csv.QUOTE_ALL).writerows(rows)
 print(json.dumps({'owners':len(m['owners']),'sha256':hashlib.sha256(open(sys.argv[1],'rb').read()).hexdigest(),'source':m['source_revision']}))`,archive,csvFile],{encoding:'utf8'}));
 check('Downloaded ZIP verifies all member hashes and saved issuance references exact artifact',await page.evaluate(proof=>{const event=S.data.remediation_exchanges[0].events[0];return event.sha256===proof.sha256&&event.source_revision===proof.source&&event.count===2;},archiveProof));
 await page.locator('[data-return-file]').setInputFiles(csvFile);await page.locator('[data-return-preview]').click();await page.waitForFunction(()=>document.querySelectorAll('[data-return-change]').length===1);
 await page.locator('[data-return-change]').check();await page.locator('[data-return-reviewed]').check();
 await page.waitForFunction(()=>WorkbenchUI.hasLivePreview());
 let previewReceived=false,release;const pending=new Promise(resolve=>release=resolve);
 await context.route(base+'/api/projects/return-fixture/preview',async route=>{const response=await route.fetch();previewReceived=true;await pending;await route.fulfill({response});});
 await page.locator('[data-return-apply]').click();
 for(let n=0;!previewReceived&&n<500;n++)await page.waitForTimeout(10);assert.ok(previewReceived,'Actual updated preview request received');
 check('Return mutation invalidates stale preview before the replacement loads',await page.evaluate(()=>S.data.findings[0].owner==='New reviewed owner'&&!WorkbenchUI.hasLivePreview()&&document.getElementById('previewFreshness').dataset.stale==='true'&&document.getElementById('pdfPreview').contentDocument.body.textContent.includes('Initial owner')));
 release();await page.waitForFunction(()=>WorkbenchUI.hasLivePreview()&&document.getElementById('pdfPreview').contentDocument.body.textContent.includes('New reviewed owner'));
 check('Replacement preview contains new owner and only then claims current revision',await page.locator('#previewFreshness').getAttribute('data-stale')==='false');
 await context.unroute(base+'/api/projects/return-fixture/preview');
 await page.locator('[data-return-ledger] > summary').click();
 check('Ledger separates issuance, registered receipt and accepted change with exact source revisions',await page.locator('[data-return-ledger]').textContent().then(text=>text.includes('Emitido localmente')&&text.includes('Recepción registrada')&&text.includes('Cambios aceptados')&&text.includes(archiveProof.source)));
 await page.locator('[data-return-file]').setInputFiles(csvFile);await page.locator('[data-return-preview]').click();await page.waitForFunction(()=>document.querySelector('[data-return-status]').textContent.includes('0 cambios'));
 check('Unchanged returned CSV can be received explicitly without applying fields',await page.locator('[data-return-receive]').isEnabled()&&await page.locator('[data-return-apply]').isDisabled());
 await page.locator('[data-return-receive]').click();await page.waitForFunction(()=>projectBusyCount===0&&document.querySelector('[data-return-file]').files.length===0);
 check('Duplicate explicit receipt keeps bounded ledger without adding fake acceptance',await page.evaluate(()=>S.data.remediation_exchanges[0].events.length===3&&S.data.findings[0].owner==='New reviewed owner'));
 await page.locator('[data-return-ledger] > summary').click();await page.locator('[data-return-ledger-batch] > summary').click();page.once('dialog',dialog=>dialog.accept());await page.getByRole('button',{name:'Revocar este lote',exact:true}).click();await page.waitForFunction(()=>projectBusyCount===0&&S.data.remediation_exchanges[0].revoked);
 await page.locator('[data-return-file]').setInputFiles(csvFile);await page.locator('[data-return-preview]').click();await page.waitForFunction(()=>document.querySelector('[data-return-status]').textContent.includes('caducó'));
 check('Revoked batch cannot be compared or accepted and finding owner is preserved',await page.locator('[data-return-apply]').isDisabled()&&await page.evaluate(()=>S.data.findings[0].owner==='New reviewed owner'));
 await page.locator('[data-remediation-return] > details > summary').first().click();await page.locator('[data-return-finding]').first().check();await page.locator('[data-return-private]').check();await page.locator('[data-return-retention]').check();
 await context.route(base+'/api/projects/return-fixture',route=>route.fulfill({status:503,contentType:'application/json',body:'{"error":"refresh failure"}'}));
 const recoveryDownload=page.waitForEvent('download');await page.locator('[data-return-issue]').click();const retainedDownload=await recoveryDownload;await retainedDownload.saveAs(path.join(out,'issued-despite-refresh-failure.csv'));
 await page.waitForFunction(()=>projectBusyCount===0&&document.querySelector('[data-return-status]').textContent.includes('la asignación se guardó'));
 check('Committed issuance still downloads its artifact when subsequent project refresh fails',fs.readFileSync(path.join(out,'issued-despite-refresh-failure.csv'),'utf8').includes('report-gen-remediation-return-1')&&await page.evaluate(()=>S.data.remediation_exchanges.length===1));
 await context.unroute(base+'/api/projects/return-fixture');
 await page.locator('[data-remediation-refresh]').click();await page.waitForFunction(()=>projectBusyCount===0&&S.data.remediation_exchanges.length===2);
 check('Reload recovers the committed receipt after refresh failure without duplicate issuance',await page.evaluate(()=>S.data.remediation_exchanges.length===2));
 await page.evaluate(()=>{setUiLang('en');select('workflow','remediation_tasks');});await page.locator('[data-return-ledger] > summary').click();await page.locator('[data-return-ledger-batch] > summary').first().click();
 await page.setViewportSize({width:320,height:1000});
 await page.evaluate(()=>{const nodes=[...document.querySelectorAll('[data-remediation-view], [data-remediation-view] *')];const sizes=nodes.map(n=>parseFloat(getComputedStyle(n).fontSize));nodes.forEach((n,i)=>n.style.fontSize=sizes[i]*2+'px');});
 check('English delivery ledger reflows at 320 px with 200% text',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 const axeSource=fs.readFileSync(option('--axe',process.env.AXE_CORE_PATH)||require.resolve('axe-core/axe.min.js',{paths:[root]}),'utf8');await page.evaluate(axeSource);
 const axe=await page.evaluate(async()=>{const r=await axe.run(document.querySelector('[data-remediation-return]'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return {violations:r.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})),incomplete:r.incomplete.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)}))};});
 results.axe=axe;check('Delivery and event ledger have no automatic accessibility violations',axe.violations.length===0,axe.violations);
 await page.mouse.move(310,5);await page.keyboard.press('Escape');
 await page.screenshot({path:path.join(out,'delivery-ledger-mobile-200.png'),fullPage:true});
 check('No browser errors or external requests',results.pageErrors.length===0&&results.externalRequests.length===0);save();
 }catch(error){if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw error;}finally{clearTimeout(timer);await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{results.error=String(error.stack||error);save();console.error(error);process.exitCode=1;});
