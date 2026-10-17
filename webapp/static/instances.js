/* Affected occurrences retain independent proof, ownership and retest history. */
const InstancesUI=(()=>{
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const statuses={open:['Abierto','Open','Aberto'],in_progress:['En corrección','In progress','Em correção'],reported_fixed:['Corrección comunicada','Reported fixed','Correção comunicada'],verified_fixed:['Corregido y verificado','Verified fixed','Corrigido e verificado'],accepted:['Riesgo aceptado','Risk accepted','Risco aceito'],not_verified:['No verificable','Not verifiable','Não verificável'],blocked:['Verificación bloqueada','Verification blocked','Verificação bloqueada']};
  const results={open:['Sigue abierto','Still open','Continua aberto'],fixed:['Corregido','Fixed','Corrigido'],partial:['Corrección parcial','Partially fixed','Correção parcial'],not_verified:['No verificable','Not verifiable','Não verificável']};
  const labels={asset_uid:['Activo','Asset','Ativo'],endpoint:['Endpoint o destino','Endpoint or target','Endpoint ou destino'],parameter:['Parámetro','Parameter','Parâmetro'],identity:['Identidad o rol','Identity or role','Identidade ou função'],environment:['Entorno','Environment','Ambiente'],owner:['Responsable','Owner','Responsável'],due_date:['Fecha objetivo','Due date','Prazo'],status:['Estado','Status','Status'],notes_md:['Notas y limitaciones','Notes and limitations','Notas e limitações'],tested_on:['Fecha de retest','Retest date','Data do reteste'],assessor:['Evaluador','Assessor','Avaliador'],result:['Resultado','Result','Resultado']};
  const limits={endpoint:2048,parameter:300,identity:300,environment:300,owner:200,notes_md:16000,assessor:200};
  const metadata=['asset_uid','endpoint','parameter','identity','environment','owner','due_date','status','notes_md'];
  const retestFields=['tested_on','assessor','result','notes_md'];
  const label=key=>statuses[key]?w(...statuses[key]):key;
  function draft(input){
    if(!input||input.schema!==1||!['create','edit','retest'].includes(input.mode)||typeof input.finding_uid!=='string'||typeof input.instance_uid!=='string'||!input.values||typeof input.values!=='object'||Array.isArray(input.values))throw Error(w('Borrador de instancia inválido.','Invalid instance draft.','Rascunho de instância inválido.'));
    const fields=input.mode==='retest'?retestFields:metadata,values={};
    if(Object.keys(input.values).some(key=>!fields.includes(key)&&key!=='evidence_uids'))throw Error(w('Borrador de instancia inválido.','Invalid instance draft.','Rascunho de instância inválido.'));
    for(const key of fields){const value=input.values[key]??'';if(typeof value!=='string'||value.length>(limits[key]||100))throw Error(w('Borrador de instancia inválido.','Invalid instance draft.','Rascunho de instância inválido.'));values[key]=value;}
    const refs=input.values.evidence_uids||[];if(!Array.isArray(refs)||refs.length>500||refs.some(uid=>typeof uid!=='string')||new Set(refs).size!==refs.length)throw Error(w('Referencias de evidencia inválidas.','Invalid evidence references.','Referências de evidência inválidas.'));
    values.evidence_uids=[...refs];return {...input,values};
  }
  function missingReference(row){
    const value=draft(row.data),finding=(S.data?.findings||[]).find(f=>f.uid===value.finding_uid);
    return !finding||(value.mode!=='create'&&!(finding.instances||[]).some(i=>i.uid===value.instance_uid))||value.values.asset_uid&&!(S.data.assets||[]).some(a=>a.uid===value.values.asset_uid)||(value.values.evidence_uids||[]).some(uid=>!(S.data.evidence||[]).some(e=>e.uid===uid));
  }
  function path(findingUid,instanceUid=''){return '/api/projects/'+encodeURIComponent(S.slug)+'/findings/'+encodeURIComponent(findingUid)+'/instances'+(instanceUid?'/'+encodeURIComponent(instanceUid):'');}
  async function saveRequest(endpoint,method,values,context){
    if(S.slug!==context.slug||S.workspace_id!==context.workspace)throw Error(w('El proyecto cambió. Vuelve a abrir la instancia.','The project changed. Reopen the instance.','O projeto mudou. Reabra a instância.'));
    if(!await doSave())throw Error(w('Guarda primero el informe.','Save the report first.','Salve o relatório primeiro.'));
    if(S.slug!==context.slug||S.workspace_id!==context.workspace)throw Error(w('El proyecto cambió.','The project changed.','O projeto mudou.'));
    const state={revision:projectStore.revision,etag:projectStore.etag,data:S.data,json:JSON.stringify(S.data)};
    const response=await requireOk(await appFetch(endpoint,{method,headers:{'Content-Type':'application/json','If-Match':state.etag},body:JSON.stringify(values)}));
    const body=await response.json();
    if(S.slug!==context.slug||S.workspace_id!==context.workspace||state.revision!==projectStore.revision||state.data!==S.data||state.json!==JSON.stringify(S.data)||projectStore.dirty)throw Error(w('El servidor guardó la instancia, pero el borrador cambió. Se conserva tu borrador; revisa el conflicto antes de recargar.','The server saved the instance, but the draft changed. Your draft is retained; review the conflict before reloading.','O servidor salvou a instância, mas o rascunho mudou. Seu rascunho foi mantido; revise o conflito antes de recarregar.'));
    await adoptSavedProject(body.data,response.headers.get('ETag'));renderSidebar();renderMain();if(S.previewMode==='live')refreshLivePreview();return body;
  }
  function open(finding,instance=null,mode='create',recovered=null){
    if(!S.slug||projectBusyCount||projectStore.loading)return;
    const key='instance:'+finding.uid+':'+(instance?.uid||'new')+':'+mode;
    if(document.querySelector('[data-instance-dialog]')){document.querySelector('[data-instance-dialog] input')?.focus();return;}
    const stored=PendingUI.active.get(S.slug+'|'+key),initial=recovered?draft(recovered.data):stored?draft(stored.read().data):null;
    if(recovered&&(recovered.slug!==S.slug||recovered.workspace_id!==BrowserWorkspace.current())||initial&&missingReference({data:initial}))throw Error(w('Este borrador no corresponde al proyecto actual.','This draft does not match the current project.','Este rascunho não corresponde ao projeto atual.'));
    const fields=mode==='retest'?retestFields:metadata;
    const values=initial?.values||Object.fromEntries(fields.map(key=>[key,mode==='retest'?({tested_on:new Date().toISOString().slice(0,10),assessor:S.data.meta?.assessor||'',result:'open'}[key]||''):instance?.[key]||(key==='status'?'open':'')]));
    values.evidence_uids=initial?[...initial.values.evidence_uids]:mode==='retest'?[]:[...(instance?.evidence_uids||[])];
    const context={slug:S.slug,workspace:S.workspace_id},trigger=document.activeElement;
    let pending=null,edited=!!initial,busy=false;
    const title=mode==='retest'?w('Retest de instancia','Instance retest','Reteste da instância'):mode==='edit'?w('Editar instancia','Edit instance','Editar instância'):w('Añadir instancia afectada','Add affected instance','Adicionar instância afetada');
    const dialog=h('dialog',{class:'experience-dialog instance-dialog','aria-label':title,'data-instance-dialog':mode});
    const form=h('fieldset',{class:'instance-form'}),error=h('p',{role:'alert'}),close=h('button',{type:'button',class:'btn',onclick:()=>{if(!busy)dialog.close();}},w('Cerrar','Close','Fechar'));
    const changed=()=>{edited=true;error.textContent='';if(pending)PendingUI.changed(pending);};
    for(const key of fields){
      let input;
      if(key==='asset_uid')input=h('select',{},h('option',{value:''},w('Sin activo; indicar destino','No asset; specify target','Sem ativo; informe o destino')),...(S.data.assets||[]).map(a=>h('option',{value:a.uid},a.name||a.target||a.uid)));
      else if(key==='status'||key==='result')input=h('select',{},...Object.entries(key==='status'?statuses:results).filter(([value])=>key!=='status'||value!=='verified_fixed'||values.status===value).map(([value,text])=>h('option',{value},w(...text))));
      else if(key==='notes_md')input=h('textarea',{rows:5,maxlength:16000});
      else input=h('input',{type:key.endsWith('_date')||key==='tested_on'?'date':'text',maxlength:limits[key]||100});
      input.value=values[key]||'';input.dataset.instanceField=key;input.addEventListener('input',()=>{values[key]=input.value;changed();});input.addEventListener('change',()=>{values[key]=input.value;changed();});
      form.append(h('label',{class:key==='notes_md'?'instance-form-wide':''},h('span',{},key==='notes_md'&&mode==='retest'?w('Procedimiento y resultado observado','Procedure and observed result','Procedimento e resultado observado'):w(...labels[key])),input));
    }
    const evidence=h('fieldset',{class:'instance-form-wide instance-evidence'},h('legend',{},w('Evidencia vinculada','Linked evidence','Evidência vinculada')));
    for(const item of S.data.evidence||[]){const check=h('input',{type:'checkbox',checked:values.evidence_uids.includes(item.uid)?'':null,onchange:()=>{values.evidence_uids=check.checked?[...values.evidence_uids,item.uid]:values.evidence_uids.filter(uid=>uid!==item.uid);changed();}});evidence.append(h('label',{class:'wf-check'},check,item.title||item.caption||item.uid));}
    if(!(S.data.evidence||[]).length)evidence.append(h('p',{},w('Registra evidencia en el proyecto para vincularla aquí.','Register project evidence to link it here.','Cadastre evidência no projeto para vinculá-la aqui.')));
    form.append(evidence);
    pending=PendingUI.track(key,title,()=>({data:{schema:1,mode,finding_uid:finding.uid,instance_uid:instance?.uid||'',values:structuredClone(values)}}),{origin:recovered});
    if(recovered)PendingUI.changed(pending);
    const protect=event=>{if(busy||edited&&(!pending||pending.error||pending.persisted!==pending.revision)){event.preventDefault();event.returnValue='';}};window.addEventListener('beforeunload',protect);
    dialog.addEventListener('cancel',event=>{if(busy)event.preventDefault();});
    dialog.addEventListener('close',()=>{window.removeEventListener('beforeunload',protect);dialog.remove();if(trigger?.isConnected)trigger.focus({preventScroll:true});});
    const discard=h('button',{type:'button',class:'btn',onclick:async()=>{if(busy)return;try{if(await PendingUI.clear(pending)){edited=false;dialog.close();}}catch(e){error.textContent=e.message;}}},w('Descartar formulario','Discard form','Descartar formulário'));
    const save=h('button',{type:'button',class:'btn primary','data-instance-save':'',onclick:async()=>{
      if(busy)return;busy=true;form.disabled=true;save.disabled=true;close.disabled=true;discard.disabled=true;error.textContent='';busyProject(true);
      try{
        const revision=pending.revision;
        if(mode!=='retest'&&!values.asset_uid&&!values.endpoint.trim())throw Error(w('Indica un activo o destino.','Specify an asset or target.','Informe um ativo ou destino.'));
        await saveRequest(path(finding.uid,mode==='create'?'':instance.uid)+(mode==='retest'?'/retests':''),mode==='edit'?'PUT':'POST',values,context);
        const cleanup=await PendingUI.committed(pending,revision);if(cleanup.finished){edited=false;dialog.close();}
        if(cleanup.warning)toast(w('Guardado; revisa la copia local pendiente.','Saved; review the pending local copy.','Salvo; revise a cópia local pendente.'),'err');
        else toast(w('Instancia guardada.','Instance saved.','Instância salva.'),'ok');
      }catch(e){error.textContent=e.message;}finally{busy=false;form.disabled=false;save.disabled=false;close.disabled=false;discard.disabled=false;busyProject(false);}
    }},mode==='retest'?w('Guardar retest','Save retest','Salvar reteste'):w('Guardar instancia','Save instance','Salvar instância'));
    dialog.append(h('div',{class:'experience-heading'},h('h2',{},title),close),h('div',{class:'experience-body'},h('p',{},w('Cada instancia conserva su propio estado y retests. Cerrar conserva el formulario pendiente.','Each instance retains its own status and retests. Closing retains the pending form.','Cada instância mantém seu próprio status e retestes. Fechar mantém o formulário pendente.')),PendingUI.status(pending),form,error,h('div',{class:'studio-actions'},save,discard)));document.body.append(dialog);dialog.showModal();form.querySelector('input,select,textarea')?.focus();
  }
  function render(host,finding){
    const instances=finding.instances||[],assets=new Map((S.data.assets||[]).map(a=>[a.uid,a])),counts={};let page=0;
    for(const item of instances)counts[item.status||'open']=(counts[item.status||'open']||0)+1;
    const box=h('section',{class:'instance-workspace','data-instances-finding':finding.uid},h('h3',{},w('Instancias afectadas','Affected instances','Instâncias afetadas')),h('p',{},w('Separa los destinos afectados para verificar cada corrección de forma independiente.','Separate affected targets to verify each remediation independently.','Separe os destinos afetados para verificar cada correção de forma independente.')));
    const summary=h('div',{class:'instance-summary',role:'status'},h('strong',{},instances.length+' '+w('instancias','instances','instâncias')),...Object.entries(counts).map(([key,count])=>h('span',{class:'instance-count'},label(key)+': '+count)));
    const list=h('div',{class:'instance-list'}),pager=h('div',{}),search=h('input',{type:'search','aria-label':w('Buscar instancias','Search instances','Pesquisar instâncias'),'data-instance-search':'',placeholder:w('Destino, rol o responsable','Target, role or owner','Destino, função ou responsável')});
    function draw(){
      const query=search.value.toLocaleLowerCase().trim(),rows=instances.filter(i=>!query||[i.endpoint,i.parameter,i.identity,i.environment,i.owner,assets.get(i.asset_uid)?.name].join(' ').toLocaleLowerCase().includes(query));
      page=Math.min(page,Math.max(0,Math.ceil(rows.length/20)-1));list.replaceChildren();pager.replaceChildren();
      for(const instance of rows.slice(page*20,page*20+20)){
        const asset=assets.get(instance.asset_uid),title=instance.endpoint||asset?.name||asset?.target||instance.uid;
        const card=h('article',{class:'card instance-card','data-instance-uid':instance.uid},h('div',{class:'instance-card-heading'},h('h4',{},title),h('span',{class:'instance-status'},label(instance.status||'open'))),h('p',{class:'instance-context'},[asset?.name,instance.parameter,instance.identity,instance.environment].filter(Boolean).join(' · ')),h('p',{},[instance.owner,instance.due_date].filter(Boolean).join(' · ')));
        if(instance.notes_md)card.append(h('p',{class:'instance-notes'},instance.notes_md));
        const history=h('details',{},h('summary',{},(instance.retests||[]).length+' '+w('retests registrados','recorded retests','retestes registrados')));
        for(const record of [...(instance.retests||[])].sort((a,b)=>b.tested_on.localeCompare(a.tested_on)))history.append(h('article',{class:'instance-retest'},h('strong',{},record.tested_on+' · '+w(...(results[record.result]||results.not_verified))),h('p',{},record.assessor),h('p',{class:'instance-notes'},record.notes_md),h('p',{},(record.evidence_uids||[]).map(uid=>(S.data.evidence||[]).find(e=>e.uid===uid)?.title||uid).join(' · '))));
        const remove=h('button',{type:'button',class:'btn sm',onclick:async()=>{if(projectBusyCount||!confirm(w('¿Eliminar esta instancia y su historial de retests? La versión anterior se conserva en Versiones.','Remove this instance and its retest history? The previous version is retained in Versions.','Remover esta instância e seu histórico de retestes? A versão anterior é mantida em Versões.')))return;const context={slug:S.slug,workspace:S.workspace_id};busyProject(true);try{await saveRequest(path(finding.uid,instance.uid),'DELETE',{ack_delete:true},context);}catch(e){toast(e.message,'err');}finally{busyProject(false);}}},w('Eliminar','Remove','Remover'));
        card.append(h('p',{},(instance.evidence_uids||[]).length+' '+w('evidencias vinculadas','linked evidence items','evidências vinculadas')),history,h('div',{class:'studio-actions'},h('button',{type:'button',class:'btn sm',onclick:()=>open(finding,instance,'edit')},w('Editar instancia','Edit instance','Editar instância')),h('button',{type:'button',class:'btn sm',onclick:()=>open(finding,instance,'retest')},w('Registrar retest','Record retest','Registrar reteste')),remove));list.append(card);
      }
      if(!rows.length)list.append(h('p',{},instances.length?w('Sin coincidencias.','No matches.','Nenhum resultado.'):w('No se crean instancias automáticamente a partir de los activos vinculados.','Linked assets do not create instances automatically.','Ativos vinculados não criam instâncias automaticamente.')));
      if(rows.length>20)pager.append(workspacePageBar('instances-'+finding.uid,rows.length,page,20,next=>{page=next;draw();}));
    }
    search.addEventListener('input',()=>{page=0;draw();});box.append(summary,h('div',{class:'studio-actions'},h('button',{type:'button',class:'btn','data-instance-create':'',disabled:instances.length>=500?'':null,onclick:()=>open(finding)},w('Añadir instancia','Add instance','Adicionar instância')),search),list,pager);host.append(box);draw();
  }
  PendingUI.register('instance:',{validate:row=>{const value=draft(row.data);if(row.key!=='instance:'+value.finding_uid+':'+(value.instance_uid||'new')+':'+value.mode)throw Error(w('Borrador de instancia inválido.','Invalid instance draft.','Rascunho de instância inválido.'));},missingReference,restore:row=>{const value=draft(row.data),finding=S.data.findings.find(f=>f.uid===value.finding_uid);open(finding,(finding.instances||[]).find(i=>i.uid===value.instance_uid)||null,value.mode,row);}});
  return {render,open};
})();
