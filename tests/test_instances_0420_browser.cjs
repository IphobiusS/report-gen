/* Real Chromium/server acceptance. Requires an installed Playwright browser. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const out=path.resolve(option('--output','out/instances-0420'));
const {chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
fs.mkdirSync(out,{recursive:true});
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-instances-'));
fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const result={checks:[],pageErrors:[],externalRequests:[]};
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2));
const check=(name,value)=>{result.checks.push({name,passed:!!value});save();assert.ok(value,name);console.log('PASS '+name);};
let server,browser,page;
async function start(){
  server=spawn(process.env.RG_PYTHON||'python',[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:{...process.env,REPORT_GEN_UI_LANG:'en'}});
  server.stderr.on('data',chunk=>fs.appendFileSync(path.join(out,'server.log'),chunk));
  return new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Instance server startup timeout')),20000);server.stdout.on('data',chunk=>{text+=chunk;for(const line of text.split('\n'))try{const row=JSON.parse(line);if(row.url){clearTimeout(timer);resolve(row.url);}}catch{}});server.on('exit',code=>{clearTimeout(timer);reject(Error('Server exited '+code));});});
}
async function ready(){await page.waitForFunction(()=>typeof InstancesUI!=='undefined'&&!document.querySelector('#splash')&&!projectBusyCount&&!projectStore.loading);}
(async()=>{try{
  const base=await start();browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']});
  result.browser=browser.version();const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){result.externalRequests.push(url);return route.abort();}return route.continue();});
  page=await context.newPage();page.on('pageerror',error=>{result.pageErrors.push(String(error));save();});page.on('dialog',dialog=>dialog.accept());
  await page.addInitScript(()=>localStorage.setItem('rg.previewVisible','0'));await page.goto(base);await ready();
  await page.evaluate(async()=>{
    await requireOk(await api.post('/api/projects',{slug:'instances',title:'Fictional Aster instance review'}));await refreshProjects();await loadProject('instances');
    S.data.meta.assessor='Synthetic reviewer';
    const f={uid:WorkflowUI.uid(),id:'F1',mode:'vuln',severity:'high',title:'Synthetic cross-tenant authorization',status:'in_progress',instances:[]};
    for(let i=0;i<18;i++)f.instances.push({uid:WorkflowUI.uid(),endpoint:'/v2/accounts/SYNTH-'+String(i+1).padStart(3,'0'),identity:'Operator '+(i%4+1),owner:'Synthetic API team',status:i<15?'verified_fixed':i===17?'blocked':'open',evidence_uids:[],retests:i<15?[{uid:WorkflowUI.uid(),tested_on:'2026-10-17',assessor:'Synthetic reviewer',result:'fixed',notes_md:'Invented comparison retained for acceptance.',evidence_uids:[]}]:[]});
    S.data.findings=[f];S.data.finding_sequence=1;scheduleSave();if(!await doSave())throw Error('Fixture save failed');select('finding',0);
  });await ready();
  check('Eighteen occurrences preserve fifteen fixed, two open and one blocked',await page.evaluate(()=>{const rows=S.data.findings[0].instances;return rows.length===18&&rows.filter(i=>i.status==='verified_fixed').length===15&&rows.filter(i=>i.status==='open').length===2&&rows.filter(i=>i.status==='blocked').length===1&&S.data.findings[0].status==='in_progress';}));
  for(const lang of ['es','en','pt']){
    await page.evaluate(lang=>{setUiLang(lang);select('finding',0);},lang);await page.locator('[data-instances-finding]').scrollIntoViewIfNeeded();
    check(lang+' instance panel renders independent history',await page.locator('[data-instance-uid]').count()===18&&await page.locator('.instance-summary').innerText().then(text=>text.includes('15')&&text.includes('18')));
    await page.screenshot({path:path.join(out,'instances-'+lang+'.png'),fullPage:false});
  }
  await page.evaluate(()=>setUiLang('en'));await page.locator('[data-instance-create]').click();await page.locator('[data-instance-field="endpoint"]').fill('/v2/accounts/SYNTH-NEW');await page.locator('[data-instance-field="owner"]').fill('Draft owner');
  await page.waitForFunction(()=>{const handle=[...PendingUI.active.values()].find(h=>h.key.startsWith('instance:'));return handle?.revision&&handle.persisted===handle.revision;});
  check('Pending form commits privately before report mutation',await page.evaluate(async()=>S.data.findings[0].instances.length===18&&(await PendingUI.list(S.slug)).some(row=>row.key.startsWith('instance:')&&row.data.values.owner==='Draft owner')));
  await page.keyboard.press('Escape');await page.locator('[data-instance-create]').click();check('Closing and reopening restores the pending local form',await page.locator('[data-instance-field="owner"]').inputValue()==='Draft owner');
  await page.locator('[data-instance-save]').click();await page.waitForFunction(()=>!projectBusyCount&&!document.querySelector('[data-instance-dialog]'));
  check('Explicit create saves the nineteenth occurrence without closing others',await page.evaluate(()=>S.data.findings[0].instances.length===19&&S.data.findings[0].status==='in_progress'));
  await page.evaluate(()=>InstancesUI.open(S.data.findings[0],S.data.findings[0].instances.at(-1),'retest'));await page.locator('[data-instance-field="notes_md"]').fill('Synthetic role comparison: denied unrelated role; retained owner role.');await page.locator('[data-instance-field="result"]').selectOption('fixed');
  await page.screenshot({path:path.join(out,'instance-retest.png'),fullPage:false});await page.locator('[data-instance-save]').click();await page.waitForFunction(()=>!projectBusyCount&&!document.querySelector('[data-instance-dialog]'));
  check('Retest closes only the selected occurrence',await page.evaluate(()=>S.data.findings[0].instances.filter(i=>i.status==='verified_fixed').length===16&&S.data.findings[0].status==='in_progress'));
  await page.setViewportSize({width:390,height:844});await page.locator('[data-instances-finding]').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'instances-mobile.png'),fullPage:false});
  check('Instance workspace stays within a narrow viewport',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  check('No browser errors or external scenario connections',result.pageErrors.length===0&&result.externalRequests.length===0);save();
}catch(error){result.error=String(error.stack||error);save();if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw error;}finally{await browser?.close();if(server&&server.exitCode===null){server.kill('SIGTERM');await new Promise(resolve=>server.once('exit',resolve));}fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{console.error(error);process.exitCode=1;});
