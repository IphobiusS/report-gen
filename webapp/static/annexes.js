/* Revision-bound inventory. Scan results are advisory and never contain secrets. */
const AnnexUI=(()=>{
 const w=(es,en,pt)=>uiText(es,en,pt);
 const size=bytes=>bytes<1024?bytes+' bytes':(bytes/1024).toFixed(1)+' KiB';
 function button(label,action,onerror=e=>toast(e.message,'err')){const b=h('button',{class:'btn',type:'button'},label);b.addEventListener('click',async()=>{b.disabled=true;try{await action();}catch(e){onerror(e);}finally{if(b.isConnected)b.disabled=false;}});return b;}
 function card(){return h('section',{class:'card annex-stage'},h('h2',{},w('2. Comprobar anexos','2. Check annexes', "2. Verificar anexos")),h('p',{},w('Selecciona las copias revisadas. Los anexos obligatorios pendientes bloquean la entrega.','Select reviewed copies. Missing required annexes block delivery.', "Selecione as cópias revisadas. Anexos obrigatórios ausentes bloqueiam a entrega.")),button(w('Inventario de anexos','Annex inventory', "Inventário de anexos"),open));}
 async function open(){
  if(!S.slug||!await doSave())return;const slug=S.slug,revision=projectStore.etag;
  const result=await api.get('/api/projects/'+encodeURIComponent(slug)+'/attachments');if(S.slug!==slug||projectStore.etag!==revision)return;
  const previous=document.activeElement,d=h('dialog',{class:'experience-dialog annex-dialog','aria-label':w('Inventario de anexos','Annex inventory', "Inventário de anexos")}),body=h('div',{class:'experience-body'});
  d.append(h('div',{class:'experience-heading'},h('h2',{},w('Inventario de anexos','Annex inventory', "Inventário de anexos")),button(w('Cerrar','Close', "Fechar"),()=>d.close())),body);
  d.addEventListener('close',()=>{d.remove();(previous?.isConnected?previous:$('#editor')).focus();});
  const stale=()=>{if(S.slug!==slug||projectStore.etag!==revision||projectStore.dirty)throw Error(w('El proyecto cambió. Vuelve a abrir el inventario.','The project changed. Reopen the inventory.', "O projeto mudou. Reabra o inventário."));};
  const reopen=async()=>{d.close();await open();};
  const notice=h('p',{role:'alert',class:'wf-error annex-error'}),fail=e=>{notice.textContent=e.message;};
  const action=(label,fn)=>button(label,async()=>{notice.textContent='';await fn();},fail);
  body.append(h('p',{},w('Solo el paquete de entrega incluye anexos. Las descargas individuales contienen únicamente el informe.','Only the delivery package includes annexes. Individual downloads contain the report alone.', "Somente o pacote de entrega inclui anexos. Downloads individuais contêm apenas o relatório.")),
   h('p',{class:'annex-caution'},w('Los anexos se copian sin cambios: no se les aplica censura ni eliminación de metadatos. Carga copias redactadas y revísalas antes de incluirlas.','Annexes are copied unchanged: no redaction or metadata removal is applied. Upload redacted copies and review them before inclusion.', "Os anexos são copiados sem alterações: não há ocultação de dados nem remoção de metadados. Envie cópias com os dados ocultados e revise-as antes de incluí-las.")));
  const upload=h('input',{type:'file',accept:'.txt,.json,.csv,.md,.pdf,.png,.jpg,.jpeg,.webp','aria-label':w('Cargar anexo','Upload annex', "Enviar anexo")});
  upload.addEventListener('change',async()=>{notice.textContent='';try{stale();const file=upload.files[0];if(!file)return;if(file.size>16*1024*1024)throw Error(w('Máximo 16 MiB por anexo.','Maximum 16 MiB per annex.', "Máximo de 16 MiB por anexo."));
    upload.disabled=true;busyProject(true);const form=new FormData();form.append('file',file);
    await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/attachments/upload',{method:'POST',headers:{'If-Match':revision},body:form}));
    await loadProject(slug);await reopen();
   }catch(e){fail(e);upload.disabled=false;upload.value='';}finally{busyProject(false);}});
  body.append(h('label',{},w('Cargar copia revisada (16 MiB por archivo; 64 MiB total)','Upload reviewed copy (16 MiB per file; 64 MiB total)', "Enviar cópia revisada (16 MiB por arquivo; 64 MiB no total)"),upload),notice);
  const name=h('input',{maxlength:120,placeholder:w('evidencia-redactada.json','redacted-evidence.json','evidencia-com-dados-ocultados.json'),'aria-label':w('Nombre del anexo previsto','Expected annex filename', "Nome de arquivo esperado do anexo")});
  const required=h('input',{type:'checkbox','data-annex-declare-required':''});
  name.addEventListener('input',()=>{notice.textContent='';name.removeAttribute('aria-invalid');});
  body.append(h('details',{},h('summary',{},w('Declarar un anexo todavía pendiente','Declare an annex not ready yet', "Declarar um anexo ainda não pronto")),h('label',{},w('Nombre con extensión','Filename with extension', "Nome de arquivo com extensão"),name),
   h('label',{class:'wf-check'},required,w('Obligatorio para entregar','Required for delivery', "Obrigatório para a entrega")),
   action(w('Agregar al inventario','Add to inventory', "Adicionar ao inventário"),async()=>{stale();if(!name.value.trim()){name.setAttribute('aria-invalid','true');throw Error(w('Escribe un nombre.','Enter a filename.', "Informe um nome de arquivo."));}busyProject(true);try{await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/attachments/declare',{method:'POST',headers:{'Content-Type':'application/json','If-Match':revision},body:JSON.stringify({name:name.value.trim(),required:required.checked})}));await loadProject(slug);await reopen();}catch(e){name.setAttribute('aria-invalid','true');throw e;}finally{busyProject(false);}})));
  const statuses={declared:['Pendiente de cargar','Awaiting upload', "Aguardando envio"],missing:['Archivo ausente o alterado','File missing or changed', "Arquivo ausente ou alterado"],excluded:['Solo en el proyecto','Project only', "Somente no projeto"],included:['Se incluirá en el paquete','Included in package', "Incluído no pacote"]};
  if(!result.files.length)body.append(h('p',{class:'annex-empty'},w('No has declarado anexos. Si el informe menciona archivos adicionales, agrégalos aquí.','No annexes declared. Add any additional files mentioned in the report here.', "Nenhum anexo declarado. Adicione aqui os arquivos adicionais mencionados no relatório.")));
  result.files.forEach(item=>{const row=S.data.attachments.find(x=>x.uid===item.uid),section=h('section',{class:'card annex-item','data-annex':item.uid},h('h3',{},item.name),h('p',{class:'annex-status'},w(...statuses[item.status])));
   if(item.bytes)section.append(h('small',{class:'annex-size'},size(item.bytes)),h('p',{class:'hash'},'SHA-256: '+item.sha256));
   if(item.error)section.append(h('p',{class:'wf-error'},item.error));
   const include=h('input',{type:'checkbox',class:'annex-include',checked:item.include?'':null,disabled:['declared','missing'].includes(item.status)?'':null});
   const must=h('input',{type:'checkbox',class:'annex-required',checked:item.required?'':null});
   const change=async(fn)=>{notice.textContent='';try{stale();fn();scheduleSave();if(await doSave())await reopen();else throw Error(w('No se guardó el cambio; reintenta desde el indicador de guardado.','Change not saved; retry from the save indicator.', "Alteração não salva; tente novamente pelo indicador de salvamento."));}catch(e){fail(e);}};
   include.addEventListener('change',()=>change(()=>{row.include=include.checked;row.reviewed=include.checked;}));
   must.addEventListener('change',()=>change(()=>{row.required=must.checked;}));
   section.append(h('label',{class:'wf-check'},include,w('Revisado y autorizado para incluir en la entrega','Reviewed and approved for inclusion in the delivery', "Revisado e aprovado para inclusão na entrega")),
    h('label',{class:'wf-check'},must,w('Obligatorio para entregar','Required for delivery', "Obrigatório para a entrega")));
   if(item.bytes){const report=h('div',{class:'annex-scan',role:'status'});section.append(action(w('Analizar posibles secretos','Check for possible secrets', "Verificar possíveis segredos"),async()=>{
    stale();const scan=await api.get('/api/projects/'+encodeURIComponent(slug)+'/attachments/scan?uid='+encodeURIComponent(item.uid));stale();if(!d.isConnected)return;
    if(scan.sha256!==item.sha256)throw Error(w('El archivo cambió. Vuelve a abrir el inventario.','The file changed. Reopen the inventory.', "O arquivo mudou. Reabra o inventário."));
    report.replaceChildren();const scopes={utf8_patterns:['Patrones en texto UTF-8','Patterns in UTF-8 text', "Padrões em texto UTF-8"],image_metadata:['Solo metadatos de imagen; sin OCR','Image metadata only; no OCR', "Somente metadados da imagem; sem OCR"],manual:['Este tipo requiere revisión manual; no fue analizado','This type requires manual review; it was not scanned', "Este tipo requer revisão manual; não foi analisado"]};
    report.append(h('p',{},w(...scopes[scan.scope])+' · '+size(scan.bytes_inspected)+' / '+size(scan.bytes)),h('p',{},w('El análisis no cambia el archivo y no certifica ausencia de secretos.','Scanning does not change the file or certify absence of secrets.', "A verificação não altera o arquivo nem certifica a ausência de segredos.")));
    if(scan.scope==='utf8_patterns'&&!scan.complete)report.append(h('p',{class:'wf-error'},w('Análisis parcial: solo el primer MiB. Revisa el resto.','Partial scan: first MiB only. Review the rest.', "Verificação parcial: somente o primeiro MiB. Revise o restante.")));
    const labels={private_key:['Clave privada','Private key', "Chave privada"],credential:['Posible credencial','Possible credential', "Possível credencial"],bearer:['Token Bearer','Bearer token', "Token Bearer"],aws_key:['Posible clave AWS','Possible AWS key', "Possível chave AWS"],possible_email:['Posible correo','Possible email', "Possível e-mail"],possible_rut:['Posible RUT','Possible RUT', "Possível RUT"],image_metadata:['Entradas de metadatos','Metadata entries', "Entradas de metadados"]};
    for(const alert of scan.alerts)report.append(h('p',{class:'wf-error'},w(...labels[alert.kind])+': '+alert.count));
    if(!scan.alerts.length&&scan.scope!=='manual')report.append(h('p',{},w('Sin coincidencias en el alcance analizado.','No matches within the scanned scope.', "Nenhuma correspondência no escopo verificado.")));
   }),report);}
   section.append(action(w('Retirar del inventario','Remove from inventory', "Remover do inventário"),async()=>{stale();UndoUI.remove(S.data.attachments,S.data.attachments.indexOf(row));scheduleSave();if(await doSave())await reopen();}));body.append(section);
  });
  body.append(h('p',{class:'wf-hint'},w('Retirar del inventario no borra la copia privada ni las versiones. El respaldo editable conserva los archivos del proyecto.','Removing an inventory entry does not delete the private copy or history. Editable backups retain project files.', "Remover uma entrada do inventário não exclui a cópia privada nem o histórico. Backups editáveis preservam os arquivos do projeto.")));
  document.body.append(d);d.showModal();
 }
 return {open,card,size};
})();
