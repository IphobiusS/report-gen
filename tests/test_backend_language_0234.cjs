'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');

function fixture(fetch) {
  const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'));
  const source=fs.readFileSync(path.join(root,'webapp/static/app.js'),'utf8');
  const boundary=source.indexOf('// ---- CVSS 3.1');
  assert.ok(boundary>0,'Load the actual request helpers');
  const context=vm.createContext({fetch,document:{},Error});
  vm.runInContext('const S={uiLang:"es"}; const projectStore={etag:"rev-7"};\n'+source.slice(0,boundary),context);
  return {run:expression=>vm.runInContext(expression,context)};
}
const response=(ok=true,error)=>({ok,status:ok?200:403,json:async()=>error?{error}:{csrf:'local-token'}});

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
  const f=fixture(async()=>({ok:false,json:async()=>{throw Error('invalid JSON');}}));
  await assert.rejects(f.run('S.uiLang="en"; api.post("/api/projects",{})'),/Could not start the local session/);
  await assert.rejects(f.run('S.uiLang="es"; api.post("/api/projects",{})'),/No se pudo iniciar la sesión local/);
});
