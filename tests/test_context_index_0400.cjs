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
  w.eval(sources.join('\n')+'\nwindow.qa={S,projectStore,api,requireOk,select,setUiLang,renderSidebar,renderMain,loadProject,refreshProjects,scheduleSave,doSave,ContextIndexUI,WorkbenchUI,WorkspaceUI};');
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
function input(env,id,value,event='input'){
  const element=env.doc.getElementById(id);assert.ok(element,id);element.value=value;
  element.dispatchEvent(new env.w.Event(event,{bubbles:true}));return element;
}
const hidden=element=>!element||element.hidden||!!element.closest('[hidden]');
const findingRows=doc=>[...doc.querySelectorAll('#findingList li[data-finding-uid]')];
const findingUids=doc=>findingRows(doc).map(row=>row.dataset.findingUid);
const currentUid=doc=>doc.querySelector('#findingList [aria-current="page"]')?.closest('[data-finding-uid]')?.dataset.findingUid;
const resetFilters=q=>q.ContextIndexUI.setFilters({query:'',severity:'',kind:''});
const localLabels={es:{sections:'Secciones',findings:'Hallazgos'},en:{sections:'Sections',findings:'Findings'},pt:{sections:'Seções',findings:'Achados'}};
(async()=>{
  const env=await world(),{w,doc,q}=env,index=q.ContextIndexUI;
  check('An empty workspace has an unavailable context trigger and no exposed index',doc.querySelector('#contextIndexToggle').disabled&&hidden(doc.querySelector('#contextIndex')));
  check('The contextual index is outside global navigation',!doc.querySelector('#workspaceSidebar').contains(doc.querySelector('#contextIndex'))&&!doc.querySelector('#workspaceSidebar').contains(doc.querySelector('#sectionList'))&&!doc.querySelector('#workspaceSidebar').contains(doc.querySelector('#findingList')));
  check('Moving indices creates no duplicate IDs',new Set([...doc.querySelectorAll('[id]')].map(node=>node.id)).size===doc.querySelectorAll('[id]').length);
  await createProject(env,'context-regression','Contextual navigation regression');
  for(const [reportLanguage,interfaceLanguage,title] of [['es','pt','Declaración de confidencialidad'],['pt','en','Declaração de confidencialidade']]){
    q.S.data.meta.lang=reportLanguage;q.setUiLang(interfaceLanguage);q.select('section','confidentiality');index.open('sections');index.setSorting(true);
    const beforeDialog=frontend(q);doc.querySelector('[data-section-move="confidentiality"]').click();
    check(reportLanguage+' move dialog uses the report-language catalogue title independently of interface language',doc.querySelector('dialog[open] h2').textContent.startsWith(title+' · '));
    check(reportLanguage+' move dialog title matches the contextual row and editor heading',doc.querySelector('#sectionList [data-section-key="confidentiality"] .ftitle').textContent.endsWith(title)&&doc.querySelector('#editor h2').textContent===title);
    doc.querySelector('dialog[open]').close();
    check(reportLanguage+' inspecting the localized move dialog does not change source or revision',equal(frontend(q),beforeDialog));
  }
  q.S.data.report.sections=Array.from({length:23},(_,i)=>({key:'custom-context-'+String(i+1).padStart(2,'0'),title:i===22?'Conclusión São Paulo':'Sección de tesorería '+String(i+1).padStart(2,'0'),body:'Original technical section '+(i+1)+'\n\n`preserve-this-content`',enabled:true}));
  q.S.data.findings=Array.from({length:63},(_,i)=>({uid:w.crypto.randomUUID(),id:'F'+String(i+1).padStart(2,'0'),mode:i%9===0?'machine':'vuln',title:({0:'Gestión de créditos Águila',49:'Límite cincuenta',50:'Controle de crédito São Paulo',60:'Límite sesenta y uno',62:'Último hallazgo Zafiro'})[i]||'Registro de prueba '+(i+1),severity:i===61?'':['critical','high','medium','low','info'][i%5],verification:'confirmed',status:'open',owner:'Preserved owner '+i,description_md:'Technical narrative '+i+'\n\n`code_value_'+i+'`',retests:[{uid:w.crypto.randomUUID(),tested_on:'2026-10-01',assessor:'Synthetic auditor',result:'open',notes_md:'Preserve retest '+i}]}));
  q.S.data.finding_sequence=63;q.scheduleSave();check('The real API saves the 63-record fixture',await q.doSave());await env.settle();
  q.renderSidebar();q.renderMain();
  const initial=frontend(q),saved=await backend(env),uids=q.S.data.findings.map(row=>row.uid);
  check('Fixture persisted through Flask with 63 stable identities and 23 sections',saved.data.findings.length===63&&new Set(saved.data.findings.map(row=>row.uid)).size===63&&saved.data.report.sections.length===23);
  q.select('finding',0);resetFilters(q);index.open('findings');
  check('The index owns one bounded list scroll area',doc.querySelectorAll('#contextIndex .context-index-list-scroll').length===1);
  check('The first page renders the exact first 50 UIDs',equal(findingUids(doc),uids.slice(0,50)));
  check('Native pagination covers all records',doc.querySelector('[data-workspace-pagination="context"] select')?.options.length===2&&index.state().total===63&&index.state().matched===63);
  check('Normal reading mode has no section move controls',doc.querySelectorAll('#contextIndex [data-section-move]').length===0);
  for(const language of ['es','en','pt']){
    q.setUiLang(language);resetFilters(q);
    check(language+' localizes both context tabs',doc.querySelector('#contextSectionsTab').textContent.trim()===localLabels[language].sections&&doc.querySelector('#contextFindingsTab').textContent.trim()===localLabels[language].findings);
    for(const position of [49,50,60,62]){
      q.select('finding',position);
      check(language+' selects boundary '+(position+1)+' by exact stable UID',currentUid(doc)===uids[position]&&index.state().selected.uid===uids[position]&&index.state().page===Math.floor(position/50));
      check(language+' boundary '+(position+1)+' uses the correct bounded page',equal(findingUids(doc),uids.slice(position<50?0:50,position<50?50:100)));
    }
    input(env,'contextIndexSearch','  GESTION de CREDITOS AGUILA  ');
    check(language+' query matches accented title case-insensitively',equal(findingUids(doc),[uids[0]])&&index.state().matched===1);
    input(env,'contextIndexSearch','f51');
    check(language+' query matches finding ID',equal(findingUids(doc),[uids[50]]));
    input(env,'contextIndexSearch','sao paulo');
    check(language+' query normalizes Portuguese accents',equal(findingUids(doc),[uids[50]]));
    input(env,'contextIndexSearch','');
    input(env,'contextIndexSeverity','high','change');input(env,'contextIndexKind','vuln','change');
    const filtered=q.S.data.findings.filter(row=>row.severity==='high'&&row.mode==='vuln').map(row=>row.uid);
    check(language+' combines severity and kind without losing UID order',equal(findingUids(doc),filtered)&&index.state().matched===filtered.length&&index.state().total===63);
    input(env,'contextIndexSeverity','','change');input(env,'contextIndexKind','machine','change');
    check(language+' machine filtering retains all machine identities',equal(findingUids(doc),q.S.data.findings.filter(row=>row.mode==='machine').map(row=>row.uid)));
    input(env,'contextIndexSeverity','pending','change');input(env,'contextIndexKind','','change');
    check(language+' pending severity includes the unassessed finding',equal(findingUids(doc),[uids[61]]));
    input(env,'contextIndexSeverity','high','change');input(env,'contextIndexKind','vuln','change');
    const selection=plain(q.S.sel);input(env,'contextIndexSearch','no-results-0400');
    check(language+' an empty result is distinct from an empty source',findingRows(doc).length===0&&index.state().matched===0&&index.state().total===63&&!hidden(doc.querySelector('#contextIndexCount'))&&doc.querySelector('#contextIndexCount').textContent.includes('0'));
    check(language+' filters do not change the selected finding',equal(q.S.sel,selection)&&!hidden(doc.querySelector('#contextIndexSelectionStatus'))&&index.state().selected.visible===false);
    q.select('finding',50);
    check(language+' external navigation retains filters and explains excluded selection',index.state().query==='no-results-0400'&&index.state().severity==='high'&&index.state().kind==='vuln'&&index.state().selected.uid===uids[50]&&index.state().selected.visible===false&&!hidden(doc.querySelector('#contextIndexReveal')));
    doc.querySelector('#contextIndexReveal').click();
    check(language+' explicit reveal clears filters and displays the exact selected UID',index.state().query===''&&index.state().severity===''&&index.state().kind===''&&currentUid(doc)===uids[50]&&index.state().selected.visible===true);
    const beforeTab=plain(q.S.sel);doc.querySelector('#contextSectionsTab').click();
    check(language+' switching index tabs preserves the open finding',equal(q.S.sel,beforeTab));
    doc.querySelector('#contextIndexClose').click();doc.querySelector('#contextIndexToggle').focus();doc.querySelector('#contextIndexToggle').click();
    check(language+' reopening an opposite-mode index preserves the exact editor selection',equal(q.S.sel,beforeTab)&&index.state().mode==='sections'&&doc.querySelector('#editor [data-field="title"]').value===q.S.data.findings[beforeTab.idx].title);
    check(language+' section mode hides finding-only filters and actions',hidden(doc.querySelector('#contextIndexFilters'))&&hidden(doc.querySelector('#contextIndexFindingActions'))&&!hidden(doc.querySelector('#contextIndexSort')));
    check(language+' section mode exposes all 23 stable keys',index.state().mode==='sections'&&doc.querySelectorAll('#sectionList li').length===23&&doc.querySelector('#contextSectionsTab').getAttribute('aria-pressed')==='true');
    input(env,'contextIndexSearch','CONCLUSAO');
    // The authored title is Spanish, so title lookup uses its actual spelling.
    check(language+' searching absent authored prose does not silently translate content',index.state().matched===0);
    input(env,'contextIndexSearch','conclusion sao');
    check(language+' section title search is accent-insensitive',doc.querySelectorAll('#sectionList li').length===1&&doc.querySelector('#sectionList').textContent.includes('Conclusión São Paulo'));
    input(env,'contextIndexSearch','custom-context-02');
    check(language+' section key search is available',doc.querySelectorAll('#sectionList li').length===1&&doc.querySelector('#sectionList').textContent.includes('tesorería 02'));
    resetFilters(q);q.select('section','custom-context-23');
    check(language+' section navigation preserves stable selection key',q.S.sel.key==='custom-context-23'&&index.state().selected.key==='custom-context-23'&&doc.querySelector('#sectionList [aria-current="page"]'));
    const breadcrumb=doc.querySelector('#workspaceContext').textContent;
    input(env,'contextIndexSearch','not-the-selected-section');q.WorkspaceUI.update();
    check(language+' filtering an open section preserves its breadcrumb title',doc.querySelector('#workspaceContext').textContent===breadcrumb&&breadcrumb.includes('Conclusión São Paulo'));
    resetFilters(q);
    const order=q.S.data.report.sections.map(row=>row.key);doc.querySelector('#contextIndexSort').click();
    check(language+' explicit order mode exposes move controls only for sections',index.state().sorting&&doc.querySelector('#contextIndexSort').getAttribute('aria-pressed')==='true'&&doc.querySelectorAll('#contextIndex [data-section-move]').length===23);
    doc.querySelector('#contextIndexSort').click();
    check(language+' entering and leaving order mode leaves section order intact',!index.state().sorting&&equal(q.S.data.report.sections.map(row=>row.key),order)&&doc.querySelectorAll('#contextIndex [data-section-move]').length===0);
    input(env,'contextIndexWidth','420');
    check(language+' width uses an accessible bounded native range',doc.querySelector('#contextIndexWidth').type==='range'&&doc.querySelector('#contextIndexWidth').min==='220'&&doc.querySelector('#contextIndexWidth').max==='420'&&doc.querySelector('#contextIndexWidth').step==='20'&&index.state().width===420);
    doc.querySelector('#contextIndexClose').click();
    check(language+' folding hides all descendants semantically and updates trigger',hidden(doc.querySelector('#contextIndex'))&&doc.querySelector('#contextIndexToggle').getAttribute('aria-expanded')==='false');
    doc.querySelector('#contextIndexToggle').click();
    check(language+' trigger restores the context panel without editing',!hidden(doc.querySelector('#contextIndex'))&&doc.querySelector('#contextIndexToggle').getAttribute('aria-expanded')==='true');
    await env.settle();check(language+' all view operations preserve data, ETag, revision and clean state',equal(frontend(q),initial));
  }
  check('All navigation/filter/width/fold/order-mode operations leave persisted bytes and ETag unchanged',equal(await backend(env),saved));
  // Re-render an active control: typing and localization must not drop focus/caret.
  index.open('findings');resetFilters(q);
  const search=doc.querySelector('#contextIndexSearch');search.focus();input(env,'contextIndexSearch','registro');search.setSelectionRange(2,5);
  q.renderSidebar();
  check('Background rerender preserves the search focus and selection range',doc.activeElement.id==='contextIndexSearch'&&doc.activeElement.selectionStart===2&&doc.activeElement.selectionEnd===5);
  q.setUiLang('en');
  check('Interface translation preserves the focused context search',doc.activeElement.id==='contextIndexSearch'&&doc.activeElement.value==='registro');
  resetFilters(q);index.setPage(1);
  const pager=doc.querySelector('[data-workspace-pagination="context"] select');pager.value='0';pager.dispatchEvent(new w.Event('change',{bubbles:true}));await env.settle();
  check('Pagination rerender restores focus to its native page selector',doc.activeElement.matches('[data-workspace-pagination="context"] select')&&index.state().page===0);
  q.select('finding',0);index.open('findings');
  const nav=doc.querySelector('#findingList [aria-current="page"]');nav.focus();q.renderSidebar();
  check('Background rerender preserves the exact focused navigation identity',doc.activeElement.closest('[data-finding-uid]')?.dataset.findingUid===uids[0]);
  // A stale DOM listener must resolve its UID at click time, never a captured array index.
  const stale=doc.querySelector('#findingList [data-finding-uid="'+uids[0]+'"] .finding-nav');
  const first=q.S.data.findings.shift();q.S.data.findings.push(first);stale.click();
  check('A row click resolves stable UID after an intervening order change',q.S.sel.idx===62&&q.S.data.findings[q.S.sel.idx].uid===uids[0]);
  q.S.data.findings.unshift(q.S.data.findings.pop());q.select('finding',0);
  check('The stale-listener diagnostic restores the unmodified fixture',equal(frontend(q),initial));
  // Mobile events are real DOM events; layout/native focus containment is a browser gate.
  resetFilters(q);env.setMobile(true);index.open('findings');
  doc.querySelector('#sidebarToggle').click();
  check('Opening global mobile navigation closes the contextual panel',doc.querySelector('.layout').classList.contains('navigation-open')&&hidden(doc.querySelector('#contextIndex')));
  doc.querySelector('#contextIndexToggle').focus();doc.querySelector('#contextIndexToggle').click();
  check('Opening the mobile index closes global navigation',!hidden(doc.querySelector('#contextIndex'))&&!doc.querySelector('.layout').classList.contains('navigation-open')&&doc.querySelector('#sidebarToggle').getAttribute('aria-expanded')==='false');
  const mobileRow=doc.querySelector('#findingList .finding-nav');mobileRow.click();
  check('Mobile row navigation closes the panel and focuses the editor',hidden(doc.querySelector('#contextIndex'))&&doc.activeElement.id==='editor');
  doc.querySelector('#contextIndexToggle').focus();doc.querySelector('#contextIndexToggle').click();doc.querySelector('#contextIndexSearch').focus();
  doc.activeElement.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  check('Escape closes the mobile index and returns focus to its trigger',hidden(doc.querySelector('#contextIndex'))&&doc.activeElement.id==='contextIndexToggle');
  index.open('sections');index.setSorting(true);
  const move=doc.querySelector('[data-section-move="custom-context-01"]');move.focus();move.click();
  const dialog=doc.querySelector('dialog[open]');
  check('A section move opens the existing dialog with input focus',dialog?.contains(doc.activeElement)&&doc.activeElement.hasAttribute('data-section-position')&&!hidden(doc.querySelector('#contextIndex')));
  check('A custom section title is retained verbatim in the move dialog',dialog.querySelector('h2').textContent.startsWith('Sección de tesorería 01 · '));
  doc.activeElement.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
  check('Context Escape does not steal modal focus or close the parent panel',dialog.open&&dialog.contains(doc.activeElement)&&!hidden(doc.querySelector('#contextIndex')));
  dialog.close();
  check('Cancelling a move restores its logical opener and preserves report bytes',doc.activeElement.getAttribute('data-section-move')==='custom-context-01'&&equal(frontend(q),initial));
  env.setMobile(false);
  // Exercise a real persistence-changing operation and its existing Undo, not a mock.
  q.select('section','custom-context-01');index.open('sections');index.setSorting(true);
  doc.querySelector('[data-section-move="custom-context-01"]').focus();doc.activeElement.click();
  const beforeMove=await backend(env),beforeMoveRevision=q.projectStore.revision;
  const destination=doc.querySelector('[data-section-position]');destination.value='23';
  doc.querySelector('[data-section-move-apply]').click();
  check('Moving the selected section returns focus to its stable move control',doc.activeElement.getAttribute('data-section-move')==='custom-context-01');
  const expectedMove=plain(beforeMove.data);expectedMove.report.sections.push(expectedMove.report.sections.shift());
  check('Moving a section preserves its key selection and every technical field',q.S.sel.key==='custom-context-01'&&equal(q.S.data,expectedMove)&&q.projectStore.dirty&&q.projectStore.revision>beforeMoveRevision);
  check('A real section reorder saves successfully',await q.doSave());await env.settle();
  check('The backend contains only the intended section-order change',equal((await backend(env)).data,expectedMove));
  const undo=doc.querySelector('#undoNotice button');check('The actual Undo action is available after section movement',!!undo&&!undo.disabled);undo.click();
  check('Undo restores exact section order, identities and full report content',equal(q.S.data,beforeMove.data)&&q.projectStore.dirty);
  check('Undo saves successfully through the real API',await q.doSave());await env.settle();
  check('Persisted Undo restores the entire original report',equal((await backend(env)).data,saved.data));
  // Preference isolation uses real workspace IDs from two separate Flask stores.
  resetFilters(q);index.setSorting(false);index.open('findings');
  input(env,'contextIndexWidth','420');input(env,'contextIndexSearch','zafiro');
  input(env,'contextIndexSeverity','medium','change');input(env,'contextIndexKind','vuln','change');
  q.select('finding',62);doc.querySelector('#contextIndexClose').click();
  const preferenceKey='rg.wb.workspace.'+q.S.workspace_id+'.context-index.'+encodeURIComponent(q.S.slug);
  const stored=JSON.parse(w.localStorage.getItem(preferenceKey));
  check('Context preferences use the real workspace and project key',stored&&stored.width===420&&stored.findings.query==='zafiro'&&stored.open===false);
  check('Context preferences never write a legacy unscoped key',!Object.keys(env.storage()).some(key=>key.startsWith('rg.wb.context-index.')));
  index.setWidth(-100);check('Programmatic width is clamped to the minimum',index.state().width===220);
  index.setWidth(9999);check('Programmatic width is clamped to the maximum',index.state().width===420);
  index.setWidth(391);check('Programmatic width respects the native range step',index.state().width===400);
  index.setWidth('not-a-number');check('Invalid width falls back to a safe default',index.state().width===280);index.setWidth(420);
  const stateCopy=index.state();stateCopy.width=220;stateCopy.query='mutated caller copy';
  check('The public state snapshot cannot mutate preferences',index.state().width===420&&index.state().query==='zafiro');
  await createProject(env,'context-empty','Empty contextual navigation');
  const emptyOriginal=await backend(env);q.select('findings');index.open('findings');
  check('Another project receives independent default preferences',index.state().width===280&&index.state().query===''&&index.state().severity===''&&index.state().kind===''&&!index.state().sorting);
  check('An empty findings collection remains navigable with an explicit zero count',index.state().total===0&&index.state().matched===0&&findingRows(doc).length===0&&index.state().selected===null&&doc.querySelector('#contextIndexCount').textContent.includes('0'));
  input(env,'contextIndexSearch','absent');
  check('Searching an empty collection remains empty without inventing a selection',index.state().total===0&&index.state().matched===0&&index.state().selected===null);
  check('Empty-source navigation does not persist a report change',equal(await backend(env),emptyOriginal)&&!q.projectStore.dirty);
  q.S.data.report.sections=[];q.scheduleSave();check('A no-sections fixture saves through the real API',await q.doSave());
  resetFilters(q);index.open('sections');
  check('An empty section collection has no navigation or move controls',index.state().total===0&&index.state().matched===0&&doc.querySelectorAll('#sectionList li').length===0&&doc.querySelectorAll('#contextIndex [data-section-move]').length===0);
  await q.loadProject('context-regression');await env.settle();
  check('Returning to a project restores its own filters, width and folded preference',index.state().width===420&&index.state().query==='zafiro'&&index.state().severity==='medium'&&index.state().kind==='vuln'&&index.state().open===false&&!index.state().sorting);
  index.open('sections');index.setSorting(true);await q.loadProject('context-empty');await q.loadProject('context-regression');
  check('Order mode never resumes implicitly after a project switch',!index.state().sorting);
  q.select('findings');index.open('findings');resetFilters(q);
  input(env,'contextIndexWidth','420');input(env,'contextIndexSearch','zafiro');
  const copy=env.storage();copy['rg.wb.context-index.context-regression']=JSON.stringify({width:220,query:'legacy-leak',open:true});
  const otherBridge=makeTransport();
  const otherSession=await otherBridge.fetch('/api/session').then(response=>response.json());
  const created=await otherBridge.fetch('/api/projects',{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':otherSession.csrf},body:JSON.stringify({slug:'context-regression',title:'Same slug, different workspace'})});
  assert.equal(created.status,200);
  const other=await world(copy,otherBridge);other.q.select('findings');other.q.ContextIndexUI.open('findings');
  check('Same-named projects in distinct real workspaces do not inherit index preferences',other.q.S.workspace_id!==q.S.workspace_id&&other.q.S.slug===q.S.slug&&other.q.ContextIndexUI.state().width===280&&other.q.ContextIndexUI.state().query==='');
  check('Legacy context preferences remain untouched and are not adopted',other.w.localStorage.getItem('rg.wb.context-index.context-regression')===copy['rg.wb.context-index.context-regression']);
  check('Opening another workspace does not alter the original stored preference',other.w.localStorage.getItem(preferenceKey)===copy[preferenceKey]);
  const otherKey='rg.wb.workspace.'+other.q.S.workspace_id+'.context-index.'+encodeURIComponent(other.q.S.slug);
  other.w.localStorage.setItem(otherKey,JSON.stringify({width:999999,mode:'unexpected',open:true,sorting:true,findings:{query:{unsafe:'shape'},severity:'unexpected',kind:'unexpected',page:-99},sections:{query:[],page:Infinity}}));
  other.q.ContextIndexUI.projectChanged();other.q.ContextIndexUI.open('findings');
  const safe=other.q.ContextIndexUI.state();
  check('Malformed stored preferences are bounded and validated without enabling ordering',safe.width>=220&&safe.width<=420&&typeof safe.query==='string'&&safe.severity===''&&safe.kind===''&&safe.page===0&&!safe.sorting);
  other.w.localStorage.setItem(otherKey,'{invalid JSON');other.q.ContextIndexUI.projectChanged();other.q.ContextIndexUI.open('findings');
  check('Corrupt stored JSON falls back to usable defaults',other.q.ContextIndexUI.state().width===280&&other.q.ContextIndexUI.state().query==='');
  q.select('finding',0);resetFilters(q);index.open('findings');
  check('Finding mode hides section-only ordering from accessibility navigation',hidden(doc.querySelector('#contextIndexSort'))||doc.querySelector('#contextIndexSort').disabled);
  const ownBefore=frontend(q);q.select('home');
  check('Inactive routes hide the index while retaining its preferred open state',hidden(doc.querySelector('#contextIndex'))&&index.state().open&&!index.state().visible);
  await env.settle();check('Returning to overview preserves the final saved source',equal(frontend(q),ownBefore)&&equal((await backend(env)).data,saved.data));
  // Crossing a contextual page boundary must reveal the moved selected row and
  // its Undo without clearing the active query or changing record identities.
  await createProject(env,'context-reorder-pages','Contextual section page regression');
  q.S.data.report.sections=Array.from({length:61},(_,i)=>({key:'page-section-'+String(i+1).padStart(2,'0'),title:'Stable section '+String(i+1).padStart(2,'0'),body:'Preserved body '+i,enabled:true}));
  q.scheduleSave();check('The 61-section page-boundary fixture saves through the API',await q.doSave());await env.settle();
  q.select('section','page-section-01');index.open('sections');index.setFilters({query:'Stable'});index.setSorting(true);
  const pageBaseline=await backend(env),pageOrder=q.S.data.report.sections.map(section=>section.key);
  doc.querySelector('[data-section-move="page-section-01"]').focus();doc.activeElement.click();doc.querySelector('[data-section-position]').value='61';doc.querySelector('[data-section-move-apply]').click();
  const expectedPageMove=plain(pageBaseline.data);expectedPageMove.report.sections.push(expectedPageMove.report.sections.shift());
  check('Selected section movement across 50 rows opens its destination page without clearing the query',index.state().page===1&&index.state().query==='Stable'&&index.state().selected.key==='page-section-01'&&index.state().selected.visible);
  check('Page-crossing movement focuses the same section control in its new row',doc.activeElement.getAttribute('data-section-move')==='page-section-01'&&doc.activeElement.closest('li').querySelector('[aria-current="page"]'));
  check('Page-crossing movement changes only the intended section order',equal(q.S.data,expectedPageMove));
  check('Page-crossing movement persists successfully',await q.doSave());await env.settle();
  check('Persisted page-crossing movement retains all original section content',equal((await backend(env)).data,expectedPageMove));
  doc.querySelector('#undoNotice button').click();
  check('Undo returns the selected section to its original visible page without clearing the query',index.state().page===0&&index.state().query==='Stable'&&index.state().selected.key==='page-section-01'&&index.state().selected.visible&&doc.activeElement.id==='editor');
  check('Page-crossing Undo restores the exact original report',equal(q.S.data,pageBaseline.data)&&equal(q.S.data.report.sections.map(section=>section.key),pageOrder));
  check('Page-crossing Undo persists successfully',await q.doSave());await env.settle();
  q.select('section','page-section-20');index.setSorting(true);const scroll=doc.querySelector('#contextIndexListScroll');scroll.scrollTop=137;
  doc.querySelector('[data-section-move="page-section-01"]').focus();doc.activeElement.click();doc.querySelector('[data-section-position]').value='61';doc.querySelector('[data-section-move-apply]').click();
  check('Moving an unselected section preserves the editor selection, query, page and manual scroll',q.S.sel.key==='page-section-20'&&index.state().query==='Stable'&&index.state().page===0&&scroll.scrollTop===137);
  doc.querySelector('#undoNotice button').click();
  check('Undo of an unselected section preserves manual scroll and the selected editor',q.S.sel.key==='page-section-20'&&index.state().query==='Stable'&&index.state().page===0&&scroll.scrollTop===137&&equal(q.S.data,pageBaseline.data));
  check('Unselected movement and Undo persist the unchanged source',await q.doSave());await env.settle();
  check('The page-boundary regression ends with byte-equivalent report content',equal((await backend(env)).data,pageBaseline.data));
  for(const instance of worlds)await instance.settle();
  check('Both real workspace sessions complete without application DOM errors',worlds.every(instance=>instance.errors.length===0));
  console.log(JSON.stringify({status:'passed',passed:checks.length,checks,scope:'Production JavaScript, DOM events and real Flask persistence in two isolated workspaces; browser geometry, native key behavior and accessibility audit are separate gates'},null,2));
})().catch(error=>{console.error(JSON.stringify({status:'failed',passed:checks.length,checks,error:error.stack},null,2));process.exitCode=1;}).finally(async()=>{for(const env of worlds){
  if(env.q?.projectStore){env.q.projectStore.timers.clearTimeout(env.q.projectStore.timer);env.q.projectStore.timer=null;await env.q.projectStore.pending.catch(()=>{});}
  await env.settle?.();env.dom.window.close();env.bridge.close();
}});
