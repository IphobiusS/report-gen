/* Production comparison dialog: request lifecycle and private blob ownership. */
'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),app=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
const helpers=app.slice(0,app.indexOf('// ---- shared transport'));
const source=fs.readFileSync(path.join(root,'webapp/static/pdf-compare.js'),'utf8');
const capabilities={available:true,max_pdf_bytes:16*1024*1024,max_output_bytes:32*1024*1024};
const settle=()=>new Promise(resolve=>setImmediate(resolve));
async function until(predicate){for(let turn=0;turn<30;turn++){if(predicate())return;await settle();}assert.fail('UI did not settle');}
function setup(language='en',request){
 const dom=new JSDOM('<button id="entry">Open</button><input id="globalSearch"><div id="searchResults"><button id="command">Compare</button></div><main id="editor" tabindex="-1"></main>',{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,requests=[],created=[],revoked=[];
 w.S={uiLang:language,data:{findings:[{title:'Preserve this exact report'}]}};
 w.scopedResourceURL=value=>value;
 w.appFetch=(url,options={})=>{requests.push({url,options});return request?request(url,options):Promise.resolve(new Response(url.endsWith('/capabilities')?JSON.stringify(capabilities):'<!doctype html><p>Compared</p>',{headers:{'Content-Type':url.endsWith('/capabilities')?'application/json':'text/html'}}));};
 w.requireOk=async response=>{if(!response.ok)throw Error((await response.json()).error);return response;};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
 w.URL.createObjectURL=blob=>{const url='blob:comparison-'+created.length;created.push({url,blob});return url;};
 w.URL.revokeObjectURL=url=>revoked.push(url);
 w.eval(helpers+'\n'+source+'\nwindow.comparison=PDFComparisonUI;');
 const get=selector=>w.document.querySelector(selector),entry=get('#entry');entry.focus();
 w.comparison.open(entry);
 function files(size=40){for(const selector of ['[data-pdf-before]','[data-pdf-after]']){const input=get(selector),file=new w.File(['%PDF synthetic'],selector+'.pdf',{type:'application/pdf'});Object.defineProperty(file,'size',{value:size});Object.defineProperty(input,'files',{configurable:true,value:[file]});input.dispatchEvent(new w.Event('change'));}}
 return {dom,w,get,entry,files,requests,created,revoked,close:()=>dom.window.close()};
}

for(const language of ['es','en','pt'])test('PDF comparison '+language+' retains one sandboxed result and revokes it when inputs change',async()=>{
 const q=setup(language);try{
  const snapshot=JSON.stringify(q.w.S.data);await until(()=>q.get('[data-pdf-compare-status]').textContent.includes({es:'Selecciona',en:'Select',pt:'Selecione'}[language]));q.files();q.get('[data-pdf-compare-submit]').click();
  await until(()=>q.get('[data-pdf-compare-frame]'));
  const request=q.requests.find(r=>r.options.method==='POST');assert.ok(request);assert.equal(request.url,'/api/pdf-compare');assert.equal(request.options.body.get('language'),language);assert.equal(request.options.body.getAll('before').length,1);assert.equal(request.options.body.getAll('after').length,1);
  const frame=q.get('iframe'),download=q.get('[data-pdf-compare-download]');assert.equal(frame.getAttribute('sandbox'),'');assert.equal(frame.getAttribute('referrerpolicy'),'no-referrer');assert.equal(frame.getAttribute('src'),download.getAttribute('href'));assert.equal(q.created.length,1);assert.equal(JSON.stringify(q.w.S.data),snapshot);
  q.files();assert.equal(q.get('iframe'),null);assert.deepEqual(q.revoked,[q.created[0].url]);assert.equal(q.get('[data-pdf-compare-download]'),null);
  q.get('dialog').close();assert.equal(q.get('dialog'),null);assert.equal(q.w.document.activeElement,q.entry);assert.equal(JSON.stringify(q.w.S.data),snapshot);
 }finally{q.close();}
});

test('PDF comparison rejects empty and oversized files before sending data',async()=>{
 const q=setup();try{await settle();for(const size of [0,16*1024*1024+1]){q.files(size);q.get('[data-pdf-compare-submit]').click();await settle();assert.match(q.get('[data-pdf-compare-error]').textContent,/16 MiB/);assert.equal(q.requests.filter(r=>r.options.method==='POST').length,0);assert.equal(q.created.length,0);}}finally{q.close();}
});

test('PDF comparison cancellation aborts transport and ignores a response that arrives late',async()=>{
 let resolve;const response=new Promise(done=>resolve=done);
 const q=setup('en',url=>url.endsWith('/capabilities')?Promise.resolve(Response.json(capabilities)):response);
 try{
  await settle();q.files();q.get('[data-pdf-compare-submit]').click();const pending=q.requests.find(r=>r.options.method==='POST');assert.ok(pending);q.get('[data-pdf-compare-submit]').click();assert.equal(q.requests.filter(r=>r.options.method==='POST').length,1);
  q.get('[data-pdf-compare-cancel]').click();assert.ok(pending.options.signal.aborted);assert.match(q.get('[data-pdf-compare-status]').textContent,/Waiting cancelled.*45 seconds/);assert.equal(q.get('[data-pdf-compare-submit]').disabled,false);
  resolve(new Response('<p>Stale comparison</p>',{headers:{'Content-Type':'text/html'}}));await settle();await settle();assert.equal(q.created.length,0);assert.equal(q.get('iframe'),null);assert.equal(q.get('[data-pdf-compare-download]'),null);
 }finally{q.close();}
});

test('PDF comparison close aborts outstanding capability lookup and restores command search focus',async()=>{
 let resolve;const pending=new Promise(done=>resolve=done);const q=setup('en',()=>pending);
 try{
  q.get('dialog').close();assert.ok(q.requests[0].options.signal.aborted);
  q.w.comparison.open(q.get('#command'));q.get('dialog').dispatchEvent(new q.w.Event('cancel',{cancelable:true}));assert.equal(q.get('dialog'),null);assert.equal(q.w.document.activeElement,q.get('#globalSearch'));assert.ok(q.requests[1].options.signal.aborted);
  resolve(Response.json(capabilities));await settle();assert.equal(q.get('dialog'),null);assert.equal(q.created.length,0);
 }finally{q.close();}
});

test('PDF comparison rejects a non-HTML response and permits another attempt',async()=>{
 const q=setup('en',url=>Promise.resolve(url.endsWith('/capabilities')?Response.json(capabilities):Response.json({error:'unexpected body'})));
 try{await settle();q.files();q.get('[data-pdf-compare-submit]').click();await until(()=>q.get('[data-pdf-compare-error]').textContent);assert.match(q.get('[data-pdf-compare-error]').textContent,/not a valid HTML/);assert.equal(q.get('[data-pdf-compare-submit]').disabled,false);assert.equal(q.created.length,0);}finally{q.close();}
});

test('PDF comparison close discards both result URL and selected input values',async()=>{
 const q=setup();try{await settle();q.files();q.get('[data-pdf-compare-submit]').click();await until(()=>q.get('iframe'));const before=q.get('[data-pdf-before]'),after=q.get('[data-pdf-after]');q.get('dialog').close();assert.deepEqual(q.revoked,q.created.map(item=>item.url));assert.equal(before.value,'');assert.equal(after.value,'');assert.equal(q.get('dialog'),null);}finally{q.close();}
});
