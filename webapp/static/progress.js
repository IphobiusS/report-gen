/* Durable save feedback, immutable export jobs and reviewed scanner intake. */
const ProgressUI = (() => {
  'use strict';
  const w=(es,en)=>S.uiLang==='en'?en:es;
  const stages={rendering_html:['Generando HTML','Rendering HTML'],checking_html:['Comprobando HTML','Checking HTML'],queued:['En cola','Queued'],validating:['Validando copia guardada','Validating saved snapshot'],
    rendering_pdf:['Generando PDF','Rendering PDF'],checking_pdf:['Comprobando PDF','Checking PDF'],
    rendering_docx:['Generando Word','Rendering Word'],checking_docx:['Comprobando Word','Checking Word'],
    rendering_md:['Generando Markdown','Rendering Markdown'],checking_md:['Comprobando Markdown','Checking Markdown'],
    packaging:['Preparando ZIP','Packaging ZIP'],done:['Lista para descargar','Ready to download'],
    cancelling:['Cancelando y limpiando archivos','Cancelling and cleaning files'],cancelled:['Cancelada','Cancelled'],error:['Error de exportación','Export failed']};
  const fields={title:['Título','Title'],severity:['Severidad','Severity'],affected:['Objetivo','Target'],
    description_md:['Descripción','Description'],impact_md:['Impacto','Impact'],remediation_md:['Remediación','Remediation'],
    cvss_vector:['Vector CVSS','CVSS vector'],cwe:['CWE','CWE'],references:['Referencias','References'],external_id:['ID de origen','Source ID']};
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
    d.append(h('div',{class:'experience-heading'},h('h2',{},title),button(w('Cerrar','Close'),()=>d.close())),body);
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
    const labels={ready:w('Guardado en disco','Saved on disk'),pending:w('Cambios pendientes','Unsaved changes'),
      saving:w('Guardando…','Saving…'),saved:w('Guardado','Saved'),loading:w('Abriendo proyecto…','Opening project…'),error:w('Sin guardar','Not saved')};
    el.dataset.state=saveError?'error':state;
    el.textContent=saveError?w('Error de guardado','Save failed'):(S.slug||projectStore.slug?labels[state]||labels.ready:w('Sin proyecto','No project'));
    if(projectStore.lastSavedAt)el.textContent+=' / '+projectStore.lastSavedAt.toLocaleTimeString(S.uiLang==='en'?'en-GB':'es-CL');
    el.title=projectStore.lastSavedAt?w('Último guardado correcto: ','Last successful save: ')+projectStore.lastSavedAt.toLocaleString():el.textContent;
    let banner=$('#saveError');
    if(!saveError){const focused=banner?.contains(document.activeElement);banner?.remove();if(focused)$('#editor')?.focus({preventScroll:true});return;}
    if(!banner){banner=h('div',{id:'saveError',class:'save-error',role:'alert'},h('span',{}),button('',async()=>{if(await doSave())$('#editor')?.focus({preventScroll:true});}));$('.topbar').after(banner);}
    banner.querySelector('span').textContent=w('Tus cambios siguen en esta pestaña. ','Your changes remain in this tab. ')+saveError.message;
    banner.querySelector('button').textContent=w('Reintentar guardado','Retry saving');
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
    const {body}=dialog(w('Comprobaciones de la exportación','Export checks'));
    body.append(h('p',{},w('Revisión guardada: ','Saved revision: ')+(data.source_revision||'—')),
      h('p',{},w('Estos controles verifican los archivos generados. No confirman los hallazgos ni reemplazan la revisión visual.','These checks verify generated files. They do not confirm findings or replace visual review.')));
    for(const [name,file] of Object.entries(data.files||{})){
      const section=h('section',{class:'card export-check-card'},h('h3',{},name),h('p',{},file.bytes+' bytes'),h('p',{class:'hash'},'SHA-256: '+file.sha256));
      const labels={authored_list_items_order_checked:['Elementos de lista originales comprobados en orden','Source list items checked in order'],authored_tables_checked:['Tablas originales comprobadas','Source tables checked'],pdf_wrapped_code_lines:['Líneas de código divididas en PDF','Code lines wrapped in PDF'],metadata_values_checked:['Metadatos comprobados','Metadata checked'],link_targets_checked:['Destinos comparados con el original','Link targets matched to source'],evidence_associations_checked:['Colocaciones de evidencia comprobadas','Evidence placements matched to source'],static_visibility_checked:['Visibilidad estática comprobada','Static visibility checked'],evidence_association_checked:['Asociación de imágenes comprobada','Image association checked'],pages:['Páginas','Pages'],image_placements:['Imágenes','Images'],expected_image_placements:['Imágenes previstas','Expected images'],toc_references_checked:['Referencias del índice comprobadas','TOC references checked'],archive_integrity:['Integridad del archivo','Archive integrity'],editable_document:['Documento editable','Editable document'],images_verified:['Imágenes verificadas','Verified images'],standalone:['Autónomo','Standalone'],read_only:['Solo lectura','Read only'],internal_references_checked:['Enlaces internos comprobados','Internal links checked'],content_units_checked:['Unidades de contenido comprobadas','Content units checked'],structure_units_checked:['Bloques estructurales comprobados','Structural blocks checked'],attachment:['Anexo incluido','Included attachment'],paragraphs_checked:['Párrafos comprobados','Paragraphs checked'],literal_code_blocks_checked:['Bloques de código comparados literalmente','Code blocks compared literally'],finding_association_checked:['Asociación con el hallazgo comprobada','Finding association checked'],contract_version:['Versión del contrato','Contract version'],manual_review_required:['Revisión manual requerida','Manual review required'],format_specific_omissions:['Leyendas de gráfico omitidas en Markdown','Chart captions omitted in Markdown'],pdf_page_break_paragraphs:['Párrafos PDF comprobados en páginas contiguas','PDF paragraphs checked across adjacent pages']};
      for(const [key,value] of Object.entries(file.checks||{})){if(['verification_scope','limitations'].includes(key))continue;section.append(h('p',{},(labels[key]?w(...labels[key]):key)+': '+(typeof value==='boolean'?(value?w('Sí','Yes'):w('No','No')):String(value))));}
      const scope=file.checks?.verification_scope;if(scope)section.append(h('p',{class:'wf-hint'},scope==='text_presence_only'?w('PDF: presencia de texto. No comprueba literalmente espacios ni la asociación de los bloques.','PDF: text presence. Literal whitespace and block association are not verified.'):w('Contenido por hallazgo y código literal. La presentación visual requiere revisión.','Content by finding and literal code. Visual presentation requires review.')));
      for(const limit of file.checks?.limitations||[])section.append(h('p',{class:'wf-hint'},limit));
      body.append(section);
    }
    body.append(h('h3',{},w('Avisos de esta revisión','Warnings for this revision')));
    if(!data.warnings?.length)body.append(h('p',{},w('Sin avisos registrados.','No recorded warnings.')));
    for(const issue of data.warnings||[])body.append(h('p',{},issue.message));
    body.append(button(w('Descargar registro JSON','Download JSON record'),()=>{const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));h('a',{href:url,download:'verificacion-'+job.id.slice(0,8)+'.json'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);}));
  }
  let jobData=[],jobTimer=null,lastJobAnnouncement='',drawerBody=null;
  function closeJobs(restore=true){if(!jobsDialog)return;const target=jobsDialog._opener;jobsDialog.remove();jobsDialog=null;drawerBody=null;paintJobs();if(restore)(target?.isConnected&&!target.disabled?target:$('#exportIndicator'))?.focus();}
  function jobSummary(){const active=jobData.filter(j=>!['done','cancelled','error'].includes(j.stage)),ready=jobData.filter(j=>j.stage==='done');return active.length?active.length+' '+w('exportando','exporting'):ready.length?ready.length+' '+(ready.length===1?w('descarga','download'):w('descargas','downloads')):w('Exportaciones','Exports');}
  function paintJobs(){
    const indicator=$('#exportIndicator');if(indicator){indicator.textContent=jobSummary();indicator.setAttribute('aria-expanded',String(!!jobsDialog));if(jobsDialog?.isConnected)indicator.setAttribute('aria-controls','exportDrawer');else indicator.removeAttribute('aria-controls');}
    const summary=jobData.map(j=>j.label+': '+w(...(stages[j.stage]||[j.stage,j.stage]))).join('. ');
    if(summary!==lastJobAnnouncement){lastJobAnnouncement=summary;const live=$('#exportAnnouncement');if(live)live.textContent=summary;}
    if(!drawerBody)return;
    const list=drawerBody.querySelector('.job-list'),status=drawerBody.querySelector('[data-job-notice]');status.textContent=jobData.length?'':w('No hay exportaciones en esta sesión.','No exports in this session.');
    const present=new Set(jobData.map(j=>j.id));list.querySelectorAll('[data-job]').forEach(row=>{if(!present.has(row.dataset.job))row.remove();});
    for(const job of jobData){let row=list.querySelector('[data-job="'+job.id+'"]');const key=JSON.stringify([job.stage,job.error,job.position,job.verification_available,S.uiLang]);if(row?.dataset.key===key)continue;
      if(!row){row=h('section',{class:'card job-card','data-job':job.id});list.append(row);}
      const focused=row.contains(document.activeElement);row.dataset.key=key;row.dataset.stage=job.stage;
      row.replaceChildren(h('h3',{},job.label),h('p',{},w(...(stages[job.stage]||[job.stage,job.stage]))+(job.stage==='queued'?' / '+job.position:'')),h('small',{},w('Revisión: ','Revision: ')+job.revision.slice(0,12)));
      if(job.error)row.append(h('p',{},job.error));
      if(job.stage==='done'){row.append(button(w('Descargar','Download'),()=>download(job),true));if(job.verification_available)row.append(button(w('Ver comprobaciones','View checks'),()=>verification(job)));}
      if(['done','error','cancelled'].includes(job.stage))row.append(button(w('Eliminar resultado','Remove result'),async()=>{await json('/api/jobs/'+job.id,{method:'DELETE'});await pollJobs();}));
      else if(job.stage!=='cancelling')row.append(button(w('Cancelar tarea','Cancel job'),async()=>{await json('/api/jobs/'+job.id+'/cancel',options({}));await pollJobs();}));
      if(focused){const target=row.querySelector('button')||jobsDialog.querySelector('button');target?.focus();}
    }
  }
  async function pollJobs(){clearTimeout(jobTimer);try{const {data}=await json('/api/jobs');jobData=data;paintJobs();}catch(e){const n=drawerBody?.querySelector('[data-job-notice]');if(n)n.textContent=e.message;}finally{jobTimer=setTimeout(pollJobs,jobData.some(j=>!['done','error','cancelled'].includes(j.stage))?800:4000);}}
  function jobs(){
    if(jobsDialog?.isConnected){jobsDialog.querySelector('button')?.focus();return;}
    const active=document.activeElement===document.body?opener:document.activeElement;
    const previous=active?.closest('details:not([open])')?.querySelector('summary')||active;
    const d=h('section',{class:'export-drawer',id:'exportDrawer',role:'region','aria-label':w('Exportaciones','Exports')}),body=h('div',{class:'experience-body'});jobsDialog=d;drawerBody=body;d._opener=previous;
    d.append(h('div',{class:'experience-heading'},h('h2',{},w('Exportaciones','Exports')),button(w('Cerrar','Close'),()=>closeJobs())),body);
    body.append(h('p',{},w('Cada tarea usa su revisión guardada. Los resultados duran una hora mientras la aplicación está abierta.','Each job uses its saved revision. Results last one hour while the application is open.')),h('p',{'data-job-notice':'',role:'status'}),h('div',{class:'job-list'}));document.body.append(d);d.querySelector('button').focus();paintJobs();pollJobs();
  }
  async function intake(){
    if(!S.slug||!await doSave())return;
    const slug=S.slug;let etag=projectStore.etag,raw='',bytesBase64='',format='csv',mapping=null,current=null,generation=0,step=1;
    const {d,body}=dialog(w('Importar resultados','Import results'));
    const steps=h('ol',{class:'import-steps','aria-label':w('Pasos de importación','Import steps')},...[[1,'Archivo','File'],[2,'Campos','Fields'],[3,'Revisión','Review']].map(([n,es,en])=>h('li',{'data-import-step':n},n+'. '+w(es,en))));
    const type=h('select',{'aria-label':w('Formato','Format')},h('option',{value:'csv'},'CSV'),h('option',{value:'burp'},'Burp XML'),h('option',{value:'nuclei'},'Nuclei JSONL'),h('option',{value:'nmap'},'Nmap XML'));
    const file=h('input',{type:'file',accept:'.csv,.xml,.jsonl,text/csv,application/xml,application/json,application/x-ndjson','aria-label':w('Archivo UTF-8','UTF-8 file')});
    const mapBox=h('div',{class:'intake-mapping'}),rows=h('div',{class:'intake-rows'}),notice=h('p',{role:'status'}),chosen=new Set();
    const one=h('section',{'data-import-panel':'1'},h('p',{},w('Máximo 4 MiB y 500 filas o hosts. Selecciona un archivo UTF-8. Nmap importa activos y servicios; Nuclei importa resultados pendientes de revisión.','Maximum 4 MiB and 500 rows or hosts. Select a UTF-8 file. Nmap imports assets and services; Nuclei imports findings awaiting review.')),h('label',{},w('Formato','Format'),type),h('label',{},w('Archivo','File'),file));
    const two=h('section',{'data-import-panel':'2'},h('p',{},w('Comprueba las correspondencias propuestas y sus ejemplos. Los campos opcionales están agrupados.','Check the suggested mappings and their examples. Optional fields are grouped.')),mapBox);
    const three=h('section',{'data-import-panel':'3'},h('p',{},w('Revisa el contenido y la selección. Los duplicados se omiten. Los resultados entran sin verificar; revisa también posibles secretos en mensajes HTTP.','Review content and selection. Duplicates are skipped. Findings arrive unverified; check HTTP messages for possible secrets.')),rows);
    const back=button(w('Anterior','Back'),()=>show(step-1));
    const next=button(w('Continuar','Continue'),async()=>{if(!raw)throw Error(w('Selecciona un archivo.','Select a file.'));if(step===1){if(!current)await preview(true);if(current)show(2);}else if(await preview(false))show(3);});
    const apply=button(w('Importar selección como pendiente','Import selection for review'),async()=>{
      if(!current||!chosen.size)throw Error(w('Selecciona filas válidas.','Select valid rows.'));
      if(S.slug!==slug||projectStore.dirty||projectStore.etag!==etag)throw Error(w('El proyecto cambió; vuelve a abrir la importación.','The project changed; reopen the import.'));
      busyProject(true);try{const result=await json('/api/projects/'+encodeURIComponent(slug)+'/intake/apply',options({format,text:raw,bytes_base64:bytesBase64,mapping,selected:[...chosen]},etag));await adoptSavedProject(result.data.data,result.etag);d.close();renderSidebar();renderMain();toast(result.data.imported+' '+(result.data.import_kind==='inventory'?w('observaciones de inventario pendientes de revisión','inventory observations awaiting review'):w('hallazgos pendientes de revisión','findings awaiting review')),'ok');}finally{busyProject(false);}
    },true);
    function show(n){step=Math.max(1,Math.min(3,n));three.querySelector('p').textContent=format==='nmap'?w('Revisa el alcance y los servicios observados. La selección se incorpora como inventario y cobertura pendiente. Un puerto abierto no confirma una vulnerabilidad.','Review scope and observed services. The selection is added as inventory and pending coverage. An open port does not confirm a vulnerability.'):w('Revisa el contenido y la selección. Los duplicados se omiten. Los resultados entran sin verificar; revisa también posibles secretos en mensajes HTTP.','Review content and selection. Duplicates are skipped. Findings arrive unverified; check HTTP messages for possible secrets.');one.hidden=step!==1;two.hidden=step!==2;three.hidden=step!==3;back.hidden=step===1;next.hidden=step===3;next.textContent=step===2?w('Revisar selección','Review selection'):w('Continuar','Continue');apply.hidden=step!==3;apply.disabled=!current||!chosen.size;steps.querySelectorAll('li').forEach(li=>{if(Number(li.dataset.importStep)===step)li.setAttribute('aria-current','step');else li.removeAttribute('aria-current');});notice.textContent=step===3&&current?current.rows.length+' '+w('filas; ','rows; ')+chosen.size+' '+w('seleccionadas; ','selected; ')+(current.counts?.duplicates||0)+' '+w('coincidencias','matches')+(format==='nmap'?'; '+current.counts.services+' '+w('servicios observados','observed services'):''):'';}
    async function preview(rebuild){
      const run=++generation;current=null;apply.disabled=true;chosen.clear();rows.replaceChildren();notice.textContent=w('Analizando…','Reading…');
      try{if(!raw)return false;const result=await json('/api/projects/'+encodeURIComponent(slug)+'/intake/preview',options({format,text:raw,bytes_base64:bytesBase64,...(mapping?{mapping}:{})},etag));if(!d.isConnected||run!==generation)return false;current=result.data;etag=result.etag;mapping=current.mapping;
        if(rebuild){mapBox.replaceChildren();if(format==='csv'){
          const advanced=h('details',{class:'mapping-advanced'},h('summary',{},w('Campos opcionales','Optional fields'))),optional=h('div',{class:'intake-mapping'});advanced.append(optional);
          Object.entries(fields).forEach(([key,label])=>{const input=h('select',{'data-map':key},h('option',{value:''},w('No importar','Do not import')),...current.headers.map(head=>h('option',{value:head},head)));input.value=mapping[key]||'';
            const example=h('small',{class:'mapping-example'},w('Ejemplo: ','Example: ')+String(current.rows[0]?.finding[key]||'—').slice(0,160));
            input.addEventListener('change',()=>{generation++;mapping[key]=input.value;current=null;apply.disabled=true;rows.replaceChildren();example.textContent=w('Se comprobará al continuar.','Will be checked when you continue.');});
            (['title','severity','affected','description_md'].includes(key)?mapBox:optional).append(h('label',{},w(...label),input,example));});mapBox.append(advanced);
        }else mapBox.append(h('p',{},format==='nmap'?w('Nmap: una fila por host, con puertos, estados y versiones observadas. Se reutilizan los activos con la misma IP; cada observación queda en Cobertura como pendiente. No crea vulnerabilidades ni importa scripts NSE.','Nmap: one row per host, with observed ports, states and versions. Assets with the same IP are reused; each observation is added to Coverage as pending. Creates no vulnerabilities and does not import NSE scripts.'):w('Campos reconocidos automáticamente. Revisa cada resultado; una coincidencia del escáner no confirma una vulnerabilidad.','Fields recognized automatically. Review each result; a scanner match does not confirm a vulnerability.')));}
        for(const row of current.rows){if(row.kind==='inventory'){renderInventory(row);continue;}const f=row.finding,blocked=row.existing_duplicate||row.errors.length>0;const checkbox=h('input',{type:'checkbox',checked:(blocked||row.duplicate)?null:'',disabled:blocked?'':null,'data-intake-row':row.index});if(!blocked&&!row.duplicate)chosen.add(row.index);checkbox.addEventListener('change',()=>{if(checkbox.checked)chosen.add(row.index);else chosen.delete(row.index);show(step);});
          rows.append(h('article',{class:'card'},h('label',{class:'wf-check'},checkbox,f.title||w('Sin título','Untitled')),h('p',{},(f.severity||'?')+' / '+f.affected),row.duplicate?h('p',{},w('Coincidencia: selecciona solo una fila válida.','Match: choose only one valid row.')):null,...row.errors.map(error=>h('p',{class:'wf-error'},error)),h('details',{},h('summary',{},w('Revisar contenido','Review content')),...['description_md','impact_md','remediation_md','cvss_vector','cwe','references'].map(key=>h('section',{},h('h4',{},w(...fields[key])),h('pre',{},Array.isArray(f[key])?f[key].join('\n'):f[key]||'—'))),...(f.walkthrough||[]).map(s=>h('section',{},h('h4',{},s.lead),h('pre',{},s.command))),h('p',{},'ID: '+f.import_source.external_id+' / '+w('Confianza de origen: ','Source confidence: ')+f.import_source.confidence),h('p',{class:'hash'},'SHA-256: '+f.import_source.file_sha256))));}
        notice.textContent='';apply.disabled=!chosen.size;return true;
      }catch(e){if(run===generation&&d.isConnected){notice.textContent=e.message;current=null;apply.disabled=true;}return false;}
    }
    function renderInventory(row){
      const item=row.inventory,source=item.import_source,blocked=row.existing_duplicate||row.errors.length>0;
      const checkbox=h('input',{type:'checkbox',checked:(blocked||row.duplicate)?null:'',disabled:blocked?'':null,'data-intake-row':row.index});
      if(!blocked&&!row.duplicate)chosen.add(row.index);
      checkbox.addEventListener('change',()=>{if(checkbox.checked)chosen.add(row.index);else chosen.delete(row.index);show(step);});
      const contents=h('details',{},h('summary',{},w('Revisar servicios y origen','Review services and provenance')),
        h('p',{},w('Estado del host: ','Host state: ')+item.state),h('p',{},item.hostnames.join(', ')||w('Sin nombre de host','No hostname')),
        h('pre',{},item.services.map(s=>s.port+'/'+s.protocol+' · '+s.state+' · '+[s.tunnel,s.name,s.product,s.version,s.extrainfo].filter(Boolean).join(' ')).join('\n')||w('Sin puertos individuales en el archivo','No individual ports in this file')),
        ...item.extraports.map(p=>h('p',{},'Extraports: '+p.state+' ('+p.count+')')),
        h('p',{},'Nmap '+source.scanner_version+' / '+source.observed_at),h('p',{class:'hash'},'SHA-256: '+source.file_sha256));
      if(!item.scan_complete)contents.append(h('p',{class:'wf-hint'},w('El archivo no acredita que el escaneo terminara correctamente. La cobertura puede ser parcial.','The file does not record successful scan completion. Coverage may be partial.')));
      if(source.omitted_scripts)contents.append(h('p',{},source.omitted_scripts+' '+w('scripts NSE omitidos','NSE scripts omitted')));
      rows.append(h('article',{class:'card'},h('label',{class:'wf-check'},checkbox,item.target),
        h('p',{},item.services.length+' '+w('servicios; ','services; ')+(row.existing_asset?w('activo existente','existing asset'):w('activo nuevo','new asset'))),
        row.duplicate?h('p',{},w('Observación ya importada o repetida en el archivo. Selecciona solo una.','Observation already imported or repeated in this file. Select only one.')):null,contents));
    }
    type.addEventListener('change',()=>{generation++;format=type.value;mapping=null;current=null;rows.replaceChildren();mapBox.replaceChildren();show(1);});
    file.addEventListener('change',async()=>{const read=++generation;raw='';mapping=null;current=null;rows.replaceChildren();mapBox.replaceChildren();show(1);const selected=file.files[0];if(!selected)return;try{if(selected.size>4*1024*1024)throw Error(w('El archivo supera 4 MiB.','The file exceeds 4 MiB.'));const bytes=await selected.arrayBuffer();if(read!==generation||!d.isConnected)return;raw=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(bytes);bytesBase64=btoa(Array.from(new Uint8Array(bytes),x=>String.fromCharCode(x)).join(''));if(await preview(true))show(2);}catch(e){if(read===generation)notice.textContent=e.message;}});
    body.append(steps,one,two,three,notice,h('div',{class:'import-navigation'},back,next,apply));show(1);
  }
  function importReview(box,f){
    if(!f.import_source)return;
    const source=f.import_source;
    box.append(h('div',{class:'import-origin','data-field':'import_source'},h('h4',{},w('Origen de importación','Import provenance')),
      h('p',{},source.format+' / ID '+source.external_id),h('p',{class:'hash'},(source.hash_scope==='original_bytes'?w('SHA-256 del archivo: ','File SHA-256: '):source.hash_scope==='received_utf8_text'?w('SHA-256 del texto recibido: ','Received text SHA-256: '):w('SHA-256 del texto normalizado (legado): ','Normalized text SHA-256 (legacy): '))+source.file_sha256),
      h('label',{class:'wf-check'},h('input',{type:'checkbox',checked:source.reviewed?'':null,onchange:e=>{source.reviewed=e.target.checked;scheduleSave();}}),
        w('He revisado el contenido importado. Esto no confirma técnicamente el hallazgo.','I reviewed the imported content. This does not technically confirm the finding.'))));
  }
  function inventoryReview(item){
    if(item.import_source?.format!=='nmap')return null;
    const source=item.import_source;
    return h('details',{class:'import-origin'},h('summary',{},w('Observación Nmap original','Original Nmap observation')),
      h('p',{},w('Origen conservado. Editar las notas o marcar la prueba como realizada no modifica esta observación.','Preserved source. Editing notes or marking the test performed does not change this observation.')),
      h('p',{},source.external_id+' / Nmap '+source.scanner_version+' / '+source.observed_at),
      h('p',{class:'hash'},'SHA-256: '+source.file_sha256),
      h('pre',{},(item.services||[]).map(s=>s.port+'/'+s.protocol+' · '+s.state+' · '+[s.tunnel,s.name,s.product,s.version,s.extrainfo].filter(Boolean).join(' ')).join('\n')||w('Sin puertos individuales','No individual ports')));
  }
  function compare(box,slug,from,to){
    const path='/api/projects/'+encodeURIComponent(slug)+'/history/'+encodeURIComponent(from)+'/visual?lang='+S.uiLang+(to?'&to='+encodeURIComponent(to):'');
    box.replaceChildren(h('h3',{},w('Comparación visual','Visual comparison')),
      h('p',{},w('El HTML descargado incluye las imágenes y se puede abrir sin conexión o imprimir a PDF desde el navegador.','The downloaded HTML includes images and can be opened offline or printed to PDF in your browser.')),
      h('a',{class:'btn',href:path+'&download=1',download:'comparison.html'},w('Descargar comparación HTML','Download comparison HTML')),
      h('iframe',{class:'comparison-frame',src:path,sandbox:'',title:w('Texto y evidencias antes y después','Text and evidence before and after')}));
    box.append(button(w('Ver comparación interna privada','View private internal comparison'),()=>{if(!confirm(w('Incluye capturas y borradores privados. ¿Abrir para revisión interna?','Includes private captures and drafts. Open for internal review?')))return;const frame=box.querySelector('iframe');frame.src=path+'&internal=1';box.append(button(w('Descargar comparación interna','Download internal comparison'),()=>{if(confirm(w('Este archivo contiene datos privados. ¿Descargar?','This file contains private data. Download?')))h('a',{href:path+'&internal=1&download=1&ack_private=1',download:'comparison-private.html'}).click();}));}));
    box.scrollIntoView?.({block:'start'});
  }
  function update(){drawSave();paintJobs();const b=$('#jobsBtn');if(b)b.textContent=w('Exportaciones','Exports');const i=$('#intakeBtn');if(i){i.textContent=w('Importar resultados','Import results');i.disabled=!S.slug||projectBusyCount>0;}}
  function bind(){
    const b=button(w('Exportaciones','Exports'),jobs);b.id='jobsBtn';$('#exportMenu .action-menu-body').append(b);
    const i=button(w('Importar resultados','Import results'),intake);i.id='intakeBtn';$('#projectActionsList').append(i);
    const indicator=button('',jobs);indicator.id='exportIndicator';$('.workspace-toolbar').append(indicator);document.body.append(h('span',{id:'exportAnnouncement',class:'export-announcement',role:'status','aria-live':'polite'}));
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&jobsDialog){e.preventDefault();closeJobs();}});
    document.addEventListener('focusin',e=>{if(jobsDialog&&!jobsDialog.contains(e.target)&&e.target!==indicator)closeJobs(false);});pollJobs();update();
  }
  return {bind,update,saveState,enqueue,jobs,intake,compare,importReview,inventoryReview};
})();
