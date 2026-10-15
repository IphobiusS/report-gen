/* Rebuild real tutorial screenshots from disposable, authored ES/EN/PT fixtures.
 * Requires a browser-capable host. No screenshots or fixtures use user projects.
 */
'use strict';
const fs=require('node:fs'), path=require('node:path'), os=require('node:os');
const {spawn,spawnSync}=require('node:child_process');
const {createHash}=require('node:crypto');
const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'));
const args=process.argv.slice(2);
const out=path.resolve(args.includes('--output')?args[args.indexOf('--output')+1]:'out/tutorial-captures');
const langs=args.includes('--lang')?[args[args.indexOf('--lang')+1]]:['es','en','pt'];
if(langs.some(lang=>!['es','en','pt'].includes(lang)))throw Error('Supported languages: es, en, pt');
const python=process.env.RG_PYTHON||'python';
const {chromium}=require(require.resolve('playwright',{paths:[root]}));
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-tutorial-capture-'));
fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
fs.mkdirSync(out,{recursive:true});
const result={screens:[],errors:[],external:[],fixture:'Authored synthetic tutorial project; no real security test',languages:langs};
const seed=spawnSync(python,[path.join(root,'scripts/tutorial-fixture.py'),'--workspace',workspace],{cwd:root,encoding:'utf8'});
if(seed.status!==0){fs.rmSync(workspace,{recursive:true,force:true});throw Error(seed.stderr||seed.stdout);}
const server=spawn(python,[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:{...process.env,PYTHONPATH:root+path.delimiter+path.join(root,'webapp')}});
server.stderr.on('data',data=>fs.appendFileSync(path.join(out,'server.log'),data));
let browser,page,timer;
async function ready(){await page.waitForFunction(()=>!document.querySelector('#splash')&&typeof GuideUI!=='undefined'&&!projectStore.loading&&!projectBusyCount);}
async function shot(key,lang,selector){
  await page.evaluate(()=>document.fonts.ready);
  const locator=page.locator(selector);
  await locator.waitFor({state:'visible'});
  await locator.locator('img').evaluateAll(nodes=>Promise.all(nodes.map(n=>{n.loading="eager";return n.decode();})));
  const png=path.join(out,key+'-'+lang+'.png');
  await locator.screenshot({path:png,animations:'disabled'});
  const webp=path.join(out,key+'-'+lang+'.webp');
  const converted=spawnSync(python,['-c','from PIL import Image; import sys; Image.open(sys.argv[1]).save(sys.argv[2], "WEBP", quality=88, method=6)',png,webp],{encoding:'utf8'});
  if(converted.status!==0)throw Error(converted.stderr);
  const bounds=await locator.boundingBox();
  result.screens.push({key,lang,file:path.basename(webp),width:Math.round(bounds.width),height:Math.round(bounds.height),sha256:createHash('sha256').update(fs.readFileSync(webp)).digest('hex')});
}
(async()=>{try{
 const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server timeout')),30000);server.stdout.on('data',data=>{text+=data;for(const line of text.split('\n'))try{const parsed=JSON.parse(line);if(parsed.url){clearTimeout(timer);resolve(parsed.url);}}catch{}});server.on('exit',code=>reject(Error('Server exited '+code)));});
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||undefined});result.browser=browser.version();
 for(const lang of langs){
  const context=await browser.newContext({viewport:{width:1440,height:1080},deviceScaleFactor:1,reducedMotion:'reduce'});
  await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){result.external.push(url);return route.abort();}return route.continue();});
  await context.addInitScript(lang=>{localStorage.setItem('rg.uiLang',lang);localStorage.setItem('rg.previewVisible','0');localStorage.setItem('rg.visualTutorial.v1',JSON.stringify({version:1,dismissed:true,completed:false,step:0,visited:[]}));},lang);
  page=await context.newPage();page.on('pageerror',e=>result.errors.push(String(e)));
  await page.goto(base);await ready();
  await page.evaluate(async lang=>{setUiLang(lang);await loadProject('tutorial-'+lang);applyUiTheme('dark');},lang);await ready();
  if(await page.evaluate(()=>S.data.meta.lang)!==lang)throw Error('Unexpected authored report language');
  await page.evaluate(()=>DesignLibraryUI.gallery(null,{create:true}));
  await page.locator('dialog.design-dialog[open] [data-design="serio"]').waitFor();
  await shot('gallery',lang,'dialog.design-dialog[open]');await page.keyboard.press('Escape');
  await page.evaluate(()=>select('report'));await shot('metadata',lang,'#editor');
  await page.evaluate(()=>select('finding',0));await shot('finding',lang,'#editor');
  await page.evaluate(()=>select('workflow','evidence'));await page.locator('[data-evidence-uid]').waitFor();await shot('evidence',lang,'#editor');
  await page.evaluate(()=>StudioUI.inspector());await page.locator('dialog[open] .publication-text').waitFor();await shot('privacy',lang,'dialog[open]');await page.keyboard.press('Escape');
  await page.evaluate(()=>document.querySelector('#deliveryBtn').click());
  const exportButtons=page.locator('dialog[open] [data-delivery-format]');
  await exportButtons.first().waitFor();
  await exportButtons.last().scrollIntoViewIfNeeded();
  for(const button of await exportButtons.all()){
   const visible=await button.evaluate(el=>{const r=el.getBoundingClientRect(),d=el.closest('dialog').getBoundingClientRect();return r.top>=Math.max(0,d.top)&&r.bottom<=Math.min(innerHeight,d.bottom);});
   if(!visible)throw Error('Delivery screenshot omits an export button: '+lang);
  }
  await shot('delivery',lang,'dialog[open]');await page.keyboard.press('Escape');
  await page.evaluate(()=>select('workflow','backup'));await page.locator('#editor .card').waitFor();await shot('backup',lang,'[data-workflow-view="backup"]');
  await context.close();
 }
 if(result.errors.length||result.external.length)throw Error('Runtime or external request failures: '+JSON.stringify(result));
}finally{clearTimeout(timer);fs.writeFileSync(path.join(out,'capture-manifest.json'),JSON.stringify(result,null,2)+'\n');await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{console.error(error);process.exitCode=1;});
