/* Production UI + Flask persistence + standalone HTML reviewer, without model networking. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {JSDOM}=require('jsdom'),transport=require('./flask_transport.cjs');
const root=path.resolve(__dirname,'..'),bridge=transport(),checks=[],errors=[],downloads=[];let dom,reviewerDom,pending=0;
const check=(name,value)=>{assert.ok(value,name);checks.push(name);};
async function until(predicate){for(let i=0;i<500;i++){if(predicate())return;await new Promise(r=>setTimeout(r,20));}throw Error('Timed out: '+predicate);}
function inputFor(document,text,selector='input,textarea,select'){const node=[...document.querySelectorAll('label')].find(n=>[...n.childNodes].filter(child=>child.nodeType===3).map(child=>child.textContent).join('').trim()===text);assert.ok(node,'label '+text);return node.querySelector(selector);}
(async()=>{
 const html=fs.readFileSync(path.join(root,'webapp/static/index.html'),'utf8');
 dom=new JSDOM(html,{url:'http://127.0.0.1/',runScripts:'outside-only',pretendToBeVisual:true});const w=dom.window,d=w.document;
 w.fetch=(...args)=>{pending++;return bridge.fetch(...args).then(async response=>{if(response.status>=400)console.error('HTTP failure',args[0],response.status,await response.clone().text());return response;}).finally(()=>pending--);};w.confirm=()=>true;w.alert=()=>{};w.structuredClone=structuredClone;w.AbortController=AbortController;w.AbortSignal=AbortSignal;w.Blob=Blob;
 w.CSS={escape:value=>Array.from(String(value),c=>'\\'+c.codePointAt(0).toString(16)+' ').join('')};w.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});w.ResizeObserver=class{observe(){}disconnect(){}};w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};w.HTMLAnchorElement.prototype.click=function(){};
 w.URL.createObjectURL=blob=>{downloads.push(blob);return 'blob:review-download';};w.URL.revokeObjectURL=()=>{};w.localStorage.setItem('rg.previewVisible','0');w.addEventListener('error',e=>errors.push(e.message));
 w.eval([...html.matchAll(/<script src="\/static\/([^"/]+)"/g)].map(m=>fs.readFileSync(path.join(root,'webapp/static',m[1]),'utf8')).join('\n')+'\nwindow.qa={S,projectStore,api,requireOk,select,setUiLang,refreshProjects,loadProject,scheduleSave,doSave,PendingUI,resetProjectCaches,busy:()=>projectBusyCount};');const q=w.qa;
 await until(()=>d.querySelector('.workspace-dashboard')&&!q.projectStore.loading);
 await q.requireOk(await q.api.post('/api/projects',{slug:'review-roundtrip',title:'Synthetic review'}));await q.refreshProjects();await q.loadProject('review-roundtrip');
 const uid=w.crypto.randomUUID();q.S.data.findings=[{uid,id:'F1',mode:'vuln',title:'Synthetic finding',severity:'info',cvss:0,description_md:'Original finding text',impact_md:'CONFIDENTIAL IMPACT',remediation_md:'Validate access',references:['https://example.test/reference'],closure_criteria_md:'Repeat the test across both roles'}];q.S.data.finding_sequence=1;q.scheduleSave();assert.ok(await q.doSave());
 q.select('workflow','review_exchange');await until(()=>d.querySelector('[data-review-exchange="profile-save"]'));
 check('Review page is reachable through production navigation',!!d.querySelector('[data-review-exchange="issue-preview"]'));
 inputFor(d,'F1 · Synthetic finding').click();
 // Share only description; selected fields are the privacy boundary.
 inputFor(d,'Impacto').click();inputFor(d,'Remediación').click();
 d.querySelector('[data-review-exchange="issue-preview"]').click();await until(()=>!pending&&d.querySelector('pre.insights-context'));
 check('Exact selected text is shown before issue',d.querySelector('pre.insights-context').textContent==='Original finding text');
 inputFor(d,'Revisé los textos seleccionados y su contenido privado. Autorizo incluirlos en el archivo y conservar una copia de origen en el proyecto.').click();
 d.querySelector('[data-review-exchange="issue"]').click();await until(()=>q.S.data.review_exchange?.packages.length===1&&d.querySelector('[data-review-exchange="profile-save"]')&&!pending);
 const offline=await downloads[0].text();check('Issued offline editor excludes unrelated impact',!offline.includes('CONFIDENTIAL IMPACT'));
 let returned;
 reviewerDom=new JSDOM(offline,{runScripts:'dangerously',url:'file:///review.html',beforeParse(window){window.Blob=Blob;window.alert=()=>{};window.URL.createObjectURL=blob=>{returned=blob;return 'blob:returned';};window.URL.revokeObjectURL=()=>{};window.HTMLAnchorElement.prototype.click=function(){};}});
 const rd=reviewerDom.window.document;rd.querySelector('input').value='Local reviewer';rd.querySelector('textarea').value='Reviewed exact text';rd.querySelectorAll('textarea')[1].value='Evidence wording clarified';rd.querySelector('button').click();
 const returnText=await returned.text(),returnValue=JSON.parse(returnText);check('Standalone reviewer creates only explicit field proposals',returnValue.changes.length===1&&returnValue.changes[0].field==='description_md');
 const upload=d.querySelector('input[aria-label="JSON devuelto por el revisor"]');Object.defineProperty(upload,'files',{configurable:true,value:[{size:Buffer.byteLength(returnText),text:async()=>returnText}]});upload.dispatchEvent(new w.Event('change'));await new Promise(r=>setTimeout(r,0));
 d.querySelector('[data-review-exchange="return-preview"]').click();await until(()=>!pending&&d.body.textContent.includes('Revisor declarado: Local reviewer'));
 const change=[...d.querySelectorAll('label')].find(el=>el.textContent==='F1 · Descripción');assert.ok(change);change.querySelector('input').click();inputFor(d,'Revisé las propuestas seleccionadas y los conflictos.').click();d.querySelector('[data-review-exchange="return-apply"]').click();
 await until(()=>q.S.data.findings[0].description_md==='Reviewed exact text'&&!pending);
 check('Explicit acceptance changes only reviewed field',q.S.data.findings[0].impact_md==='CONFIDENTIAL IMPACT'&&q.S.data.findings[0].references[0]==='https://example.test/reference');
 check('Declared review acceptance remains inspectable',q.S.data.review_exchange.accepted[0].reviewer==='Local reviewer'&&q.S.data.review_exchange.accepted[0].changes[0].note==='Evidence wording clarified');
 await until(()=>d.querySelector('[data-review-exchange="profile-save"]'));
 inputFor(d,'Nombre del perfil').value='Synthetic bank';inputFor(d,'Cliente').value='Synthetic customer';inputFor(d,'Criterios de aceptación: uno por línea').value='Evidence reviewed\nCustomer delivery approved';
 d.querySelector('[data-review-exchange="profile-save"]').click();await until(()=>!pending&&[...d.querySelectorAll('option')].some(n=>n.textContent==='Synthetic bank · v1'));
 const profile=inputFor(d,'Perfil y versión');profile.value=[...profile.options].find(n=>n.textContent==='Synthetic bank · v1').value;profile.dispatchEvent(new w.Event('change'));d.querySelector('[data-review-exchange="profile-preview"]').click();await until(()=>!pending&&d.body.textContent.includes('Vincular requisitos y preferencias de esta versión'));
 inputFor(d,'Vincular requisitos y preferencias de esta versión').click();d.querySelector('[data-review-exchange="profile-apply"]').click();await until(()=>q.S.data.client_profile?.name==='Synthetic bank'&&!pending);
 check('Explicit profile binding preserves client name when not selected',q.S.data.meta.client!== 'Synthetic customer'&&q.S.data.client_profile.acceptance_criteria.length===2);
 for(const [lang,phrase]of [['en','Request critique without changing report'],['pt','Solicitar crítica sem alterar o relatório'],['es','Solicitar crítica sin modificar el informe']]){q.setUiLang(lang);await until(()=>d.querySelector('[data-review-exchange="critique"]')?.textContent===phrase&&!pending);check(lang+' review interface translated',true);}
 inputFor(d,'Hallazgo a revisar').value=uid;inputFor(d,'Hallazgo a revisar').dispatchEvent(new w.Event('change'));d.querySelector('[data-review-exchange="precheck"]').click();await until(()=>!pending&&d.body.textContent.includes('No hay evidencia enlazada'));
 check('Local source checks are usable without installed Ollama',d.body.textContent.includes('No hay evidencia enlazada'));

 const changeValue=(label,value)=>{const input=inputFor(d,label);input.value=value;input.dispatchEvent(new w.Event('input',{bubbles:true}));return input;};
 const idle=()=>until(()=>!pending&&!q.busy());
 const review=async()=>{q.select('workflow','review_exchange');await until(()=>d.querySelector('[data-review-exchange="profile-save"]')&&!pending&&!q.busy());};
 changeValue('Nombre del perfil','Recoverable synthetic profile');changeValue('Terminología: una línea «término => preferido»','endpoint => operation');
 const projectBeforeDraft=JSON.stringify(q.S.data);
 q.select('report',-1);await review();
 check('Profile draft survives ordinary navigation without changing the project',inputFor(d,'Nombre del perfil').value==='Recoverable synthetic profile'&&JSON.stringify(q.S.data)===projectBeforeDraft);
 q.setUiLang('en');await until(()=>d.querySelector('[data-review-exchange="profile-save"]')?.textContent==='Save new profile version'&&!pending);check('Profile draft survives language changes',inputFor(d,'Profile name').value==='Recoverable synthetic profile');q.setUiLang('es');await until(()=>d.querySelector('[data-review-exchange="profile-save"]')?.textContent==='Guardar nueva versión del perfil'&&!pending);
 d.querySelector('[data-pending-discard="review-exchange:profile"]').click();await until(()=>d.querySelector('[data-review-exchange="profile-save"]')&&inputFor(d,'Nombre del perfil').value==='');
 check('Explicit profile form discard clears retained values',q.PendingUI.retained('review-exchange:profile','workspace').data.name==='');
 const nativeFetch=w.fetch;let delayedPath='',release=null;
 w.fetch=async(url,options)=>{const response=await nativeFetch(url,options);if(delayedPath&&String(url).endsWith(delayedPath)){delayedPath='';return new Promise(resolve=>{release=()=>resolve(response);});}return response;};
 const hold=path=>{delayedPath=path;release=null;};
 const selectProfile=()=>{const input=inputFor(d,'Perfil y versión');input.value=[...input.options].find(option=>option.textContent==='Synthetic bank · v1').value;input.dispatchEvent(new w.Event('change',{bubbles:true}));};
 selectProfile();hold('/client-profile/preview');d.querySelector('[data-review-exchange="profile-preview"]').click();await until(()=>release);
 changeValue('Nombre del perfil','Newer draft while preview pending');release();await idle();
 check('Delayed profile preview cannot validate a newer form revision',!d.body.textContent.includes('Vincular requisitos y preferencias de esta versión')&&inputFor(d,'Nombre del perfil').value==='Newer draft while preview pending');
 // A completed POST must preserve edits made after its submitted revision.
 hold('/api/client-profiles');d.querySelector('[data-review-exchange="profile-save"]').click();await until(()=>release);
 changeValue('Nombre del perfil','Keep this later profile edit');release();await idle();
 check('Profile save response retains a newer pending form revision',inputFor(d,'Nombre del perfil').value==='Keep this later profile edit'&&q.PendingUI.retained('review-exchange:profile','workspace').data.name==='Keep this later profile edit');
 // Selection and workspace changes are simulated while a real response is delayed.
 inputFor(d,'F1 · Synthetic finding').click();hold('/review-exchange/issue-preview');d.querySelector('[data-review-exchange="issue-preview"]').click();await until(()=>release);inputFor(d,'F1 · Synthetic finding').click();release();await idle();
 check('Late sharing preview is discarded after selection changes',!d.querySelector('pre.insights-context'));
 inputFor(d,'F1 · Synthetic finding').click();d.querySelector('[data-review-exchange="issue-preview"]').click();await until(()=>d.querySelector('pre.insights-context')&&!q.busy());inputFor(d,'Revisé los textos seleccionados y su contenido privado. Autorizo incluirlos en el archivo y conservar una copia de origen en el proyecto.').click();
 const downloadCount=downloads.length,packageCount=q.S.data.review_exchange.packages.length,previousWorkspace=q.S.workspace_id;
 hold('/review-exchange/issue');d.querySelector('[data-review-exchange="issue"]').click();await until(()=>release);q.S.workspace_id='changed-workspace-context';release();await idle();
 check('Late issue response cannot download or adopt into a different workspace',downloads.length===downloadCount&&q.S.data.review_exchange.packages.length===packageCount);
 q.S.workspace_id=previousWorkspace;await q.loadProject('review-roundtrip');await review();
 // Explicit project-reset hook must clear project caches while preserving workspace profiles.
 q.select('workflow','assessment_cases');await until(()=>d.querySelector('[data-assessment-action="new"]'));d.querySelector('[data-assessment-action="new"]').click();await until(()=>d.querySelector('[data-assessment-form]'));
 const assessment=d.querySelector('[data-assessment-form] [data-assessment-field="title"]');assessment.value='Pending project assessment';assessment.dispatchEvent(new w.Event('input',{bubbles:true}));
 const prefix='rg.wb.workspace.'+q.S.workspace_id+'.',own=prefix+'reviewQueue.'+q.S.slug,other=prefix+'reviewQueue.other-project',otherWorkspace='rg.wb.workspace.other-workspace.reviewQueue.'+q.S.slug;
 w.localStorage.setItem(own,'private-own');w.localStorage.setItem(other,'keep-other-project');w.localStorage.setItem(otherWorkspace,'keep-other-workspace');q.resetProjectCaches(q.S.slug);q.select('workflow','assessment_cases');await until(()=>d.querySelector('[data-assessment-action="new"]'));
 check('Explicit project reset clears assessment forms and only that project preferences',!d.querySelector('[data-assessment-form]')&&!w.localStorage.getItem(own)&&w.localStorage.getItem(other)==='keep-other-project'&&w.localStorage.getItem(otherWorkspace)==='keep-other-workspace');
 check('Project reset preserves independent workspace profile draft',q.PendingUI.retained('review-exchange:profile','workspace').data.name==='Keep this later profile edit');
 await idle();

 check('Production review flow raises no JavaScript errors',errors.length===0);
 console.log(JSON.stringify({passed:checks.length,checks,scope:'JSDOM events with actual Flask persistence; no native geometry or installed model claim'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{dom?.window.close();reviewerDom?.window.close();bridge.close();});
