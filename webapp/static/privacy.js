/* Private retention overview; deletions require a fresh revision and an explicit choice. */
const PrivacyUI=(()=>{
 const w=(es,en)=>S.uiLang==='en'?en:es;
 const names={document:['Datos actuales del proyecto','Current project data'],images:['Imágenes de trabajo','Working images'],originals:['Imágenes originales privadas','Private original images'],annexes:['Anexos registrados','Registered annexes'],unused_annexes:['Anexos retirados del inventario','Annexes removed from inventory'],history:['Historial y objetos de versiones','History and version objects'],legacy_backup:['Respaldo YAML anterior','Legacy YAML backup'],other:['Otros archivos del proyecto','Other project files']};
 async function open(){
  if(!S.slug)return;const slug=S.slug,etag=projectStore.etag;
  const data=await api.get('/api/projects/'+encodeURIComponent(slug)+'/privacy');if(S.slug!==slug)return;
  const previous=document.activeElement,d=h('dialog',{class:'experience-dialog privacy-dialog','aria-label':w('Datos privados guardados','Stored private data')}),body=h('div',{class:'experience-body'}),notice=h('p',{role:'alert',class:'wf-error'});
  const button=(label,fn)=>{const b=h('button',{class:'btn',type:'button'},label);b.addEventListener('click',async()=>{b.disabled=true;notice.textContent='';try{await fn();}catch(e){notice.textContent=e.message;}finally{if(b.isConnected)b.disabled=false;}});return b;};
  d.append(h('div',{class:'experience-heading'},h('h2',{},w('Datos privados guardados','Stored private data')),button(w('Cerrar','Close'),()=>d.close())),body);
  d.addEventListener('close',()=>{d.remove();(previous?.isConnected?previous:$('#editor')).focus();});
  body.append(h('p',{},w('Esta vista corresponde al proyecto guardado. Los archivos privados pueden conservar datos que ya censuraste en el informe publicado.','This view describes the saved project. Private files may retain data already redacted in the published report.')),h('p',{class:'hash privacy-location'},data.root),notice);
  const checks=[];
  for(const group of data.categories){
   const section=h('section',{class:'card privacy-category','data-privacy-category':group.key},h('h3',{},w(...names[group.key])),h('p',{},group.count+' '+(group.count===1?w('archivo','file'):w('archivos','files'))+' · '+AnnexUI.size(group.bytes)));
   if(group.key==='history')section.append(h('p',{},data.versions+' '+w('versiones; pueden incluir originales y anexos retirados.','versions; may include originals and removed annexes.')));
   if(group.files.length)section.append(h('details',{},h('summary',{},w('Ver rutas guardadas','Show stored paths')),h('ul',{class:'privacy-files'},...group.files.map(file=>h('li',{},file.name+' · '+AnnexUI.size(file.bytes)))),...(group.truncated?[h('p',{},w('Se muestran los primeros 100 archivos.','Showing the first 100 files.'))]:[])));
   if(group.can_prune&&group.count){const input=h('input',{type:'checkbox','data-prune':group.key});checks.push(input);section.append(h('label',{class:'wf-check'},input,w('Seleccionar para limpiar','Select for cleanup')));}
   body.append(section);
  }
  body.append(h('h3',{},w('Borradores en este navegador','Drafts in this browser')),h('p',{},w('Se guardan sin cifrado de la aplicación durante 30 días, separados por espacio de trabajo, perfil del navegador, host y puerto. Otras pestañas del mismo espacio pueden volver a guardarlos. Las copias anteriores sin identidad se conservan en Más → Copias anteriores sin asignación.','Stored without application encryption for 30 days, separated by workspace, browser profile, host and port. Other tabs of the same workspace may save them again. Earlier unidentified copies are retained under More → Unassigned legacy copies.')));
  const draftBox=h('div',{class:'privacy-drafts'});body.append(draftBox);
  try{const rows=await projectStore.journal?.list(slug)||[];
   if(!rows.length)draftBox.append(h('p',{},w('No hay borradores recuperables para este proyecto en este origen.','No recoverable drafts for this project at this origin.')));
   for(const row of rows){const section=h('section',{class:'card privacy-draft'},h('p',{},new Date(row.updated).toLocaleString()));
    section.append(button(w('Descargar borrador privado','Download private draft'),()=>StudioUI.downloadDraft(row)),button(w('Eliminar este borrador','Delete this draft'),async()=>{
     if(!confirm(w('¿Eliminar esta copia privada del navegador? No elimina el proyecto guardado ni otras copias.','Delete this private browser copy? The saved project and other copies are not deleted.')))return;
     if(!await projectStore.journal.removeUnchanged(row))throw Error(w('El borrador cambió. Vuelve a abrir esta vista.','The draft changed. Reopen this view.'));
     if(row.id===projectStore.journal.id+':'+slug){projectStore.recoverableRevision=0;projectStore.draftError=Error('Borrador eliminado / Draft removed');StudioUI.update();}
     projectStore.recovery=projectStore.recovery.filter(x=>x.id!==row.id);section.remove();
    }));draftBox.append(section);}
  }catch(e){draftBox.append(h('p',{class:'wf-error'},e.message));}
  if(typeof PendingUI!=='undefined'){
   const pendingBox=h('section',{},h('h3',{},w('Capturas y formularios pendientes','Pending captures and forms')));
   body.append(pendingBox);
   try{const rows=await PendingUI.list(slug);if(!rows.length)pendingBox.append(h('p',{},w('No hay copias pendientes recuperables en este navegador.','No recoverable pending copies in this browser.')));
    for(const row of rows){const section=PendingUI.recoverySection(row);pendingBox.append(section);d.addEventListener('close',()=>section.release?.(),{once:true});}
   }catch(error){pendingBox.append(h('p',{class:'wf-error'},error.message));}
  }
  body.append(h('h3',{},w('Copias fuera de este proyecto','Copies outside this project')),h('p',{},w('Los respaldos y las descargas que guardaste fuera de la herramienta no se pueden inventariar ni borrar desde aquí. Las exportaciones temporales se gestionan en Exportaciones y descargas.','Backups and downloads saved outside the tool cannot be inventoried or deleted here. Temporary exports are managed under Exports and downloads.')),
   button(w('Ver exportaciones temporales','View temporary exports'),()=>{d.close();return ProgressUI.jobs();}),button(w('Abrir inventario de anexos','Open annex inventory'),()=>{d.close();return AnnexUI.open();}),button(w('Gestionar evidencias','Manage evidence'),()=>{d.close();select('workflow','evidence');}),button(w('Preparar respaldo integral privado','Prepare private workspace backup'),()=>{d.close();return WorkspaceUI.backup();}));
  const confirmName=h('input',{'aria-label':w('Identificador del proyecto para limpiar','Project ID for cleanup'),autocomplete:'off'});
  body.append(h('h3',{},w('Limpiar las categorías seleccionadas','Clean selected categories')),h('p',{},w('La limpieza es irreversible desde la aplicación. No borra datos actuales, imágenes originales, borradores del navegador ni respaldos externos. Al limpiar el historial se conserva una nueva versión del estado actual; ese estado puede seguir conteniendo datos privados.','Cleanup cannot be undone in the app. Current data, original images, browser drafts and external backups are retained. Cleaning history keeps a new snapshot of the current state, which may still contain private data.')),
   h('label',{},w('Escribe el identificador: ','Type project ID: ')+slug,confirmName),button(w('Limpiar lo seleccionado','Clean selected categories'),async()=>{
    if(S.slug!==slug||projectStore.etag!==etag||projectStore.dirty||projectStore.loading)throw Error(w('Guarda o resuelve los cambios y vuelve a abrir esta vista.','Save or resolve changes and reopen this view.'));
    const categories=checks.filter(x=>x.checked).map(x=>x.dataset.prune);
    if(!categories.length||confirmName.value!==slug)throw Error(w('Selecciona categorías y escribe el identificador exacto del proyecto.','Select categories and type the exact project ID.'));
    busyProject(true);try{await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/privacy/prune',{method:'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify({categories,inventory_revision:data.inventory_revision,confirm_project:slug})}));d.close();await open();}finally{busyProject(false);}
   }));
  if(S.slug!==slug)return;document.body.append(d);d.showModal();
 }
 function ocr(image,slug,etag){
  const status=h('div',{role:'status','data-ocr-result':''}),control=h('button',{type:'button',class:'btn','data-ocr-image':image.name},w('Revisar esta imagen con OCR local','Inspect this image with local OCR'));
  const labels={private_key:['Clave privada','Private key'],credential:['Posible credencial','Possible credential'],bearer:['Token de autorización','Authorization token'],aws_key:['Posible clave AWS','Possible AWS key'],possible_email:['Posible correo electrónico','Possible email address'],possible_rut:['Posible RUT','Possible Chilean ID']};
  const states={unavailable:['OCR no disponible. Instala Tesseract y los datos eng en este equipo.','OCR unavailable. Install Tesseract and eng data on this computer.'],engine_error:['El motor OCR no pudo revisar la imagen. Comprueba Tesseract y sus datos eng; revisa la imagen manualmente.','OCR could not inspect the image. Check Tesseract and its eng data; review the image manually.'],timeout:['OCR alcanzó el límite de tiempo. La imagen requiere revisión manual.','OCR reached its time limit. Review this image manually.'],image_limit:['OCR admite imágenes de hasta 12 megapíxeles. Revisa esta imagen manualmente.','OCR supports images up to 12 megapixels. Review this image manually.'],animation_unsupported:['OCR no revisa animaciones. Revisa todos sus fotogramas manualmente.','OCR does not inspect animations. Review every frame manually.'],output_limit:['OCR superó su límite de salida. La revisión quedó incompleta.','OCR exceeded its output limit. Inspection is incomplete.']};
  control.addEventListener('click',async()=>{
   control.disabled=true;status.replaceChildren(h('p',{},w('Revisando localmente…','Inspecting locally…')));
   try{
    if(S.slug!==slug||projectStore.etag!==etag||projectStore.dirty)throw Error(w('El proyecto cambió. Vuelve a abrir el inspector.','The project changed. Reopen the inspector.'));
    const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/privacy/ocr',{method:'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify({name:image.name})}));
    const result=await response.json();
    if(S.slug!==slug||projectStore.etag!==etag||projectStore.dirty||(result.status==='completed'&&result.image_sha256!==image.sha256))throw Error(w('La imagen o el proyecto cambió. Vuelve a abrir el inspector.','The image or project changed. Reopen the inspector.'));
    status.replaceChildren();
    if(result.status!=='completed'){status.append(h('p',{},w(...(states[result.status]||states.engine_error))));return;}
    status.append(h('p',{},w('OCR ejecutado con Tesseract (eng). Palabras reconocidas: ','OCR ran using Tesseract (eng). Recognized words: ')+result.words_recognized+'. '+w('Puede omitir texto y datos sensibles. Revisa visualmente la imagen.','It may miss text and sensitive data. Inspect the image visually.')));
    if(!result.alerts.length)status.append(h('p',{},result.words_recognized?w('Sin coincidencias en los patrones comprobados; no certifica ausencia de secretos.','No matches in the checked patterns; this does not certify absence of secrets.'):w('No se reconoció texto. No se puede concluir que la imagen no contenga datos sensibles.','No text recognized. This does not establish that the image has no sensitive data.')));
    else status.append(h('ul',{},...result.alerts.map(alert=>h('li',{},w(...(labels[alert.kind]||['Dato sensible posible','Possible sensitive data']))+' × '+alert.count+' · '+w('zona x, y, ancho, alto (píxeles): ','area x, y, width, height (pixels): ')+alert.bounds.join(', ')))));
   }catch(error){status.replaceChildren(h('p',{class:'wf-error'},error.message));}finally{if(control.isConnected)control.disabled=false;}
  });
  return h('div',{class:'privacy-ocr'},control,status);
 }
 return {open,ocr};
})();
