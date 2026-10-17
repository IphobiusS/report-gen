/* Explicit test plans and causal paths. Form drafts never become technical results automatically. */
const AssessmentUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt), clone=x=>JSON.parse(JSON.stringify(x));
  const names={assessment_cases:['Plan de pruebas','Test plan','Plano de testes'],assessment_paths:['Rutas de ataque','Attack paths','Caminhos de ataque']};
  const states=[['pending','Pendiente','Pending','Pendente'],['passed','Realizada sin fallo observado','Performed; no failure observed','Realizada sem falha observada'],['failed','Fallo observado','Failure observed','Falha observada'],['blocked','Bloqueada','Blocked','Bloqueada'],['not_applicable','No aplica','Not applicable','Não se aplica']];
  const causal=[['inferred','Inferida','Inferred','Inferida'],['observed','Demostrada por el analista','Demonstrated by the analyst','Demonstrada pelo analista'],['blocked','Bloqueada','Blocked','Bloqueada']];
  const specialties=[['custom','Personalizada','Custom','Personalizada'],['web','Web','Web','Web'],['api','API','API','API'],['ad','Active Directory','Active Directory','Active Directory'],['cloud','Cloud','Cloud','Cloud'],['mobile','Móvil','Mobile','Móvel'],['ai','IA / LLM','AI / LLM','IA / LLM']];
  const forms=new Map(); let form=null, pending=null, registered=false;
  const context=()=>({slug:S.slug,workspace:BrowserWorkspace.current(),viewWorkspace:S.workspace_id});
  const matches=state=>state.slug===S.slug&&state.workspace===BrowserWorkspace.current()&&state.viewWorkspace===S.workspace_id;
  const memoryKey=(slug,key,workspace=BrowserWorkspace.current())=>workspace+'|'+slug+'|'+key;
  const contextError=()=>Error(w('El contexto o contenido cambió. Conserva el borrador y vuelve a abrir la evaluación.','The context or content changed. Keep the draft and reopen the assessment.','O contexto ou conteúdo mudou. Preserve o rascunho e reabra a avaliação.'));
  const title=kind=>w(...names[kind]);
  const row=(...nodes)=>h('div',{class:'assessment-row'},...nodes);
  const card=(...nodes)=>h('section',{class:'card assessment-card'},...nodes);
  const note=(es,en,pt)=>h('p',{class:'wf-hint'},w(es,en,pt));
  function button(label,run,key,primary=false){
    const b=h('button',{type:'button',class:'btn sm'+(primary?' primary':''),'data-assessment-action':key},label);
    b.addEventListener('click',async()=>{if(projectBusyCount>0)return;b.disabled=true;try{await run();}catch(e){toast(e.message,'err');}finally{b.disabled=false;}});return b;
  }
  function input(label,obj,key,area=false){
    const value=h(area?'textarea':'input',{'data-assessment-field':key,rows:area?4:null,type:area?null:'text',oninput:e=>{obj[key]=e.target.value;}});value.value=obj[key]||'';
    return h('label',{},h('span',{},label),value);
  }
  function selectField(label,obj,key,choices){
    const e=h('select',{'data-assessment-field':key,onchange:ev=>{obj[key]=ev.target.value;}});
    for(const [value,...labels] of choices)e.append(h('option',{value},labels.length===1?labels[0]:w(...labels)));
    e.value=obj[key]||choices[0]?.[0]||'';return h('label',{},h('span',{},label),e);
  }
  function refs(label,obj,key,collection){
    const group=h('fieldset',{class:'assessment-refs','data-assessment-refs':key},h('legend',{},label));
    for(const item of S.data[collection]||[]){
      const labelText=(item.id?item.id+' · ':'')+(collection==='http_evidence'?w('HTTP privado · ','Private HTTP · ','HTTP privado · ')+(item.title||item.uid):(item.title||item.target||item.name||item.uid));
      group.append(h('label',{},h('input',{type:'checkbox',checked:(obj[key]||[]).includes(item.uid)?'':null,onchange:e=>{obj[key]=e.target.checked?[...new Set([...(obj[key]||[]),item.uid])]:(obj[key]||[]).filter(uid=>uid!==item.uid);}}),labelText));
    }
    if(!group.querySelector('input'))group.append(note('No hay registros disponibles.','No records available.','Não há registros disponíveis.'));return group;
  }
  function open(kind){select('workflow',kind);}
  function keyFor(kind,uid){return 'assessment:'+kind+':'+(uid||'new');}
  function choose(kind,item){
    const key=keyFor(kind,item?.uid),saved=[...forms.values()].find(value=>matches(value)&&value.kind===kind&&value.uid===(item?.uid||''))||forms.get(memoryKey(S.slug,key))||(PendingUI.retained(key)?.data?.workspace===BrowserWorkspace.current()?PendingUI.retained(key).data:null);
    form=saved||{kind,uid:item?.uid||'',entry:clone(item|| (kind==='case'?{title:'',specialty:'custom',status:'pending',asset_uids:[],finding_uids:[],evidence_uids:[],http_evidence_uids:[]}:{title:'',nodes:[],edges:[]})),original:item?JSON.stringify(item):null,...context()};
    form.pendingKey||=key;forms.set(memoryKey(S.slug,form.pendingKey),form);renderMain();queueMicrotask(()=>{const target=$('[data-assessment-form] [data-assessment-field=title]');target?.focus({preventScroll:true});target?.scrollIntoView({block:'start'});});
  }
  function changed(){pending?.changed();}
  async function request(path,body,method='POST',state=context()){
    if(!matches(state))throw contextError();const slug=state.slug;busyProject(true);
    try{
      if(!await doSave())throw Error(w('Guarda el proyecto antes de continuar.','Save the project before continuing.','Salve o projeto antes de continuar.'));
      if(!matches(state))throw contextError();
      const before=S.data,revision=projectStore.revision,encoded=JSON.stringify(S.data),etag=projectStore.etag;
      const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/assessment/'+path,{method,headers:{'Content-Type':'application/json','If-Match':etag},body:body===null?undefined:JSON.stringify(body)}));
      const result=await response.json();
      if(!matches(state)||S.data!==before||projectStore.revision!==revision||projectStore.etag!==etag||JSON.stringify(S.data)!==encoded||projectStore.dirty)throw contextError();
      if(result.data)await adoptSavedProject(result.data,response.headers.get('ETag')||projectStore.etag);
      return result;
    }finally{busyProject(false);}
  }
  async function saveForm(){
    const current=form,handle=pending,revision=handle?.handle.revision,payload=current?clone(current.entry):null;if(!current||!matches(current))throw contextError();
    const collection=current.kind==='case'?'test_cases':'attack_paths';
    if(current.uid&&JSON.stringify((S.data[collection]||[]).find(x=>x.uid===current.uid))!==current.original)throw Error(w('El registro cambió desde que abriste el formulario. Conserva tu borrador y vuelve a compararlo.','The record changed since you opened the form. Keep the draft and compare it again.','O registro mudou desde que você abriu o formulário. Preserve o rascunho e compare novamente.'));
    const controls=$('[data-assessment-form]');controls?.setAttribute('inert','');handle?.setBusy(true);
    try{
      const path=(current.kind==='case'?'test-cases':'attack-paths')+(current.uid?'/'+encodeURIComponent(current.uid):'');
      const result=await request(path,payload,current.uid?'PUT':'POST',current);
      current.uid=result.uid||current.uid;current.entry.uid=current.uid;current.original=JSON.stringify((result.data[collection]||[]).find(row=>row.uid===current.uid));
      const cleanup=await handle?.committed(revision);
      if(cleanup&&!cleanup.finished){await handle.changed();toast(w('La revisión enviada se guardó. Los cambios posteriores siguen pendientes en este formulario.','The submitted revision was saved. Later changes remain pending in this form.','A revisão enviada foi salva. Alterações posteriores continuam pendentes neste formulário.'));return;}
      forms.delete(memoryKey(current.slug,current.pendingKey,current.workspace));if(form===current)form=null;
      renderSidebar();renderMain();if(S.previewMode==='live')refreshLivePreview();
      toast(w('Evaluación guardada.','Assessment saved.','Avaliação salva.'),'ok');
    }finally{controls?.removeAttribute('inert');handle?.setBusy(false);}
  }
  function protect(box,current){
    const key=current.pendingKey||keyFor(current.kind,current.uid);
    pending=PendingUI.attach(key,w('Evaluación pendiente','Pending assessment','Avaliação pendente'),()=>({data:current}),{container:box,onDiscard:()=>{forms.delete(memoryKey(current.slug,key,current.workspace));form=null;renderMain();}});
    box.append(button(w('Guardar cambios','Save changes','Salvar alterações'),saveForm,'save',true));
  }
  function editorCase(box,current){
    const obj=current.entry,body=card(h('h3',{},current.uid?w('Editar caso','Edit case','Editar caso'):w('Nuevo caso','New case','Novo caso')));body.dataset.assessmentForm='case';
    body.append(input(w('Título','Title','Título'),obj,'title'),row(selectField(w('Especialidad','Specialty','Especialidade'),obj,'specialty',specialties),selectField(w('Estado','Status','Status'),obj,'status',states)),row(input(w('Metodología','Methodology','Metodologia'),obj,'methodology'),input(w('Versión de metodología','Methodology version','Versão da metodologia'),obj,'methodology_version'),input(w('ID de prueba','Test ID','ID de teste'),obj,'test_id')),
      row(input(w('Identidad / rol','Identity / role','Identidade / papel'),obj,'identity'),input(w('Organización / tenant','Organization / tenant','Organização / tenant'),obj,'tenant'),input(w('Operación','Operation','Operação'),obj,'operation')),
      input(w('Condiciones previas','Prerequisites','Pré-condições'),obj,'prerequisites',true),input(w('Resultado esperado','Expected result','Resultado esperado'),obj,'expected',true),input(w('Resultado observado o limitación','Observed result or limitation','Resultado observado ou limitação'),obj,'observed',true),input(w('Notas','Notes','Notas'),obj,'notes',true),
      note('Para finalizar, bloquear o descartar una prueba debes registrar el resultado o motivo. El estado no certifica seguridad.','To finish, block or mark a test inapplicable, record its result or reason. Status does not certify security.','Para concluir, bloquear ou marcar um teste como inaplicável, registre o resultado ou motivo. O status não certifica segurança.'),
      refs(w('Activos','Assets','Ativos'),obj,'asset_uids','assets'),refs(w('Hallazgos relacionados','Related findings','Achados relacionados'),obj,'finding_uids','findings'),refs(w('Evidencias','Evidence','Evidências'),obj,'evidence_uids','evidence'),refs(w('Evidencias HTTP','HTTP evidence','Evidências HTTP'),obj,'http_evidence_uids','http_evidence'));
    protect(body,current);box.append(body);
  }
  function localPreview(obj){
    const preview=card(h('h3',{},w('Lectura causal','Causal reading','Leitura causal'))),nodes=new Map((obj.nodes||[]).map(x=>[x.uid,x]));
    preview.append(note('Cada flecha representa una relación declarada. Las inferencias y bloqueos permanecen visibles; ninguna conexión prueba por sí sola una explotación.','Each arrow represents a declared relationship. Inferences and blockers remain visible; a connection alone does not prove exploitation.','Cada seta representa uma relação declarada. Inferências e bloqueios permanecem visíveis; uma conexão isolada não comprova exploração.'));
    for(const edge of obj.edges||[]){const label=causal.find(x=>x[0]===edge.state);preview.append(h('div',{class:'assessment-transition','data-causal-state':edge.state},h('strong',{},(nodes.get(edge.source_uid)?.title||'?')+' → '+(nodes.get(edge.target_uid)?.title||'?')),h('span',{class:'assessment-status'},label?w(...label.slice(1)):''),h('p',{},edge.observation||w('Fundamento pendiente','Rationale pending','Fundamento pendente'))));}
    if(!obj.edges?.length)preview.append(note('Añade etapas y luego sus transiciones.','Add stages and then their transitions.','Adicione etapas e depois suas transições.'));return preview;
  }
  function editorPath(box,current){
    const obj=current.entry,body=card(h('h3',{},current.uid?w('Editar ruta','Edit path','Editar caminho'):w('Nueva ruta','New path','Novo caminho')));body.dataset.assessmentForm='path';
    body.append(input(w('Título','Title','Título'),obj,'title'),input(w('Descripción','Description','Descrição'),obj,'description',true),input(w('Consecuencia','Consequence','Consequência'),obj,'consequence',true));
    const stages=h('div',{'data-assessment-stages':''}),transitions=h('div',{'data-assessment-transitions':''}),preview=h('div',{'data-assessment-causal-preview':''});
    function draw(){
      stages.replaceChildren();transitions.replaceChildren();preview.replaceChildren(localPreview(obj));
      obj.nodes.forEach((node,index)=>stages.append(card(h('h4',{},w('Etapa ','Stage ','Etapa ')+(index+1)),input(w('Nombre de la etapa','Stage name','Nome da etapa'),node,'title'),input(w('Condición o privilegio','Condition or privilege','Condição ou privilégio'),node,'privilege'),refs(w('Activos','Assets','Ativos'),node,'asset_uids','assets'),refs(w('Hallazgos','Findings','Achados'),node,'finding_uids','findings'),button(w('Eliminar etapa y sus transiciones','Delete stage and its transitions','Excluir etapa e suas transições'),()=>{if(!confirm(w('¿Eliminar esta etapa y sus transiciones del borrador?','Delete this stage and its transitions from the draft?','Excluir esta etapa e suas transições do rascunho?')))return;obj.nodes=obj.nodes.filter(x=>x.uid!==node.uid);obj.edges=obj.edges.filter(x=>x.source_uid!==node.uid&&x.target_uid!==node.uid);changed();draw();},'remove-stage'))));
      const choices=[['',w('Elige una etapa','Choose a stage','Escolha uma etapa')],...obj.nodes.map((x,i)=>[x.uid,(i+1)+'. '+(x.title||w('Sin título','Untitled','Sem título'))])];
      obj.edges.forEach((edge,index)=>transitions.append(card(h('h4',{},w('Transición ','Transition ','Transição ')+(index+1)),row(selectField(w('Desde','From','De'),edge,'source_uid',choices),selectField(w('Hasta','To','Para'),edge,'target_uid',choices),selectField(w('Estado causal','Causal state','Estado causal'),edge,'state',causal)),input(w('Condiciones previas','Prerequisites','Pré-condições'),edge,'preconditions',true),input(w('Observación o fundamento de la inferencia/bloqueo','Observation or rationale for inference/blocker','Observação ou fundamento da inferência/bloqueio'),edge,'observation',true),input(w('Medida que interrumpe esta transición','Control interrupting this transition','Medida que interrompe esta transição'),edge,'mitigation',true),refs(w('Evidencia que demuestra esta transición','Evidence demonstrating this transition','Evidência que demonstra esta transição'),edge,'evidence_uids','evidence'),refs(w('Evidencia HTTP','HTTP evidence','Evidência HTTP'),edge,'http_evidence_uids','http_evidence'),button(w('Eliminar transición','Delete transition','Excluir transição'),()=>{obj.edges=obj.edges.filter(x=>x.uid!==edge.uid);changed();draw();},'remove-edge'))));
    }
    body.append(h('h3',{},w('Etapas','Stages','Etapas')),stages,button(w('Añadir etapa','Add stage','Adicionar etapa'),()=>{if(obj.nodes.length>=40)throw Error(w('Máximo 40 etapas.','Maximum 40 stages.','Máximo de 40 etapas.'));obj.nodes.push({uid:crypto.randomUUID(),title:'',privilege:'',asset_uids:[],finding_uids:[]});changed();draw();},'add-stage'),h('h3',{},w('Transiciones explícitas','Explicit transitions','Transições explícitas')),transitions,button(w('Añadir transición','Add transition','Adicionar transição'),()=>{if(obj.nodes.length<2)throw Error(w('Añade al menos dos etapas.','Add at least two stages.','Adicione pelo menos duas etapas.'));if(obj.edges.length>=100)throw Error(w('Máximo 100 transiciones.','Maximum 100 transitions.','Máximo de 100 transições.'));obj.edges.push({uid:crypto.randomUUID(),source_uid:obj.nodes[0].uid,target_uid:obj.nodes[1].uid,state:'inferred',preconditions:'',observation:'',mitigation:'',evidence_uids:[],http_evidence_uids:[]});changed();draw();},'add-edge'),button(w('Actualizar lectura causal','Refresh causal reading','Atualizar leitura causal'),()=>draw(),'preview-path'),preview);
    draw();protect(body,current);box.append(body);
  }
  function matrixForm(box){
    const state=context(),initial={title:'',roles:'',tenants:'',operations:'',expected:'',...state},retained=PendingUI.retained('assessment:matrix')?.data,obj=retained&&matches(retained)?retained:initial;
    const section=card(h('h3',{},w('Matriz de identidades, organizaciones y operaciones','Identity, tenant and operation matrix','Matriz de identidades, organizações e operações')),note('Un valor por línea. Máximo 30 valores por eje y 300 casos por matriz. Todos se crean pendientes, sin copiar resultados ni evidencias.','One value per line. Up to 30 values per axis and 300 cases per matrix. All start pending, without copying results or evidence.','Um valor por linha. Até 30 valores por eixo e 300 casos por matriz. Todos começam pendentes, sem copiar resultados ou evidências.'),input(w('Título común','Shared title','Título comum'),obj,'title'),row(input(w('Roles','Roles','Papéis'),obj,'roles',true),input(w('Organizaciones / tenants','Organizations / tenants','Organizações / tenants'),obj,'tenants',true),input(w('Operaciones','Operations','Operações'),obj,'operations',true)),input(w('Resultado esperado','Expected result','Resultado esperado'),obj,'expected',true));
    const preview=h('div',{'data-assessment-matrix-preview':'',role:'status'});let signature=null;
    const pack=()=>({roles:obj.roles.split('\n').map(x=>x.trim()).filter(Boolean),tenants:obj.tenants.split('\n').map(x=>x.trim()).filter(Boolean),operations:obj.operations.split('\n').map(x=>x.trim()).filter(Boolean),base:{title:obj.title,specialty:'api',expected:obj.expected,status:'pending',methodology:w('Matriz del proyecto','Project matrix','Matriz do projeto'),methodology_version:'1.0'}});
    const handle=PendingUI.attach('assessment:matrix',w('Matriz pendiente','Pending matrix','Matriz pendente'),()=>({data:obj}),{container:section,onDiscard:()=>renderMain()});
    const apply=button(w('Crear casos revisados','Create reviewed cases','Criar casos revisados'),async()=>{
      const body=pack();if(signature!==JSON.stringify(body))throw Error(w('Revisa la vista previa de la matriz actual.','Review the current matrix preview.','Revise a prévia da matriz atual.'));
      const revision=handle.handle.revision;await request('matrix',body,'POST',state);const cleanup=await handle.committed(revision);if(!cleanup.finished){signature=null;apply.disabled=true;toast(w('Los casos revisados se crearon. Los cambios posteriores de la matriz siguen pendientes.','The reviewed cases were created. Later matrix changes remain pending.','Os casos revisados foram criados. Alterações posteriores da matriz continuam pendentes.'));return;}renderSidebar();renderMain();
    },'apply-matrix',true);apply.disabled=true;
    section.addEventListener('input',()=>{signature=null;apply.disabled=true;preview.replaceChildren();});
    section.append(row(button(w('Revisar matriz','Review matrix','Revisar matriz'),async()=>{const body=pack(),result=await request('matrix',{...body,preview:true},'POST',state);if(!section.isConnected||JSON.stringify(body)!==JSON.stringify(pack()))return;signature=JSON.stringify(body);preview.replaceChildren(h('p',{},result.count+' '+w('casos pendientes','pending cases','casos pendentes')),h('ol',{},result.cases.slice(0,20).map(item=>h('li',{},item.identity+' · '+item.tenant+' · '+item.operation))));if(result.count>20)preview.append(note('Se muestran los primeros 20; se crearán todos los casos contados.','Showing the first 20; all counted cases will be created.','Exibindo os primeiros 20; todos os casos contados serão criados.'));apply.disabled=false;},'preview-matrix'),apply),preview);box.append(h('details',{},h('summary',{},w('Generar matriz de pruebas','Generate test matrix','Gerar matriz de testes')),section));
  }
  async function starters(box,slug){
    const state=context();const section=h('details',{},h('summary',{},w('Planes iniciales por especialidad','Starter plans by specialty','Planos iniciais por especialidade'))),body=card();section.append(body);box.append(section);
    const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/assessment/catalog?lang='+encodeURIComponent(S.uiLang)));const catalog=await response.json();if(!body.isConnected||!matches(state))return;
    const selected={specialty:'web'};body.append(h('p',{},catalog.notice),selectField(w('Especialidad','Specialty','Especialidade'),selected,'specialty',specialties.filter(x=>x[0]!=='custom')));
    const preview=h('ul',{'data-assessment-starter-preview':''}),draw=()=>{preview.replaceChildren(...(catalog.plans.find(x=>x.specialty===selected.specialty)?.cases||[]).map(item=>h('li',{},item.test_id+' · '+item.title)));};body.addEventListener('change',draw);draw();body.append(preview,button(w('Incorporar plan pendiente','Add pending plan','Adicionar plano pendente'),async()=>{await request('test-cases/batch',{cases:catalog.plans.find(x=>x.specialty===selected.specialty).cases},'POST',state);renderSidebar();renderMain();},'add-plan'));
  }
  async function remove(kind,item,state){if(!confirm(w('¿Eliminar este registro? El historial conserva las revisiones anteriores.','Delete this record? History retains previous revisions.','Excluir este registro? O histórico mantém as revisões anteriores.')))return;await request((kind==='case'?'test-cases':'attack-paths')+'/'+encodeURIComponent(item.uid),null,'DELETE',state);if(form?.uid===item.uid)form=null;renderSidebar();renderMain();}
  function register(){if(registered)return;registered=true;PendingUI.register('assessment:',{missingReference:record=>{const data=PendingUI.unpack(record.data);return data.uid&&!(S.data[data.kind==='case'?'test_cases':'attack_paths']||[]).some(x=>x.uid===data.uid);},restore:record=>{
    const guard=PendingUI.recoveryGuard(record);guard();const data=PendingUI.unpack(record.data);
    if(record.key==='assessment:matrix'){Object.assign(data,context());const handle=PendingUI.track(record.key,record.label,()=>({data}),{origin:record});PendingUI.changed(handle);open('assessment_cases');return;}
    if(!['case','path'].includes(data.kind)||data.slug!==S.slug||data.workspace!==BrowserWorkspace.current()||data.viewWorkspace!==S.workspace_id||!data.entry||typeof data.entry!=='object')throw Error(w('Borrador de evaluación inválido.','Invalid assessment draft.','Rascunho de avaliação inválido.'));
    data.pendingKey=record.key;form=data;forms.set(memoryKey(S.slug,record.key),data);const handle=PendingUI.track(record.key,record.label,()=>({data}),{origin:record});PendingUI.changed(handle);open(data.kind==='case'?'assessment_cases':'assessment_paths');
  }});}
  function render(kind,el){
    register();pending=null;const isCases=kind==='assessment_cases',collection=isCases?'test_cases':'attack_paths',mode=isCases?'case':'path',slug=S.slug,state=context();
    const box=h('div',{class:'assessment-view','data-assessment-view':kind});el.append(box);
    box.append(note('Resultados y relaciones registrados por el analista. No ejecuta pruebas ni determina automáticamente la seguridad.','Analyst-recorded results and relationships. This does not execute tests or automatically determine security.','Resultados e relações registrados pelo analista. Não executa testes nem determina automaticamente a segurança.'));
    const controls=row(button(isCases?w('Nuevo caso de prueba','New test case','Novo caso de teste'):w('Nueva ruta de ataque','New attack path','Novo caminho de ataque'),()=>choose(mode),'new',true));
    const filter=h('input',{type:'search','aria-label':w('Filtrar registros','Filter records','Filtrar registros'),placeholder:w('Buscar título, identidad o resultado…','Search title, identity or result…','Buscar título, identidade ou resultado…')}),list=h('div',{'data-assessment-list':''});controls.append(filter);box.append(controls,list);
    let page=0;const pager=row();box.append(pager);
    function drawList(){const query=filter.value.trim().toLocaleLowerCase(),items=(S.data[collection]||[]).filter(item=>JSON.stringify(item).toLocaleLowerCase().includes(query));page=Math.min(page,Math.max(0,Math.ceil(items.length/25)-1));list.replaceChildren(h('p',{},items.length+' '+w('registros','records','registros')));pager.replaceChildren(button(w('Anterior','Previous','Anterior'),()=>{page=Math.max(0,page-1);drawList();},'previous-page'),h('span',{},(page+1)+' / '+Math.max(1,Math.ceil(items.length/25))),button(w('Siguiente','Next','Próxima'),()=>{page=Math.min(Math.max(0,Math.ceil(items.length/25)-1),page+1);drawList();},'next-page'));pager.querySelector('button:first-child').disabled=page===0;pager.querySelector('button:last-child').disabled=page>=Math.ceil(items.length/25)-1;for(const item of items.slice(page*25,page*25+25)){const status=states.find(x=>x[0]===item.status);const summary=isCases?(status?w(...status.slice(1)):'')+' · '+[item.identity,item.tenant,item.operation].filter(Boolean).join(' · '):item.nodes.length+' '+w('etapas','stages','etapas')+' · '+item.edges.length+' '+w('transiciones','transitions','transições');const entry=card(h('strong',{},item.title),h('p',{},summary),row(button(w('Editar','Edit','Editar'),()=>choose(mode,item),'edit-'+item.uid),button(w('Eliminar','Delete','Excluir'),()=>remove(mode,item,state),'delete-'+item.uid)));if(!isCases){const details=h('details',{},h('summary',{},w('Ver diagrama guardado','View saved diagram','Ver diagrama salvo')));details.addEventListener('toggle',()=>{if(details.open&&!details.querySelector('img'))details.append(h('img',{class:'assessment-graph',alt:w('Ruta declarada: ','Declared path: ','Caminho declarado: ')+item.title,src:'/api/projects/'+encodeURIComponent(slug)+'/assessment/attack-paths/'+encodeURIComponent(item.uid)+'/graph.svg?lang='+encodeURIComponent(S.uiLang)+'&revision='+encodeURIComponent(projectStore.etag||'')}));});entry.append(details);}list.append(entry);}}filter.addEventListener('input',()=>{page=0;drawList();});drawList();
    if(form&&matches(form)&&form.kind===mode){if(isCases)editorCase(box,form);else editorPath(box,form);}
    if(isCases){matrixForm(box);starters(box,slug).catch(e=>{if(box.isConnected)box.append(h('p',{role:'alert'},e.message));});}
  }
  function forgetPending(slug,key){forms.delete(memoryKey(slug,key));if(form&&matches(form)&&form.slug===slug&&(form.pendingKey||keyFor(form.kind,form.uid))===key){form=null;pending=null;}}
  function resetProject(slug){for(const [key,value] of forms)if(value.slug===slug)forms.delete(key);if(form?.slug===slug){form=null;pending=null;}}
  register();
  return {names,title,open,render,states,causal,resetProject,forgetPending};
})();
