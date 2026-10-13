/* Real editor startup, language switch and reload preserve control labels. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{createHash}=require('node:crypto');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),opt=(n,d)=>args.includes(n)?args[args.indexOf(n)+1]:d;
const engine=opt('--browser','chromium'),out=path.resolve(opt('--output','out/restore-language-0345'));
const playwright=require(require.resolve('playwright',{paths:[root]})),sourceOverride=opt('--source-dir','');
fs.mkdirSync(out,{recursive:true});const result={engine,checks:[],errors:[],screens:[],source_hashes:{}};
for(const name of ['app.js','studio.js'])result.source_hashes[name]=createHash('sha256').update(fs.readFileSync(path.join(sourceOverride||path.join(root,'webapp/static'),name))).digest('hex');
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2));
const check=(name,passed,detail)=>{result.checks.push({name,passed:!!passed,detail});save();assert.ok(passed,name);};
const labels={en:{publication:'Publication inspector',shown:'Hide preview',hidden:'Show preview',validation:'Validate report'},es:{publication:'Inspector de publicación',shown:'Ocultar vista previa',hidden:'Mostrar vista previa',validation:'Validar informe'}};
let server,browser,timer;
const idle=page=>page.waitForFunction(()=>typeof S!=='undefined'&&typeof projectStore!=='undefined'&&!projectStore.loading&&!projectBusyCount&&document.querySelector('#publicationBtn')&&document.querySelector('.workspace-dashboard'));
const more=async page=>{if(!await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();};
async function sample(page,lang,shown,name){
 const actual=await page.evaluate(()=>({lang:S.uiLang,htmlLang:document.documentElement.lang,publication:document.querySelector('#publicationBtn').textContent,preview:document.querySelector('#previewToggle').textContent,validation:document.querySelector('#validateBtn').getAttribute('aria-label'),title:document.querySelector('#validateBtn').title}));
 const expected=labels[lang];check(name,actual.lang===lang&&actual.htmlLang===lang&&actual.publication===expected.publication&&actual.preview===expected[shown?'shown':'hidden']&&actual.validation===expected.validation&&actual.title===expected.validation,actual);
}
(async()=>{try{
 server=spawn(process.env.RG_PYTHON||'python3',[path.join(root,'scripts/browser-server-0210.py')],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});server.stderr.pipe(fs.createWriteStream(path.join(out,'server.log')));
 const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server startup timeout')),30000);server.stdout.on('data',chunk=>{text+=chunk;if(text.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(text.split('\n')[0]).url)}catch(e){reject(e)}}});server.once('exit',c=>reject(Error('Server exit '+c)))});
 const executable=opt('--executable',engine==='chromium'?process.env.RG_CHROMIUM_EXECUTABLE:undefined);browser=await playwright[engine].launch({headless:true,...(executable?{executablePath:executable}:{})});result.version=browser.version();
 for(const initial of ['es','en'])for(const shown of [true,false]){
  const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});await context.addInitScript(({initial,shown})=>{if(localStorage.getItem('rg.uiLang')===null)localStorage.setItem('rg.uiLang',initial);if(localStorage.getItem('rg.previewVisible')===null)localStorage.setItem('rg.previewVisible',shown?'1':'0');},{initial,shown});
  if(sourceOverride)for(const name of ['app.js','studio.js'])await context.route('**/static/'+name,route=>route.fulfill({status:200,contentType:'text/javascript',body:fs.readFileSync(path.join(sourceOverride,name),'utf8')}));
  const page=await context.newPage();page.on('pageerror',e=>result.errors.push(String(e)));await page.goto(base);await idle(page);
  const label=initial+' '+(shown?'visible':'hidden');await sample(page,initial,shown,label+' startup labels');
  if(!await page.evaluate(()=>S.slug))await page.getByRole('button',{name:initial==='es'?'Probar demo Nimbus':'Try Nimbus demo',exact:true}).click();await page.waitForFunction(()=>S.slug&&!projectStore.loading&&!projectBusyCount);await idle(page);
  const before=await page.evaluate(()=>({data:JSON.stringify(S.data),etag:projectStore.etag}));
  await more(page);if(!await page.locator('#studioPreferences').evaluate(el=>el.open))await page.locator('#studioPreferences > summary').click();await page.locator('#langToggle').click();const changed=initial==='es'?'en':'es';await sample(page,changed,shown,label+' language switch labels');
  check(label+' interface switch preserves authored report and revision',await page.evaluate(before=>JSON.stringify(S.data)===before.data&&projectStore.etag===before.etag,before));
  await page.reload();await idle(page);await sample(page,changed,shown,label+' restored labels after real reload');
  if(initial==='es'){
   await more(page);if(!await page.locator('#exportMenu').evaluate(el=>el.open))await page.locator('#exportMenu > summary').click();const dest=path.join(out,label.replaceAll(' ','-')+'-restored.png');await page.screenshot({path:dest});result.screens.push({path:dest,sha256:createHash('sha256').update(fs.readFileSync(dest)).digest('hex')});
  }
  await context.close();
 }
 check('No application JavaScript errors',result.errors.length===0,result.errors);result.passed=true;save();console.log('PASS '+result.checks.length+' language restoration checks in '+engine);
 }catch(e){result.failure=String(e.stack||e);result.passed=false;save();console.error(e);process.exitCode=1;}
 finally{clearTimeout(timer);await browser?.close();server?.kill('SIGTERM');}
})();
