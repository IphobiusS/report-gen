/* Production inspector/pending integration. Rendering and real storage have separate browser gates. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),test=require('node:test');
const {JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..');
function world(lang='es'){
 const dom=new JSDOM('<main id="editor" tabindex="-1"></main>',{runScripts:'outside-only',pretendToBeVisual:true,url:'http://127.0.0.1/'}),w=dom.window,records=new Map(),errors=[];
 let serial=0;
 w.S={slug:'fictional',data:{findings:[],publication:{redactions:[],exceptions:[]}},uiLang:lang};
 w.projectStore={etag:'revision-1',revision:1,dirty:false,loading:false};
 w.BrowserWorkspace={current:()=> 'workspace-test'};
 w.uiText=(es,en,pt)=>({es,en,pt})[w.S.uiLang];w.toast=message=>errors.push(message);w.confirm=()=>true;
 w.$=selector=>w.document.querySelector(selector);
 w.h=(tag,attrs={},...children)=>{const el=w.document.createElement(tag);for(const [key,value]of Object.entries(attrs)){if(['value','checked','disabled','tabindex'].includes(key))el[key]=value;else el.setAttribute(key,value);}el.append(...children.flat().filter(x=>x!=null).map(x=>typeof x==='object'?x:String(x)));return el;};
 w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
 w.PendingJournal=class{async put(input){if(w.failStorage)throw Error('Synthetic quota failure');const row={...input,id:input.slug+'|'+input.key,token:String(++serial),format:'report-gen-pending',version:1,updated:Date.now(),workspace_id:'workspace-test'};records.set(row.id,row);return row;}async list(slug){return [...records.values()].filter(row=>row.slug===slug);}async removeUnchanged(row){if(records.get(row.id)?.token!==row.token)return false;records.delete(row.id);return true;}};
 w.inspection={revision:'revision-1',images:[],private_captures:0,alerts:[{id:'alert-1',kind:'password',preview:'SYNTHETIC_TOKEN',reason:''}],text:'Fictional outgoing text'};
 w.api={get:async()=>{if(w.heldRead)await w.heldRead;return w.inspection;}};
 w.saveCalls=0;w.doSave=async()=>{w.saveCalls++;if(w.failSave)return false;w.projectStore.dirty=false;return true;};
 w.scheduleSave=()=>{w.projectStore.dirty=true;};w.PrivacyUI={ocr:()=>w.h('span')};w.select=()=>{};
 w.eval(fs.readFileSync(path.join(root,'webapp/static/pending-work.js'),'utf8')+'\n'+fs.readFileSync(path.join(root,'webapp/static/studio.js'),'utf8')+'\nwindow.qa={PendingUI,StudioUI};');
 const q=w.qa,doc=w.document;
 const input=(selector,value)=>{const element=doc.querySelector(selector);assert.ok(element,selector);element.value=value;element.dispatchEvent(new w.Event('input',{bubbles:true}));return element;};
 const settle=async()=>{for(let i=0;i<8;i++){await Promise.resolve();await new Promise(resolve=>setImmediate(resolve));}};
 const click=label=>{const button=[...doc.querySelectorAll('dialog[open] button')].find(el=>el.textContent===label);assert.ok(button,label);button.click();return button;};
 const record=key=>[...records.values()].find(row=>row.key===key);
 const recover=async row=>{q.PendingUI.reset(w.S.slug);const d=doc.createElement('dialog');doc.body.append(d);d.showModal();d.append(q.PendingUI.recoverySection(row));click(({es:'Recuperar formulario',en:'Recover form',pt:'Recuperar formulário'})[w.S.uiLang]);await settle();return d;};
 return{dom,w,q,doc,errors,records,input,settle,click,record,recover};
}
for(const lang of ['es','en','pt'])test(lang+': reasons and redactions recover only input; explicit save consumes its copy',async()=>{
 const e=world(lang),{w,q,doc}=e;try{
  await q.StudioUI.inspector();const before=JSON.stringify(w.S.data.publication);
  e.input('[data-publication-reason]','Private synthetic rationale');e.input('[data-publication-needle]','SYNTHETIC_TOKEN');e.input('[data-publication-replacement]','[FICTIONAL]');await e.settle();
  const reason=e.record('studio:publication:exception:alert-1'),redaction=e.record('studio:publication:redaction');
  assert.equal(reason.data.reason,'Private synthetic rationale');assert.equal(redaction.data.replacement,'[FICTIONAL]');
  assert.deepEqual(Object.keys(reason.data).sort(),['alert_id','kind','reason']);assert.deepEqual(Object.keys(redaction.data).sort(),['kind','needle','replacement']);assert.equal(JSON.stringify(w.S.data.publication),before);
  doc.querySelector('dialog[open]').close();await q.StudioUI.inspector();assert.equal(doc.querySelector('[data-publication-reason]').value,'Private synthetic rationale');assert.equal(doc.querySelector('[data-publication-needle]').value,'SYNTHETIC_TOKEN');
  doc.querySelector('dialog[open]').close();const saves=w.saveCalls;await e.recover({...reason,id:'old-reason-copy'}); // Missing original storage is checked before restore.
  assert.equal(w.saveCalls,saves);assert.equal(JSON.stringify(w.S.data.publication),before);
  doc.querySelector('dialog[open]').close();await e.recover(reason);
  assert.equal(doc.querySelector('[data-publication-reason]').value,'Private synthetic rationale');assert.equal(JSON.stringify(w.S.data.publication),before);assert.equal(w.saveCalls,saves);
  e.click(({es:'Registrar excepción',en:'Record exception',pt:'Registrar exceção'})[lang]);await e.settle();
  assert.equal(w.S.data.publication.exceptions[0].reason,'Private synthetic rationale');assert.equal(e.record(reason.key),undefined);assert.ok(e.record(redaction.key));
  doc.querySelector('dialog[open]').close();await e.recover(redaction);
  assert.equal(doc.querySelector('[data-publication-needle]').value,'SYNTHETIC_TOKEN');assert.equal(w.S.data.publication.redactions.length,0);
  e.click(({es:'Aplicar y volver a inspeccionar',en:'Apply and inspect again',pt:'Aplicar e inspecionar novamente'})[lang]);await e.settle();
  assert.equal(w.S.data.publication.redactions[0].replacement,'[FICTIONAL]');assert.equal(e.record(redaction.key),undefined);
 }finally{e.dom.window.close();}
});
test('An alert removed from the current revision keeps its draft visible and never records an exception',async()=>{
 const e=world();try{await e.q.StudioUI.inspector();e.input('[data-publication-reason]','Retain this reason');await e.settle();const row=e.record('studio:publication:exception:alert-1');e.doc.querySelector('dialog[open]').close();e.w.inspection.alerts=[];
  const recovery=await e.recover(row);assert.ok(recovery.open);assert.match(recovery.textContent,/Retain this reason/);assert.ok(e.errors.some(text=>text.includes('alerta ya no existe')));assert.equal(e.w.S.data.publication.exceptions.length,0);assert.ok(e.record(row.key));
 }finally{e.dom.window.close();}
});
test('A failed save retains pending content and a quota failure reports tab-only storage',async()=>{
 const e=world();try{await e.q.StudioUI.inspector();e.input('[data-publication-needle]','SYNTHETIC_TOKEN');await e.settle();e.w.failSave=true;e.click('Aplicar y volver a inspeccionar');await e.settle();assert.ok(e.record('studio:publication:redaction'));assert.equal(e.doc.querySelector('[data-publication-needle]').value,'SYNTHETIC_TOKEN');
  e.w.failStorage=true;e.input('[data-publication-reason]','Only in tab');await e.settle();assert.match(e.doc.querySelector('[data-pending-status="studio:publication:exception:alert-1"]').textContent,/Solo en esta pestaña/);assert.equal(e.doc.querySelector('[data-publication-reason]').value,'Only in tab');
 }finally{e.dom.window.close();}
});
test('Changing projects while recovering cannot display or apply the previous project reason',async()=>{
 const e=world();try{await e.q.StudioUI.inspector();e.input('[data-publication-reason]','Project A reason');await e.settle();const row=e.record('studio:publication:exception:alert-1');e.doc.querySelector('dialog[open]').close();
  let release;e.w.heldRead=new Promise(resolve=>release=resolve);const recovering=e.recover(row);await e.settle();e.w.S.slug='project-b';e.w.S.data={findings:[],publication:{exceptions:[],redactions:[]}};release();await recovering;
  assert.equal(e.doc.querySelector('[data-publication-reason]'),null);assert.equal(e.w.S.data.publication.exceptions.length,0);assert.ok(e.record(row.key));
 }finally{e.dom.window.close();}
});

test('Reopening an untouched inspector uses the current saved reason instead of an old empty form',async()=>{
 const e=world();try{await e.q.StudioUI.inspector();e.doc.querySelector('dialog[open]').close();e.w.inspection.alerts[0].reason='Reason updated in the current revision';await e.q.StudioUI.inspector();assert.equal(e.doc.querySelector('[data-publication-reason]').value,'Reason updated in the current revision');assert.equal(e.records.size,0);
 }finally{e.dom.window.close();}
});
