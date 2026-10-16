/* Production UI state: manual coverage, source binding and explicit private saves. */
'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),app=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8'),source=fs.readFileSync(path.join(root,'webapp/static/pdf-compare.js'),'utf8');
const helpers=app.slice(0,app.indexOf('// ---- shared transport')),receipt='a'.repeat(43),uid='d61f2ae0-1949-4dc5-8267-40974a6c9c7b';
const cap={available:true,max_pdf_bytes:16*1024*1024,max_output_bytes:32*1024*1024};
const metadata=()=>({schema:'report-gen-pdf-metadata/1',before:{sha256:'b'.repeat(64),bytes:14,pages:[1,2,3].map(number=>({number,width:240,height:300}))},after:{sha256:'c'.repeat(64),bytes:14,pages:[1,2,3,4].map(number=>({number,width:240,height:300}))}});
const record={schema:'report-gen-pdf-comparison-review/1',uid,created:'2026-01-02T03:04:05Z',author:'Reviewer',decision:'issues',note:'Inspect page 2',page_pairs:[{before_page:1,after_page:2}],summary:{changed:1}};
const result=()=>new Response('<p>Compared pages</p>',{headers:{'Content-Type':'text/html','X-Report-Gen-Comparison-Id':receipt}});
const settle=()=>new Promise(resolve=>setImmediate(resolve));
async function until(predicate){for(let i=0;i<40;i++){if(predicate())return;await settle();}assert.fail('UI did not settle');}
function setup(language='en',handler){
 const dom=new JSDOM('<button id="entry">Open</button><main id="editor" tabindex="-1"></main>',{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true}),w=dom.window,requests=[],created=[],revoked=[],downloads=[],saves=[];
 w.S={slug:'case',uiLang:language,data:{meta:{report_title:'Exact report'},findings:[]}};w.projectStore={etag:'"rev1"',loading:false,dirty:false};w.scopedResourceURL=value=>value;w.busyProject=value=>saves.push({busy:value});w.doSave=async()=>{saves.push({save:true});return true;};w.adoptSavedProject=async(data,etag)=>{w.S.data=data;w.projectStore.etag=etag;saves.push({adopt:true});};
 function defaultResponse(url,options){if(url.endsWith('/capabilities'))return Response.json(cap);if(url.endsWith('/metadata'))return Response.json(metadata());if(options.method==='DELETE')return new Response(null,{status:204});if(url==='/api/pdf-compare')return result();if(url.endsWith('/pdf-comparisons')&&options.method==='POST')return Response.json({record,records:[record],data:{...w.S.data,attachments:[{uid}]}},{status:201,headers:{ETag:'"rev2"'}});if(url.endsWith('/pdf-comparisons'))return Response.json({records:[record]},{headers:{ETag:'"rev1"'}});return Response.json(record);}
 w.appFetch=async(url,options={})=>{requests.push({url,options});return handler?handler(url,options,defaultResponse):defaultResponse(url,options);};
 w.requireOk=async response=>{if(!response.ok)throw Error((await response.json()).error);return response;};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
 w.HTMLAnchorElement.prototype.click=function(){downloads.push({href:this.href,name:this.download});};
 w.URL.createObjectURL=blob=>{const url='blob:owned-'+created.length;created.push({url,blob});return url;};w.URL.revokeObjectURL=url=>revoked.push(url);
 w.eval(helpers+'\n'+source+'\nwindow.comparison=PDFComparisonUI;');const get=selector=>w.document.querySelector(selector);get('#entry').focus();w.comparison.open(get('#entry'));
 function files(){for(const selector of ['[data-pdf-before]','[data-pdf-after]']){const input=get(selector);Object.defineProperty(input,'files',{configurable:true,value:[new w.File(['%PDF synthetic'],selector+'.pdf',{type:'application/pdf'})]});input.dispatchEvent(new w.Event('change'));}}
 function choose(number,value){const select=get('[data-pdf-pair="'+number+'"]');select.value=String(value);select.dispatchEvent(new w.Event('change'));}
 async function inspect(){await settle();files();get('[data-pdf-pair-open]').click();await until(()=>get('[data-pdf-pair="1"]')&&!get('[data-pdf-pair="1"]').disabled);}
 async function compare(){get('[data-pdf-compare-submit]').click();await until(()=>get('[data-pdf-compare-frame]'));}
 return {w,dom,get,files,choose,inspect,compare,requests,created,revoked,downloads,saves,close:()=>{get('dialog')?.close();w.close();}};
}

for(const language of ['es','en','pt'])test(language+' manual mapping covers all pages, blocks duplicates and binds metadata hashes',async()=>{
 const q=setup(language);try{
  const exact=JSON.stringify(q.w.S.data);await q.inspect();assert.equal(q.w.document.activeElement,q.get('[data-pdf-pair="1"]'));q.choose(1,2);assert.equal(q.get('[data-pdf-compare-submit]').disabled,true);assert.equal(q.get('[data-pdf-pair="1"]').getAttribute('aria-invalid'),'true');
  q.choose(2,1);q.choose(3,'');assert.equal(q.get('[data-pdf-compare-submit]').disabled,false);assert.match(q.get('[data-pdf-added-pages]').textContent,/3, 4/);await q.compare();
  const request=q.requests.find(r=>r.url==='/api/pdf-compare');assert.deepEqual(JSON.parse(request.options.body.get('page_pairs')),[{before:1,after:2},{before:2,after:1},{before:3,after:null},{before:null,after:3},{before:null,after:4}]);
  assert.equal(request.options.body.get('expected_before_sha256'),'b'.repeat(64));assert.equal(request.options.body.get('expected_after_sha256'),'c'.repeat(64));assert.equal(request.options.body.get('language'),language);assert.equal(JSON.stringify(q.w.S.data),exact);assert.deepEqual(q.saves,[]);
  q.choose(1,1);assert.equal(q.get('iframe'),null);assert.deepEqual(q.revoked,[q.created[0].url]);assert.ok(q.requests.some(r=>r.options.method==='DELETE'&&r.url.endsWith(receipt)));
  q.get('[data-pdf-pair-reset]').click();assert.equal(q.get('[data-pdf-pair="1"]').value,'1');assert.equal(q.get('[data-pdf-pair="3"]').value,'3');assert.equal(q.get('[data-pdf-compare-submit]').disabled,false);
  q.get('[data-pdf-pair-positional]').click();await q.compare();const positional=q.requests.filter(r=>r.url==='/api/pdf-compare').at(-1).options.body;assert.equal(positional.has('page_pairs'),false);assert.equal(positional.has('expected_before_sha256'),false);assert.equal(positional.has('expected_after_sha256'),false);
 }finally{q.close();}
});

test('metadata structure, page ranges and file lengths are validated before mapping',async()=>{
 const invalid=[m=>m.schema='unknown',m=>m.before.sha256='short',m=>m.after.pages[0].number=2,m=>m.after.pages[0].width=0,m=>m.before.bytes++,m=>m.before.pages=[],m=>m.after.pages=Array.from({length:81},(_,i)=>({number:i+1,width:10,height:10}))];
 for(const change of invalid){const value=metadata();change(value);const q=setup('en',(url,opt,fallback)=>url.endsWith('/metadata')?Response.json(value):fallback(url,opt));try{await settle();q.files();q.get('[data-pdf-pair-open]').click();await until(()=>q.get('[data-pdf-compare-error]').textContent);assert.match(q.get('[data-pdf-compare-error]').textContent,/page information is invalid/);assert.equal(q.get('[data-pdf-pairs]').hidden,true);assert.equal(q.get('[data-pdf-compare-submit]').disabled,false);}finally{q.close();}}
});

test('file changes abort inspection and ignore stale metadata, then allow a fresh inspection',async()=>{
 let finish,hold=true;const delayed=new Promise(resolve=>finish=resolve);const q=setup('en',(url,opt,fallback)=>url.endsWith('/metadata')&&hold?delayed:fallback(url,opt));
 try{await settle();q.files();q.get('[data-pdf-pair-open]').click();await until(()=>q.requests.some(r=>r.url.endsWith('/metadata')));const request=q.requests.at(-1);q.files();assert.equal(request.options.signal.aborted,true);finish(Response.json(metadata()));await settle();assert.equal(q.get('[data-pdf-pairs]').hidden,true);hold=false;q.get('[data-pdf-pair-open]').click();await until(()=>q.get('[data-pdf-pair="1"]'));assert.equal(q.get('[data-pdf-pairs]').hidden,false);}finally{q.close();}
});

test('replacing a File identity without an event cannot submit the old inspected mapping',async()=>{
 const q=setup();try{await q.inspect();const input=q.get('[data-pdf-before]');Object.defineProperty(input,'files',{configurable:true,value:[new q.w.File(['%PDF changed!!'],'changed.pdf')]});q.get('[data-pdf-compare-submit]').click();await settle();assert.equal(q.requests.filter(r=>r.url==='/api/pdf-compare').length,0);}finally{q.close();}
});

test('closing an in-flight comparison discards a late receipt and never creates its URL',async()=>{
 let finish;const delayed=new Promise(resolve=>finish=resolve),q=setup('en',(url,opt,fallback)=>url==='/api/pdf-compare'?delayed:fallback(url,opt));
 try{await settle();q.files();q.get('[data-pdf-compare-submit]').click();const request=q.requests.at(-1);q.get('dialog').close();assert.equal(request.options.signal.aborted,true);finish(result());await settle();assert.equal(q.created.length,0);assert.ok(q.requests.some(r=>r.options.method==='DELETE'&&r.url.endsWith(receipt)));assert.equal(q.w.document.activeElement,q.get('#entry'));}finally{q.close();}
});

test('private save is explicit, sends current ETag, adopts data and loads downloadable records',async()=>{
 const q=setup();try{await settle();q.files();await q.compare();assert.deepEqual(q.saves,[]);q.get('[data-pdf-review-open]').click();assert.equal(q.w.document.activeElement,q.get('[data-pdf-review-author]'));q.get('[data-pdf-review-author]').value=' Reviewer ';q.get('[data-pdf-review-decision]').value='issues';q.get('[data-pdf-review-decision]').dispatchEvent(new q.w.Event('change'));assert.equal(q.get('[data-pdf-review-note]').required,true);
  q.get('[data-pdf-review-form]').dispatchEvent(new q.w.Event('submit',{cancelable:true}));await settle();assert.equal(q.requests.filter(r=>r.url.endsWith('/pdf-comparisons')&&r.options.method==='POST').length,0);
  q.get('[data-pdf-review-note]').value=' Inspect page 2 ';q.get('[data-pdf-review-form]').dispatchEvent(new q.w.Event('submit',{cancelable:true}));await until(()=>q.get('[data-pdf-record]'));
  const sent=q.requests.find(r=>r.url.endsWith('/pdf-comparisons')&&r.options.method==='POST');assert.deepEqual(JSON.parse(sent.options.body),{comparison_id:receipt,author:'Reviewer',decision:'issues',note:'Inspect page 2'});assert.equal(sent.options.headers['If-Match'],'"rev1"');assert.equal(q.w.projectStore.etag,'"rev2"');assert.equal(q.w.S.data.attachments[0].uid,uid);assert.equal(q.get('[data-pdf-review-form]').hidden,true);assert.equal(q.w.document.activeElement,q.get('[data-pdf-review-open]'));
  q.get('[data-pdf-record-reload]').click();await until(()=>q.requests.filter(r=>r.url.endsWith('/pdf-comparisons')&&!r.options.method).length===1);await settle();q.get('[data-pdf-record-download]').click();await until(()=>q.downloads.length);assert.equal(q.downloads[0].name,'report-gen-pdf-review-'+uid+'.json');q.get('dialog').close();assert.deepEqual(q.revoked.sort(),q.created.map(v=>v.url).sort());
 }finally{q.close();}
});

test('expired receipts show server error without claiming a save or changing project data',async()=>{
 const q=setup('en',(url,opt,fallback)=>url.endsWith('/pdf-comparisons')&&opt.method==='POST'?Response.json({error:'Comparison receipt expired'},{status:404}):fallback(url,opt));
 try{await settle();q.files();await q.compare();const exact=JSON.stringify(q.w.S.data);q.get('[data-pdf-review-open]').click();q.get('[data-pdf-review-author]').value='Reviewer';q.get('[data-pdf-review-form]').dispatchEvent(new q.w.Event('submit',{cancelable:true}));await until(()=>q.get('[data-pdf-review-status]').textContent.includes('expired'));assert.equal(JSON.stringify(q.w.S.data),exact);assert.equal(q.get('[data-pdf-review-form]').hidden,false);assert.equal(q.get('[data-pdf-review-save]').disabled,false);assert.equal(q.saves.some(s=>s.adopt),false);}finally{q.close();}
});

test('a changed project blocks private saves and requests for another project',async()=>{
 const q=setup();try{await settle();q.files();await q.compare();q.w.S.slug='other';q.get('[data-pdf-review-open]').click();q.get('[data-pdf-review-author]').value='Reviewer';q.get('[data-pdf-review-form]').dispatchEvent(new q.w.Event('submit',{cancelable:true}));await until(()=>q.get('[data-pdf-review-status]').textContent.includes('project changed'));q.get('[data-pdf-record-reload]').click();await settle();assert.equal(q.requests.filter(r=>r.url.includes('/projects/')).length,0);assert.equal(q.saves.some(s=>s.save),false);}finally{q.close();}
});

test('closing aborts a record list and ignores its late response',async()=>{
 let finish;const delayed=new Promise(resolve=>finish=resolve),q=setup('en',(url,opt,fallback)=>url.endsWith('/pdf-comparisons')?delayed:fallback(url,opt));
 try{await settle();q.get('[data-pdf-record-reload]').click();const request=q.requests.at(-1);q.get('dialog').close();assert.equal(request.options.signal.aborted,true);finish(Response.json({records:[record]}));await settle();assert.equal(q.get('[data-pdf-record]'),null);assert.equal(q.created.length,0);}finally{q.close();}
});
