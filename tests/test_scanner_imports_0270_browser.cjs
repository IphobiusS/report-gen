/* Real UI intake with offline inputs; no scanner execution or target requests. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),output=args.includes('--output')?args[args.indexOf('--output')+1]:'out/scanner-imports-0270',out=path.resolve(output);
fs.mkdirSync(out,{recursive:true});
const results={checks:[],pageErrors:[],external:[]};
function save(){fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));}
function check(name,ok,detail){results.checks.push({name,passed:!!ok,...(detail?{detail}:{})});save();assert.ok(ok,name);console.log('PASS '+name);}
const server=spawn(process.env.RG_PYTHON||'python',[path.join(root,'scripts/browser-server-0212.py')],{cwd:root});
server.stderr.on('data',value=>fs.appendFileSync(path.join(out,'server.log'),value));
let browser,page,timer;
const nuclei=JSON.stringify({'template-id':'synthetic-header','matched-at':'https://example.test/','matcher-name':'header',type:'http',info:{name:'Synthetic <img src=x onerror=alert(1)>',severity:'low',description:'Observed candidate',reference:['https://example.test/advisory']},request:'GET / HTTP/1.1\r\nHost: example.test\r\n\r\n'});
const nmap='<?xml version="1.0"?><!DOCTYPE nmaprun><nmaprun scanner="nmap" version="7.99"><host><status state="up"/><address addr="192.0.2.1" addrtype="ipv4"/><ports><port portid="22" protocol="tcp"><state state="open"/><service name="ssh" product="OpenSSH" version="9.0"/></port><port portid="53" protocol="udp"><state state="open|filtered"/><service name="domain"/></port></ports></host><runstats><finished exit="success"/></runstats></nmaprun>';
(async()=>{try{
  const base=await new Promise((resolve,reject)=>{let raw='';timer=setTimeout(()=>reject(Error('Server timeout')),20000);server.stdout.on('data',part=>{raw+=part;if(raw.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(raw.split('\n')[0]).url);}catch(e){reject(e);}}});server.on('exit',code=>reject(Error('Server exited '+code)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||undefined});
  results.browser=browser.version();
  const context=await browser.newContext({viewport:{width:1366,height:1000},reducedMotion:'reduce'});
  page=await context.newPage();page.on('pageerror',e=>results.pageErrors.push(String(e)));
  page.on('request',r=>{if(!r.url().startsWith(base)&&!r.url().startsWith('data:')&&!r.url().startsWith('blob:'))results.external.push(r.url());});
  await page.addInitScript(()=>localStorage.setItem('rg.previewVisible','0'));
  await page.goto(base);await page.locator('.workspace-dashboard').waitFor();
  await page.locator('.workspace-hero-actions .primary').click();
  await page.waitForFunction(()=>S.slug&&S.data?.findings?.length&&!projectStore.loading&&!projectBusyCount);
  const original=await page.evaluate(()=>({findings:S.data.findings.length,assets:S.data.assets.length,coverage:S.data.coverage.length}));
  async function intake(format,raw){
    if(!await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();
    if(!await page.locator('#projectActions').evaluate(el=>el.open))await page.locator('#projectActions > summary').click();
    await page.locator('#intakeBtn').click();const d=page.locator('dialog.progress-dialog');await d.waitFor();
    await d.getByLabel('Formato',{exact:true}).selectOption(format);
    await d.locator('input[type=file]').setInputFiles({name:format+(format==='nuclei'?'.jsonl':'.xml'),mimeType:'text/plain',buffer:Buffer.from(raw)});
    await d.locator('[data-import-panel="2"]').waitFor({state:'visible'});
    await d.getByRole('button',{name:'Revisar selección',exact:true}).click();
    await d.locator('[data-import-panel="3"]').waitFor({state:'visible'});return d;
  }
  let d=await intake('nuclei',nuclei+'\n'+nuclei);
  check('Nuclei duplicate preview selects just one candidate',await d.locator('[data-intake-row="0"]').isChecked()&&!await d.locator('[data-intake-row="1"]').isChecked());
  check('Preview leaves project unchanged',await page.evaluate(n=>S.data.findings.length===n,original.findings));
  check('Scanner title is inert text',await d.locator('.intake-rows img').count()===0&&(await d.locator('.intake-rows').innerText()).includes('<img src=x'));
  await d.locator('.intake-rows details').first().locator('summary').click();
  check('Source hash is visible in candidate details',(await d.locator('.intake-rows').innerText()).includes('SHA-256:'));
  for(const sample of [{width:1366,lang:'es',theme:'dark'},{width:390,lang:'en',theme:'light'},{width:320,lang:'es',theme:'dark'}]){
    await page.setViewportSize({width:sample.width,height:1000});
    await page.evaluate(sample=>applyUiTheme(sample.theme),sample);
    const size=await d.evaluate(el=>({width:el.getBoundingClientRect().width,viewport:innerWidth,scroll:el.scrollWidth,client:el.clientWidth}));
    check('Scanner dialog fits '+sample.width+'px '+sample.theme,size.width<=size.viewport&&size.scroll<=size.client+1,size);
    const controls=await d.evaluate(el=>{const bounds=el.getBoundingClientRect();return [...el.querySelectorAll('.import-navigation button:not([hidden])')].map(b=>{const r=b.getBoundingClientRect();return {w:r.width,h:r.height,inside:r.bottom<=bounds.bottom&&r.top>=bounds.top};});});
    check('Import controls are entirely visible and at least 44px at '+sample.width,controls.every(c=>c.w>=44&&c.h>=44&&c.inside),controls);
    await page.screenshot({path:path.join(out,'nuclei-'+sample.width+'.png'),fullPage:true});
  }
  await d.getByRole('button',{name:'Importar selección como pendiente',exact:true}).click();await d.waitFor({state:'detached'});
  check('Nuclei commits one unverified finding awaiting source review',await page.evaluate(n=>{const f=S.data.findings.at(-1);return S.data.findings.length===n+1&&f.verification==='unverified'&&f.import_source.reviewed===false;},original.findings));
  await page.setViewportSize({width:1366,height:1000});
  d=await intake('nuclei',nuclei);
  check('Reimport disables existing duplicate and commit',await d.locator('[data-intake-row="0"]').isDisabled()&&await d.getByRole('button',{name:'Importar selección como pendiente',exact:true}).isDisabled());
  await d.getByRole('button',{name:'Cerrar',exact:true}).click();
  d=await intake('nmap',nmap);await d.getByText('Revisar servicios y origen',{exact:true}).click();
  check('Nmap preview explains services, counts and origin',(await d.innerText()).includes('53/udp · open|filtered')&&(await d.innerText()).includes('2 servicios observados')&&(await d.innerText()).includes('SHA-256:'));
  await page.screenshot({path:path.join(out,'nmap-preview.png'),fullPage:true});
  await d.getByRole('button',{name:'Importar selección como pendiente',exact:true}).click();await d.waitFor({state:'detached'});
  check('Nmap adds inventory and pending coverage without findings',await page.evaluate(before=>S.data.findings.length===before.findings+1&&S.data.assets.length===before.assets+1&&S.data.coverage.length===before.coverage+1&&S.data.coverage.at(-1).status==='pending'&&S.data.coverage.at(-1).services.length===2,original));
  await page.reload();await page.waitForFunction(()=>S.slug&&S.data&&!projectStore.loading&&!projectBusyCount);
  check('Scanner observations survive reload',await page.evaluate(()=>S.data.coverage.at(-1).import_source.format==='nmap'&&S.data.findings.at(-1).import_source.format==='nuclei'));
  await page.locator('#workspaceResearch > summary').click();await page.locator('[data-workflow=coverage]').click();await page.getByText('Observación Nmap original',{exact:true}).click();
  check('Coverage exposes immutable original provenance',await page.getByText('Observación Nmap original',{exact:true}).isVisible()&&(await page.locator('#editor').innerText()).includes('OpenSSH 9.0'));
  check('No scanner target or external network requests',results.external.length===0,results.external);
  check('No browser runtime errors',results.pageErrors.length===0,results.pageErrors);
}catch(e){results.error=String(e.stack||e);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw e;}
finally{save();clearTimeout(timer);await browser?.close();server.kill('SIGTERM');}})().catch(e=>{console.error(e);process.exitCode=1;});
