/* The workspace reads report data. Navigating or changing UI language never edits it. */
const WorkspaceUI = (() => {
  'use strict';
  const w = (es, en) => S.uiLang === 'en' ? en : es;
  const labels = {
    skip:['Saltar al contenido','Skip to content'], activeProject:['Proyecto activo','Active project'],
    navigation:['Navegación','Navigation'], home:['Inicio','Overview'], projectActions:['Proyecto','Project'],
    exportOptions:['Vista y exportación','Preview and export'], format:['Formato','Format'],
    tools:['Bibliotecas y respaldo','Libraries and backup'], newProject:['Nuevo proyecto','New project'], projectManagement:['Gestión del proyecto','Project management']
  };
  function button(text, run, primary=false) {
    const b=h('button',{type:'button',class:'btn'+(primary?' primary':'')},text);
    b.addEventListener('click',async()=>{b.disabled=true;try{await run(b);}catch(e){toast(e.message,'err');}finally{b.disabled=false;}});
    return b;
  }
  function go(type='report', value=-1) { select(type,value); $('#editor').focus({preventScroll:true}); }
  function update() {
    if(typeof ProgressUI!=='undefined')ProgressUI.update();
    document.querySelectorAll('[data-workspace-text]').forEach(el=>{const pair=labels[el.dataset.workspaceText];if(pair)el.textContent=w(...pair);});
    const guide=S.sel.type==='guide'||S.sel.type==='insights';
    const home=!guide&&(!S.data||S.sel.type==='home');
    $('.layout').classList.toggle('workspace-home',home||guide);
    $('#navHome').classList.toggle('active',home);
    $('#navHome').setAttribute('aria-current',home?'page':'false');
    $('#navReport').setAttribute('aria-current',S.sel.type==='report'?'page':'false');
    const section=S.sel.type==='section'?$('#sectionList .active .ftitle')?.textContent:
      S.sel.type==='finding'?S.data?.findings?.[S.sel.idx]?.title:
      S.sel.type==='workflow'?$('[data-workflow="'+S.sel.idx+'"]')?.textContent:
      S.sel.type==='capture'?w('Bandeja de captura','Capture inbox'):
      S.sel.type==='findings'?w('Hallazgos','Findings'):
      guide?w('Guía del primer informe','First report guide'):home?w('Inicio','Overview'):w('Informe','Report');
    $('#workspaceContext').textContent=section||w('Espacio de trabajo','Workspace');
    $('#brandHome').title='report-gen: '+w('inicio','overview');
    $('#globalSearch').setAttribute('aria-label',w('Buscar en el proyecto','Search project'));
    $('#workspaceSidebar').setAttribute('aria-label',w('Navegación del proyecto','Project navigation'));
    $('#editor').setAttribute('aria-label',w('Contenido del proyecto','Project content'));
    $('#pdfPreview').title=w('Vista previa del informe','Report preview');
    $('#langToggle').setAttribute('aria-label',w('ES: Idioma de la interfaz: español. Cambiar a inglés.','EN: Interface language: English. Switch to Spanish.'));
    $('#themeToggle').setAttribute('aria-label',$('#themeToggle').title);
    $('#validateBtn').setAttribute('aria-label',w('Validar informe','Validate report'));
    $('#workspaceBackupBtn').textContent=w('Respaldo integral','Workspace backup');
    const privacy=$('#privacyBtn');if(privacy){privacy.textContent=w('Datos privados guardados','Stored private data');privacy.disabled=!S.slug;}
    $('#designLibraryBtn').textContent=w('Biblioteca de informes','Report design library');
    const absent=!S.slug;
    for(const id of ['downloadBtn','previewBtn','previewToggle','validateBtn','exportFormat','globalSearch','navReport','manageSections']) $('#'+id).disabled=absent||projectBusyCount>0;
    document.querySelectorAll('[data-add],[data-workflow]').forEach(b=>{b.disabled=(absent&&b.dataset.workflow!=='library')||projectBusyCount>0;});
    if(typeof WorkbenchUI!=='undefined')WorkbenchUI.update();
    if(typeof StudioUI!=='undefined')StudioUI.update();
    if(typeof GuideUI!=='undefined')GuideUI.update();
    if(typeof InsightsUI!=='undefined')InsightsUI.update();
  }
  function stat(value, label, kind) {
    const b=button('',()=>go('workflow',kind)); b.className='workspace-stat';
    b.append(h('strong',{},String(value)),h('span',{},label),h('span',{class:'stat-action'},w('Abrir','Open')));return b;
  }
  function render(el) {
    const shell=h('div',{class:'workspace-dashboard'}), meta=S.data?.meta||{};
    const hero=h('div',{class:'workspace-hero'},
      h('div',{},h('p',{class:'workspace-path'},S.slug?'~/projects/'+S.slug:'~/report-gen'),
        h('h1',{},S.data?(meta.report_title||S.slug):w('De la evidencia al informe.','From evidence to report.')),
        h('p',{class:'workspace-intro'},S.data?[meta.client||w('Cliente por completar','Client not set'),meta.lang==='en'?'English':'Español',meta.design?.name||meta.theme].filter(Boolean).join(' / '):
          w('Documenta el trabajo, conecta las evidencias y prepara una entrega que puedas defender.','Document your work, connect the evidence and prepare a defensible delivery.')),
        h('div',{class:'workspace-hero-actions'},...(S.data?
          [button(w('Continuar donde lo dejé','Continue where I left off'),()=>WorkbenchUI.resume(),typeof GuideUI==='undefined'),
            ...(typeof GuideUI==='undefined'?[button(w('Revisar entrega','Review delivery'),()=>go('workflow','review'))]:[])]:
          [button(w('Probar demo Nimbus','Try Nimbus demo'),()=>$('#demoBtn').click(),true),button(w('Crear mi proyecto','Create my project'),()=>$('#newProjectBtn').click())]))),
      h('figure',{class:'workspace-mascots'},h('img',{src:'/static/brand-mark.webp',width:300,height:200,alt:w('Prometeo y Evaristo, los dos perros de report-gen, sobre una consola.','Prometeo and Evaristo, the two report-gen dogs, above a console.')}),h('figcaption',{},'Prometeo & Evaristo')));
    shell.append(hero);
    if(typeof GuideUI!=='undefined')shell.append(GuideUI.entry());
    if(!S.data) {
      shell.append(h('div',{class:'workspace-empty-actions'},
        h('div',{},h('h2',{},w('Primero el contenido, después el diseño','Content first, then appearance')),h('p',{},w('Empieza con el diseño general recomendado. Puedes cambiar la presentación más adelante sin sustituir los hallazgos. Nimbus incluye datos y evidencias ficticios para practicar.','Start with the recommended general design. You can change its appearance later without replacing findings. Nimbus includes fictional data and evidence for practice.')),button(w('Ver diseños de informe','View report designs'),b=>DesignLibraryUI.gallery(b))),
        h('div',{},h('h2',{},w('Continúa tu trabajo','Continue your work')),h('p',{},w('Abre el respaldo de un proyecto o recupera tu espacio de trabajo en una instalación vacía.','Open a project backup or recover your workspace on an empty installation.')),button(w('Abrir respaldo de proyecto','Open project backup'),()=>$('#importProjectBtn').click()),button(w('Respaldo integral','Workspace backup'),backup))));
    } else {
      const findings=S.data.findings||[], coverage=S.data.coverage||[], done=coverage.filter(x=>x.status==='done').length;
      const findingMetric=button('',()=>go('findings'));findingMetric.className='workspace-stat';
      findingMetric.append(h('strong',{},String(findings.length)),h('span',{},w('Hallazgos y máquinas','Findings and machines')),h('span',{class:'stat-action'},w('Abrir','Open')));
      shell.append(h('div',{class:'workspace-stats'},findingMetric,stat((S.data.assets||[]).length,w('Activos registrados','Registered assets'),'assets'),stat((S.data.evidence||[]).length,w('Evidencias registradas','Registered evidence'),'evidence'),stat(done+'/'+coverage.length,w('Pruebas realizadas','Tests performed'),'coverage')));
      const recent=h('section',{class:'workspace-findings'},h('div',{class:'workspace-section-title'},h('h2',{},w('Retomar hallazgos','Resume findings')),h('span',{},findings.length+' '+w('entradas','entries'))));
      if(!findings.length)recent.append(h('p',{class:'workspace-intro'},w('Todavía no hay hallazgos. Añade uno y registra cómo lo verificaste.','No findings yet. Add one and record how you verified it.')),button(w('Añadir hallazgo','Add finding'),()=>addFinding('blank')));
      WorkbenchUI.recentFindings().forEach((f,i)=>{const b=button('',()=>go('finding',S.data.findings.indexOf(f)));b.className='workspace-finding';
        const sev=f.mode==='machine'?'machine':(f.severity||'pending');const sevNames={critical:['Crítica','Critical'],high:['Alta','High'],medium:['Media','Medium'],low:['Baja','Low'],info:['Informativa','Informational'],pending:['Pendiente de valoración','Pending assessment'],machine:['Máquina','Machine']};
        b.append(h('span',{class:'workspace-finding-id'},f.id||String(i+1)),h('span',{class:'workspace-finding-title'},f.title||w('Sin título','Untitled')),h('span',{class:'workspace-severity severity-'+sev},w(...(sevNames[sev]||sevNames.info))));recent.append(b);});
      if(findings.length>6)recent.append(button(w('Ver todos los hallazgos','View all findings'),()=>go('findings')));
      const steps=h('section',{class:'workspace-next'});WorkbenchUI.attention(steps);
      shell.append(h('div',{class:'workspace-columns'},recent,steps));
      const more=h('details',{class:'workspace-extra'},h('summary',{},w('Más herramientas del proyecto','More project tools'))),body=h('div',{class:'workspace-extra-body'});
      if(typeof InsightsUI!=='undefined')body.append(InsightsUI.entry());
      if(typeof ExperienceUI!=='undefined')ExperienceUI.guide(body);
      if(body.childElementCount){more.append(body);shell.append(more);}
    }
    if(S.projects.length>1){const projects=h('section',{class:'workspace-projects'},h('h2',{},w('Tus proyectos','Your projects')));
      S.projects.forEach(p=>{const b=button('',()=>loadProject(p.slug));b.className='workspace-project';b.append(h('strong',{},p.title||p.slug),h('span',{},p.slug),h('span',{},p.slug===S.slug?w('Abierto','Open'):(p.lang||'').toUpperCase()));projects.append(b);});shell.append(projects);}
    shell.append(h('div',{class:'workspace-footnote'},h('span',{},w('Trabajo local. Sin cuenta ni servicios externos para editar.','Local workspace. No account or external service needed to edit.')),button(w('Comprobar instalación','Check installation'),()=>$('#diagnosticsBtn').click())));
    el.append(shell);
  }
  async function backup(opener) {
    const focus=opener instanceof HTMLElement?opener:document.activeElement;
    const d=h('dialog',{class:'experience-dialog','aria-label':w('Respaldo integral','Workspace backup')}),body=h('div',{class:'experience-body'});
    d.append(h('div',{class:'experience-heading'},h('h2',{},w('Respaldo integral','Workspace backup')),button(w('Cerrar','Close'),()=>d.close())),body);
    body.append(h('p',{},w('Incluye todos los proyectos, evidencias originales, versiones y las dos bibliotecas personales. Guárdalo como información confidencial.','Includes all projects, original evidence, versions and both personal libraries. Store it as confidential information.')));
    const status=h('p',{role:'status'});
    body.append(button(w('Descargar todo','Download workspace'),async()=>{
      if(S.slug&&!await doSave())return;busyProject(true);
      try{status.textContent=w('Preparando respaldo…','Preparing backup…');const r=await requireOk(await appFetch('/api/workspace/backup',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}));
        const url=URL.createObjectURL(await r.blob());h('a',{href:url,download:'report-gen-workspace.zip'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);status.textContent=w('Respaldo descargado.','Backup downloaded.');
      }finally{busyProject(false);}
    },true),h('h3',{},w('Recuperar en una instalación vacía','Restore to an empty installation')),
    h('p',{},w('La restauración se bloquea si ya hay proyectos o plantillas personales. No combina ni sustituye información existente.','Restoration is blocked if projects or personal templates already exist. It does not merge or replace existing data.')));
    const file=h('input',{type:'file',accept:'.zip,application/zip','data-workspace-file':'backup'});
    const restoreButton=button(w('Restaurar espacio de trabajo','Restore workspace'),async()=>{
      if(!file.files.length)throw Error(w('Selecciona un respaldo.','Select a backup.'));
      const data=new FormData();data.append('file',file.files[0]);busyProject(true);
      try{
        status.textContent=w('Comprobando y recuperando…','Validating and restoring…');
        const response=await requireOk(await appFetch('/api/workspace/restore',{method:'POST',body:data})),restored=await response.json();
        await refreshProjects();if(S.projects.length)await loadProject(S.projects[0].slug);else renderMain();
        const warnings=Array.isArray(restored.warnings)?restored.warnings.filter(x=>typeof x==='string'&&x.trim()):[];
        if(warnings.length){status.setAttribute('role','alert');status.textContent=w('Espacio de trabajo recuperado. Advertencias: ','Workspace restored. Warnings: ')+warnings.join(' ');file.closest('label').hidden=true;restoreButton.hidden=true;}
        else{d.close();toast(w('Espacio de trabajo recuperado.','Workspace restored.'),'ok');}
      }
      finally{busyProject(false);}
    });body.append(h('label',{},w('Archivo de respaldo integral','Workspace backup file'),file),restoreButton,status);
    d.addEventListener('close',()=>{d.remove();if(focus?.isConnected)focus.focus();});document.body.append(d);d.showModal();
  }
  function bind() {
    $('#brandHome').addEventListener('click',()=>go('home'));$('#navHome').addEventListener('click',()=>go('home'));
    $('#deliverySlot').append($('#deliveryBtn'));$('#projectActionsList').prepend($('#demoBtn'));
    $('#workflowNav .side-head').dataset.workspaceText='projectManagement';
    const newProject=button(w('Nuevo proyecto','New project'),()=>$('#newProjectBtn').click());newProject.dataset.workspaceText='newProject';newProject.classList.add('mobile-create');$('#projectActionsList').prepend(newProject);
    const tools=h('div',{class:'workspace-utilities'},h('div',{class:'side-head','data-workspace-text':'tools'}));
    const backupButton=button(w('Respaldo integral','Workspace backup'),backup);backupButton.id='workspaceBackupBtn';
    const privacyButton=button(w('Datos privados guardados','Stored private data'),()=>PrivacyUI.open());privacyButton.id='privacyBtn';
    tools.append($('#designLibraryBtn'),backupButton,privacyButton,$('#diagnosticsBtn'));$('.sidebar').append(tools);
    $('#sidebarToggle').addEventListener('click',()=>{const open=$('.layout').classList.toggle('navigation-open');$('#sidebarToggle').setAttribute('aria-expanded',String(open));});
    $('.sidebar').addEventListener('click',event=>{if(event.target.closest('.navitem,.findinglist li')&&window.matchMedia('(max-width:760px)').matches){$('.layout').classList.remove('navigation-open');$('#sidebarToggle').setAttribute('aria-expanded','false');$('#editor').focus({preventScroll:true});}});
    document.querySelectorAll('.action-menu').forEach(menu=>menu.addEventListener('toggle',()=>{if(menu.open)document.querySelectorAll('.action-menu').forEach(other=>{if(other!==menu)other.open=false;});}));
    document.addEventListener('click',event=>{document.querySelectorAll('.action-menu[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;});});
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!document.querySelector('dialog[open],.modal.open'))document.querySelectorAll('.action-menu[open]').forEach(menu=>{menu.open=false;menu.querySelector('summary').focus();});});
  }
  return {bind,update,render,backup};
})();
