/* Explicit retest baseline; this view never edits, saves or declares delivery. */
const RetestDiffUI = (() => {
  'use strict';
  const w=(es,en)=>S.uiLang==='en'?en:es;
  let generation=0,activeHost=null;
  const urls=new Set();
  const tag=value=>(value||'').replace(/^"|"$/g,'');
  const stageNames={delivered:['Entrega registrada','Recorded delivery'],draft:['Borrador','Draft'],retest:['Retest','Retest'],auto:['Autoguardado','Autosave']};
  const changeNames={added:['Añadidos','Added'],removed:['Retirados','Removed'],modified:['Modificados','Modified'],unchanged:['Sin cambios','Unchanged']};
  function note(es,en){return h('p',{class:'wf-hint'},w(es,en));}
  function button(es,en,fn,attrs={}){
    const node=h('button',{type:'button',class:'btn sm',...attrs},w(es,en));
    node.addEventListener('click',async()=>{node.disabled=true;try{await fn();}catch(error){toast(error.message,'err');}finally{node.disabled=false;}});
    return node;
  }
  function release(){for(const url of urls)URL.revokeObjectURL(url);urls.clear();}
  function render(host){
    release();activeHost=host;const token=++generation,slug=S.slug,etag=projectStore.etag,version=projectStore.revision,source=S.data,snapshot=JSON.stringify(source),lang=S.uiLang;
    const valid=()=>token===generation&&host.isConnected&&S.slug===slug&&S.uiLang===lang&&projectStore.etag===etag&&projectStore.revision===version&&S.data===source&&JSON.stringify(S.data)===snapshot&&!projectStore.dirty&&!projectStore.loading;
    host.classList.add('retest-diff');host.replaceChildren(h('h3',{},w('Comparar desde una entrega','Compare from a delivery')));
    if(!slug||projectStore.loading){host.append(note('Abre un proyecto antes de comparar.','Open a project before comparing.'));return Promise.resolve();}
    if(projectStore.dirty){host.append(note('Guarda o resuelve los cambios del proyecto antes de comparar. La lectura no guarda ni crea versiones.','Save or resolve project changes before comparing. Reading does not save or create versions.'));return Promise.resolve();}
    const status=h('p',{role:'status','data-retest-diff-status':''},w('Consultando versiones guardadas…','Reading saved versions…'));
    const content=h('div',{'data-retest-diff-content':''});host.append(status,content);
    const base='/api/projects/'+encodeURIComponent(slug)+'/retest-diff';let selected='',baselineGeneration=0;
    const path=(suffix='',baseline=selected)=>base+suffix+'?revision='+encodeURIComponent(tag(etag))+'&lang='+lang+(baseline?'&baseline='+encodeURIComponent(baseline):'');
    async function load(){
      const requestToken=++baselineGeneration;
      let response,data;
      try{response=await requireOk(await appFetch(path()));data=await response.json();}
      catch(error){if(valid()&&requestToken===baselineGeneration)status.textContent=error.message;return;}
      if(!valid()||requestToken!==baselineGeneration||tag(response.headers.get('ETag'))!==tag(etag)||data.revision!==tag(etag)||data.project_slug!==slug)return;
      status.textContent='';content.replaceChildren();
      content.append(note('Una etapa «entregado» es un registro local del autor. No demuestra que una exportación haya finalizado ni que el destinatario la haya recibido.','A “delivered” stage is a local author record. It does not prove that an export finished or that the recipient received it.'));
      const choose=h('select',{'data-retest-baseline':'','aria-label':w('Versión base para comparar','Comparison baseline')},h('option',{value:''},w('Última entrega registrada (si es inequívoca)','Latest recorded delivery (if unambiguous)')));
      for(const item of data.candidates||[])choose.append(h('option',{value:item.id},item.label+' / '+w(...(stageNames[item.stage]||[item.stage,item.stage]))+' / '+item.created));
      choose.value=selected;choose.addEventListener('change',()=>{selected=choose.value;status.textContent=w('Consultando comparación…','Reading comparison…');load().catch(error=>{if(valid())status.textContent=error.message;});});
      content.append(h('label',{class:'retest-diff-field'},w('Versión base','Baseline version'),choose));
      if(data.state!=='ready'){
        status.textContent=data.state==='no_delivered_baseline'?w('No hay una entrega registrada. Elige una versión existente o registra la entrega desde Versiones.','No recorded delivery exists. Choose an existing version or record delivery under Versions.'):
          w('La última entrega es ambigua por empate de fechas o falta de zona horaria. Elige una versión explícitamente.','The latest delivery is ambiguous because dates tie or lack a timezone. Choose a version explicitly.');
        return;
      }
      const chosen=data.baseline;
      content.append(h('div',{class:'card wf-card','data-retest-baseline-active':''},h('h4',{},chosen.label),h('p',{},w(...(stageNames[chosen.stage]||[chosen.stage,chosen.stage]))+' / '+chosen.created),note(data.selection==='explicit'?'Base elegida explícitamente. Su etapa no se convierte en una entrega por compararla.':'Base seleccionada por la fecha real de la última etapa entregada registrada.',data.selection==='explicit'?'Explicitly selected baseline. Comparing it does not turn its stage into a delivery.':'Baseline selected by the actual date of the latest recorded delivered stage.'),h('p',{class:'hash'},'SHA-256 '+chosen.snapshot_sha256)));
      content.append(note('Retirado significa que un hallazgo ya no está en el informe; no acredita una corrección. Los estados describen lo registrado y no validan técnicamente el resultado.','Removed means a finding is no longer in the report; it does not prove remediation. States describe recorded information and do not technically validate the result.'));
      if(data.legacy_identity)content.append(note('Hay identidades antiguas basadas en el ID visible. No se infiere continuidad con nuevos UID; una migración puede aparecer como retirada y añadido.','Some legacy identities use the displayed ID. Continuity with new UIDs is not inferred; migration can appear as removal and addition.'));
      const totals=h('ul',{class:'retest-diff-counts','data-retest-diff-counts':''});for(const key of Object.keys(changeNames))totals.append(h('li',{'data-retest-count':key},w(...changeNames[key])+': '+data.summary[key]));content.append(totals);
      const filter=h('select',{'data-retest-change-filter':'','aria-label':w('Filtrar cambios','Filter changes')},h('option',{value:''},w('Todos los hallazgos','All findings')),Object.keys(changeNames).map(key=>h('option',{value:key},w(...changeNames[key]))));
      const list=h('div',{'data-retest-diff-findings':''});content.append(h('label',{class:'retest-diff-field'},w('Mostrar','Show'),filter),list);
      const paint=()=>{
        list.replaceChildren();const rows=(data.findings||[]).filter(row=>!filter.value||row.change===filter.value);
        for(const item of rows){const row=h('article',{class:'card wf-card','data-retest-change':item.change,'data-retest-identity':item.identity},h('h4',{},item.id+' / '+item.title),h('p',{},w(...changeNames[item.change])));
          const fields=data.changes.filter(change=>change.finding_uid===item.identity).map(change=>change.path.split('.').slice(2).join('.')||w('Hallazgo completo','Whole finding'));if(fields.length)row.append(h('p',{class:'retest-diff-fields'},w('Campos modificados: ','Changed fields: ')+fields.join(', ')));
          const current=S.data.findings.findIndex(finding=>(finding.uid||finding.id)===item.identity);
          if(current>=0)row.append(button('Abrir hallazgo actual','Open current finding',()=>{if(valid())select('finding',S.data.findings.findIndex(finding=>(finding.uid||finding.id)===item.identity));}));
          list.append(row);
        }
        if(!rows.length)list.append(note('No hay hallazgos en este filtro.','No findings match this filter.'));
      };filter.addEventListener('change',paint);paint();
      const output=h('div',{'data-retest-visual-output':''}),ack=h('input',{type:'checkbox','data-retest-private-ack':''});
      const visualPath=privacy=>path('/visual',chosen.id)+'&baseline_sha256='+encodeURIComponent(chosen.snapshot_sha256)+'&privacy='+privacy+(privacy==='private'?'&ack_private=1':'');
      async function visual(privacy,download){
        if(!valid()||requestToken!==baselineGeneration)throw Error(w('El proyecto cambió. Vuelve a abrir la comparación.','Project changed. Reopen the comparison.'));
        if(privacy==='private'&&!ack.checked)throw Error(w('Confirma el acceso al contenido privado.','Acknowledge access to private content.'));
        const response=await requireOk(await appFetch(visualPath(privacy)+(download?'&download=1':''))),blob=await response.blob();
        if(!valid()||requestToken!==baselineGeneration||tag(response.headers.get('ETag'))!==tag(etag)||response.headers.get('X-Report-Gen-Baseline')!==chosen.snapshot_sha256)return;
        const url=URL.createObjectURL(blob);urls.add(url);
        if(download){h('a',{href:url,download:privacy==='private'?'retest-comparison-private.html':'retest-comparison-shareable.html'}).click();setTimeout(()=>{URL.revokeObjectURL(url);urls.delete(url);},1000);}
        else{const frame=h('iframe',{class:'comparison-frame',src:url,sandbox:'',title:privacy==='private'?w('Comparación interna privada','Private internal comparison'):w('Comparación de contenido publicado','Published-content comparison')});frame.addEventListener('load',()=>{URL.revokeObjectURL(url);urls.delete(url);},{once:true});output.replaceChildren(frame);}
      }
      content.append(h('div',{class:'card wf-card'},h('h4',{},w('Revisar y descargar','Review and download')),note('La comparación compartible usa el contenido publicado y las censuras actuales. Es una comparación del informe, no un extracto público ni un paquete por destinatario. Revisa también el texto histórico antes de compartir.','The shareable comparison uses published content and current redactions. It compares the report; it is not a public case or an audience package. Also review historical text before sharing.'),h('div',{class:'wf-row'},button('Revisar comparación compartible','Review shareable comparison',()=>visual('shareable',false),{'data-retest-shared-view':''}),button('Descargar HTML compartible','Download shareable HTML',()=>visual('shareable',true),{'data-retest-shared-download':''})),h('label',{class:'wf-check'},ack,w('Entiendo que la comparación interna contiene datos y borradores privados.','I understand that the internal comparison contains private data and drafts.')),h('div',{class:'wf-row'},button('Revisar comparación interna privada','Review private internal comparison',()=>visual('private',false),{'data-retest-private-view':''}),button('Descargar HTML interno privado','Download private internal HTML',()=>visual('private',true),{'data-retest-private-download':''})),output));
    }
    return load().catch(error=>{if(valid())status.textContent=error.message;});
  }
  function invalidate(){
    generation++;release();
    if(activeHost?.isConnected){
      const status=activeHost.querySelector('[data-retest-diff-status]');
      if(status)status.textContent=w('El contenido cambió. Vuelve a abrir la comparación con la versión guardada.','Content changed. Reopen comparison with the saved version.');
      activeHost.querySelector('[data-retest-diff-content]')?.replaceChildren();
    }
  }
  return {render,invalidate};
})();
