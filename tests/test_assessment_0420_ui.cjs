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
  w.eval(sources.join('\n')+'\nwindow.qa={S,projectStore,api,requireOk,select,setUiLang,renderSidebar,renderMain,loadProject,refreshProjects,scheduleSave,doSave,ContextIndexUI,WorkbenchUI,WorkspaceUI,searchProject,navTo,BulkUI,AssessmentUI,PendingUI,BrowserWorkspace,appFetch};');
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
 const env=await world(),{w,doc,q}=env;let duplicateAdapter=false;try{q.PendingUI.register('assessment:',{restore(){}});}catch{duplicateAdapter=true;}check('Recovery adapter is available before visiting the assessment workspace',duplicateAdapter);await createProject(env,'assessment-ui','Synthetic assessment');
 const find=selector=>doc.querySelector(selector),click=action=>find('[data-assessment-action="'+action+'"]').click();
 const set=(field,value)=>{const node=find('[data-assessment-form] [data-assessment-field="'+field+'"]');node.value=value;node.dispatchEvent(new w.Event(node.tagName==='SELECT'?'change':'input',{bubbles:true}));};
 for(const language of ['es','en','pt']){
   q.setUiLang(language);q.AssessmentUI.open('assessment_cases');await until(()=>find('[data-assessment-action="add-plan"]'));click('add-plan');const count=(['es','en','pt'].indexOf(language)+1)*2;await until(()=>q.S.data.test_cases?.length===count);
   check(language+' creates two pending versioned specialty cases',q.S.data.test_cases.slice(-2).every(row=>row.status==='pending'&&row.methodology_version==='1.0'));
 }
 q.setUiLang('es');q.AssessmentUI.open('assessment_cases');await until(()=>find('[data-assessment-action="new"]'));click('new');await until(()=>find('[data-assessment-form]'));set('title','Case requires explicit observation');set('status','passed');click('save');await until(()=>!find('[data-assessment-form]').hasAttribute('inert'));
 check('Missing observed result rejects save and retains authored form',find('[data-assessment-form] [data-assessment-field="title"]').value==='Case requires explicit observation'&&!q.S.data.test_cases.some(row=>row.title==='Case requires explicit observation'));
 set('observed','No failures observed for the agreed synthetic request');click('save');await until(()=>q.S.data.test_cases.some(row=>row.title==='Case requires explicit observation'));check('Explicit observed result commits with stable identity',!!q.S.data.test_cases.at(-1).uid);
 q.AssessmentUI.open('assessment_cases');await until(()=>find('[data-assessment-action="new"]'));click('new');await until(()=>find('[data-assessment-form]'));set('title','Scoped pending assessment');const currentWorkspace=q.S.workspace_id;q.S.workspace_id='another-view-workspace';q.AssessmentUI.open('assessment_cases');await until(()=>find('[data-assessment-view]'));await env.settle();check('Same-named project context does not display previous workspace form',!find('[data-assessment-form]'));q.S.workspace_id=currentWorkspace;q.AssessmentUI.open('assessment_cases');await until(()=>find('[data-assessment-form]'));check('Returning to original workspace restores its uncommitted form',find('[data-assessment-form] [data-assessment-field="title"]').value==='Scoped pending assessment');
 q.PendingUI.active.delete(q.S.slug+'|assessment:case:new');q.AssessmentUI.forgetPending(q.S.slug,'assessment:case:new');q.renderMain();await until(()=>find('[data-assessment-action="new"]'));click('new');await until(()=>find('[data-assessment-form]'));check('Privacy purge clears cached form as well as active pending input',find('[data-assessment-form] [data-assessment-field="title"]').value==='');
 set('title','Delayed response form');const originalFetch=w.fetch;let release=null,seen=false;
 w.fetch=async(url,options)=>{if(String(url).endsWith('/assessment/test-cases')&&options.method==='POST'){seen=true;return new Promise(resolve=>{release=resolve;});}return originalFetch(url,options);};
 const snapshot=plain(q.S.data);click('save');await until(()=>seen);check('Saving locks the form during a pending request',find('[data-assessment-form]').hasAttribute('inert'));
 q.S.data.meta.report_subtitle='Concurrent local draft';q.scheduleSave();const saved=plain(snapshot);saved.test_cases.push({uid:w.crypto.randomUUID(),title:'Delayed response form',status:'pending',specialty:'custom',asset_uids:[],finding_uids:[],evidence_uids:[],http_evidence_uids:[]});
 release(new Response(JSON.stringify({data:saved}),{status:200,headers:{'Content-Type':'application/json',ETag:'"new-response-tag"','X-Report-Gen-Workspace':q.S.workspace_id}}));await until(()=>!find('[data-assessment-form]').hasAttribute('inert'));
 check('Delayed save response cannot overwrite concurrent local edits',q.S.data.meta.report_subtitle==='Concurrent local draft'&&!q.S.data.test_cases.some(row=>row.title==='Delayed response form')&&find('[data-assessment-form] [data-assessment-field="title"]').value==='Delayed response form');
 w.fetch=originalFetch;await q.doSave();q.AssessmentUI.open('assessment_paths');await until(()=>find('[data-assessment-action="new"]'));click('new');await until(()=>find('[data-assessment-form]'));set('title','Synthetic causal route');click('add-stage');await env.settle();click('add-stage');await env.settle();let stages=doc.querySelectorAll('[data-assessment-stages] > section');for(let i=0;i<stages.length;i++){const node=stages[i].querySelector('[data-assessment-field="title"]');node.value='Stage '+i;node.dispatchEvent(new w.Event('input',{bubbles:true}));}click('add-edge');set('observation','Explicit unverified hypothesis');click('save');await until(()=>q.S.data.attack_paths?.length===1);check('Causal route persists declared inferred transition',q.S.data.attack_paths[0].edges[0].state==='inferred');
 q.AssessmentUI.open('assessment_cases');await until(()=>find('[data-assessment-action="new"]'));click('new');await until(()=>find('[data-assessment-form]'));set('title','Preserve late auxiliary revision');
 const beforeLate=q.S.data.test_cases.length;let releaseActual=null;w.fetch=async(url,options)=>{const response=await originalFetch(url,options);if(String(url).endsWith('/assessment/test-cases')&&options.method==='POST')return new Promise(resolve=>{releaseActual=()=>resolve(response);});return response;};
 click('save');await until(()=>releaseActual);set('observed','Late edit after the submitted snapshot');releaseActual();await until(()=>!find('[data-assessment-form]').hasAttribute('inert'));
 check('Later auxiliary revision survives accepted save and binds to the created identity',find('[data-assessment-form] [data-assessment-field="observed"]').value==='Late edit after the submitted snapshot'&&q.S.data.test_cases.length===beforeLate+1&&!q.S.data.test_cases.at(-1).observed);
 w.fetch=originalFetch;click('save');await until(()=>!find('[data-assessment-form]'));check('Retry saves late edits into the same case without a duplicate',q.S.data.test_cases.length===beforeLate+1&&q.S.data.test_cases.at(-1).observed==='Late edit after the submitted snapshot');
 check('No unexpected DOM exceptions',env.errors.length===0);
 console.log(JSON.stringify({passed:checks.length,checks,scope:'Production UI and Flask over pipes; no browser geometry or native IndexedDB claims.'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{for(const env of worlds)env.dom.window.close();for(const bridge of new Set(worlds.map(env=>env.bridge)))bridge.close();});
