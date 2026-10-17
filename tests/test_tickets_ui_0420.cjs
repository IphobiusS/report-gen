/* Contextual index with production JavaScript and real Flask persistence.
 * JSDOM verifies state/events/DOM semantics; browser geometry and native keys
 * are covered separately by the focused browser acceptance harness. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom'),makeTransport=require('./flask_transport.cjs'),{isDeepStrictEqual}=require('node:util');
const root=path.resolve(__dirname,'..'),checks=[],worlds=[];
const check=(name,value)=>{assert.ok(value,name);checks.push(name);};
const plain=value=>JSON.parse(JSON.stringify(value));
const equal=(left,right)=>isDeepStrictEqual(plain(left),plain(right));
async function until(predicate){for(let i=0;i<800;i++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,25));}throw Error('UI timeout: '+predicate);}
async function world(storage={},bridge=makeTransport()){
  const html=fs.readFileSync(path.join(root,'webapp/static/index.html'),'utf8');
  const dom=new JSDOM(html,{url:'http://127.0.0.1/',runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window,doc=w.document,errors=[];let mobile=false,pending=0;
  const instance={dom,w,doc,bridge,errors,setMobile:value=>{mobile=value;}};worlds.push(instance);
  w.addEventListener('error',event=>errors.push(event.message));
  w.fetch=(...args)=>{pending++;return bridge.fetch(...args).finally(()=>pending--);};
  w.confirm=()=>true;w.alert=()=>{};w.structuredClone=structuredClone;
  w.AbortController=AbortController;w.AbortSignal=AbortSignal;
  w.CSS={escape:value=>Array.from(String(value),character=>'\\'+character.codePointAt(0).toString(16)+' ').join('')};
  w.matchMedia=()=>({get matches(){return mobile;},addEventListener(){},removeEventListener(){}});
  w.ResizeObserver=class{observe(){}disconnect(){}};w.HTMLElement.prototype.scrollIntoView=()=>{};
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;this.querySelector('button')?.focus();};
  w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
  w.HTMLAnchorElement.prototype.click=function(){};w.URL.createObjectURL=()=> 'blob:context-index-test';w.URL.revokeObjectURL=()=>{};
  w.localStorage.setItem('rg.previewVisible','0');
  for(const [key,value] of Object.entries(storage))w.localStorage.setItem(key,value);
  const sources=[...html.matchAll(/<script src="\/static\/([^"/]+)"/g)].map(match=>fs.readFileSync(path.join(root,'webapp/static',match[1]),'utf8'));
  w.eval(sources.join('\n')+'\nwindow.qa={S,projectStore,api,appFetch,requireOk,select,setUiLang,renderSidebar,renderMain,loadProject,refreshProjects,scheduleSave,doSave,ContextIndexUI,WorkbenchUI,WorkspaceUI,searchProject,navTo,BulkUI};');
  instance.q=w.qa;
  instance.settle=async()=>{await until(()=>pending===0);await new Promise(resolve=>w.requestAnimationFrame(resolve));await until(()=>pending===0);};
  instance.storage=()=>Object.fromEntries(Array.from({length:w.localStorage.length},(_,index)=>{const key=w.localStorage.key(index);return [key,w.localStorage.getItem(key)];}));
  await until(()=>doc.querySelector('.workspace-dashboard')&&!instance.q.projectStore.loading);
  return instance;
}
async function createProject(env,slug,title){
  await env.q.requireOk(await env.q.api.post('/api/projects',{slug,title}));
  await env.q.refreshProjects();await env.q.loadProject(slug);await env.settle();
  assert.equal(env.q.S.slug,slug);
}
async function backend(env){
  const response=await env.bridge.fetch('/api/projects/'+encodeURIComponent(env.q.S.slug));
  assert.equal(response.status,200);return {etag:response.headers.get('ETag'),data:await response.json()};
}
function frontend(q){return plain({data:q.S.data,etag:q.projectStore.etag,revision:q.projectStore.revision,dirty:q.projectStore.dirty});}


(async()=>{
 const env=await world(),{w,doc,q}=env;await createProject(env,'ticket-ui','Synthetic connector UI');
 q.S.data.findings=[{uid:w.crypto.randomUUID(),id:'F1',mode:'vuln',title:'Initial title',severity:'low',description_md:'Description',impact_md:'Impact',remediation_md:'Fix',status:'open',verification:'confirmed'}];q.S.data.finding_sequence=1;q.scheduleSave();assert.ok(await q.doSave());
 const response=await q.requireOk(await q.appFetch('/api/projects/ticket-ui/tickets',{method:'POST',headers:{'Content-Type':'application/json','If-Match':q.projectStore.etag},body:JSON.stringify({finding_uid:q.S.data.findings[0].uid,provider:'jira',base_url:'https://example.atlassian.net',external_id:'SEC-123'})}));await q.loadProject('ticket-ui');q.select('workflow','tickets');await until(()=>doc.querySelector('[data-ticket-field="token"]'));
 const originalFetch=w.fetch,requests=[];let reply=null;
 w.fetch=async(url,options)=>{if(/\/tickets\/[^/]+\/(push|pull)-(preview|apply)/.test(String(url))){requests.push({url:String(url),body:JSON.parse(options.body),etag:options.headers.get?options.headers.get('If-Match'):options.headers['If-Match']});return reply(String(url),options);}return originalFetch(url,options);};
 const responseOf=(data,etag=q.projectStore.etag)=>new Response(JSON.stringify(data),{status:200,headers:{'Content-Type':'application/json',ETag:etag,'X-Report-Gen-Workspace':q.S.workspace_id}});
 const find=selector=>doc.querySelector(selector),click=action=>find('[data-ticket-action="'+action+'"]').click();
 const set=(field,value)=>{const node=find('[data-ticket-field="'+field+'"]');node.value=value;node.dispatchEvent(new w.Event('input',{bubbles:true}));};
 const token='PRIVATE_EPHEMERAL_TEST_TOKEN';set('username','tester@example.test');set('token',token);
 reply=async()=>responseOf({payload:{fields:{summary:'Initial title'}},changes:[{field:'summary',before:'Remote existing title',after:'Initial title',available:true},{field:'description',before:null,after:{type:'doc',content:[]},available:false}],preview_token:'synthetic-token',remote_hash:'synthetic-hash'});
 click('push-preview');await until(()=>{if(find('[data-ticket-error]').textContent)throw Error(find('[data-ticket-error]').textContent);return find('[data-ticket-action="push-apply"]')&&!find('.tickets-form').disabled;});
 check('Reviewed outgoing changes show an explicit second action',!!find('[data-ticket-comparison] pre'));
 check('Outgoing comparison shows exact before/after and unavailable remote values explicitly',find('[data-ticket-outgoing-field="summary"]').textContent.includes('Remote existing title')&&find('[data-ticket-outgoing-field="summary"]').textContent.includes('Initial title')&&find('[data-ticket-outgoing-field="description"]').textContent.includes('La API no devolvió el valor actual')&&find('[data-ticket-outgoing-field="description"]').textContent.includes('\"type\": \"doc\"'));
 check('Credentials are never stored in the project or local preferences',!JSON.stringify(q.S.data).includes(token)&&!JSON.stringify(env.storage()).includes(token));
 set('token','CHANGED_TOKEN');check('Changing credentials invalidates the existing preview',!find('[data-ticket-action="push-apply"]'));
 click('push-preview');await until(()=>{if(find('[data-ticket-error]').textContent)throw Error(find('[data-ticket-error]').textContent);return find('[data-ticket-action="push-apply"]')&&!find('.tickets-form').disabled;});
 find('[data-ticket-choice="description_md"]').click();check('Changing the selected fields invalidates the existing preview',!find('[data-ticket-action="push-apply"]'));
 click('push-preview');await until(()=>{if(find('[data-ticket-error]').textContent)throw Error(find('[data-ticket-error]').textContent);return find('[data-ticket-action="push-apply"]')&&!find('.tickets-form').disabled;});
 const beforeApply=requests.length;q.S.data.findings[0].title='New unsaved title';q.scheduleSave();click('push-apply');await until(()=>!find('.tickets-form').disabled&&find('[data-ticket-error]').textContent);
 check('A stale preview cannot send or implicitly save a newer local draft',requests.length===beforeApply&&q.S.data.findings[0].title==='New unsaved title'&&q.projectStore.dirty);
 await q.doSave();q.select('workflow','tickets');await until(()=>doc.querySelector('[data-ticket-field="token"]')); set('token',token);
 let release;reply=()=>new Promise(resolve=>{release=resolve;});click('push-preview');await until(()=>!!release);
 check('An in-flight request disables the entire connector form',find('.tickets-form').disabled);
 q.S.data.findings[0].title='Concurrent local edit';q.scheduleSave();release(responseOf({payload:{fields:{summary:'Old title'}},preview_token:'old-token',remote_hash:'old-hash'}));await until(()=>!find('.tickets-form').disabled);
 check('A delayed preview cannot overwrite or validate a changed draft',q.S.data.findings[0].title==='Concurrent local edit'&&!find('[data-ticket-action="push-apply"]')&&!!find('[data-ticket-error]').textContent);
 await q.doSave();q.select('workflow','tickets');await until(()=>doc.querySelector('[data-ticket-field="token"]')); set('token',token);reply=async()=>responseOf({remote_state:{owner:'Server owner'},changes:[{field:'owner',before:'',after:'Server owner',conflict:false}],preview_token:'pull-token'});
 click('pull-preview');await until(()=>find('[data-ticket-action="pull-apply"]')&&!find('.tickets-form').disabled);check('Incoming assignments require explicit per-field selection',find('[data-ticket-action="pull-apply"]').disabled);
 find('[data-ticket-choice="accept:owner"]').click();check('Selecting a reviewed incoming change enables acceptance',!find('[data-ticket-action="pull-apply"]').disabled);
 const original=structuredClone(q.S.data);reply=()=>new Promise(resolve=>{release=resolve;});release=null;click('pull-apply');await until(()=>!!release);q.S.data.findings[0].impact_md='Preserve this concurrent draft';q.scheduleSave();const saved=structuredClone(original);saved.findings[0].owner='Server owner';release(responseOf({data:saved},'"synthetic-new-etag"'));await until(()=>!find('.tickets-form').disabled);
 check('An apply response never discards a concurrent local edit',q.S.data.findings[0].impact_md==='Preserve this concurrent draft'&&q.S.data.findings[0].owner!=='Server owner'&&q.projectStore.dirty);
 await q.doSave();q.select('workflow','tickets');await until(()=>doc.querySelector('[data-ticket-field="token"]')); set('token',token);release=null;reply=()=>new Promise(resolve=>{release=resolve;});click('push-preview');await until(()=>!!release);const oldWorkspace=q.S.workspace_id;q.S.workspace_id='different-workspace';release(responseOf({payload:{fields:{summary:'Old title'}},preview_token:'old-token',remote_hash:'old-hash'}));await until(()=>!find('.tickets-form').disabled);check('A response from a previous workspace cannot become an applicable preview',!find('[data-ticket-action="push-apply"]'));q.S.workspace_id=oldWorkspace;
 await env.settle();check('Guarded connector UI raises no DOM errors',env.errors.length===0);
 console.log(JSON.stringify({passed:checks.length,checks,scope:'Production connector UI, Flask project persistence, controlled remote protocol responses; no external service contacted'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{for(const env of worlds)env.dom.window.close();for(const bridge of new Set(worlds.map(env=>env.bridge)))bridge.close();});
