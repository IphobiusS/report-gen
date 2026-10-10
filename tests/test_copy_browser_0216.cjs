/* Exact product helpers in Chromium, with controlled Clipboard API outcomes.
 * Run with REPORT_GEN_CHROMIUM and REPORT_GEN_PLAYWRIGHT_MODULE, optionally --tool/--output. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const args=process.argv.slice(2),opt=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const root=path.resolve(opt('--tool',path.join(__dirname,'..')));
const out=path.resolve(opt('--output',path.join(root,'out/copy-0216')));
const {chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
const source=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
const helper=source.slice(0,source.indexOf('// ---- shared transport'));
const translations=source.slice(source.indexOf('const I18N ='),source.indexOf('function applyStaticI18n('));
const toast=source.slice(source.indexOf('function toast('),source.indexOf('function openModal('));
const copy=['cvss31.js','cvss-editor.js'].map(file=>fs.readFileSync(path.join(root,'webapp/static',file),'utf8')).join('\n');
assert.ok(helper&&translations&&toast&&copy,'Extract the actual complete product functions.');
fs.mkdirSync(out,{recursive:true});let browser;const result={checks:[],cases:[]};
function check(name,condition){result.checks.push({name,passed:!!condition});assert.ok(condition,name);}
(async()=>{
 browser=await chromium.launch({headless:true,...(process.env.REPORT_GEN_CHROMIUM?{executablePath:process.env.REPORT_GEN_CHROMIUM}:{})});
 result.browser=browser.version();
 for(const language of ['es','en']) for(const scenario of ['reject','unavailable','pending','resolve']){
  const page=await browser.newPage();const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.setContent('<!doctype html><html lang="'+language+'"><body><main><code id="vector"></code></main></body></html>');
  await page.evaluate(({language,scenario})=>{
   window.S={uiLang:language};window.copyRejections=[];window.copyCalls=[];
   addEventListener('unhandledrejection',event=>{copyRejections.push(event.reason?.name||String(event.reason));event.preventDefault();});
   const clipboard=scenario==='unavailable'?undefined:{writeText:vector=>{
    copyCalls.push(vector);
    return scenario==='reject'?Promise.reject(new DOMException('Clipboard denied','NotAllowedError')):
           scenario==='pending'?new Promise(resolve=>window.completeCopy=resolve):Promise.resolve();
   }};
   Object.defineProperty(navigator,'clipboard',{configurable:true,value:clipboard});
  },{language,scenario});
  await page.addScriptTag({content:helper+'\n'+translations+'\n'+toast+'\n'+copy});
  const vector='CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:N/A:N';
  await page.evaluate(vector=>{document.querySelector('#vector').textContent=vector;document.querySelector('main').append(CVSSEditor.copyVectorButton(vector));},vector);
  const button=page.locator('button'),prefix=language+' / '+scenario;
  await button.click();await page.waitForTimeout(40);
  if(scenario==='pending'){
   check(prefix+' does not announce success while pending',await button.textContent()!=='✓'&&await page.getByRole('status').count()===0);
   check(prefix+' pending operation is exposed and prevents duplicate copy',await button.isDisabled()&&await button.getAttribute('aria-busy')==='true');
   await button.evaluate(node=>node.click());check(prefix+' duplicate activation is ignored',await page.evaluate(()=>copyCalls.length)===1);
   await page.evaluate(()=>completeCopy());await page.waitForTimeout(40);
  }
  if(scenario==='resolve'||scenario==='pending'){
   check(prefix+' success follows resolved write',await button.textContent()==='✓'&&await page.getByRole('status').textContent()===(language==='es'?'Copiado':'Copied'));
   check(prefix+' writes the exact vector once',await page.evaluate(()=>copyCalls.length===1&&copyCalls[0],vector)===vector);
   await page.waitForTimeout(1050);check(prefix+' temporary confirmation restores action glyph',await button.textContent()==='⧉');
  }else{
   check(prefix+' never shows false success',await button.textContent()!=='✓'&&await page.getByRole('status').count()===0);
   const message=await page.getByRole('alert').textContent();
   check(prefix+' exposes the failure and manual alternative',message.includes(language==='es'?'No se pudo copiar':'Could not copy')&&message.includes(language==='es'?'manualmente':'manually'));
  }
  check(prefix+' stable accessible action',await button.getAttribute('aria-label')===(language==='es'?'Copiar vector':'Copy vector'));
  check(prefix+' native non-submit button',await button.getAttribute('type')==='button');
  check(prefix+' action remains available with a stable name',await button.isEnabled()&&await button.getAttribute('aria-busy')===null&&await button.getAttribute('aria-label')===(language==='es'?'Copiar vector':'Copy vector'));
  const rejections=await page.evaluate(()=>copyRejections);
  check(prefix+' handles promise rejections',!rejections.length&&!errors.length);
  result.cases.push({language,scenario,passed:true,errors,rejections});await page.close();
 }
 console.log(JSON.stringify({browser:result.browser,checks:result.checks.length,failures:0}));
})().catch(error=>{result.error=error.stack;console.error(error);process.exitCode=1;}).finally(async()=>{
 await browser?.close();fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2)+'\n');
});
