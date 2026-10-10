/* The static shell stays honest and usable when its main script never executes. */
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'));
const args=process.argv.slice(2),opt=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const out=path.resolve(opt('--output','out/static-startup-0218'));
const {chromium}=require(require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
fs.mkdirSync(out,{recursive:true});let server,browser;const results={checks:[],errors:[]};
const check=(name,condition)=>{results.checks.push({name,passed:!!condition});assert.ok(condition,name);console.log('PASS '+name);};
(async()=>{
 const temp=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-'));fs.writeFileSync(path.join(temp,'.test-only'),'synthetic acceptance workspace');
 server=spawn(process.env.RG_PYTHON||'python3',[path.join(root,'scripts/browser-server-0211.py'),'--workspace',temp],{cwd:root,stdio:['ignore','pipe','pipe']});server.stderr.pipe(fs.createWriteStream(path.join(out,'server.log')));
 const base=await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Server timeout')),20000);server.stdout.on('data',d=>{text+=d;if(text.includes('\n')){clearTimeout(timer);resolve(JSON.parse(text.split('\n')[0]).url)}});server.once('exit',reject)});
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined});results.browser=browser.version();
 for(const width of [320,1366])for(const scenario of ['app-abort','no-js']){
  const context=await browser.newContext({viewport:{width,height:900},javaScriptEnabled:scenario!=='no-js'}),page=await context.newPage(),prefix=width+'/'+scenario;page.on('pageerror',e=>results.errors.push(e.message));
  if(scenario==='app-abort')await page.route('**/static/app.js',r=>r.abort());await page.goto(base+'/?lang=en&source=static-startup');
  check(prefix+' honest startup notice remains visible',await page.locator('#splash').isVisible()&&(await page.locator('#splash').innerText()).includes('JavaScript'));
  check(prefix+' unloaded application never says ready',!(await page.locator('#saveState').innerText()).includes('listo'));
  check(prefix+' editor and navigation are inert',await page.locator('main').evaluate(e=>e.inert)&&await page.locator('header').evaluate(e=>e.inert));
  const protocol=await context.newCDPSession(page),tree=await protocol.send('Accessibility.getFullAXTree');await protocol.detach();
  check(prefix+' dead editor buttons are absent from the native accessibility tree',!tree.nodes.some(node=>!node.ignored&&node.role?.value==='button'&&node.name?.value==='Nuevo proyecto'));
  const recovery=page.getByRole('link',{name:'Recargar / Reload',exact:true});check(prefix+' recovery is a native link available without app code',await recovery.isVisible()&&await recovery.getAttribute('href')==='');
  await recovery.focus();check(prefix+' recovery accepts keyboard focus',await recovery.evaluate(e=>document.activeElement===e));
  check(prefix+' startup notice fits a narrow or desktop viewport',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));await page.screenshot({path:path.join(out,prefix.replace('/','-')+'.png')});
  if(scenario==='app-abort'){
   await page.unroute('**/static/app.js');await page.keyboard.press('Enter');await page.waitForFunction(()=>!document.querySelector('#splash')&&!!document.querySelector('.workspace-dashboard'));
   check(prefix+' native reload preserves URL query parameters',new URL(page.url()).search==='?lang=en&source=static-startup');
   check(prefix+' native reload restores working application',await page.getByRole('button',{name:'Crear proyecto',exact:true}).isEnabled());check(prefix+' normal startup releases inert and removes notice',await page.locator('main[inert],header[inert],footer[inert],.skip-link[inert]').count()===0);
   await page.getByRole('button',{name:'Crear proyecto',exact:true}).click();check(prefix+' recovered create control opens a real modal',await page.locator('#newModal').evaluate(e=>e.matches(':modal')));
  }
  await context.close();
 }
 check('No script exceptions from static failure and recovery',results.errors.length===0);
})().catch(error=>{results.failure=error.stack;console.error(error);process.exitCode=1}).finally(async()=>{await browser?.close();server?.kill('SIGTERM');fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));});
