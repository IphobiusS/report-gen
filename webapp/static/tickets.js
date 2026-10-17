/* Explicit ticket exchange. Credentials live only in the visible form. */
const TicketsUI=(()=>{
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const names={owner:['Responsable','Owner','Responsável'],due_date:['Fecha objetivo','Due date','Prazo'],reported_remediation:['Avance comunicado','Reported progress','Avanço informado'],title:['Título','Title','Título'],description_md:['Descripción','Description','Descrição'],remediation_md:['Corrección','Remediation','Correção']};
  const changed=()=>Error(w('El proyecto o la selección cambió. Conservamos tus ediciones; vuelve a comparar.','The project or selection changed. Your edits are preserved; compare again.','O projeto ou a seleção mudou. Suas edições foram mantidas; compare novamente.'));
  const url=(slug,tail='')=>'/api/projects/'+encodeURIComponent(slug)+'/tickets'+tail;
  const snapshot=()=>({data:S.data,json:JSON.stringify(S.data),revision:projectStore.revision,etag:projectStore.etag});
  function same(before){return before.data===S.data&&before.revision===projectStore.revision&&before.etag===projectStore.etag&&before.json===JSON.stringify(S.data)&&!projectStore.dirty;}
  function current(context){if(!context.host.isConnected||context.slug!==S.slug||context.workspace!==S.workspace_id||projectStore.loading)throw changed();}
  async function call(context,tail,body,{method='POST',expected=null,guard=()=>true}={}){
    current(context);if(!guard()||expected&&!same(expected))throw changed();
    // Applying an old comparison never silently saves a newer draft first.
    if(!expected){if(!await doSave())throw Error(w('Guarda el proyecto antes de continuar.','Save the project before continuing.','Salve o projeto antes de continuar.'));current(context);if(!guard())throw changed();}
    const before=snapshot();if(projectStore.dirty)throw changed();
    const r=await requireOk(await appFetch(url(context.slug,tail),{method,headers:{'Content-Type':'application/json','If-Match':before.etag},...(method==='DELETE'?{}:{body:JSON.stringify(body)})}));
    const value=await r.json();current(context);if(!same(before)||!guard())throw changed();
    if(value.data){await adoptSavedProject(value.data,r.headers.get('ETag'));renderSidebar();}
    else if(r.headers.get('ETag')!==before.etag)throw changed();
    return {value,revision:before};
  }
  function input(label,type='text',value='',field=''){const node=h('input',{type,autocomplete:'off','data-ticket-field':field});node.value=value;return {node,label:h('label',{},label,node)};}
  function choice(label,value,changed,field=''){const node=h('input',{type:'checkbox','data-ticket-choice':field});node.checked=value;node.onchange=()=>changed(node.checked);return h('label',{class:'wf-check'},node,label);}
  async function render(host,slug=S.slug){
    host.classList.add('tickets-view');
    const context={host,slug,workspace:S.workspace_id},form=h('fieldset',{class:'tickets-form'}),error=h('p',{role:'alert','data-ticket-error':''});let requestBusy=false;
    function button(label,fn,primary=false,action=''){
      const b=h('button',{type:'button',class:'btn sm'+(primary?' primary':''),'data-ticket-action':action},label);
      b.onclick=async()=>{if(requestBusy)return;requestBusy=true;form.disabled=true;error.textContent='';busyProject(true);try{current(context);await fn();}catch(e){if(host.isConnected)error.textContent=e.message;else toast(e.message,'err');}finally{form.disabled=false;requestBusy=false;busyProject(false);}};return b;
    }
    host.append(h('p',{class:'wf-hint'},w('Vincula tickets existentes. Compara antes de enviar o aceptar cambios; el estado técnico y los retests se conservan.','Link existing tickets. Compare before sending or accepting changes; technical status and retests are preserved.','Vincule tickets existentes. Compare antes de enviar ou aceitar alterações; o estado técnico e os retestes são preservados.')),error,form);
    const finding=h('select',{'aria-label':w('Hallazgo','Finding','Achado'),'data-ticket-field':'finding_uid'},(S.data.findings||[]).map(f=>h('option',{value:f.uid},f.id+' · '+f.title)));
    const provider=h('select',{'aria-label':w('Proveedor','Provider','Provedor'),'data-ticket-field':'provider'},h('option',{value:'jira'},'Jira Cloud'),h('option',{value:'defectdojo'},'DefectDojo'));
    const base=input(w('Origen HTTPS público','Public HTTPS origin','Origem HTTPS pública'),'url','','base_url');base.node.placeholder='https://equipo.atlassian.net';
    const external=input(w('ID del ticket o hallazgo externo','External ticket or finding ID','ID do ticket ou achado externo'),'text','','external_id');external.node.placeholder='SEC-123 / 123';
    form.append(h('section',{class:'card wf-card'},h('h3',{},w('Vincular ticket','Link ticket','Vincular ticket')),h('div',{class:'wf-row'},h('label',{},w('Hallazgo','Finding','Achado'),finding),h('label',{},w('Proveedor','Provider','Provedor'),provider)),base.label,external.label,button(w('Guardar vínculo','Save link','Salvar vínculo'),async()=>{await call(context,'',{finding_uid:finding.value,provider:provider.value,base_url:base.node.value,external_id:external.node.value});renderMain();},false,'link')));
    for(const link of S.data.external_tickets||[]){
      const f=(S.data.findings||[]).find(row=>row.uid===link.finding_uid);
      const box=h('section',{class:'card wf-card','data-ticket-uid':link.uid},h('h3',{},(f?.id||'')+' · '+link.provider+' '+link.external_id),h('p',{},link.base_url));
      const user=input(w('Usuario Jira (correo)','Jira user (email)','Usuário Jira (e-mail)'),'text','','username');
      const token=input(w('Token de API (solo esta sesión)','API token (this session only)','Token de API (apenas nesta sessão)'),'password','','token');token.node.setAttribute('data-sensitive','true');token.node.autocomplete='new-password';
      if(link.provider==='jira')box.append(user.label);box.append(token.label,h('p',{class:'wf-hint'},w('El token no se guarda en el proyecto ni en el borrador.','The token is not stored in the project or draft.','O token não é salvo no projeto nem no rascunho.')));
      const result=h('div',{'aria-live':'polite','data-ticket-comparison':''});const credentials=()=>({username:user.node.value,token:token.node.value});let generation=0;
      function invalidate(){generation++;result.replaceChildren();}
      user.node.addEventListener('input',invalidate);token.node.addEventListener('input',invalidate);
      const selected=new Set(['title']);
      const fields=h('fieldset',{},h('legend',{},w('Campos para envío','Fields to send','Campos para envio')));
      for(const key of ['title','description_md','remediation_md',...(link.provider==='jira'?['due_date']:[])])fields.append(choice(w(...names[key]),selected.has(key),on=>{on?selected.add(key):selected.delete(key);invalidate();},key));
      box.append(fields,h('div',{class:'wf-row'},
        button(w('Consultar y comparar avances','Fetch and compare progress','Consultar e comparar avanços'),async()=>{
          invalidate();const serial=generation,identity=JSON.stringify(credentials()),guard=()=>serial===generation&&identity===JSON.stringify(credentials());
          const {value:preview,revision}=await call(context,'/'+link.uid+'/pull-preview',{credentials:credentials()},{guard});
          const accepted=new Set();result.append(h('p',{},w('Selecciona los cambios que deseas aceptar.','Select the changes to accept.','Selecione as alterações a aceitar.')));
          if(!preview.changes.length)result.append(h('p',{},w('No hay diferencias.','No differences.','Sem diferenças.')));
          for(const row of preview.changes){result.append(h('section',{class:'card'},choice(w(...names[row.field]),false,on=>{on?accepted.add(row.field):accepted.delete(row.field);apply.disabled=!accepted.size;},'accept:'+row.field),row.conflict?h('strong',{},w('Conflicto con una edición local','Conflict with a local edit','Conflito com uma edição local')):null,h('pre',{},w('Actual: ','Current: ','Atual: ')+row.before+'\n'+w('Externo: ','External: ','Externo: ')+row.after)));}
          const apply=button(w('Aceptar selección revisada','Accept reviewed selection','Aceitar seleção revisada'),async()=>{if(!accepted.size)throw changed();await call(context,'/'+link.uid+'/pull-apply',{remote_state:preview.remote_state,accepted:[...accepted],preview_token:preview.preview_token,ack_reviewed:true},{expected:revision,guard});token.node.value='';renderMain();},true,'pull-apply');apply.disabled=true;
          if(preview.changes.length)result.append(apply);
        },false,'pull-preview'),
        button(w('Revisar envío','Review outgoing changes','Revisar envio'),async()=>{
          invalidate();const serial=generation,identity=JSON.stringify(credentials()),guard=()=>serial===generation&&identity===JSON.stringify(credentials()),chosen=[...selected];
          if(!chosen.length)throw Error(w('Selecciona al menos un campo.','Select at least one field.','Selecione pelo menos um campo.'));
          const {value:preview,revision}=await call(context,'/'+link.uid+'/push-preview',{fields:chosen,credentials:credentials()},{guard});
          result.append(h('p',{},w('Estos campos reemplazarán los campos correspondientes del ticket externo.','These fields will replace the corresponding external ticket fields.','Estes campos substituirão os campos correspondentes do ticket externo.')));
          for(const change of preview.changes||[]){const available=change.before_available??change.available;result.append(h('section',{class:'card','data-ticket-outgoing-field':change.field},h('h4',{},change.field),h('strong',{},w('Antes','Before','Antes')),h('pre',{},available===false?w('La API no devolvió el valor actual. Verifícalo en el servicio antes de reemplazarlo.','The API did not return the current value. Verify it in the service before replacing it.','A API não retornou o valor atual. Verifique-o no serviço antes de substituí-lo.'):JSON.stringify(change.before,null,2)),h('strong',{},w('Después','After','Depois')),h('pre',{},JSON.stringify(change.after,null,2))));}
          result.append(h('details',{},h('summary',{},w('Carga exacta del envío','Exact outgoing payload','Conteúdo exato do envio')),h('pre',{},JSON.stringify(preview.payload,null,2))),button(w('Enviar cambios revisados','Send reviewed changes','Enviar alterações revisadas'),async()=>{await call(context,'/'+link.uid+'/push-apply',{fields:chosen,credentials:credentials(),remote_hash:preview.remote_hash,preview_token:preview.preview_token,ack_reviewed:true},{expected:revision,guard});token.node.value='';renderMain();},true,'push-apply'));
        },false,'push-preview'),button(w('Desvincular','Unlink','Desvincular'),async()=>{await call(context,'/'+link.uid,{}, {method:'DELETE'});renderMain();},false,'unlink')
      ),result);form.append(box);
    }
  }
  return {render};
})();
