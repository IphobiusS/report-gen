'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync(path.join(__dirname,'../webapp/static/http_evidence.js'),'utf8');
const flush=()=>new Promise(resolve=>setImmediate(resolve));
function deferred(){let resolve,reject;const promise=new Promise((yes,no)=>{resolve=yes;reject=no;});return{promise,resolve,reject};}
function setup(language){
  const dom=new JSDOM('<main id="host"></main>',{url:'http://127.0.0.1:8080',runScripts:'outside-only'}),w=dom.window,requests=[];
  w.uiText=(es,en,pt)=>({es,en,pt}[language]);w.projectBusyCount=0;
  const entry=index=>({uid:'http-'+index,title:'Evidence '+index,notes:'',original:{request:{url:'https://example.test/'+index},identity:'reader'}});
  w.S={slug:'original',workspace_id:'workspace',previewMode:'off',data:{findings:[],assets:[],http_evidence:[entry(1),entry(2),entry(3)]}};
  w.projectStore={revision:1,etag:'"saved"',dirty:false};
  w.h=(tag,attrs,...children)=>{const el=w.document.createElement(tag);for(const[key,value]of Object.entries(attrs||{})){if(value==null)continue;if(key.startsWith('on'))el.addEventListener(key.slice(2),value);else el.setAttribute(key,value);}for(const child of children.flat(Infinity))if(child!=null)el.append(child instanceof w.Node?child:w.document.createTextNode(String(child)));return el;};
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
  w.doSave=async()=>true;w.busyProject=value=>{w.projectBusyCount+=value?1:-1;};w.renderMain=()=>{};w.renderSidebar=()=>{};w.refreshLivePreview=()=>{};
  w.adoptSavedProject=async data=>{w.S.data=data;w.projectStore.revision++;};w.requireOk=async response=>response;
  w.appFetch=(url,options)=>{const task=deferred();requests.push({url,body:options?.body?JSON.parse(options.body):null,...task});return task.promise;};
  w.PendingUI={register:()=>{}};
  w.eval(source+'\nwindow.HTTP=HttpEvidenceUI;');w.HTTP.render(w.document.querySelector('#host'));
  function openHar(){[...w.document.querySelectorAll('button')].find(b=>/Import.*HAR/.test(b.textContent)).click();return w.document.querySelector('dialog');}
  function choose(dialog,text){const input=dialog.querySelector('input[type=file]');Object.defineProperty(input,'files',{value:[{size:128,text:()=>Promise.resolve(text)}],configurable:true});input.dispatchEvent(new w.Event('change'));}
  function respond(index,value){requests[index].resolve({headers:{get:()=> '"saved"'},json:async()=>value});}
  return{dom,w,requests,openHar,choose,respond};
}
for(const language of ['es','en','pt']){
  test(language+': changing HAR while previews are pending keeps only the newest file and selection',async()=>{
    const q=setup(language);try{
      const dialog=q.openHar();q.choose(dialog,'{"log":{"name":"first"}}');await flush();
      q.choose(dialog,'{"log":{"name":"second"}}');await flush();assert.equal(q.requests.length,2);
      q.respond(1,{entries:[{index:4,method:'GET',url:'https://second.example.test',status:200}]});await flush();
      q.respond(0,{entries:[{index:0,method:'GET',url:'https://first.example.test',status:200}]});await flush();
      assert.equal(dialog.querySelectorAll('.http-har-list input').length,1);assert.doesNotMatch(dialog.querySelector('.http-har-list').textContent,/first/);
      const selected=dialog.querySelector('.http-har-list input');selected.checked=true;selected.dispatchEvent(new q.w.Event('change'));
      dialog.querySelector('[data-http-har-import]').click();await flush();assert.equal(q.requests.length,3);
      assert.equal(q.requests[2].body.har.log.name,'second');assert.deepEqual(q.requests[2].body.indices,[4]);
      assert.equal(dialog.querySelector('input[type=file]').matches(':disabled'),true);
      assert.equal(dialog.querySelector('.http-har-list input').matches(':disabled'),true);
      const cancel=new q.w.Event('cancel',{cancelable:true});dialog.dispatchEvent(cancel);assert.equal(cancel.defaultPrevented,true);
      q.respond(2,{});await flush();assert.equal(q.w.document.querySelector('dialog'),null);assert.equal(q.w.projectBusyCount,0);
    }finally{q.dom.window.close();}
  });
  test(language+': a late failed HAR preview cannot clear a newer accepted file',async()=>{
    const q=setup(language);try{
      const dialog=q.openHar();q.choose(dialog,'{"log":{"name":"first"}}');await flush();q.choose(dialog,'{"log":{"name":"second"}}');await flush();
      q.respond(1,{entries:[{index:0,method:'GET',url:'https://second.example.test',status:200}]});await flush();q.requests[0].reject(Error('obsolete failure'));await flush();
      assert.equal(dialog.querySelector('[role=alert]').textContent,'');const selected=dialog.querySelector('.http-har-list input');selected.checked=true;selected.dispatchEvent(new q.w.Event('change'));
      dialog.querySelector('[data-http-har-import]').click();await flush();assert.equal(q.requests[2].body.har.log.name,'second');q.respond(2,{});await flush();
    }finally{q.dom.window.close();}
  });
  test(language+': a slow older HAR file read cannot replace the newer file or start another request',async()=>{
    const q=setup(language);try{
      const dialog=q.openHar(),input=dialog.querySelector('input[type=file]'),read=deferred();Object.defineProperty(input,'files',{value:[{size:128,text:()=>read.promise}],configurable:true});input.dispatchEvent(new q.w.Event('change'));
      q.choose(dialog,'{"log":{"name":"second"}}');await flush();q.respond(0,{entries:[{index:0,method:'GET',url:'https://second.example.test',status:200}]});await flush();
      read.resolve('{"log":{"name":"first"}}');await flush();assert.equal(q.requests.length,1);assert.match(dialog.querySelector('.http-har-list').textContent,/second/);
    }finally{q.dom.window.close();}
  });
  test(language+': a closed HAR picker does not start a preview after file reading finishes',async()=>{
    const q=setup(language);try{
      const dialog=q.openHar(),input=dialog.querySelector('input[type=file]'),read=deferred();Object.defineProperty(input,'files',{value:[{size:128,text:()=>read.promise}]});input.dispatchEvent(new q.w.Event('change'));dialog.close();read.resolve('{"log":{}}');await flush();assert.equal(q.requests.length,0);
    }finally{q.dom.window.close();}
  });
  test(language+': changing a HTTP comparison target invalidates pending and displayed results',async()=>{
    const q=setup(language);try{
      [...q.w.document.querySelectorAll('button')].find(b=>/Compar/.test(b.textContent)).click();const dialog=q.w.document.querySelector('dialog'),selectors=dialog.querySelectorAll('select'),run=[...dialog.querySelectorAll('button')].find(b=>/A → B/.test(b.textContent));
      run.click();await flush();selectors[1].value='http-3';selectors[1].dispatchEvent(new q.w.Event('change'));
      const result={request:{diff:'OLD TARGET',equal:false},response:{diff:'OLD TARGET',equal:false}};q.respond(0,result);await flush();assert.doesNotMatch(dialog.textContent,/OLD TARGET/);
      run.click();await flush();q.respond(1,{request:{diff:'CURRENT TARGET',equal:false},response:{diff:'CURRENT TARGET',equal:false}});await flush();assert.match(dialog.textContent,/CURRENT TARGET/);
      selectors[0].value='http-2';selectors[0].dispatchEvent(new q.w.Event('change'));assert.doesNotMatch(dialog.textContent,/CURRENT TARGET/);
    }finally{q.dom.window.close();}
  });
}
