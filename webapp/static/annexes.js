/* Revision-bound inventory. Scan results are advisory and never contain secrets. */
const AnnexUI=(()=>{
 const w=(es,en)=>S.uiLang==='en'?en:es;
 const size=bytes=>bytes<1024?bytes+' bytes':(bytes/1024).toFixed(1)+' KiB';
 function button(label,action,onerror=e=>toast(e.message,'err')){const b=h('button',{class:'btn',type:'button'},label);b.addEventListener('click',async()=>{b.disabled=true;try{await action();}catch(e){onerror(e);}finally{if(b.isConnected)b.disabled=false;}});return b;}
 function card(){return h('section',{class:'card annex-stage'},h('h2',{},w('2. Comprobar anexos','2. Check annexes')),h('p',{},w('Selecciona las copias revisadas. Los anexos obligatorios pendientes bloquean la entrega.','Select reviewed copies. Missing required annexes block delivery.')),button(w('Inventario de anexos','Annex inventory'),open));}
 async function open(){
  if(!S.slug||!await doSave())return;const slug=S.slug,revision=projectStore.etag;
  const result=await api.get('/api/projects/'+encodeURIComponent(slug)+'/attachments');if(S.slug!==slug||projectStore.etag!==revision)return;
  const previous=document.activeElement,d=h('dialog',{class:'experience-dialog annex-dialog','aria-label':w('Inventario de anexos','Annex inventory')}),body=h('div',{class:'experience-body'});
  d.append(h('div',{class:'experience-heading'},h('h2',{},w('Inventario de anexos','Annex inventory')),button(w('Cerrar','Close'),()=>d.close())),body);
  d.addEventListener('close',()=>{d.remove();(previous?.isConnected?previous:$('#editor')).focus();});
  const stale=()=>{if(S.slug!==slug||projectStore.etag!==revision||projectStore.dirty)throw Error(w('El proyecto cambió. Vuelve a abrir el inventario.','The project changed. Reopen the inventory.'));};
  const reopen=async()=>{d.close();await open();};
  const notice=h('p',{role:'alert',class:'wf-error annex-error'}),fail=e=>{notice.textContent=e.message;};
  const action=(label,fn)=>button(label,async()=>{notice.textContent='';await fn();},fail);
  body.append(h('p',{},w('Solo el paquete de entrega incluye anexos. Las descargas individuales contienen únicamente el informe.','Only the delivery package includes annexes. Individual downloads contain the report alone.')),
   h('p',{class:'annex-caution'},w('Los anexos se copian sin cambios: no se les aplica censura ni eliminación de metadatos. Carga copias redactadas y revísalas antes de incluirlas.','Annexes are copied unchanged: no redaction or metadata removal is applied. Upload redacted copies and review them before inclusion.')));
  const upload=h('input',{type:'file',accept:'.txt,.json,.csv,.md,.pdf,.png,.jpg,.jpeg,.webp','aria-label':w('Cargar anexo','Upload annex')});
  upload.addEventListener('change',async()=>{notice.textContent='';try{stale();const file=upload.files[0];if(!file)return;if(file.size>16*1024*1024)throw Error(w('Máximo 16 MiB por anexo.','Maximum 16 MiB per annex.'));
    upload.disabled=true;busyProject(true);const form=new FormData();form.append('file',file);
    await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/attachments/upload',{method:'POST',headers:{'If-Match':revision},body:form}));
    await loadProject(slug);await reopen();
   }catch(e){fail(e);upload.disabled=false;upload.value='';}finally{busyProject(false);}});
  body.append(h('label',{},w('Cargar copia revisada (16 MiB por archivo; 64 MiB total)','Upload reviewed copy (16 MiB per file; 64 MiB total)'),upload),notice);
  const name=h('input',{maxlength:120,placeholder:'evidencia-redactada.json','aria-label':w('Nombre del anexo previsto','Expected annex filename')});
  const required=h('input',{type:'checkbox','data-annex-declare-required':''});
  name.addEventListener('input',()=>{notice.textContent='';name.removeAttribute('aria-invalid');});
  body.append(h('details',{},h('summary',{},w('Declarar un anexo todavía pendiente','Declare an annex not ready yet')),h('label',{},w('Nombre con extensión','Filename with extension'),name),
   h('label',{class:'wf-check'},required,w('Obligatorio para entregar','Required for delivery')),
   action(w('Agregar al inventario','Add to inventory'),async()=>{stale();if(!name.value.trim()){name.setAttribute('aria-invalid','true');throw Error(w('Escribe un nombre.','Enter a filename.'));}busyProject(true);try{await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/attachments/declare',{method:'POST',headers:{'Content-Type':'application/json','If-Match':revision},body:JSON.stringify({name:name.value.trim(),required:required.checked})}));await loadProject(slug);await reopen();}catch(e){name.setAttribute('aria-invalid','true');throw e;}finally{busyProject(false);}})));
  const statuses={declared:['Pendiente de cargar','Awaiting upload'],missing:['Archivo ausente o alterado','File missing or changed'],excluded:['Solo en el proyecto','Project only'],included:['Se incluirá en el paquete','Included in package']};
  if(!result.files.length)body.append(h('p',{class:'annex-empty'},w('No has declarado anexos. Si el informe menciona archivos adicionales, agrégalos aquí.','No annexes declared. Add any additional files mentioned in the report here.')));
  result.files.forEach(item=>{const row=S.data.attachments.find(x=>x.uid===item.uid),section=h('section',{class:'card annex-item','data-annex':item.uid},h('h3',{},item.name),h('p',{class:'annex-status'},w(...statuses[item.status])));
   if(item.bytes)section.append(h('small',{class:'annex-size'},size(item.bytes)),h('p',{class:'hash'},'SHA-256: '+item.sha256));
   if(item.error)section.append(h('p',{class:'wf-error'},item.error));
   const include=h('input',{type:'checkbox',class:'annex-include',checked:item.include?'':null,disabled:['declared','missing'].includes(item.status)?'':null});
   const must=h('input',{type:'checkbox',class:'annex-required',checked:item.required?'':null});
   const change=async(fn)=>{notice.textContent='';try{stale();fn();scheduleSave();if(await doSave())await reopen();else throw Error(w('No se guardó el cambio; reintenta desde el indicador de guardado.','Change not saved; retry from the save indicator.'));}catch(e){fail(e);}};
   include.addEventListener('change',()=>change(()=>{row.include=include.checked;row.reviewed=include.checked;}));
   must.addEventListener('change',()=>change(()=>{row.required=must.checked;}));
   section.append(h('label',{class:'wf-check'},include,w('Revisado y autorizado para incluir en la entrega','Reviewed and approved for inclusion in the delivery')),
    h('label',{class:'wf-check'},must,w('Obligatorio para entregar','Required for delivery')));
   if(item.bytes){const report=h('div',{class:'annex-scan',role:'status'});section.append(action(w('Analizar posibles secretos','Check for possible secrets'),async()=>{
    stale();const scan=await api.get('/api/projects/'+encodeURIComponent(slug)+'/attachments/scan?uid='+encodeURIComponent(item.uid));stale();if(!d.isConnected)return;
    if(scan.sha256!==item.sha256)throw Error(w('El archivo cambió. Vuelve a abrir el inventario.','The file changed. Reopen the inventory.'));
    report.replaceChildren();const scopes={utf8_patterns:['Patrones en texto UTF-8','Patterns in UTF-8 text'],image_metadata:['Solo metadatos de imagen; sin OCR','Image metadata only; no OCR'],manual:['Este tipo requiere revisión manual; no fue analizado','This type requires manual review; it was not scanned']};
    report.append(h('p',{},w(...scopes[scan.scope])+' · '+size(scan.bytes_inspected)+' / '+size(scan.bytes)),h('p',{},w('El análisis no cambia el archivo y no certifica ausencia de secretos.','Scanning does not change the file or certify absence of secrets.')));
    if(scan.scope==='utf8_patterns'&&!scan.complete)report.append(h('p',{class:'wf-error'},w('Análisis parcial: solo el primer MiB. Revisa el resto.','Partial scan: first MiB only. Review the rest.')));
    const labels={private_key:['Clave privada','Private key'],credential:['Posible credencial','Possible credential'],bearer:['Token Bearer','Bearer token'],aws_key:['Posible clave AWS','Possible AWS key'],possible_email:['Posible correo','Possible email'],possible_rut:['Posible RUT','Possible RUT'],image_metadata:['Entradas de metadatos','Metadata entries']};
    for(const alert of scan.alerts)report.append(h('p',{class:'wf-error'},w(...labels[alert.kind])+': '+alert.count));
    if(!scan.alerts.length&&scan.scope!=='manual')report.append(h('p',{},w('Sin coincidencias en el alcance analizado.','No matches within the scanned scope.')));
   }),report);}
   section.append(action(w('Retirar del inventario','Remove from inventory'),async()=>{stale();UndoUI.remove(S.data.attachments,S.data.attachments.indexOf(row));scheduleSave();if(await doSave())await reopen();}));body.append(section);
  });
  body.append(h('p',{class:'wf-hint'},w('Retirar del inventario no borra la copia privada ni las versiones. El respaldo editable conserva los archivos del proyecto.','Removing an inventory entry does not delete the private copy or history. Editable backups retain project files.')));
  document.body.append(d);d.showModal();
 }
 return {open,card,size};
})();
