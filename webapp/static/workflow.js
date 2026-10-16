/* Project workflows. All mutations share the existing revision/CSRF save contract. */
const WorkflowUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const uid = () => crypto.randomUUID();
  const clone = x => JSON.parse(JSON.stringify(x));
  const names = {review:['Revisión de entrega','Delivery review', "Revisão de entrega"], history:['Versiones','Versions', "Versões"], evidence:['Evidencias','Evidence', "Evidências"], assets:['Activos','Assets', "Ativos"], coverage:['Cobertura','Coverage', "Cobertura"], root_causes:['Causas raíz','Root causes', "Causas raiz"], remediation_tasks:['Tareas de remediación','Remediation tasks', "Tarefas de correção"], retest:['Correcciones y retest','Remediation and retest', "Correções e retestes"], retest_diff:['Cambios desde la entrega','Changes since delivery', "Alterações desde a entrega"], retest_matrix:['Matriz de retest','Retest matrix', "Matriz de retestes"], backup:['Respaldo del proyecto','Project backup', "Backup do projeto"], library:['Biblioteca de hallazgos','Finding library', "Biblioteca de achados"]};
  const statuses = [['open','Abierto','Open','Aberto'],['in_progress','En corrección','In progress', "Em correção"],['reported_fixed','Corrección comunicada','Reported fixed', "Correção informada"],['verified_fixed','Corregido y verificado','Verified fixed', "Corrigido e verificado"],['accepted','Riesgo aceptado','Risk accepted', "Risco aceito"],['not_verified','No verificable','Not verifiable', "Não verificável"]];
  const results = [['fixed','Corregido','Fixed', "Corrigido"],['open','Sigue abierto','Still open', "Ainda aberto"],['partial','Corrección parcial','Partially fixed', "Parcialmente corrigido"],['not_verified','No verificable','Not verifiable', "Não verificável"]];
  const cover = [['pending','Pendiente','Pending', "Pendente"],['done','Realizada','Performed', "Realizada"],['blocked','Bloqueada','Blocked', "Bloqueada"],['not_applicable','No aplica','Not applicable', "Não aplicável"]];
  const stageNames = [['draft','Borrador','Draft', "Rascunho"],['delivered','Entrega registrada localmente','Delivery recorded locally', "Entrega registrada localmente"],['retest','Retest','Retest', "Reteste"]];
  let libraryTag = null;
  let modalTrigger = null;
  let reviewSession=null,reviewGeneration=0,reviewChecking=false;
  function title(kind) { return w(...names[kind]); }
  function safe(fn) { return async event => { try { await fn(event); } catch (e) { toast(e.message, 'err'); } }; }
  function button(text, fn, primary=false) { const b=h('button', {class:'btn sm' + (primary?' primary':''), type:'button'}, text); b.addEventListener('click',safe(async event=>{modalTrigger=b;b.disabled=true;try{await fn(event);}finally{b.disabled=false;}}));return b; }
  function hint(es,en,pt) { return h('p',{class:'wf-hint'},w(es,en,pt)); }
  function card(...children) { return h('div',{class:'card wf-card'},...children); }
  function row(...children) { return h('div',{class:'wf-row'},...children); }
  function localField(label,obj,key,type='text') {
    const input = h(type === 'textarea' ? 'textarea':'input', {type:type === 'textarea' ? null:type, rows:type==='textarea'?5:null, 'data-field':key, oninput:e=>{obj[key]=e.target.value;}});
    input.value=obj[key]??'';
    return h('label',{},label,input);
  }
  function selectField(label,obj,key,items,persist=true) {
    const input=h('select',{'data-field':key,onchange:e=>{obj[key]=e.target.value;if(persist)scheduleSave();}}, items.map(([value,es,en,pt])=>h('option',{value},en === undefined ? es : w(es,en,pt))));
    input.value=obj[key]||items[0]?.[0]||'';
    return h('label',{},label,input);
  }
  function check(label,checked,fn) {return h('label',{class:'wf-check'},h('input',{type:'checkbox',checked:checked?'':null,onchange:e=>fn(e.target.checked)}),label);}
  function links(label,obj,key,items,persist=true) {
    const box=h('fieldset',{'data-field':key,class:'wf-links'},h('legend',{},label));
    if(!items.length) box.append(hint('No hay elementos registrados. Añádelos desde el menú del proyecto.','No registered items. Add them from the project menu.', "Nenhum item cadastrado. Adicione-os pelo menu do projeto."));
    items.forEach(item=>box.append(check(item.name||item.title||item.target, (obj[key]||[]).includes(item.uid), checked=>{
      obj[key]=checked?[...new Set([...(obj[key]||[]),item.uid])]:(obj[key]||[]).filter(x=>x!==item.uid);
      if(persist)scheduleSave();
    })));
    return box;
  }
  async function requestJson(path,options) { const r=await requireOk(await appFetch(path,options)); return {body:await r.json(),etag:r.headers.get('ETag')}; }
  function url(path='',slug=S.slug) {return '/api/projects/'+encodeURIComponent(slug)+path;}
  async function mutate(path,body) {
    const slug=S.slug; busyProject(true);
    try {
      if(!await doSave())throw Error(w('No se pudo guardar el proyecto.','Could not save project.', "Não foi possível salvar o projeto."));
      const r=await requestJson(url(path,slug),{method:'POST',headers:{'Content-Type':'application/json','If-Match':projectStore.etag},body:JSON.stringify(body)});
      if(S.slug===slug){
        if(r.body.data)await adoptSavedProject(r.body.data,r.etag||projectStore.etag);
        else if(r.etag)projectStore.etag=r.etag;
        renderSidebar();renderMain();if(S.previewMode==='live')refreshLivePreview();
      }
      return r.body;
    }finally{busyProject(false);}
  }
  async function download(path,name,options) {
    const r=await requireOk(await appFetch(path,options)); const blob=await r.blob();
    const link=URL.createObjectURL(blob); const a=h('a',{href:link,download:name});a.click();setTimeout(()=>URL.revokeObjectURL(link),1000);
  }
  function jsonDownload(value,name){const link=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));h('a',{href:link,download:name}).click();setTimeout(()=>URL.revokeObjectURL(link),1000);}
  function pick(accept,fn){const input=h('input',{type:'file',accept,onchange:safe(async()=>{if(input.files[0])await fn(input.files[0]);})});input.click();}
  function go(kind){select('workflow',kind);}
  function bind(){
    const section=h('div',{class:'side-sec',id:'workflowNav'},h('div',{class:'side-head'},w('Gestión del proyecto','Project management', "Gerenciamento de projetos")));
    Object.keys(names).filter(k=>k!=='library').forEach(k=>section.append(h('button',{class:'navitem','data-workflow':k,onclick:()=>go(k)},title(k))));
    $('.sidebar').append(section);
    $('#importProjectBtn').addEventListener('click',safe(importProject));
  }
  function updateNav(){document.querySelectorAll('[data-workflow]').forEach(b=>{b.textContent=title(b.dataset.workflow);b.classList.toggle('active',S.sel.type==='workflow'&&S.sel.idx===b.dataset.workflow);});const b=$('#importProjectBtn');if(b)b.textContent=w('Abrir respaldo','Open backup', "Abrir backup");}
  function render(kind,el){
    el.append(h('h2',{},title(kind)));const box=h('div',{'data-workflow-view':kind});el.append(box);
    const slug=S.slug;
    Promise.resolve().then(()=>({review,history,evidence,assets,coverage,root_causes:rootCauses,remediation_tasks:()=>RemediationUI.render(box),retest,retest_diff:()=>RetestDiffUI.render(box),retest_matrix:()=>RetestMatrixUI.render(box),backup,library}[kind])(box,slug)).catch(e=>{if(box.isConnected)box.append(card(h('p',{role:'alert'},e.message),button(w('Reintentar','Retry', "Tentar novamente"),()=>renderMain())));});
  }
  function findingPanel(f){
    const box=card(h('h3',{},w('Seguimiento y vínculos','Tracking and links', "Acompanhamento e vínculos")));
    box.append(selectField(w('Verificación técnica','Technical verification', "Verificação técnica"),f,'verification',WorkbenchUI.verification));
    if(f.status==='not_verified'&&!f.verification)box.append(hint('Este proyecto conserva el estado anterior «No verificable». La verificación técnica está sin registrar; revísala antes de asignar un valor.','This project retains the legacy “Not verifiable” status. Technical verification has not been recorded; review it before assigning a value.', "Este projeto mantém o status legado “Não verificável”. A verificação técnica não foi registrada; revise-a antes de atribuir um valor."));
    box.append(row(field(w('Responsable','Owner', "Responsável"),f,'owner'),field(w('Fecha objetivo','Due date', "Prazo"),f,'due_date',{type:'date'}),selectField(w('Estado','Status', "Status"),f,'status',statuses)));
    if(f.reported_remediation)box.append(h('details',{},h('summary',{},w('Corrección comunicada por retorno (sin verificar)','Remediation reported through return (unverified)', "Correção informada no retorno (não verificada)")),h('p',{class:'wf-hint'},w('Comunicación recibida. No modifica el estado ni acredita un retest.','Received communication. It does not change status or prove a retest.', "Comunicação recebida. Não altera o status nem comprova um reteste.")),h('div',{style:'white-space:pre-wrap;overflow-wrap:anywhere'},f.reported_remediation)));
    box.append(rootCauseSelector(f),field(w('Criterio de cierre','Closure criteria', "Critérios de encerramento"),f,'closure_criteria_md',{area:true,ph:w('Qué comprobar para aceptar la corrección.','What to verify before accepting the fix.', "O que verificar antes de aceitar a correção.")}));
    box.append(links(w('Activos afectados','Affected assets', "Ativos afetados"),f,'asset_uids',S.data.assets||[]),links(w('Evidencias vinculadas','Linked evidence', "Evidências vinculadas"),f,'evidence_uids',S.data.evidence||[]));
    box.append(button(w('Registrar / ver retest','Record / view retest', "Registrar / ver reteste"),()=>{S.retestFinding=f.uid;go('retest');}));
    box.append(h('details',{},h('summary',{},w('Referencia permanente','Permanent reference', "Referência permanente")),h('code',{},f.uid||'')));
    if(typeof ProgressUI!=='undefined')ProgressUI.importReview(box,f);
    return box;
  }
  function reviewKey(issue){
    let path=issue.path||'report';
    if(issue.finding_uid)path=path.replace(/^findings\[\d+\]/,'findings.'+issue.finding_uid);
    else path=path.replace(/^(assets|evidence|coverage|capture_inbox|root_cause_groups)\[(\d+)\]/,(_,group,index)=>group+'.'+(S.data[group]?.[Number(index)]?.uid||index));
    return JSON.stringify([issue.level,path,issue.message]);
  }
  function reviewCategory(issue){
    if(issue.level==='error')return 'blockers';
    if(/^(publication|attachments|capture_inbox)/.test(issue.path))return 'publication';
    if(/evidence|asset_uids/.test(issue.path))return 'links';
    if(issue.finding_uid||issue.path.startsWith('findings')||issue.path.startsWith('root_cause_groups'))return 'findings';
    if(issue.path.startsWith('coverage')||issue.path==='limitations_md')return 'coverage';
    return 'report';
  }
  const reviewGroups=[['blockers','Bloqueos de entrega','Delivery blockers', "Impedimentos para a entrega"],['publication','Publicación y anexos','Publication and attachments', "Publicação e anexos"],['links','Evidencia y asociaciones','Evidence and links', "Evidências e vínculos"],['findings','Contenido de hallazgos','Finding content', "Conteúdo dos achados"],['coverage','Cobertura y límites','Coverage and limitations', "Cobertura e limitações"],['report','Contenido del informe','Report content', "Conteúdo do relatório"]];
  function orderedIssues(issues){return [...issues].sort((a,b)=>reviewGroups.findIndex(g=>g[0]===reviewCategory(a))-reviewGroups.findIndex(g=>g[0]===reviewCategory(b)));}
  function reviewProgress(){
    if(!reviewSession||reviewSession.slug!==S.slug)return null;
    const current=new Set(reviewSession.issues.map(reviewKey)),total=reviewSession.initial.size,absent=[...reviewSession.initial].filter(key=>!current.has(key)).length,newCount=[...current].filter(key=>!reviewSession.initial.has(key)).length;
    return {total,absent,newCount,pending:reviewSession.issues.length};
  }
  function progressNode(){
    const progress=reviewProgress();if(!progress)return h('span',{});
    return h('div',{class:'review-progress','data-review-progress':'',role:'status'},
      h('p',{},w('Avisos iniciales que ya no aparecen: ','Initial items no longer detected: ', "Itens iniciais não mais detectados: ")+progress.absent+' / '+progress.total+' · '+w('Pendientes actuales: ','Currently pending: ', "Pendências atuais: ")+progress.pending+(progress.newCount?' · '+w('Nuevos: ','New: ', "Novos: ")+progress.newCount:'')),
      ...(progress.total?[h('progress',{value:progress.absent,max:progress.total,'aria-label':w('Avisos iniciales que ya no aparecen','Initial items no longer detected', "Itens iniciais não mais detectados")})]:[]));
  }
  async function checkReview(slug){
    const lang=S.uiLang;
    if(!await doSave())throw Error(w('No se pudo guardar. Conserva el borrador y resuelve el aviso de guardado antes de continuar.','Could not save. Keep the draft and resolve the save warning before continuing.', "Não foi possível salvar. Mantenha o rascunho e resolva o aviso de salvamento antes de continuar."));
    if(S.slug!==slug||projectStore.loading)throw Error(w('El proyecto cambió. Vuelve a abrir la revisión.','The project changed. Reopen review.', "O projeto mudou. Reabra a revisão."));
    const etag=projectStore.etag,revision=projectStore.revision;
    const {body,etag:responseTag}=await requestJson(url('/review?lang='+lang,slug));
    if(S.slug!==slug||projectStore.revision!==revision||projectStore.etag!==etag||projectStore.dirty||S.uiLang!==lang||(responseTag&&responseTag!==etag))throw Error(w('El contenido cambió durante la comprobación. Vuelve a revisar la revisión actual.','Content changed during the check. Review the current revision again.', "O conteúdo mudou durante a verificação. Revise a revisão atual novamente."));
    const issues=orderedIssues(body.issues||[]);
    if(!reviewSession||reviewSession.slug!==slug||reviewSession.lang!==lang)reviewSession={slug,lang,initial:new Set(issues.map(reviewKey))};
    Object.assign(reviewSession,{issues,etag,revision});
    return body;
  }
  async function resolveNext(){
    if(reviewChecking||!S.slug||projectBusyCount>0||projectStore.loading)return;
    const slug=S.slug,selection=JSON.stringify(S.sel),generation=++reviewGeneration;
    reviewChecking=true;
    try{
      await checkReview(slug);
      if(generation!==reviewGeneration||S.slug!==slug||selection!==JSON.stringify(S.sel))return;
      const issue=reviewSession.issues[0];
      if(issue)navigateIssue(issue);else{go('review');toast(w('Estas comprobaciones ya no detectan avisos. La verificación técnica sigue a tu cargo.','These checks no longer detect review items. Technical verification remains your responsibility.', "Estas verificações não detectam mais itens para revisão. A verificação técnica continua sendo sua responsabilidade."),'ok');}
    }finally{reviewChecking=false;}
  }
  function reviewControls(head){
    if(!reviewSession||reviewSession.slug!==S.slug)return;
    const controls=h('div',{class:'review-session-controls'},h('span',{},w('Última comprobación: ','Last check: ', "Última verificação: ")+reviewSession.issues.length+' '+w('pendientes','pending items', "itens pendentes")),
      button(w('Guardar y comprobar siguiente','Save and check next', "Salvar e verificar o próximo"),resolveNext),button(w('Volver a la revisión','Back to review', "Voltar à revisão"),()=>go('review')));
    controls.querySelector('button').dataset.reviewNext='';head.append(controls);
  }
  function resetReview(){reviewSession=null;reviewGeneration++;}
  // A view may describe these checks, but must never treat them as technical approval.
  function reviewSnapshot(){
    if(!reviewSession||reviewSession.slug!==S.slug)return null;
    return {current:!projectStore.dirty&&!projectStore.loading&&reviewSession.revision===projectStore.revision&&reviewSession.etag===projectStore.etag,
      issues:reviewSession.issues.length,errors:reviewSession.issues.filter(issue=>issue.level==='error').length};
  }
  async function review(box,slug){
    const generation=++reviewGeneration;
    const status=h('p',{role:'status'},w('Comprobando la revisión guardada…','Checking the saved revision…', "Verificando a revisão salva…"));box.append(status);
    await checkReview(slug);if(!box.isConnected||S.slug!==slug||generation!==reviewGeneration)return;
    status.remove();const issues=reviewSession.issues,errors=issues.filter(x=>x.level==='error').length;
    const next=button(w('Resolver siguiente pendiente','Resolve next pending item', "Resolver próximo item pendente"),resolveNext,true);next.dataset.reviewNext='';next.disabled=!issues.length;
    box.append(card(h('h3',{},errors+' '+w('errores','errors', "erros")+' · '+(issues.length-errors)+' '+w('avisos','warnings', "avisos")),progressNode(),hint('El progreso compara los avisos de esta sesión con la revisión guardada actual. Que un aviso desaparezca no demuestra que una vulnerabilidad se haya corregido. La aceptación editorial y la verificación técnica se registran por separado.','Progress compares this session’s initial items with the current saved revision. An item disappearing does not prove that a vulnerability was fixed. Editorial acceptance and technical verification are recorded separately.', "O progresso compara os itens iniciais desta sessão com a revisão salva atual. O desaparecimento de um item não comprova que uma vulnerabilidade foi corrigida. A aceitação editorial e a verificação técnica são registradas separadamente."),row(next,button(w('Volver a comprobar','Check again', "Verificar novamente"),()=>renderMain()),button(w('Mesa de revisión editorial','Editorial review desk', "Mesa de revisão editorial"),()=>InsightsUI.open('review')))));
    if(!issues.length)box.append(card(w('No se detectaron omisiones en estas comprobaciones.','No omissions detected by these checks.', "Nenhuma omissão detectada por estas verificações.")));
    for(const [key,es,en,pt] of reviewGroups){
      const group=issues.filter(issue=>reviewCategory(issue)===key);if(!group.length)continue;
      const section=h('section',{class:'review-group','data-review-group':key},h('h3',{},w(es,en,pt)+' ('+group.length+')'));
      for(const issue of group)section.append(card(h('strong',{class:'wf-'+issue.level},issue.message),h('small',{},issue.path),h('details',{class:'review-help'},h('summary',{},w('Cómo resolverlo','How to resolve it', "Como resolver")),h('p',{},issue.help||w('Abre el campo, contrasta lo escrito con tu evidencia y vuelve a revisar. Un aviso no determina si el sistema es vulnerable.','Open the field, check the text against your evidence, then review again. A warning does not determine whether the system is vulnerable.', "Abra o campo, confira o texto com suas evidências e revise novamente. Um aviso não determina se o sistema é vulnerável."))),button(w('Ir al campo','Go to field', "Ir para o campo"),()=>navigateIssue(issue))));
      box.append(section);
    }
    box.append(button(w('Guardar versión de entrega','Save delivery version', "Salvar versão de entrega"),()=>{go('history');},true));
  }
  function navigateIssue(issue){
    let fieldKey=issue.path.split('.').pop().replace(/\[\d+\]/g,'');
    if(issue.finding_uid){const i=S.data.findings.findIndex(f=>f.uid===issue.finding_uid);if(i>=0)select('finding',i);}
    else if(issue.path.startsWith('attachments')){AnnexUI.open();return;}
    else if(issue.path.startsWith('capture_inbox'))select('capture');
    else if(issue.path.startsWith('root_cause_groups'))go('root_causes');
    else if(issue.path.startsWith('coverage'))go('coverage');
    else if(issue.path.startsWith('evidence'))go('evidence');
    else if(issue.path.startsWith('assets'))go('assets');
    else if(issue.path.startsWith('report.sections[')){const i=Number(issue.path.match(/\[(\d+)\]/)[1]);select('section',S.data.report.sections[i]?.key);}
    else select('report',-1);
    let attempts=0;
    function focus(){
      const scope=$('#editor');const group=issue.path.match(/^(assets|coverage|evidence|root_cause_groups)\[(\d+)\]/);
      const step=issue.path.match(/(?:walkthrough|steps)\[(\d+)\]/);
      if(group?.[1]==='evidence'&&!scope.querySelector(`[data-workflow-index="${group[2]}"]`))scope.querySelector('[data-workflow-view="evidence"]')?.dispatchEvent(new CustomEvent('report-gen:evidence-page',{detail:{index:Number(group[2])}}));
      const container=(group?scope.querySelector(`[data-workflow-index="${group[2]}"]`):step?scope.querySelector(`[data-step-index="${step[1]}"]`):scope)||scope;
      let target=Array.from(container.querySelectorAll('[data-field]')).find(x=>x.dataset.field===fieldKey);
      if(!target&&issue.path.includes('walkthrough'))target=container.querySelector('[data-add-step]');
      if(target){WorkbenchUI.revealFindingField?.(target);let ancestor=target.closest('details');while(ancestor){ancestor.open=true;ancestor=ancestor.parentElement?.closest('details');}target.scrollIntoView?.({block:'center'});(target.matches('input,textarea,select,button')?target:target.querySelector('input,textarea,select'))?.focus();target.classList.add('wf-focus');setTimeout(()=>target.classList.remove('wf-focus'),3000);}
      else if(++attempts<30)setTimeout(focus,100);
    }
    setTimeout(focus,50);
  }
  async function history(box,slug){
    box.append(card(hint('Compara visualmente dos archivos PDF de entrega, incluso si no están guardados en el historial.','Visually compare two delivery PDF files, including files outside the version history.','Compare visualmente dois arquivos PDF de entrega, inclusive arquivos fora do histórico de versões.'),button(w('Comparar archivos PDF','Compare PDF files','Comparar arquivos PDF'),event=>PDFComparisonUI.open(event.currentTarget))));
    if(!await doSave())return;
    const {body:records}=await requestJson(url('/history',slug));if(!box.isConnected||S.slug!==slug)return;
    const draft={label:'',stage:'draft'};
    box.append(card(hint('Se conservan los autoguardados y los archivos de cada versión. Usa un nombre para identificar una entrega o un retest.','Autosaves and each version’s files are retained. Name a checkpoint to identify a delivery or retest.', "Os salvamentos automáticos e os arquivos de cada versão são mantidos. Nomeie um ponto de controle para identificar uma entrega ou um reteste."),row(localField(w('Nombre de versión','Version name', "Nome da versão"),draft,'label'),selectField(w('Etapa','Stage', "Etapa"),draft,'stage',stageNames,false)),button(w('Crear versión','Create version', "Criar versão"),async()=>{if(!draft.label.trim())throw Error(w('Escribe un nombre.','Enter a name.', "Informe um nome."));await mutate('/history',draft);},true)));
    const chosen={to:''};const options=[['',w('Proyecto actual','Current project', "Projeto atual")],...records.map(r=>[r.id,r.label+' · '+new Date(r.created).toLocaleString(languageTag(S.uiLang))])];
    box.append(selectField(w('Comparar con','Compare with', "Comparar com"),chosen,'to',options,false));
    const diff=h('div',{class:'wf-diff'});box.append(diff);
    const list=h('div',{});box.append(list);const filter={auto:false};
    const draw=()=>{list.replaceChildren();records.filter(r=>filter.auto||r.stage!=='auto').forEach(r=>list.append(card(row(h('strong',{},r.label),h('small',{},(stageNames.find(s=>s[0]===r.stage)?.slice(1)[{es:0,en:1,pt:2}[S.uiLang]]||w('Autoguardado','Autosave', "Salvamento automático"))+' · '+new Date(r.created).toLocaleString(languageTag(S.uiLang)))),row(button(w('Comparar','Compare', "Comparar"),async()=>{
      if(!await doSave())return;
      ProgressUI.compare(diff,slug,r.id,chosen.to);

    }),button(w('Restaurar','Restore', "Restaurar"),async()=>{if(confirm(w('¿Restaurar esta versión y sus imágenes? El estado actual quedará en el historial.','Restore this version and its images? The current state will remain in history.', "Restaurar esta versão e suas imagens? O estado atual permanecerá no histórico.")))await mutate('/history/'+r.id+'/restore',{});})))));};
    box.insertBefore(check(w('Mostrar autoguardados','Show autosaves', "Mostrar salvamentos automáticos"),false,v=>{filter.auto=v;draw();}),list);draw();
    if(!records.some(r=>r.stage!=='auto'))list.append(hint('Todavía no hay versiones nombradas. Los autoguardados ya están disponibles.','No named versions yet. Autosaves are already available.', "Ainda não há versões nomeadas. Os salvamentos automáticos já estão disponíveis."));
  }
  function assets(box){
    const rows=S.data.assets||(S.data.assets=[]);
    box.append(hint('Registra URLs, endpoints, hosts o redes. Puedes vincular varios activos a un mismo hallazgo.','Register URLs, endpoints, hosts or networks. A finding can affect multiple assets.', "Cadastre URLs, endpoints, hosts ou redes. Um achado pode afetar vários ativos."));
    rows.forEach((a,i)=>box.append(card(row(field(w('Nombre','Name', "Nome"),a,'name'),field(w('Objetivo','Target', "Alvo"),a,'target')),row(field(w('Tipo','Type', "Tipo"),a,'kind'),field(w('Notas de alcance','Scope notes', "Notas de escopo"),a,'notes')),button(w('Eliminar activo','Delete asset', "Excluir ativo"),()=>{
      if(!confirm(w('¿Eliminar el activo y sus vínculos con hallazgos y cobertura?','Delete the asset and its finding/coverage links?', "Excluir o ativo e seus vínculos com achados/cobertura?")))return;
      S.data.findings.forEach(f=>{f.asset_uids=(f.asset_uids||[]).filter(x=>x!==a.uid);});(S.data.coverage||[]).forEach(c=>{if(c.asset_uid===a.uid)c.asset_uid='';});rows.splice(i,1);scheduleSave();renderMain();
    }))));
    box.append(button(w('Añadir activo','Add asset', "Adicionar ativo"),()=>{rows.push({uid:uid(),name:'',target:'',kind:'URL',notes:''});scheduleSave();renderMain();},true));
    box.querySelectorAll(':scope > .wf-card').forEach((c,i)=>{c.dataset.workflowIndex=i;});
    reportOptions(box,['include_assets']);
  }
  function coverage(box){
    const rows=S.data.coverage||(S.data.coverage=[]);const targets=[['',w('General','General', "Geral")],...(S.data.assets||[]).map(a=>[a.uid,a.name+' · '+a.target])];
    rows.forEach((c,i)=>box.append(card(field(w('Prueba / control','Test / control', "Teste / controle"),c,'test'),row(selectField(w('Activo','Asset', "Ativo"),c,'asset_uid',targets),selectField(w('Estado','Status', "Status"),c,'status',cover)),field(w('Resultado o impedimento','Result or blocker', "Resultado ou impedimento"),c,'notes',{area:true}),ProgressUI.inventoryReview(c),button(w('Eliminar prueba','Delete test', "Excluir teste"),()=>{rows.splice(i,1);scheduleSave();renderMain();}))));
    box.querySelectorAll(':scope > .wf-card').forEach((c,i)=>{c.dataset.workflowIndex=i;});
    box.append(button(w('Añadir prueba','Add test', "Adicionar teste"),()=>{rows.push({uid:uid(),test:'',asset_uid:'',status:'pending',notes:''});scheduleSave();renderMain();},true),card(mdEditor(w('Limitaciones del trabajo','Engagement limitations', "Limitações do trabalho"),S.data,'limitations_md')));reportOptions(box,['include_coverage']);
  }
  function rootCauseSelector(f,onChange){
    const groups=S.data.root_cause_groups||[];
    const control=selectField(w('Grupo de causa raíz','Root cause group', "Grupo de causa raiz"),f,'root_cause_uid',[
      ['',w('Sin grupo','No group', "Sem grupo")],...groups.map(g=>[g.uid,g.name||w('Grupo sin nombre','Unnamed group', "Grupo sem nome")])]);
    control.querySelector('select').dataset.rootCauseFinding=f.uid;
    if(onChange)control.querySelector('select').addEventListener('change',onChange);
    return control;
  }
  function rootCauses(box){
    const groups=S.data.root_cause_groups||[];
    box.append(hint('Relaciona hallazgos con una misma causa y acción común. Cada hallazgo conserva su ID, severidad, evidencias, responsable y retests. La acción común no sustituye las correcciones específicas.','Relate findings with a shared cause and action. Each finding keeps its ID, severity, evidence, owner and retests. The shared action does not replace finding-specific fixes.', "Relacione achados com causa e ação compartilhadas. Cada achado mantém seu ID, severidade, evidências, responsável e retestes. A ação compartilhada não substitui as correções específicas de cada achado."));
    const draft={name:''},create=button(w('Crear grupo','Create group', "Criar grupo"),()=>{
      const name=draft.name.trim();if(!name||name.length>200)throw Error(w('Escribe un nombre de 1 a 200 caracteres.','Enter a name of 1 to 200 characters.', "Informe um nome de 1 a 200 caracteres."));
      if(groups.length>=1000)throw Error(w('Máximo 1000 grupos.','Maximum 1000 groups.', "Máximo de 1000 grupos."));
      const group={uid:uid(),name,cause_md:'',remediation_md:''};S.data.root_cause_groups=groups;groups.push(group);scheduleSave();renderMain();
      requestAnimationFrame(()=>document.querySelector('[data-root-cause-group="'+group.uid+'"] [data-field="cause_md"]')?.focus());
    },true);create.dataset.rootCauseCreate='';
    const name=localField(w('Nombre del nuevo grupo','New group name', "Nome do novo grupo"),draft,'name');name.querySelector('input').maxLength=200;
    box.append(card(row(name,create)));
    const memberBoxes=new Map();
    function updateMembers(){
      for(const group of groups){
        const list=memberBoxes.get(group.uid);if(!list)continue;
        const members=(S.data.findings||[]).filter(f=>f.root_cause_uid===group.uid);
        list.replaceChildren(h('p',{},w('Hallazgos vinculados: ','Linked findings: ', "Achados vinculados: ")+members.length));
        if(!members.length)list.append(hint('Asigna hallazgos abajo o desde la ficha de cada hallazgo.','Assign findings below or from each finding’s tracking panel.', "Atribua achados abaixo ou pelo painel de acompanhamento de cada achado."));
        else list.append(h('ul',{},...members.map(f=>h('li',{},button(f.id+' · '+(f.title||''),()=>select('finding',S.data.findings.indexOf(f)))))));
      }
    }
    groups.forEach((group,index)=>{
      const members=h('div',{'data-root-cause-members':group.uid});memberBoxes.set(group.uid,members);
      const remove=button(w('Eliminar grupo','Delete group', "Excluir grupo"),()=>{
        if(!confirm(w('¿Eliminar este grupo y quitar sus vínculos? Los hallazgos, evidencias y retests se conservan.','Delete this group and remove its links? Findings, evidence and retests are retained.', "Excluir este grupo e remover seus vínculos? Achados, evidências e retestes serão mantidos.")))return;
        (S.data.findings||[]).forEach(f=>{if(f.root_cause_uid===group.uid)delete f.root_cause_uid;});
        groups.splice(groups.indexOf(group),1);scheduleSave();renderMain();
      });remove.dataset.rootCauseDelete=group.uid;
      const item=card(field(w('Nombre del grupo','Group name', "Nome do grupo"),group,'name',{onChange:()=>{for(const option of box.querySelectorAll('select[data-root-cause-finding] option'))if(option.value===group.uid)option.textContent=group.name||w('Grupo sin nombre','Unnamed group', "Grupo sem nome");}}),field(w('Causa raíz','Root cause', "Causa raiz"),group,'cause_md',{area:true}),field(w('Acción común','Shared action', "Ação compartilhada"),group,'remediation_md',{area:true}),members,
        h('details',{},h('summary',{},w('Referencia permanente del grupo','Permanent group reference', "Referência permanente do grupo")),h('code',{},group.uid)),remove);
      item.dataset.workflowIndex=index;item.dataset.rootCauseGroup=group.uid;item.querySelector('[data-field="name"]').maxLength=200;
      for(const key of ['cause_md','remediation_md'])item.querySelector('[data-field="'+key+'"]').maxLength=16000;
      box.append(item);
    });
    updateMembers();
    if(groups.length){
      const assignment=card(h('h3',{},w('Asignar hallazgos','Assign findings', "Atribuir achados"))),search=h('input',{type:'search','aria-label':w('Filtrar hallazgos para agrupar','Filter findings to group', "Filtrar achados para o grupo"),placeholder:w('Buscar por ID o título','Search by ID or title', "Pesquisar por ID ou título"),'data-root-cause-search':''}),list=h('div',{'data-root-cause-assignments':''}),pager=h('div',{});
      let page=0;function draw(){
        const query=search.value.trim().toLocaleLowerCase(),findings=(S.data.findings||[]).filter(f=>(f.id+' '+(f.title||'')).toLocaleLowerCase().includes(query)),size=20;
        page=Math.min(page,Math.max(0,Math.ceil(findings.length/size)-1));list.replaceChildren();pager.replaceChildren();
        for(const f of findings.slice(page*size,(page+1)*size))list.append(row(h('span',{},f.id+' · '+(f.title||'')),rootCauseSelector(f,updateMembers)));
        if(!findings.length)list.append(hint('No hay hallazgos que coincidan.','No matching findings.', "Nenhum achado correspondente."));
        if(findings.length>size)pager.append(workspacePageBar('root-cause-assignments',findings.length,page,size,next=>{page=next;draw();}));
      }
      search.addEventListener('input',()=>{page=0;draw();});assignment.append(search,list,pager);box.append(assignment);draw();
      reportOptions(box,['include_root_causes']);
    }
  }
  function retest(box){
    const findings=S.data.findings||[];
    box.append(hint('Una corrección comunicada por el cliente no equivale a una corrección verificada. Registra la comprobación y su evidencia.','A client-reported fix is distinct from a verified fix. Record the verification and its evidence.', "Uma correção informada pelo cliente é diferente de uma correção verificada. Registre a verificação e sua evidência."));
    findings.forEach(f=>{
      const c=card(button(f.id+' · '+(f.title||''),()=>select('finding',findings.indexOf(f))),row(field(w('Responsable','Owner', "Responsável"),f,'owner'),field(w('Fecha objetivo','Due date', "Prazo"),f,'due_date',{type:'date'}),selectField(w('Estado','Status', "Status"),f,'status',statuses)));
      (f.retests||[]).forEach(r=>c.append(h('details',{},h('summary',{},r.tested_on+' · '+w(...(results.find(x=>x[0]===r.result)||['','—','—', "—"]).slice(1))+' · '+r.assessor),h('p',{},r.notes_md),...(r.evidence_uids||[]).map(id=>{const e=(S.data.evidence||[]).find(x=>x.uid===id);return e?h('img',{class:'wf-thumb',src:url('/'+e.src),alt:e.caption||e.title}):null;}))));
      const form={finding_uid:f.uid,tested_on:new Date().toISOString().slice(0,10),assessor:S.data.meta.assessor||'',result:'open',notes_md:'',evidence_uids:[]};
      const details=h('details',{open:S.retestFinding===f.uid?'':null},h('summary',{},w('Registrar retest','Record retest', "Registrar reteste")),row(localField(w('Fecha','Date', "Data"),form,'tested_on','date'),localField(w('Evaluador','Assessor', "Avaliador"),form,'assessor')),selectField(w('Resultado','Result', "Resultado"),form,'result',results,false),localField(w('Procedimiento y resultado observado','Procedure and observed result', "Procedimento e resultado observado"),form,'notes_md','textarea'),links(w('Evidencias del retest','Retest evidence', "Evidência do reteste"),form,'evidence_uids',S.data.evidence||[],false),button(w('Guardar comprobación','Save verification', "Salvar verificação"),async()=>{await mutate('/retest',form);},true));
      c.append(details);box.append(c);
    });
    if(!findings.length)box.append(hint('Añade un hallazgo para registrar correcciones.','Add a finding to track remediation.', "Adicione um achado para acompanhar a correção."));
    reportOptions(box,['include_retest']);
    box.append(button(w('Exportar informe con retest','Export report with retest', "Exportar relatório com reteste"),async()=>{S.data.report.workflow=S.data.report.workflow||{};S.data.report.workflow.include_retest=true;scheduleSave();await exportFile($('#exportFormat').value);},true));
  }
  function reportOptions(box,keys){
    const cfg=S.data.report.workflow||{};const labels={include_assets:['Incluir activos en el informe','Include assets in report', "Incluir ativos no relatório"],include_coverage:['Incluir cobertura y limitaciones','Include coverage and limitations', "Incluir cobertura e limitações"],include_retest:['Incluir seguimiento y retest','Include tracking and retest', "Incluir acompanhamento e retestes"],include_root_causes:['Incluir causas raíz y acciones comunes en el informe','Include root causes and shared actions in report', "Incluir causas raiz e ações compartilhadas no relatório"]};
    box.append(card(...keys.map(k=>check(w(...labels[k]),k==='include_root_causes'?cfg[k]===true:cfg[k]!==false,v=>{S.data.report.workflow=S.data.report.workflow||cfg;cfg[k]=v;scheduleSave();}))));
  }
  function evidenceCard(e,slug,editable=false){
    const c=card(h('img',{class:'wf-thumb',src:url('/'+e.src,slug),alt:e.caption||e.title||w('Evidencia vinculada','Linked evidence', "Evidências vinculadas"),loading:'lazy'}),...(editable?[field(w('Título','Title', "Título"),e,'title'),field(w('Pie de imagen','Caption', "Legenda"),e,'caption')]:[h('h4',{},e.title||w('Sin título','Untitled', "Sem título")),h('p',{},e.caption||'')]));
    c.dataset.evidenceUid=e.uid;
    return c;
  }
  function evidenceActions(e,slug){
    const current=fn=>()=>{if(S.slug!==slug)throw Error(w('Vuelve a abrir la evidencia del proyecto activo.','Reopen evidence in the active project.', "Reabra a evidência no projeto ativo."));return fn();};
    return row(button(w('Anotar / censurar','Annotate / redact', "Anotar / ocultar dados"),current(()=>annotations(e))),button(w('Descargar original','Download original', "Baixar original"),current(()=>download(url('/evidence/'+e.uid+'/original',slug),'original-'+e.src.split('/').pop()))));
  }
  function findingEvidence(box,findingUid){
    box.replaceChildren();const slug=S.slug;
    const finding=(S.data.findings||[]).find(f=>f.uid===findingUid);
    if(!finding){box.append(hint('Este hallazgo ya no está en el proyecto activo.','This finding is no longer in the active project.', "Este achado não está mais no projeto ativo."));return;}
    const linked=[...new Set(finding.evidence_uids||[])],pool=new Map((S.data.evidence||[]).map(e=>[e.uid,e]));
    box.append(hint('Los informes usan la copia procesada. El original se conserva por separado y puede contener información privada.','Reports use the processed copy. The original is kept separately and may contain private information.', "Os relatórios usam a cópia processada. O original é mantido separadamente e pode conter informações privadas."));
    if(!linked.length)box.append(hint('Este hallazgo no tiene evidencias vinculadas. Selecciónalas arriba o regístralas en Evidencias.','This finding has no linked evidence. Select it above or register it in Evidence.', "Este achado não tem evidências vinculadas. Selecione-as acima ou cadastre-as em Evidências."));
    const controls=h('div',{}),gallery=h('div',{class:'wf-gallery'});box.append(controls,gallery);
    const pageSize=linked.length>50?20:50;let page=0;
    function draw(){
      controls.replaceChildren();gallery.replaceChildren();
      if(linked.length>pageSize)controls.append(workspacePageBar('finding-evidence-'+findingUid,linked.length,page,pageSize,next=>{page=next;draw();}));
      linked.slice(page*pageSize,(page+1)*pageSize).forEach(id=>{const e=pool.get(id);if(!e){gallery.append(card(h('p',{},w('Referencia de evidencia ausente: ','Missing evidence reference: ', "Referência de evidência ausente: ")+id)));return;}const c=evidenceCard(e,slug);c.append(evidenceActions(e,slug));gallery.append(c);});
    }
    draw();
  }
  async function evidence(box,slug){
    if(!await doSave())return;
    const {body}=await requestJson(url('/evidence',slug));if(!box.isConnected||S.slug!==slug)return;
    box.append(hint('Vincula cada evidencia a uno o varios hallazgos. Los informes usan la copia procesada. Los respaldos editables incluyen originales e historial.','Link evidence to one or more findings. Reports use the processed copy. Editable backups contain originals and history.', "Vincule evidências a um ou mais achados. Os relatórios usam a cópia processada. Backups editáveis contêm originais e histórico."));
    box.append(button(w('Subir evidencia','Upload evidence', "Enviar evidência"),()=>pick('image/png,image/jpeg,image/webp,image/gif',async file=>{
      const source=await sendImage(file);if(source)await mutate('/evidence',{src:source.src,title:file.name});
    }),true));
    const gallery=h('div',{class:'wf-gallery'}), galleryControls=h('div',{});box.append(galleryControls,gallery);
    const evidence=S.data.evidence||[], findings=S.data.findings||[], pageSize=evidence.length>50?20:50;
    let page=0;
    function draw(){
      gallery.replaceChildren();galleryControls.replaceChildren();
      page=Math.max(0,Math.min(Math.max(0,Math.ceil(evidence.length/pageSize)-1),page));
      if(evidence.length>pageSize)galleryControls.append(workspacePageBar('evidence',evidence.length,page,pageSize,next=>{page=next;draw();}));
      evidence.slice(page*pageSize,(page+1)*pageSize).forEach((e,offset)=>{
        const index=page*pageSize+offset;
        const c=evidenceCard(e,slug,true);
        c.dataset.workflowIndex=index;c.dataset.evidenceUid=e.uid;
        const refs=h('fieldset',{class:'wf-links'},h('legend',{},w('Usada en hallazgos','Used in findings', "Usada em achados")));
        function findingCheck(f){
          const control=check(f.id+' · '+f.title,(f.evidence_uids||[]).includes(e.uid),v=>{f.evidence_uids=v?[...new Set([...(f.evidence_uids||[]),e.uid])]:(f.evidence_uids||[]).filter(x=>x!==e.uid);scheduleSave();});
          control.querySelector('input').dataset.findingUid=f.uid;return control;
        }
        if(findings.length<=50)findings.forEach(f=>refs.append(findingCheck(f)));
        else{
          const details=h('details',{'data-evidence-associations':''}), summary=h('summary',{},w('Consultar / cambiar vínculos','Review / change links', "Revisar / alterar vínculos"));
          const list=h('div',{}), controls=h('div',{});let filter='', findingPage=0, loaded=false;
          const search=h('input',{type:'search','aria-label':w('Buscar hallazgo para vincular','Search finding to link', "Pesquisar achado para vincular"),placeholder:w('ID o título del hallazgo','Finding ID or title', "ID ou título do achado"),oninput:event=>{filter=event.target.value.trim().toLocaleLowerCase();findingPage=0;drawLinks();}});
          function drawLinks(){
            const matches=findings.filter(f=>!filter||(f.id+' '+f.title).toLocaleLowerCase().includes(filter));
            findingPage=Math.max(0,Math.min(Math.max(0,Math.ceil(matches.length/50)-1),findingPage));
            list.replaceChildren();controls.replaceChildren();
            if(matches.length>50)controls.append(workspacePageBar('evidence-links-'+e.uid,matches.length,findingPage,50,next=>{findingPage=next;drawLinks();}));
            else controls.append(h('p',{role:'status'},matches.length+' '+w('hallazgos','findings', "achados")));
            matches.slice(findingPage*50,(findingPage+1)*50).forEach(f=>list.append(findingCheck(f)));
          }
          details.append(summary,hint('Solo esta lista cambia de página. Todos los hallazgos y sus vínculos se conservan en el proyecto y en la exportación.','Only this list is paged. Every finding and its links remain in the project and export.', "Somente esta lista é paginada. Todos os achados e seus vínculos permanecem no projeto e na exportação."),search,controls,list);
          details.addEventListener('toggle',()=>{if(details.open&&!loaded){loaded=true;drawLinks();}});
          refs.append(details);
        }
        c.append(refs);
        c.append(evidenceActions(e,slug));gallery.append(c);
      });
    }
    box.addEventListener('report-gen:evidence-page',event=>{const index=event.detail?.index;if(Number.isInteger(index)&&index>=0&&index<evidence.length){page=Math.floor(index/pageSize);draw();}});
    draw();
    if(body.unlinked.length){
      const controls=h('div',{}),unregistered=h('div',{class:'wf-gallery','data-unregistered-evidence':''});let unregisteredPage=0;
      function drawUnregistered(){
        controls.replaceChildren();unregistered.replaceChildren();
        if(body.unlinked.length>50)controls.append(workspacePageBar('unregistered-evidence',body.unlinked.length,unregisteredPage,20,next=>{unregisteredPage=next;drawUnregistered();}));
        const size=body.unlinked.length>50?20:50;
        body.unlinked.slice(unregisteredPage*size,(unregisteredPage+1)*size).forEach(e=>unregistered.append(card(h('img',{class:'wf-thumb',src:url('/'+e.src,slug),alt:e.src,loading:'lazy'}),button(w('Registrar en la galería','Register in gallery', "Cadastrar na galeria"),()=>mutate('/evidence',{src:e.src,title:e.src.split('/').pop()})))));
      }
      box.append(h('h3',{},w('Imágenes del proyecto sin registrar','Unregistered project images', "Imagens do projeto não cadastradas")),controls,unregistered);drawUnregistered();
    }
  }
  function modal(titleText,...children){
    const previous=document.activeElement===document.body?modalTrigger:document.activeElement;
    const close=()=>{if(m.open)m.close();};
    const m=h('dialog',{class:'modal','aria-label':titleText},h('div',{class:'modal-box wide'},row(h('h3',{},titleText),button(w('Cerrar','Close', "Fechar"),close)),...children));
    m.addEventListener('close',()=>{
      m.remove();
      requestAnimationFrame(()=>{
        const parent=[...document.querySelectorAll('dialog[open]')].at(-1);
        const target=previous?.closest('details:not([open])')?.querySelector('summary')||previous;
        (target?.isConnected&&!target.disabled&&(!parent||parent.contains(target))?target:parent?.querySelector('button')||$('#editor'))?.focus({preventScroll:true});
      });
    });m.closeModal=close;document.body.append(m);m.showModal();return m;
  }
  function annotations(e){
    const slug=S.slug;const operations=[];let start=null;const mode={type:'redact',text:''};
    const area=h('div',{class:'wf-image-editor'});const image=h('img',{src:url('/'+e.src,slug),alt:e.title,draggable:'false'});area.append(image);const list=h('div',{});
    const redraw=()=>{
      area.querySelectorAll('.wf-overlay').forEach(n=>n.remove());list.replaceChildren();
      operations.forEach((op,i)=>{
        area.append(h('div',{class:'wf-overlay '+op.type,style:`left:${op.x*100}%;top:${op.y*100}%;width:${op.w*100}%;height:${op.h*100}%`},op.type==='text'?op.text:op.type==='arrow'?'↘':''));
        const r=row(h('strong',{},(i+1)+': '+op.type));['x','y','w','h'].forEach(k=>{const inp=h('input',{type:'number',value:(op[k]*100).toFixed(2),min:0,max:100,step:0.1,'aria-label':k+' %',onchange:ev=>{op[k]=Number(ev.target.value)/100;redraw();}});r.append(h('label',{},k+' %',inp));});r.append(button(w('Quitar','Remove', "Remover"),()=>{operations.splice(i,1);redraw();}));list.append(r);
      });
    };
    function point(event){const rect=area.getBoundingClientRect();return{x:Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))};}
    area.addEventListener('pointerdown',ev=>{ev.preventDefault();start=point(ev);area.setPointerCapture?.(ev.pointerId);});
    area.addEventListener('pointerup',ev=>{if(!start)return;const end=point(ev);const op={type:mode.type,x:Math.min(start.x,end.x),y:Math.min(start.y,end.y),w:Math.abs(end.x-start.x),h:Math.abs(end.y-start.y),text:mode.text};start=null;if(op.w>.001&&op.h>.001){operations.push(op);redraw();}});
    const m=modal(w('Anotar y censurar evidencia','Annotate and redact evidence', "Anotar e ocultar dados nas evidências"),hint('Arrastra sobre la imagen para marcar una zona. La censura negra se aplica a los píxeles al guardar; no se puede quitar de esa copia. El original se conserva por separado.','Drag on the image to mark an area. Black redaction is applied to pixels on save and cannot be removed from that copy. The original is retained separately.', "Arraste sobre a imagem para marcar uma área. A ocultação preta é aplicada aos pixels ao salvar e não pode ser removida dessa cópia. O original é mantido separadamente."),row(selectField(w('Herramienta','Tool', "Ferramenta"),mode,'type',[['redact','Censura negra','Black redaction', "Ocultação preta"],['box','Recuadro','Box', "Retângulo"],['arrow','Flecha','Arrow', "Seta"],['text','Texto','Text', "Texto"]],false),localField(w('Texto de anotación','Annotation text', "Texto da anotação"),mode,'text')),area,button(w('Añadir zona con coordenadas','Add area by coordinates', "Adicionar área por coordenadas"),()=>{operations.push({type:mode.type,x:.1,y:.1,w:.3,h:.15,text:mode.text});redraw();}),list,button(w('Aplicar y guardar copia','Apply and save copy', "Aplicar e salvar cópia"),async()=>{
      if(S.slug!==slug)throw Error(w('Vuelve a abrir la evidencia del proyecto activo.','Reopen evidence in the active project.', "Reabra a evidência no projeto ativo."));await mutate('/evidence/'+e.uid+'/edit',{operations});m.closeModal();
    },true));
  }
  function backup(box){
    box.append(card(h('h3',{},w('Proyecto editable completo','Complete editable project', "Projeto editável completo")),hint('Incluye YAML, imágenes, originales, configuración del informe y versiones. Este respaldo contiene información interna y no es el archivo de entrega al cliente.','Includes YAML, images, originals, report settings and versions. This backup contains internal information and is separate from the client deliverable.', "Inclui YAML, imagens, originais, configurações do relatório e versões. Este backup contém informações internas e é separado da entrega ao cliente."),button(w('Descargar respaldo ZIP','Download ZIP backup', "Baixar backup ZIP"),async()=>{const slug=S.slug;if(await doSave())await download(url('/bundle',slug),slug+'-project.zip');},true),button(w('Importar como otro proyecto','Import as another project', "Importar como outro projeto"),importProject)),hint('Límites: ZIP de 256 MiB; contenido descomprimido de 512 MiB y 20.000 archivos. La biblioteca global se exporta desde Biblioteca.','Limits: 256 MiB ZIP; 512 MiB expanded and 20,000 files. Export the global library from Finding library.', "Limites: ZIP de 256 MiB; 512 MiB descompactados e 20.000 arquivos. Exporte a biblioteca global pela Biblioteca de achados."));
  }
  async function importProject(){pick('.zip,application/zip',async file=>{
    const slug=prompt(w('Nombre del proyecto importado (se creará una copia):','Imported project name (creates a copy):', "Nome do projeto importado (cria uma cópia):"),file.name.replace(/(-project)?\.zip$/i,''));if(slug===null)return;
    const data=new FormData();data.append('file',file);data.append('slug',slug);
    const {body}=await requestJson('/api/projects/import',{method:'POST',body:data});await refreshProjects();await loadProject(body.slug);toast(w('Proyecto importado','Project imported', "Projeto importado"),'ok');
  });}
  async function library(box){
    const {body,etag}=await requestJson('/api/library');libraryTag=etag;if(!box.isConnected)return;
    box.append(hint('Las plantillas se guardan junto a la herramienta. Revisa su texto para retirar datos del cliente antes de reutilizarlas. Variables: {{cliente}}, {{objetivo}}, {{evaluador}} o nombres propios.','Templates are saved with the tool. Review their text to remove client data before reuse. Variables: {{cliente}}, {{objetivo}}, {{evaluador}}, or custom names.', "Os modelos são salvos com a ferramenta. Revise seus textos para remover dados de clientes antes de reutilizá-los. Variáveis: {{cliente}}, {{objetivo}}, {{evaluador}} ou nomes personalizados."));
    const search=h('input',{type:'search',placeholder:w('Buscar por nombre, etiqueta o contenido','Search name, tag or content', "Pesquisar nome, etiqueta ou conteúdo"),'aria-label':w('Buscar plantillas','Search templates', "Pesquisar modelos")});const list=h('div',{});
    function draw(){const q=search.value.trim().toLowerCase();list.replaceChildren();body.templates.filter(e=>JSON.stringify([e.name,e.tags,e.content]).toLowerCase().includes(q)).forEach(e=>list.append(card(h('h3',{},e.name),h('p',{},e.tags.join(' · ')),h('small',{},'v'+e.versions.length+' · '+new Date(e.updated).toLocaleString(languageTag(S.uiLang))),row(button(w('Insertar','Insert', "Inserir"),()=>insertTemplate(e),true),button(w('Editar / versiones','Edit / versions', "Editar / versões"),()=>editTemplate(e)),button(w('Eliminar','Delete', "Excluir"),async()=>{if(confirm(w('¿Eliminar esta plantilla?','Delete this template?', "Excluir este modelo?"))){await requestJson('/api/library/'+e.uid,{method:'DELETE',headers:{'If-Match':libraryTag}});renderMain();}})))));if(!list.childNodes.length)list.append(hint('No hay plantillas que coincidan. Guarda una desde el botón Plantilla de un hallazgo.','No matching templates. Save one using the Template button in a finding.', "Nenhum modelo correspondente. Salve um usando o botão Modelo em um achado."));}
    search.addEventListener('input',draw);box.append(search,row(button(w('Nueva plantilla','New template', "Novo modelo"),()=>editTemplate({name:'',tags:[],content:{mode:'vuln',title:'',severity:'info',description_md:'',impact_md:'',remediation_md:'',walkthrough:[]}})),button(w('Exportar biblioteca','Export library', "Exportar biblioteca"),()=>jsonDownload(body,'report-gen-library.json')),button(w('Importar biblioteca','Import library', "Importar biblioteca"),()=>pick('.json,application/json',async file=>{await requestJson('/api/library/import',{method:'POST',headers:{'Content-Type':'application/json','If-Match':libraryTag},body:await file.text()});renderMain();}))),list);
    let old=[];try{old=JSON.parse(localStorage.getItem('rg.findingLib')||'[]');}catch(_){}
    if(Array.isArray(old)&&old.length)box.append(card(h('h3',{},w('Plantillas antiguas de este navegador','Legacy templates in this browser', "Modelos legados neste navegador")),hint('Revisa y guarda cada plantilla. Los datos originales del navegador se mantienen hasta que tú los retires.','Review and save each template. Original browser data remains until you remove it.', "Revise e salve cada modelo. Os dados originais do navegador permanecem até você removê-los."),...old.map(e=>button(e.__name||e.title||w('Plantilla','Template', "Modelo"),()=>saveTemplate(e)))));
    draw();
  }
  async function saveTemplate(f){
    const context={cliente:S.data.meta.client||'',objetivo:f.affected||f.host?.ip||'',evaluador:S.data.meta.assessor||''};
    const {body}=await requestJson('/api/library/sanitize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({finding:f,context})});
    await editTemplate({name:f.__name||f.title||'',tags:[],content:body.content});
  }
  async function editTemplate(entry){
    const {etag}=await requestJson('/api/library');const draft=clone(entry);draft.tagsText=(draft.tags||[]).join(', ');
    let advancedDirty=false;const visual=h('div',{'data-template-editor':'visual'}),preview=h('div',{class:'template-preview',hidden:''});
    const raw=h('textarea',{rows:15,'aria-label':w('Contenido avanzado JSON','Advanced JSON content', "Conteúdo JSON avançado"),oninput:()=>{advancedDirty=true;}});
    function stepsEditor(steps){
      const box=h('div',{});
      const draw=()=>{
        box.replaceChildren();steps.forEach((s,i)=>box.append(h('div',{class:'template-step'},h('strong',{},w('Paso ','Step ', "Etapa ")+(i+1)),
          localField(w('Título del paso','Step title', "Título da etapa"),s,'lead'),localField(w('Procedimiento y resultado observado','Procedure and observed result', "Procedimento e resultado observado"),s,'text_md','textarea'),
          localField(w('Comando o petición (texto)','Command or request (text)', "Comando ou requisição (texto)"),s,'command','textarea'),
          button(w('Quitar paso','Remove step', "Remover etapa"),()=>{steps.splice(i,1);draw();}))));
        box.append(button(w('Añadir paso','Add step', "Adicionar etapa"),()=>{steps.push({lead:'',text_md:'',command:''});draw();}));
      };draw();return box;
    }
    function draw(){
      const c=draft.content;c.mode=c.mode||'vuln';visual.replaceChildren();preview.hidden=true;
      const mode=selectField(w('Tipo','Type', "Tipo"),c,'mode',[['vuln','Vulnerabilidad','Vulnerability', "Vulnerabilidade"],['machine','Máquina / laboratorio','Machine / lab', "Máquina / laboratório"]],false);
      mode.querySelector('select').addEventListener('change',draw);
      visual.append(mode,localField(w('Título del hallazgo','Finding title', "Título do achado"),c,'title'));
      if(c.mode==='machine'){
        visual.append(localField(w('Ruta de ataque / resumen','Attack path / summary', "Caminho de ataque / resumo"),c,'summary_md','textarea'));
        const phases=h('div',{});c.phases=c.phases||[];
        c.phases.forEach((phase,i)=>{phase.steps=phase.steps||[];phases.append(card(localField(w('Fase','Phase', "Fase"),phase,'name'),stepsEditor(phase.steps),button(w('Quitar fase','Remove phase', "Remover fase"),()=>{c.phases.splice(i,1);draw();})));});
        visual.append(phases,button(w('Añadir fase','Add phase', "Adicionar fase"),()=>{c.phases.push({name:'',steps:[]});draw();}));
      }else{
        visual.append(row(selectField(w('Severidad','Severity', "Severidade"),c,'severity',[['info','Informativa','Informational', "Informativa"],['low','Baja','Low','Baixa'],['medium','Media','Medium', "Média"],['high','Alta','High','Alta'],['critical','Crítica','Critical', "Crítica"]],false),localField('CWE',c,'cwe')),
          localField(w('Vector CVSS (opcional)','CVSS vector (optional)', "Vetor CVSS (opcional)"),c,'cvss_vector'),localField(w('Puntuación CVSS','CVSS score', "Pontuação CVSS"),c,'cvss','number'),
          button(w('Calcular desde el vector','Calculate from vector', "Calcular a partir do vetor"),async()=>{
            const vector=(c.cvss_vector||'').trim();const {body}=await requestJson('/api/cvss',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({vector})});
            if(draft.content!==c||c.cvss_vector.trim()!==vector)return;
            c.cvss=body.score;c.severity=body.severity;c.cvss_version=vector.startsWith('CVSS:4.0/')?'4.0':'3.1';draw();
          }),
          h('details',{},h('summary',{},w('Ayuda para redactar','Writing guidance', "Orientações de redação")),hint('Describe qué control falló, qué observaste y qué impacto puedes demostrar. Indica cómo reproducirlo y cómo comprobar la corrección.','Describe the failed control, observed behavior and demonstrated impact. Explain reproduction and how to verify the fix.', "Descreva o controle que falhou, o comportamento observado e o impacto demonstrado. Explique a reprodução e como verificar a correção.")),
          localField(w('Descripción (Markdown)','Description (Markdown)', "Descrição (Markdown)"),c,'description_md','textarea'),
          localField(w('Impacto demostrado (Markdown)','Demonstrated impact (Markdown)', "Impacto demonstrado (Markdown)"),c,'impact_md','textarea'),
          localField(w('Remediación (Markdown)','Remediation (Markdown)', "Correção (Markdown)"),c,'remediation_md','textarea'));
        c.walkthrough=c.walkthrough||[];visual.append(h('h4',{},w('Pasos de reproducción','Reproduction steps', "Etapas de reprodução")),stepsEditor(c.walkthrough));
      }
      const refs=h('textarea',{'data-field':'references',rows:3,oninput:e=>{c.references=e.target.value.split('\n').filter(x=>x.trim());}});refs.value=(c.references||[]).join('\n');
      visual.append(h('label',{},w('Referencias, una por línea','References, one per line', "Referências, uma por linha"),refs));
    }
    draw();
    let insertionField=null;
    visual.addEventListener('focusin',e=>{if(e.target.matches('textarea,input[type="text"]'))insertionField=e.target;});
    const variables=h('div',{class:'template-toolbar'},h('span',{},w('Insertar variable en el campo activo: ','Insert variable in the active field: ', "Inserir variável no campo ativo: ")));
    ['cliente','objetivo','evaluador','endpoint'].forEach(key=>variables.append(button('{{'+key+'}}',()=>{
      if(!insertionField?.isConnected)throw Error(w('Selecciona primero un campo de texto del hallazgo.','Select a finding text field first.', "Selecione primeiro um campo de texto do achado."));
      const target=insertionField;target.setRangeText('{{'+key+'}}',target.selectionStart,target.selectionEnd,'end');
      target.dispatchEvent(new Event('input',{bubbles:true}));target.focus();
    })));
    const advanced=h('details',{},h('summary',{},w('Edición avanzada JSON','Advanced JSON editing', "Edição avançada de JSON")),raw,
      button(w('Aplicar JSON al formulario','Apply JSON to form', "Aplicar JSON ao formulário"),()=>{
        const value=JSON.parse(raw.value);
        const validSteps=a=>Array.isArray(a)&&a.every(s=>s&&typeof s==='object'&&!Array.isArray(s));
        if(!value||typeof value!=='object'||Array.isArray(value)||
           (value.walkthrough!==undefined&&!validSteps(value.walkthrough))||
           (value.phases!==undefined&&(!validSteps(value.phases)||value.phases.some(p=>p.steps!==undefined&&!validSteps(p.steps))))||
           (value.references!==undefined&&(!Array.isArray(value.references)||value.references.some(r=>typeof r!=='string'))))
          throw Error(w('JSON incompatible: comprueba los pasos, fases y referencias. El formulario se conserva.','Incompatible JSON: check steps, phases and references. The form is preserved.', "JSON incompatível: verifique etapas, fases e referências. O formulário foi preservado."));
        draft.content=value;advancedDirty=false;draw();
      }));
    advanced.addEventListener('toggle',()=>{if(advanced.open&&!advancedDirty)raw.value=JSON.stringify(draft.content,null,2);});
    const checked={value:false};
    const m=modal(w('Plantilla reutilizable','Reusable template', "Modelo reutilizável"),hint('Se retiran imágenes, activos, responsables, retests y referencias internas. Revisa también descripciones, comandos y URLs.','Images, assets, owners, retests and internal references are removed. Review descriptions, commands and URLs too.', "Imagens, ativos, responsáveis, retestes e referências internas são removidos. Revise também descrições, comandos e URLs."),
      row(localField(w('Nombre','Name', "Nome"),draft,'name'),localField(w('Etiquetas, separadas por coma','Comma-separated tags', "Etiquetas separadas por vírgulas"),draft,'tagsText')),variables,visual,
      button(w('Vista previa del texto','Preview text', "Visualizar texto"),async()=>{
        const c=draft.content,source=JSON.stringify(c),text=['## '+(c.title||''),c.description_md,c.summary_md,c.impact_md,c.remediation_md].filter(Boolean).join('\n\n');
        const {body}=await requestJson('/api/md',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({text,slug:''})});
        if(source===JSON.stringify(draft.content)&&m.isConnected){preview.innerHTML=body.html;preview.hidden=false;}
      }),preview,advanced,check(w('He revisado que no contenga datos de otro cliente','I reviewed it for other client data', "Revisei a presença de dados de outros clientes"),false,v=>{checked.value=v;}),button(w('Guardar versión de plantilla','Save template version', "Salvar versão do modelo"),async()=>{
      if(!checked.value)throw Error(w('Revisa el contenido antes de guardar la plantilla.','Review the content before saving.', "Revise o conteúdo antes de salvar."));
      if(advancedDirty)throw Error(w('Aplica primero los cambios del JSON al formulario.','Apply your JSON changes to the form first.', "Aplique primeiro suas alterações de JSON ao formulário."));
      const payload={name:draft.name,tags:draft.tagsText.split(',').map(x=>x.trim()).filter(Boolean),content:draft.content};
      await requestJson('/api/library'+(entry.uid?'/'+entry.uid:''),{method:entry.uid?'PUT':'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify(payload)});m.closeModal();toast(w('Plantilla guardada','Template saved', "Modelo salvo"),'ok');if(S.sel.type==='workflow'&&S.sel.idx==='library')renderMain();
    },true));
    if(entry.versions?.length){const version={v:String(entry.versions.length)};const field=selectField(w('Cargar versión anterior para editar','Load previous version to edit', "Carregar versão anterior para editar"),version,'v',entry.versions.map(v=>[String(v.version),'v'+v.version+' · '+v.created]),false);field.querySelector('select').addEventListener('change',()=>{const chosen=entry.versions.find(v=>String(v.version)===version.v);draft.content=clone(chosen.content);advancedDirty=false;raw.value=JSON.stringify(draft.content,null,2);draw();});visual.before(field);}
  }
  function insertTemplate(entry){
    if(!S.data)throw Error(w('Abre un proyecto.','Open a project.', "Abra um projeto."));const slug=S.slug;
    const values={cliente:S.data.meta.client||'',objetivo:'',evaluador:S.data.meta.assessor||''};const keys=[...new Set(['objetivo',...(entry.variables||[])])];
    const m=modal(w('Insertar plantilla','Insert template', "Inserir modelo"),...keys.map(k=>localField(k,values,k)),button(w('Insertar en el proyecto','Insert into project', "Inserir no projeto"),async()=>{
      if(S.slug!==slug)throw Error(w('El proyecto activo cambió.','The active project changed.', "O projeto ativo mudou."));
      const {body:f}=await requestJson('/api/library/'+entry.uid+'/instantiate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({values})});
      if(S.slug!==slug)return;f.id=nextFid();S.data.findings.push(f);ensureFindingIds();scheduleSave();select('finding',S.data.findings.length-1);m.closeModal();
    },true));
  }
  return {bind,updateNav,render,findingPanel,findingEvidence,saveTemplate,openLibrary:()=>go('library'),navigateIssue,reviewControls,resetReview,reviewSnapshot,uid};
})();
