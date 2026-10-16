/* Native DOCX pagination is a disposable derivative of one immutable export job. */
const DocxPreviewUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const safeId=value=>typeof value==='string'&&/^[a-zA-Z0-9_-]{1,100}$/.test(value);
  let active=null;
  function open(job,trigger=document.activeElement){
    if(active?.isConnected){active.querySelector('button')?.focus();return;}
    if(!safeId(job?.id)||job.stage!=='done')return;
    let closed=false,id=null,timer=null,controller=null,pending=false,polling=false,cancelRequested=false;
    const urls=new Set();
    const title=w('Vista DOCX con LibreOffice','DOCX preview with LibreOffice','Visualização DOCX com LibreOffice');
    const dialog=h('dialog',{class:'experience-dialog docx-preview-dialog','aria-label':title,'data-docx-preview':''});
    active=dialog;
    const status=h('p',{role:'status','aria-live':'polite','data-docx-preview-status':''});
    const error=h('p',{class:'wf-error',role:'alert','data-docx-preview-error':''});
    const output=h('section',{'data-docx-preview-output':'',hidden:''});
    const run=h('button',{type:'button',class:'btn primary','data-docx-preview-run':'',disabled:''},w('Generar vista nativa','Generate native preview','Gerar visualização nativa'));
    const cancel=h('button',{type:'button',class:'btn','data-docx-preview-cancel':'',hidden:''},w('Cancelar conversión','Cancel conversion','Cancelar conversão'));
    const close=h('button',{type:'button',class:'btn',onclick:()=>dialog.close()},w('Cerrar','Close','Fechar'));
    const body=h('div',{class:'experience-body'},
      h('p',{},w('LibreOffice calcula las páginas a partir del DOCX de esta exportación guardada. El informe y el proyecto permanecen intactos.','LibreOffice calculates pages from this saved export’s DOCX. The report and project remain intact.','O LibreOffice calcula as páginas a partir do DOCX desta exportação salva. O relatório e o projeto permanecem intactos.')),
      h('p',{class:'wf-hint'},w('Esta vista refleja LibreOffice. Microsoft Word puede distribuir las páginas de forma diferente y requiere su propia comprobación.','This preview reflects LibreOffice. Microsoft Word may paginate differently and requires its own validation.','Esta visualização reflete o LibreOffice. O Microsoft Word pode paginar de forma diferente e exige sua própria verificação.')),
      h('p',{class:'wf-hint'},w('Conversión local y opcional: hasta 16 MiB de DOCX, 500 páginas y 180 segundos. Al cerrar se cancela la conversión y se solicita eliminar la vista temporal; si se pierde la conexión, caduca tras 15 minutos al siguiente acceso o al cerrar el servidor.','Optional local conversion: up to 16 MiB DOCX, 500 pages and 180 seconds. Closing cancels conversion and requests removal of the temporary preview; if connection is lost, it expires after 15 minutes on the next access or server shutdown.','Conversão local e opcional: até 16 MiB de DOCX, 500 páginas e 180 segundos. Ao fechar, a conversão é cancelada e a remoção da visualização temporária é solicitada; se a conexão cair, ela expira após 15 minutos no próximo acesso ou ao fechar o servidor.')),
      h('div',{class:'docx-preview-actions'},run,cancel),status,error,output);
    dialog.append(h('div',{class:'experience-heading'},h('h2',{},title),close),body);
    const options=method=>({method,headers:{'Content-Type':'application/json'},body:'{}'});
    const path=()=>'/api/docx-preview/'+encodeURIComponent(id);
    async function json(url,opts){const response=await requireOk(await appFetch(url,opts));return response.json();}
    function clearOutput(){output.replaceChildren();output.hidden=true;for(const url of urls)URL.revokeObjectURL(url);urls.clear();}
    function busy(value){pending=value;run.disabled=value;cancel.hidden=!value;dialog.setAttribute('aria-busy',String(value));}
    async function release(key){
      if(!safeId(key))return;
      const url='/api/docx-preview/'+encodeURIComponent(key);
      try{let row=await json(url+'/cancel',options('POST'));for(let count=0;['rendering','cancelling'].includes(row.stage)&&count<50;count++){await new Promise(resolve=>setTimeout(resolve,200));row=await json(url);}if(!['rendering','cancelling'].includes(row.stage))await json(url,options('DELETE'));}catch(_error){/* TTL/server shutdown remain the documented fallback. */}
    }
    async function done(row){
      const r=row.receipt;if(!r||r.source_docx_sha256!==row.source_docx_sha256||r.source_revision!==row.revision||r.word_verified!==false)throw Error(w('Recibo de vista DOCX no válido.','Invalid DOCX preview receipt.','Recibo de visualização DOCX inválido.'));
      controller=new AbortController();
      const response=await requireOk(await appFetch(path()+'/pdf',{signal:controller.signal}));
      if(!/application\/pdf/i.test(response.headers.get('Content-Type')||''))throw Error(w('La vista recibida no es PDF.','The preview received is not PDF.','A visualização recebida não é PDF.'));
      const blob=await response.blob();if(closed)return;
      if(!blob.size||blob.size>32*1024*1024)throw Error(w('Vista PDF vacía o demasiado grande.','PDF preview is empty or too large.','Visualização PDF vazia ou muito grande.'));
      const url=URL.createObjectURL(blob);urls.add(url);
      const receipt=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'}));urls.add(receipt);
      output.append(h('p',{'data-docx-preview-engine':''},r.engine.version+' · '+r.pages+' '+w('páginas','pages','páginas')),
        h('p',{class:'docx-preview-hash'},'DOCX SHA-256: '+r.source_docx_sha256),
        h('p',{class:'docx-preview-hash'},w('Revisión: ','Revision: ','Revisão: ')+r.source_revision),
        h('p',{class:'docx-preview-hash'},'PDF SHA-256: '+r.pdf_sha256),
        h('div',{class:'docx-preview-actions'},h('a',{class:'btn',href:url,download:'docx-libreoffice-preview.pdf'},w('Descargar PDF derivado','Download derived PDF','Baixar PDF derivado')),h('a',{class:'btn',href:receipt,download:'docx-libreoffice-preview.json'},w('Descargar recibo','Download receipt','Baixar recibo'))),
        h('iframe',{class:'docx-preview-frame',src:url,title:w('PDF derivado del DOCX','PDF derived from DOCX','PDF derivado do DOCX'),referrerpolicy:'no-referrer','data-docx-preview-frame':''}));
      output.hidden=false;status.textContent=w('Vista lista. Revisa su paginación antes de compartir el DOCX.','Preview ready. Review its pagination before sharing the DOCX.','Visualização pronta. Revise a paginação antes de compartilhar o DOCX.');
    }
    async function poll(){
      clearTimeout(timer);if(closed||!id||polling)return;polling=true;
      try{const row=await json(path());if(closed)return;
        if(row.stage==='done'){cancel.hidden=true;await done(row);if(!closed)busy(false);return;}
        if(row.stage==='error'){busy(false);error.textContent=row.error;status.textContent='';return;}
        if(row.stage==='cancelled'){busy(false);status.textContent=w('Conversión cancelada; archivos temporales eliminados.','Conversion cancelled; temporary files removed.','Conversão cancelada; arquivos temporários removidos.');return;}
        status.textContent=row.stage==='cancelling'?w('Cancelando y limpiando…','Cancelling and cleaning up…','Cancelando e limpando…'):w('LibreOffice está calculando la paginación…','LibreOffice is calculating pagination…','O LibreOffice está calculando a paginação…');
        timer=setTimeout(poll,500);
      }catch(e){if(!closed){busy(false);error.textContent=e.message;}}
      finally{polling=false;}
    }
    run.addEventListener('click',async()=>{
      if(pending)return;cancelRequested=false;cancel.disabled=false;busy(true);error.textContent='';clearOutput();
      if(id){const old=id;id=null;await release(old);}if(closed)return;
      if(cancelRequested){busy(false);return;}
      try{const row=await json('/api/jobs/'+encodeURIComponent(job.id)+'/docx-preview',options('POST'));
        if(!safeId(row.id))throw Error(w('Identificador de vista inválido.','Invalid preview identifier.','Identificador de visualização inválido.'));
        if(closed){release(row.id);return;}id=row.id;
        if(cancelRequested)await json(path()+'/cancel',options('POST'));
        cancel.disabled=false;poll();
      }catch(e){if(!closed){busy(false);error.textContent=e.message;}}
    });
    cancel.addEventListener('click',async()=>{
      cancelRequested=true;cancel.disabled=true;
      if(!id){status.textContent=w('Cancelación solicitada; esperando el identificador del servidor…','Cancellation requested; waiting for the server identifier…','Cancelamento solicitado; aguardando o identificador do servidor…');return;}
      try{await json(path()+'/cancel',options('POST'));if(!closed)poll();}catch(e){if(!closed)error.textContent=e.message;}finally{cancel.disabled=false;}
    });
    dialog.addEventListener('close',()=>{closed=true;clearTimeout(timer);controller?.abort();clearOutput();if(id)release(id);dialog.remove();if(active===dialog)active=null;if(trigger?.isConnected&&!trigger.disabled)trigger.focus();});
    document.body.append(dialog);dialog.showModal();close.focus();
    json('/api/docx-preview/capabilities').then(c=>{if(!closed){run.disabled=!c.available;status.textContent=c.available?w('LibreOffice disponible. Genera la vista cuando quieras revisar el DOCX.','LibreOffice available. Generate the preview when you want to inspect the DOCX.','LibreOffice disponível. Gere a visualização quando quiser revisar o DOCX.'):c.unavailable_message;}}).catch(e=>{if(!closed)error.textContent=e.message;});
  }
  return {open};
})();
