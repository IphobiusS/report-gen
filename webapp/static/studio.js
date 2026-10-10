/* 0.20: task navigation, recovery and the explicit publication boundary. */
const StudioUI=(()=>{
'use strict';const w=(es,en)=>S.uiLang==='en'?en:es;
let mode='work',bound=false,opener=null;
function button(text,run,primary=false){const b=h('button',{type:'button',class:'btn'+(primary?' primary':'')},text);b.addEventListener('click',async()=>{opener=b;b.disabled=true;try{await run(b);}catch(e){toast(e.message,'err');}finally{b.disabled=false;}});return b;}
function dialog(title){const previous=document.activeElement===document.body?opener:document.activeElement,d=h('dialog',{class:'experience-dialog studio-dialog','aria-label':title}),body=h('div',{class:'experience-body'});d.append(h('div',{class:'experience-heading'},h('h2',{},title),button(w('Cerrar','Close'),()=>d.close())),body);d.addEventListener('close',()=>{d.remove();const target=previous?.closest('details:not([open])')?.querySelector('summary')||previous;(target?.isConnected?target:$('#editor')).focus();});document.body.append(d);d.showModal();return{d,body};}
function downloadDraft(record=projectStore.draftFile()){const url=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}));h('a',{href:url,download:(record.slug||'project')+'.report-gen-draft.json'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function valueText(v){return v===undefined?w('(eliminado)','(deleted)'):typeof v==='string'?v:JSON.stringify(v,null,2);}
async function resolveDraft(candidate){
  const remote=await projectStore.remote(),local=candidate?.data||projectStore.data,base=candidate?.base||projectStore.base,slug=S.slug,rev=projectStore.revision;
  if(!base||!local||typeof local!=='object'||Array.isArray(local))throw Error(w('Borrador incompatible. Conserva su archivo y revisa los datos.','Incompatible draft. Keep its file and review the data.'));
  const choices={},initial=mergeDraft(base,local,remote.data),{d,body}=dialog(w('Recuperar y resolver cambios','Recover and resolve changes'));
  body.append(h('p',{},w('Se combinan los cambios independientes. Elige qué conservar donde ambos textos cambiaron. Nada se sustituye hasta guardar.','Independent edits are merged. Choose what to keep where both versions changed. Nothing is replaced until you save.')),button(w('Descargar copia de emergencia','Download emergency copy'),()=>downloadDraft(candidate||projectStore.draftFile())));
  const apply=button(w('Aplicar selección y guardar','Apply choices and save'),async()=>{
    if(S.slug!==slug||projectStore.revision!==rev)throw Error(w('El proyecto cambió. Abre nuevamente la comparación.','The project changed. Reopen the comparison.'));
    if(initial.conflicts.some(c=>!choices[c.path]))throw Error(w('Resuelve todos los campos.','Resolve every field.'));
    const merged=mergeDraft(base,local,remote.data,choices).data;
    const checked=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/draft-check',{method:'POST',headers:{'Content-Type':'application/json','If-Match':remote.etag},body:JSON.stringify(merged)}));
    const accepted=(await checked.json()).data;accepted.report||={sections:[]};accepted.report.sections||=[];
    projectStore.adopt(accepted,remote);S.data=projectStore.data;
    const saved=await doSave();renderSidebar();renderMain();
    if(saved&&candidate?.id){await projectStore.journal?.removeUnchanged(candidate);projectStore.recovery=projectStore.recovery.filter(x=>x.id!==candidate.id);}
    d.close();
  },true);
  apply.disabled=initial.conflicts.length>0;
  for(const c of initial.conflicts){const section=h('section',{class:'merge-field'},h('h3',{},c.path)),group='choice-'+Math.random().toString(36).slice(2),cols=h('div',{class:'merge-pair'});
    for(const key of ['local','remote']){const radio=h('input',{type:'radio',name:group,value:key});radio.addEventListener('change',()=>{choices[c.path]=key;apply.disabled=initial.conflicts.some(c=>!choices[c.path]);});cols.append(h('div',{},h('label',{class:'wf-check'},radio,key==='local'?w('Mi borrador','My draft'):w('Guardado en disco','Saved on disk')),h('pre',{},valueText(c[key]))));}
    section.append(cols,h('details',{},h('summary',{},w('Versión de origen','Base version')),h('pre',{},valueText(c.base))));body.append(section);
  }
  if(!initial.conflicts.length)body.append(h('p',{},w('No hay campos en conflicto.','There are no conflicting fields.')));
  body.append(apply);
}
async function recovery(){
  const slug=S.slug,rows=projectStore.recovery||[];let pending=[];try{if(typeof PendingUI!=='undefined')pending=await PendingUI.list(slug);}catch(error){/* Form status reports unavailable storage when edited. */}if(S.slug!==slug||(!rows.length&&!pending.length))return;
  const {d,body}=dialog(w('Hay borradores recuperables','Recoverable drafts found'));
  body.append(h('p',{},w('Son copias privadas de este navegador, con retención de 30 días. Pueden pertenecer a otra pestaña abierta. Revisa antes de incorporarlas.','These are private copies in this browser, retained for 30 days. Another open tab may own them. Review before applying.')));
  for(const row of pending)body.append(PendingUI.recoverySection(row));
  d.addEventListener('close',()=>body.querySelectorAll('[data-pending-record]').forEach(node=>node.release?.()));
  rows.forEach(row=>body.append(h('section',{class:'card'},h('h3',{},new Date(row.updated).toLocaleString()),
    button(w('Comparar y recuperar','Compare and recover'),async()=>{if(row.format!=='report-gen-draft'||row.version!==1)throw Error(w('Versión de borrador no compatible. Descarga una copia.','Unsupported draft version. Download a copy.'));d.close();await resolveDraft(row);},true),
    button(w('Descargar copia','Download copy'),()=>downloadDraft(row)),button(w('Descartar borrador','Discard draft'),async()=>{if(!confirm(w('¿Eliminar esta copia del navegador?','Delete this browser copy?')))return;await projectStore.journal.removeUnchanged(row);projectStore.recovery=projectStore.recovery.filter(x=>x.id!==row.id);d.close();recovery();}))));
}
function saveHelp(banner){
  if(!banner||banner.querySelector('[data-draft-actions]'))return;
  const box=h('div',{'data-draft-actions':'',class:'studio-actions'},button(w('Resolver con versión guardada','Resolve with saved version'),()=>resolveDraft()),button(w('Descargar borrador','Download draft'),()=>downloadDraft()));banner.append(box);
}
function update(){
  if(!bound)return;
  ExperienceUI.updateDeliveryChecklist();
  mode=['guide','insights'].includes(S.sel.type)?S.sel.type:S.sel.type==='studio'?S.sel.idx:S.sel.type==='workflow'&&['review','history','retest','retest_diff','retest_matrix','root_causes','remediation_tasks'].includes(S.sel.idx)?'review':'work';
  document.documentElement.dataset.studio=mode;
  const names={work:['Trabajar','Work'],review:['Revisar','Review'],deliver:['Entregar','Deliver'],library:['Biblioteca','Library']};
  Object.entries(names).forEach(([key,pair])=>{const b=$('[data-studio-nav="'+key+'"]');b.textContent=w(...pair);b.setAttribute('aria-current',key===mode?'page':'false');b.disabled=!S.slug&&['review','deliver'].includes(key);});
  $('#studioMore summary').textContent=w('Más','More');$('#studioPreferences summary').textContent=w('Preferencias','Preferences');$('#draftExportBtn').textContent=w('Descargar borrador privado','Download private draft');$('#draftExportBtn').disabled=!S.slug;$('#draftImportLabel').textContent=w('Recuperar archivo de borrador','Recover draft file');
  const indicator=$('#draftStatus');if(projectStore.dirty){indicator.textContent=projectStore.recoverableRevision===projectStore.revision?w('Borrador recuperable en este navegador','Draft recoverable in this browser'):projectStore.draftError?w('Borrador solo en esta pestaña','Draft only in this tab'):w('Protegiendo borrador…','Protecting draft…');}else indicator.textContent='';
  saveHelp($('#saveError'));
}
async function inspector(){
  if(!S.slug||!await doSave())return;
  const slug=S.slug,revision=projectStore.etag;const data=await api.get('/api/projects/'+encodeURIComponent(slug)+'/publication');
  if(S.slug!==slug)return;
  const {d,body}=dialog(w('Inspector de publicación','Publication inspector'));
  body.append(h('p',{},w('Revisa el texto completo y las imágenes que saldrán. Las capturas privadas, los originales y el historial quedan en el proyecto.','Review the full outgoing text and images. Private captures, originals and history stay in the project.')),
    h('p',{class:'hash'},w('Revisión: ','Revision: ')+data.revision.slice(0,12)+' / '+data.images.length+' '+w('imágenes','images')+' / '+data.private_captures+' '+w('capturas privadas excluidas','private captures excluded')),
    h('p',{},w('La detección por patrones puede omitir secretos. Una excepción registra tu decisión, no modifica el texto. La censura de texto solo cambia la copia publicada; revisa los comandos resultantes.','Pattern detection can miss secrets. An exception records your decision without editing text. Text redaction changes only the published copy; review resulting commands.')));
  const mutate=async fn=>{if(S.slug!==slug||projectStore.etag!==revision||projectStore.dirty)throw Error(w('El proyecto cambió. Vuelve a abrir el inspector.','The project changed. Reopen the inspector.'));S.data.publication||={redactions:[],exceptions:[]};fn(S.data.publication);scheduleSave();if(await doSave()){d.close();inspector();}};
  const alerts=h('section',{},h('h3',{},w('Posibles secretos','Possible secrets')));
  if(!data.alerts.length)alerts.append(h('p',{},w('Sin coincidencias en los patrones comprobados. Haz también una revisión manual.','No matches in the checked patterns. Review manually as well.')));
  for(const a of data.alerts){const reason=h('input',{value:a.reason,maxlength:4000,'aria-label':w('Motivo de la excepción','Exception reason')});alerts.append(h('div',{class:'card'},h('strong',{},a.kind+' / '+a.preview),h('label',{},w('Justificación si debe publicarse','Reason if it must be published'),reason),button(w('Registrar excepción','Record exception'),()=>{if(!reason.value.trim())throw Error(w('Escribe un motivo.','Enter a reason.'));return mutate(c=>{c.exceptions=(c.exceptions||[]).filter(x=>x.id!==a.id);c.exceptions.push({id:a.id,reason:reason.value});});})));}
  body.append(alerts);
  const needle=h('input',{autocomplete:'off',maxlength:2000,'aria-label':w('Texto literal a censurar','Literal text to redact')}),replacement=h('input',{value:'[REDACTED]',maxlength:4000,'aria-label':w('Sustitución','Replacement')});
  body.append(h('details',{},h('summary',{},w('Censura de texto para publicar','Text redaction for publication')),h('p',{},w('Sustituye todas las coincidencias literales en el contenido publicado. Mínimo cuatro caracteres. No edita los originales.','Replaces all literal matches in published content. At least four characters. Originals are not edited.')),h('label',{},w('Texto literal','Literal text'),needle),h('label',{},w('Sustitución','Replacement'),replacement),button(w('Aplicar y volver a inspeccionar','Apply and inspect again'),()=>{if(needle.value.length<4)throw Error(w('Usa al menos cuatro caracteres.','Use at least four characters.'));return mutate(c=>{c.redactions||=[];c.redactions.push({needle:needle.value,replacement:replacement.value});});})));
  const rules=S.data.publication?.redactions||[];
  if(rules.length)body.append(h('details',{},h('summary',{},rules.length+' '+w('censuras registradas','recorded redactions')),...rules.map((rule,index)=>h('div',{class:'card'},h('code',{},rule.needle+' → '+rule.replacement),button(w('Retirar esta censura','Remove this redaction'),()=>mutate(c=>c.redactions.splice(index,1)))))));
  body.append(h('details',{open:''},h('summary',{},w('Texto que se publicará','Outgoing text')),h('pre',{class:'publication-text',tabindex:0},data.text)));
  const inventory=h('section',{},h('h3',{},w('Imágenes de publicación','Published images')),h('p',{},w('El OCR opcional usa Tesseract local con datos eng, solo al pulsar el botón de cada imagen. Señala zonas posibles sin mostrar ni guardar el texto reconocido. No censura imágenes ni sustituye la revisión manual.','Optional OCR uses local Tesseract with eng data, only when you press each image button. It flags possible areas without displaying or retaining recognized text. It does not redact images or replace manual review.')));
  for(const img of data.images){inventory.append(h('details',{},h('summary',{},img.name+' / '+Math.round(img.bytes/1024)+' KB'),h('img',{src:'/api/projects/'+encodeURIComponent(slug)+'/publication/image?name='+encodeURIComponent(img.name)+'&revision='+encodeURIComponent(data.revision),alt:img.name,loading:'lazy'}),h('p',{},w('Metadatos retirados de la derivada','Metadata removed from derivative')+(img.metadata.length?': '+img.metadata.join(', '):'')),h('p',{class:'hash'},w('Original privado: ','Private original: ')+img.original_sha256),h('p',{class:'hash'},w('Publicado: ','Published: ')+img.sha256),PrivacyUI.ocr(img,slug,revision)));}
  body.append(inventory,button(w('Abrir evidencias para censurar una imagen','Open evidence to redact an image'),()=>{d.close();select('workflow','evidence');}),h('p',{},w('Archivos disponibles: informe.pdf, informe.docx, markdown.zip, informe.html y el registro de verificación. Solo se incluyen los formatos que selecciones.','Available files: informe.pdf, informe.docx, markdown.zip, informe.html and the verification record. Only selected formats are included.')));
}
function render(el,kind){
  if(kind==='deliver'){
    el.append(h('div',{class:'studio-stage'},h('p',{class:'workspace-path'},'~/'+S.slug+'/delivery'),h('h1',{},w('Una revisión. Cuatro entregables.','One revision. Four deliverables.')),h('p',{},w('Comprueba qué compartes y genera los formatos desde la misma copia guardada.','Check what you share and generate formats from the same saved snapshot.')),
      h('section',{class:'card'},h('h2',{},w('1. Inspeccionar','1. Inspect')),h('p',{},w('Texto completo, imágenes sin metadatos, posibles secretos y excepciones.','Full text, metadata-free images, possible secrets and exceptions.')),button(w('Abrir inspector','Open inspector'),inspector,true)),
      h('section',{class:'card'},h('h2',{},w('3. Preparar entrega','3. Prepare delivery')),h('p',{},w('PDF, Word, Markdown o un HTML autónomo con filtros, evidencias y retest. El HTML contiene todo el informe, incluso al filtrar.','PDF, Word, Markdown or standalone HTML with filters, evidence and retest. HTML contains the whole report, even when filtered.')),button(w('Elegir formatos','Choose formats'),()=>ExperienceUI.prepareDelivery(),true),button(w('Exportaciones y descargas','Exports and downloads'),()=>ProgressUI.jobs()))));
    const stage=el.querySelector('.studio-stage');stage.insertBefore(ExperienceUI.deliveryChecklist(),stage.querySelector('section'));stage.insertBefore(AnnexUI.card(),stage.lastElementChild);
  }else{
    el.append(h('div',{class:'studio-stage'},h('h1',{},w('Tu biblioteca de trabajo','Your working library')),h('p',{},w('La apariencia se aplica sin sustituir los hallazgos que ya escribiste.','Apply an appearance without replacing findings you have written.')),
      h('section',{class:'card'},h('h2',{},w('Diseño del informe','Report design')),h('p',{},w('Empieza con Serio y compara páginas equivalentes de los seis diseños generales. El catálogo completo conserva los perfiles especializados y tus plantillas personales.','Start with Serious and compare equivalent pages from the six general designs. The full catalog keeps specialized profiles and your personal designs available.')),button(w('Explorar galería','Explore gallery'),opener=>DesignLibraryUI.gallery(opener),true)),
      h('section',{class:'card'},h('h2',{},w('Hallazgos reutilizables','Reusable findings')),h('p',{},w('Variables y pasos editables. Cada nueva instancia comienza sin verificar.','Editable variables and steps. Each new instance starts unverified.')),button(w('Abrir biblioteca de hallazgos','Open findings library'),()=>{if(!S.slug)throw Error(w('Abre un proyecto primero.','Open a project first.'));WorkflowUI.openLibrary();}))));
  }
}
function bind(){
  const top=$('.workspace-topline'),toolbar=$('.workspace-toolbar');
  const prefs=h('details',{id:'studioPreferences'},h('summary',{},w('Preferencias','Preferences')),$('.workspace-preferences'));const more=h('details',{id:'studioMore'},h('summary',{},w('Más','More'))),panel=h('div',{class:'studio-more-body'});
  for(const id of ['newProjectBtn','projectActions','exportMenu','deliverySlot','exportIndicator']){const node=$('#'+id);if(node)panel.append(node);}
  panel.append(prefs,$('#workspaceContext'));more.append(panel);top.append(more);
  const search=$('.search-wrap'),media=window.matchMedia('(max-width:760px)');
  function placeSearch(){if(media.matches)panel.prepend(search);else top.insertBefore(search,more);}
  media.addEventListener?.('change',placeSearch);placeSearch();
  const nav=h('nav',{class:'studio-nav','aria-label':w('Flujo del informe','Report workflow')});
  for(const key of ['work','review','deliver','library']){const b=button('',()=>{more.open=false;if(key==='work')select('home');else if(key==='review')select('workflow','review');else select('studio',key);$('#editor').focus({preventScroll:true});});b.dataset.studioNav=key;nav.append(b);}
  toolbar.replaceChildren($('#sidebarToggle'),nav,$('#saveState'));$('#saveState').after(h('span',{id:'draftStatus',role:'status'}));
  const emergency=button('',()=>downloadDraft());emergency.id='draftExportBtn';panel.append(emergency);
  const file=h('input',{type:'file',accept:'.json','aria-label':w('Archivo de borrador','Draft file')});file.addEventListener('change',async()=>{try{const f=file.files[0];if(!f)return;if(f.size>24*1024*1024)throw Error(w('Borrador demasiado grande.','Draft too large.'));const record=JSON.parse(await f.text());if(record.format!=='report-gen-draft'||record.version!==1||record.slug!==S.slug)throw Error(w('Abre el proyecto correspondiente; el borrador debe ser de formato 1.','Open the matching project; draft format must be 1.'));await resolveDraft(record);}catch(e){toast(e.message,'err');}finally{file.value='';}});panel.append(h('label',{},h('span',{id:'draftImportLabel'}),file));
  const inspectButton=button(w('Inspector de publicación','Publication inspector'),inspector);inspectButton.id='publicationBtn';$('#exportMenu .action-menu-body').append(inspectButton);
  more.addEventListener('toggle',()=>{if(!more.open)return;});document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!document.querySelector('dialog[open]')){more.open=false;}});
  bound=true;update();
}
return{bind,update,render,recovery,resolveDraft,saveHelp,inspector,downloadDraft};
})();
