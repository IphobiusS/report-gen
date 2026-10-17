/* Read-only preparation guides and explicit creation of independent drafts. */
const WorkPackagesUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  let creating=false;
  function button(label,action,attrs={}){
    const control=h('button',{type:'button',class:'btn',...attrs},label);
    control.addEventListener('click',async()=>{
      control.disabled=true;
      try{await action(control);}catch(error){toast(error.message,'err');}
      finally{control.disabled=false;}
    });
    return control;
  }
  function dialog(title,attribute){
    const opener=document.activeElement;
    const d=h('dialog',{class:'work-package-dialog','aria-label':title,[attribute]:''});
    const body=h('div',{class:'work-package-body'});
    d.append(h('header',{class:'work-package-heading'},h('h2',{},title),button(w('Cerrar','Close','Fechar'),()=>d.close())),body);
    d.addEventListener('cancel',event=>{if(d.dataset.busy==='true')event.preventDefault();});
    d.addEventListener('close',()=>{d.remove();requestAnimationFrame(()=>{const parent=[...document.querySelectorAll('dialog[open]')].at(-1);(opener?.isConnected&&!opener.disabled&&(!parent||parent.contains(opener))?opener:parent?.querySelector('button')||document.querySelector('#editor'))?.focus({preventScroll:true});});});
    document.body.append(d);d.showModal();return {d,body};
  }
  async function get(url){return api.get(url);}
  function notice(){return w('Crea un proyecto independiente con estructura y pruebas pendientes. Seleccionar una ficha no confirma una vulnerabilidad ni asigna severidad.',
    'Create an independent project with structure and pending tests. Selecting an entry neither confirms a vulnerability nor assigns severity.',
    'Crie um projeto independente com estrutura e testes pendentes. Selecionar uma ficha não confirma uma vulnerabilidade nem atribui severidade.');}
  async function create(item,form,d,status,state,pending){
    if(creating||projectStore.loading||projectBusyCount>0||state.uncertain)return;
    creating=true;busyProject(true);d.dataset.busy='true';
    const source=S.slug, controls=[...d.querySelectorAll('button,input,select')].map(node=>[node,node.disabled]);
    controls.forEach(([node])=>node.disabled=true);
    let attempted=false;
    try{
      if(source&&!await doSave()){
        status.textContent=w('No se pudo guardar tu proyecto. Resuelve el aviso de guardado antes de continuar.','Your project could not be saved. Resolve the save warning before continuing.','Não foi possível salvar seu projeto. Resolva o aviso de salvamento antes de continuar.');
        return;
      }
      if(S.slug!==source||!d.isConnected)return;
      if(!state.created_slug){
        attempted=true;
        const response=await requireOk(await api.post('/api/work-packages/'+encodeURIComponent(item.id)+'/projects',{
          lang:item.lang,title:form.querySelector('[data-package-title]').value,client:form.querySelector('[data-package-client]').value,
          finding_ids:[...form.querySelectorAll('[data-package-entry]:checked')].map(input=>input.value)
        }));
        const result=await response.json();state.created_slug=result.slug;pending.changed();
      }
      await refreshProjects();await loadProject(state.created_slug);
      if(S.slug!==state.created_slug)throw Error(w('El borrador se creó y está disponible en Tus proyectos. Reintenta abrirlo; no se creará otro.','The draft was created and is available under Your projects. Retry opening it; another will not be created.','O rascunho foi criado e está disponível em Seus projetos. Tente abri-lo novamente; outro não será criado.'));
      await pending.committed();d.close();toast(w('Paquete creado con pruebas pendientes.','Package created with pending tests.','Pacote criado com testes pendentes.'),'ok');
    }catch(error){
      if(attempted&&!state.created_slug&&(!error.status||error.status>=500)){state.uncertain=true;pending.changed();}
      status.textContent=error.message;
      if(state.uncertain)status.append(' '+w('La respuesta no confirma si se creó. Revisa Tus proyectos antes de descartar este formulario e intentarlo otra vez.','The response does not confirm whether it was created. Review Your projects before discarding this form and trying again.','A resposta não confirma se foi criado. Revise Seus projetos antes de descartar este formulário e tentar novamente.'));
      status.setAttribute('role','alert');
    }finally{creating=false;busyProject(false);d.dataset.busy='false';controls.forEach(([node,disabled])=>node.disabled=disabled);}
  }
  function detail(item,body,d,back,recovered=null){
    const key='work-package:'+item.id+':'+item.lang,initial=recovered?.data||PendingUI.retained(key,'workspace')?.data;
    const state={created_slug:initial?.created_slug||null,uncertain:!!initial?.uncertain};let pending;
    body.replaceChildren(button(w('Volver a los paquetes','Back to packages','Voltar aos pacotes'),back,{'data-package-back':''}),
      h('h3',{},item.title),h('p',{},item.summary),h('p',{class:'work-package-notice'},notice()),
      h('h4',{},w('Define primero el alcance','Define scope first','Defina primeiro o escopo')),
      h('ul',{},item.scope_prompts.map(prompt=>h('li',{},prompt))));
    const form=h('form',{'data-package-form':item.id});
    const title=h('input',{type:'text',maxlength:500,value:initial?.title??item.title,'data-package-title':''});
    const client=h('input',{type:'text',maxlength:500,value:initial?.client||'','data-package-client':''});
    form.append(h('p',{class:'work-package-notice'},w('Idioma del paquete: ','Package language: ','Idioma do pacote: ')+({es:'Español',en:'English',pt:'Português (Brasil)'})[item.lang]),h('label',{},w('Título del informe','Report title','Título do relatório'),title),
      h('label',{},w('Cliente (opcional)','Client (optional)','Cliente (opcional)'),client),
      h('p',{},w('Se crearán ','This will create ','Serão criados ')+item.entries.length+w(' casos de prueba pendientes. Las fichas siguientes son opcionales y empiezan sin verificar.',' pending test cases. The following entries are optional and start unverified.',' casos de teste pendentes. As fichas abaixo são opcionais e começam sem verificação.')));
    const fieldset=h('fieldset',{},h('legend',{},w('Hallazgos sugeridos para adaptar','Suggested findings to adapt','Achados sugeridos para adaptar')));
    for(const entry of item.entries){
      const checkbox=h('input',{type:'checkbox',value:entry.id,'data-package-entry':entry.id,checked:initial?.finding_ids?.includes(entry.id)?'':null});
      fieldset.append(h('label',{class:'work-package-choice'},checkbox,h('span',{},h('strong',{},entry.title),h('small',{},entry.id+' · '+entry.summary))));
    }
    const status=h('p',{role:'status','aria-live':'polite','data-package-status':''});
    const submit=h('button',{type:'submit',class:'btn primary','data-package-create':''},w('Crear proyecto independiente','Create independent project','Criar projeto independente'));
    form.addEventListener('submit',async event=>{event.preventDefault();if(submit.disabled)return;submit.disabled=true;pending.setBusy(true);try{await create(item,form,d,status,state,pending);}finally{submit.disabled=state.uncertain;pending.setBusy(false);if(state.created_slug)submit.textContent=w('Abrir proyecto creado','Open created project','Abrir projeto criado');}});
    form.append(fieldset,status,submit);body.append(form);
    pending=PendingUI.attach(key,w('Paquete de trabajo pendiente','Pending work package','Pacote de trabalho pendente'),()=>({data:{package_id:item.id,lang:item.lang,title:title.value,client:client.value,finding_ids:[...form.querySelectorAll('[data-package-entry]:checked')].map(node=>node.value),...state}}),{scope:'workspace',container:form,events:form,origin:recovered,onDiscard:()=>d.close()});
    if(state.uncertain){submit.disabled=true;status.textContent=w('Creación sin confirmar. Revisa Tus proyectos antes de descartar este formulario.','Unconfirmed creation. Review Your projects before discarding this form.','Criação não confirmada. Revise Seus projetos antes de descartar este formulário.');}
    if(state.created_slug)submit.textContent=w('Abrir proyecto creado','Open created project','Abrir projeto criado');
    body.querySelector('[data-package-back]').focus();
  }
  async function open(){
    const {d,body}=dialog(w('Paquetes de trabajo','Work packages','Pacotes de trabalho'),'data-work-packages-dialog');
    body.append(h('p',{role:'status'},w('Cargando…','Loading…','Carregando…')));
    try{
      const result=await get('/api/work-packages?lang='+encodeURIComponent(S.uiLang||'es'));
      if(!d.isConnected)return;
      function list(){
        body.replaceChildren(h('p',{},notice()));
        const cards=h('div',{class:'work-package-grid'});
        for(const item of result.packages)cards.append(h('article',{class:'work-package-card'},h('h3',{},item.title),h('p',{},item.summary),
          button(w('Preparar paquete','Prepare package','Preparar pacote')+' · '+item.entries.length,()=>detail(item,body,d,list),{'data-work-package':item.id})));
        body.append(cards);body.querySelector('[data-work-package]')?.focus();
      }
      list();
    }catch(error){body.replaceChildren(h('p',{role:'alert'},error.message));}
  }
  async function openExample(){
    const {d,body}=dialog(w('Informe comentado','Annotated report','Relatório comentado'),'data-annotated-example-dialog');
    body.append(h('p',{role:'status'},w('Cargando…','Loading…','Carregando…')));
    try{
      const result=await get('/api/work-packages/example?lang='+encodeURIComponent(S.uiLang||'es'));
      if(!d.isConnected)return;
      body.replaceChildren(h('h3',{},result.title),h('p',{},w(
        'Lee las decisiones de redacción junto al informe ficticio completo de Nimbus. Las notas no se añaden a tus exportaciones. Crear una copia conserva tu proyecto actual y permite volver a él.',
        'Read the writing decisions alongside the complete fictional Nimbus report. Notes are not added to your exports. Creating a copy preserves your current project and lets you return to it.',
        'Leia as decisões de redação junto ao relatório fictício completo do Nimbus. As notas não são adicionadas às exportações. Criar uma cópia preserva seu projeto atual e permite voltar a ele.')),
        button(w('Crear copia de Nimbus para practicar','Create a Nimbus practice copy','Criar cópia do Nimbus para praticar'),async()=>{
          if(await ExperienceUI.createPractice())d.close();
        },{'data-annotated-create':''}));
      for(const lesson of result.lessons){const note=h('details',{'data-report-lesson':lesson.id},h('summary',{},lesson.title),h('p',{},lesson.text));note.addEventListener('keydown',event=>{if(event.key==='Escape'&&note.open){event.preventDefault();event.stopPropagation();note.open=false;note.querySelector('summary').focus();}});body.append(note);}
      body.append(h('p',{class:'work-package-notice'},w('Para contrastar las notas con el informe, abre Nimbus, vuelve aquí desde la biblioteca y después exporta con los controles habituales.','To compare the notes with the report, open Nimbus, return here from the library and then export using the usual controls.','Para comparar as notas com o relatório, abra o Nimbus, volte aqui pela biblioteca e exporte usando os controles habituais.')));
    }catch(error){body.replaceChildren(h('p',{role:'alert'},error.message));}
  }
  if(typeof PendingUI!=='undefined')PendingUI.register('work-package:',{
    validate(row){const data=row.data;if(!data||typeof data.package_id!=='string'||!['es','en','pt'].includes(data.lang)||row.key!=='work-package:'+data.package_id+':'+data.lang||typeof data.title!=='string'||typeof data.client!=='string'||!Array.isArray(data.finding_ids)||data.finding_ids.some(id=>typeof id!=='string')||typeof data.uncertain!=='boolean'||data.created_slug!==null&&typeof data.created_slug!=='string')throw Error(w('Paquete pendiente no compatible.','Unsupported pending package.','Pacote pendente não compatível.'));},
    async restore(row){const check=PendingUI.recoveryGuard(row),item=await get('/api/work-packages/'+encodeURIComponent(row.data.package_id)+'?lang='+encodeURIComponent(row.data.lang));check();if(row.data.finding_ids.some(id=>!item.entries.some(entry=>entry.id===id)))throw Error(w('El catálogo cambió. Conserva el formulario y revisa las fichas.','The catalog changed. Keep the form and review the entries.','O catálogo mudou. Mantenha o formulário e revise as fichas.'));const {d,body}=dialog(w('Paquete de trabajo pendiente','Pending work package','Pacote de trabalho pendente'),'data-work-packages-dialog');detail(item,body,d,()=>d.close(),row);}
  });
  return {open,openExample};
})();
