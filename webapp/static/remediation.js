/* Local task deliveries. Preview and download use the same immutable saved revision. */
const RemediationUI = (() => {
  'use strict';
  const w=(es,en)=>S.uiLang==='en'?en:es;
  const fields=[
    ['id','ID del hallazgo','Finding ID'],['finding_uid','Referencia permanente','Permanent reference'],
    ['title','Título','Title'],['assets','Activos afectados','Affected assets'],
    ['action','Acción de remediación','Remediation action'],['owner','Responsable','Owner'],
    ['due_date','Plazo','Due date'],['closure_criteria','Criterio de cierre','Closure criteria'],
    ['status','Estado registrado','Recorded status'],['group_uid','Referencia del grupo','Group reference'],
    ['group_name','Grupo por causa raíz','Root-cause group'],['shared_action','Acción común del grupo','Shared group action']
  ];
  const privateFields=new Set(['title','assets','action','owner','closure_criteria','group_name','shared_action']);
  let mounted=null,generation=0;
  const tag=etag=>String(etag||'').replace(/^"|"$/g,'');
  function same(state){return S.slug===state.slug&&S.data===state.data&&JSON.stringify(S.data)===state.json&&
    projectStore.etag===state.etag&&projectStore.revision===state.revision&&S.uiLang===state.lang&&
    !projectStore.dirty&&!projectStore.loading&&projectBusyCount===0;}
  function invalidate(){if(mounted&&!same(mounted)){mounted.token=null;invalidateReturn(mounted);mounted.host.querySelector('[data-remediation-preview]')?.replaceChildren();
    mounted.status.textContent=w('El proyecto cambió. Guarda desde la barra y actualiza esta vista.','The project changed. Save from the toolbar and refresh this view.');
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
  function clearPreview(state){state.token=null;state.count=0;state.preview.replaceChildren();state.status.textContent=w('Previsualiza los campos seleccionados antes de descargar.','Preview selected fields before downloading.');updateButtons(state);}
  function body(state){return {fields:selection(state),lang:state.lang,ack_private:state.ack.checked};}
  async function request(state,operation,options){return requireOk(await appFetch('/api/projects/'+encodeURIComponent(state.slug)+'/remediation-tasks/'+operation,
    {method:'POST',headers:{'Content-Type':'application/json','If-Match':state.etag},body:JSON.stringify(options)}));}
  async function preview(state){
    if(!guard(state))return;state.loading=true;updateButtons(state);
    const sequence=++state.sequence,options=body(state),signature=JSON.stringify(options);
    state.token=null;state.preview.replaceChildren();state.status.textContent=w('Leyendo la revisión guardada…','Reading the saved revision…');
    try{const response=await request(state,'preview',options),result=await response.json();
      if(!guard(state)||sequence!==state.sequence||JSON.stringify(body(state))!==signature)return;
      if(response.headers.get('ETag')!==state.etag||result.revision!==tag(state.etag)||result.project_slug!==state.slug||
        result.version!==1||result.source!=='saved_project'||!Array.isArray(result.rows)||JSON.stringify(result.fields)!==JSON.stringify(options.fields))
        throw Error(w('La revisión recibida no coincide; actualiza esta vista.','The returned revision differs; refresh this view.'));
      state.token=result.preview_token;state.count=result.rows.length;
      state.status.textContent=result.rows.length+' '+w('tareas. Revisa el contenido antes de descargar.','tasks. Review the contents before downloading.');
      if(!result.rows.length){state.preview.append(h('p',{},w('Añade un hallazgo para preparar tareas.','Add a finding to prepare tasks.')));return;}
      result.rows.forEach((row,index)=>{
        const values=h('dl',{});result.fields.forEach(key=>values.append(h('dt',{},result.labels[key]),h('dd',{},row[key]||w('Sin registrar','Not recorded'))));
        state.preview.append(h('details',{class:'rt-card',open:index===0?'':null},h('summary',{},w('Tarea ','Task ')+(index+1)+' · '+row.id),values));
      });
    }catch(error){if(guard(state)){state.token=null;state.status.textContent=error.message;}}
    finally{if(mounted===state){state.loading=false;updateButtons(state);}}
  }
  async function download(state,format){
    if(!guard(state)||!state.token)return;state.loading=true;updateButtons(state);
    const token=state.token,options={...body(state),format,preview_token:token};
    try{const response=await request(state,'export',options),blob=await response.blob();
      if(!guard(state)||state.token!==token)return;
      if(response.headers.get('ETag')!==state.etag)throw Error(w('La descarga no corresponde a esta revisión.','The download does not match this revision.'));
      const url=URL.createObjectURL(blob),link=h('a',{href:url,download:'remediation-tasks.'+(format==='csv'?'csv':'zip')});
      link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      state.status.textContent=w('Descarga preparada con los campos previsualizados.','Download prepared with the previewed fields.');
    }catch(error){if(guard(state)){state.token=null;state.status.textContent=error.message;}}
    finally{if(mounted===state){state.loading=false;updateButtons(state);}}
  }
  function invalidateReturn(state){
    if(!state.returning)return;
    state.returning.token=null;state.returning.selected.clear();state.returning.changes.replaceChildren();
    state.returning.apply.disabled=true;state.returning.reviewed.checked=false;
  }
  function updateReturnButtons(state){
    const r=state.returning;if(!r)return;
    const ready=same(state)&&!state.loading&&mounted===state&&state.host.isConnected;
    r.issue.disabled=!ready||!r.assigned.size||!r.private.checked||!r.retention.checked;
    r.preview.disabled=!ready||!r.text;
    r.apply.disabled=!ready||!r.token||!r.selected.size||!r.reviewed.checked;
    r.file.disabled=!ready;
  }
  async function acceptReturnMutation(state,response,data){
    if(S.slug!==state.slug||S.data!==state.data||projectStore.etag!==state.etag||projectStore.dirty)
      throw Error(w('El proyecto cambió. Recarga el proyecto para ver el resultado guardado.','The project changed. Reload it to see the saved result.'));
    S.data=data;projectStore.data=data;projectStore.base=JSON.parse(JSON.stringify(data));
    projectStore.etag=response.headers.get('ETag');projectStore.lastSavedAt=new Date();UndoUI.clear();ProgressUI.saveState('saved');
  }
  async function issueReturn(state){
    if(!guard(state))return;
    const r=state.returning,options={finding_uids:[...r.assigned],ack_private:r.private.checked,ack_retention:r.retention.checked};
    state.loading=true;updateButtons(state);busyProject(true);
    try{
      const response=await request(state,'return-template',options),blob=await response.blob();
      const current=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(state.slug)));
      if(current.headers.get('ETag')!==response.headers.get('ETag'))throw Error(w('El proyecto cambió. Recarga antes de emitir otra plantilla.','The project changed. Reload before issuing another template.'));
      await acceptReturnMutation(state,current,await current.json());
      const url=URL.createObjectURL(blob);h('a',{href:url,download:'remediation-return.csv'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      toast(w('Plantilla emitida y asignación guardada.','Template issued and assignment saved.'),'ok');
    }finally{state.loading=false;busyProject(false);if(S.slug===state.slug){renderSidebar();select('workflow','remediation_tasks');}}
  }
  async function previewReturn(state){
    if(!guard(state))return;
    const r=state.returning,text=r.text,sequence=++r.sequence;
    invalidateReturn(state);state.loading=true;updateButtons(state);
    r.status.textContent=w('Comparando con el proyecto guardado…','Comparing against the saved project…');
    try{
      const response=await request(state,'return-preview',{text}),result=await response.json();
      if(!guard(state)||r.text!==text||r.sequence!==sequence)return;
      if(response.headers.get('ETag')!==state.etag||result.revision!==tag(state.etag)||result.project_slug!==state.slug||result.version!==1||!Array.isArray(result.changes))
        throw Error(w('La revisión recibida no coincide.','The returned revision does not match.'));
      r.token=result.preview_token;
      r.status.textContent=result.changes.length+' '+w('cambios propuestos. Selecciona individualmente los que aceptas.','proposed changes. Select individually those you accept.');
      const labels={owner:w('Responsable','Owner'),due_date:w('Plazo','Due date'),reported_remediation:w('Corrección comunicada (sin verificar)','Reported remediation (unverified)')};
      result.changes.forEach(change=>{
        const input=h('input',{type:'checkbox','data-return-change':change.key});
        input.addEventListener('change',()=>{if(input.checked)r.selected.add(change.key);else r.selected.delete(change.key);r.reviewed.checked=false;updateReturnButtons(state);});
        const values=h('dl',{},h('dt',{},w('Valor actual','Current value')),h('dd',{},change.before||w('Vacío','Empty')),
          h('dt',{},w('Propuesta recibida','Received proposal')),h('dd',{},change.after||w('Vacío (se eliminará este dato)','Empty (this value will be cleared)')));
        const card=h('section',{class:'rt-card rt-return-change'},h('label',{class:'rt-check'},input,change.finding_id+' · '+labels[change.field]),values);
        if(change.changed_since_issue){card.append(h('p',{class:'wf-hint'},w('Este campo cambió desde que se emitió la plantilla. Compara también su valor de origen antes de aceptar.','This field changed after the template was issued. Also compare its original value before accepting.')),
          h('dl',{},h('dt',{},w('Al emitir la plantilla','When issued')),h('dd',{},change.issued||w('Vacío','Empty'))));}
        r.changes.append(card);
      });
    }catch(error){if(guard(state)){invalidateReturn(state);r.status.textContent=error.message;}}
    finally{if(mounted===state){state.loading=false;updateButtons(state);}}
  }
  async function applyReturn(state){
    if(!guard(state))return;
    const r=state.returning,options={text:r.text,preview_token:r.token,selected:[...r.selected],ack_reviewed:r.reviewed.checked};
    state.loading=true;updateButtons(state);busyProject(true);
    try{
      const response=await request(state,'return-apply',options),result=await response.json();
      await acceptReturnMutation(state,response,result.data);
      toast(result.applied+' '+w('cambios guardados. La verificación técnica y los retests se conservan.','changes saved. Technical verification and retests are preserved.'),'ok');
    }finally{state.loading=false;busyProject(false);if(S.slug===state.slug){renderSidebar();select('workflow','remediation_tasks');}}
  }
  function returnView(state){
    const r=state.returning={assigned:new Set(),selected:new Set(),text:'',token:null,sequence:0};
    r.changes=h('div',{'data-return-changes':''});
    r.status=h('p',{role:'status','aria-live':'polite','data-return-status':''});
    r.private=h('input',{type:'checkbox','data-return-private':''});r.retention=h('input',{type:'checkbox','data-return-retention':''});
    r.reviewed=h('input',{type:'checkbox','data-return-reviewed':''});
    [r.private,r.retention,r.reviewed].forEach(input=>input.addEventListener('change',()=>updateReturnButtons(state)));
    const assigned=h('fieldset',{class:'rt-fields'},h('legend',{},w('Hallazgos que asignarás','Findings to assign')));
    (S.data.findings||[]).forEach(finding=>{
      const valid=!!finding.owner?.trim(),input=h('input',{type:'checkbox','data-return-finding':finding.uid,disabled:valid?null:''});
      input.addEventListener('change',()=>{if(input.checked)r.assigned.add(finding.uid);else r.assigned.delete(finding.uid);updateReturnButtons(state);});
      assigned.append(h('label',{class:'rt-check'},input,(finding.id||'')+' · '+(finding.owner||w('Asigna un responsable en el hallazgo','Assign an owner in the finding'))));
    });
    if(!(S.data.findings||[]).length)assigned.append(h('p',{},w('Añade hallazgos y asigna sus responsables primero.','Add findings and assign their owners first.')));
    r.issue=button(w('Emitir plantilla de retorno CSV','Issue return CSV template'),()=>issueReturn(state),{'data-return-issue':'',disabled:''});
    r.preview=button(w('Comparar retorno','Compare return'),()=>previewReturn(state),{'data-return-preview':'',disabled:''});
    r.apply=button(w('Guardar cambios seleccionados','Save selected changes'),()=>applyReturn(state),{'data-return-apply':'',disabled:''});
    r.file=h('input',{type:'file',accept:'.csv,text/csv','data-return-file':''});
    r.file.addEventListener('change',async()=>{
      const sequence=++r.sequence;invalidateReturn(state);r.text='';r.status.textContent='';updateReturnButtons(state);
      try{const file=r.file.files[0];if(!file)return;
        if(file.size>2*1024*1024)throw Error(w('El CSV supera 2 MiB.','CSV exceeds 2 MiB.'));
        const text=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(await file.arrayBuffer());
        if(!guard(state)||r.sequence!==sequence)return;r.text=text;r.status.textContent=w('Archivo leído. Compara antes de guardar.','File read. Compare before saving.');
      }catch(error){if(guard(state))r.status.textContent=w('No se pudo leer el CSV UTF-8: ','Could not read the UTF-8 CSV: ')+error.message;}
      finally{if(mounted===state)updateReturnButtons(state);}
    });
    return h('section',{class:'rt-return','data-remediation-return':''},h('h3',{},w('Recibir avances del responsable','Receive owner updates')),
      h('p',{},w('Emite una plantilla específica y entrega aparte las tareas informativas si se necesita contexto. Al recibirla, podrás aceptar cada cambio de responsable, plazo o corrección comunicada. Esta importación nunca modifica el estado, la verificación técnica ni los retests.','Issue a specific template and provide the informational tasks separately when context is needed. On return, accept each owner, due date or reported remediation change. This import never modifies status, technical verification or retests.')),
      h('details',{},h('summary',{},w('1. Emitir una plantilla','1. Issue a template')),assigned,
        h('label',{class:'rt-check rt-private'},r.private,w('Revisé los responsables y las comunicaciones que saldrán del proyecto.','I reviewed the owners and communications that will leave the project.')),
        h('label',{class:'rt-check rt-private'},r.retention,w('Entiendo que emitir guarda una asignación. Se conservan hasta 20 lotes o 4 MiB; los más antiguos dejan de admitirse.','I understand issuance saves an assignment. Up to 20 batches or 4 MiB are retained; older batches stop being accepted.')),
        h('p',{class:'wf-hint'},w('Edita solo owner, due_date y reported_remediation. Conserva el apóstrofo inicial en owner y reported_remediation, incluso si estaban vacíos. Fechas: AAAA-MM-DD. Conserva las referencias y guarda como CSV UTF-8 con comas. Puedes devolver solo algunas filas.','Edit only owner, due_date and reported_remediation. Preserve the initial apostrophe in owner and reported_remediation, even when empty. Dates: YYYY-MM-DD. Preserve references and save as comma-separated UTF-8 CSV. You may return only some rows.')),
        h('div',{class:'rt-actions'},r.issue)),
      h('h4',{},w('2. Revisar el CSV recibido','2. Review the returned CSV')),
      h('label',{},w('Plantilla de retorno CSV (hasta 2 MiB)','Return CSV template (up to 2 MiB)'),r.file),h('div',{class:'rt-actions'},r.preview),r.status,r.changes,
      h('label',{class:'rt-check rt-private'},r.reviewed,w('Revisé cada cambio seleccionado y entiendo que una corrección comunicada no demuestra que esté corregido.','I reviewed each selected change and understand that a reported remediation does not prove it is fixed.')),
      h('div',{class:'rt-actions'},r.apply));
  }
  function render(host){
    ++generation;mounted=null;
    const refresh=button(w('Actualizar desde el proyecto guardado','Refresh from saved project'),()=>render(host),{'data-remediation-refresh':''});
    if(!S.slug||!S.data){host.replaceChildren(h('p',{},w('Abre un proyecto para preparar tareas.','Open a project to prepare tasks.')));return;}
    if(projectStore.dirty||projectStore.loading||projectBusyCount>0){host.replaceChildren(h('p',{role:'status'},w('Guarda desde la barra del proyecto y espera a que termine antes de abrir las tareas. Esta vista no guarda el borrador.','Save from the project toolbar and wait for completion before opening tasks. This view does not save the draft.')),refresh);return;}
    const state={host,slug:S.slug,data:S.data,json:JSON.stringify(S.data),etag:projectStore.etag,revision:projectStore.revision,lang:S.uiLang,
      selected:new Set(['id','finding_uid','due_date','status']),token:null,count:0,loading:false,sequence:generation};
    state.status=h('p',{role:'status','aria-live':'polite','data-remediation-status':''});
    state.preview=h('div',{'data-remediation-preview':''});
    state.ack=h('input',{type:'checkbox','data-remediation-private':''});
    state.ack.addEventListener('change',()=>{state.sequence++;clearPreview(state);});
    const options=h('fieldset',{class:'rt-fields'},h('legend',{},w('Campos que incluirás en la descarga','Fields to include in the download')));
    fields.forEach(([key,es,en])=>{const required=key==='id'||key==='finding_uid';
      const input=h('input',{type:'checkbox',checked:state.selected.has(key)?'':null,disabled:required?'':null,'data-remediation-field':key});
      input.addEventListener('change',()=>{if(input.checked)state.selected.add(key);else state.selected.delete(key);state.sequence++;clearPreview(state);});
      options.append(h('label',{class:'rt-check'},input,w(es,en)+(required?w(' (obligatorio)',' (required)'):'')));
    });
    state.previewButton=button(w('Previsualizar tareas','Preview tasks'),()=>preview(state),{'data-remediation-preview-button':''});
    host.replaceChildren(h('section',{class:'rt-view','data-remediation-view':''},
      h('p',{},w('Prepara tareas desde la versión guardada, sin cambiar el informe. Los datos se descargan localmente; no se envían a un gestor externo.','Prepare tasks from the saved version without changing the report. Downloads stay local; nothing is sent to an external tracker.')),
      refresh,options,h('label',{class:'rt-check rt-private'},state.ack,w('He revisado que los campos seleccionados pueden incluir información interna, activos y responsables.','I have reviewed that selected fields may include internal information, assets and owners.')),
      h('p',{class:'wf-hint'},w('Las acciones usan la remediación individual; si está vacía, usan la acción del grupo. El criterio de cierre se registra en Seguimiento y vínculos; nunca se inventa. Las fichas muestran Markdown como texto.','Actions use individual remediation; when empty, they use the group action. Closure criteria are recorded in Tracking and links and are never invented. Cards display Markdown as text.')),
      h('div',{class:'rt-actions'},state.previewButton,
        button(w('Descargar CSV','Download CSV'),()=>download(state,'csv'),{'data-remediation-download':'csv',disabled:''}),
        button(w('Descargar fichas HTML (ZIP)','Download HTML task cards (ZIP)'),()=>download(state,'cards'),{'data-remediation-download':'cards',disabled:''})),
      state.status,state.preview,returnView(state)));
    mounted=state;clearPreview(state);
  }
  return {render,invalidate};
})();
