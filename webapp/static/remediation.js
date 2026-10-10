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
  function invalidate(){if(mounted&&!same(mounted)){mounted.token=null;mounted.host.querySelector('[data-remediation-preview]')?.replaceChildren();
    mounted.status.textContent=w('El proyecto cambió. Guarda desde la barra y actualiza esta vista.','The project changed. Save from the toolbar and refresh this view.');
    mounted.host.querySelectorAll('[data-remediation-download],[data-remediation-preview-button]').forEach(button=>button.disabled=true);}}
  function guard(state){if(!same(state)){invalidate();return false;}return mounted===state&&state.host.isConnected;}
  function button(label,run,attributes={}){const node=h('button',{type:'button',class:'btn sm',...attributes},label);
    node.addEventListener('click',async()=>{node.disabled=true;try{await run();}catch(error){if(node.isConnected)toast(error.message,'err');}
      finally{if(node.isConnected){node.disabled=false;if(mounted)updateButtons(mounted);}}});return node;}
  function selection(state){return fields.map(row=>row[0]).filter(key=>state.selected.has(key));}
  function sensitive(state){return [...state.selected].some(key=>privateFields.has(key));}
  function updateButtons(state){const allowed=guard(state)&&(!sensitive(state)||state.ack.checked);
    state.previewButton.disabled=!allowed||state.loading;
    state.host.querySelectorAll('[data-remediation-download]').forEach(node=>node.disabled=!allowed||state.loading||!state.token||!state.count);}
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
      state.status,state.preview));
    mounted=state;clearPreview(state);
  }
  return {render,invalidate};
})();
