/* 0.20: task navigation, recovery and the explicit publication boundary. */
const StudioUI=(()=>{
'use strict';const w=(es,en,pt)=>uiText(es,en,pt);
let mode='work',bound=false,opener=null,recoveryGeneration=0,recoveryDialog=null,resolutionGeneration=0;
function button(text,run,primary=false){const b=h('button',{type:'button',class:'btn'+(primary?' primary':'')},text);b.addEventListener('click',async()=>{opener=b;b.disabled=true;try{await run(b);}catch(e){toast(e.message,'err');}finally{b.disabled=false;}});return b;}
function dialog(title){const previous=document.activeElement===document.body?opener:document.activeElement,d=h('dialog',{class:'experience-dialog studio-dialog','aria-label':title}),body=h('div',{class:'experience-body'});d.append(h('div',{class:'experience-heading'},h('h2',{},title),button(w('Cerrar','Close', "Fechar"),()=>d.close())),body);d.addEventListener('close',()=>{d.remove();const target=previous?.closest('details:not([open])')?.querySelector('summary')||previous;(target?.isConnected?target:$('#editor')).focus();});document.body.append(d);d.showModal();return{d,body};}
function downloadDraft(record=projectStore.draftFile()){const url=URL.createObjectURL(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}));h('a',{href:url,download:(record.slug||'project')+'.report-gen-draft.json'}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function valueText(v){return v===undefined?w('(eliminado)','(deleted)', "(excluído)"):typeof v==='string'?v:JSON.stringify(v,null,2);}
async function resolveDraft(candidate){
  if(candidate&&candidate.workspace_id!==BrowserWorkspace.current()&&!confirm(w('Este archivo no identifica el espacio actual. Puede pertenecer a otro cliente o instalación. ¿Confirmas que quieres compararlo con este proyecto? Todavía no se guardará nada.','This file does not identify the current workspace. It may belong to another client or installation. Confirm that you want to compare it with this project. Nothing will be saved yet.', "Este arquivo não identifica o espaço de trabalho atual. Ele pode pertencer a outro cliente ou instalação. Confirme que deseja compará-lo com este projeto. Nada será salvo ainda.")))return;
  const generation=++resolutionGeneration,slug=S.slug,current=S.data,rev=projectStore.revision,etag=projectStore.etag;
  const stale=()=>{if(generation!==resolutionGeneration||S.slug!==slug||S.data!==current||projectStore.revision!==rev||projectStore.etag!==etag||projectStore.loading)throw Error(w('El proyecto cambió. Abre nuevamente la comparación.','The project changed. Reopen the comparison.', "O projeto mudou. Reabra a comparação."));};
  if(!slug||(candidate&&candidate.slug!==slug))throw Error(w('Abre el proyecto correspondiente al borrador.','Open the project matching this draft.', "Abra o projeto correspondente a este rascunho."));
  const local=candidate?.data||projectStore.data,base=candidate?.base||projectStore.base;
  const remote=await projectStore.remote();stale();
  if(!base||!local||typeof local!=='object'||Array.isArray(local))throw Error(w('Borrador incompatible. Conserva su archivo y revisa los datos.','Incompatible draft. Keep its file and review the data.', "Rascunho incompatível. Mantenha o arquivo e revise os dados."));
  const choices={},initial=mergeDraft(base,local,remote.data),{d,body}=dialog(w('Recuperar y resolver cambios','Recover and resolve changes', "Recuperar e resolver alterações"));
  body.append(h('p',{},w('Se combinan los cambios independientes. Elige qué conservar donde ambos textos cambiaron. Nada se sustituye hasta guardar.','Independent edits are merged. Choose what to keep where both versions changed. Nothing is replaced until you save.', "Edições independentes são mescladas. Escolha o que manter onde ambas as versões mudaram. Nada será substituído até você salvar.")),button(w('Descargar copia de emergencia','Download emergency copy', "Baixar cópia de emergência"),()=>downloadDraft(candidate||projectStore.draftFile())));
  const apply=button(w('Aplicar selección y guardar','Apply choices and save', "Aplicar escolhas e salvar"),async()=>{
    stale();if(!d.open||!d.isConnected)return;
    if(initial.conflicts.some(c=>!choices[c.path]))throw Error(w('Resuelve todos los campos.','Resolve every field.', "Resolva todos os campos."));
    const merged=mergeDraft(base,local,remote.data,choices).data;
    const checked=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/draft-check',{method:'POST',headers:{'Content-Type':'application/json','If-Match':remote.etag},body:JSON.stringify(merged)}));
    const accepted=(await checked.json()).data;stale();if(!d.open||!d.isConnected)return;
    accepted.report||={sections:[]};accepted.report.sections||=[];
    const selectedFinding=S.sel?.type==='finding'?S.data.findings[S.sel.idx]?.uid:null;
    invalidateValidation();projectStore.adopt(accepted,remote);S.data=projectStore.data;
    if(S.sel?.type==='finding'){
      const idx=selectedFinding?(S.data.findings||[]).findIndex(f=>f.uid===selectedFinding):-1;
      S.sel=idx>=0?{type:'finding',idx}:{type:'report',idx:-1};
    }else if(S.sel?.type==='section'&&!S.data.report.sections.some(section=>section.key===S.sel.key))S.sel={type:'report',idx:-1};
    const saved=await doSave();renderSidebar();renderMain();
    if(saved&&candidate?.id){await projectStore.journal?.removeUnchanged(candidate);projectStore.recovery=projectStore.recovery.filter(x=>x.id!==candidate.id);}
    d.close();
  },true);
  apply.disabled=initial.conflicts.length>0;
  for(const c of initial.conflicts){const section=h('section',{class:'merge-field'},h('h3',{},c.path)),group='choice-'+Math.random().toString(36).slice(2),cols=h('div',{class:'merge-pair'});
    for(const key of ['local','remote']){const radio=h('input',{type:'radio',name:group,value:key});radio.addEventListener('change',()=>{choices[c.path]=key;apply.disabled=initial.conflicts.some(c=>!choices[c.path]);});cols.append(h('div',{},h('label',{class:'wf-check'},radio,key==='local'?w('Mi borrador','My draft', "Meu rascunho"):w('Guardado en disco','Saved on disk', "Salvo no disco")),h('pre',{},valueText(c[key]))));}
    section.append(cols,h('details',{},h('summary',{},w('Versión de origen','Base version', "Versão base")),h('pre',{},valueText(c.base))));body.append(section);
  }
  if(!initial.conflicts.length)body.append(h('p',{},w('No hay campos en conflicto.','There are no conflicting fields.', "Não há campos em conflito.")));
  body.append(apply);
}
function legacyCopies(){
 const {body}=dialog(w('Copias anteriores sin asignación','Unassigned legacy copies', "Cópias legadas sem atribuição"));
 body.append(h('p',{},w('Las versiones anteriores guardaban borradores y capturas sin identificar el espacio de trabajo. No podemos determinar a qué instalación pertenecen. Se conservan sin incorporarlos ni eliminarlos automáticamente.','Earlier versions stored drafts and captures without a workspace identity. Their installation cannot be determined. They are retained without automatic adoption or deletion.', "Versões anteriores armazenavam rascunhos e capturas sem identidade do espaço de trabalho. Não é possível determinar a instalação de origem. Eles são mantidos sem adoção ou exclusão automática.")),
  h('p',{},w('Revisar mostrará contenido privado que puede pertenecer a otro espacio. Puedes descargarlo y eliminar únicamente las copias que elijas. Para recuperar un borrador descargado, abre primero el proyecto correcto y usa Recuperar archivo de borrador.','Reviewing shows private content that may belong to another workspace. You can download it and delete only the copies you choose. To recover a downloaded draft, first open the correct project and use Recover draft file.', "A revisão mostra conteúdo privado que pode pertencer a outro espaço de trabalho. Você pode baixá-lo e excluir somente as cópias escolhidas. Para recuperar um rascunho baixado, abra primeiro o projeto correto e use Recuperar arquivo de rascunho.")));
 const review=button(w('Entiendo el origen incierto; revisar copias','I understand the uncertain origin; review copies', "Entendo a origem incerta; revisar cópias"),async()=>{
  const rows=await LegacyBrowserCopies.list();review.remove();
  if(!rows.length)body.append(h('p',{},w('No hay copias anteriores sin asignación en este navegador.','There are no unassigned legacy copies in this browser.', "Não há cópias legadas sem atribuição neste navegador.")));
  for(const {kind,row} of rows){
   const section=h('section',{class:'card','data-legacy-record':row.id},h('h3',{},String(row.label||row.slug||w('Copia privada','Private copy', "Cópia privada"))),
    h('p',{},w('Sin espacio identificado · ','Workspace unknown · ', "Espaço de trabalho desconhecido · ")+new Date(row.updated||0).toLocaleString(languageTag(S.uiLang))),
    h('details',{},h('summary',{},w('Ver contenido privado','Show private content', "Mostrar conteúdo privado")),h('pre',{class:'publication-text',tabindex:0},JSON.stringify(row.data,null,2))));
   const actions=h('div',{class:'studio-actions'});section.append(actions);
   function download(blob,name){const url=URL.createObjectURL(blob);h('a',{href:url,download:name}).click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
   actions.append(button(w('Descargar copia privada','Download private copy', "Baixar cópia privada"),()=>{
    if(kind==='drafts')downloadDraft(row);
    else {const record={...row,file:row.file?{name:row.file.name||'pending-image',type:row.file.type,size:row.file.size}:null};download(new Blob([JSON.stringify(record,null,2)],{type:'application/json'}),(row.slug||'project')+'.report-gen-pending.json');}
   }));
   if(kind==='pending'&&row.file)actions.append(button(w('Descargar imagen original pendiente','Download original pending image', "Baixar imagem original pendente"),()=>download(row.file,row.file.name||'pending-image')));
   actions.append(button(w('Eliminar esta copia anterior','Delete this legacy copy', "Excluir esta cópia legada"),async()=>{
    if(!confirm(w('¿Eliminar únicamente esta copia anterior del navegador? Guarda antes una descarga si necesitas conservarla.','Delete only this legacy browser copy? Download it first if you need to keep it.', "Excluir somente esta cópia legada do navegador? Baixe-a primeiro se precisar mantê-la.")))return;
    if(!await LegacyBrowserCopies.remove(kind,row))throw Error(w('La copia cambió; vuelve a abrir esta vista.','The copy changed; reopen this view.', "A cópia mudou; reabra esta visualização."));
    section.remove();
   }));body.append(section);
  }
 });review.dataset.legacyReview='';body.append(review);
}
async function recovery(){
  const generation=++recoveryGeneration,slug=S.slug,data=S.data,etag=projectStore.etag,lang=S.uiLang,rows=projectStore.recovery||[];
  if(recoveryDialog?.isConnected&&recoveryDialog.dataset.recoveryProject!==slug){recoveryDialog.close();recoveryDialog.remove();recoveryDialog=null;}
  if(projectStore.loading||projectBusyCount>0)return;
  let pending=[];try{if(typeof PendingUI!=='undefined')pending=await PendingUI.list(slug);}catch{/* Form status reports unavailable storage when edited. */}
  // Loading and the explicit recovery action can overlap. Only the latest
  // request for this exact project view may present its private records.
  if(generation!==recoveryGeneration||S.slug!==slug||S.data!==data||projectStore.etag!==etag||S.uiLang!==lang||projectStore.loading||projectBusyCount>0)return;
  const signature=JSON.stringify([slug,etag,lang,rows,pending.map(row=>[row.id,row.token])]);
  if(recoveryDialog?.isConnected){
    if(recoveryDialog.open&&recoveryDialog.recoverySignature===signature)return;
    recoveryDialog.close();recoveryDialog.remove();recoveryDialog=null;
  }
  if(!rows.length&&!pending.length)return;
  const {d,body}=dialog(w('Hay borradores recuperables','Recoverable drafts found', "Rascunhos recuperáveis encontrados"));
  recoveryDialog=d;d.dataset.recoveryProject=slug;d.recoverySignature=signature;
  d.addEventListener('close',()=>{if(recoveryDialog===d)recoveryDialog=null;});
  body.append(h('p',{},w('Son copias privadas de este navegador, con retención de 30 días. Pueden pertenecer a otra pestaña abierta. Revisa antes de incorporarlas.','These are private copies in this browser, retained for 30 days. Another open tab may own them. Review before applying.', "Estas são cópias privadas neste navegador, mantidas por 30 dias. Outra aba aberta pode ser sua proprietária. Revise antes de aplicar.")));
  for(const row of pending)body.append(PendingUI.recoverySection(row));
  d.addEventListener('close',()=>body.querySelectorAll('[data-pending-record]').forEach(node=>node.release?.()));
  rows.forEach(row=>body.append(h('section',{class:'card'},h('h3',{},new Date(row.updated).toLocaleString()),
    button(w('Comparar y recuperar','Compare and recover', "Comparar e recuperar"),async()=>{if(row.format!=='report-gen-draft'||row.version!==1)throw Error(w('Versión de borrador no compatible. Descarga una copia.','Unsupported draft version. Download a copy.', "Versão de rascunho não compatível. Baixe uma cópia."));d.close();await resolveDraft(row);},true),
    button(w('Descargar copia','Download copy', "Baixar cópia"),()=>downloadDraft(row)),button(w('Descartar borrador','Discard draft', "Descartar rascunho"),async()=>{if(!confirm(w('¿Eliminar esta copia del navegador?','Delete this browser copy?', "Excluir esta cópia do navegador?")))return;await projectStore.journal.removeUnchanged(row);projectStore.recovery=projectStore.recovery.filter(x=>x.id!==row.id);d.close();recovery();}))));
}
function saveHelp(banner){
  if(!banner||banner.querySelector('[data-draft-actions]'))return;
  const box=h('div',{'data-draft-actions':'',class:'studio-actions'},button(w('Resolver con versión guardada','Resolve with saved version', "Resolver com a versão salva"),()=>resolveDraft()),button(w('Descargar borrador','Download draft', "Baixar rascunho"),()=>downloadDraft()));banner.append(box);
}
function update(){
  if(!bound)return;
  ExperienceUI.updateDeliveryChecklist();
  if(typeof DeliveryFlowUI!=='undefined')DeliveryFlowUI.update();
  mode=['guide','insights'].includes(S.sel.type)?S.sel.type:S.sel.type==='studio'?S.sel.idx:S.sel.type==='workflow'&&['review','history','retest','retest_diff','retest_matrix','root_causes','remediation_tasks'].includes(S.sel.idx)?'review':'work';
  document.documentElement.dataset.studio=mode;
  const names={work:['Trabajar','Work', "Trabalhar"],review:['Revisar','Review', "Revisar"],deliver:['Entregar','Deliver', "Entregar"],library:['Biblioteca','Library', "Biblioteca"]};
  Object.entries(names).forEach(([key,pair])=>{const b=$('[data-studio-nav="'+key+'"]');b.textContent=w(...pair);b.setAttribute('aria-current',key===mode?'page':'false');b.disabled=!S.slug&&['review','deliver'].includes(key);});
  $('#studioMore summary').textContent=w('Más','More', "Mais");$('#studioPreferences summary').textContent=w('Preferencias','Preferences', "Preferências");$('#draftExportBtn').textContent=w('Descargar borrador privado','Download private draft', "Baixar rascunho privado");$('#draftExportBtn').disabled=!S.slug;$('#draftImportLabel').textContent=w('Recuperar archivo de borrador','Recover draft file', "Recuperar arquivo de rascunho");
  $('#publicationBtn').textContent=w('Inspector de publicación','Publication inspector', "Inspetor de publicação");
  $('[data-legacy-copies]').textContent=w('Copias anteriores sin asignación','Unassigned legacy copies', "Cópias legadas sem atribuição");
  const indicator=$('#draftStatus');if(projectStore.dirty){indicator.textContent=projectStore.recoverableRevision===projectStore.revision?w('Borrador recuperable en este navegador','Draft recoverable in this browser', "Rascunho recuperável neste navegador"):projectStore.draftError?w('Borrador solo en esta pestaña','Draft only in this tab', "Rascunho somente nesta aba"):w('Protegiendo borrador…','Protecting draft…', "Protegendo rascunho…");}else indicator.textContent='';
  saveHelp($('#saveError'));
}
async function inspector(origin=null){
  if(origin?.format!=='report-gen-pending')origin=null;
  if(origin&&(origin.workspace_id!==BrowserWorkspace.current()||origin.slug!==S.slug||projectStore.dirty||projectStore.loading))throw Error(w('Abre el proyecto original y guarda o resuelve sus cambios antes de recuperar.','Open the original project and save or resolve its changes before recovering.','Abra o projeto original e salve ou resolva suas alterações antes de recuperar.'));
  const generation=(inspector.generation||0)+1;inspector.generation=generation;
  if(!S.slug||(!origin&&!await doSave()))return;
  const slug=S.slug,current=S.data,localRevision=projectStore.revision,revision=projectStore.etag;const data=await api.get('/api/projects/'+encodeURIComponent(slug)+'/publication');
  if(generation!==inspector.generation||S.slug!==slug||S.data!==current||projectStore.revision!==localRevision||projectStore.etag!==revision||projectStore.dirty||projectStore.loading)return;
  if(origin?.data?.kind==='exception'&&!data.alerts.some(alert=>alert.id===origin.data.alert_id))throw Error(w('La alerta ya no existe. Conserva el texto de la copia pendiente; no se registró ninguna excepción.','The alert no longer exists. Keep the pending copy text; no exception was recorded.','O alerta não existe mais. Guarde o texto da cópia pendente; nenhuma exceção foi registrada.'));
  inspector.activeDialog?.close();
  const attachments=[];
  const {d,body}=dialog(w('Inspector de publicación','Publication inspector', "Inspetor de publicação"));
  inspector.activeDialog=d;d.dataset.publicationInspector='';
  d.addEventListener('close',()=>{attachments.forEach(pending=>pending.dispose());if(inspector.activeDialog===d)inspector.activeDialog=null;});
  const initial=key=>origin?.key===key?PendingUI.unpack(origin.data):PendingUI.active.get(slug+'|'+key)?.revision?PendingUI.retained(key)?.data:null;
  const attach=(key,label,read,container)=>{const pending=PendingUI.attach(key,label,()=>({data:read()}),{container,origin:origin?.key===key?origin:null,onDiscard:()=>{d.close();return inspector();}});attachments.push(pending);return pending;};
  body.append(h('p',{},w('Revisa el texto completo y las imágenes que saldrán. Las capturas privadas, los originales y el historial quedan en el proyecto.','Review the full outgoing text and images. Private captures, originals and history stay in the project.', "Revise todo o texto e as imagens de saída. Capturas privadas, originais e histórico permanecem no projeto.")),
    h('p',{class:'hash'},w('Revisión: ','Revision: ', "Revisão: ")+data.revision.slice(0,12)+' / '+data.images.length+' '+w('imágenes','images', "imagens")+' / '+data.private_captures+' '+w('capturas privadas excluidas','private captures excluded', "capturas privadas excluídas")),
    h('p',{},w('La detección por patrones puede omitir secretos. Una excepción registra tu decisión, no modifica el texto. La censura de texto solo cambia la copia publicada; revisa los comandos resultantes.','Pattern detection can miss secrets. An exception records your decision without editing text. Text redaction changes only the published copy; review resulting commands.', "A detecção por padrões pode não identificar segredos. Uma exceção registra sua decisão sem editar o texto. A ocultação de texto altera somente a cópia publicada; revise os comandos resultantes.")));
  const mutate=async(fn,pending=null)=>{
    if(S.slug!==slug||S.data!==current||projectStore.etag!==revision||projectStore.dirty||projectStore.loading||!d.open)throw Error(w('El proyecto cambió. Vuelve a abrir el inspector.','The project changed. Reopen the inspector.', "O projeto mudou. Reabra o inspetor."));
    const pendingRevision=pending?.handle.revision;
    pending?.setBusy(true);
    try{S.data.publication||={redactions:[],exceptions:[]};fn(S.data.publication);scheduleSave();if(await doSave()){if(pending)await pending.committed(pendingRevision);d.close();await inspector();}}
    finally{pending?.setBusy(false);}
  };
  const alerts=h('section',{},h('h3',{},w('Posibles secretos','Possible secrets', "Possíveis segredos")));
  if(!data.alerts.length)alerts.append(h('p',{},w('Sin coincidencias en los patrones comprobados. Haz también una revisión manual.','No matches in the checked patterns. Review manually as well.', "Nenhuma correspondência nos padrões verificados. Revise manualmente também.")));
  for(const a of data.alerts){
    const key='studio:publication:exception:'+a.id,draft=initial(key),card=h('div',{class:'card','data-publication-alert':a.id});
    const reason=h('input',{value:draft?.reason??a.reason??'',maxlength:4000,'data-publication-reason':'','aria-label':w('Motivo de la excepción','Exception reason', "Motivo da exceção")});
    card.append(h('strong',{},a.kind+' / '+a.preview),h('label',{},w('Justificación si debe publicarse','Reason if it must be published', "Motivo pelo qual deve ser publicado"),reason));
    const pending=attach(key,w('Motivo de excepción pendiente','Pending exception reason','Motivo de exceção pendente'),()=>({kind:'exception',alert_id:a.id,reason:reason.value}),card);
    card.append(button(w('Registrar excepción','Record exception', "Registrar exceção"),()=>{if(!reason.value.trim())throw Error(w('Escribe un motivo.','Enter a reason.', "Informe um motivo."));return mutate(c=>{c.exceptions=(c.exceptions||[]).filter(x=>x.id!==a.id);c.exceptions.push({id:a.id,reason:reason.value});},pending);}));
    alerts.append(card);
  }
  body.append(alerts);
  const redactionKey='studio:publication:redaction',redactionDraft=initial(redactionKey);
  const needle=h('input',{value:redactionDraft?.needle??'',autocomplete:'off',maxlength:2000,'data-publication-needle':'','aria-label':w('Texto literal a censurar','Literal text to redact', "Texto literal a ocultar")}),replacement=h('input',{value:redactionDraft?.replacement??'[REDACTED]',maxlength:4000,'data-publication-replacement':'','aria-label':w('Sustitución','Replacement', "Substituição")});
  const redaction=h('details',redactionDraft?{open:''}:{},h('summary',{},w('Censura de texto para publicar','Text redaction for publication', "Ocultação de texto para publicação")),h('p',{},w('Sustituye todas las coincidencias literales en el contenido publicado. Mínimo cuatro caracteres. No edita los originales.','Replaces all literal matches in published content. At least four characters. Originals are not edited.', "Substitui todas as correspondências literais no conteúdo publicado. No mínimo quatro caracteres. Os originais não são editados.")),h('label',{},w('Texto literal','Literal text', "Texto literal"),needle),h('label',{},w('Sustitución','Replacement', "Substituição"),replacement));
  const redactionPending=attach(redactionKey,w('Censura de texto pendiente','Pending text redaction','Ocultação de texto pendente'),()=>({kind:'redaction',needle:needle.value,replacement:replacement.value}),redaction);
  redaction.append(button(w('Aplicar y volver a inspeccionar','Apply and inspect again', "Aplicar e inspecionar novamente"),()=>{if(needle.value.length<4)throw Error(w('Usa al menos cuatro caracteres.','Use at least four characters.', "Use pelo menos quatro caracteres."));return mutate(c=>{c.redactions||=[];c.redactions.push({needle:needle.value,replacement:replacement.value});},redactionPending);}));
  body.append(redaction);
  const rules=S.data.publication?.redactions||[];
  if(rules.length)body.append(h('details',{},h('summary',{},rules.length+' '+w('censuras registradas','recorded redactions', "ocultações registradas")),...rules.map((rule,index)=>h('div',{class:'card'},h('code',{},rule.needle+' → '+rule.replacement),button(w('Retirar esta censura','Remove this redaction', "Remover esta ocultação"),()=>mutate(c=>c.redactions.splice(index,1)))))));
  body.append(h('details',{open:''},h('summary',{},w('Texto que se publicará','Outgoing text', "Texto de saída")),h('pre',{class:'publication-text',tabindex:0},data.text)));
  const inventory=h('section',{},h('h3',{},w('Imágenes de publicación','Published images', "Imagens publicadas")),h('p',{},w('El OCR opcional usa Tesseract local con datos eng, solo al pulsar el botón de cada imagen. Señala zonas posibles sin mostrar ni guardar el texto reconocido. No censura imágenes ni sustituye la revisión manual.','Optional OCR uses local Tesseract with eng data, only when you press each image button. It flags possible areas without displaying or retaining recognized text. It does not redact images or replace manual review.', "O OCR opcional usa o Tesseract local com os dados eng, somente quando você pressiona o botão de cada imagem. Ele sinaliza possíveis áreas sem exibir nem manter o texto reconhecido. Não oculta dados nas imagens nem substitui a revisão manual.")));
  for(const img of data.images){inventory.append(h('details',{},h('summary',{},img.name+' / '+Math.round(img.bytes/1024)+' KB'),h('img',{src:'/api/projects/'+encodeURIComponent(slug)+'/publication/image?name='+encodeURIComponent(img.name)+'&revision='+encodeURIComponent(data.revision),alt:img.name,loading:'lazy'}),h('p',{},w('Metadatos retirados de la derivada','Metadata removed from derivative', "Metadados removidos da cópia derivada")+(img.metadata.length?': '+img.metadata.join(', '):'')),h('p',{class:'hash'},w('Original privado: ','Private original: ', "Original privado: ")+img.original_sha256),h('p',{class:'hash'},w('Publicado: ','Published: ', "Publicado: ")+img.sha256),PrivacyUI.ocr(img,slug,revision)));}
  body.append(inventory,button(w('Abrir evidencias para censurar una imagen','Open evidence to redact an image', "Abrir evidências para ocultar dados de uma imagem"),()=>{d.close();select('workflow','evidence');}),h('p',{},w('Archivos disponibles: informe.pdf, informe.docx, markdown.zip, informe.html y el registro de verificación. Solo se incluyen los formatos que selecciones.','Available files: informe.pdf, informe.docx, markdown.zip, informe.html and the verification record. Only selected formats are included.', "Arquivos disponíveis: informe.pdf, informe.docx, markdown.zip, informe.html e o registro de verificação. Somente os formatos selecionados são incluídos.")));
}
PendingUI.register('studio:publication:',{
  async validate(row){
    const form=PendingUI.unpack(row.data),exception=form?.kind==='exception'&&row.key==='studio:publication:exception:'+form.alert_id&&typeof form.alert_id==='string'&&typeof form.reason==='string'&&form.reason.length<=4000;
    const redaction=form?.kind==='redaction'&&row.key==='studio:publication:redaction'&&typeof form.needle==='string'&&form.needle.length<=2000&&typeof form.replacement==='string'&&form.replacement.length<=4000;
    if(!exception&&!redaction)throw Error(w('Formulario de publicación incompatible. Conserva el contenido mostrado.','Incompatible publication form. Keep the displayed content.','Formulário de publicação incompatível. Guarde o conteúdo exibido.'));
    if(row.slug!==S.slug||projectStore.dirty||projectStore.loading)throw Error(w('El proyecto cambió. Vuelve a abrir la recuperación.','The project changed. Reopen recovery.','O projeto mudou. Reabra a recuperação.'));
    const slug=S.slug,current=S.data,revision=projectStore.etag;
    if(exception){const inspection=await api.get('/api/projects/'+encodeURIComponent(slug)+'/publication');
      if(S.slug!==slug||S.data!==current||projectStore.etag!==revision||projectStore.dirty||projectStore.loading)throw Error(w('El proyecto cambió. Vuelve a abrir la recuperación.','The project changed. Reopen recovery.','O projeto mudou. Reabra a recuperação.'));
      if(!inspection.alerts.some(alert=>alert.id===form.alert_id))throw Error(w('La alerta ya no existe. Conserva el texto de la copia pendiente; no se registró ninguna excepción.','The alert no longer exists. Keep the pending copy text; no exception was recorded.','O alerta não existe mais. Guarde o texto da cópia pendente; nenhuma exceção foi registrada.'));
    }
  },
  restore:row=>inspector(row)
});
function render(el,kind){
  if(kind==='deliver'){
    DeliveryFlowUI.render(el);
  }else{
    el.append(h('div',{class:'studio-stage'},h('h1',{},w('Tu biblioteca de trabajo','Your working library', "Sua biblioteca de trabalho")),h('p',{},w('La apariencia se aplica sin sustituir los hallazgos que ya escribiste.','Apply an appearance without replacing findings you have written.', "Aplique uma aparência sem substituir os achados que escreveu.")),
      h('section',{class:'card'},h('h2',{},w('Diseño del informe','Report design', "Modelo de relatório")),h('p',{},w('Empieza con Serio y compara páginas equivalentes de los seis diseños generales. El catálogo completo conserva los perfiles especializados y tus plantillas personales.','Start with Serious and compare equivalent pages from the six general designs. The full catalog keeps specialized profiles and your personal designs available.', "Comece com Serious e compare páginas equivalentes dos seis modelos gerais. O catálogo completo mantém disponíveis os perfis especializados e seus modelos pessoais.")),button(w('Explorar galería','Explore gallery', "Explorar galeria"),opener=>DesignLibraryUI.gallery(opener),true)),
      h('section',{class:'card'},h('h2',{},w('Hallazgos reutilizables','Reusable findings', "Achados reutilizáveis")),h('p',{},w('Variables y pasos editables. Cada nueva instancia comienza sin verificar.','Editable variables and steps. Each new instance starts unverified.', "Variáveis e etapas editáveis. Cada nova instância começa como não verificada.")),button(w('Abrir biblioteca de hallazgos','Open findings library', "Abrir biblioteca de achados"),()=>{if(!S.slug)throw Error(w('Abre un proyecto primero.','Open a project first.', "Abra um projeto primeiro."));WorkflowUI.openLibrary();}))));
  }
}
function bind(){
  const top=$('.workspace-topline'),toolbar=$('.workspace-toolbar');
  const prefs=h('details',{id:'studioPreferences'},h('summary',{},w('Preferencias','Preferences', "Preferências")),$('.workspace-preferences'));const more=h('details',{id:'studioMore'},h('summary',{},w('Más','More', "Mais"))),panel=h('div',{class:'studio-more-body'});
  for(const id of ['newProjectBtn','projectActions','exportMenu','deliverySlot','exportIndicator']){const node=$('#'+id);if(node)panel.append(node);}
  panel.append(prefs,$('#workspaceContext'));more.append(panel);top.append(more);
  const search=$('.search-wrap'),media=window.matchMedia('(max-width:760px)');
  function placeSearch(){if(media.matches)panel.prepend(search);else top.insertBefore(search,more);}
  media.addEventListener?.('change',placeSearch);placeSearch();
  const nav=h('nav',{class:'studio-nav','aria-label':w('Flujo del informe','Report workflow', "Fluxo do relatório")});
  for(const key of ['work','review','deliver','library']){const b=button('',()=>{more.open=false;if(key==='work')select('home');else if(key==='review')select('workflow','review');else select('studio',key);$('#editor').focus({preventScroll:true});});b.dataset.studioNav=key;nav.append(b);}
  toolbar.replaceChildren($('#sidebarToggle'),nav,$('#saveState'));$('#saveState').after(h('span',{id:'draftStatus',role:'status'}));
  const emergency=button('',()=>downloadDraft());emergency.id='draftExportBtn';panel.append(emergency);
  const legacy=button('',legacyCopies);legacy.dataset.legacyCopies='';panel.append(legacy);
  const file=h('input',{type:'file',accept:'.json','aria-label':w('Archivo de borrador','Draft file', "Arquivo de rascunho")});file.addEventListener('change',async()=>{try{const f=file.files[0];if(!f)return;if(f.size>24*1024*1024)throw Error(w('Borrador demasiado grande.','Draft too large.', "Rascunho muito grande."));const record=JSON.parse(await f.text());if(record.format!=='report-gen-draft'||record.version!==1||record.slug!==S.slug)throw Error(w('Abre el proyecto correspondiente; el borrador debe ser de formato 1.','Open the matching project; draft format must be 1.', "Abra o projeto correspondente; o formato do rascunho deve ser 1."));await resolveDraft(record);}catch(e){toast(e.message,'err');}finally{file.value='';}});panel.append(h('label',{},h('span',{id:'draftImportLabel'}),file));
  const inspectButton=button(w('Inspector de publicación','Publication inspector', "Inspetor de publicação"),inspector);inspectButton.id='publicationBtn';$('#exportMenu .action-menu-body').append(inspectButton);
  document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!document.querySelector('dialog[open]')){more.open=false;}});
  bound=true;update();
}
return{bind,update,render,recovery,resolveDraft,saveHelp,inspector,downloadDraft,legacyCopies};
})();
