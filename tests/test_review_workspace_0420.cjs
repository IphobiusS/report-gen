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
  w.eval(sources.join('\n')+'\nwindow.qa={S,projectStore,api,requireOk,select,setUiLang,renderSidebar,renderMain,loadProject,refreshProjects,scheduleSave,doSave,ContextIndexUI,WorkbenchUI,WorkspaceUI,searchProject,navTo,BulkUI};');
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
 const env=await world(),{w,doc,q}=env;
 await createProject(env,'review-queue','Synthetic review queue');
 q.S.data.assets=[{uid:w.crypto.randomUUID(),name:'Atlas API',target:'https://atlas.example.test/payments',kind:'API',notes:'Unique asset context'}];
 q.S.data.findings=Array.from({length:4},(_,i)=>({uid:w.crypto.randomUUID(),id:'F'+(i+1),mode:'vuln',title:'Synthetic finding '+i,severity:i%2?'high':'low',owner:i%2?'API team':'Platform',asset_uids:[q.S.data.assets[0].uid],description_md:'Description '+i,impact_md:'Unique impact '+i,remediation_md:'Fix '+i,verification:'confirmed',status:'open'}));
 q.S.data.finding_sequence=4;q.scheduleSave();assert.ok(await q.doSave());
 q.S.dashFilter='high';q.select('findings');
 const expected=[q.S.data.findings[1].uid,q.S.data.findings[3].uid],before=JSON.stringify(q.S.data);
 check('The high view contains only its two findings',equal([...doc.querySelectorAll('.dash-row')].map(row=>row.dataset.findingUid),expected));
 doc.querySelector('.finding-row-open').click();
 check('Opening a filtered row starts its stable queue',q.S.data.findings[q.S.sel.idx].uid===expected[0]&&doc.querySelector('[data-finding-position-label]').textContent.includes('1 de 2'));
 doc.querySelector('[data-finding-step="1"]').click();
 check('The contextual list shows the same queue in order',equal([...doc.querySelectorAll('#findingList li[data-finding-uid]')].map(row=>row.dataset.findingUid),expected));
 check('Next skips the intermediate finding excluded by the view',q.S.data.findings[q.S.sel.idx].uid===expected[1]);
 doc.querySelector('[data-finding-step="-1"]').click();
 q.S.data.findings[q.S.sel.idx].severity='low';q.scheduleSave();
 doc.querySelector('[data-finding-save-next]').click();await until(()=>q.S.data.findings[q.S.sel.idx]?.uid===expected[1]&&!q.projectStore.dirty);
 check('Save and next preserves membership after editing out of the original filter',doc.querySelector('[data-finding-position-label]').textContent.includes('2 de 2'));
 const key='rg.wb.workspace.'+q.S.workspace_id+'.reviewQueue.'+q.S.slug;
 check('Queue progress is persisted by workspace and project',JSON.parse(w.localStorage.getItem(key)).current_uid===expected[1]);
 check('UI navigation does not invent verification changes',q.S.data.findings.every(f=>f.status==='open'&&f.verification==='confirmed'));
 const current=JSON.stringify(q.S.data);
 for(const language of ['es','en','pt']){q.setUiLang(language);check(language+' translates the review controls',!!doc.querySelector('[data-finding-save-next]').textContent&&doc.querySelector('[data-finding-position-label]').textContent.includes('2'));}
 check('Language and queue rendering preserve report content',JSON.stringify(q.S.data)===current);
 q.select('findings');
 const resume=[...doc.querySelectorAll('[data-review-queue-controls] button')].find(button=>/Retomar/.test(button.textContent));check('A saved queue is offered even when the current filter now has one row',!!resume);resume.click();check('Resume returns to the same stable finding',q.S.data.findings[q.S.sel.idx].uid===expected[1]);
 const savedStorage=env.storage(),reload=await world(savedStorage,env.bridge);await reload.q.loadProject('review-queue');reload.q.WorkbenchUI.resumeQueue();
 check('A fresh page resumes the queue position and saved filter',reload.q.S.data.findings[reload.q.S.sel.idx].uid===expected[1]&&reload.q.S.dashFilter==='high');
 const oldWorkspace=q.S.workspace_id;q.S.workspace_id='separate-workspace';q.WorkbenchUI.projectChanged();q.select('findings');
 check('Same-named projects in another workspace do not see the saved queue',doc.querySelector('[data-review-queue-controls]').querySelectorAll('button').length===1);
 q.S.workspace_id=oldWorkspace;q.WorkbenchUI.projectChanged();q.S.dashFilter=null;q.select('findings');
 doc.querySelector('[data-board-select]').click();check('Checkbox selection does not open a finding',q.S.sel.type==='findings');
 doc.querySelector('[data-board-bulk]').click();
 check('Selected table rows seed the guarded bulk editor',doc.querySelectorAll('[data-bulk-finding]:checked').length===1&&doc.querySelectorAll('[data-bulk-field]:checked').length===0&&doc.querySelector('[data-bulk-apply]').disabled);
 doc.querySelector('[data-bulk-dialog]').close();
 doc.querySelector('[data-board-column="owner"]').click();
 check('Operational columns can be shown without changing project data',doc.querySelector('[data-board-column-cell="owner"]').hidden===false&&JSON.stringify(q.S.data)===current);
 const asset=q.searchProject('atlas.example.test')[0];check('Search returns a typed asset result',asset.nav.type==='asset');q.navTo(asset.nav);await until(()=>doc.activeElement.dataset.field==='target');
 check('Asset search focuses its exact target field',doc.activeElement.value==='https://atlas.example.test/payments');
 q.select('findings');const impact=q.searchProject('Unique impact 3')[0];q.navTo(impact.nav);await until(()=>doc.activeElement.dataset.field==='impact_md');
 check('Finding text search opens the exact Markdown field',q.S.data.findings[q.S.sel.idx].uid===expected[1]&&doc.activeElement.value==='Unique impact 3');
 // Test read-only entities without persisting artificial image or review metadata.
 const evidence={uid:w.crypto.randomUUID(),src:'images/synthetic.png',title:'<img src=x onerror=alert(1)>',caption:'Pinned unique evidence'};
 q.S.data.evidence=[evidence];q.S.data.findings[q.S.sel.idx].evidence_uids=[evidence.uid];q.renderMain();
 doc.querySelector('[data-inspector-toggle]').click();
 check('Pinned evidence and editable finding exist simultaneously',!!doc.querySelector('#pinnedEvidence img')&&!!doc.querySelector('#editor textarea[data-field="impact_md"]'));
 check('Evidence titles remain plain text and use the processed local image',!doc.querySelector('#pinnedEvidence [onerror]')&&new URL(doc.querySelector('#pinnedEvidence img').src).pathname.endsWith('/images/synthetic.png'));
 const pinData=JSON.stringify(q.S.data);q.WorkbenchUI.refreshInspector();q.setUiLang('en');
 check('Refreshing and translating the inspector do not mutate report content',JSON.stringify(q.S.data)===pinData&&doc.querySelectorAll('#pinnedEvidence').length===1);
 const comment={uid:w.crypto.randomUUID(),body:'Unique editorial comment',author:'Reviewer',field:'impact_md',finding_uid:expected[1],status:'open'};q.S.data.insights={comments:[comment]};
 const result=q.searchProject('Unique editorial comment')[0];q.navTo(result.nav);
 check('Comment search opens the selected comment rather than an unrelated page',result.nav.type==='comment'&&doc.querySelector('dialog[open]').textContent.includes(comment.body));doc.querySelector('dialog[open]').close();
 check('Evidence captions are searchable as typed references',q.searchProject('Pinned unique evidence')[0].nav.type==='evidence');
 q.ContextIndexUI.togglePreview();check('Showing the report preview closes the inspector and enables the preview',!doc.querySelector('#pinnedEvidence')&&q.S.previewVisible);
 q.select('report',-1);check('Leaving the finding removes the inspector',!doc.querySelector('#pinnedEvidence'));
 // Invalid and stale queue preferences never select arbitrary or deleted entities.
 w.localStorage.setItem(key,JSON.stringify({schema:1,uids:[expected[0],'deleted'],current_uid:'deleted',active:true}));q.WorkbenchUI.projectChanged();q.WorkbenchUI.resumeQueue();
 check('Stale queue entries are pruned and resume chooses a surviving finding',q.S.data.findings[q.S.sel.idx].uid===expected[0]);
 w.localStorage.setItem(key,'{"schema":1,"uids":{},"current_uid":null}');q.WorkbenchUI.projectChanged();q.select('findings');check('Malformed local preferences cannot crash or create a queue',doc.querySelector('[data-review-queue-controls]').querySelectorAll('button').length===1);
 await env.settle();await reload.settle();check('Review flows raise no DOM errors',worlds.every(instance=>!instance.errors.length));
 console.log(JSON.stringify({passed:checks.length,checks,scope:'Production UI and Flask bridge; geometry covered by browser acceptance'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{for(const env of worlds)env.dom.window.close();for(const bridge of new Set(worlds.map(env=>env.bridge)))bridge.close();});
