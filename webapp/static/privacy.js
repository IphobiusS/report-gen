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
  body.append(h('h3',{},w('Borradores en este navegador','Drafts in this browser')),h('p',{},w('Se guardan sin cifrado de la aplicación durante 30 días, para este perfil, host y puerto. Otras pestañas abiertas pueden volver a guardar sus borradores.','Stored without application encryption for 30 days, in this browser profile, host and port. Other open tabs can save their drafts again.')));
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
 return {open};
})();
