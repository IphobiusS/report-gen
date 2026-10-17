/* Production instance forms: scoped persistence, failure retention and CAS adoption. */
'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),app=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
const helpers=app.slice(0,app.indexOf('// ---- shared transport')),source=fs.readFileSync(path.join(root,'webapp/static/instances.js'),'utf8');
const settle=()=>new Promise(resolve=>setImmediate(resolve));
async function until(fn){for(let i=0;i<60;i++){if(fn())return;await settle();}assert.fail('Instance dialog did not settle');}
function setup(lang='en',handler){
  const dom=new JSDOM('<main id="host"></main>',{url:'http://localhost/',runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window,requests=[],saved=[],registry=new Map();
  w.S={slug:'synthetic',workspace_id:'workspace',uiLang:lang,previewMode:'off',data:{meta:{assessor:'Synthetic tester'},assets:[],evidence:[],findings:[{uid:'finding',title:'Synthetic',status:'open',instances:[]}]}};
  w.structuredClone=structuredClone;w.projectStore={revision:1,etag:'"revision-1"',dirty:false,loading:false};w.projectBusyCount=0;w.busyProject=value=>{w.projectBusyCount+=value?1:-1;};
  w.doSave=async()=>true;w.renderSidebar=()=>{};w.renderMain=()=>{};w.refreshLivePreview=()=>{};w.toast=()=>{};w.BrowserWorkspace={current:()=>w.S.workspace_id};
  w.PendingUI={active:new Map(),register:(prefix,callbacks)=>registry.set(prefix,callbacks),track:(key,title,read)=>{const handle={key,read,revision:0,persisted:0};w.PendingUI.active.set(w.S.slug+'|'+key,handle);return handle;},changed:handle=>{handle.revision++;handle.persisted=handle.revision;saved.push(structuredClone(handle.read()));},status:()=>w.document.createElement('p'),clear:async handle=>{w.PendingUI.active.delete(w.S.slug+'|'+handle.key);return true;},committed:async handle=>{w.PendingUI.active.delete(w.S.slug+'|'+handle.key);return {finished:true};}};
  w.appFetch=(url,options)=>{requests.push({url,options});if(handler)return handler(url,options);const data=structuredClone(w.S.data);data.findings[0].instances.push({uid:'new-instance',...JSON.parse(options.body)});return Promise.resolve(Response.json({data},{headers:{ETag:'"revision-2"'}}));};
  w.requireOk=async response=>{if(!response.ok)throw Error((await response.json()).error);return response;};
  w.adoptSavedProject=async(data,etag)=>{w.S.data=data;w.projectStore.etag=etag;w.projectStore.revision++;};
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
  w.workspacePageBar=()=>w.document.createElement('div');w.eval(helpers+'\n'+source+'\nwindow.instances=InstancesUI;');
  const get=s=>w.document.querySelector(s),set=(field,value)=>{const input=get('[data-instance-field="'+field+'"]');input.value=value;input.dispatchEvent(new w.Event('input',{bubbles:true}));};
  w.instances.render(get('#host'),w.S.data.findings[0]);
  return {w,dom,get,set,requests,saved,registry,close:()=>dom.window.close()};
}
for(const lang of ['es','en','pt'])test('Instance '+lang+' form keeps local draft until explicit revision-bound save',async()=>{
  const q=setup(lang);try{
    q.get('[data-instance-create]').click();q.set('endpoint','/synthetic/account');q.set('identity','Tenant A role');q.set('owner','Team A');
    assert.equal(q.w.S.data.findings[0].instances.length,0);assert.equal(q.requests.length,0);assert.equal(q.saved.at(-1).data.values.owner,'Team A');
    const pending=q.w.PendingUI.active.values().next().value;const row={key:pending.key,data:pending.read().data};q.registry.get('instance:').validate(row);
    q.get('dialog').close();assert.equal(q.w.S.data.findings[0].instances.length,0);q.get('[data-instance-create]').click();assert.equal(q.get('[data-instance-field="owner"]').value,'Team A');
    q.get('[data-instance-save]').click();await until(()=>!q.get('dialog'));
    assert.equal(q.requests.length,1);assert.equal(q.requests[0].options.headers['If-Match'],'"revision-1"');assert.equal(q.requests[0].url,'/api/projects/synthetic/findings/finding/instances');
    assert.equal(q.w.S.data.findings[0].instances[0].identity,'Tenant A role');assert.equal(q.w.projectStore.etag,'"revision-2"');assert.equal(q.w.projectBusyCount,0);
  }finally{q.close();}
});
test('Failed instance save retains form and pending data for retry',async()=>{
  const q=setup('en',()=>Promise.resolve(Response.json({error:'Synthetic revision conflict'},{status:409})));try{
    q.get('[data-instance-create]').click();q.set('endpoint','/keep');q.get('[data-instance-save]').click();await until(()=>q.get('[role="alert"]').textContent);
    assert.match(q.get('[role="alert"]').textContent,/revision conflict/);assert.equal(q.get('[data-instance-field="endpoint"]').value,'/keep');assert.equal(q.w.S.data.findings[0].instances.length,0);assert.equal(q.w.PendingUI.active.size,1);assert.equal(q.get('[data-instance-save]').disabled,false);
  }finally{q.close();}
});
test('Late success never overwrites a changed local report',async()=>{
  let resolve;const pending=new Promise(done=>resolve=done),q=setup('en',()=>pending);try{
    q.get('[data-instance-create]').click();q.set('endpoint','/late');q.get('[data-instance-save]').click();await until(()=>q.requests.length);
    const server=structuredClone(q.w.S.data);server.findings[0].instances.push({uid:'new',endpoint:'/late'});q.w.S.data.findings[0].title='Preserve newer local draft';
    resolve(Response.json({data:server},{headers:{ETag:'"revision-2"'}}));await until(()=>q.get('[role="alert"]').textContent);
    assert.match(q.get('[role="alert"]').textContent,/draft changed/);assert.equal(q.w.S.data.findings[0].title,'Preserve newer local draft');assert.equal(q.w.S.data.findings[0].instances.length,0);assert.equal(q.w.projectStore.etag,'"revision-1"');
  }finally{q.close();}
});
test('Retest form targets selected instance and does not allow manual verified status',()=>{
  const q=setup();try{
    const f=q.w.S.data.findings[0],instance={uid:'instance-A',endpoint:'/a',status:'open',evidence_uids:[],retests:[]};f.instances.push(instance);
    q.w.instances.open(f,instance,'edit');assert.equal(q.get('[data-instance-field="status"] option[value="verified_fixed"]'),null);q.get('dialog').close();
    q.w.instances.open(f,instance,'retest');q.set('notes_md','Compared A and B');q.set('result','fixed');const record=q.saved.at(-1).data;assert.equal(record.instance_uid,'instance-A');assert.equal(record.mode,'retest');assert.equal(record.values.result,'fixed');assert.equal(instance.retests.length,0);
  }finally{q.close();}
});
test('Instance search is bounded and escapes author-controlled markup',()=>{
  const q=setup();try{
    const f=q.w.S.data.findings[0];f.instances=Array.from({length:65},(_,i)=>({uid:'instance-'+i,endpoint:i===4?'<img src=x onerror=alert(1)>':'/item/'+i,status:'open'}));q.get('#host').replaceChildren();q.w.instances.render(q.get('#host'),f);
    assert.equal(q.w.document.querySelectorAll('[data-instance-uid]').length,20);assert.equal(q.get('#host img'),null);const input=q.get('[data-instance-search]');input.value='/item/64';input.dispatchEvent(new q.w.Event('input'));assert.equal(q.w.document.querySelectorAll('[data-instance-uid]').length,1);assert.equal(q.get('[data-instance-uid]').dataset.instanceUid,'instance-64');
  }finally{q.close();}
});
