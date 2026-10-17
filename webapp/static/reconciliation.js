/* Reviewed scanner observations. No scanner status can close a finding. */
const ReconciliationUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const labels={title:['Título','Title','Título'],affected:['Objetivo','Target','Alvo'],description_md:['Descripción','Description','Descrição'],impact_md:['Impacto','Impact','Impacto'],remediation_md:['Remediación','Remediation','Correção'],cwe:['CWE','CWE','CWE'],references:['Referencias','References','Referências'],walkthrough:['Añadir evidencia al recorrido','Append evidence to walkthrough','Adicionar evidência ao roteiro'],cvss_vector:['CVSS de origen','Source CVSS','CVSS da origem'],severity:['Severidad de origen','Source severity','Severidade da origem']};
  const text=value=>typeof value==='string'?value:JSON.stringify(value,null,2);
  const options=(body,etag)=>({method:'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify(body)});
  async function open(source,{slug=S.slug,etag=projectStore.etag,onCommitted}={}){
    if(!slug||S.slug!==slug||projectStore.dirty||etag!==projectStore.etag)throw Error(w('Guarda el proyecto y vuelve a analizar el archivo.','Save the project and analyze the file again.','Salve o projeto e analise o arquivo novamente.'));
    const opener=document.activeElement,dialog=h('dialog',{class:'experience-dialog progress-dialog','aria-label':w('Conciliar resultados','Reconcile results','Conciliar resultados'),'data-reconciliation-dialog':''});
    const status=h('p',{role:'status'}),body=h('div',{class:'experience-body'}),close=h('button',{type:'button',class:'btn'},w('Cerrar','Close','Fechar'));
    close.addEventListener('click',()=>dialog.close());
    dialog.addEventListener('close',()=>{dialog.remove();if(opener?.isConnected)opener.focus();});
    dialog.append(h('div',{class:'experience-heading'},h('h2',{},w('Conciliar resultados','Reconcile results','Conciliar resultados')),close),body,status);
    document.body.append(dialog);dialog.showModal();
    const check=()=>{if(!dialog.isConnected||S.slug!==slug||projectStore.dirty||projectStore.etag!==etag)throw Error(w('El proyecto cambió. Cierra y analiza nuevamente el archivo.','The project changed. Close and analyze the file again.','O projeto mudou. Feche e analise o arquivo novamente.'));};
    try{
      status.textContent=w('Buscando coincidencias…','Matching observations…','Buscando correspondências…');
      const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/imports/reconcile/preview',options(source,etag)));
      const preview=await response.json();check();
      body.append(h('p',{},preview.notice),h('p',{},preview.counts.new+' '+w('nuevas','new','novas')+' · '+preview.counts.exact+' '+w('exactas','exact','exatas')+' · '+preview.counts.probable+' '+w('probables','probable','prováveis')));
      const plans=[];
      for(const row of preview.rows){
        const finding=row.finding,plan={index:row.index,action:'skip'},card=h('article',{class:'card','data-reconcile-row':row.index});plans.push(plan);
        const matchLabel={new:w('Nueva observación','New observation','Nova observação'),exact:w('Identidad de origen coincidente','Matching source identity','Identidade de origem correspondente'),probable:w('Coincidencia probable: revisar','Probable match: review','Correspondência provável: revisar')};
        card.append(h('h3',{},finding.title),h('p',{},finding.affected),h('p',{},matchLabel[row.match]),...row.errors.map(error=>h('p',{class:'wf-error'},error)));
        const action=h('select',{'aria-label':w('Decisión','Decision','Decisão')},h('option',{value:'skip'},w('Omitir','Skip','Ignorar')),
          ...(!row.errors.length&&row.match!=='exact'?[h('option',{value:'create'},w('Crear hallazgo sin verificar','Create unverified finding','Criar achado não verificado'))]:[]),
          ...(!row.errors.length?[h('option',{value:'attach'},w('Adjuntar a hallazgo existente','Attach to existing finding','Anexar a achado existente'))]:[]));
        const target=h('select',{'aria-label':w('Hallazgo de destino','Target finding','Achado de destino')},h('option',{value:''},w('Selecciona el hallazgo','Select a finding','Selecione um achado')),
          ...S.data.findings.map(f=>h('option',{value:f.uid},f.id+' · '+f.title+(row.matches.some(m=>m.finding_uid===f.uid)?' · '+w('coincidencia','match','correspondência'):''))));
        const instance=h('select',{'aria-label':w('Instancia de destino','Target instance','Instância de destino')}),changes=h('div',{}),attach=h('div',{},h('label',{},w('Hallazgo de destino','Target finding','Achado de destino'),target),h('label',{},w('Instancia (opcional)','Instance (optional)','Instância (opcional)'),instance),changes);attach.hidden=true;
        function redrawTarget(){
          plan.finding_uid=target.value;plan.instance_uid='';plan.fields=[];changes.replaceChildren();
          const current=S.data.findings.find(f=>f.uid===target.value);
          instance.replaceChildren(h('option',{value:''},w('Observación general','General observation','Observação geral')),...(current?.instances||[]).map(item=>h('option',{value:item.uid},[item.endpoint,item.parameter,item.identity].filter(Boolean).join(' · ')||item.uid)));
          if(!current)return;
          changes.append(h('p',{},w('Por defecto se conserva todo el contenido manual. Marca solo los campos que deseas copiar; CVSS, estado y retests se conservan siempre.','All authored content is preserved by default. Select only fields to copy; CVSS, status and retests are always preserved.','Todo o conteúdo manual é preservado por padrão. Selecione somente os campos a copiar; CVSS, estado e retestes são sempre preservados.')));
          for(const field of preview.copy_fields){
            if(current.mode==='machine'&&!['title','references','walkthrough'].includes(field))continue;
            const before=current[field]??(['references','walkthrough'].includes(field)?[]:''),after=finding[field]??(['references','walkthrough'].includes(field)?[]:'');
            if(JSON.stringify(before)===JSON.stringify(after))continue;
            const checkbox=h('input',{type:'checkbox','data-reconcile-field':field});
            checkbox.addEventListener('change',()=>{plan.fields=checkbox.checked?[...plan.fields,field]:plan.fields.filter(item=>item!==field);ack.checked=false;});
            changes.append(h('details',{},h('summary',{},w(...labels[field])),h('h4',{},w('Actual','Current','Atual')),h('pre',{},text(before)||'—'),h('h4',{},w('Observación entrante','Incoming observation','Observação recebida')),h('pre',{},text(after)||'—'),h('label',{class:'wf-check'},checkbox,w(field==='walkthrough'?'Añadir estos pasos':'Copiar este campo',field==='walkthrough'?'Append these steps':'Copy this field',field==='walkthrough'?'Adicionar estes passos':'Copiar este campo'))));
          }
        }
        target.addEventListener('change',()=>{redrawTarget();ack.checked=false;});
        instance.addEventListener('change',()=>{plan.instance_uid=instance.value;ack.checked=false;});
        action.addEventListener('change',()=>{for(const key of Object.keys(plan))if(!['index','action'].includes(key))delete plan[key];plan.action=action.value;attach.hidden=action.value!=='attach';if(!attach.hidden)redrawTarget();ack.checked=false;});
        card.append(h('label',{},w('Decisión','Decision','Decisão'),action),attach,h('details',{},h('summary',{},w('Contenido y origen entrante','Incoming content and provenance','Conteúdo recebido e origem')),h('pre',{},JSON.stringify(finding,null,2))));body.append(card);
      }
      const ack=h('input',{type:'checkbox','data-reconcile-ack':''}),apply=h('button',{type:'button',class:'btn primary','data-reconcile-apply':''},w('Aplicar decisiones revisadas','Apply reviewed decisions','Aplicar decisões revisadas'));
      body.append(h('label',{class:'wf-check'},ack,w('Revisé el destino, las diferencias y los campos seleccionados.','I reviewed the destination, differences and selected fields.','Revisei o destino, as diferenças e os campos selecionados.')),apply);
      apply.addEventListener('click',async()=>{
        let busy=false;
        try{
          check();if(!ack.checked)throw Error(w('Confirma las decisiones revisadas.','Confirm the reviewed decisions.','Confirme as decisões revisadas.'));
          if(!plans.some(plan=>plan.action!=='skip'))throw Error(w('Selecciona una acción.','Select an action.','Selecione uma ação.'));
          if(plans.some(plan=>plan.action==='attach'&&!plan.finding_uid))throw Error(w('Selecciona el hallazgo de destino.','Select the target finding.','Selecione o achado de destino.'));
          apply.disabled=true;close.disabled=true;busyProject(true);busy=true;
          const result=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/imports/reconcile/apply',options({...source,decisions:plans,preview_token:preview.preview_token,ack_reviewed:true},etag)));
          const saved=await result.json();await adoptSavedProject(saved.data,result.headers.get('ETag'));
          await onCommitted?.();dialog.close();renderSidebar();renderMain();toast(saved.applied+' '+w('observaciones incorporadas','observations incorporated','observações incorporadas'),'ok');
        }catch(error){status.textContent=error.message;}finally{apply.disabled=false;close.disabled=false;if(busy)busyProject(false);}
      });
      status.textContent='';
    }catch(error){status.textContent=error.message;}
  }
  function observations(box,finding){
    if(!finding.import_observations?.length)return;
    const panel=h('details',{class:'import-origin'},h('summary',{},w('Observaciones conciliadas (privadas)','Reconciled observations (private)','Observações conciliadas (privadas)')+' · '+finding.import_observations.length),h('p',{},w('El historial original es privado. Solo los campos copiados explícitamente forman parte del informe.','Original history is private. Only explicitly copied fields form part of the report.','O histórico original é privado. Somente os campos copiados explicitamente fazem parte do relatório.')));
    for(const row of finding.import_observations)panel.append(h('details',{},h('summary',{},row.source.format+' · '+row.imported_at),h('p',{},w('Instancia: ','Instance: ','Instância: ')+(row.instance_uid||'—')),h('p',{},w('Campos copiados: ','Copied fields: ','Campos copiados: ')+row.selected_fields.map(field=>w(...labels[field])).join(', ')),h('pre',{},JSON.stringify({source:row.source,observation:row.snapshot},null,2))));
    box.append(panel);
  }
  return {open,observations};
})();
