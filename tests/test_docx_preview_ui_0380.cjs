/* Actual native DOCX dialog: immutable source, cancellation and blob ownership. */
'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
const app=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
const helpers=app.slice(0,app.indexOf('// ---- shared transport'));
const source=fs.readFileSync(path.join(root,'webapp/static/docx-preview.js'),'utf8');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
async function until(predicate){for(let i=0;i<50;i++){if(predicate())return;await settle();}assert.fail('Native DOCX dialog did not settle');}
const ready={id:'preview-id',stage:'done',revision:'immutable-revision',source_docx_sha256:'a'.repeat(64),receipt:{engine:{name:'LibreOffice',version:'LibreOffice test renderer'},pages:12,source_revision:'immutable-revision',source_docx_sha256:'a'.repeat(64),pdf_sha256:'b'.repeat(64),word_verified:false}};
function setup(language='en',handler){
 const dom=new JSDOM('<button id="open">Preview</button>',{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
 const w=dom.window,requests=[],created=[],revoked=[];
 w.S={uiLang:language,data:{findings:[{title:'Keep authored content'}]}};
 w.scopedResourceURL=value=>value;
 w.appFetch=(url,options={})=>{requests.push({url,options});if(handler)return handler(url,options);
   if(url.endsWith('/capabilities'))return Promise.resolve(Response.json({available:true}));
   if(url.endsWith('/pdf'))return Promise.resolve(new Response('%PDF synthetic transport fixture',{headers:{'Content-Type':'application/pdf'}}));
   return Promise.resolve(Response.json(options.method==='POST'&&url.endsWith('/docx-preview')?{id:'preview-id',stage:'rendering'}:ready));};
 w.requireOk=async r=>{if(!r.ok)throw Error((await r.json()).error);return r;};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
 w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
 w.URL.createObjectURL=blob=>{const url='blob:native-'+created.length;created.push({url,blob});return url;};
 w.URL.revokeObjectURL=url=>revoked.push(url);
 w.eval(helpers+'\n'+source+'\nwindow.preview=DocxPreviewUI;');
 const get=s=>w.document.querySelector(s),entry=get('#open');entry.focus();
 w.preview.open({id:'own-job',stage:'done',revision:'immutable-revision',filename:'report.docx'},entry);
 return {w,dom,get,entry,requests,created,revoked,close:()=>dom.window.close()};
}
for(const language of ['es','en','pt'])test('Native DOCX '+language+' shows real renderer provenance without mutating authored source',async()=>{
 const q=setup(language);try{
  const before=JSON.stringify(q.w.S.data);await until(()=>!q.get('[data-docx-preview-run]').disabled);
  q.get('[data-docx-preview-run]').click();await until(()=>q.get('[data-docx-preview-frame]')||q.get('[data-docx-preview-error]').textContent);
  assert.equal(q.get('[data-docx-preview-error]').textContent,'');
  const request=q.requests.find(r=>r.options.method==='POST');assert.equal(request.url,'/api/jobs/own-job/docx-preview');assert.equal(request.options.body,'{}');
  assert.match(q.get('[data-docx-preview-engine]').textContent,/LibreOffice test renderer.*12/);
  assert.ok(q.get('[data-docx-preview-output]').textContent.includes('a'.repeat(64)));
  assert.ok(q.get('[data-docx-preview-output]').textContent.includes('immutable-revision'));
  assert.match(q.get('dialog').textContent,/Microsoft Word/);assert.equal(q.created.length,2);
  assert.equal(q.get('iframe').getAttribute('src'),q.created[0].url);assert.equal(q.get('iframe').getAttribute('referrerpolicy'),'no-referrer');
  assert.equal(JSON.stringify(q.w.S.data),before);q.get('dialog').close();await until(()=>q.requests.some(r=>r.options.method==='DELETE'));
  assert.deepEqual(q.revoked,q.created.map(r=>r.url));assert.equal(q.w.document.activeElement,q.entry);assert.equal(q.get('dialog'),null);
 }finally{q.close();}
});
test('Missing LibreOffice is actionable and never launches a conversion',async()=>{
 const q=setup('en',()=>Promise.resolve(Response.json({available:false,unavailable_message:'Install LibreOffice Writer and reopen report-gen.'})));
 try{await until(()=>q.get('[data-docx-preview-status]').textContent);assert.match(q.get('[data-docx-preview-status]').textContent,/Install LibreOffice Writer/);assert.equal(q.get('[data-docx-preview-run]').disabled,true);q.get('[data-docx-preview-run]').click();assert.equal(q.requests.length,1);}finally{q.close();}
});
test('Closing before a late POST response cancels and removes its conversion',async()=>{
 let resolve;const deferred=new Promise(r=>resolve=r);
 const q=setup('en',(url,opts)=>url.endsWith('/capabilities')?Promise.resolve(Response.json({available:true})):url==='/api/jobs/own-job/docx-preview'?deferred:Promise.resolve(Response.json({id:'preview-id',stage:'cancelled'})));
 try{await until(()=>!q.get('[data-docx-preview-run]').disabled);q.get('[data-docx-preview-run]').click();q.get('dialog').close();resolve(Response.json({id:'preview-id',stage:'rendering'}));await until(()=>q.requests.some(r=>r.options.method==='DELETE'));assert.ok(q.requests.some(r=>r.url==='/api/docx-preview/preview-id/cancel'));assert.equal(q.created.length,0);assert.equal(q.get('dialog'),null);}finally{q.close();}
});
test('Duplicate clicks create only one conversion and cancellation reaches server',async()=>{
 let stage='rendering';
 const q=setup('en',(url,opts)=>{if(url.endsWith('/capabilities'))return Promise.resolve(Response.json({available:true}));if(url.endsWith('/cancel'))stage='cancelled';return Promise.resolve(Response.json({id:'preview-id',stage}));});
 try{await until(()=>!q.get('[data-docx-preview-run]').disabled);q.get('[data-docx-preview-run]').click();q.get('[data-docx-preview-run]').click();await until(()=>q.requests.some(r=>r.url==='/api/docx-preview/preview-id'));assert.equal(q.requests.filter(r=>r.url==='/api/jobs/own-job/docx-preview').length,1);q.get('[data-docx-preview-cancel]').click();await until(()=>q.get('[data-docx-preview-status]').textContent.includes('cancelled'));assert.equal(q.created.length,0);assert.equal(q.get('[data-docx-preview-run]').disabled,false);}finally{q.close();}
});
test('Cancellation before the POST response is remembered and applied to its eventual job',async()=>{
 let resolve;const deferred=new Promise(r=>resolve=r);
 const q=setup('en',url=>url.endsWith('/capabilities')?Promise.resolve(Response.json({available:true})):url==='/api/jobs/own-job/docx-preview'?deferred:Promise.resolve(Response.json({id:'preview-id',stage:'cancelled'})));
 try{await until(()=>!q.get('[data-docx-preview-run]').disabled);q.get('[data-docx-preview-run]').click();q.get('[data-docx-preview-cancel]').click();assert.match(q.get('[data-docx-preview-status]').textContent,/Cancellation requested/);resolve(Response.json({id:'preview-id',stage:'rendering'}));await until(()=>q.get('[data-docx-preview-status]').textContent.includes('cancelled'));assert.ok(q.requests.some(r=>r.url.endsWith('/preview-id/cancel')));assert.equal(q.created.length,0);assert.equal(q.get('[data-docx-preview-run]').disabled,false);}finally{q.close();}
});
for(const mismatch of ['source','revision','word'])test('Native preview refuses receipt '+mismatch+' mismatch',async()=>{
 const invalid=JSON.parse(JSON.stringify(ready));if(mismatch==='source')invalid.receipt.source_docx_sha256='c'.repeat(64);if(mismatch==='revision')invalid.receipt.source_revision='other';if(mismatch==='word')invalid.receipt.word_verified=true;
 const q=setup('en',url=>Promise.resolve(Response.json(url.endsWith('/capabilities')?{available:true}:url==='/api/jobs/own-job/docx-preview'?{id:'preview-id',stage:'rendering'}:invalid)));
 try{await until(()=>!q.get('[data-docx-preview-run]').disabled);q.get('[data-docx-preview-run]').click();await until(()=>q.get('[data-docx-preview-error]').textContent);assert.match(q.get('[data-docx-preview-error]').textContent,/Invalid DOCX preview receipt/);assert.equal(q.created.length,0);assert.equal(q.requests.filter(r=>r.url.endsWith('/pdf')).length,0);}finally{q.close();}
});
test('Closing during PDF download discards the late blob',async()=>{
 let resolve;const deferred=new Promise(r=>resolve=r);
 const q=setup('en',url=>url.endsWith('/pdf')?deferred:Promise.resolve(Response.json(url.endsWith('/capabilities')?{available:true}:url==='/api/jobs/own-job/docx-preview'?{id:'preview-id',stage:'rendering'}:ready)));
 try{await until(()=>!q.get('[data-docx-preview-run]').disabled);q.get('[data-docx-preview-run]').click();await until(()=>q.requests.some(r=>r.url.endsWith('/pdf')));assert.equal(q.get('[data-docx-preview-run]').disabled,true);q.get('dialog').close();assert.equal(q.requests.find(r=>r.url.endsWith('/pdf')).options.signal.aborted,true);resolve(new Response('%PDF late',{headers:{'Content-Type':'application/pdf'}}));await settle();await settle();assert.equal(q.created.length,0);assert.equal(q.get('iframe'),null);}finally{q.close();}
});
