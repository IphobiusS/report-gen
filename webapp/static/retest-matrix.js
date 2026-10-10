/* Read-only saved-revision retest matrix. No save, mutation or export side effect. */
const RetestMatrixUI = (() => {
  'use strict';
  let generation = 0, mounted = null;
  const w = (es, en) => S.uiLang === 'en' ? en : es;
  const tagValue = etag => String(etag || '').replace(/^"|"$/g, '');
  const snapshot = () => ({slug:S.slug, data:S.data, json:JSON.stringify(S.data), revision:projectStore.revision,
    etag:projectStore.etag, lang:S.uiLang});
  function same(state) {
    return S.slug===state.slug && S.data===state.data && JSON.stringify(S.data)===state.json &&
      projectStore.revision===state.revision && projectStore.etag===state.etag && S.uiLang===state.lang &&
      !projectStore.dirty && !projectStore.loading && projectBusyCount===0;
  }
  function note(es,en){return h('p',{class:'rm-note'},w(es,en));}
  function reloadButton(host) {
    return h('button',{type:'button',class:'btn sm','data-retest-refresh':'',onclick:()=>render(host)},w('Actualizar desde el proyecto guardado','Refresh from saved project'));
  }
  function stale(state) {
    if(!state.host.isConnected)return;
    const banner=state.host.querySelector('[data-retest-stale]');
    if(banner){banner.hidden=false;banner.textContent=w('El contenido cambió. Guarda desde la barra del proyecto y actualiza esta vista antes de usar sus destinos.','Content changed. Save from the project toolbar and refresh this view before using its destinations.');}
    state.host.querySelectorAll('[data-retest-finding-uid]').forEach(button=>button.disabled=true);
    state.host.querySelectorAll('[data-retest-filter]').forEach(control=>control.disabled=true);
    state.host.setAttribute('data-retest-obsolete','true');
  }
  function invalidate() {if(mounted&&!same(mounted))stale(mounted);}
  function guard(state) {
    if(!same(state)){stale(state);return false;}
    return state.host.isConnected&&mounted===state;
  }
  function filterControl(label,key,choices,change) {
    const select=h('select',{'data-retest-filter':key,onchange:change},h('option',{value:''},w('Todos','All')),
      choices.map(choice=>h('option',{value:choice.key},choice.label)));
    return h('label',{class:'rm-filter'},h('span',{},label),select);
  }
  function association(label,group) {
    const warnings=(group.missing||0)+(group.ambiguous||0)+(group.invalid||0);
    return h('p',{},h('strong',{},label+': '),String(group.registered||0),
      warnings?' · '+w('Referencias por revisar: ','References to review: ')+warnings:null);
  }
  function cell(label,...contents) {return h('td',{},h('span',{class:'rm-cell-label','aria-hidden':'true'},label),...contents);}
  function openFinding(state,row) {
    if(!guard(state))return;
    const matches=(S.data.findings||[]).map((finding,index)=>({finding,index})).filter(item=>item.finding.uid===row.finding_uid);
    if(matches.length!==1){stale(state);return;}
    select('finding',matches[0].index);
    const title=document.querySelector('.finding-context-title strong');
    if(title){title.setAttribute('tabindex','-1');title.focus({preventScroll:true});title.scrollIntoView({block:'nearest'});}
  }
  function chart(state,rows,host) {
    const counts=Object.fromEntries(Object.keys(state.matrix.result_counts).map(key=>[key,0]));
    rows.forEach(row=>{if(Object.hasOwn(counts,row.outcome))counts[row.outcome]++;});
    const labels=state.matrix.result_labels,entries=Object.entries(counts),max=Math.max(1,...Object.values(counts));
    const list=h('ul',{class:'rm-counts','data-retest-chart':''},entries.map(([key,count])=>{
      const bar=h('span',{class:'rm-chart-bar'});bar.style.width=(count/max*100)+'%';
      return h('li',{'data-retest-result-count':key},h('span',{class:'rm-count-label'},labels[key]+': '),
        h('strong',{class:'rm-count-value'},String(count)),h('span',{class:'rm-chart-track','aria-hidden':'true'},bar));
    }));
    host.replaceChildren(h('h3',{},w('Último resultado registrado por hallazgo','Latest recorded result per finding')),
      note('Cada barra cuenta hallazgos del filtro actual. «Corregido» es el resultado escrito en el retest, no una certificación de esta herramienta.','Each bar counts findings in the current filter. “Fixed” is the retest’s recorded result, not a certification by this tool.'),list);
  }
  function table(state,rows,host) {
    const labels=[w('Hallazgo y severidad','Finding and severity'),w('Estado de seguimiento','Tracking status'),w('Verificación técnica','Technical verification'),w('Última observación fechada','Latest dated observation'),w('Asociaciones explícitas','Explicit associations'),w('Avisos de interpretación','Interpretation notes')];
    const body=h('tbody',{},rows.map(row=>{
      const findingLabel=(row.display_id?row.display_id+' · ':'')+(row.title||w('Sin título','Untitled'));
      const finding=row.identity_status==='unique'?h('button',{type:'button',class:'rm-finding','data-retest-finding-uid':row.finding_uid,onclick:()=>openFinding(state,row)},findingLabel):h('span',{},findingLabel);
      const latest=row.latest?h('div',{},h('strong',{},row.outcome_label),h('p',{},row.latest.tested_on),h('p',{},w('Evaluador: ','Assessor: ')+(row.latest.assessor||w('Sin registrar','Not recorded')))):h('strong',{},row.outcome_label);
      return h('tr',{'data-retest-row':row.key,'data-retest-outcome':row.outcome,role:'row'},
        h('th',{scope:'row'},finding,h('p',{},row.severity_label)),cell(labels[1],row.status_label),cell(labels[2],row.verification_label),
        cell(labels[3],latest,h('p',{},w('Observaciones registradas: ','Recorded observations: ')+row.observations)),
        cell(labels[4],association(w('Evidencia original vinculada','Linked original evidence'),row.original_evidence),association(w('Evidencia del último retest','Latest retest evidence'),row.retest_evidence),association(w('Activos vinculados','Linked assets'),row.assets),
          row.assets.items.length?h('ul',{},row.assets.items.map(asset=>h('li',{},asset.label))):null),
        cell(labels[5],row.notices.length?h('ul',{},row.notices.map(item=>h('li',{},item.text))):w('Sin avisos derivados de estos registros. La revisión humana sigue pendiente.','No notes derived from these records. Human review is still required.')));
    }));
    const table=h('table',{class:'rm-table',role:'table'},h('caption',{},w('Matriz de retest del proyecto guardado','Saved-project retest matrix')),h('thead',{},h('tr',{role:'row'},labels.map(label=>h('th',{scope:'col'},label)))),body);
    host.replaceChildren(table);
    if(!rows.length)host.append(h('p',{role:'status','data-retest-empty':''},w('No hay hallazgos que coincidan con estos filtros.','No findings match these filters.')));
  }
  function content(state) {
    const host=state.host,matrix=state.matrix,filters={status:'',severity:'',asset:'',outcome:''};
    const chartHost=h('section',{class:'rm-executive','aria-label':w('Resumen ejecutivo del retest','Executive retest summary')}),tableHost=h('div',{class:'rm-table-host'}),count=h('p',{'data-retest-count':'',role:'status'});
    function update(){
      if(!guard(state))return;
      const rows=matrix.rows.filter(row=>(!filters.status||row.status===filters.status)&&(!filters.severity||row.severity===filters.severity)&&(!filters.outcome||row.outcome===filters.outcome)&&(!filters.asset||row.assets.items.some(asset=>asset.uid===filters.asset)));
      count.textContent=w('Hallazgos mostrados: ','Findings shown: ')+rows.length+' / '+matrix.total_findings;
      chart(state,rows,chartHost);table(state,rows,tableHost);
    }
    const choices={status:matrix.filters.statuses,severity:matrix.filters.severities,asset:matrix.filters.assets,outcome:Object.keys(matrix.result_labels).map(key=>({key,label:matrix.result_labels[key]}))};
    const filterBox=h('fieldset',{class:'rm-filters'},h('legend',{},w('Filtrar hechos registrados','Filter recorded facts')),
      ...[['status',w('Estado de seguimiento','Tracking status')],['severity',w('Severidad','Severity')],['asset',w('Activo vinculado','Linked asset')],['outcome',w('Resultado de retest','Retest result')]].map(([key,label])=>filterControl(label,key,choices[key],event=>{filters[key]=event.target.value;update();})));
    const coverage=h('details',{class:'rm-scope'},h('summary',{},w('Cobertura registrada y límites de esta vista','Recorded coverage and limits of this view')),
      h('p',{},w('Registros de cobertura: ','Coverage records: ')+matrix.coverage.registered),
      h('ul',{},Object.entries(matrix.coverage.counts).map(([key,value])=>h('li',{},matrix.coverage.labels[key]+': '+value))),
      h('ul',{},matrix.scope.map(text=>h('li',{},text))));
    host.replaceChildren(h('div',{'data-retest-matrix':'',class:'rm-view'},
      note('Vista de la revisión guardada. Leer, filtrar y abrir un hallazgo no guarda ni cambia el informe.','Saved-revision view. Reading, filtering and opening a finding do not save or change the report.'),
      h('p',{'data-retest-stale':'',class:'rm-stale',role:'status',hidden:''}),
      reloadButton(host),filterBox,count,chartHost,coverage,tableHost));
    update();
  }
  async function render(host) {
    const token=++generation;
    mounted=null;
    if(!S.slug||!S.data){host.replaceChildren(note('Abre un proyecto para consultar la matriz.','Open a project to view the matrix.'));return;}
    if(projectStore.dirty||projectStore.loading||projectBusyCount>0){
      host.replaceChildren(h('p',{'data-retest-stale':'',class:'rm-stale',role:'status'},w('Guarda desde la barra del proyecto y espera a que termine la operación antes de abrir la matriz. Esta vista no guarda el borrador.','Save from the project toolbar and wait for the operation to finish before opening the matrix. This view does not save the draft.')),reloadButton(host));return;
    }
    const state={...snapshot(),host};
    host.replaceChildren(h('p',{role:'status','data-retest-loading':''},w('Leyendo observaciones guardadas…','Reading saved observations…')));
    try{
      const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(state.slug)+'/retest-matrix?revision='+encodeURIComponent(tagValue(state.etag))+'&lang='+encodeURIComponent(state.lang)));
      const body=await response.json();
      if(token!==generation||!host.isConnected)return;
      if(!same(state)||response.headers.get('ETag')!==state.etag||body.revision!==tagValue(state.etag)||body.project_slug!==state.slug){
        host.replaceChildren(h('p',{'data-retest-stale':'',class:'rm-stale',role:'status'},w('La revisión o el proyecto cambió durante la lectura. Conserva el borrador, guarda cuando corresponda y vuelve a abrir esta vista.','The revision or project changed during loading. Keep the draft, save when appropriate, and reopen this view.')),reloadButton(host));return;
      }
      if(body.matrix?.version!==1||body.matrix.source!=='saved_project'||!Array.isArray(body.matrix.rows))throw Error(w('Respuesta de matriz no reconocida.','Unrecognized matrix response.'));
      state.matrix=body.matrix;mounted=state;content(state);
    }catch(error){
      if(token!==generation||!host.isConnected)return;
      host.replaceChildren(h('p',{role:'alert'},error.message),reloadButton(host));
    }
  }
  return {render,invalidate};
})();
