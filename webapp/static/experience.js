/* First-use and delivery UI. It operates through the normal saved-project API. */
const ExperienceUI = (() => {
  const w=(es,en,pt)=>uiText(es,en,pt);
  let creatingPractice = false;
  const practicePreferences = new Map();
  let dialogTrigger = null;
  // Only server-recorded creation provenance identifies a practice copy.
  // Names and browser preferences cannot label a customer project as fictional.
  const isPractice = (slug=S.slug) => typeof slug==='string' && !!S.projects?.some(project=>project.slug===slug&&project.practice===true);
  const validProjectSlug = slug => typeof slug==='string'&&slug.length>0&&slug.length<=256;
  function practiceState() {
    const key='rg.practiceProjects.v1.'+String(S.workspace_id||'session');
    if(practicePreferences.has(key))return practicePreferences.get(key);
    const state={key,hidden:new Set(),returns:new Map()};
    try {
      const saved=JSON.parse(localStorage.getItem(key)||'null');
      if(saved?.version===1) {
        if(Array.isArray(saved.hidden))state.hidden=new Set(saved.hidden.filter(validProjectSlug).slice(-200));
        if(Array.isArray(saved.returns))for(const pair of saved.returns.slice(-200)){
          if(Array.isArray(pair)&&pair.length===2&&validProjectSlug(pair[0])&&validProjectSlug(pair[1]))state.returns.set(pair[0],pair[1]);
        }
      }
    } catch (_) {}
    practicePreferences.set(key,state);return state;
  }
  function rememberPractice(state) {
    try { localStorage.setItem(state.key,JSON.stringify({version:1,hidden:[...state.hidden].slice(-200),returns:[...state.returns].slice(-200)})); } catch (_) {}
  }
  function button(text, action, primary=false) {
    const b = h('button',{class:'btn'+(primary?' primary':''),type:'button'},text);
    b.addEventListener('click',async()=>{dialogTrigger=b;b.disabled=true;try{await action(b);}catch(e){toast(e.message,'err');}finally{b.disabled=false;}});
    return b;
  }
  function dialog(title) {
    const previous=document.activeElement===document.body?dialogTrigger:document.activeElement;
    const d=h('dialog',{class:'experience-dialog','aria-label':title});
    const body=h('div',{class:'experience-body'});
    d.append(h('div',{class:'experience-heading'},h('h2',{},title),button(w('Cerrar','Close', "Fechar"),()=>d.close())),body);
    d.addEventListener('close',()=>{d.remove();previous?.focus();});document.body.append(d);d.showModal();return {d,body};
  }
  async function createPractice() {
    if(creatingPractice||projectStore.loading||projectBusyCount>0)return false;
    creatingPractice=true;
    busyProject(true);
    try {
      // Lock before the first await: two entry points must never create two
      // copies, and edits must not arrive after the saved snapshot is taken.
      const sourceSlug=S.slug,state=practiceState();
      if(sourceSlug && !await doSave())return false;
      if(S.slug!==sourceSlug)return false;
      const r=await requireOk(await api.post('/api/demo',{lang:S.uiLang}));const {slug}=await r.json();
      const previous=isPractice(sourceSlug)?state.returns.get(sourceSlug):sourceSlug;
      if(previous)state.returns.set(slug,previous);
      rememberPractice(state);
      await refreshProjects();await loadProject(slug);
      if(S.slug!==slug)throw Error(w('La copia de práctica se creó, pero no se pudo abrir. Está disponible en Tus proyectos.','The practice copy was created but could not be opened. It is available under Your projects.', 'A cópia de prática foi criada, mas não pôde ser aberta. Ela está disponível em Seus projetos.'));
      toast(w('Copia ficticia de Nimbus creada. Puedes editarla.','Fictional Nimbus copy created. You can edit it.', 'Cópia fictícia do Nimbus criada. Você pode editá-la.'),'ok');
      return true;
    } finally { creatingPractice=false;busyProject(false); }
  }
  async function returnToProject(slug) {
    if(creatingPractice||projectStore.loading||projectBusyCount>0)return false;
    busyProject(true);
    try {
      if(S.slug&&!await doSave())return false;
      await loadProject(slug);
      if(S.slug!==slug)return false;
      $('#editor')?.focus({preventScroll:true});return true;
    } finally { busyProject(false); }
  }
  function practiceNotice() {
    if(!isPractice())return null;
    const notice=h('aside',{class:'card demo-guide','data-practice-notice':'','aria-labelledby':'practiceNoticeTitle'},
      h('strong',{id:'practiceNoticeTitle'},w('Proyecto de práctica · Nimbus','Practice project · Nimbus','Projeto de prática · Nimbus')),
      h('p',{},w('Esta copia de Nimbus se creó con datos ficticios y se guarda como un proyecto independiente. Puedes volver a tus informes desde aquí.','This Nimbus copy was created with fictional data and saves as an independent project. You can return to your reports here.','Esta cópia do Nimbus foi criada com dados fictícios e é salva como um projeto independente. Você pode voltar aos seus relatórios por aqui.')));
    const actions=h('div',{class:'experience-actions'}),previous=practiceState().returns.get(S.slug);
    function action(key,label,run){const control=button(label,run);control.dataset.practiceAction=key;actions.append(control);}
    if(previous&&!isPractice(previous)&&S.projects.some(project=>project.slug===previous))action('return',w('Volver a mi proyecto','Return to my project','Voltar ao meu projeto'),()=>returnToProject(previous));
    action('projects',w('Ver mis proyectos','View my projects','Ver meus projetos'),()=>{select('home');$('[data-catalog-search]')?.focus();});
    action('new',w('Crear proyecto real','Create real project','Criar projeto real'),opener=>DesignLibraryUI.newProject(opener));
    notice.append(actions);return notice;
  }
  async function diagnostics() {
    const {d,body}=dialog(w('Comprobar instalación','Check installation', "Verificar instalação"));
    body.append(h('p',{role:'status'},w('Probando motores y escritura local…','Testing engines and local storage…', "Testando mecanismos e armazenamento local…")));
    try {
      const r=await requireOk(await api.post('/api/diagnostics',{lang:S.uiLang}));const result=await r.json();if(!d.isConnected)return;
      body.replaceChildren(h('p',{},w('PDF disponible: ','PDF available: ', "PDF disponível: ")+(result.pdf_ready?w('sí','yes', "sim"):w('no','no', "não"))));
      result.checks.forEach(c=>body.append(h('div',{class:'card'},h('strong',{},(c.ready?'✓ ':'! ')+c.label),h('p',{},c.detail))));
      body.append(h('p',{class:'wf-hint'},result.note));
      const share=h('section',{'data-support-preview':''},h('h3',{},w('Diagnóstico para compartir','Shareable diagnostics', "Diagnóstico compartilhável")),
        h('p',{},w('Revisa exactamente el JSON que descargarás. Contiene versión, sistema genérico y resultados de pruebas sintéticas. No incluye proyectos, rutas, nombres de usuario ni detalles de excepciones.','Review the exact JSON you will download. It contains version, generic operating system and synthetic test results. It excludes projects, paths, usernames and exception details.', "Revise o JSON exato que será baixado. Ele contém a versão, o sistema operacional genérico e resultados de testes sintéticos. Exclui projetos, caminhos, nomes de usuário e detalhes de exceções.")));
      // The server is authoritative for byte order; show every nested field.
      share.append(h('pre',{'data-support-json':''},JSON.stringify(result.support_report,null,2)));
      const acknowledged=h('input',{type:'checkbox','data-support-reviewed':''});
      const download=button(w('Descargar diagnóstico revisado','Download reviewed diagnostics', "Baixar diagnóstico revisado"),async()=>{
        if(!acknowledged.checked)return;
        const response=await requireOk(await api.post('/api/diagnostics/download',{report:result.support_report,preview_token:result.support_token}));
        const url=URL.createObjectURL(await response.blob());h('a',{href:url,download:'report-gen-support.json'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      });download.disabled=true;acknowledged.addEventListener('change',()=>{download.disabled=!acknowledged.checked;});
      share.append(h('label',{class:'support-review-label'},acknowledged,w('He revisado los campos del diagnóstico.','I have reviewed the diagnostic fields.', "Revisei os campos do diagnóstico.")),download);body.append(share);

    } catch(e){body.replaceChildren(h('p',{role:'alert'},e.message));}
  }
  function welcome(el) {
    el.append(h('div',{class:'experience-welcome'},h('p',{class:'experience-version'},'report-gen '+(S.version||'')),
      h('h1',{},w('Tu evidencia. Tu informe.','Your evidence. Your report.', "Sua evidência. Seu relatório.")),
      h('p',{},w('Prueba el flujo completo con Nimbus, un proyecto ficticio editable.','Try the complete workflow with Nimbus, an editable fictional project.', "Experimente o fluxo completo com o Nimbus, um projeto fictício editável.")),
      button(w('Probar Nimbus','Try Nimbus', "Experimentar Nimbus"),createPractice,true),
      h('p',{},w('O comienza con tus propios datos desde «Nuevo proyecto».','Or start with your own data using “New project”.', "Ou comece com seus próprios dados usando “Novo projeto”.")),
      button(w('Abrir biblioteca de informes','Open report design library', "Abrir biblioteca de modelos de relatório"),opener=>DesignLibraryUI.gallery(opener)),
      button(w('Comprobar instalación','Check installation', "Verificar instalação"),diagnostics),
      button(w('Actualizar report-gen','Update report-gen', "Atualizar report-gen"),opener=>UpdateUI.open(opener))));
  }
  function guide(el) {
    if(!isPractice()||practiceState().hidden.has(S.slug))return;
    const box=h('details',{class:'demo-guide',open:''},h('summary',{},w('Nimbus: recorrido de prueba','Nimbus: trial walkthrough', "Nimbus: percurso de demonstração")));
    box.append(h('p',{},w('Datos ficticios. Esta copia es tuya y se guarda como cualquier proyecto.','Fictional data. This is your copy and it saves like any project.', "Dados fictícios. Esta é sua cópia e ela é salva como qualquer projeto.")),
      h('div',{class:'experience-actions'},
        button(w('1. Editar hallazgo','1. Edit finding', "1. Editar achado"),()=>select('finding',0)),
        button(w('2. Revisar el informe','2. Review report', "2. Revisar relatório"),()=>select('workflow','review')),
        button(w('3. Inspeccionar publicación','3. Inspect publication', "3. Inspecionar publicação"),()=>StudioUI.inspector()),
        button(w('4. Preparar entrega','4. Prepare delivery', "4. Preparar entrega"),prepareDelivery)),
      button(w('Ocultar guía','Hide guide', "Ocultar guia"),()=>{const state=practiceState();state.hidden.add(S.slug);rememberPractice(state);box.remove();}));
    el.append(box);
  }
  function readinessSummary(report) {
    const slug=S.slug;
    const box=h('section',{'data-readiness-summary':'','aria-label':w('Preparación de la entrega','Delivery preparation', "Preparação da entrega")},
      h('h2',{},w('Preparación de la entrega','Delivery preparation', "Preparação da entrega")),
      h('p',{class:'hash'},w('Revisión guardada: ','Saved revision: ', "Revisão salva: ")+report.revision.slice(0,12)));
    const states={blocked:w('Requiere corrección','Correction required', "Correção necessária"),attention:w('Requiere revisión','Review required', "Revisão necessária"),checked:w('Comprobación realizada','Check performed', "Verificação realizada"),not_checked:w('Sin comprobar','Not checked', "Não verificado"),manual:w('Revisión manual necesaria','Manual review required', "Revisão manual necessária")};
    const icons={blocked:'!',attention:'!',checked:'✓',not_checked:'—',manual:'○'};
    const checks=report.readiness.checks,completed=checks.filter(check=>check.status==='checked').length;
    box.append(h('p',{'data-readiness-progress':''},w(completed+' de '+checks.length+' puntos con comprobación realizada.',completed+' of '+checks.length+' items checked.',completed+' de '+checks.length+' itens verificados.')),
      h('p',{class:'readiness-scope'},w('Revisa los puntos pendientes y realiza la revisión humana. Este contador no acredita la aprobación de la entrega.','Review outstanding items and perform the human review. This count does not certify delivery approval.', "Revise os itens pendentes e realize a revisão humana. Esta contagem não certifica a aprovação da entrega.")));
    const destinations={
      review:[w('Abrir revisión del informe','Open report review', "Abrir revisão do relatório"),()=>select('workflow','review')],
      annexes:[w('Abrir inventario de anexos','Open annex inventory', "Abrir inventário de anexos"),()=>AnnexUI.open()],
      secrets:[w('Abrir inspector de publicación','Open publication inspector', "Abrir inspetor de publicação"),()=>StudioUI.inspector()],
      associations:[w('Abrir galería de evidencias','Open evidence gallery', "Abrir galeria de evidências"),()=>select('workflow','evidence')],
      human_review:typeof InsightsUI!=='undefined'?
        [w('Abrir revisión visual de archivos','Open visual file review', "Abrir revisão visual de arquivos"),()=>InsightsUI.open('visual')]:
        [w('Abrir revisión del informe','Open report review', "Abrir revisão do relatório"),()=>select('workflow','review')]
    };
    const list=h('ul',{class:'readiness-list'});
    for(const check of checks){
      const row=h('li',{'data-readiness-check':check.key,'data-readiness-status':check.status},
        h('span',{class:'readiness-icon','aria-hidden':'true'},icons[check.status]||'?'),
        h('div',{class:'readiness-copy'},h('strong',{},check.title+' · '+states[check.status]),h('p',{},check.detail)));
      const destination=destinations[check.key];
      if(destination){const action=button(destination[0],async()=>{
        if(S.slug!==slug)return;
        box.closest('dialog')?.close();
        await destination[1]();
        if(!document.querySelector('dialog[open]'))$('#editor').focus({preventScroll:true});
      });action.dataset.readinessAction=check.key;row.lastElementChild.append(action);}
      list.append(row);
    }
    box.append(list);
    const compatibility=report.readiness.compatibility;
    if(compatibility?.format==='docx'&&compatibility.count){
      const details=h('details',{'data-docx-url-compatibility':''},
        h('summary',{},w('Compatibilidad de URLs en Word','URL compatibility in Word', "Compatibilidade de URLs no Word")+' ('+compatibility.count+')'),
        h('p',{},w('Estas ubicaciones muestran URLs de 96 o más caracteres. Es una señal para revisar el DOCX, no una medición del salto: LibreOffice puede dejar espacio al dividirlas. La URL y su destino se conservan.','These locations display URLs of 96 or more characters. This flags the DOCX for review; it does not measure line breaks. LibreOffice may leave space when wrapping them. URL text and destinations are retained.', "Estes locais exibem URLs com 96 ou mais caracteres. Isso sinaliza o DOCX para revisão; não mede quebras de linha. O LibreOffice pode deixar espaços ao quebrá-las. O texto e os destinos das URLs são preservados.")),
        h('p',{},w('En texto Markdown puedes usar Enlace para escribir un nombre descriptivo y conservar la URL completa como destino. Si el valor literal es evidencia o un comando, consérvalo y revisa el archivo generado.','In Markdown text, use Link to enter a descriptive name and retain the complete URL as its destination. If the literal value is evidence or a command, preserve it and review the generated file.', "Em texto Markdown, use Link para inserir um nome descritivo e preservar a URL completa como destino. Se o valor literal for uma evidência ou um comando, preserve-o e revise o arquivo gerado.")));
      const locations=h('ul',{});
      for(const location of compatibility.locations||[]){
        const action=button(location.label+' ('+location.count+')',()=>{
          if(S.slug!==slug)return;
          box.closest('dialog')?.close();
          WorkflowUI.navigateIssue(location);
        });
        action.dataset.docxUrlLocation=location.path;locations.append(h('li',{},action));
      }
      details.append(locations);box.append(details);
    }
    return box;
  }
  function deliveryChecklist() {
    const slug=S.slug,box=h('section',{class:'card','data-delivery-readiness':'','aria-label':w('Preparación de la entrega','Delivery preparation', "Preparação da entrega")});
    const state=h('div',{role:'status','aria-live':'polite'}),refresh=button(w('Guardar y volver a comprobar','Save and check again', "Salvar e verificar novamente"),async()=>{if(S.slug!==slug)return;if(await doSave())await load();});
    box.append(state,refresh);
    async function load() {
      delete box.dataset.readinessRevision;box.dataset.readinessCurrent='false';
      state.replaceChildren(h('p',{},w('Comprobando la revisión guardada…','Checking the saved revision…', "Verificando a revisão salva…")));
      try {
        const report=await api.get('/api/projects/'+encodeURIComponent(slug)+'/review?lang='+S.uiLang);
        if(!box.isConnected||S.slug!==slug)return;
        if(projectStore.dirty||report.revision!==projectStore.etag?.replace(/^"|"$/g,'')){
          state.replaceChildren(h('p',{class:'wf-warning'},w('El borrador o la versión guardada cambió. Guarda y vuelve a comprobar antes de preparar la entrega.','The draft or saved version changed. Save and check again before preparing delivery.', "O rascunho ou a versão salva mudou. Salve e verifique novamente antes de preparar a entrega.")));return;
        }
        box.dataset.readinessRevision=projectStore.etag;box.dataset.readinessCurrent='true';
        state.replaceChildren(readinessSummary(report));
      }catch(e){if(box.isConnected)state.replaceChildren(h('p',{class:'wf-error'},e.message));}
    }
    // The caller attaches the section synchronously. No write is made merely
    // by entering Deliver; the action above explicitly saves the draft.
    queueMicrotask(load);return box;
  }
  function updateDeliveryChecklist() {
    const box=$('[data-delivery-readiness]');if(!box?.dataset.readinessRevision)return;
    if(projectStore.dirty||projectStore.etag!==box.dataset.readinessRevision){
      delete box.dataset.readinessRevision;box.dataset.readinessCurrent='false';
      box.firstElementChild.replaceChildren(h('p',{class:'wf-warning'},w('La comprobación anterior corresponde a otra revisión. Guarda y vuelve a comprobar.','The previous check belongs to another revision. Save and check again.', "A verificação anterior pertence a outra revisão. Salve e verifique novamente.")));
    }
  }
  async function prepareDelivery() {
    if(!S.slug){toast(w('Abre un proyecto primero.','Open a project first.', "Abra um projeto primeiro."),'err');return;}
    if(!await doSave())return;
    const slug=S.slug, revision=projectStore.etag;
    const report=await api.get('/api/projects/'+encodeURIComponent(slug)+'/review?lang='+S.uiLang);
    if(S.slug!==slug)return;
    if(projectStore.dirty||projectStore.etag!==revision||report.revision!==revision?.replace(/^"|"$/g,''))throw Error(w('El proyecto cambió durante la revisión. Guarda y vuelve a preparar la entrega.','The project changed during review. Save and prepare delivery again.', "O projeto mudou durante a revisão. Salve e prepare a entrega novamente."));
    const {d,body}=dialog(w('Preparar entrega','Prepare delivery', "Preparar entrega"));
    const errors=report.issues.filter(i=>i.level==='error'), warnings=report.issues.filter(i=>i.level!=='error');
    const label=h('input',{value:(S.data.meta.client||slug)+' - '+(S.data.meta.version||'1.0'),maxlength:120,'data-delivery':'label'});
    body.append(h('p',{},w('Todos los formatos se generan desde la misma revisión guardada.','All formats are generated from the same saved revision.', "Todos os formatos são gerados a partir da mesma revisão salva.")),
      h('label',{},w('Nombre de la entrega','Delivery name', "Nome da entrega"),label));
    body.append(readinessSummary(report));
    if(report.delivery_guidance)body.append(DesignLibraryUI.guideBox(report.delivery_guidance));
    const defaults=report.delivery_guidance?.formats||['pdf','docx','md'];
    const formats=h('fieldset',{class:'delivery-formats'},h('legend',{},w('Archivos para el cliente','Client files', "Arquivos do cliente")));
    S.formats.forEach(spec=>{const fmt=spec.key;formats.append(h('label',{class:'wf-check'},h('input',{type:'checkbox',value:fmt,checked:defaults.includes(fmt)?'':null,'data-delivery-format':fmt}),spec['label_'+S.uiLang]));});
    body.append(formats,h('p',{class:'wf-hint'},w('El respaldo editable, los originales y el historial se descargan por separado desde «Respaldo del proyecto».','The editable backup, originals and history are downloaded separately under “Project backup”.', "O backup editável, os originais e o histórico são baixados separadamente em “Backup do projeto”.")));
    const issues=h('div',{class:'delivery-issues'});
    report.issues.forEach(i=>issues.append(h('p',{class:i.level==='error'?'wf-error':'wf-warning'},i.message)));
    if(report.issues.length)body.append(h('details',{open:''},h('summary',{},report.issues.length+' '+(report.issues.length===1?w('observación','review item', "item para revisão"):w('observaciones','review items', "itens para revisão"))),issues));
    const ack=h('input',{type:'checkbox','data-delivery':'ack'});
    if(warnings.length)body.append(h('label',{class:'wf-check'},ack,w('He revisado los avisos que acompañarán a esta entrega.','I reviewed the warnings that will accompany this delivery.', "Revisei os avisos que acompanharão esta entrega.")));
    const state=h('p',{role:'status','aria-live':'polite'});body.append(state);
    const generate=button(w('Generar paquete','Generate package', "Gerar pacote"),async()=>{
      if(S.slug!==slug||projectStore.etag!==revision||projectStore.dirty){const message=w('El proyecto cambió. Vuelve a preparar la entrega.','The project changed. Prepare delivery again.', "O projeto mudou. Prepare a entrega novamente.");state.textContent=message;throw Error(message);}
      if(errors.length)throw Error(w('Corrige los errores antes de entregar.','Fix the errors before delivery.', "Corrija os erros antes da entrega."));
      if(warnings.length&&!ack.checked)throw Error(w('Revisa y confirma los avisos.','Review and acknowledge the warnings.', "Revise e reconheça os avisos."));
      const selected=[...formats.querySelectorAll('input:checked')].map(c=>c.value);
      if(!selected.length)throw Error(w('Selecciona al menos un formato.','Select at least one format.', "Selecione pelo menos um formato."));
      state.textContent=w('Añadiendo a la cola…','Adding to queue…', "Adicionando à fila…");
      try {
        await ProgressUI.enqueue(slug,revision,{kind:'delivery',formats:selected,label:label.value,acknowledge_warnings:ack.checked},false);
        d.addEventListener('close',()=>ProgressUI.jobs(),{once:true});
        d.close();
      }catch(e){state.textContent=e.message;throw e;}

    },true);
    generate.disabled=errors.length>0;body.append(generate);
  }
  function update() {
    const demo=$('#demoBtn'),delivery=$('#deliveryBtn');
    if(demo)demo.textContent=w('Probar demo','Try demo', "Experimentar demonstração");
    const diagnose=$('#diagnosticsBtn');if(diagnose)diagnose.textContent=w('Comprobar instalación','Check installation', "Verificar instalação");
    const updater=$('#updateAppBtn');if(updater)updater.textContent=w('Actualizar report-gen','Update report-gen', "Atualizar report-gen");
    if(delivery){delivery.textContent=w('Preparar entrega','Prepare delivery', "Preparar entrega");delivery.disabled=!S.slug||projectBusyCount>0;}
  }
  function bind() {
    const demo=button(w('Probar demo','Try demo', "Experimentar demonstração"),createPractice);demo.id='demoBtn';demo.classList.add('sm');$('#newProjectBtn').after(demo);
    const deliver=button(w('Preparar entrega','Prepare delivery', "Preparar entrega"),prepareDelivery,true);deliver.id='deliveryBtn';deliver.classList.add('sm');$('#downloadBtn').after(deliver);
    const diagnose=button(w('Comprobar instalación','Check installation', "Verificar instalação"),diagnostics);diagnose.id='diagnosticsBtn';$('.sidebar').append(diagnose);
    const updater=button(w('Actualizar report-gen','Update report-gen', "Atualizar report-gen"),opener=>UpdateUI.open(opener));updater.id='updateAppBtn';$('.sidebar').append(updater);update();
  }
  return {bind,update,welcome,guide,createPractice,isPractice,practiceNotice,prepareDelivery,deliveryChecklist,updateDeliveryChecklist};
})();
