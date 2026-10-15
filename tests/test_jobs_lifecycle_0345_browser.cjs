/* Real-browser regression for export polling during pagehide and restoration.
 * The fixture serves the production ProgressUI and GET-only persistent jobs.
 * Synthetic persisted events make the BFCache lifecycle deterministic; this is
 * not a claim that every engine actually places this fixture in its BFCache. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),http=require('node:http'),assert=require('node:assert/strict');
const {createHash}=require('node:crypto');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),opt=(n,d)=>args.includes(n)?args[args.indexOf(n)+1]:d;
const engine=opt('--browser','webkit'),output=path.resolve(opt('--output','out/jobs-lifecycle-0345'));
const source=path.resolve(opt('--source',path.join(root,'webapp/static/progress.js'))),code=fs.readFileSync(source,'utf8');
const appSource=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
const languageHelpers=appSource.slice(appSource.indexOf('// Language selection'),appSource.indexOf('// ---- shared transport'));
assert.ok(languageHelpers.includes('function uiText('),'Production language helpers are available');
const playwright=require(require.resolve('playwright',{paths:[root]}));
const result={engine,source_sha256:createHash('sha256').update(code).digest('hex'),checks:[],errors:[],failedRequests:[],requests:[],limitations:['Restoration uses deterministic persisted PageTransitionEvent events; actual BFCache admission is not asserted.']};
fs.mkdirSync(output,{recursive:true});
const save=()=>fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(result,null,2));
const check=(name,value,detail)=>{result.checks.push({name,passed:!!value,detail});save();assert.ok(value,name);};
let browser,server,hold=false,fail=false,sequence=0;const waiting=new Set(),job={id:'fixture',label:'Server export',stage:'rendering_pdf',revision:'a'.repeat(64),verification_available:false};
const fixture=`<!doctype html><html lang="en"><title>Export polling lifecycle</title><body>
<div id="exportMenu"><div class="action-menu-body"></div></div><div id="projectActionsList"></div><div class="workspace-toolbar"></div>
<script>
const S={uiLang:'en',slug:null},projectStore={},projectBusyCount=0;
${languageHelpers}
const $=s=>document.querySelector(s);function h(tag,attrs,...kids){const el=document.createElement(tag);for(const[k,v]of Object.entries(attrs||{}))el.setAttribute(k,v);for(const c of kids.flat())if(c!=null)el.append(c.nodeType?c:String(c));return el;}
const appFetch=(...args)=>fetch(...args),requireOk=async r=>{if(!r.ok)throw Error('HTTP '+r.status);return r;};
window.qa={timers:new Set(),lastPoll:null,unhandled:[],persisted:[]};
const nativeSetTimeout=window.setTimeout.bind(window),nativeClearTimeout=window.clearTimeout.bind(window);
window.setTimeout=(cb,ms,...rest)=>{let id;id=nativeSetTimeout(()=>{qa.timers.delete(id);cb(...rest)},ms);if(cb.name==='pollJobs'){qa.timers.add(id);qa.lastPoll=cb;}return id;};
window.clearTimeout=id=>{qa.timers.delete(id);nativeClearTimeout(id)};
addEventListener('unhandledrejection',e=>qa.unhandled.push(String(e.reason)));
addEventListener('pageshow',e=>qa.persisted.push(e.persisted));
</script><script src="/progress.js"></script><script>ProgressUI.bind();window.progress=ProgressUI;</script></body></html>`;
const settle=page=>page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
(async()=>{try{
 server=http.createServer((req,res)=>{
  if(req.url==='/progress.js'){res.writeHead(200,{'Content-Type':'text/javascript'});res.end(code);return;}
  if(req.url==='/api/jobs'){
   result.requests.push({sequence:++sequence,method:req.method});res.on('close',()=>waiting.delete(res));
   if(hold){waiting.add(res);return;}
   res.writeHead(fail?500:200,{'Content-Type':'application/json'});res.end(JSON.stringify(fail?{error:'Simulated polling failure'}:[job]));return;
  }
  res.writeHead(200,{'Content-Type':'text/html'});res.end(fixture);
 });
 await new Promise(r=>server.listen(0,'127.0.0.1',r));const base='http://127.0.0.1:'+server.address().port;
 const executable=opt('--executable',engine==='chromium'?process.env.RG_CHROMIUM_EXECUTABLE:undefined);
 browser=await playwright[engine].launch({headless:true,...(executable?{executablePath:executable}:{})});result.version=browser.version();
 const page=await browser.newPage();page.on('pageerror',e=>{result.errors.push({name:e.name,message:e.message,stack:e.stack});save();});page.on('requestfailed',r=>result.failedRequests.push({url:r.url(),error:r.failure()}));
 await page.goto(base);await page.waitForFunction(()=>qa.timers.size===1);
 check('Initial polling has one scheduled continuation',await page.evaluate(()=>qa.timers.size===1));
 // Replay a previously queued polling callback at the real navigation boundary.
 // The old implementation emits the same WebKit access-control pageerror as CI.
 await page.evaluate(()=>{const queued=qa.lastPoll;addEventListener('pagehide',()=>queued(),{once:true});});
 await page.reload();await page.waitForFunction(()=>qa.timers.size===1);await settle(page);
 check('A queued callback during real pagehide creates no JavaScript error',result.errors.length===0,result.errors);
 const beforeHide=sequence;
 await page.evaluate(()=>{const queued=qa.lastPoll;dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true}));queued();});await settle(page);
 check('Suspended document has no poll timer or late GET',sequence===beforeHide&&await page.evaluate(()=>qa.timers.size===0));
 const restored=page.waitForResponse(r=>r.url().endsWith('/api/jobs'));
 await page.evaluate(()=>{dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true}));});await restored;await page.waitForFunction(()=>qa.timers.size===1);
 check('Repeated restoration starts exactly one polling loop',sequence===beforeHide+1&&await page.evaluate(()=>qa.timers.size===1));
 hold=true;const pending=page.waitForRequest(r=>r.url().endsWith('/api/jobs'));
 await page.evaluate(()=>progress.jobs());await pending;const beforeAbort=sequence;
 const aborted=page.waitForEvent('requestfailed',r=>r.url().endsWith('/api/jobs'));
 await page.evaluate(()=>dispatchEvent(new PageTransitionEvent('pagehide',{persisted:true})));await aborted;await settle(page);
 check('Leaving aborts the pending GET and does not schedule a successor',await page.evaluate(()=>qa.timers.size===0)&&sequence===beforeAbort);
 check('Polling abort never cancels the server export',job.stage==='rendering_pdf'&&result.requests.every(r=>r.method==='GET'));
 hold=false;job.stage='done';for(const res of waiting){res.writeHead(200,{'Content-Type':'application/json'});res.end(JSON.stringify([job]));}waiting.clear();
 await page.evaluate(()=>dispatchEvent(new PageTransitionEvent('pageshow',{persisted:true})));
 await page.locator('[data-job="fixture"][data-stage="done"]').waitFor();await page.waitForFunction(()=>qa.timers.size===1);
 check('Restoration shows the completed server job',await page.locator('[data-job="fixture"]').innerText().then(t=>t.includes('Ready to download')));
 fail=true;await page.evaluate(()=>qa.lastPoll());await page.locator('[data-job-notice]').filter({hasText:'HTTP 500'}).waitFor();
 check('A genuine polling failure remains visible and retryable',await page.evaluate(()=>qa.timers.size===1));
 fail=false;await page.evaluate(()=>qa.lastPoll());await page.waitForFunction(()=>document.querySelector('[data-job-notice]').textContent==='');
 check('Recovery clears the failure without duplicating timers',await page.evaluate(()=>qa.timers.size===1));
 check('No JavaScript error or unhandled rejection is filtered',result.errors.length===0&&await page.evaluate(()=>qa.unhandled.length===0));
 result.passed=true;save();console.log('PASS '+result.checks.length+' lifecycle checks in '+engine);
 }catch(error){result.failure=String(error.stack||error);result.passed=false;save();console.error(error);process.exitCode=1;}
 finally{await browser?.close();server?.closeAllConnections();if(server)await new Promise(r=>server.close(r));}
})();
