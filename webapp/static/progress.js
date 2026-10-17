/* Durable save feedback, immutable export jobs and reviewed scanner intake. */
const ProgressUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const diagnosticLocations=(details,source=null)=>typeof DiagnosticUI==='undefined'?null:DiagnosticUI.render(details,S.uiLang,source);
  const stages={rendering_html:['Generando HTML','Rendering HTML', "Gerando HTML"],checking_html:['Comprobando HTML','Checking HTML', "Verificando HTML"],queued:['En cola','Queued', "Na fila"],validating:['Validando copia guardada','Validating saved snapshot', "Validando cópia salva"],
    rendering_pdf:['Generando PDF','Rendering PDF', "Gerando PDF"],checking_pdf:['Comprobando PDF','Checking PDF', "Verificando PDF"],
    rendering_docx:['Generando Word','Rendering Word', "Gerando Word"],checking_docx:['Comprobando Word','Checking Word', "Verificando Word"],
    rendering_md:['Generando Markdown','Rendering Markdown', "Gerando Markdown"],checking_md:['Comprobando Markdown','Checking Markdown', "Verificando Markdown"],
    packaging:['Preparando ZIP','Packaging ZIP', "Preparando ZIP"],done:['Lista para descargar','Ready to download', "Pronto para baixar"],
    cancelling:['Cancelando y limpiando archivos','Cancelling and cleaning files', "Cancelando e limpando arquivos"],cancelled:['Cancelada','Cancelled', "Cancelada"],error:['Error de exportación','Export failed', "Falha na exportação"]};
  const fields={title:['Título','Title', "Título"],severity:['Severidad','Severity', "Severidade"],affected:['Objetivo','Target', "Alvo"],
    description_md:['Descripción','Description', "Descrição"],impact_md:['Impacto','Impact', "Impacto"],remediation_md:['Remediación','Remediation', "Correção"],
    cvss_vector:['Vector CVSS','CVSS vector', "Vetor CVSS"],cwe:['CWE','CWE', "CWE"],references:['Referencias','References', "Referências"],external_id:['ID de origen','Source ID', "ID de origem"]};
  let state='ready', saveError=null, jobsDialog=null, opener=null;
  function button(text,action,primary=false){
    const b=h('button',{type:'button',class:'btn'+(primary?' primary':'')},text);
    b.addEventListener('click',async()=>{opener=b;b.disabled=true;try{await action();}catch(e){toast(e.message,'err');}finally{b.disabled=false;}});return b;
  }
  async function json(url,options){const r=await requireOk(await appFetch(url,options));return {data:await r.json(),etag:r.headers.get('ETag')};}
  function options(body,etag){return {method:'POST',headers:{'Content-Type':'application/json',...(etag?{'If-Match':etag}:{})},body:JSON.stringify(body)};}
  function dialog(title){
    const previous=document.activeElement===document.body?opener:document.activeElement,d=h('dialog',{class:'experience-dialog progress-dialog','aria-label':title});
    const body=h('div',{class:'experience-body'});
    d.append(h('div',{class:'experience-heading'},h('h2',{},title),button(w('Cerrar','Close', "Fechar"),()=>d.close())),body);
    d.addEventListener('close',()=>{d.remove();const target=previous?.closest('details:not([open])')?.querySelector('summary')||previous;if(target?.isConnected&&!target.disabled)target.focus();});
    document.body.append(d);d.showModal();return {d,body};
  }
  function saveState(next,error){
    state=next;
    if(error)saveError=error;
    if(next==='saved'||next==='ready')saveError=null;
    drawSave();
    if(typeof StudioUI!=="undefined")StudioUI.update();
  }
  function drawSave(){
    const el=$('#saveState');if(!el)return;
    const labels={ready:w('Guardado en disco','Saved on disk', "Salvo no disco"),pending:w('Cambios pendientes','Unsaved changes', "Alterações não salvas"),
      saving:w('Guardando…','Saving…', "Salvando…"),saved:w('Guardado','Saved', "Salvo"),loading:w('Abriendo proyecto…','Opening project…', "Abrindo projeto…"),error:w('Sin guardar','Not saved', "Não salvo")};
    el.dataset.state=saveError?'error':state;
    el.textContent=saveError?w('Error de guardado','Save failed', "Falha ao salvar"):(S.slug||projectStore.slug?labels[state]||labels.ready:w('Sin proyecto','No project', "Nenhum projeto"));
    if(projectStore.lastSavedAt)el.textContent+=' / '+projectStore.lastSavedAt.toLocaleTimeString(languageTag(S.uiLang));
    el.title=projectStore.lastSavedAt?w('Último guardado correcto: ','Last successful save: ', "Último salvamento bem-sucedido: ")+projectStore.lastSavedAt.toLocaleString():el.textContent;
    let banner=$('#saveError');
    if(!saveError){const focused=banner?.contains(document.activeElement);banner?.remove();if(focused)$('#editor')?.focus({preventScroll:true});return;}
    if(!banner){banner=h('div',{id:'saveError',class:'save-error',role:'alert'},h('span',{}),button('',async()=>{if(await doSave())$('#editor')?.focus({preventScroll:true});}));$('.topbar').after(banner);}
    banner.querySelector('span').textContent=w('Tus cambios siguen en esta pestaña. ','Your changes remain in this tab. ', "Suas alterações permanecem nesta aba. ")+saveError.message;
    banner.querySelector('button').textContent=w('Reintentar guardado','Retry saving', "Tentar salvar novamente");
  }
  async function enqueue(slug,etag,body,show=true){
    const {data}=await json('/api/projects/'+encodeURIComponent(slug)+'/jobs',options(body,etag));
    if(show)jobs();return data;
  }
  async function download(job){
    const response=await requireOk(await appFetch('/api/jobs/'+job.id+'/download'));
    const url=URL.createObjectURL(await response.blob());h('a',{href:url,download:job.filename}).click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
  async function verification(job){
    const {data}=await json('/api/jobs/'+job.id+'/verification');
    const {body}=dialog(w('Comprobaciones de la exportación','Export checks', "Verificações da exportação"));
    body.append(h('p',{},w('Revisión guardada: ','Saved revision: ', "Revisão salva: ")+(data.source_revision||'—')),
      h('p',{},w('Estos controles verifican los archivos generados. No confirman los hallazgos ni reemplazan la revisión visual.','These checks verify generated files. They do not confirm findings or replace visual review.', "Estas verificações validam os arquivos gerados. Não confirmam achados nem substituem a revisão visual.")));
    for(const [name,file] of Object.entries(data.files||{})){
      const section=h('section',{class:'card export-check-card'},h('h3',{},name),h('p',{},file.bytes+' bytes'),h('p',{class:'hash'},'SHA-256: '+file.sha256));
      const labels={pdf_finding_regions_checked:['Texto comprobado por hallazgo en PDF','PDF text checked per finding', "Texto do PDF verificado por achado"],authored_list_items_order_checked:['Elementos de lista originales comprobados en orden','Source list items checked in order', "Itens de lista originais verificados em ordem"],authored_tables_checked:['Tablas originales comprobadas','Source tables checked', "Tabelas originais verificadas"],pdf_wrapped_code_lines:['Líneas de código divididas en PDF','Code lines wrapped in PDF', "Linhas de código quebradas no PDF"],metadata_values_checked:['Metadatos comprobados','Metadata checked', "Metadados verificados"],link_targets_checked:['Destinos comparados con el original','Link targets matched to source', "Destinos dos links comparados com a origem"],evidence_associations_checked:['Colocaciones de evidencia comprobadas','Evidence placements matched to source', "Posicionamentos de evidências comparados com a origem"],static_visibility_checked:['Visibilidad estática comprobada','Static visibility checked', "Visibilidade estática verificada"],evidence_association_checked:['Asociación de imágenes comprobada','Image association checked', "Associação de imagens verificada"],pages:['Páginas','Pages', "Páginas"],image_placements:['Imágenes','Images', "Imagens"],expected_image_placements:['Imágenes previstas','Expected images', "Imagens esperadas"],toc_references_checked:['Referencias del índice comprobadas','TOC references checked', "Referências do índice verificadas"],archive_integrity:['Integridad del archivo','Archive integrity', "Integridade do arquivo"],editable_document:['Documento editable','Editable document', "Documento editável"],images_verified:['Imágenes verificadas','Verified images', "Imagens verificadas"],standalone:['Autónomo','Standalone', "Independente"],read_only:['Solo lectura','Read only', "Somente leitura"],internal_references_checked:['Enlaces internos comprobados','Internal links checked', "Links internos verificados"],content_units_checked:['Unidades de contenido comprobadas','Content units checked', "Unidades de conteúdo verificadas"],structure_units_checked:['Bloques estructurales comprobados','Structural blocks checked', "Blocos estruturais verificados"],attachment:['Anexo incluido','Included attachment', "Anexo incluído"],paragraphs_checked:['Párrafos comprobados','Paragraphs checked', "Parágrafos verificados"],literal_code_blocks_checked:['Bloques de código comparados literalmente','Code blocks compared literally', "Blocos de código comparados literalmente"],finding_association_checked:['Asociación con el hallazgo comprobada','Finding association checked', "Associação com o achado verificada"],contract_version:['Versión del contrato','Contract version', "Versão do contrato"],manual_review_required:['Revisión manual requerida','Manual review required', "Revisão manual necessária"],format_specific_omissions:['Leyendas de gráfico omitidas en Markdown','Chart captions omitted in Markdown', "Legendas de gráficos omitidas no Markdown"],pdf_page_break_paragraphs:['Párrafos PDF comprobados en páginas contiguas','PDF paragraphs checked across adjacent pages', "Parágrafos do PDF verificados entre páginas adjacentes"]};
      for(const [key,value] of Object.entries(file.checks||{})){if(['verification_scope','limitations'].includes(key))continue;section.append(h('p',{},(labels[key]?w(...labels[key]):key)+': '+(typeof value==='boolean'?(value?w('Sí','Yes', "Sim"):w('No','No', "Não")):String(value))));}
      const scope=file.checks?.verification_scope;if(scope)section.append(h('p',{class:'wf-hint'},scope==='text_presence_only'?w('PDF: presencia de texto. No comprueba literalmente espacios ni la asociación de los bloques.','PDF: text presence. Literal whitespace and block association are not verified.', "PDF: presença de texto. Espaços em branco literais e associação entre blocos não são verificados."):w('Contenido por hallazgo y código literal. La presentación visual requiere revisión.','Content by finding and literal code. Visual presentation requires review.', "Conteúdo por achado e código literal. A apresentação visual requer revisão.")));
      for(const limit of file.checks?.limitations||[])section.append(h('p',{class:'wf-hint'},limit));
      body.append(section);
    }
    body.append(h('h3',{},w('Avisos de esta revisión','Warnings for this revision', "Avisos desta revisão")));
    if(!data.warnings?.length)body.append(h('p',{},w('Sin avisos registrados.','No recorded warnings.', "Nenhum aviso registrado.")));
    for(const issue of data.warnings||[])body.append(h('p',{},issue.message));
    body.append(button(w('Descargar registro JSON','Download JSON record', "Baixar registro JSON"),()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));h('a',{href:url,download:'verificacion-'+job.id.slice(0,8)+'.json'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);}));
  }
  let jobData=[],jobTimer=null,lastJobAnnouncement='',drawerBody=null;
  let jobSuspended=false,jobController=null,jobGeneration=0;
  function closeJobs(restore=true){if(!jobsDialog)return;const target=jobsDialog._opener;jobsDialog.remove();jobsDialog=null;drawerBody=null;paintJobs();if(restore)(target?.isConnected&&!target.disabled?target:$('#exportIndicator'))?.focus();}
  function jobSummary(){const active=jobData.filter(j=>!['done','cancelled','error'].includes(j.stage)),ready=jobData.filter(j=>j.stage==='done');return active.length?active.length+' '+w('exportando','exporting', "exportando"):ready.length?ready.length+' '+(ready.length===1?w('descarga','download', "download"):w('descargas','downloads', "downloads")):w('Exportaciones','Exports', "Exportações");}
  function paintJobs(){
    const indicator=$('#exportIndicator');if(indicator){indicator.textContent=jobSummary();indicator.setAttribute('aria-expanded',String(!!jobsDialog));if(jobsDialog?.isConnected)indicator.setAttribute('aria-controls','exportDrawer');else indicator.removeAttribute('aria-controls');}
    const summary=jobData.map(j=>j.label+': '+w(...(stages[j.stage]||[j.stage,j.stage,j.stage]))).join('. ');
    if(summary!==lastJobAnnouncement){lastJobAnnouncement=summary;const live=$('#exportAnnouncement');if(live)live.textContent=summary;}
    if(!drawerBody)return;
    const list=drawerBody.querySelector('.job-list'),status=drawerBody.querySelector('[data-job-notice]');status.textContent=jobData.length?'':w('No hay exportaciones en esta sesión.','No exports in this session.', "Nenhuma exportação nesta sessão.");
    const present=new Set(jobData.map(j=>j.id));list.querySelectorAll('[data-job]').forEach(row=>{if(!present.has(row.dataset.job))row.remove();});
    for(const job of jobData){let row=list.querySelector('[data-job="'+job.id+'"]');const key=JSON.stringify([job.stage,job.error,job.position,job.verification_available,job.formats,job.diagnostics,S.uiLang]);if(row?.dataset.key===key)continue;
      if(!row){row=h('section',{class:'card job-card','data-job':job.id});list.append(row);}
      const focused=row.contains(document.activeElement);row.dataset.key=key;row.dataset.stage=job.stage;
      row.replaceChildren(h('h3',{},job.label),h('p',{},w(...(stages[job.stage]||[job.stage,job.stage,job.stage]))+(job.stage==='queued'?' / '+job.position:'')),h('small',{},w('Revisión: ','Revision: ', "Revisão: ")+job.revision.slice(0,12)));
      if(job.error)row.append(h('p',{},job.error));
      const locations=diagnosticLocations(job.diagnostics);if(locations)row.append(locations);
      if(job.stage==='done'&&((job.formats||[]).includes('docx')||/\.docx$/i.test(job.filename||''))&&typeof DocxPreviewUI!=='undefined')row.append(button(w('Vista DOCX con LibreOffice','DOCX preview with LibreOffice','Visualização DOCX com LibreOffice'),()=>DocxPreviewUI.open(job)));
      if(job.stage==='done'){row.append(button(w('Descargar','Download', "Baixar"),()=>download(job),true));if(job.verification_available)row.append(button(w('Ver comprobaciones','View checks', "Ver verificações"),()=>verification(job)));}
      if(['done','error','cancelled'].includes(job.stage))row.append(button(w('Eliminar resultado','Remove result', "Remover resultado"),async()=>{await json('/api/jobs/'+job.id,{method:'DELETE'});await pollJobs();}));
      else if(job.stage!=='cancelling')row.append(button(w('Cancelar tarea','Cancel job', "Cancelar tarefa"),async()=>{await json('/api/jobs/'+job.id+'/cancel',options({}));await pollJobs();}));
      if(focused){const target=row.querySelector('button')||jobsDialog.querySelector('button');target?.focus();}
    }
  }
  async function pollJobs(){
    clearTimeout(jobTimer);
    if(jobSuspended)return;
    const generation=++jobGeneration;
    jobController?.abort();
    const controller=new AbortController();jobController=controller;
    try{
      const {data}=await json('/api/jobs',{signal:controller.signal});
      if(jobSuspended||generation!==jobGeneration)return;
      jobData=data;paintJobs();
    }catch(e){
      if(controller.signal.aborted||jobSuspended||generation!==jobGeneration)return;
      const n=drawerBody?.querySelector('[data-job-notice]');if(n)n.textContent=e.message;
    }finally{
      if(generation===jobGeneration){
        jobController=null;
        if(!jobSuspended)jobTimer=setTimeout(pollJobs,jobData.some(j=>!['done','error','cancelled'].includes(j.stage))?800:4000);
      }
    }
  }
  function suspendJobs(){
    jobSuspended=true;++jobGeneration;clearTimeout(jobTimer);
    jobController?.abort();jobController=null;
  }
  function resumeJobs(){if(jobSuspended){jobSuspended=false;pollJobs();}}
  function jobs(){
    if(jobsDialog?.isConnected){jobsDialog.querySelector('button')?.focus();return;}
    const active=document.activeElement===document.body?opener:document.activeElement;
    const previous=active?.closest('details:not([open])')?.querySelector('summary')||active;
    const d=h('section',{class:'export-drawer',id:'exportDrawer',role:'region','aria-label':w('Exportaciones','Exports', "Exportações")}),body=h('div',{class:'experience-body'});jobsDialog=d;drawerBody=body;d._opener=previous;
    d.append(h('div',{class:'experience-heading'},h('h2',{},w('Exportaciones','Exports', "Exportações")),button(w('Cerrar','Close', "Fechar"),()=>closeJobs())),body);
    body.append(h('p',{},w('Cada tarea usa su revisión guardada. Los resultados duran una hora mientras la aplicación está abierta.','Each job uses its saved revision. Results last one hour while the application is open.', "Cada tarefa usa sua revisão salva. Os resultados duram uma hora enquanto a aplicação está aberta.")),h('p',{'data-job-notice':'',role:'status'}),h('div',{class:'job-list'}));document.body.append(d);d.querySelector('button').focus();paintJobs();pollJobs();
  }
  async function intake(recovered=null){
    if(recovered?.format!=='report-gen-pending')recovered=null;
    const checkRecovery=recovered?PendingUI.recoveryGuard(recovered):()=>{};
    if(!S.slug||!await doSave())return;checkRecovery();
    const slug=S.slug,initial=recovered?{data:recovered.data,file:recovered.file}:PendingUI.retained('progress:intake');
    if(recovered&&(recovered.slug!==slug||recovered.workspace_id!==BrowserWorkspace.current()))throw Error(w('Abre el proyecto original.','Open the original project.','Abra o projeto original.'));
    let etag=projectStore.etag,raw='',bytesBase64='',format=initial?.data.format||'csv',mapping=initial?.data.mapping||null,current=null,generation=0,step=1,sourceFile=initial?.file||null,pending=null,selectionToKeep=initial?new Set(initial.data.selected):null;
    const {d,body}=dialog(w('Importar resultados','Import results', "Importar resultados"));
    const steps=h('ol',{class:'import-steps','aria-label':w('Pasos de importación','Import steps', "Etapas da importação")},...[[1,'Archivo','File','Arquivo'],[2,'Campos','Fields','Campos'],[3,'Revisión','Review','Revisão']].map(([n,es,en,pt])=>h('li',{'data-import-step':n},n+'. '+w(es,en,pt))));
    const type=h('select',{'aria-label':w('Formato','Format', "Formato")},h('option',{value:'csv'},'CSV'),h('option',{value:'burp'},'Burp XML'),h('option',{value:'nuclei'},'Nuclei JSONL'),h('option',{value:'nmap'},'Nmap XML'),h('option',{value:'sarif'},'SARIF 2.1.0'));
    const file=h('input',{type:'file',accept:'.csv,.xml,.jsonl,.json,.sarif,text/csv,application/xml,application/json,application/sarif+json,application/x-ndjson','aria-label':w('Archivo UTF-8','UTF-8 file', "Arquivo UTF-8")});
    type.value=format;
    const mapBox=h('div',{class:'intake-mapping'}),rows=h('div',{class:'intake-rows'}),notice=h('p',{role:'status'}),failureDetails=h('div',{'aria-live':'polite'}),chosen=new Set();
    const one=h('section',{'data-import-panel':'1'},h('p',{},w('Máximo 4 MiB y 500 filas o hosts. Selecciona un archivo UTF-8. Nmap importa activos y servicios; Nuclei y SARIF importan resultados pendientes de revisión.','Maximum 4 MiB and 500 rows or hosts. Select a UTF-8 file. Nmap imports assets and services; Nuclei and SARIF import findings awaiting review.', "Máximo de 4 MiB e 500 linhas ou hosts. Selecione um arquivo UTF-8. Nmap importa ativos e serviços; Nuclei e SARIF importam achados que aguardam revisão.")),h('label',{},w('Formato','Format', "Formato"),type),h('label',{},w('Archivo','File', "Arquivo"),file));
    const two=h('section',{'data-import-panel':'2'},h('p',{},w('Comprueba las correspondencias propuestas y sus ejemplos. Los campos opcionales están agrupados.','Check the suggested mappings and their examples. Optional fields are grouped.', "Verifique os mapeamentos sugeridos e seus exemplos. Os campos opcionais estão agrupados.")),mapBox);
    const three=h('section',{'data-import-panel':'3'},h('p',{},w('Revisa el contenido y la selección. Los duplicados se omiten. Los resultados entran sin verificar; revisa también posibles secretos en mensajes HTTP.','Review content and selection. Duplicates are skipped. Findings arrive unverified; check HTTP messages for possible secrets.', "Revise o conteúdo e a seleção. Duplicatas são ignoradas. Os achados chegam como não verificados; confira possíveis segredos nas mensagens HTTP.")),rows);
    const back=button(w('Anterior','Back', "Voltar"),()=>show(step-1));
    const next=button(w('Continuar','Continue', "Continuar"),async()=>{if(!raw)throw Error(w('Selecciona un archivo.','Select a file.', "Selecione um arquivo."));if(step===1){if(!current)await preview(true);if(current)show(2);}else if(await preview(false))show(3);});
    const apply=button(w('Importar selección como pendiente','Import selection for review', "Importar seleção para revisão"),async()=>{
      if(!current||!chosen.size)throw Error(w('Selecciona filas válidas.','Select valid rows.', "Selecione linhas válidas."));
      if(S.slug!==slug||projectStore.dirty||projectStore.etag!==etag)throw Error(w('El proyecto cambió; vuelve a abrir la importación.','The project changed; reopen the import.', "O projeto mudou; reabra a importação."));
      const pendingRevision=pending.handle.revision;pending.setBusy(true);busyProject(true);try{const result=await json('/api/projects/'+encodeURIComponent(slug)+'/intake/apply',options({format,text:raw,bytes_base64:bytesBase64,mapping,selected:[...chosen]},etag));await adoptSavedProject(result.data.data,result.etag);if((await pending.committed(pendingRevision)).finished)d.close();renderSidebar();renderMain();toast(result.data.imported+' '+(result.data.import_kind==='inventory'?w('observaciones de inventario pendientes de revisión','inventory observations awaiting review', "observações do inventário aguardando revisão"):w('hallazgos pendientes de revisión','findings awaiting review', "achados aguardando revisão")),'ok');}catch(e){notice.textContent=e.message;const locations=diagnosticLocations(e.diagnostics);failureDetails.replaceChildren(...(locations?[locations]:[]));throw e;}finally{pending.setBusy(false);busyProject(false);}
    },true);
    function show(n){step=Math.max(1,Math.min(3,n));three.querySelector('p').textContent=format==='nmap'?w('Revisa el alcance y los servicios observados. La selección se incorpora como inventario y cobertura pendiente. Un puerto abierto no confirma una vulnerabilidad.','Review scope and observed services. The selection is added as inventory and pending coverage. An open port does not confirm a vulnerability.', "Revise o escopo e os serviços observados. A seleção é adicionada como inventário e cobertura pendente. Uma porta aberta não confirma uma vulnerabilidade."):w('Revisa el contenido y la selección. Los duplicados se omiten. Los resultados entran sin verificar; revisa también posibles secretos en mensajes HTTP.','Review content and selection. Duplicates are skipped. Findings arrive unverified; check HTTP messages for possible secrets.', "Revise o conteúdo e a seleção. Duplicatas são ignoradas. Os achados chegam como não verificados; confira possíveis segredos nas mensagens HTTP.");one.hidden=step!==1;two.hidden=step!==2;three.hidden=step!==3;back.hidden=step===1;next.hidden=step===3;next.textContent=step===2?w('Revisar selección','Review selection', "Revisar seleção"):w('Continuar','Continue', "Continuar");apply.hidden=step!==3;apply.disabled=!current||!chosen.size;steps.querySelectorAll('li').forEach(li=>{if(Number(li.dataset.importStep)===step)li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');});notice.textContent=step===3&&current?current.rows.length+' '+w('filas; ','rows; ', "linhas; ")+chosen.size+' '+w('seleccionadas; ','selected; ', "selecionadas; ")+(current.counts?.duplicates||0)+' '+w('coincidencias','matches', "resultados")+(format==='nmap'?'; '+current.counts.services+' '+w('servicios observados','observed services', "serviços observados"):'')+(format==='sarif'?'; '+(current.counts?.excluded||0)+' '+w('excluidas','excluded','excluídas')+'. '+(current.notice||''):''):'';}
    async function preview(rebuild){
      if(S.slug!==slug||projectStore.dirty||projectStore.etag!==etag)throw Error(w('El proyecto cambió; vuelve a abrir la importación.','The project changed; reopen the import.','O projeto mudou; reabra a importação.'));
      const previousSelection=current?new Set(chosen):selectionToKeep;selectionToKeep=null;
      const run=++generation;current=null;apply.disabled=true;chosen.clear();rows.replaceChildren();failureDetails.replaceChildren();notice.textContent=w('Analizando…','Reading…', "Lendo…");
      try{if(!raw)return false;const result=await json('/api/projects/'+encodeURIComponent(slug)+'/intake/preview',options({format,text:raw,bytes_base64:bytesBase64,...(mapping?{mapping}:{})},etag));if(!d.isConnected||run!==generation||S.slug!==slug)return false;current=result.data;etag=result.etag;mapping=current.mapping;
        if(rebuild){mapBox.replaceChildren();if(format==='csv'){
          const advanced=h('details',{class:'mapping-advanced'},h('summary',{},w('Campos opcionales','Optional fields', "Campos opcionais"))),optional=h('div',{class:'intake-mapping'});advanced.append(optional);
          Object.entries(fields).forEach(([key,label])=>{const input=h('select',{'data-map':key},h('option',{value:''},w('No importar','Do not import', "Não importar")),...current.headers.map(head=>h('option',{value:head},head)));input.value=mapping[key]||'';
            const example=h('small',{class:'mapping-example'},w('Ejemplo: ','Example: ', "Exemplo: ")+String(current.rows[0]?.finding[key]||'—').slice(0,160));
            input.addEventListener('change',()=>{generation++;mapping[key]=input.value;current=null;selectionToKeep=null;chosen.clear();apply.disabled=true;rows.replaceChildren();example.textContent=w('Se comprobará al continuar.','Will be checked when you continue.', "Será verificado ao continuar.");});
            (['title','severity','affected','description_md'].includes(key)?mapBox:optional).append(h('label',{},w(...label),input,example));});mapBox.append(advanced);
        }else mapBox.append(h('p',{},format==='sarif'?w('SARIF 2.1.0: conserva la regla, la herramienta, las ubicaciones y el nivel original. El nivel del analizador no acredita severidad: los resultados entran como informativos y sin verificar. Las exclusiones se explican antes de importar.','SARIF 2.1.0: preserves the rule, tool, locations and original level. Analyzer levels do not establish severity: results arrive informational and unverified. Exclusions are explained before import.','SARIF 2.1.0: preserva a regra, a ferramenta, as localizações e o nível original. O nível do analisador não comprova a severidade: os resultados entram como informativos e não verificados. As exclusões são explicadas antes da importação.'):format==='nmap'?w('Nmap: una fila por host, con puertos, estados y versiones observadas. Se reutilizan los activos con la misma IP; cada observación queda en Cobertura como pendiente. No crea vulnerabilidades ni importa scripts NSE.','Nmap: one row per host, with observed ports, states and versions. Assets with the same IP are reused; each observation is added to Coverage as pending. Creates no vulnerabilities and does not import NSE scripts.', "Nmap: uma linha por host, com portas, estados e versões observados. Ativos com o mesmo IP são reutilizados; cada observação é adicionada à Cobertura como pendente. Não cria vulnerabilidades nem importa scripts NSE."):w('Campos reconocidos automáticamente. Revisa cada resultado; una coincidencia del escáner no confirma una vulnerabilidad.','Fields recognized automatically. Review each result; a scanner match does not confirm a vulnerability.', "Campos reconhecidos automaticamente. Revise cada resultado; uma correspondência do scanner não confirma uma vulnerabilidade.")));}
        for(const row of current.rows){if(row.kind==='inventory'){renderInventory(row);continue;}const f=row.finding,blocked=row.existing_duplicate||row.errors.length>0;const checkbox=h('input',{type:'checkbox',checked:(blocked||row.duplicate)?null:'',disabled:blocked?'':null,'data-intake-row':row.index});if(!blocked&&!row.duplicate)chosen.add(row.index);checkbox.addEventListener('change',()=>{if(checkbox.checked)chosen.add(row.index);else chosen.delete(row.index);show(step);pending?.changed();});
          rows.append(h('article',{class:'card'},h('label',{class:'wf-check'},checkbox,f.title||w('Sin título','Untitled', "Sem título")),h('p',{},(f.severity||'?')+' / '+f.affected),row.duplicate?h('p',{},w('Coincidencia: selecciona solo una fila válida.','Match: choose only one valid row.', "Correspondência: escolha somente uma linha válida.")):null,...row.errors.map(error=>h('p',{class:'wf-error'},error)),diagnosticLocations(row.diagnostics,row.source_location),h('details',{},h('summary',{},w('Revisar contenido','Review content', "Revisar conteúdo")),...['description_md','impact_md','remediation_md','cvss_vector','cwe','references'].map(key=>h('section',{},h('h4',{},w(...fields[key])),h('pre',{},Array.isArray(f[key])?f[key].join('\n'):f[key]||'—'))),...(f.walkthrough||[]).map(s=>h('section',{},h('h4',{},s.lead),h('pre',{},s.command))),h('p',{},'ID: '+f.import_source.external_id+' / '+w('Confianza de origen: ','Source confidence: ', "Confiança da origem: ")+f.import_source.confidence),h('p',{class:'hash'},'SHA-256: '+f.import_source.file_sha256),sarifOrigin(f.import_source))));}
        if(previousSelection){chosen.clear();for(const input of rows.querySelectorAll('[data-intake-row]')){input.checked=!input.disabled&&previousSelection.has(Number(input.dataset.intakeRow));if(input.checked)chosen.add(Number(input.dataset.intakeRow));}}
        notice.textContent='';apply.disabled=!chosen.size;pending?.changed();return true;
      }catch(e){if(run===generation&&d.isConnected){notice.textContent=e.message;const locations=diagnosticLocations(e.diagnostics);failureDetails.replaceChildren(...(locations?[locations]:[]));current=null;apply.disabled=true;}return false;}
    }
    function renderInventory(row){
      const item=row.inventory,source=item.import_source,blocked=row.existing_duplicate||row.errors.length>0;
      const checkbox=h('input',{type:'checkbox',checked:(blocked||row.duplicate)?null:'',disabled:blocked?'':null,'data-intake-row':row.index});
      if(!blocked&&!row.duplicate)chosen.add(row.index);
      checkbox.addEventListener('change',()=>{if(checkbox.checked)chosen.add(row.index);else chosen.delete(row.index);show(step);pending?.changed();});
      const contents=h('details',{},h('summary',{},w('Revisar servicios y origen','Review services and provenance', "Revisar serviços e proveniência")),
        h('p',{},w('Estado del host: ','Host state: ', "Estado do host: ")+item.state),h('p',{},item.hostnames.join(', ')||w('Sin nombre de host','No hostname', "Sem nome de host")),
        h('pre',{},item.services.map(s=>s.port+'/'+s.protocol+' · '+s.state+' · '+[s.tunnel,s.name,s.product,s.version,s.extrainfo].filter(Boolean).join(' ')).join('\n')||w('Sin puertos individuales en el archivo','No individual ports in this file', "Nenhuma porta individual neste arquivo")),
        ...item.extraports.map(p=>h('p',{},'Extraports: '+p.state+' ('+p.count+')')),
        h('p',{},'Nmap '+source.scanner_version+' / '+source.observed_at),h('p',{class:'hash'},'SHA-256: '+source.file_sha256));
      if(!item.scan_complete)contents.append(h('p',{class:'wf-hint'},w('El archivo no acredita que el escaneo terminara correctamente. La cobertura puede ser parcial.','The file does not record successful scan completion. Coverage may be partial.', "O arquivo não registra a conclusão bem-sucedida da varredura. A cobertura pode ser parcial.")));
      if(source.omitted_scripts)contents.append(h('p',{},source.omitted_scripts+' '+w('scripts NSE omitidos','NSE scripts omitted', "Scripts NSE omitidos")));
      rows.append(h('article',{class:'card'},h('label',{class:'wf-check'},checkbox,item.target),
        h('p',{},item.services.length+' '+w('servicios; ','services; ', "serviços; ")+(row.existing_asset?w('activo existente','existing asset', "ativo existente"):w('activo nuevo','new asset', "novo ativo"))),diagnosticLocations(row.diagnostics,row.source_location),
        row.duplicate?h('p',{},w('Observación ya importada o repetida en el archivo. Selecciona solo una.','Observation already imported or repeated in this file. Select only one.', "Observação já importada ou repetida neste arquivo. Selecione somente uma.")):null,contents));
    }
    type.addEventListener('change',()=>{generation++;format=type.value;mapping=null;current=null;selectionToKeep=null;chosen.clear();rows.replaceChildren();mapBox.replaceChildren();failureDetails.replaceChildren();show(1);});
    async function readSource(selected){if(!selected||selected.size>4*1024*1024)throw Error(w('Selecciona un archivo de hasta 4 MiB.','Select a file up to 4 MiB.','Selecione um arquivo de até 4 MiB.'));const bytes=await selected.arrayBuffer();return {text:new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes),base64:btoa(Array.from(new Uint8Array(bytes),x=>String.fromCharCode(x)).join(''))};}
    file.addEventListener('change',async()=>{const read=++generation;raw='';bytesBase64='';sourceFile=null;mapping=null;current=null;selectionToKeep=null;chosen.clear();rows.replaceChildren();mapBox.replaceChildren();failureDetails.replaceChildren();show(1);const selected=file.files[0];if(!selected)return;try{const decoded=await readSource(selected);if(read!==generation||!d.isConnected||S.slug!==slug)return;raw=decoded.text;bytesBase64=decoded.base64;sourceFile=selected;pending.changed();if(await preview(true))show(2);}catch(e){if(read===generation)notice.textContent=e.message;}});
    body.append(steps,one,two,three,notice,failureDetails,h('div',{class:'import-navigation'},back,next,apply));show(1);d.dataset.intakeDialog='';
    pending=PendingUI.attach('progress:intake',w('Importación pendiente','Pending import','Importação pendente'),()=>({data:{schema:1,format,mapping,selected:selectionToKeep?[...selectionToKeep]:[...chosen],filename:sourceFile?.name||''},file:sourceFile}),{container:body,origin:recovered,onDiscard:()=>{generation++;d.close();}});
    if(sourceFile){const run=++generation;try{const decoded=await readSource(sourceFile);if(run!==generation||!d.isConnected||S.slug!==slug)return;raw=decoded.text;bytesBase64=decoded.base64;notice.textContent=w('Archivo recuperado: ','Recovered file: ','Arquivo recuperado: ')+sourceFile.name+'. '+w('Continúa para analizarlo de nuevo y revisar la selección. No se ha importado nada.','Continue to analyze it again and review the selection. Nothing has been imported.','Continue para analisá-lo novamente e revisar a seleção. Nada foi importado.');}catch(e){notice.textContent=e.message;}}

  }
  function importReview(box,f){
    if(!f.import_source)return;
    const source=f.import_source;
    box.append(h('div',{class:'import-origin','data-field':'import_source'},h('h4',{},w('Origen de importación','Import provenance', "Proveniência da importação")),
      h('p',{},source.format+' / ID '+source.external_id),h('p',{class:'hash'},(source.hash_scope==='original_bytes'?w('SHA-256 del archivo: ','File SHA-256: ', "SHA-256 do arquivo: "):source.hash_scope==='received_utf8_text'?w('SHA-256 del texto recibido: ','Received text SHA-256: ', "SHA-256 do texto recebido: "):w('SHA-256 del texto normalizado (legado): ','Normalized text SHA-256 (legacy): ', "SHA-256 do texto normalizado (legado): "))+source.file_sha256),
      sarifOrigin(source),
      h('label',{class:'wf-check'},h('input',{type:'checkbox',checked:source.reviewed?'':null,onchange:e=>{source.reviewed=e.target.checked;scheduleSave();}}),
        w('He revisado el contenido importado. Esto no confirma técnicamente el hallazgo.','I reviewed the imported content. This does not technically confirm the finding.', "Revisei o conteúdo importado. Isso não confirma tecnicamente o achado."))));
  }
  function sarifOrigin(source){
    if(source?.format!=='sarif')return null;
    const original={tool:source.tool,tool_component:source.tool_component,tool_component_kind:source.tool_component_kind,tool_component_index:source.tool_component_index,tool_component_identity:source.tool_component_identity,rule_id:source.rule_id,rule_name:source.rule_name,level:source.level,result_kind:source.result_kind,baseline_state:source.baseline_state,message:source.message,locations:source.locations,fingerprints:source.fingerprints,partialFingerprints:source.partialFingerprints,suppressions:source.suppressions,omitted_fields:source.omitted_fields};
    return h('details',{class:'import-origin sarif-origin'},h('summary',{},w('Origen SARIF conservado','Preserved SARIF provenance','Origem SARIF preservada')),
      h('p',{},w('Herramienta: ','Tool: ','Ferramenta: ')+(source.tool?.name||'—')+' / '+(source.tool?.semanticVersion||source.tool?.version||'—')),
      source.tool_component_kind==='extension'?h('p',{'data-sarif-extension':''},w('Extensión de reglas: ','Rule extension: ','Extensão de regras: ')+(source.tool_component?.name||'—')+' / '+(source.tool_component?.semanticVersion||source.tool_component?.version||'—')):null,
      h('p',{},w('Regla: ','Rule: ','Regra: ')+(source.rule_id||'—')),
      h('p',{},w('Nivel original del analizador: ','Original analyzer level: ','Nível original do analisador: ')+(source.level||'—')),
      h('p',{class:'wf-hint'},w('Este nivel no confirma la severidad ni la existencia de una vulnerabilidad. Las rutas y las URL se muestran como texto; no se consultan.','This level does not confirm severity or the existence of a vulnerability. Paths and URLs are shown as text; they are not requested.','Este nível não confirma a severidade nem a existência de uma vulnerabilidade. Caminhos e URLs são exibidos como texto; não são acessados.')),
      h('pre',{},JSON.stringify(original,null,2)));
  }
  function inventoryReview(item){
    if(item.import_source?.format!=='nmap')return null;
    const source=item.import_source;
    return h('details',{class:'import-origin'},h('summary',{},w('Observación Nmap original','Original Nmap observation', "Observação original do Nmap")),
      h('p',{},w('Origen conservado. Editar las notas o marcar la prueba como realizada no modifica esta observación.','Preserved source. Editing notes or marking the test performed does not change this observation.', "Origem preservada. Editar notas ou marcar o teste como realizado não altera esta observação.")),
      h('p',{},source.external_id+' / Nmap '+source.scanner_version+' / '+source.observed_at),
      h('p',{class:'hash'},'SHA-256: '+source.file_sha256),
      h('pre',{},(item.services||[]).map(s=>s.port+'/'+s.protocol+' · '+s.state+' · '+[s.tunnel,s.name,s.product,s.version,s.extrainfo].filter(Boolean).join(' ')).join('\n')||w('Sin puertos individuales','No individual ports', "Nenhuma porta individual")));
  }
  function compare(box,slug,from,to){
    const path='/api/projects/'+encodeURIComponent(slug)+'/history/'+encodeURIComponent(from)+'/visual?lang='+S.uiLang+(to?'&to='+encodeURIComponent(to):'');
    box.replaceChildren(h('h3',{},w('Comparación visual','Visual comparison', "Comparação visual")),
      h('p',{},w('El HTML descargado incluye las imágenes y se puede abrir sin conexión o imprimir a PDF desde el navegador.','The downloaded HTML includes images and can be opened offline or printed to PDF in your browser.', "O HTML baixado inclui imagens e pode ser aberto sem conexão ou impresso em PDF pelo navegador.")),
      h('a',{class:'btn',href:path+'&download=1',download:'comparison.html'},w('Descargar comparación HTML','Download comparison HTML', "Baixar HTML da comparação")),
      h('iframe',{class:'comparison-frame',src:path,sandbox:'',title:w('Texto y evidencias antes y después','Text and evidence before and after', "Texto e evidências antes e depois")}));
    box.append(button(w('Ver comparación interna privada','View private internal comparison', "Ver comparação interna privada"),()=>{if(!confirm(w('Incluye capturas y borradores privados. ¿Abrir para revisión interna?','Includes private captures and drafts. Open for internal review?', "Inclui capturas privadas e rascunhos. Abrir para revisão interna?")))return;const frame=box.querySelector('iframe');frame.src=path+'&internal=1';box.append(button(w('Descargar comparación interna','Download internal comparison', "Baixar comparação interna"),()=>{if(confirm(w('Este archivo contiene datos privados. ¿Descargar?','This file contains private data. Download?', "Este arquivo contém dados privados. Baixar?")))h('a',{href:path+'&internal=1&download=1&ack_private=1',download:'comparison-private.html'}).click();}));}));
    box.scrollIntoView?.({block:'start'});
  }
  function update(){drawSave();paintJobs();const b=$('#jobsBtn');if(b)b.textContent=w('Exportaciones','Exports', "Exportações");const i=$('#intakeBtn');if(i){i.textContent=w('Importar resultados','Import results', "Importar resultados");i.disabled=!S.slug||projectBusyCount>0;}}
  function bind(){
    const b=button(w('Exportaciones','Exports', "Exportações"),jobs);b.id='jobsBtn';$('#exportMenu .action-menu-body').append(b);
    const i=button(w('Importar resultados','Import results', "Importar resultados"),intake);i.id='intakeBtn';$('#projectActionsList').append(i);
    const indicator=button('',jobs);indicator.id='exportIndicator';$('.workspace-toolbar').append(indicator);document.body.append(h('span',{id:'exportAnnouncement',class:'export-announcement',role:'status','aria-live':'polite'}));
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&jobsDialog){e.preventDefault();closeJobs();}});
    document.addEventListener('focusin',e=>{if(jobsDialog&&!jobsDialog.contains(e.target)&&e.target!==indicator)closeJobs(false);});
    // A queued callback may arrive while WebKit unloads the document. Stop only
    // this tab's GET polling; server export jobs continue independently.
    window.addEventListener('pagehide',suspendJobs);
    window.addEventListener('pageshow',resumeJobs);
    pollJobs();update();
  }
  PendingUI.register('progress:intake',{
    validate(row){const data=row.data;if(row.key!=='progress:intake'||!data||data.schema!==1||!['csv','burp','nuclei','nmap','sarif'].includes(data.format)||!Array.isArray(data.selected)||data.selected.some(n=>!Number.isInteger(n)||n<0)||data.selected.length>500||(data.mapping!==null&&(typeof data.mapping!=='object'||Array.isArray(data.mapping)||Object.values(data.mapping).some(value=>typeof value!=='string')))||row.file&&row.file.size>4*1024*1024)throw Error(w('Importación pendiente no compatible.','Unsupported pending import.','Importação pendente não compatível.'));},
    restore:intake
  });
  return {bind,update,saveState,enqueue,jobs,intake,compare,importReview,inventoryReview};
})();
