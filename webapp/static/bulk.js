/* Explicit assignments with a saved-revision comparison and one atomic save. */
const BulkUI=(()=>{
  'use strict';
  const w=(es,en)=>S.uiLang==='en'?en:es;
  const labels={owner:['Responsable','Owner'],due_date:['Fecha de corrección','Remediation date'],root_cause_uid:['Grupo de causa raíz','Root cause group']};
  function open(){
    if(!S.slug||projectBusyCount||projectStore.loading)return;
    const slug=S.slug,workspace=S.workspace_id,trigger=document.activeElement,selected=new Set();
    let preview=null,requestBusy=false,edited=false,page=0;
    const dialog=h('dialog',{class:'experience-dialog workbench-dialog','aria-label':w('Editar hallazgos por lotes','Bulk edit findings'),'data-bulk-dialog':''});
    const body=h('div',{class:'experience-body'}),form=h('fieldset',{}),list=h('div',{'data-bulk-findings':''}),review=h('div',{'data-bulk-review':''}),error=h('p',{role:'alert'}),count=h('p',{role:'status'});
    const close=h('button',{type:'button',class:'btn',onclick:()=>requestClose()},w('Cerrar','Close'));
    const protectUnload=event=>{if(edited||requestBusy){event.preventDefault();event.returnValue='';}};
    window.addEventListener('beforeunload',protectUnload);
    function requestClose(){if(requestBusy)return;if(edited&&!confirm(w('¿Cerrar y descartar esta selección y propuesta sin guardar?','Close and discard this unsaved selection and proposal?')))return;dialog.close();}
    dialog.addEventListener('cancel',event=>{event.preventDefault();requestClose();});
    dialog.addEventListener('close',()=>{window.removeEventListener('beforeunload',protectUnload);dialog.remove();(trigger?.isConnected&&!trigger.disabled?trigger:document.querySelector('[data-bulk-open]')||$('#editor'))?.focus({preventScroll:true});});
    const search=h('input',{type:'search','aria-label':w('Buscar hallazgos para seleccionar','Find findings to select'),oninput:()=>{page=0;draw();}});
    const previous=h('button',{type:'button',class:'btn sm',onclick:()=>{page--;draw();}},w('Anterior','Previous'));
    const next=h('button',{type:'button',class:'btn sm',onclick:()=>{page++;draw();}},w('Siguiente','Next'));
    const pagination=h('div',{class:'studio-actions'},previous,next);
    const values={},enabled={};
    const ack=h('input',{type:'checkbox','data-bulk-ack':'',onchange:()=>{apply.disabled=!preview||!preview.changes.length||!ack.checked;}});
    function invalidate(){edited=true;preview=null;review.replaceChildren();ack.checked=false;apply.disabled=true;error.textContent='';}
    function draw(){
      const query=search.value.trim().toLocaleLowerCase(),rows=(S.data.findings||[]).filter(f=>!query||(f.id+' '+f.title).toLocaleLowerCase().includes(query)),pages=Math.max(1,Math.ceil(rows.length/50));
      page=Math.min(page,pages-1);previous.disabled=page===0;next.disabled=page===pages-1;list.replaceChildren();
      for(const f of rows.slice(page*50,(page+1)*50)){
        const checkbox=h('input',{type:'checkbox','data-bulk-finding':f.uid,checked:selected.has(f.uid)?'':null,onchange:()=>{
          if(checkbox.checked&&selected.size>=500){checkbox.checked=false;error.textContent=w('El máximo es 500 hallazgos por operación.','The limit is 500 findings per operation.');return;}
          if(checkbox.checked)selected.add(f.uid);else selected.delete(f.uid);invalidate();updateCount();
        }});
        list.append(h('label',{class:'wf-check'},checkbox,f.id+' · '+(f.title||w('Sin título','Untitled'))));
      }
      if(!rows.length)list.append(h('p',{},w('Sin coincidencias. La selección de otras páginas se conserva.','No matches. Selections on other pages are retained.')));
      updateCount();
    }
    function updateCount(){count.textContent=selected.size+' '+w('hallazgos seleccionados, incluidas otras páginas. Máximo 500.','selected findings, including other pages. Maximum 500.');}
    form.append(h('legend',{},w('1. Selecciona hallazgos y campos','1. Select findings and fields')),h('p',{},w('Solo se cambia lo que selecciones. Vacío retira el valor. Estado, verificación, evidencias y retests se conservan. La comparación incluye todos los seleccionados, aunque estén ocultos por la búsqueda.','Only selected fields change. Empty clears a value. Status, verification, evidence and retests are preserved. The comparison includes every selected finding, including those hidden by search.')),search,count,list,pagination);
    for(const field of Object.keys(labels)){
      const input=field==='root_cause_uid'?h('select',{'data-bulk-value':field},h('option',{value:''},w('Sin grupo','No group')),...(S.data.root_cause_groups||[]).map(g=>h('option',{value:g.uid},g.name||g.uid))):h('input',{type:field==='due_date'?'date':'text',maxlength:field==='owner'?200:10,'data-bulk-value':field});
      input.disabled=true;input.setAttribute('aria-label',w(...labels[field]));input.addEventListener('input',invalidate);input.addEventListener('change',invalidate);values[field]=input;
      const checkbox=h('input',{type:'checkbox','data-bulk-field':field,onchange:()=>{input.disabled=!checkbox.checked;invalidate();}});enabled[field]=checkbox;
      form.append(h('div',{},h('label',{class:'wf-check'},checkbox,w('Cambiar ','Change ')+w(...labels[field])),input));
    }
    async function run(action){
      if(requestBusy)return;requestBusy=true;form.disabled=true;close.disabled=true;compare.disabled=true;apply.disabled=true;error.textContent='';busyProject(true);
      try{await action();}catch(e){error.textContent=e.message;}finally{requestBusy=false;form.disabled=false;close.disabled=false;compare.disabled=false;apply.disabled=!preview||!preview.changes.length||!ack.checked;busyProject(false);}
    }
    function current(){if(slug!==S.slug||workspace!==S.workspace_id||!dialog.isConnected)throw Error(w('El espacio o proyecto cambió. Cierra y vuelve a abrir esta edición.','The workspace or project changed. Close and reopen this editor.'));}
    const compare=h('button',{type:'button',class:'btn','data-bulk-compare':'',onclick:()=>run(async()=>{
      current();const payload={finding_uids:[...selected],values:{}};for(const [field,input]of Object.entries(values))if(enabled[field].checked)payload.values[field]=input.value;
      if(!payload.finding_uids.length||!Object.keys(payload.values).length)throw Error(w('Selecciona al menos un hallazgo y un campo.','Select at least one finding and one field.'));
      if(!await doSave())throw Error(w('Guarda primero los cambios pendientes del informe.','Save pending report changes first.'));current();
      const revision=projectStore.revision,etag=projectStore.etag;
      const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/bulk-edit/preview',{method:'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify(payload)}));
      const result=await response.json();current();if(revision!==projectStore.revision||etag!==projectStore.etag||response.headers.get('ETag')!==etag)throw Error(w('El informe cambió. Vuelve a comparar.','The report changed. Compare again.'));
      preview={...result,payload,etag,revision};ack.checked=false;review.replaceChildren(h('h3',{},w('2. Compara antes de guardar','2. Compare before saving')));
      if(!result.changes.length)review.append(h('p',{role:'status'},w('Los valores seleccionados ya coinciden. No hay cambios para guardar.','Selected values already match. There are no changes to save.')));
      const groups=new Map((S.data.root_cause_groups||[]).map(g=>[g.uid,g.name||g.uid]));
      for(const change of result.changes){const display=value=>value?(change.field==='root_cause_uid'?groups.get(value)||value:value):w('(vacío)','(empty)');const card=h('article',{class:'card','data-bulk-change':change.finding_uid+'.'+change.field},h('h4',{},change.id+' · '+change.title),h('strong',{},w(...labels[change.field])),h('p',{},w('Antes: ','Before: ')+display(change.before)),h('p',{},w('Después: ','After: ')+display(change.after)));if(change.field==='root_cause_uid')card.append(h('p',{},w('Acción efectiva antes: ','Effective action before: ')+(change.effective_action_before||w('(vacío)','(empty)'))),h('p',{},w('Acción efectiva después: ','Effective action after: ')+(change.effective_action_after||w('(vacío)','(empty)'))));review.append(card);}
      review.append(h('p',{},result.changes.length+' '+w('cambios. Se guardan en una sola operación con una versión recuperable.','changes. Saved in one operation with a recoverable version.')));review.scrollIntoView({block:'nearest'});
    })},w('Comparar cambios','Compare changes'));
    const apply=h('button',{type:'button',class:'btn primary','data-bulk-apply':'',disabled:'',onclick:()=>run(async()=>{
      current();if(!preview||!ack.checked)throw Error(w('Compara y confirma los cambios.','Compare and confirm the changes.'));
      if(projectStore.dirty||preview.revision!==projectStore.revision||preview.etag!==projectStore.etag)throw Error(w('El informe cambió. Vuelve a comparar.','The report changed. Compare again.'));
      const beforeRevision=projectStore.revision,beforeData=S.data,beforeJson=JSON.stringify(S.data);
      const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/bulk-edit/apply',{method:'POST',headers:{'Content-Type':'application/json','If-Match':preview.etag},body:JSON.stringify({...preview.payload,preview_token:preview.preview_token,ack_reviewed:true})}));
      const result=await response.json();current();
      if(beforeRevision!==projectStore.revision||beforeData!==S.data||beforeJson!==JSON.stringify(S.data)||projectStore.dirty)throw Error(w('El servidor guardó la asignación, pero el borrador local cambió. Se conserva tu borrador; revisa el conflicto antes de recargar.','The server saved the assignment, but the local draft changed. Your draft is preserved; review the conflict before reloading.'));
      await adoptSavedProject(result.data,response.headers.get('ETag'));renderSidebar();renderMain();if(S.previewMode==='live')refreshLivePreview();
      edited=false;dialog.close();toast(w('Asignaciones guardadas. Puedes recuperar la versión anterior en Versiones.','Assignments saved. Recover the previous version in Versions.'),'ok');
    })},w('Guardar cambios revisados','Save reviewed changes'));
    form.addEventListener('change',()=>{if(!requestBusy&&preview){preview=null;review.replaceChildren();ack.checked=false;apply.disabled=true;}});
    body.append(form,compare,review,h('label',{class:'wf-check'},ack,w('Revisé todos los cambios. Esta asignación no verifica una corrección.','I reviewed every change. This assignment does not verify a fix.')),error,apply);
    dialog.append(h('div',{class:'experience-heading'},h('h2',{},w('Edición por lotes','Bulk edit')),close),body);document.body.append(dialog);draw();dialog.showModal();search.focus();
  }
  return {open};
})();
