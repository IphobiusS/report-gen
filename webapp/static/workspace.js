/* The workspace reads report data. Navigating or changing UI language never edits it. */
const WorkspaceUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const labels = {
    skip:['Saltar al contenido','Skip to content', "Pular para o conteúdo"], activeProject:['Proyecto activo','Active project', "Projeto ativo"],
    navigation:['Navegación','Navigation', "Navegação"], home:['Inicio','Overview', "Visão geral"], projectActions:['Proyecto','Project', "Projeto"],
    exportOptions:['Vista y exportación','Preview and export', "Prévia e exportação"], format:['Formato','Format', "Formato"],
    tools:['Bibliotecas y respaldo','Libraries and backup', "Bibliotecas e backup"], newProject:['Nuevo proyecto','New project', "Novo projeto"], projectManagement:['Gestión del proyecto','Project management', "Gerenciamento de projetos"]
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
      S.sel.type==='capture'?w('Bandeja de captura','Capture inbox', "Caixa de capturas"):
      S.sel.type==='findings'?w('Hallazgos','Findings', "Achados"):
      guide?w('Guía del primer informe','First report guide', "Guia do primeiro relatório"):home?w('Inicio','Overview', "Visão geral"):w('Informe','Report', "Relatório");
    $('#workspaceContext').textContent=section||w('Espacio de trabajo','Workspace', "Espaço de trabalho");
    $('#brandHome').title='report-gen: '+w('inicio','overview', "visão geral");
    $('#globalSearch').setAttribute('aria-label',w('Buscar en el proyecto','Search project', "Pesquisar no projeto"));
    $('#workspaceSidebar').setAttribute('aria-label',w('Navegación del proyecto','Project navigation', "Navegação do projeto"));
    $('#editor').setAttribute('aria-label',w('Contenido del proyecto','Project content', "Conteúdo do projeto"));
    $('#pdfPreview').title=w('Vista previa del informe','Report preview', "Prévia do relatório");
    $('#langToggle').setAttribute('aria-label',w('ES: Idioma de la interfaz: español.','EN: Interface language: English.', "PT: Idioma da interface: Português (Brasil)."));
    $('#themeToggle').setAttribute('aria-label',$('#themeToggle').title);
    $('#validateBtn').setAttribute('aria-label',w('Validar informe','Validate report', "Validar relatório"));
    $('#workspaceBackupBtn').textContent=w('Respaldo integral','Workspace backup', "Backup do espaço de trabalho");
    const privacy=$('#privacyBtn');if(privacy){privacy.textContent=w('Datos privados guardados','Stored private data', "Dados privados armazenados");privacy.disabled=!S.slug;}
    $('#designLibraryBtn').textContent=w('Biblioteca de informes','Report design library', "Biblioteca de modelos de relatório");
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
    b.append(h('strong',{},String(value)),h('span',{},label),h('span',{class:'stat-action'},w('Abrir','Open', "Abrir")));return b;
  }
  const catalogState={query:'',status:'active',order:'modified',page:0};
  function projectCatalog(shell) {
    const section=h('section',{class:'workspace-projects','data-project-catalog':''},h('h2',{},w('Tus proyectos','Your projects', "Seus projetos")));
    const search=h('input',{type:'search',value:catalogState.query,'data-catalog-search':'',placeholder:w('Título, cliente o identificador','Title, client or identifier', "Título, cliente ou identificador")});
    const filter=h('select',{'data-catalog-status':''}),order=h('select',{'data-catalog-order':''});
    for(const [key,label] of [['active',w('Activos','Active', "Ativos")],['archived',w('Archivados','Archived', "Arquivados")],['all',w('Todos','All', "Todos")],['retest',w('Retest pendiente','Pending retest', "Reteste pendente")]])filter.append(h('option',{value:key},label));
    for(const [key,label] of [['modified',w('Última modificación','Last modified', "Última alteração")],['client',w('Cliente','Client', "Cliente")],['deadline',w('Fecha más próxima','Nearest due date', "Prazo mais próximo")],['retest',w('Retests pendientes','Pending retests', "Retestes pendentes")]])order.append(h('option',{value:key},label));
    filter.value=catalogState.status;order.value=catalogState.order;
    const controls=h('div',{class:'catalog-controls'},h('label',{},w('Buscar proyectos','Search projects', "Pesquisar projetos"),search),h('label',{},w('Mostrar','Show', "Mostrar"),filter),h('label',{},w('Ordenar','Sort', "Ordenar"),order));
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
        toast(w('Organización del proyecto guardada.','Project organization saved.', "Organização do projeto salva."),'ok');
      }finally{busyProject(false);}
    }
    function paint(){
      const query=fold(catalogState.query),locale=languageTag(S.uiLang);
      const matches=rows.filter(project=>((catalogState.status==='all')||(catalogState.status==='archived'?project.archived:!project.archived))&&(catalogState.status!=='retest'||project.pending_retests>0)&&fold([project.title,project.client,project.slug].join(' ')).includes(query));
      matches.sort((a,b)=>{
        if(catalogState.order==='client')return String(a.client||'').localeCompare(String(b.client||''),locale)||String(a.title).localeCompare(String(b.title),locale);
        if(catalogState.order==='deadline')return (a.next_due_date||'9999').localeCompare(b.next_due_date||'9999')||a.slug.localeCompare(b.slug);
        if(catalogState.order==='retest')return b.pending_retests-a.pending_retests||a.slug.localeCompare(b.slug);
        return String(b.modified_at).localeCompare(String(a.modified_at))||a.slug.localeCompare(b.slug);
      });
      const size=8,pages=Math.max(1,Math.ceil(matches.length/size));catalogState.page=Math.min(catalogState.page,pages-1);
      status.textContent=matches.length+' '+w('proyectos encontrados','projects found', "projetos encontrados");status.setAttribute('role','status');list.replaceChildren();pager.replaceChildren();
      if(!matches.length)list.append(h('p',{},w('No hay proyectos con estos filtros.','No projects match these filters.', "Nenhum projeto corresponde a estes filtros.")));
      for(const project of matches.slice(catalogState.page*size,(catalogState.page+1)*size)){
        const card=h('article',{class:'catalog-project','data-project-slug':project.slug});
        const name=button(project.title||project.slug,()=>loadProject(project.slug));name.classList.add('catalog-open');
        const description=h('div',{},h('h3',{},name),h('p',{},project.client||w('Cliente por completar','Client not set', "Cliente não definido")),h('p',{class:'wf-hint'},project.slug+' · '+(project.archived?w('Archivado','Archived', "Arquivados"):w('Activo','Active', "Ativos"))));
        card.append(description);
        if(project.available){
          const details=h('dl',{class:'catalog-metrics'});
          for(const [label,value] of [[w('Modificado','Modified', "Alterado"),new Date(project.modified_at).toLocaleString(locale)],[w('Próxima fecha','Next due date', "Próximo prazo"),project.next_due_date||w('Sin fecha','No date', "Sem data")],[w('Retests pendientes','Pending retests', "Retestes pendentes"),String(project.pending_retests)]])details.append(h('div',{},h('dt',{},label),h('dd',{},value)));
          const delivery=h('input',{type:'date',value:project.delivery_date,'data-project-delivery':project.slug});
          const actions=h('div',{class:'catalog-actions'},h('label',{},w('Entrega prevista','Planned delivery', "Entrega prevista"),delivery),button(w('Guardar fecha','Save date', "Salvar data"),()=>{if(!delivery.checkValidity()){delivery.reportValidity();return;}return change(project,{delivery_date:delivery.value});}),button(project.archived?w('Reactivar','Reactivate', "Reativar"):w('Archivar','Archive', "Arquivar"),()=>change(project,{archived:!project.archived})));
          card.append(details,actions);
        }else card.append(h('p',{role:'status'},w('No se pudo leer el proyecto. Abre el informe para revisar el error o recupera un respaldo.','The project could not be read. Open the report to inspect the error or recover a backup.', "Não foi possível ler o projeto. Abra o relatório para verificar o erro ou recuperar um backup.")));
        list.append(card);
      }
      const previous=button(w('Anterior','Previous', "Anterior"),()=>{catalogState.page--;paint();status.focus();}),next=button(w('Siguiente','Next', "Próximo"),()=>{catalogState.page++;paint();status.focus();});previous.disabled=catalogState.page===0;next.disabled=catalogState.page===pages-1;
      if(pages>1)pager.append(previous,h('span',{},(catalogState.page+1)+' / '+pages),next);
    }
    for(const [control,key] of [[search,'query'],[filter,'status'],[order,'order']])control.addEventListener(key==='query'?'input':'change',()=>{catalogState[key]=control.value;catalogState.page=0;paint();});
    section.append(h('p',{class:'wf-hint'},w('Archivar conserva el contenido y permite reactivarlo. Retest pendiente cuenta las correcciones comunicadas que aún requieren verificación. La próxima fecha incluye la entrega y los plazos de hallazgos abiertos, incluso vencidos.','Archiving preserves content and can be reversed. Pending retests count reported fixes still requiring verification. The next date includes delivery and open finding deadlines, including overdue dates.', "Arquivar preserva o conteúdo e pode ser desfeito. Os retestes pendentes contabilizam correções informadas que ainda exigem verificação. A próxima data inclui a entrega e os prazos dos achados abertos, inclusive os vencidos.")));
    status.textContent=w('Cargando proyectos…','Loading projects…', "Carregando projetos…");reload();
  }
  function render(el) {
    const shell=h('div',{class:'workspace-dashboard'}), meta=S.data?.meta||{};
    const hero=h('div',{class:'workspace-hero'},
      h('div',{},h('p',{class:'workspace-path'},S.slug?'~/projects/'+S.slug:'~/report-gen'),
        h('h1',{},S.data?(meta.report_title||S.slug):w('De la evidencia al informe.','From evidence to report.', "Da evidência ao relatório.")),
        h('p',{class:'workspace-intro'},S.data?[meta.client||w('Cliente por completar','Client not set', "Cliente não definido"),({es:'Español',en:'English',pt:'Português (Brasil)'})[normalizeUiLanguage(meta.lang,'en')],meta.design?.name||meta.theme].filter(Boolean).join(' / '):
          w('Documenta el trabajo, conecta las evidencias y prepara una entrega que puedas defender.','Document your work, connect the evidence and prepare a defensible delivery.', "Documente seu trabalho, relacione as evidências e prepare uma entrega fundamentada.")),
        h('div',{class:'workspace-hero-actions'},...(S.data?
          [button(w('Continuar donde lo dejé','Continue where I left off', "Continuar de onde parei"),()=>WorkbenchUI.resume(),typeof GuideUI==='undefined'),
            ...(typeof GuideUI==='undefined'?[button(w('Revisar entrega','Review delivery', "Revisar entrega"),()=>go('workflow','review'))]:[])]:
          [button(w('Probar demo Nimbus','Try Nimbus demo', "Experimentar demonstração Nimbus"),()=>$('#demoBtn').click(),true),button(w('Crear mi proyecto','Create my project', "Criar meu projeto"),b=>DesignLibraryUI.newProject(b))]))),
      h('figure',{class:'workspace-mascots'},h('img',{src:'/static/brand-mark.webp',width:300,height:200,alt:w('Prometeo y Evaristo, los dos perros de report-gen, sobre una consola.','Prometeo and Evaristo, the two report-gen dogs, above a console.', "Prometeo e Evaristo, os dois cães do report-gen, acima de um console.")}),h('figcaption',{},'Prometeo & Evaristo')));
    shell.append(hero);
    if(typeof GuideUI!=='undefined')shell.append(GuideUI.entry());
    if(!S.data) {
      shell.append(h('div',{class:'workspace-empty-actions'},
        h('div',{},h('h2',{},w('Un punto de partida para cada informe','A starting point for every report', "Um ponto de partida para cada relatório")),h('p',{},w('Explora la galería y compara los diseños generales, empresariales y especializados. Al crear el proyecto podrás revisar su estructura. Después puedes cambiar la apariencia sin sustituir tus hallazgos.','Explore the gallery and compare general, corporate and specialized designs. Review the starter structure before creating your project. Later, you can change its appearance without replacing your findings.', "Explore a galeria e compare modelos gerais, corporativos e especializados. Revise a estrutura inicial antes de criar seu projeto. Depois, você pode mudar a aparência sem substituir seus achados.")),button(w('Ver diseños de informe','View report designs', "Ver modelos de relatório"),b=>DesignLibraryUI.gallery(b))),
        h('div',{},h('h2',{},w('Continúa tu trabajo','Continue your work', "Continue seu trabalho")),h('p',{},w('Abre el respaldo de un proyecto o recupera tu espacio de trabajo en una instalación vacía.','Open a project backup or recover your workspace on an empty installation.', "Abra um backup do projeto ou recupere seu espaço de trabalho em uma instalação vazia.")),button(w('Abrir respaldo de proyecto','Open project backup', "Abrir backup do projeto"),()=>$('#importProjectBtn').click()),button(w('Respaldo integral','Workspace backup', "Backup do espaço de trabalho"),backup))));
    } else {
      const findings=S.data.findings||[], coverage=S.data.coverage||[], done=coverage.filter(x=>x.status==='done').length;
      const findingMetric=button('',()=>go('findings'));findingMetric.className='workspace-stat';
      findingMetric.append(h('strong',{},String(findings.length)),h('span',{},w('Hallazgos y máquinas','Findings and machines', "Achados e máquinas")),h('span',{class:'stat-action'},w('Abrir','Open', "Abrir")));
      shell.append(h('div',{class:'workspace-stats'},findingMetric,stat((S.data.assets||[]).length,w('Activos registrados','Registered assets', "Ativos cadastrados"),'assets'),stat((S.data.evidence||[]).length,w('Evidencias registradas','Registered evidence', "Evidências cadastradas"),'evidence'),stat(done+'/'+coverage.length,w('Pruebas realizadas','Tests performed', "Testes realizados"),'coverage')));
      const recent=h('section',{class:'workspace-findings'},h('div',{class:'workspace-section-title'},h('h2',{},w('Retomar hallazgos','Resume findings', "Retomar achados")),h('span',{},findings.length+' '+w('entradas','entries', "registros"))));
      if(!findings.length)recent.append(h('p',{class:'workspace-intro'},w('Todavía no hay hallazgos. Añade uno y registra cómo lo verificaste.','No findings yet. Add one and record how you verified it.', "Ainda não há achados. Adicione um e registre como o verificou.")),button(w('Añadir hallazgo','Add finding', "Adicionar achado"),()=>addFinding('blank')));
      WorkbenchUI.recentFindings().forEach((f,i)=>{const b=button('',()=>go('finding',S.data.findings.indexOf(f)));b.className='workspace-finding';
        const sev=f.mode==='machine'?'machine':(f.severity||'pending');const sevNames={critical:['Crítica','Critical', "Crítica"],high:['Alta','High','Alta'],medium:['Media','Medium', "Média"],low:['Baja','Low','Baixa'],info:['Informativa','Informational', "Informativa"],pending:['Pendiente de valoración','Pending assessment', "Avaliação pendente"],machine:['Máquina','Machine', "Máquina"]};
        b.append(h('span',{class:'workspace-finding-id'},f.id||String(i+1)),h('span',{class:'workspace-finding-title'},f.title||w('Sin título','Untitled', "Sem título")),h('span',{class:'workspace-severity severity-'+sev},w(...(sevNames[sev]||sevNames.info))));recent.append(b);});
      if(findings.length>6)recent.append(button(w('Ver todos los hallazgos','View all findings', "Ver todos os achados"),()=>go('findings')));
      const steps=h('section',{class:'workspace-next'});WorkbenchUI.attention(steps);
      shell.append(h('div',{class:'workspace-columns'},recent,steps));
      const more=h('details',{class:'workspace-extra'},h('summary',{},w('Más herramientas del proyecto','More project tools', "Mais ferramentas do projeto"))),body=h('div',{class:'workspace-extra-body'});
      if(typeof InsightsUI!=='undefined')body.append(InsightsUI.entry());
      if(typeof ExperienceUI!=='undefined')ExperienceUI.guide(body);
      if(body.childElementCount){more.append(body);shell.append(more);}
    }
    projectCatalog(shell);
    shell.append(h('div',{class:'workspace-footnote'},h('span',{},w('Trabajo local. Sin cuenta ni servicios externos para editar.','Local workspace. No account or external service needed to edit.', "Espaço de trabalho local. Nenhuma conta ou serviço externo é necessário para editar.")),button(w('Comprobar instalación','Check installation', "Verificar instalação"),()=>$('#diagnosticsBtn').click())));
    el.append(shell);
  }
  async function backup(opener) {
    const focus=opener instanceof HTMLElement?opener:document.activeElement;
    const d=h('dialog',{class:'experience-dialog workspace-backup-dialog','aria-label':w('Respaldo integral','Workspace backup', "Backup do espaço de trabalho")}),body=h('div',{class:'experience-body'});
    d.append(h('div',{class:'experience-heading'},h('h2',{},w('Respaldo integral','Workspace backup', "Backup do espaço de trabalho")),button(w('Cerrar','Close', "Fechar"),()=>d.close())),body);
    body.append(h('p',{},w('Incluye todos los proyectos, evidencias originales, versiones y las dos bibliotecas personales. Guárdalo como información confidencial.','Includes all projects, original evidence, versions and both personal libraries. Store it as confidential information.', "Inclui todos os projetos, evidências originais, versões e as duas bibliotecas pessoais. Armazene como informação confidencial.")));
    body.append(h('p',{},w('Las capturas y formularios pendientes del navegador no se incluyen; incorpóralos y guarda antes de respaldar.','Pending browser captures and forms are not included; incorporate them and save before backing up.', "Capturas e formulários pendentes do navegador não estão incluídos; incorpore-os e salve antes de criar o backup.")));
    BackupRoutineUI.mount(body);
    const status=h('p',{role:'status'});
    const password=h('input',{type:'password',minlength:12,maxlength:256,autocomplete:'new-password','data-backup-password':'','aria-label':w('Contraseña del respaldo privado','Private backup password', "Senha do backup privado")}),confirmation=h('input',{type:'password',minlength:12,maxlength:256,autocomplete:'new-password','data-backup-confirm':'','aria-label':w('Repetir contraseña','Repeat password', "Repetir senha")});
    body.append(h('h3',{},w('Respaldo privado con contraseña','Password-protected private backup', "Backup privado protegido por senha")),h('p',{},w('Este archivo contiene los proyectos guardados y sus archivos privados; no es una entrega para el cliente. Usa una contraseña larga y guárdala por separado: no se puede recuperar desde report-gen. El cifrado protege el archivo descargado; no cifra los proyectos en disco ni los borradores del navegador.','This file contains saved projects and their private files; it is not a client deliverable. Use a long password and keep it separately: report-gen cannot recover it. Encryption protects the downloaded file; it does not encrypt projects on disk or browser drafts.', "Este arquivo contém projetos salvos e seus arquivos privados; não é uma entrega ao cliente. Use uma senha longa e guarde-a separadamente: o report-gen não pode recuperá-la. A criptografia protege o arquivo baixado; não criptografa os projetos no disco nem os rascunhos do navegador.")),h('label',{},w('Contraseña (12–256 caracteres)','Password (12–256 characters)', "Senha (12–256 caracteres)"),password),h('label',{},w('Repetir contraseña','Repeat password', "Repetir senha"),confirmation));
    async function download(encrypted){
      if(encrypted&&(password.value.length<12||password.value.length>256||password.value!==confirmation.value))throw Error(w('Usa entre 12 y 256 caracteres y repite la misma contraseña.','Use 12 to 256 characters and repeat the same password.', "Use de 12 a 256 caracteres e repita a mesma senha."));
      if(S.slug&&!await doSave())return;busyProject(true);
      try{status.textContent=w('Preparando respaldo…','Preparing backup…', "Preparando backup…");const r=await requireOk(await appFetch('/api/workspace/backup'+(encrypted?'/encrypted':''),{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(encrypted?{password:password.value}:{})}));
        const url=URL.createObjectURL(await r.blob());h('a',{href:url,download:encrypted?'report-gen-private.rgbackup':'report-gen-workspace.zip'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);status.textContent=encrypted?w('Respaldo privado cifrado descargado. Conserva su contraseña por separado.','Encrypted private backup downloaded. Keep its password separately.', "Backup privado criptografado baixado. Guarde a senha separadamente."):w('ZIP privado descargado sin cifrado.','Unencrypted private ZIP downloaded.', "ZIP privado sem criptografia baixado.");
      }finally{password.value='';confirmation.value='';busyProject(false);}
    }
    body.append(button(w('Descargar respaldo cifrado','Download encrypted backup', "Baixar backup criptografado"),()=>download(true),true),button(w('Descargar ZIP sin cifrado','Download unencrypted ZIP', "Baixar ZIP sem criptografia"),()=>download(false)),h('h3',{},w('Recuperar en una instalación vacía','Restore to an empty installation', "Restaurar em uma instalação vazia")),
    h('p',{},w('La restauración se bloquea si ya hay proyectos o plantillas personales. No combina ni sustituye información existente.','Restoration is blocked if projects or personal templates already exist. It does not merge or replace existing data.', "A restauração é bloqueada se já houver projetos ou modelos pessoais. Ela não mescla nem substitui dados existentes.")));
    const file=h('input',{type:'file',accept:'.zip,.rgbackup,application/zip,application/octet-stream','data-workspace-file':'backup'});
    const restorePassword=h('input',{type:'password',maxlength:256,autocomplete:'current-password','data-restore-password':'','aria-label':w('Contraseña del respaldo cifrado','Encrypted backup password', "Senha do backup criptografado")});
    const restoreButton=button(w('Restaurar espacio de trabajo','Restore workspace', "Restaurar espaço de trabalho"),async()=>{
      if(!file.files.length)throw Error(w('Selecciona un respaldo.','Select a backup.', "Selecione um backup."));
      const data=new FormData();data.append('file',file.files[0]);if(restorePassword.value)data.append('password',restorePassword.value);busyProject(true);
      try{
        status.textContent=w('Comprobando y recuperando…','Validating and restoring…', "Validando e restaurando…");
        const response=await requireOk(await appFetch('/api/workspace/restore',{method:'POST',body:data})),restored=await response.json();
        await refreshProjects();if(S.projects.length)await loadProject(S.projects[0].slug);else renderMain();
        const warnings=Array.isArray(restored.warnings)?restored.warnings.filter(x=>typeof x==='string'&&x.trim()):[];
        if(warnings.length){status.setAttribute('role','alert');status.textContent=w('Espacio de trabajo recuperado. Advertencias: ','Workspace restored. Warnings: ', "Espaço de trabalho restaurado. Avisos: ")+warnings.join(' ');file.closest('label').hidden=true;restoreButton.hidden=true;}
        else{d.close();toast(w('Espacio de trabajo recuperado.','Workspace restored.', "Espaço de trabalho restaurado."),'ok');}
      }
      finally{restorePassword.value='';busyProject(false);}
    });body.append(h('label',{},w('Archivo de respaldo integral','Workspace backup file', "Arquivo de backup do espaço de trabalho"),file),h('label',{},w('Contraseña (solo para .rgbackup)','Password (only for .rgbackup)', "Senha (somente para .rgbackup)"),restorePassword),h('p',{},w('La recuperación autentica el archivo cifrado y valida el contenido antes de activar los proyectos. Un ZIP sin cifrar no usa contraseña.','Restore authenticates the encrypted file and validates its contents before activating projects. An unencrypted ZIP has no password.', "A restauração autentica o arquivo criptografado e valida seu conteúdo antes de ativar os projetos. Um ZIP sem criptografia não tem senha.")),restoreButton,status);
    d.addEventListener('close',()=>{password.value='';confirmation.value='';restorePassword.value='';d.remove();if(focus?.isConnected)focus.focus();});document.body.append(d);d.showModal();
  }
  function bind() {
    $('#brandHome').addEventListener('click',()=>go('home'));$('#navHome').addEventListener('click',()=>go('home'));
    $('#deliverySlot').append($('#deliveryBtn'));$('#projectActionsList').prepend($('#demoBtn'));
    $('#workflowNav .side-head').dataset.workspaceText='projectManagement';
    const newProject=button(w('Nuevo proyecto','New project', "Novo projeto"),b=>DesignLibraryUI.newProject(b));newProject.dataset.workspaceText='newProject';newProject.classList.add('mobile-create');$('#projectActionsList').prepend(newProject);
    const tools=h('div',{class:'workspace-utilities'},h('div',{class:'side-head','data-workspace-text':'tools'}));
    const backupButton=button(w('Respaldo integral','Workspace backup', "Backup do espaço de trabalho"),backup);backupButton.id='workspaceBackupBtn';
    const privacyButton=button(w('Datos privados guardados','Stored private data', "Dados privados armazenados"),()=>PrivacyUI.open());privacyButton.id='privacyBtn';
    tools.append($('#designLibraryBtn'),backupButton,privacyButton,$('#diagnosticsBtn'));$('.sidebar').append(tools);
    $('#sidebarToggle').addEventListener('click',()=>{const open=$('.layout').classList.toggle('navigation-open');$('#sidebarToggle').setAttribute('aria-expanded',String(open));});
    $('.sidebar').addEventListener('click',event=>{if(event.target.closest('.navitem,.findinglist li')&&window.matchMedia('(max-width:760px)').matches){$('.layout').classList.remove('navigation-open');$('#sidebarToggle').setAttribute('aria-expanded','false');$('#editor').focus({preventScroll:true});}});
    document.querySelectorAll('.action-menu').forEach(menu=>menu.addEventListener('toggle',()=>{if(menu.open)document.querySelectorAll('.action-menu').forEach(other=>{if(other!==menu)other.open=false;});}));
    document.addEventListener('click',event=>{document.querySelectorAll('.action-menu[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;});});
    document.addEventListener('keydown',event=>{if(event.key==='Escape'&&!document.querySelector('dialog[open],.modal.open'))document.querySelectorAll('.action-menu[open]').forEach(menu=>{menu.open=false;menu.querySelector('summary').focus();});});
  }
  return {bind,update,render,backup};
})();
