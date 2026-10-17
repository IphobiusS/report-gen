/* Explicit assignments with a saved-revision comparison and one atomic save. */
const BulkUI=(()=>{
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const labels={owner:['Responsable','Owner', "Responsável"],due_date:['Fecha de corrección','Remediation date', "Data da correção"],root_cause_uid:['Grupo de causa raíz','Root cause group', "Grupo de causa raiz"]};
  // Only editable assignments are journaled. Comparisons and acknowledgements
  // are deliberately rebuilt against the current server revision on recovery.
  function cleanDraft(input){
    if(!input||input.schema!==1||!Array.isArray(input.finding_uids)||input.finding_uids.length>500||input.finding_uids.some(uid=>typeof uid!=='string'||!uid)||new Set(input.finding_uids).size!==input.finding_uids.length||!input.values||typeof input.values!=='object'||Array.isArray(input.values)||!input.enabled||typeof input.enabled!=='object')throw Error(w('Borrador por lotes no compatible.','Unsupported bulk draft.','Rascunho em lote não compatível.'));
    const output={schema:1,finding_uids:[...input.finding_uids],values:{},enabled:{}};
    for(const field of Object.keys(labels)){
      if(typeof input.values[field]!=='string'||input.values[field].length>(field==='owner'?200:field==='due_date'?10:100)||typeof input.enabled[field]!=='boolean')throw Error(w('Borrador por lotes no compatible.','Unsupported bulk draft.','Rascunho em lote não compatível.'));
      output.values[field]=input.values[field];output.enabled[field]=input.enabled[field];
    }
    return output;
  }
  function missingReference(row){
    const data=cleanDraft(row.data),uids=new Set((S.data.findings||[]).map(f=>f.uid)),groups=new Set((S.data.root_cause_groups||[]).map(g=>g.uid));
    return data.finding_uids.some(uid=>!uids.has(uid))||!!(data.values.root_cause_uid&&!groups.has(data.values.root_cause_uid));
  }
  function open(recovered=null){
    if(recovered?.format!=='report-gen-pending')recovered=null;
    if(!S.slug||projectBusyCount||projectStore.loading)return;
    if(document.querySelector('[data-bulk-dialog]')){document.querySelector('[data-bulk-dialog] input')?.focus();return;}
    const slug=S.slug,workspace=S.workspace_id,trigger=document.activeElement,retained=PendingUI.active.get(S.slug+'|bulk:assignments');
    const initial=recovered?cleanDraft(recovered.data):retained?cleanDraft(retained.read().data):null;
    if((recovered&&(recovered.slug!==slug||recovered.workspace_id!==BrowserWorkspace.current()))||(initial&&missingReference({data:initial})))throw Error(w('El borrador ya no corresponde al proyecto actual.','The draft no longer matches the current project.','O rascunho não corresponde mais ao projeto atual.'));
    const selected=new Set(initial?.finding_uids||[]);
    let preview=null,requestBusy=false,edited=!!initial,page=0,pending=null;
    const dialog=h('dialog',{class:'experience-dialog workbench-dialog','aria-label':w('Editar hallazgos por lotes','Bulk edit findings', "Editar achados em lote"),'data-bulk-dialog':''});
    const body=h('div',{class:'experience-body'}),form=h('fieldset',{}),list=h('div',{'data-bulk-findings':''}),review=h('div',{'data-bulk-review':''}),error=h('p',{role:'alert'}),count=h('p',{role:'status'});
    const close=h('button',{type:'button',class:'btn',onclick:()=>requestClose()},w('Cerrar','Close', "Fechar"));
    const protectUnload=event=>{if(requestBusy||edited&&(!pending||pending.error||pending.persisted!==pending.revision)){event.preventDefault();event.returnValue='';}};
    window.addEventListener('beforeunload',protectUnload);
    function requestClose(){if(requestBusy)return;dialog.close();}
    dialog.addEventListener('cancel',event=>{event.preventDefault();requestClose();});
    dialog.addEventListener('close',()=>{window.removeEventListener('beforeunload',protectUnload);dialog.remove();(trigger?.isConnected&&!trigger.disabled?trigger:document.querySelector('[data-bulk-open]')||$('#editor'))?.focus({preventScroll:true});});
    const search=h('input',{type:'search','aria-label':w('Buscar hallazgos para seleccionar','Find findings to select', "Pesquisar achados para selecionar"),oninput:()=>{page=0;draw();}});
    const previous=h('button',{type:'button',class:'btn sm',onclick:()=>{page--;draw();}},w('Anterior','Previous', "Anterior"));
    const next=h('button',{type:'button',class:'btn sm',onclick:()=>{page++;draw();}},w('Siguiente','Next', "Próximo"));
    const pagination=h('div',{class:'studio-actions'},previous,next);
    const values={},enabled={};
    const ack=h('input',{type:'checkbox','data-bulk-ack':'',onchange:()=>{apply.disabled=!preview||!preview.changes.length||!ack.checked;}});
    function invalidate(){edited=true;preview=null;review.replaceChildren();ack.checked=false;apply.disabled=true;error.textContent='';if(pending)PendingUI.changed(pending);}
    function draw(){
      const query=search.value.trim().toLocaleLowerCase(),rows=(S.data.findings||[]).filter(f=>!query||(f.id+' '+f.title).toLocaleLowerCase().includes(query)),pages=Math.max(1,Math.ceil(rows.length/50));
      page=Math.min(page,pages-1);previous.disabled=page===0;next.disabled=page===pages-1;list.replaceChildren();
      for(const f of rows.slice(page*50,(page+1)*50)){
        const checkbox=h('input',{type:'checkbox','data-bulk-finding':f.uid,checked:selected.has(f.uid)?'':null,onchange:()=>{
          if(checkbox.checked&&selected.size>=500){checkbox.checked=false;error.textContent=w('El máximo es 500 hallazgos por operación.','The limit is 500 findings per operation.', "O limite é de 500 achados por operação.");return;}
          if(checkbox.checked)selected.add(f.uid);else selected.delete(f.uid);invalidate();updateCount();
        }});
        list.append(h('label',{class:'wf-check'},checkbox,f.id+' · '+(f.title||w('Sin título','Untitled', "Sem título"))));
      }
      if(!rows.length)list.append(h('p',{},w('Sin coincidencias. La selección de otras páginas se conserva.','No matches. Selections on other pages are retained.', "Nenhum resultado. As seleções em outras páginas foram mantidas.")));
      updateCount();
    }
    function updateCount(){count.textContent=selected.size+' '+w('hallazgos seleccionados, incluidas otras páginas. Máximo 500.','selected findings, including other pages. Maximum 500.', "achados selecionados, incluindo outras páginas. Máximo de 500.");}
    form.append(h('legend',{},w('1. Selecciona hallazgos y campos','1. Select findings and fields', "1. Selecionar achados e campos")),h('p',{},w('Solo se cambia lo que selecciones. Vacío retira el valor. Estado, verificación, evidencias y retests se conservan. La comparación incluye todos los seleccionados, aunque estén ocultos por la búsqueda.','Only selected fields change. Empty clears a value. Status, verification, evidence and retests are preserved. The comparison includes every selected finding, including those hidden by search.', "Somente os campos selecionados mudam. Vazio apaga um valor. Status, verificação, evidências e retestes são preservados. A comparação inclui todos os achados selecionados, inclusive os ocultos pela pesquisa.")),search,count,list,pagination);
    for(const field of Object.keys(labels)){
      const input=field==='root_cause_uid'?h('select',{'data-bulk-value':field},h('option',{value:''},w('Sin grupo','No group', "Sem grupo")),...(S.data.root_cause_groups||[]).map(g=>h('option',{value:g.uid},g.name||g.uid))):h('input',{type:field==='due_date'?'date':'text',maxlength:field==='owner'?200:10,'data-bulk-value':field});
      input.disabled=true;input.setAttribute('aria-label',w(...labels[field]));input.addEventListener('input',invalidate);input.addEventListener('change',invalidate);values[field]=input;
      const checkbox=h('input',{type:'checkbox','data-bulk-field':field,onchange:()=>{input.disabled=!checkbox.checked;invalidate();}});enabled[field]=checkbox;
      if(initial){input.value=initial.values[field];checkbox.checked=initial.enabled[field];input.disabled=!checkbox.checked;}
      form.append(h('div',{},h('label',{class:'wf-check'},checkbox,w('Cambiar ','Change ', "Alterar ")+w(...labels[field])),input));
    }
    const read=()=>({data:{schema:1,finding_uids:[...selected],values:Object.fromEntries(Object.entries(values).map(([field,input])=>[field,input.value])),enabled:Object.fromEntries(Object.entries(enabled).map(([field,input])=>[field,input.checked]))}});
    pending=PendingUI.track('bulk:assignments',w('Asignaciones por lotes pendientes','Pending bulk assignments','Atribuições em lote pendentes'),read,{origin:recovered});
    const discard=h('button',{type:'button',class:'btn','data-bulk-discard':'',onclick:async()=>{
      if(requestBusy||!confirm(w('¿Descartar esta selección, propuesta y su copia local? Los hallazgos guardados se conservan.','Discard this selection, proposal and local copy? Saved findings are retained.','Descartar esta seleção, proposta e cópia local? Os achados salvos serão mantidos.')))return;
      discard.disabled=true;try{if(await PendingUI.clear(pending)){edited=false;dialog.close();}}catch(e){error.textContent=e.message;}finally{discard.disabled=false;}
    }},w('Descartar formulario pendiente','Discard pending form','Descartar formulário pendente'));
    if(recovered)PendingUI.changed(pending);
    async function run(action){
      if(requestBusy)return;requestBusy=true;form.disabled=true;close.disabled=true;discard.disabled=true;compare.disabled=true;apply.disabled=true;error.textContent='';busyProject(true);
      try{await action();}catch(e){error.textContent=e.message;}finally{requestBusy=false;form.disabled=false;close.disabled=false;discard.disabled=false;compare.disabled=false;apply.disabled=!preview||!preview.changes.length||!ack.checked;busyProject(false);}
    }
    function current(){if(slug!==S.slug||workspace!==S.workspace_id||!dialog.isConnected)throw Error(w('El espacio o proyecto cambió. Cierra y vuelve a abrir esta edición.','The workspace or project changed. Close and reopen this editor.', "O espaço de trabalho ou o projeto mudou. Feche e reabra este editor."));}
    const compare=h('button',{type:'button',class:'btn','data-bulk-compare':'',onclick:()=>run(async()=>{
      current();const payload={finding_uids:[...selected],values:{}};for(const [field,input]of Object.entries(values))if(enabled[field].checked)payload.values[field]=input.value;
      if(!payload.finding_uids.length||!Object.keys(payload.values).length)throw Error(w('Selecciona al menos un hallazgo y un campo.','Select at least one finding and one field.', "Selecione pelo menos um achado e um campo."));
      if(!await doSave())throw Error(w('Guarda primero los cambios pendientes del informe.','Save pending report changes first.', "Salve primeiro as alterações pendentes do relatório."));current();
      const revision=projectStore.revision,etag=projectStore.etag;
      const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/bulk-edit/preview',{method:'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify(payload)}));
      const result=await response.json();current();if(revision!==projectStore.revision||etag!==projectStore.etag||response.headers.get('ETag')!==etag)throw Error(w('El informe cambió. Vuelve a comparar.','The report changed. Compare again.', "O relatório mudou. Compare novamente."));
      preview={...result,payload,etag,revision};ack.checked=false;review.replaceChildren(h('h3',{},w('2. Compara antes de guardar','2. Compare before saving', "2. Comparar antes de salvar")));
      if(!result.changes.length)review.append(h('p',{role:'status'},w('Los valores seleccionados ya coinciden. No hay cambios para guardar.','Selected values already match. There are no changes to save.', "Os valores selecionados já correspondem. Não há alterações para salvar.")));
      const groups=new Map((S.data.root_cause_groups||[]).map(g=>[g.uid,g.name||g.uid]));
      for(const change of result.changes){const display=value=>value?(change.field==='root_cause_uid'?groups.get(value)||value:value):w('(vacío)','(empty)', "(vazio)");const card=h('article',{class:'card','data-bulk-change':change.finding_uid+'.'+change.field},h('h4',{},change.id+' · '+change.title),h('strong',{},w(...labels[change.field])),h('p',{},w('Antes: ','Before: ', "Antes: ")+display(change.before)),h('p',{},w('Después: ','After: ', "Depois: ")+display(change.after)));if(change.field==='root_cause_uid')card.append(h('p',{},w('Acción efectiva antes: ','Effective action before: ', "Ação efetiva antes: ")+(change.effective_action_before||w('(vacío)','(empty)', "(vazio)"))),h('p',{},w('Acción efectiva después: ','Effective action after: ', "Ação efetiva depois: ")+(change.effective_action_after||w('(vacío)','(empty)', "(vazio)"))));review.append(card);}
      review.append(h('p',{},result.changes.length+' '+w('cambios. Se guardan en una sola operación con una versión recuperable.','changes. Saved in one operation with a recoverable version.', "alterações. Salvas em uma única operação com uma versão recuperável.")));review.scrollIntoView({block:'nearest'});
    })},w('Comparar cambios','Compare changes', "Comparar alterações"));
    const apply=h('button',{type:'button',class:'btn primary','data-bulk-apply':'',disabled:'',onclick:()=>run(async()=>{
      current();if(!preview||!ack.checked)throw Error(w('Compara y confirma los cambios.','Compare and confirm the changes.', "Compare e confirme as alterações."));
      if(projectStore.dirty||preview.revision!==projectStore.revision||preview.etag!==projectStore.etag)throw Error(w('El informe cambió. Vuelve a comparar.','The report changed. Compare again.', "O relatório mudou. Compare novamente."));
      const pendingRevision=pending.revision,beforeRevision=projectStore.revision,beforeData=S.data,beforeJson=JSON.stringify(S.data);
      const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/bulk-edit/apply',{method:'POST',headers:{'Content-Type':'application/json','If-Match':preview.etag},body:JSON.stringify({...preview.payload,preview_token:preview.preview_token,ack_reviewed:true})}));
      const result=await response.json();current();
      if(beforeRevision!==projectStore.revision||beforeData!==S.data||beforeJson!==JSON.stringify(S.data)||projectStore.dirty)throw Error(w('El servidor guardó la asignación, pero el borrador local cambió. Se conserva tu borrador; revisa el conflicto antes de recargar.','The server saved the assignment, but the local draft changed. Your draft is preserved; review the conflict before reloading.', "O servidor salvou a atribuição, mas o rascunho local mudou. Seu rascunho foi preservado; revise o conflito antes de recarregar."));
      await adoptSavedProject(result.data,response.headers.get('ETag'));renderSidebar();renderMain();if(S.previewMode==='live')refreshLivePreview();
      const cleanup=await PendingUI.committed(pending,pendingRevision);
      if(cleanup.finished){edited=false;dialog.close();}
      if(cleanup.warning)toast(w('Asignaciones guardadas, pero su copia local no se pudo eliminar. Revísala en Datos privados guardados.','Assignments saved, but their local copy could not be deleted. Review Stored private data.','Atribuições salvas, mas a cópia local não pôde ser excluída. Revise Dados privados armazenados.'),'err');
      else toast(w('Asignaciones guardadas. Puedes recuperar la versión anterior en Versiones.','Assignments saved. Recover the previous version in Versions.', "Atribuições salvas. Recupere a versão anterior em Versões."),'ok');
    })},w('Guardar cambios revisados','Save reviewed changes', "Salvar alterações revisadas"));
    form.addEventListener('change',()=>{if(!requestBusy&&preview){preview=null;review.replaceChildren();ack.checked=false;apply.disabled=true;}});
    body.append(h('p',{},w('Cerrar conserva el formulario pendiente. Recuperarlo no guarda asignaciones: deberás comparar y confirmar de nuevo.','Closing retains the pending form. Recovery does not save assignments: compare and confirm again.','Fechar mantém o formulário pendente. Recuperar não salva atribuições: compare e confirme novamente.')),PendingUI.status(pending),form,compare,review,h('label',{class:'wf-check'},ack,w('Revisé todos los cambios. Esta asignación no verifica una corrección.','I reviewed every change. This assignment does not verify a fix.', "Revisei cada alteração. Esta atribuição não verifica uma correção.")),error,h('div',{class:'studio-actions'},apply,discard));
    dialog.append(h('div',{class:'experience-heading'},h('h2',{},w('Edición por lotes','Bulk edit', "Editar em lote")),close),body);document.body.append(dialog);draw();dialog.showModal();search.focus();
  }
  PendingUI.register('bulk:',{validate:row=>{if(row.key!=='bulk:assignments')throw Error(w('Formulario por lotes no compatible.','Unsupported bulk form.','Formulário em lote não compatível.'));cleanDraft(row.data);},missingReference,restore:open});
  return {open};
})();
