'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const workspace='a'.repeat(64),otherWorkspace='b'.repeat(64);

function fixture(fetch) {
  const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'));
  const context=vm.createContext({fetch,Error,URL});
  for(const file of ['drafts.js','transport.js']) {
    vm.runInContext(fs.readFileSync(path.join(root,'webapp/static',file),'utf8'),context);
  }
  vm.runInContext(`
    const S={uiLang:'es'}, projectStore={etag:'rev-7'};
    BrowserWorkspace.bind(${JSON.stringify(workspace)});
    const transport=ReportTransport.create({fetch,workspace:BrowserWorkspace,
      getLanguage:()=>S.uiLang,getETag:()=>projectStore.etag,baseURL:()=>'http://localhost/'});
    const {request:appFetch,api}=transport;
  `,context);
  return {run:expression=>vm.runInContext(expression,context)};
}
const response=(ok=true,error)=>({ok,status:ok?200:403,headers:{get:()=>workspace},json:async()=>error?{error}:{csrf:'local-token'}});

test('read requests use UI language rather than report content',async()=>{
  const calls=[];const f=fixture(async(url,options)=>{calls.push({url,options});return response();});
  await f.run('S.uiLang="en"; S.data={meta:{report_lang:"es"}}; api.get("/api/projects")');
  assert.equal(calls.length,1);assert.equal(calls[0].options.headers['X-UI-Language'],'en');
});
test('an explicit Spanish UI request keeps the Spanish backend contract',async()=>{
  const calls=[];const f=fixture(async(url,options)=>{calls.push({url,options});return response();});
  await f.run('api.get("/api/projects")');
  assert.equal(calls[0].options.headers['X-UI-Language'],'es');
});
test('unknown persisted UI language falls back to Spanish',async()=>{
  const calls=[];const f=fixture(async(url,options)=>{calls.push({url,options});return response();});
  await f.run('S.uiLang="xx"; appFetch("/api/projects")');
  assert.equal(calls[0].options.headers['X-UI-Language'],'es');
});
test('mutation carries language, CSRF, JSON and If-Match without changing input headers',async()=>{
  const calls=[];const f=fixture(async(url,options)=>{calls.push({url,options});return response();});
  await f.run('S.uiLang="en"; const requestOptions={method:"PUT",headers:{"If-Match":"revision-11","Content-Type":"application/json"},body:"{}"}; appFetch("/api/projects/demo",requestOptions)');
  assert.equal(calls[0].url,'/api/session');assert.equal(calls[0].options.headers['X-UI-Language'],'en');
  assert.equal(calls[1].options.headers['X-CSRF-Token'],'local-token');
  assert.equal(calls[1].options.headers['If-Match'],'revision-11');
  assert.equal(calls[1].options.headers['Content-Type'],'application/json');
  assert.equal(calls[1].options.headers['X-UI-Language'],'en');
  assert.equal(f.run('Object.keys(requestOptions.headers).length'),2);
});
test('concurrent mutations share CSRF acquisition and preserve each captured language',async()=>{
  const calls=[];let release;const session=new Promise(resolve=>{release=resolve;});
  const f=fixture(async(url,options)=>{calls.push({url,options});return url==='/api/session'?session:response();});
  const english=f.run('S.uiLang="en"; api.post("/api/projects",{})');
  const spanish=f.run('S.uiLang="es"; api.del("/api/projects/demo")');
  assert.equal(calls.length,1);release(response());await Promise.all([english,spanish]);
  assert.equal(calls.length,3);
  assert.equal(calls.find(c=>c.url==='/api/projects').options.headers['X-UI-Language'],'en');
  const deletion=calls.find(c=>c.url==='/api/projects/demo');
  assert.equal(deletion.options.headers['X-UI-Language'],'es');assert.equal(deletion.options.headers['If-Match'],'rev-7');
});
test('localized session failures preserve the actual server diagnostic and allow retry',async()=>{
  let count=0;const f=fixture(async()=>++count===1?response(false,'Origin mismatch'):response());
  await assert.rejects(f.run('S.uiLang="en"; api.post("/api/projects",{})'),/Origin mismatch/);
  await f.run('api.post("/api/projects",{})');assert.equal(count,3);
});
test('an unreadable session failure uses a localized diagnostic',async()=>{
  const f=fixture(async()=>({...response(false),json:async()=>{throw Error('invalid JSON');}}));
  await assert.rejects(f.run('S.uiLang="en"; api.post("/api/projects",{})'),/Could not start the local session/);
  await assert.rejects(f.run('S.uiLang="es"; api.post("/api/projects",{})'),/No se pudo iniciar la sesión local/);
});

test('same-workspace conflict keeps its status and diagnostic without blocking retry',async()=>{
  const conflict={...response(false,'Synthetic stale ETag'),status:412};
  let count=0;const f=fixture(async()=>++count===1?conflict:response());
  const result=await f.run('appFetch("/api/projects/demo")');
  assert.equal(result.status,412);assert.equal((await result.json()).error,'Synthetic stale ETag');
  assert.equal(f.run('BrowserWorkspace.blocked()'),false);
  await f.run('appFetch("/api/projects/demo")');assert.equal(count,2);
});

test('HTTP errors without identity never expose their body and retain scope for retry',async()=>{
  for(const status of [412,503]){
    const calls=[];let bodyReads=0;
    const f=fixture(async(url,options)=>{calls.push({url,options});return calls.length===1?{ok:false,status,headers:{get:()=>null},json:async()=>{bodyReads++;return {error:'PRIVATE_B_ERROR'};}}:response();});
    await assert.rejects(f.run('S.uiLang="en"; appFetch("/api/projects/demo")'),error=>error.status===status&&error.message.includes('unverified')&&!error.message.includes('PRIVATE_B_ERROR'));
    assert.equal(bodyReads,0);assert.equal(f.run('BrowserWorkspace.blocked()'),false);
    await f.run('appFetch("/api/projects/demo")');
    assert.equal(calls.length,2);assert.ok(calls.every(call=>call.options.headers['X-Report-Gen-Workspace']===workspace));
  }
});

test('CSRF failure without identity retries its handshake with the original workspace',async()=>{
  const calls=[];let bodyReads=0;
  const f=fixture(async(url,options)=>{calls.push({url,options});return calls.length===1?{ok:false,status:503,headers:{get:()=>null},json:async()=>{bodyReads++;return {csrf:'foreign-token',workspace_id:otherWorkspace};}}:response();});
  await assert.rejects(f.run('api.post("/api/projects",{})'),error=>error.status===503);
  assert.equal(bodyReads,0);assert.equal(f.run('BrowserWorkspace.blocked()'),false);
  await f.run('api.post("/api/projects",{})');
  assert.deepEqual(calls.map(call=>call.url),['/api/session','/api/session','/api/projects']);
  assert.ok(calls.every(call=>call.options.headers['X-Report-Gen-Workspace']===workspace));
  assert.equal(calls[2].options.headers['X-CSRF-Token'],'local-token');
});

test('successful responses without identity and mismatched identities permanently block before body reads',async()=>{
  for(const [status,identity] of [[200,null],[204,null],[200,otherWorkspace],[409,otherWorkspace],[503,otherWorkspace],[503,'']]){
    let calls=0,bodyReads=0;
    const f=fixture(async()=>{calls++;return {ok:status<400,status,headers:{get:()=>identity},json:async()=>{bodyReads++;return {private:'FOREIGN_DATA'};}};});
    await assert.rejects(f.run('appFetch("/api/projects/demo")'),error=>error.status===409);
    assert.equal(f.run('BrowserWorkspace.blocked()'),true);assert.equal(bodyReads,0);
    await assert.rejects(f.run('appFetch("/api/projects/demo",{method:"PUT",body:"{}"})'),error=>error.status===409);
    assert.equal(calls,1);
  }
});

test('a foreign or unidentified successful CSRF response cannot send a mutation or adopt a token',async()=>{
  for(const identity of [null,otherWorkspace]){
    let calls=0,bodyReads=0;
    const f=fixture(async()=>{calls++;return {ok:true,status:200,headers:{get:()=>identity},json:async()=>{bodyReads++;return {csrf:'foreign-token',workspace_id:otherWorkspace};}};});
    await assert.rejects(f.run('api.post("/api/projects",{})'),error=>error.status===409);
    assert.equal(f.run('BrowserWorkspace.blocked()'),true);assert.equal(bodyReads,0);assert.equal(calls,1);
    assert.equal(f.run('BrowserWorkspace.current()'),workspace);
  }
});

test('a pending CSRF handshake cannot resume a mutation after another response blocks the workspace',async()=>{
  const calls=[];let release;
  const handshake=new Promise(resolve=>{release=resolve;});
  const f=fixture(async(url,options)=>{
    calls.push({url,options});
    return url==='/api/session'?handshake:{...response(),headers:{get:()=>otherWorkspace}};
  });
  const mutation=f.run('api.put("/api/projects/demo",{})');
  await assert.rejects(f.run('appFetch("/api/projects/changed")'),error=>error.status===409);
  release(response());
  await assert.rejects(mutation,error=>error.status===409);
  assert.deepEqual(calls.map(call=>call.url),['/api/session','/api/projects/changed']);
});

test('an older same-workspace response is discarded when another response already blocked the tab',async()=>{
  let release;
  const pending=new Promise(resolve=>{release=resolve;});
  const f=fixture(async url=>url.endsWith('/older')?pending:{...response(),headers:{get:()=>otherWorkspace}});
  const older=f.run('appFetch("/api/projects/older")');
  await assert.rejects(f.run('appFetch("/api/projects/changed")'),error=>error.status===409);
  release(response());
  await assert.rejects(older,error=>error.status===409);
});

test('resource URLs keep query and fragment while enforcing the bound workspace',()=>{
  const f=fixture(async()=>response());
  assert.equal(f.run('transport.scopedResourceURL("/api/projects/demo/img/evidence.png?raw=1&workspace_id=foreign#caption")'),
    '/api/projects/demo/img/evidence.png?raw=1&workspace_id='+workspace+'#caption');
  for(const url of ['/static/logo.png','#finding','https://example.invalid/api/image']){
    assert.equal(f.run('transport.scopedResourceURL('+JSON.stringify(url)+')'),url);
  }
});
