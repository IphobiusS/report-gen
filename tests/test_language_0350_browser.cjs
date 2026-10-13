/* Real startup, explicit language selection and report-language independence. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process'),{createHash}=require('node:crypto');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),opt=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const engine=opt('--browser','chromium'),out=path.resolve(opt('--output','out/language-0350'));
const playwright=require('playwright'),result={engine,checks:[],errors:[],screens:[],source_hashes:{}};
fs.mkdirSync(out,{recursive:true});for(const name of ['app.js','index.html','workspace.js'])result.source_hashes[name]=createHash('sha256').update(fs.readFileSync(path.join(root,'webapp/static',name))).digest('hex');
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2));
const check=(name,passed,detail)=>{result.checks.push({name,passed:!!passed,detail});save();assert.ok(passed,name);};
const labels={es:{newProject:'Nuevo proyecto',validate:'Validar informe',finding:'Hallazgos',report:'Informe'},en:{newProject:'New project',validate:'Validate report',finding:'Findings',report:'Report'},pt:{newProject:'Novo projeto',validate:'Validar relatório',finding:'Achados',report:'Relatório'}};
const idle=page=>page.waitForFunction(()=>typeof S!=='undefined'&&typeof projectStore!=='undefined'&&!projectStore.loading&&!projectBusyCount&&!document.querySelector('#splash')&&document.querySelector('.workspace-dashboard'));
async function more(page){if(!await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();if(!await page.locator('#studioPreferences').evaluate(el=>el.open))await page.locator('#studioPreferences > summary').click();}
async function sample(page,lang,label){
 const actual=await page.evaluate(()=>({language:S.uiLang,dom:document.documentElement.lang,selected:document.querySelector('#langToggle').value,newProject:document.querySelector('#newProjectBtn').textContent,validate:document.querySelector('#validateBtn').getAttribute('aria-label'),finding:document.querySelector('[data-i18n="findings_head"]').textContent,report:document.querySelector('#navReport').textContent,format:[...document.querySelector('#exportFormat').options].map(o=>o.textContent)}));
 const expected=labels[lang];check(label,actual.language===lang&&actual.dom===(lang==='pt'?'pt-BR':lang)&&actual.selected===lang&&actual.newProject===expected.newProject&&actual.validate===expected.validate&&actual.finding===expected.finding&&actual.report===expected.report&&actual.format.every(Boolean),actual);
}
let server,browser,timer;
(async()=>{try{
 server=spawn(process.env.RG_PYTHON||'python3',[path.join(root,'scripts/browser-server-0210.py')],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});server.stderr.pipe(fs.createWriteStream(path.join(out,'server.log')));
 const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server startup timeout')),60000);server.stdout.on('data',chunk=>{text+=chunk;if(text.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(text.split('\n')[0]).url)}catch(e){reject(e)}}});server.once('exit',code=>reject(Error('Server exit '+code)))});
 const executable=opt('--executable',engine==='chromium'?(process.env.RG_CHROMIUM_EXECUTABLE||process.env.REPORT_GEN_CHROMIUM):undefined);browser=await playwright[engine].launch({headless:true,...(executable?{executablePath:executable}:{})});result.version=browser.version();
 for(const initial of ['es','en','pt-BR']){
  const language=initial==='pt-BR'?'pt':initial,context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
  await context.addInitScript(initial=>{if(localStorage.getItem('rg.uiLang')===null)localStorage.setItem('rg.uiLang',initial);localStorage.setItem('rg.previewVisible','0');},initial);
  const page=await context.newPage();page.on('pageerror',error=>result.errors.push(String(error)));await page.goto(base);await idle(page);await sample(page,language,initial+' restored startup');
  if(!await page.evaluate(()=>S.slug)){
   await page.locator('.workspace-hero-actions .primary').click();await page.waitForFunction(()=>S.slug&&!projectStore.loading&&!projectBusyCount);await idle(page);
  }
  const before=await page.evaluate(()=>({data:JSON.stringify(S.data),etag:projectStore.etag,revision:projectStore.revision}));
  for(const target of ['pt','en','es']){
   await more(page);await page.locator('#langToggle').selectOption(target);await sample(page,target,initial+' selects '+target);
   check(initial+' '+target+' leaves exact report and revision unchanged',await page.evaluate(before=>JSON.stringify(S.data)===before.data&&projectStore.etag===before.etag&&projectStore.revision===before.revision&&!projectStore.dirty,before));
   await page.reload();await idle(page);await sample(page,target,initial+' reloads '+target);
  }
  if(initial==='pt-BR'){
   await more(page);await page.locator('#langToggle').selectOption('pt');await page.locator('#studioMore > summary').click();
   for(const width of [320,390,1440]){
    await page.setViewportSize({width,height:1000});await more(page);
    const geometry=await page.locator('#langToggle').evaluate(el=>({width:innerWidth,document:document.documentElement.scrollWidth,rect:{left:el.getBoundingClientRect().left,right:el.getBoundingClientRect().right,height:el.getBoundingClientRect().height},name:el.getAttribute('aria-label'),options:[...el.options].map(o=>o.text)}));
    check('Portuguese language control fits '+width,geometry.document<=width+1&&geometry.rect.left>=0&&geometry.rect.right<=width+1&&geometry.rect.height>=40&&geometry.name.includes('PT')&&geometry.options.includes('Português (Brasil)'),geometry);
    if(width===390){const destination=path.join(out,'portuguese-language-mobile.png');await page.screenshot({path:destination});result.screens.push({path:destination,sha256:createHash('sha256').update(fs.readFileSync(destination)).digest('hex')});}
    await page.locator('#studioMore > summary').click();
   }
   await page.setViewportSize({width:1440,height:1000});await page.locator('#navReport').click();
   check('Report metadata provides all three languages with readable native names',await page.locator('[data-field="lang"]').evaluate(el=>el.options.length===3&&el.querySelector('option[value="pt"]').textContent==='Português (Brasil)'));
   const contents=await page.evaluate(()=>JSON.stringify({findings:S.data.findings,sections:S.data.report.sections,title:S.data.meta.report_title}));
   await page.locator('[data-field="lang"]').selectOption('pt');await page.waitForFunction(()=>!projectStore.dirty&&!projectStore.saving);
   check('Explicit report-language edit is saved and UI stays Portuguese',await page.evaluate(()=>S.data.meta.lang==='pt'&&S.uiLang==='pt'&&document.activeElement.matches('[data-field="lang"]')));
   check('Explicit report-language edit preserves authored sections, findings and title',await page.evaluate(contents=>JSON.stringify({findings:S.data.findings,sections:S.data.report.sections,title:S.data.meta.report_title})===contents,contents));
   const sidebar=await page.locator('#sectionList').innerText();check('Report-language edit refreshes section labels immediately',sidebar.includes(await page.evaluate(()=>S.catBy.findings.title_pt)),sidebar);
   const destination=path.join(out,'portuguese-editor.png');await page.screenshot({path:destination});result.screens.push({path:destination,sha256:createHash('sha256').update(fs.readFileSync(destination)).digest('hex')});
   await page.reload();await idle(page);check('Saved report language survives real reload',await page.evaluate(()=>S.data.meta.lang==='pt'));
  }
  await context.close();
 }
 check('No application JavaScript errors',result.errors.length===0,result.errors);result.passed=true;save();console.log('PASS '+result.checks.length+' Portuguese core checks in '+engine);
 }catch(error){result.failure=String(error.stack||error);result.passed=false;save();console.error(error);process.exitCode=1;}
 finally{clearTimeout(timer);await browser?.close();server?.kill('SIGTERM');}
})();
