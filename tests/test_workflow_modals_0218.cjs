/* Native modality, keyboard closure and successful workflow actions in a real browser. */
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'));
const args=process.argv.slice(2),option=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const out=path.resolve(option('--output','out/workflow-modals-0218'));
const {chromium}=require(require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
fs.mkdirSync(out,{recursive:true});let server,browser,temp;const results={checks:[],errors:[]};
const check=(name,condition)=>{results.checks.push({name,passed:!!condition});assert.ok(condition,name);console.log('PASS '+name);};
(async()=>{
 temp=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-'));fs.writeFileSync(path.join(temp,'.test-only'),'synthetic acceptance workspace');
 server=spawn(process.env.RG_PYTHON||'python3',[path.join(root,'scripts/browser-server-0211.py'),'--workspace',temp],{cwd:root,stdio:['ignore','pipe','pipe']});server.stderr.pipe(fs.createWriteStream(path.join(out,'server.log')));
 const base=await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Server startup timeout')),20000);server.stdout.on('data',d=>{text+=d;if(text.includes('\n')){clearTimeout(timer);resolve(JSON.parse(text.split('\n')[0]).url)}});server.once('exit',reject)});
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined});results.browser=browser.version();
 for(const language of ['es','en'])for(const width of [320,1366]){
  const prefix=language+'/'+width,context=await browser.newContext({viewport:{width,height:900},reducedMotion:'reduce'});const page=await context.newPage();page.on('pageerror',e=>results.errors.push(e.message));
  const w=(es,en)=>language==='es'?es:en;
  await page.addInitScript(language=>{localStorage.setItem('rg.previewVisible','0');localStorage.setItem('rg.uiLang',language)},language);await page.goto(base);await page.waitForFunction(()=>typeof S!=='undefined'&&!!document.querySelector('.workspace-dashboard'));
  // Each context has a new synthetic project; existing files are never touched.
  await page.evaluate(()=>document.querySelector('#demoBtn').click());await page.waitForFunction(()=>S.slug&&!projectStore.loading&&projectBusyCount===0);
  const ready=()=>page.waitForFunction(()=>!projectStore.loading&&!projectStore.saving&&!projectStore.dirty&&!projectStore.lastError&&projectBusyCount===0);
  const library=async()=>{await page.evaluate(()=>WorkflowUI.openLibrary());await page.getByRole('button',{name:w('Nueva plantilla','New template'),exact:true}).waitFor();};
  const inspect=async(dialog,name)=>{
   check(prefix+' '+name+' is a native modal',await dialog.evaluate(el=>el.tagName==='DIALOG'&&el.matches(':modal')));
   check(prefix+' '+name+' starts with focus inside',await dialog.evaluate(el=>el.contains(document.activeElement)));
   await page.evaluate(()=>document.querySelector('#editor').focus());
   check(prefix+' '+name+' blocks focus behind the dialog',await dialog.evaluate(el=>el.contains(document.activeElement)));
   await page.keyboard.press('Tab');check(prefix+' '+name+' keeps keyboard focus inside',await dialog.evaluate(el=>el.contains(document.activeElement)));
   check(prefix+' '+name+' fits the viewport',await dialog.evaluate(el=>{const r=el.getBoundingClientRect();return r.x>=-1&&r.right<=innerWidth+1}));
  };
  await library();const create=page.getByRole('button',{name:w('Nueva plantilla','New template'),exact:true});await create.click();let d=page.getByRole('dialog',{name:w('Plantilla reutilizable','Reusable template'),exact:true});await inspect(d,'template');
  await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('dialog[open]'));await page.waitForFunction(label=>document.activeElement?.textContent===label,w('Nueva plantilla','New template'));
  check(prefix+' Escape restores template opener focus',await create.evaluate(el=>document.activeElement===el));
  await create.click();d=page.getByRole('dialog',{name:w('Plantilla reutilizable','Reusable template'),exact:true});await d.locator('[data-field="name"]').fill('Synthetic template '+prefix);await d.locator('[data-field="title"]').fill('Synthetic template finding '+prefix);
  await d.getByRole('checkbox',{name:w('He revisado que no contenga datos de otro cliente','I reviewed it for other client data'),exact:true}).check();await d.getByRole('button',{name:w('Guardar versión de plantilla','Save template version'),exact:true}).click();await page.waitForFunction(()=>!document.querySelector('dialog[open]'));await page.getByText('Synthetic template '+prefix,{exact:true}).waitFor();
  check(prefix+' saving template closes the native dialog',await page.locator('dialog[open]').count()===0);
  const card=page.locator('.wf-card').filter({has:page.getByText('Synthetic template '+prefix,{exact:true})});const initial=await page.evaluate(()=>S.data.findings.length);await card.getByRole('button',{name:w('Insertar','Insert'),exact:true}).click();d=page.getByRole('dialog',{name:w('Insertar plantilla','Insert template'),exact:true});await inspect(d,'insert');
  await d.locator('input[data-field="objetivo"]').fill('Synthetic target');await d.getByRole('button',{name:w('Insertar en el proyecto','Insert into project'),exact:true}).click();await ready();await page.waitForFunction(()=>!document.querySelector('dialog[open]'));
  check(prefix+' inserting creates one finding and closes cleanly',await page.evaluate(n=>S.data.findings.length===n+1&&document.activeElement.id==='editor',initial));
  await page.evaluate(()=>select('workflow','evidence'));const annotate=page.getByRole('button',{name:w('Anotar / censurar','Annotate / redact'),exact:true}).first();await annotate.waitFor();await annotate.click();d=page.getByRole('dialog',{name:w('Anotar y censurar evidencia','Annotate and redact evidence'),exact:true});await inspect(d,'annotation');
  await d.getByRole('button',{name:w('Cerrar','Close'),exact:true}).click();await page.waitForFunction(()=>!document.querySelector('dialog[open]'));await page.waitForFunction(label=>document.activeElement?.textContent===label,w('Anotar / censurar','Annotate / redact'));
  check(prefix+' annotation close restores its opener',await annotate.evaluate(el=>document.activeElement===el));
  check(prefix+' document has no horizontal overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(out,'workflow-'+language+'-'+width+'.png')});await context.close();
 }
 check('No JavaScript exceptions in workflow dialogs',results.errors.length===0);
})().catch(error=>{results.failure=error.stack;console.error(error);process.exitCode=1}).finally(async()=>{await browser?.close();server?.kill('SIGTERM');fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));});
