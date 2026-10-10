/* First-use and delivery UI. It operates through the normal saved-project API. */
const ExperienceUI = (() => {
  const w = (es,en) => S.uiLang === 'en' ? en : es;
  let demoSlugs = new Set();
  let dialogTrigger = null;
  try { demoSlugs = new Set(JSON.parse(localStorage.getItem('rg.demoProjects') || '[]')); } catch (_) {}
  function button(text, action, primary=false) {
    const b = h('button',{class:'btn'+(primary?' primary':''),type:'button'},text);
    b.addEventListener('click',async()=>{dialogTrigger=b;b.disabled=true;try{await action(b);}catch(e){toast(e.message,'err');}finally{b.disabled=false;}});
    return b;
  }
  function dialog(title) {
    const previous=document.activeElement===document.body?dialogTrigger:document.activeElement;
    const d=h('dialog',{class:'experience-dialog','aria-label':title});
    const body=h('div',{class:'experience-body'});
    d.append(h('div',{class:'experience-heading'},h('h2',{},title),button(w('Cerrar','Close'),()=>d.close())),body);
    d.addEventListener('close',()=>{d.remove();previous?.focus();});document.body.append(d);d.showModal();return {d,body};
  }
  async function createDemo() {
    if(S.slug && !await doSave())return;
    busyProject(true);
    try {
      const r=await requireOk(await api.post('/api/demo',{}));const {slug}=await r.json();
      demoSlugs.add(slug);try{localStorage.setItem('rg.demoProjects',JSON.stringify([...demoSlugs]));}catch(_){}
      await refreshProjects();await loadProject(slug);
      toast(w('Copia de Nimbus creada. Puedes editarla.','Nimbus copy created. You can edit it.'),'ok');
    } finally { busyProject(false); }
  }
  async function diagnostics() {
    const {d,body}=dialog(w('Comprobar instalación','Check installation'));
    body.append(h('p',{role:'status'},w('Probando motores y escritura local…','Testing engines and local storage…')));
    try {
      const r=await requireOk(await api.post('/api/diagnostics',{lang:S.uiLang}));const result=await r.json();if(!d.isConnected)return;
      body.replaceChildren(h('p',{},w('PDF disponible: ','PDF available: ')+(result.pdf_ready?w('sí','yes'):w('no','no'))));
      result.checks.forEach(c=>body.append(h('div',{class:'card'},h('strong',{},(c.ready?'✓ ':'! ')+c.label),h('p',{},c.detail))));
      body.append(h('p',{class:'wf-hint'},result.note));
      const share=h('section',{'data-support-preview':''},h('h3',{},w('Diagnóstico para compartir','Shareable diagnostics')),
        h('p',{},w('Revisa exactamente el JSON que descargarás. Contiene versión, sistema genérico y resultados de pruebas sintéticas. No incluye proyectos, rutas, nombres de usuario ni detalles de excepciones.','Review the exact JSON you will download. It contains version, generic operating system and synthetic test results. It excludes projects, paths, usernames and exception details.')));
      // The server is authoritative for byte order; show every nested field.
      share.append(h('pre',{'data-support-json':''},JSON.stringify(result.support_report,null,2)));
      const acknowledged=h('input',{type:'checkbox','data-support-reviewed':''});
      const download=button(w('Descargar diagnóstico revisado','Download reviewed diagnostics'),async()=>{
        if(!acknowledged.checked)return;
        const response=await requireOk(await api.post('/api/diagnostics/download',{report:result.support_report,preview_token:result.support_token}));
        const url=URL.createObjectURL(await response.blob());h('a',{href:url,download:'report-gen-support.json'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);
      });download.disabled=true;acknowledged.addEventListener('change',()=>{download.disabled=!acknowledged.checked;});
      share.append(h('label',{class:'support-review-label'},acknowledged,w('He revisado los campos del diagnóstico.','I have reviewed the diagnostic fields.')),download);body.append(share);

    } catch(e){body.replaceChildren(h('p',{role:'alert'},e.message));}
  }
  function welcome(el) {
    el.append(h('div',{class:'experience-welcome'},h('p',{class:'experience-version'},'report-gen '+(S.version||'')),
      h('h1',{},w('Tu evidencia. Tu informe.','Your evidence. Your report.')),
      h('p',{},w('Prueba el flujo completo con Nimbus, un proyecto ficticio editable.','Try the complete workflow with Nimbus, an editable fictional project.')),
      button(w('Probar Nimbus','Try Nimbus'),createDemo,true),
      h('p',{},w('O comienza con tus propios datos desde «Nuevo proyecto».','Or start with your own data using “New project”.')),
      button(w('Abrir biblioteca de informes','Open report design library'),opener=>DesignLibraryUI.gallery(opener)),
      button(w('Comprobar instalación','Check installation'),diagnostics),
      button(w('Actualizar report-gen','Update report-gen'),opener=>UpdateUI.open(opener))));
  }
  function guide(el) {
    if(!demoSlugs.has(S.slug))return;
    const box=h('details',{class:'demo-guide',open:''},h('summary',{},w('Nimbus: recorrido de prueba','Nimbus: trial walkthrough')));
    box.append(h('p',{},w('Datos ficticios. Esta copia es tuya y se guarda como cualquier proyecto.','Fictional data. This is your copy and it saves like any project.')),
      h('div',{class:'experience-actions'},
        button(w('1. Editar hallazgo','1. Edit finding'),()=>select('finding',0)),
        button(w('2. Revisar el informe','2. Review report'),()=>select('workflow','review')),
        button(w('3. Inspeccionar publicación','3. Inspect publication'),()=>StudioUI.inspector()),
        button(w('4. Preparar entrega','4. Prepare delivery'),prepareDelivery)),
      button(w('Ocultar guía','Hide guide'),()=>{demoSlugs.delete(S.slug);try{localStorage.setItem('rg.demoProjects',JSON.stringify([...demoSlugs]));}catch(_){}box.remove();}));
    el.append(box);
  }
  function readinessSummary(report) {
    const slug=S.slug;
    const box=h('section',{'data-readiness-summary':'','aria-label':w('Preparación de la entrega','Delivery preparation')},
      h('h2',{},w('Preparación de la entrega','Delivery preparation')),
      h('p',{class:'hash'},w('Revisión guardada: ','Saved revision: ')+report.revision.slice(0,12)));
    const states={blocked:w('Requiere corrección','Correction required'),attention:w('Requiere revisión','Review required'),checked:w('Comprobación realizada','Check performed'),not_checked:w('Sin comprobar','Not checked'),manual:w('Revisión manual necesaria','Manual review required')};
    const icons={blocked:'!',attention:'!',checked:'✓',not_checked:'—',manual:'○'};
    const checks=report.readiness.checks,completed=checks.filter(check=>check.status==='checked').length;
    box.append(h('p',{'data-readiness-progress':''},w(completed+' de '+checks.length+' puntos con comprobación realizada.',completed+' of '+checks.length+' items checked.')),
      h('p',{class:'readiness-scope'},w('Revisa los puntos pendientes y realiza la revisión humana. Este contador no acredita la aprobación de la entrega.','Review outstanding items and perform the human review. This count does not certify delivery approval.')));
    const destinations={
      review:[w('Abrir revisión del informe','Open report review'),()=>select('workflow','review')],
      annexes:[w('Abrir inventario de anexos','Open annex inventory'),()=>AnnexUI.open()],
      secrets:[w('Abrir inspector de publicación','Open publication inspector'),()=>StudioUI.inspector()],
      associations:[w('Abrir galería de evidencias','Open evidence gallery'),()=>select('workflow','evidence')],
      human_review:typeof InsightsUI!=='undefined'?
        [w('Abrir revisión visual de archivos','Open visual file review'),()=>InsightsUI.open('visual')]:
        [w('Abrir revisión del informe','Open report review'),()=>select('workflow','review')]
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
    box.append(list);return box;
  }
  function deliveryChecklist() {
    const slug=S.slug,box=h('section',{class:'card','data-delivery-readiness':'','aria-label':w('Preparación de la entrega','Delivery preparation')});
    const state=h('div',{role:'status','aria-live':'polite'}),refresh=button(w('Guardar y volver a comprobar','Save and check again'),async()=>{if(S.slug!==slug)return;if(await doSave())await load();});
    box.append(state,refresh);
    async function load() {
      delete box.dataset.readinessRevision;box.dataset.readinessCurrent='false';
      state.replaceChildren(h('p',{},w('Comprobando la revisión guardada…','Checking the saved revision…')));
      try {
        const report=await api.get('/api/projects/'+encodeURIComponent(slug)+'/review?lang='+S.uiLang);
        if(!box.isConnected||S.slug!==slug)return;
        if(projectStore.dirty||report.revision!==projectStore.etag?.replace(/^"|"$/g,'')){
          state.replaceChildren(h('p',{class:'wf-warning'},w('El borrador o la versión guardada cambió. Guarda y vuelve a comprobar antes de preparar la entrega.','The draft or saved version changed. Save and check again before preparing delivery.')));return;
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
      box.firstElementChild.replaceChildren(h('p',{class:'wf-warning'},w('La comprobación anterior corresponde a otra revisión. Guarda y vuelve a comprobar.','The previous check belongs to another revision. Save and check again.')));
    }
  }
  async function prepareDelivery() {
    if(!S.slug){toast(w('Abre un proyecto primero.','Open a project first.'),'err');return;}
    if(!await doSave())return;
    const slug=S.slug, revision=projectStore.etag;
    const report=await api.get('/api/projects/'+encodeURIComponent(slug)+'/review?lang='+S.uiLang);
    if(S.slug!==slug)return;
    if(projectStore.dirty||projectStore.etag!==revision||report.revision!==revision?.replace(/^"|"$/g,''))throw Error(w('El proyecto cambió durante la revisión. Guarda y vuelve a preparar la entrega.','The project changed during review. Save and prepare delivery again.'));
    const {d,body}=dialog(w('Preparar entrega','Prepare delivery'));
    const errors=report.issues.filter(i=>i.level==='error'), warnings=report.issues.filter(i=>i.level!=='error');
    const label=h('input',{value:(S.data.meta.client||slug)+' - '+(S.data.meta.version||'1.0'),maxlength:120,'data-delivery':'label'});
    body.append(h('p',{},w('Todos los formatos se generan desde la misma revisión guardada.','All formats are generated from the same saved revision.')),
      h('label',{},w('Nombre de la entrega','Delivery name'),label));
    body.append(readinessSummary(report));
    if(report.delivery_guidance)body.append(DesignLibraryUI.guideBox(report.delivery_guidance));
    const defaults=report.delivery_guidance?.formats||['pdf','docx','md'];
    const formats=h('fieldset',{class:'delivery-formats'},h('legend',{},w('Archivos para el cliente','Client files')));
    S.formats.forEach(spec=>{const fmt=spec.key;formats.append(h('label',{class:'wf-check'},h('input',{type:'checkbox',value:fmt,checked:defaults.includes(fmt)?'':null,'data-delivery-format':fmt}),spec['label_'+(S.uiLang==='en'?'en':'es')]));});
    body.append(formats,h('p',{class:'wf-hint'},w('El respaldo editable, los originales y el historial se descargan por separado desde «Respaldo del proyecto».','The editable backup, originals and history are downloaded separately under “Project backup”.')));
    const issues=h('div',{class:'delivery-issues'});
    report.issues.forEach(i=>issues.append(h('p',{class:i.level==='error'?'wf-error':'wf-warning'},i.message)));
    if(report.issues.length)body.append(h('details',{open:''},h('summary',{},report.issues.length+' '+w('observaciones','review items')),issues));
    const ack=h('input',{type:'checkbox','data-delivery':'ack'});
    if(warnings.length)body.append(h('label',{class:'wf-check'},ack,w('He revisado los avisos que acompañarán a esta entrega.','I reviewed the warnings that will accompany this delivery.')));
    const state=h('p',{role:'status','aria-live':'polite'});body.append(state);
    const generate=button(w('Generar paquete','Generate package'),async()=>{
      if(S.slug!==slug||projectStore.etag!==revision||projectStore.dirty){const message=w('El proyecto cambió. Vuelve a preparar la entrega.','The project changed. Prepare delivery again.');state.textContent=message;throw Error(message);}
      if(errors.length)throw Error(w('Corrige los errores antes de entregar.','Fix the errors before delivery.'));
      if(warnings.length&&!ack.checked)throw Error(w('Revisa y confirma los avisos.','Review and acknowledge the warnings.'));
      const selected=[...formats.querySelectorAll('input:checked')].map(c=>c.value);
      if(!selected.length)throw Error(w('Selecciona al menos un formato.','Select at least one format.'));
      state.textContent=w('Añadiendo a la cola…','Adding to queue…');
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
    if(demo)demo.textContent=w('Probar demo','Try demo');
    const diagnose=$('#diagnosticsBtn');if(diagnose)diagnose.textContent=w('Comprobar instalación','Check installation');
    const updater=$('#updateAppBtn');if(updater)updater.textContent=w('Actualizar report-gen','Update report-gen');
    if(delivery){delivery.textContent=w('Preparar entrega','Prepare delivery');delivery.disabled=!S.slug||projectBusyCount>0;}
  }
  function bind() {
    const demo=button(w('Probar demo','Try demo'),createDemo);demo.id='demoBtn';demo.classList.add('sm');$('#newProjectBtn').after(demo);
    const deliver=button(w('Preparar entrega','Prepare delivery'),prepareDelivery,true);deliver.id='deliveryBtn';deliver.classList.add('sm');$('#downloadBtn').after(deliver);
    const diagnose=button(w('Comprobar instalación','Check installation'),diagnostics);diagnose.id='diagnosticsBtn';$('.sidebar').append(diagnose);
    const updater=button(w('Actualizar report-gen','Update report-gen'),opener=>UpdateUI.open(opener));updater.id='updateAppBtn';$('.sidebar').append(updater);update();
  }
  return {bind,update,welcome,guide,prepareDelivery,deliveryChecklist,updateDeliveryChecklist};
})();
