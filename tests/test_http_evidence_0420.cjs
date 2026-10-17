/* DOM behavior independent of Chromium: publication consent and stale context. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{JSDOM}=require('jsdom');
const source=fs.readFileSync(path.join(__dirname,'../webapp/static/http_evidence.js'),'utf8');
const uid='11111111-1111-4111-8111-111111111111',finding='22222222-2222-4222-8222-222222222222';
function setup(lang='es'){
 const dom=new JSDOM('<!doctype html><body><main id="host"></main></body>',{url:'http://127.0.0.1:8080',runScripts:'outside-only'}),w=dom.window;
 w.uiText=(es,en,pt)=>({es,en,pt}[lang]);w.projectBusyCount=0;w.requests=[];
 w.S={slug:'case',workspace_id:'workspace',previewMode:'off',data:{findings:[{uid:finding,title:'Finding'}],assets:[],http_evidence:[{uid,title:'<img src=x onerror=alert(1)>',notes:'private',created:'date',sha256:'a'.repeat(64),finding_uids:[finding],asset_uids:[],publication:null,original:{request:{method:'GET',url:'https://target.invalid/?secret=PRIVATE',http_version:'HTTP/1.1',headers:[{name:'Authorization',value:'PRIVATE'}],body:'',body_encoding:'utf-8'},response:{status:200,http_version:'HTTP/1.1',headers:[],body:'PRIVATE',body_encoding:'utf-8'},identity:'reader',captured_at:'date',source:'manual'}}]}};
 w.projectStore={revision:1,etag:'"a"',dirty:false};
 w.h=(tag,attrs,...children)=>{const el=w.document.createElement(tag);for(const[key,value]of Object.entries(attrs||{})){if(value==null)continue;if(key.startsWith('on'))el.addEventListener(key.slice(2),value);else el.setAttribute(key,value);}for(const child of children.flat(Infinity))if(child!=null)el.append(child instanceof w.Node?child:w.document.createTextNode(String(child)));return el;};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
 w.doSave=async()=>true;w.busyProject=v=>{w.projectBusyCount+=v?1:-1;};w.renderMain=()=>{};w.renderSidebar=()=>{};w.refreshLivePreview=()=>{};
 w.adoptSavedProject=async data=>{w.S.data=data;w.projectStore.revision++;};w.requireOk=async x=>x;
 w.appFetch=async(url,options)=>{const body=JSON.parse(options.body);w.requests.push({url,body});const data=JSON.parse(JSON.stringify(w.S.data));if(url.endsWith('/edit'))Object.assign(data.http_evidence[0],body);return{headers:{get:()=> '"b"'},json:async()=>({data})};};
 w.PendingUI={retained:()=>null,register:()=>{},attach:(key,label,read)=>({handle:{revision:1},setBusy:()=>{},committed:async()=>({finished:true}),read})};
 w.eval(source+'\nwindow.HTTP=HttpEvidenceUI;');return {dom,w};
}
const flush=()=>new Promise(resolve=>setImmediate(resolve));
(async()=>{
 for(const lang of ['es','en','pt']){
  const {dom,w}=setup(lang);w.HTTP.render(w.document.querySelector('#host'));assert.equal(w.document.querySelectorAll('img').length,0);
  const hook=w.ReportGenReviewHooks.inspectorItems(w.S.data.findings[0])[0],proof=w.document.createElement('div');hook.render(proof);assert.ok(proof.textContent.includes('PRIVATE'));assert.equal(proof.querySelectorAll('img,a').length,0);
  w.HTTP.open(uid);let dialog=w.document.querySelector('dialog'),publish=dialog.querySelector('[data-http-publish]');publish.checked=true;publish.dispatchEvent(new w.Event('change'));
  const copy=[...dialog.querySelectorAll('button')].find(b=>/Copiar original|Copy original/.test(b.textContent));copy.click();assert.ok(dialog.querySelector('[data-http-publication=request]').value.includes('PRIVATE'));
  const request=dialog.querySelector('[data-http-publication=request]'),response=dialog.querySelector('[data-http-publication=response]'),caption=dialog.querySelector('[data-http-publication=caption]'),ack=dialog.querySelector('[data-http-reviewed]');
  request.value='GET /safe HTTP/1.1';response.value='HTTP/1.1 200';caption.value='Reviewed';ack.checked=true;caption.dispatchEvent(new w.Event('input',{bubbles:true}));assert.equal(ack.checked,false);
  dialog.querySelector('[data-http-save]').click();await flush();assert.equal(w.requests.length,0);assert.ok(dialog.querySelector('[role=alert]').textContent);
  ack.checked=true;dialog.querySelector('[data-http-save]').click();await flush();await flush();assert.equal(w.requests.length,1);assert.equal(w.requests[0].body.publication.request_text,'GET /safe HTTP/1.1');assert.equal(w.requests[0].body.ack_reviewed,true);assert.ok(!('original'in w.requests[0].body));assert.equal(w.document.querySelector('dialog'),null);
  assert.ok(w.S.data.http_evidence[0].original.request.url.includes('PRIVATE'));
  w.HTTP.open(uid);dialog=w.document.querySelector('dialog');w.S.data.http_evidence[0]={...w.S.data.http_evidence[0],notes:'updated by other editor'};dialog.querySelector('[data-http-reviewed]').checked=true;dialog.querySelector('[data-http-save]').click();await flush();assert.equal(w.requests.length,1);assert.ok(dialog.querySelector('[role=alert]').textContent);dialog.close();
  w.HTTP.open();dialog=w.document.querySelector('dialog');dialog.querySelector('[data-http-message-field="request.headers"]').value='malformed header';dialog.querySelector('[data-http-save]').click();await flush();assert.equal(w.requests.length,1);assert.ok(dialog.querySelector('[role=alert]').textContent);dialog.close();
  w.HTTP.open(uid);dialog=w.document.querySelector('dialog');w.S.slug='different';dialog.querySelector('[data-http-reviewed]').checked=true;dialog.querySelector('[data-http-save]').click();await flush();assert.equal(w.requests.length,1);assert.ok(dialog.querySelector('[role=alert]').textContent);
  assert.equal(w.projectBusyCount,0);dom.window.close();console.log('PASS '+lang+' literal evidence, consent reset, exact copy, stale row/project, malformed manual headers');
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
