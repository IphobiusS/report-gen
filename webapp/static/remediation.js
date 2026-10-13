/* Local task deliveries. Preview and download use the same immutable saved revision. */
const RemediationUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const fields=[
    ['id','ID del hallazgo','Finding ID', "ID do achado"],['finding_uid','Referencia permanente','Permanent reference', "Referência permanente"],
    ['title','Título','Title', "Título"],['assets','Activos afectados','Affected assets', "Ativos afetados"],
    ['action','Acción de remediación','Remediation action', "Ação de correção"],['owner','Responsable','Owner', "Responsável"],
    ['due_date','Plazo','Due date', "Prazo"],['closure_criteria','Criterio de cierre','Closure criteria', "Critérios de encerramento"],
    ['status','Estado registrado','Recorded status', "Status registrado"],['group_uid','Referencia del grupo','Group reference', "Referência do grupo"],
    ['group_name','Grupo por causa raíz','Root-cause group', "Grupo de causa raiz"],['shared_action','Acción común del grupo','Shared group action', "Ação compartilhada do grupo"]
  ];
  const privateFields=new Set(['title','assets','action','owner','closure_criteria','group_name','shared_action']);
  let mounted=null,generation=0;
  const tag=etag=>String(etag||'').replace(/^"|"$/g,'');
  function same(state){return S.slug===state.slug&&S.data===state.data&&JSON.stringify(S.data)===state.json&&
    projectStore.etag===state.etag&&projectStore.revision===state.revision&&S.uiLang===state.lang&&
    !projectStore.dirty&&!projectStore.loading&&projectBusyCount===0;}
  function invalidate(){if(mounted&&!same(mounted)){mounted.token=null;invalidateReturn(mounted);mounted.host.querySelector('[data-remediation-preview]')?.replaceChildren();
    mounted.status.textContent=w('El proyecto cambió. Guarda desde la barra y actualiza esta vista.','The project changed. Save from the toolbar and refresh this view.', "O projeto mudou. Salve pela barra de ferramentas e atualize esta visualização.");
    mounted.host.querySelectorAll('[data-remediation-download],[data-remediation-preview-button],[data-return-issue],[data-return-preview],[data-return-apply],[data-return-file]').forEach(button=>button.disabled=true);}}
  function guard(state){if(!same(state)){invalidate();return false;}return mounted===state&&state.host.isConnected;}
  function button(label,run,attributes={}){const node=h('button',{type:'button',class:'btn sm',...attributes},label);
    node.addEventListener('click',async()=>{node.disabled=true;try{await run();}catch(error){if(node.isConnected)toast(error.message,'err');}
      finally{if(node.isConnected){node.disabled=false;if(mounted)updateButtons(mounted);}}});return node;}
  function selection(state){return fields.map(row=>row[0]).filter(key=>state.selected.has(key));}
  function sensitive(state){return [...state.selected].some(key=>privateFields.has(key));}
  function updateButtons(state){const allowed=guard(state)&&(!sensitive(state)||state.ack.checked);
    state.previewButton.disabled=!allowed||state.loading;
    state.host.querySelectorAll('[data-remediation-download]').forEach(node=>node.disabled=!allowed||state.loading||!state.token||!state.count);updateReturnButtons(state);}
  function clearPreview(state){state.token=null;state.count=0;state.preview.replaceChildren();clearDelivery(state);state.status.textContent=w('Previsualiza los campos seleccionados antes de descargar.','Preview selected fields before downloading.', "Confira os campos selecionados antes de baixar.");updateButtons(state);}
  function body(state){return {fields:selection(state),lang:state.lang,ack_private:state.ack.checked};}
  async function request(state,operation,options){return requireOk(await appFetch('/api/projects/'+encodeURIComponent(state.slug)+'/remediation-tasks/'+operation,
    {method:'POST',headers:{'Content-Type':'application/json','If-Match':state.etag},body:JSON.stringify(options)}));}
  async function preview(state){
    if(!guard(state))return;state.loading=true;updateButtons(state);
    const sequence=++state.sequence,options=body(state),signature=JSON.stringify(options);
    state.token=null;state.preview.replaceChildren();state.status.textContent=w('Leyendo la revisión guardada…','Reading the saved revision…', "Lendo a revisão salva…");
    try{const response=await request(state,'preview',options),result=await response.json();
      if(!guard(state)||sequence!==state.sequence||JSON.stringify(body(state))!==signature)return;
      if(response.headers.get('ETag')!==state.etag||result.revision!==tag(state.etag)||result.project_slug!==state.slug||
        result.version!==1||result.source!=='saved_project'||!Array.isArray(result.rows)||JSON.stringify(result.fields)!==JSON.stringify(options.fields))
        throw Error(w('La revisión recibida no coincide; actualiza esta vista.','The returned revision differs; refresh this view.', "A revisão retornada é diferente; atualize esta visualização."));
      state.token=result.preview_token;state.count=result.rows.length;
      state.status.textContent=result.rows.length+' '+w('tareas. Revisa el contenido antes de descargar.','tasks. Review the contents before downloading.', "tarefas. Revise o conteúdo antes de baixar.");
      if(!result.rows.length){state.preview.append(h('p',{},w('Añade un hallazgo para preparar tareas.','Add a finding to prepare tasks.', "Adicione um achado para preparar tarefas.")));return;}
      result.rows.forEach((row,index)=>{
        const values=h('dl',{});result.fields.forEach(key=>values.append(h('dt',{},result.labels[key]),h('dd',{},row[key]||w('Sin registrar','Not recorded', "Não registrado"))));
        state.preview.append(h('details',{class:'rt-card',open:index===0?'':null},h('summary',{},w('Tarea ','Task ', "Tarefa ")+(index+1)+' · '+row.id),values));
      });
    }catch(error){if(guard(state)){state.token=null;state.status.textContent=error.message;}}
    finally{if(mounted===state){state.loading=false;updateButtons(state);}}
  }
  async function download(state,format){
    if(!guard(state)||!state.token)return;state.loading=true;updateButtons(state);
    const token=state.token,options={...body(state),format,preview_token:token};
    try{const response=await request(state,'export',options),blob=await response.blob();
      if(!guard(state)||state.token!==token)return;
      if(response.headers.get('ETag')!==state.etag)throw Error(w('La descarga no corresponde a esta revisión.','The download does not match this revision.', "O download não corresponde a esta revisão."));
      const url=URL.createObjectURL(blob),link=h('a',{href:url,download:'remediation-tasks.'+(format==='csv'?'csv':'zip')});
      link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      state.status.textContent=w('Descarga preparada con los campos previsualizados.','Download prepared with the previewed fields.', "Download preparado com os campos apresentados na prévia.");
    }catch(error){if(guard(state)){state.token=null;state.status.textContent=error.message;}}
    finally{if(mounted===state){state.loading=false;updateButtons(state);}}
  }
  function invalidateReturn(state){
    if(!state.returning)return;
    clearDelivery(state);
    state.returning.token=null;state.returning.selected.clear();state.returning.changes.replaceChildren();
    state.returning.apply.disabled=true;state.returning.reviewed.checked=false;
  }
  function updateReturnButtons(state){
    const r=state.returning;if(!r)return;
    const ready=same(state)&&!state.loading&&mounted===state&&state.host.isConnected;
    r.issue.disabled=!ready||!r.assigned.size||!r.private.checked||!r.retention.checked;
    r.preview.disabled=!ready||!r.text;
    r.apply.disabled=!ready||!r.token||!r.selected.size||!r.reviewed.checked;
    r.receive.disabled=!ready||!r.token;
    r.deliveryPreview.disabled=!ready||!r.assigned.size||!r.private.checked||!r.retention.checked;
    r.deliveryExport.disabled=r.deliveryPreview.disabled||!r.deliveryToken;
    r.file.disabled=!ready;
  }
  async function acceptReturnMutation(state,response,data){
    if(S.slug!==state.slug||S.data!==state.data||projectStore.etag!==state.etag||projectStore.revision!==state.revision||JSON.stringify(S.data)!==state.json||projectStore.dirty)
      throw Error(w('El proyecto cambió. Recarga el proyecto para ver el resultado guardado.','The project changed. Reload it to see the saved result.', "O projeto mudou. Recarregue-o para ver o resultado salvo."));
    if(!data||typeof data!=='object'||!Array.isArray(data.findings)||!/^"[a-f0-9]{64}"$/.test(response.headers.get('ETag')||''))
      throw Error(w('Respuesta de guardado inválida. Recarga el proyecto para comprobar el resultado.','Invalid saved response. Reload the project to check the result.', "Resposta salva inválida. Recarregue o projeto para verificar o resultado."));
    await adoptSavedProject(data,response.headers.get('ETag'));
    if(typeof RetestMatrixUI!=='undefined')RetestMatrixUI.invalidate();
    if(typeof RetestDiffUI!=='undefined')RetestDiffUI.invalidate();
    if(S.previewVisible&&S.previewMode==='live')refreshLivePreview();
  }
  async function issueReturn(state,delivery=false){
    if(!guard(state))return;
    const r=state.returning,options=delivery?{...deliveryBody(state),preview_token:r.deliveryToken}:{finding_uids:[...r.assigned],ack_private:r.private.checked,ack_retention:r.retention.checked};
    let success=false;
    let downloaded=false;
    state.loading=true;updateButtons(state);busyProject(true);
    try{
      const response=await request(state,delivery?'delivery-export':'return-template',options),blob=await response.blob();
      // The server has already committed this assignment. Do not lose its
      // artifact if the subsequent project refresh fails or sees another edit.
      const url=URL.createObjectURL(blob);h('a',{href:url,download:delivery?'remediation-delivery.zip':'remediation-return.csv'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);downloaded=true;
      const current=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(state.slug)));
      if(current.headers.get('ETag')!==response.headers.get('ETag'))throw Error(w('El proyecto cambió. Recarga antes de emitir otra plantilla.','The project changed. Reload before issuing another template.', "O projeto mudou. Recarregue antes de emitir outro modelo."));
      await acceptReturnMutation(state,current,await current.json());
      success=true;
      toast(w('Plantilla emitida y asignación guardada.','Template issued and assignment saved.', "Modelo emitido e atribuição salva."),'ok');
    }catch(error){if(mounted===state)r.status.textContent=(downloaded?w('La descarga fue preparada y la asignación se guardó. Recarga el proyecto antes de continuar. ','The download was prepared and the assignment was saved. Reload the project before continuing. ', "O download foi preparado e a atribuição foi salva. Recarregue o projeto antes de continuar. "):'')+error.message;throw error;}
    finally{state.loading=false;busyProject(false);if(success&&mounted===state){renderSidebar();select('workflow','remediation_tasks');}else if(mounted===state)updateButtons(state);}
  }
  async function previewReturn(state){
    if(!guard(state))return;
    const r=state.returning,text=r.text,sequence=++r.sequence;
    invalidateReturn(state);state.loading=true;updateButtons(state);
    r.status.textContent=w('Comparando con el proyecto guardado…','Comparing against the saved project…', "Comparando com o projeto salvo…");
    try{
      const response=await request(state,'return-preview',{text}),result=await response.json();
      if(!guard(state)||r.text!==text||r.sequence!==sequence)return;
      if(response.headers.get('ETag')!==state.etag||result.revision!==tag(state.etag)||result.project_slug!==state.slug||result.version!==1||!Array.isArray(result.changes))
        throw Error(w('La revisión recibida no coincide.','The returned revision does not match.', "A revisão retornada não corresponde."));
      r.token=result.preview_token;
      r.status.textContent=result.changes.length+' '+w('cambios propuestos. Selecciona individualmente los que aceptas.','proposed changes. Select individually those you accept.', "alterações propostas. Selecione individualmente as que aceita.");
      const labels={owner:w('Responsable','Owner', "Responsável"),due_date:w('Plazo','Due date', "Prazo"),reported_remediation:w('Corrección comunicada (sin verificar)','Reported remediation (unverified)', "Correção informada (não verificada)")};
      result.changes.forEach(change=>{
        const input=h('input',{type:'checkbox','data-return-change':change.key});
        input.addEventListener('change',()=>{if(input.checked)r.selected.add(change.key);else r.selected.delete(change.key);r.reviewed.checked=false;updateReturnButtons(state);});
        const values=h('dl',{},h('dt',{},w('Valor actual','Current value', "Valor atual")),h('dd',{},change.before||w('Vacío','Empty', "Vazio")),
          h('dt',{},w('Propuesta recibida','Received proposal', "Proposta recebida")),h('dd',{},change.after||w('Vacío (se eliminará este dato)','Empty (this value will be cleared)', "Vazio (este valor será apagado)")));
        const card=h('section',{class:'rt-card rt-return-change'},h('label',{class:'rt-check'},input,change.finding_id+' · '+labels[change.field]),values);
        if(change.changed_since_issue){card.append(h('p',{class:'wf-hint'},w('Este campo cambió desde que se emitió la plantilla. Compara también su valor de origen antes de aceptar.','This field changed after the template was issued. Also compare its original value before accepting.', "Este campo mudou após a emissão do modelo. Compare também o valor original antes de aceitar.")),
          h('dl',{},h('dt',{},w('Al emitir la plantilla','When issued', "Na emissão")),h('dd',{},change.issued||w('Vacío','Empty', "Vazio"))));}
        r.changes.append(card);
      });
    }catch(error){if(guard(state)){invalidateReturn(state);r.status.textContent=error.message;}}
    finally{if(mounted===state){state.loading=false;updateButtons(state);}}
  }
  async function applyReturn(state,receive=false){
    if(!guard(state))return;
    const r=state.returning,options=receive?{text:r.text,preview_token:r.token,ack_reviewed:true}:{text:r.text,preview_token:r.token,selected:[...r.selected],ack_reviewed:r.reviewed.checked};
    let success=false;
    state.loading=true;updateButtons(state);busyProject(true);
    try{
      const response=await request(state,receive?'return-receive':'return-apply',options),result=await response.json();
      await acceptReturnMutation(state,response,result.data);
      success=true;
      toast(receive?w('Recepción registrada. No se aplicaron cambios a hallazgos.','Receipt recorded. No finding changes were applied.', "Recebimento registrado. Nenhuma alteração foi aplicada aos achados."):result.applied+' '+w('cambios guardados. La verificación técnica y los retests se conservan.','changes saved. Technical verification and retests are preserved.', "alterações salvas. A verificação técnica e os retestes foram preservados."),'ok');
    }catch(error){if(mounted===state)r.status.textContent=error.message+' '+w('Se conservan el archivo y la selección para reintentar. Si la revisión cambió, recarga el proyecto y compara de nuevo.','The file and selection are preserved for retry. If the revision changed, reload the project and compare again.', "O arquivo e a seleção foram preservados para nova tentativa. Se a revisão mudou, recarregue o projeto e compare novamente.");throw error;}
    finally{state.loading=false;busyProject(false);if(success&&mounted===state){renderSidebar();select('workflow','remediation_tasks');}else if(mounted===state)updateButtons(state);}
  }
  function clearDelivery(state){const r=state.returning;if(!r)return;r.deliveryToken=null;r.deliveryRows?.replaceChildren();}
  function deliveryBody(state){const r=state.returning;return {finding_uids:[...r.assigned],fields:selection(state),lang:state.lang,ack_private:r.private.checked,ack_retention:r.retention.checked};}
  async function previewDelivery(state){
    if(!guard(state))return;
    const r=state.returning,options=deliveryBody(state),signature=JSON.stringify(options);clearDelivery(state);
    state.loading=true;updateButtons(state);
    try{
      const response=await request(state,'delivery-preview',options),result=await response.json();
      if(!guard(state)||JSON.stringify(deliveryBody(state))!==signature)return;
      if(response.headers.get('ETag')!==state.etag||result.revision!==tag(state.etag)||result.project_slug!==state.slug||result.version!==1||!Array.isArray(result.rows)||JSON.stringify(result.fields)!==JSON.stringify(options.fields))
        throw Error(w('La revisión recibida no coincide.','The returned revision does not match.', "A revisão retornada não corresponde."));
      const labels={owner:w('Responsable','Owner', "Responsável"),due_date:w('Plazo','Due date', "Prazo"),reported_remediation:w('Corrección comunicada (sin verificar)','Reported remediation (unverified)', "Correção informada (não verificada)")};
      result.rows.forEach((row,index)=>{
        const values=h('dl',{});result.fields.forEach(key=>values.append(h('dt',{},result.labels[key]),h('dd',{},row.card[key]||w('Vacío','Empty', "Vazio"))));
        const returned=h('dl',{});Object.keys(labels).forEach(key=>returned.append(h('dt',{},labels[key]),h('dd',{},row.return_values[key]||w('Vacío','Empty', "Vazio"))));
        r.deliveryRows.append(h('details',{class:'rt-card',open:index===0?'':null},h('summary',{},row.card.id+' · '+row.return_values.owner),
          h('h4',{},w('Ficha con los campos seleccionados arriba','Card with fields selected above', "Cartão com os campos selecionados acima")),values,
          h('h4',{},w('Valores incluidos siempre en el CSV editable','Values always included in the editable CSV', "Valores sempre incluídos no CSV editável")),returned));
      });
      r.deliveryToken=result.preview_token;
      r.status.textContent=w('Revisa las fichas y todos los valores del CSV. El ZIP y su manifiesto reúnen todos los responsables: comparte solo la carpeta de cada destinatario. No se envía automáticamente.','Review the cards and every CSV value. The ZIP and manifest combine all owners: share only each recipient’s folder. Nothing is sent automatically.', "Revise os cartões e todos os valores do CSV. O ZIP e o manifesto reúnem todos os responsáveis: compartilhe somente a pasta de cada destinatário. Nada é enviado automaticamente.");
    }catch(error){if(mounted===state)r.status.textContent=error.message;}
    finally{if(mounted===state){state.loading=false;updateButtons(state);}}
  }
  async function revokeReturn(state,batch){
    if(!guard(state)||!confirm(w('¿Revocar este lote? Sus retornos dejarán de admitirse. No cambia hallazgos ni borra registros.','Revoke this batch? Its returns will no longer be accepted. Findings and records are preserved.', "Revogar este lote? Seus retornos não serão mais aceitos. Achados e registros serão preservados.")))return;
    let success=false;state.loading=true;updateButtons(state);busyProject(true);
    try{const response=await request(state,'return-revoke',{batch_uid:batch.uid,ack_reviewed:true}),result=await response.json();
      await acceptReturnMutation(state,response,result.data);success=true;
    }catch(error){if(mounted===state)state.returning.status.textContent=error.message;throw error;}
    finally{state.loading=false;busyProject(false);if(success&&mounted===state){renderSidebar();select('workflow','remediation_tasks');}else if(mounted===state)updateButtons(state);}
  }
  function ledgerView(state){
    const labels={issued:w('Emitido localmente','Issued locally', "Emitido localmente"),received:w('Recepción registrada','Receipt recorded', "Recebimento registrado"),accepted:w('Cambios aceptados','Changes accepted', "Alterações aceitas"),revoked:w('Revocado','Revoked', "Revogado")};
    const hashLabels={issued:w('SHA-256 de la descarga emitida','SHA-256 of the issued download', "SHA-256 do download emitido"),received:w('SHA-256 del CSV recibido','SHA-256 of the received CSV', "SHA-256 do CSV recebido"),accepted:w('SHA-256 de los cambios aceptados','SHA-256 of accepted changes', "SHA-256 das alterações aceitas"),revoked:w('SHA-256 de la referencia del lote','SHA-256 of the batch reference', "SHA-256 da referência do lote")};
    const box=h('details',{'data-return-ledger':''},h('summary',{},w('Registro local de lotes','Local batch log', "Registro local de lotes")),
      h('p',{},w('Hasta 20 lotes o 4 MiB y 16 eventos por lote. Se indican los eventos anteriores omitidos. Este registro local editable no demuestra envío, identidad del remitente ni verificación técnica. Restaurar una versión antigua también restaura sus lotes y revocaciones.','Up to 20 batches or 4 MiB and 16 events per batch. Older omitted events are counted. This editable local record does not prove delivery, sender identity or technical verification. Restoring an older version also restores its batches and revocations.', "Até 20 lotes ou 4 MiB e 16 eventos por lote. Eventos antigos omitidos são contabilizados. Este registro local editável não comprova entrega, identidade do remetente nem verificação técnica. Restaurar uma versão antiga também restaura seus lotes e revogações.")));
    for(const batch of [...(state.data.remediation_exchanges||[])].reverse()){
      const rows=h('details',{class:'rt-card','data-return-ledger-batch':''},h('summary',{},batch.uid+' · '+(batch.revoked?w('Revocado','Revoked', "Revogado"):w('Admite retornos','Returns accepted', "Retornos aceitos"))));
      if(!batch.events?.length)rows.append(h('p',{},w('Lote anterior sin eventos registrados; no se inventan fechas.','Legacy batch without recorded events; no dates are inferred.', "Lote legado sem eventos registrados; nenhuma data é inferida.")));
      if(batch.events_omitted)rows.append(h('p',{},batch.events_omitted+' '+w('eventos anteriores omitidos.','older events omitted.', "eventos antigos omitidos.")));
      for(const event of batch.events||[]){const time=h('time',{datetime:event.at},new Date(event.at).toLocaleString(languageTag(state.lang)));
        const count=event.kind==='revoked'?'':' · '+event.count+' '+(event.kind==='accepted'?w('cambios','changes', "alterações"):w('hallazgos','findings', "achados"));
        rows.append(h('p',{},labels[event.kind]+' · ',time,count),h('dl',{},h('dt',{},w('Revisión de origen','Source revision', "Revisão de origem")),h('dd',{},event.source_revision),h('dt',{},hashLabels[event.kind]),h('dd',{},event.sha256)));}
      if(!batch.revoked)rows.append(button(w('Revocar este lote','Revoke this batch', "Revogar este lote"),()=>revokeReturn(state,batch)));
      box.append(rows);
    }
    return box;
  }
  function returnView(state){
    const r=state.returning={assigned:new Set(),selected:new Set(),text:'',token:null,sequence:0};
    r.changes=h('div',{'data-return-changes':''});
    r.status=h('p',{role:'status','aria-live':'polite','data-return-status':''});
    r.private=h('input',{type:'checkbox','data-return-private':''});r.retention=h('input',{type:'checkbox','data-return-retention':''});
    r.reviewed=h('input',{type:'checkbox','data-return-reviewed':''});
    [r.private,r.retention,r.reviewed].forEach(input=>input.addEventListener('change',()=>{if(input!==r.reviewed)clearDelivery(state);updateReturnButtons(state);}));
    const assigned=h('fieldset',{class:'rt-fields'},h('legend',{},w('Hallazgos que asignarás','Findings to assign', "Achados a atribuir")));
    (S.data.findings||[]).forEach(finding=>{
      const valid=!!finding.owner?.trim(),input=h('input',{type:'checkbox','data-return-finding':finding.uid,disabled:valid?null:''});
      input.addEventListener('change',()=>{if(input.checked)r.assigned.add(finding.uid);else r.assigned.delete(finding.uid);clearDelivery(state);updateReturnButtons(state);});
      assigned.append(h('label',{class:'rt-check'},input,(finding.id||'')+' · '+(finding.owner||w('Asigna un responsable en el hallazgo','Assign an owner in the finding', "Atribua um responsável no achado"))));
    });
    if(!(S.data.findings||[]).length)assigned.append(h('p',{},w('Añade hallazgos y asigna sus responsables primero.','Add findings and assign their owners first.', "Adicione achados e atribua seus responsáveis primeiro.")));
    r.issue=button(w('Emitir plantilla de retorno CSV','Issue return CSV template', "Emitir modelo CSV de retorno"),()=>issueReturn(state),{'data-return-issue':'',disabled:''});
    r.preview=button(w('Comparar retorno','Compare return', "Comparar retorno"),()=>previewReturn(state),{'data-return-preview':'',disabled:''});
    r.apply=button(w('Guardar cambios seleccionados','Save selected changes', "Salvar alterações selecionadas"),()=>applyReturn(state),{'data-return-apply':'',disabled:''});
    r.receive=button(w('Registrar recepción sin aplicar cambios','Record receipt without applying changes', "Registrar recebimento sem aplicar alterações"),()=>applyReturn(state,true),{'data-return-receive':'',disabled:''});
    r.deliveryPreview=button(w('Previsualizar entrega por responsable','Preview owner delivery', "Visualizar entrega por responsável"),()=>previewDelivery(state),{'data-return-delivery-preview':'',disabled:''});
    r.deliveryExport=button(w('Emitir fichas y CSV por responsable (ZIP)','Issue cards and CSV by owner (ZIP)', "Emitir cartões e CSV por responsável (ZIP)"),()=>issueReturn(state,true),{'data-return-delivery-export':'',disabled:''});
    r.deliveryRows=h('div',{'data-return-delivery-rows':''});
    r.file=h('input',{type:'file',accept:'.csv,text/csv','data-return-file':''});
    r.file.addEventListener('change',async()=>{
      const sequence=++r.sequence;invalidateReturn(state);r.text='';r.status.textContent='';updateReturnButtons(state);
      try{const file=r.file.files[0];if(!file)return;
        if(file.size>2*1024*1024)throw Error(w('El CSV supera 2 MiB.','CSV exceeds 2 MiB.', "O CSV excede 2 MiB."));
        const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(await file.arrayBuffer());
        if(!guard(state)||r.sequence!==sequence)return;r.text=text;r.status.textContent=w('Archivo leído. Compara antes de guardar.','File read. Compare before saving.', "Arquivo lido. Compare antes de salvar.");
      }catch(error){if(guard(state)&&r.sequence===sequence)r.status.textContent=w('No se pudo leer el CSV UTF-8: ','Could not read the UTF-8 CSV: ', "Não foi possível ler o CSV UTF-8: ")+error.message;}
      finally{if(mounted===state)updateReturnButtons(state);}
    });
    return h('section',{class:'rt-return','data-remediation-return':''},h('h3',{},w('Recibir avances del responsable','Receive owner updates', "Receber atualizações dos responsáveis")),
      h('p',{},w('Emite una plantilla o prepara fichas y CSV juntos por responsable. Al recibirla, podrás aceptar cada cambio de responsable, plazo o corrección comunicada. Esta importación nunca modifica el estado, la verificación técnica ni los retests.','Issue a template or prepare cards and CSV together by owner. On return, accept each owner, due date or reported remediation change. This import never modifies status, technical verification or retests.', "Emita um modelo ou prepare cartões e CSV juntos por responsável. No retorno, aceite cada alteração de responsável, prazo ou correção informada. Esta importação nunca modifica o status, a verificação técnica nem os retestes.")),
      h('details',{},h('summary',{},w('1. Emitir una plantilla','1. Issue a template', "1. Emitir um modelo")),assigned,
        h('label',{class:'rt-check rt-private'},r.private,w('Revisé los responsables y las comunicaciones que saldrán del proyecto.','I reviewed the owners and communications that will leave the project.', "Revisei os responsáveis e as comunicações que sairão do projeto.")),
        h('label',{class:'rt-check rt-private'},r.retention,w('Entiendo que emitir guarda una asignación. Se conservan hasta 20 lotes o 4 MiB; los más antiguos dejan de admitirse.','I understand issuance saves an assignment. Up to 20 batches or 4 MiB are retained; older batches stop being accepted.', "Entendo que a emissão salva uma atribuição. São mantidos até 20 lotes ou 4 MiB; lotes mais antigos deixam de ser aceitos.")),
        h('p',{class:'wf-hint'},w('Edita solo owner, due_date y reported_remediation. Conserva el apóstrofo inicial en owner y reported_remediation, incluso si estaban vacíos. Fechas: AAAA-MM-DD. Conserva las referencias y guarda como CSV UTF-8 con comas. Puedes devolver solo algunas filas.','Edit only owner, due_date and reported_remediation. Preserve the initial apostrophe in owner and reported_remediation, even when empty. Dates: YYYY-MM-DD. Preserve references and save as comma-separated UTF-8 CSV. You may return only some rows.', "Edite somente owner, due_date e reported_remediation. Preserve o apóstrofo inicial em owner e reported_remediation, mesmo quando vazios. Datas: YYYY-MM-DD. Preserve as referências e salve como CSV UTF-8 separado por vírgulas. Você pode devolver somente algumas linhas.")),
        h('p',{class:'wf-hint'},w('El ZIP completo y manifest.json contienen todos los responsables seleccionados. Comparte únicamente la carpeta owner-NNN que corresponda al destinatario.','The full ZIP and manifest.json contain all selected owners. Share only the owner-NNN folder belonging to the recipient.', "O ZIP completo e manifest.json contêm todos os responsáveis selecionados. Compartilhe somente a pasta owner-NNN que pertence ao destinatário.")),
        h('div',{class:'rt-actions'},r.issue,r.deliveryPreview,r.deliveryExport),r.deliveryRows),
      h('h4',{},w('2. Revisar el CSV recibido','2. Review the returned CSV', "2. Revisar o CSV retornado")),
      h('label',{},w('Plantilla de retorno CSV (hasta 2 MiB)','Return CSV template (up to 2 MiB)', "Modelo CSV de retorno (até 2 MiB)"),r.file),h('div',{class:'rt-actions'},r.preview),r.status,r.changes,
      h('label',{class:'rt-check rt-private'},r.reviewed,w('Revisé cada cambio seleccionado y entiendo que una corrección comunicada no demuestra que esté corregido.','I reviewed each selected change and understand that a reported remediation does not prove it is fixed.', "Revisei cada alteração selecionada e entendo que uma correção informada não comprova que o problema foi corrigido.")),
      h('div',{class:'rt-actions'},r.apply,r.receive),ledgerView(state));
  }
  function render(host){
    ++generation;mounted=null;
    const refresh=button(w('Recargar proyecto guardado y reiniciar esta vista','Reload saved project and reset this view', "Recarregar projeto salvo e reiniciar esta visualização"),async()=>{
      if(!S.slug||projectStore.dirty||projectStore.loading||projectBusyCount>0){render(host);return;}
      const slug=S.slug;await loadProject(slug);if(S.slug===slug&&!projectStore.lastError)select('workflow','remediation_tasks');
    },{'data-remediation-refresh':''});
    if(!S.slug||!S.data){host.replaceChildren(h('p',{},w('Abre un proyecto para preparar tareas.','Open a project to prepare tasks.', "Abra um projeto para preparar tarefas.")));return;}
    if(projectStore.dirty||projectStore.loading||projectBusyCount>0){host.replaceChildren(h('p',{role:'status'},w('Guarda desde la barra del proyecto y espera a que termine antes de abrir las tareas. Esta vista no guarda el borrador.','Save from the project toolbar and wait for completion before opening tasks. This view does not save the draft.', "Salve pela barra de ferramentas do projeto e aguarde a conclusão antes de abrir as tarefas. Esta visualização não salva o rascunho.")),refresh);return;}
    const state={host,slug:S.slug,data:S.data,json:JSON.stringify(S.data),etag:projectStore.etag,revision:projectStore.revision,lang:S.uiLang,
      selected:new Set(['id','finding_uid','due_date','status']),token:null,count:0,loading:false,sequence:generation};
    state.status=h('p',{role:'status','aria-live':'polite','data-remediation-status':''});
    state.preview=h('div',{'data-remediation-preview':''});
    state.ack=h('input',{type:'checkbox','data-remediation-private':''});
    state.ack.addEventListener('change',()=>{state.sequence++;clearPreview(state);});
    const options=h('fieldset',{class:'rt-fields'},h('legend',{},w('Campos que incluirás en la descarga','Fields to include in the download', "Campos a incluir no download")));
    fields.forEach(([key,es,en,pt])=>{const required=key==='id'||key==='finding_uid';
      const input=h('input',{type:'checkbox',checked:state.selected.has(key)?'':null,disabled:required?'':null,'data-remediation-field':key});
      input.addEventListener('change',()=>{if(input.checked)state.selected.add(key);else state.selected.delete(key);state.sequence++;clearPreview(state);});
      options.append(h('label',{class:'rt-check'},input,w(es,en,pt)+(required?w(' (obligatorio)',' (required)', " (obrigatório)"):'')));
    });
    state.previewButton=button(w('Previsualizar tareas','Preview tasks', "Visualizar tarefas"),()=>preview(state),{'data-remediation-preview-button':''});
    host.replaceChildren(h('section',{class:'rt-view','data-remediation-view':''},
      h('p',{},w('Prepara tareas desde la versión guardada, sin cambiar el informe. Los datos se descargan localmente; no se envían a un gestor externo.','Prepare tasks from the saved version without changing the report. Downloads stay local; nothing is sent to an external tracker.', "Prepare tarefas a partir da versão salva sem alterar o relatório. Os downloads permanecem locais; nada é enviado a um gerenciador externo.")),
      refresh,options,h('label',{class:'rt-check rt-private'},state.ack,w('He revisado que los campos seleccionados pueden incluir información interna, activos y responsables.','I have reviewed that selected fields may include internal information, assets and owners.', "Revisei que os campos selecionados podem incluir informações internas, ativos e responsáveis.")),
      h('p',{class:'wf-hint'},w('Las acciones usan la remediación individual; si está vacía, usan la acción del grupo. El criterio de cierre se registra en Seguimiento y vínculos; nunca se inventa. Las fichas muestran Markdown como texto.','Actions use individual remediation; when empty, they use the group action. Closure criteria are recorded in Tracking and links and are never invented. Cards display Markdown as text.', "As ações usam a correção individual; quando vazia, usam a ação do grupo. Os critérios de encerramento são registrados em Acompanhamento e vínculos e nunca são inventados. Os cartões exibem Markdown como texto.")),
      h('div',{class:'rt-actions'},state.previewButton,
        button(w('Descargar CSV','Download CSV', "Baixar CSV"),()=>download(state,'csv'),{'data-remediation-download':'csv',disabled:''}),
        button(w('Descargar fichas HTML (ZIP)','Download HTML task cards (ZIP)', "Baixar cartões de tarefas em HTML (ZIP)"),()=>download(state,'cards'),{'data-remediation-download':'cards',disabled:''})),
      state.status,state.preview,returnView(state)));
    mounted=state;clearPreview(state);
  }
  return {render,invalidate};
})();
