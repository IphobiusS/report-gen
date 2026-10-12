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
  const catalogState={query:'',status:'active',order:'modified',page:0};
  function projectCatalog(shell) {
    const section=h('section',{class:'workspace-projects','data-project-catalog':''},h('h2',{},w('Tus proyectos','Your projects')));
    const search=h('input',{type:'search',value:catalogState.query,'data-catalog-search':'',placeholder:w('Título, cliente o identificador','Title, client or identifier')});
    const filter=h('select',{'data-catalog-status':''}),order=h('select',{'data-catalog-order':''});
    for(const [key,label] of [['active',w('Activos','Active')],['archived',w('Archivados','Archived')],['all',w('Todos','All')],['retest',w('Retest pendiente','Pending retest')]])filter.append(h('option',{value:key},label));
    for(const [key,label] of [['modified',w('Última modificación','Last modified')],['client',w('Cliente','Client')],['deadline',w('Fecha más próxima','Nearest due date')],['retest',w('Retests pendientes','Pending retests')]])order.append(h('option',{value:key},label));
    filter.value=catalogState.status;order.value=catalogState.order;
    const controls=h('div',{class:'catalog-controls'},h('label',{},w('Buscar proyectos','Search projects'),search),h('label',{},w('Mostrar','Show'),filter),h('label',{},w('Ordenar','Sort'),order));
    const status=h('p',{role:'status',tabindex:-1,'data-catalog-count':''}),list=h('div',{class:'catalog-list'}),pager=h('div',{class:'catalog-pager'});
    section.append(controls,status,list,pager);shell.append(section);
    let rows=[],generation=0;
    const fold=value=>String(value||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase();
    async function reload(){
      const current=++generation;
      try{const values=await api.get('/api/projects');if(!section.isConnected||current!==generation)return;rows=values;paint();}
      catch(error){if(section.isConnected){status.textContent=error.message;status.setAttribute('role','alert');}}
    }
    async function change(project,patch){
      if(S.slug&&!await doSave())return;
      busyProject(true);
      try{
        // Saving the open project may advance its revision. Other project cards
        // keep their original revision so concurrent changes remain a conflict.
        const tag=project.slug===S.slug?projectStore.etag:'"'+project.revision+'"';
        await requireOk(await appFetch('/api/projects/'+encodeURIComponent(project.slug)+'/management',{method:'POST',headers:{'Content-Type':'application/json','If-Match':tag},body:JSON.stringify(patch)}));
        await refreshProjects();
        if(S.slug===project.slug)await loadProject(project.slug);else await reload();
        toast(w('Organización del proyecto guardada.','Project organization saved.'),'ok');
      }finally{busyProject(false);}
    }
    function paint(){
      const query=fold(catalogState.query),locale=S.uiLang==='en'?'en':'es';
      const matches=rows.filter(project=>((catalogState.status==='all')||(catalogState.status==='archived'?project.archived:!project.archived))&&(catalogState.status!=='retest'||project.pending_retests>0)&&fold([project.title,project.client,project.slug].join(' ')).includes(query));
      matches.sort((a,b)=>{
        if(catalogState.order==='client')return String(a.client||'').localeCompare(String(b.client||''),locale)||String(a.title).localeCompare(String(b.title),locale);
        if(catalogState.order==='deadline')return (a.next_due_date||'9999').localeCompare(b.next_due_date||'9999')||a.slug.localeCompare(b.slug);
        if(catalogState.order==='retest')return b.pending_retests-a.pending_retests||a.slug.localeCompare(b.slug);
        return String(b.modified_at).localeCompare(String(a.modified_at))||a.slug.localeCompare(b.slug);
      });
      const size=8,pages=Math.max(1,Math.ceil(matches.length/size));catalogState.page=Math.min(catalogState.page,pages-1);
      status.textContent=matches.length+' '+w('proyectos encontrados','projects found');status.setAttribute('role','status');list.replaceChildren();pager.replaceChildren();
      if(!matches.length)list.append(h('p',{},w('No hay proyectos con estos filtros.','No projects match these filters.')));
      for(const project of matches.slice(catalogState.page*size,(catalogState.page+1)*size)){
        const card=h('article',{class:'catalog-project','data-project-slug':project.slug});
        const name=button(project.title||project.slug,()=>loadProject(project.slug));name.classList.add('catalog-open');
        const description=h('div',{},h('h3',{},name),h('p',{},project.client||w('Cliente por completar','Client not set')),h('p',{class:'wf-hint'},project.slug+' · '+(project.archived?w('Archivado','Archived'):w('Activo','Active'))));
        card.append(description);
        if(project.available){
          const details=h('dl',{class:'catalog-metrics'});
          for(const [label,value] of [[w('Modificado','Modified'),new Date(project.modified_at).toLocaleString(locale)],[w('Próxima fecha','Next due date'),project.next_due_date||w('Sin fecha','No date')],[w('Retests pendientes','Pending retests'),String(project.pending_retests)]])details.append(h('div',{},h('dt',{},label),h('dd',{},value)));
          const delivery=h('input',{type:'date',value:project.delivery_date,'data-project-delivery':project.slug});
          const actions=h('div',{class:'catalog-actions'},h('label',{},w('Entrega prevista','Planned delivery'),delivery),button(w('Guardar fecha','Save date'),()=>{if(!delivery.checkValidity()){delivery.reportValidity();return;}return change(project,{delivery_date:delivery.value});}),button(project.archived?w('Reactivar','Reactivate'):w('Archivar','Archive'),()=>change(project,{archived:!project.archived})));
          card.append(details,actions);
        }else card.append(h('p',{role:'status'},w('No se pudo leer el proyecto. Abre el informe para revisar el error o recupera un respaldo.','The project could not be read. Open the report to inspect the error or recover a backup.')));
        list.append(card);
      }
      const previous=button(w('Anterior','Previous'),()=>{catalogState.page--;paint();status.focus();}),next=button(w('Siguiente','Next'),()=>{catalogState.page++;paint();status.focus();});previous.disabled=catalogState.page===0;next.disabled=catalogState.page===pages-1;
      if(pages>1)pager.append(previous,h('span',{},(catalogState.page+1)+' / '+pages),next);
    }
    for(const [control,key] of [[search,'query'],[filter,'status'],[order,'order']])control.addEventListener(key==='query'?'input':'change',()=>{catalogState[key]=control.value;catalogState.page=0;paint();});
    section.append(h('p',{class:'wf-hint'},w('Archivar conserva el contenido y permite reactivarlo. Retest pendiente cuenta las correcciones comunicadas que aún requieren verificación. La próxima fecha incluye la entrega y los plazos de hallazgos abiertos, incluso vencidos.','Archiving preserves content and can be reversed. Pending retests count reported fixes still requiring verification. The next date includes delivery and open finding deadlines, including overdue dates.')));
    status.textContent=w('Cargando proyectos…','Loading projects…');reload();
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
          [button(w('Probar demo Nimbus','Try Nimbus demo'),()=>$('#demoBtn').click(),true),button(w('Crear mi proyecto','Create my project'),b=>DesignLibraryUI.newProject(b))]))),
      h('figure',{class:'workspace-mascots'},h('img',{src:'/static/brand-mark.webp',width:300,height:200,alt:w('Prometeo y Evaristo, los dos perros de report-gen, sobre una consola.','Prometeo and Evaristo, the two report-gen dogs, above a console.')}),h('figcaption',{},'Prometeo & Evaristo')));
    shell.append(hero);
    if(typeof GuideUI!=='undefined')shell.append(GuideUI.entry());
    if(!S.data) {
      shell.append(h('div',{class:'workspace-empty-actions'},
        h('div',{},h('h2',{},w('Un punto de partida para cada informe','A starting point for every report')),h('p',{},w('Explora la galería y compara los diseños generales, empresariales y especializados. Al crear el proyecto podrás revisar su estructura. Después puedes cambiar la apariencia sin sustituir tus hallazgos.','Explore the gallery and compare general, corporate and specialized designs. Review the starter structure before creating your project. Later, you can change its appearance without replacing your findings.')),button(w('Ver diseños de informe','View report designs'),b=>DesignLibraryUI.gallery(b))),
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
    projectCatalog(shell);
    shell.append(h('div',{class:'workspace-footnote'},h('span',{},w('Trabajo local. Sin cuenta ni servicios externos para editar.','Local workspace. No account or external service needed to edit.')),button(w('Comprobar instalación','Check installation'),()=>$('#diagnosticsBtn').click())));
    el.append(shell);
  }
  async function backup(opener) {
    const focus=opener instanceof HTMLElement?opener:document.activeElement;
    const d=h('dialog',{class:'experience-dialog workspace-backup-dialog','aria-label':w('Respaldo integral','Workspace backup')}),body=h('div',{class:'experience-body'});
    d.append(h('div',{class:'experience-heading'},h('h2',{},w('Respaldo integral','Workspace backup')),button(w('Cerrar','Close'),()=>d.close())),body);
    body.append(h('p',{},w('Incluye todos los proyectos, evidencias originales, versiones y las dos bibliotecas personales. Guárdalo como información confidencial.','Includes all projects, original evidence, versions and both personal libraries. Store it as confidential information.')));
    body.append(h('p',{},w('Las capturas y formularios pendientes del navegador no se incluyen; incorpóralos y guarda antes de respaldar.','Pending browser captures and forms are not included; incorporate them and save before backing up.')));
    BackupRoutineUI.mount(body);
    const status=h('p',{role:'status'});
    const password=h('input',{type:'password',minlength:12,maxlength:256,autocomplete:'new-password','data-backup-password':'','aria-label':w('Contraseña del respaldo privado','Private backup password')}),confirmation=h('input',{type:'password',minlength:12,maxlength:256,autocomplete:'new-password','data-backup-confirm':'','aria-label':w('Repetir contraseña','Repeat password')});
    body.append(h('h3',{},w('Respaldo privado con contraseña','Password-protected private backup')),h('p',{},w('Este archivo contiene los proyectos guardados y sus archivos privados; no es una entrega para el cliente. Usa una contraseña larga y guárdala por separado: no se puede recuperar desde report-gen. El cifrado protege el archivo descargado; no cifra los proyectos en disco ni los borradores del navegador.','This file contains saved projects and their private files; it is not a client deliverable. Use a long password and keep it separately: report-gen cannot recover it. Encryption protects the downloaded file; it does not encrypt projects on disk or browser drafts.')),h('label',{},w('Contraseña (12–256 caracteres)','Password (12–256 characters)'),password),h('label',{},w('Repetir contraseña','Repeat password'),confirmation));
    async function download(encrypted){
      if(encrypted&&(password.value.length<12||password.value.length>256||password.value!==confirmation.value))throw Error(w('Usa entre 12 y 256 caracteres y repite la misma contraseña.','Use 12 to 256 characters and repeat the same password.'));
      if(S.slug&&!await doSave())return;busyProject(true);
      try{status.textContent=w('Preparando respaldo…','Preparing backup…');const r=await requireOk(await appFetch('/api/workspace/backup'+(encrypted?'/encrypted':''),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(encrypted?{password:password.value}:{})}));
        const url=URL.createObjectURL(await r.blob());h('a',{href:url,download:encrypted?'report-gen-private.rgbackup':'report-gen-workspace.zip'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);status.textContent=encrypted?w('Respaldo privado cifrado descargado. Conserva su contraseña por separado.','Encrypted private backup downloaded. Keep its password separately.'):w('ZIP privado descargado sin cifrado.','Unencrypted private ZIP downloaded.');
      }finally{password.value='';confirmation.value='';busyProject(false);}
    }
    body.append(button(w('Descargar respaldo cifrado','Download encrypted backup'),()=>download(true),true),button(w('Descargar ZIP sin cifrado','Download unencrypted ZIP'),()=>download(false)),h('h3',{},w('Recuperar en una instalación vacía','Restore to an empty installation')),
    h('p',{},w('La restauración se bloquea si ya hay proyectos o plantillas personales. No combina ni sustituye información existente.','Restoration is blocked if projects or personal templates already exist. It does not merge or replace existing data.')));
    const file=h('input',{type:'file',accept:'.zip,.rgbackup,application/zip,application/octet-stream','data-workspace-file':'backup'});
    const restorePassword=h('input',{type:'password',maxlength:256,autocomplete:'current-password','data-restore-password':'','aria-label':w('Contraseña del respaldo cifrado','Encrypted backup password')});
    const restoreButton=button(w('Restaurar espacio de trabajo','Restore workspace'),async()=>{
      if(!file.files.length)throw Error(w('Selecciona un respaldo.','Select a backup.'));
      const data=new FormData();data.append('file',file.files[0]);if(restorePassword.value)data.append('password',restorePassword.value);busyProject(true);
      try{
        status.textContent=w('Comprobando y recuperando…','Validating and restoring…');
        const response=await requireOk(await appFetch('/api/workspace/restore',{method:'POST',body:data})),restored=await response.json();
        await refreshProjects();if(S.projects.length)await loadProject(S.projects[0].slug);else renderMain();
        const warnings=Array.isArray(restored.warnings)?restored.warnings.filter(x=>typeof x==='string'&&x.trim()):[];
        if(warnings.length){status.setAttribute('role','alert');status.textContent=w('Espacio de trabajo recuperado. Advertencias: ','Workspace restored. Warnings: ')+warnings.join(' ');file.closest('label').hidden=true;restoreButton.hidden=true;}
        else{d.close();toast(w('Espacio de trabajo recuperado.','Workspace restored.'),'ok');}
      }
      finally{restorePassword.value='';busyProject(false);}
    });body.append(h('label',{},w('Archivo de respaldo integral','Workspace backup file'),file),h('label',{},w('Contraseña (solo para .rgbackup)','Password (only for .rgbackup)'),restorePassword),h('p',{},w('La recuperación autentica el archivo cifrado y valida el contenido antes de activar los proyectos. Un ZIP sin cifrar no usa contraseña.','Restore authenticates the encrypted file and validates its contents before activating projects. An unencrypted ZIP has no password.')),restoreButton,status);
    d.addEventListener('close',()=>{password.value='';confirmation.value='';restorePassword.value='';d.remove();if(focus?.isConnected)focus.focus();});document.body.append(d);d.showModal();
  }
  function bind() {
    $('#brandHome').addEventListener('click',()=>go('home'));$('#navHome').addEventListener('click',()=>go('home'));
    $('#deliverySlot').append($('#deliveryBtn'));$('#projectActionsList').prepend($('#demoBtn'));
    $('#workflowNav .side-head').dataset.workspaceText='projectManagement';
    const newProject=button(w('Nuevo proyecto','New project'),b=>DesignLibraryUI.newProject(b));newProject.dataset.workspaceText='newProject';newProject.classList.add('mobile-create');$('#projectActionsList').prepend(newProject);
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
