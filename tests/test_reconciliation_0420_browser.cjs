/* Real import -> authored edit -> second scan -> reviewed reconciliation. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..'),out=path.resolve(process.env.RG_RECONCILE_OUTPUT||'out/reconciliation-0420');fs.mkdirSync(out,{recursive:true});
const results={checks:[],errors:[],external:[]};
function check(name,ok){results.checks.push({name,passed:!!ok});assert.ok(ok,name);console.log('PASS '+name);}
const server=spawn(process.env.RG_PYTHON||'python',[path.join(root,'scripts/browser-server-0212.py')],{cwd:root});server.stderr.on('data',value=>fs.appendFileSync(path.join(out,'server.log'),value));
const scan={site:[{'@name':'https://example.test',alerts:[{pluginid:'10020',alertRef:'10020-1',name:'Reimport candidate',riskcode:'1',confidence:'2',desc:'<p>Scanner text</p>',solution:'<p>New scanner recommendation</p>',instances:[{uri:'https://example.test/account',method:'GET',param:'id',evidence:'Observed header', 'request-header':'GET /account HTTP/1.1\r\nHost: example.test'}]}]}]};
let browser,page,timer;
(async()=>{try{
 const base=await new Promise((resolve,reject)=>{let raw='';timer=setTimeout(()=>reject(Error('server timeout')),20000);server.stdout.on('data',part=>{raw+=part;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]).url);}});server.on('exit',code=>reject(Error('server exit '+code)));});
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||undefined});page=await browser.newPage({viewport:{width:1440,height:1000}});
 page.on('pageerror',e=>results.errors.push(String(e)));page.on('request',r=>{if(!r.url().startsWith(base)&&!r.url().startsWith('blob:')&&!r.url().startsWith('data:'))results.external.push(r.url());});
 await page.addInitScript(()=>localStorage.setItem('rg.previewVisible','0'));await page.goto(base);await page.locator('.workspace-dashboard').waitFor();await page.locator('.workspace-hero-actions .primary').click();await page.waitForFunction(()=>S.slug&&S.data?.findings?.length&&!projectStore.loading&&!projectBusyCount);
 async function intake(){await page.evaluate(()=>ProgressUI.intake());const d=page.locator('dialog[data-intake-dialog]');await d.getByLabel('Formato',{exact:true}).selectOption('zap');await d.locator('input[type=file]').setInputFiles({name:'zap.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(scan))});await d.locator('[data-import-panel="2"]').waitFor({state:'visible'});await d.getByRole('button',{name:'Revisar selección',exact:true}).click();await d.locator('[data-import-panel="3"]').waitFor({state:'visible'});return d;}
 let d=await intake();await d.getByRole('button',{name:'Importar selección como pendiente',exact:true}).click();await d.waitFor({state:'detached'});
 const uid=await page.evaluate(async()=>{const f=S.data.findings.at(-1);f.description_md='AUTHOR TEXT';f.remediation_md='AUTHOR REMEDIATION';f.status='in_progress';f.import_source.reviewed=true;scheduleSave();await doSave();return f.uid;});
 d=await intake();check('Existing scanner identity disables duplicate creation',await d.locator('[data-intake-row="0"]').isDisabled());await d.getByRole('button',{name:'Conciliar con hallazgos existentes',exact:true}).click();
 const r=page.locator('dialog[data-reconciliation-dialog]');await r.locator('[data-reconcile-row="0"]').waitFor();
 check('Reconciliation starts with explicit skip',await r.getByLabel('Decisión',{exact:true}).inputValue()==='skip');await r.getByLabel('Decisión',{exact:true}).selectOption('attach');await r.getByLabel('Hallazgo de destino',{exact:true}).selectOption(uid);
 check('Authored field diffs available without selecting them',(await r.innerText()).includes('AUTHOR TEXT')===false&&await r.locator('[data-reconcile-field="description_md"]').count()===1);
 await r.getByText('Remediación',{exact:true}).click();await r.locator('[data-reconcile-field="remediation_md"]').check();await r.locator('[data-reconcile-ack]').check();
 await page.screenshot({path:path.join(out,'reconciliation-desktop.png'),fullPage:true});
 for(const width of [390,320]){await page.setViewportSize({width,height:1000});check('Reconciliation fits '+width+' px',await r.evaluate(el=>el.scrollWidth<=el.clientWidth+1&&el.getBoundingClientRect().width<=innerWidth));}
 await page.setViewportSize({width:1440,height:1000});await r.locator('[data-reconcile-apply]').click();await r.waitFor({state:'detached'});
 check('Only reviewed remediation changed; manual description and status survive',await page.evaluate(uid=>{const f=S.data.findings.find(f=>f.uid===uid);return f.description_md==='AUTHOR TEXT'&&f.remediation_md==='New scanner recommendation'&&f.status==='in_progress'&&f.import_observations.length===1&&f.import_observations[0].selected_fields.join()==='remediation_md';},uid));
 await page.reload();await page.waitForFunction(()=>S.slug&&S.data&&!projectStore.loading&&!projectBusyCount);check('Observation survives disk reload',await page.evaluate(uid=>S.data.findings.find(f=>f.uid===uid).import_observations.length===1,uid));
 check('No scanner target requests',results.external.length===0);check('No runtime errors',results.errors.length===0);
}catch(error){results.error=String(error.stack||error);if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw error;}finally{fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));clearTimeout(timer);await browser?.close();server.kill('SIGTERM');}})().catch(error=>{console.error(error);process.exitCode=1;});
