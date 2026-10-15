/* Compare two supplied PDFs without changing the open project. */
const PDFComparisonUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const MAX_PDF_BYTES=16*1024*1024,MAX_OUTPUT_BYTES=32*1024*1024;
  let activeDialog=null;

  function open(trigger=document.activeElement){
    if(activeDialog?.isConnected){activeDialog.querySelector('input')?.focus();return;}
    const title=w('Comparar archivos PDF','Compare PDF files','Comparar arquivos PDF');
    const dialog=h('dialog',{class:'experience-dialog pdf-compare-dialog','aria-label':title,'data-pdf-compare':''});
    activeDialog=dialog;
    let capabilities=null,capabilityController=null,comparisonController=null,generation=0,objectURL=null,closed=false,busy=false;
    const status=h('p',{class:'pdf-compare-status',role:'status','aria-live':'polite','data-pdf-compare-status':''});
    const error=h('p',{class:'wf-error',role:'alert','data-pdf-compare-error':''});
    const output=h('section',{class:'pdf-compare-output','data-pdf-compare-output':'',hidden:''});
    const before=h('input',{type:'file',accept:'.pdf,application/pdf','data-pdf-before':'','aria-label':w('PDF anterior','Earlier PDF','PDF anterior')});
    const after=h('input',{type:'file',accept:'.pdf,application/pdf','data-pdf-after':'','aria-label':w('PDF nuevo','Later PDF','PDF novo')});
    const compare=h('button',{type:'button',class:'btn primary','data-pdf-compare-submit':'',disabled:''},w('Comparar PDF','Compare PDFs','Comparar PDFs'));
    const cancel=h('button',{type:'button',class:'btn','data-pdf-compare-cancel':'',hidden:''},w('Cancelar espera','Stop waiting','Parar de esperar'));
    const retry=h('button',{type:'button',class:'btn',hidden:''},w('Comprobar de nuevo','Check again','Verificar novamente'));
    const close=h('button',{type:'button',class:'btn',onclick:()=>dialog.close()},w('Cerrar','Close','Fechar'));
    const body=h('div',{class:'experience-body'},
      h('p',{},w('Revisa cambios visibles, páginas añadidas o eliminadas y diferencias de tamaño. Las páginas se comparan por posición; un cambio de orden puede afectar varias páginas.','Review visible changes, added or removed pages and differences in page size. Pages are compared by position; reordering may affect several pages.','Revise alterações visuais, páginas adicionadas ou removidas e diferenças no tamanho das páginas. As páginas são comparadas pela posição; uma mudança de ordem pode afetar várias páginas.')),
      h('p',{class:'wf-hint'},w('Los PDF se procesan en el servidor local de report-gen y sus archivos temporales se eliminan al terminar. La comparación descargada contiene imágenes del contenido de ambos informes.','PDFs are processed by the local report-gen server and its temporary files are deleted when processing finishes. The downloaded comparison contains images of both reports’ content.','Os PDFs são processados pelo servidor local do report-gen e os arquivos temporários são excluídos ao concluir. A comparação baixada contém imagens do conteúdo de ambos os relatórios.')),
      h('p',{class:'wf-hint'},w('Hasta 16 MiB y 80 páginas por PDF. No modifica el proyecto.','Up to 16 MiB and 80 pages per PDF. Leaves the project unchanged.','Até 16 MiB e 80 páginas por PDF. Mantém o projeto inalterado.')),
      h('div',{class:'pdf-compare-files'},h('label',{},w('PDF anterior','Earlier PDF','PDF anterior'),before),h('label',{},w('PDF nuevo','Later PDF','PDF novo'),after)),
      h('div',{class:'pdf-compare-actions'},compare,cancel,retry),status,error,output);
    dialog.append(h('div',{class:'experience-heading'},h('h2',{},title),close),body);

    function clearOutput(){
      output.replaceChildren();output.hidden=true;
      if(objectURL){URL.revokeObjectURL(objectURL);objectURL=null;}
    }
    function updateControls(){
      before.disabled=after.disabled=busy;
      compare.disabled=busy||!capabilities?.available||!before.files?.length||!after.files?.length;
      cancel.hidden=!busy;
      dialog.setAttribute('aria-busy',String(busy));
    }
    function cancelled(){
      ++generation;comparisonController?.abort();comparisonController=null;
      busy=false;clearOutput();error.textContent='';
      status.textContent=w('Espera cancelada. Si el procesamiento ya comenzó, finalizará y eliminará los archivos temporales en un máximo de 45 segundos.','Waiting cancelled. If processing already started, it will finish and remove temporary files within 45 seconds.','Espera cancelada. Se o processamento já começou, ele terminará e removerá os arquivos temporários em até 45 segundos.');updateControls();compare.focus();
    }
    function cleanup(){
      if(closed)return;
      closed=true;++generation;capabilityController?.abort();comparisonController?.abort();
      clearOutput();before.value=after.value='';dialog.remove();
      if(activeDialog===dialog)activeDialog=null;
      const focus=trigger?.closest('#searchResults')?$('#globalSearch'):trigger?.closest('details:not([open])')?.querySelector('summary')||trigger;
      (focus?.isConnected&&!focus.disabled?focus:$('#editor'))?.focus({preventScroll:true});
    }
    async function loadCapabilities(){
      capabilityController?.abort();const controller=new AbortController();capabilityController=controller;
      retry.hidden=true;error.textContent='';status.textContent=w('Comprobando disponibilidad…','Checking availability…','Verificando disponibilidade…');
      try{
        const response=await requireOk(await appFetch('/api/pdf-compare/capabilities',{signal:controller.signal}));
        const value=await response.json();if(closed||controller.signal.aborted)return;
        capabilities=value;
        status.textContent=value.available?w('Selecciona los dos PDF para comenzar.','Select both PDFs to begin.','Selecione os dois PDFs para começar.'):w('La comparación PDF no está disponible en esta instalación. Revisa la instalación del renderizador PDF.','PDF comparison is unavailable in this installation. Check the PDF renderer installation.','A comparação de PDF está indisponível nesta instalação. Verifique a instalação do renderizador PDF.');
        retry.hidden=!!value.available;
      }catch(e){if(!closed&&!controller.signal.aborted){error.textContent=e.message;status.textContent='';retry.hidden=false;}}
      finally{if(!closed&&!controller.signal.aborted)updateControls();}
    }
    async function run(){
      if(busy||!capabilities?.available)return;
      const files=[before.files?.[0],after.files?.[0]];
      error.textContent='';clearOutput();
      if(files.some(file=>!file)){error.textContent=w('Selecciona ambos archivos PDF.','Select both PDF files.','Selecione os dois arquivos PDF.');return;}
      const limit=Math.min(MAX_PDF_BYTES,capabilities.max_pdf_bytes||MAX_PDF_BYTES);
      if(files.some(file=>file.size===0||file.size>limit)){error.textContent=w('Cada PDF debe contener datos y pesar como máximo 16 MiB.','Each PDF must contain data and be no larger than 16 MiB.','Cada PDF deve conter dados e ter no máximo 16 MiB.');return;}
      const current=++generation,controller=new AbortController();comparisonController=controller;busy=true;updateControls();
      status.textContent=w('Comparando las páginas…','Comparing pages…','Comparando as páginas…');
      const data=new FormData();data.append('before',files[0]);data.append('after',files[1]);data.append('language',S.uiLang);
      try{
        const response=await requireOk(await appFetch('/api/pdf-compare',{method:'POST',body:data,signal:controller.signal}));
        if(!/\btext\/html\b/i.test(response.headers.get('Content-Type')||''))throw Error(w('La comparación recibida no es un archivo HTML válido.','The received comparison is not a valid HTML file.','A comparação recebida não é um arquivo HTML válido.'));
        const blob=await response.blob();if(closed||current!==generation||controller.signal.aborted)return;
        if(!blob.size||blob.size>Math.min(MAX_OUTPUT_BYTES,capabilities.max_output_bytes||MAX_OUTPUT_BYTES))throw Error(w('La comparación supera el tamaño permitido o está vacía.','The comparison exceeds the size limit or is empty.','A comparação excede o tamanho permitido ou está vazia.'));
        objectURL=URL.createObjectURL(blob);
        const download=h('a',{class:'btn',href:objectURL,download:'report-gen-pdf-comparison.html','data-pdf-compare-download':''},w('Descargar comparación HTML','Download HTML comparison','Baixar comparação HTML'));
        const frame=h('iframe',{class:'pdf-compare-frame',src:objectURL,sandbox:'',referrerpolicy:'no-referrer',title:w('Resultado de la comparación PDF','PDF comparison result','Resultado da comparação PDF'),'data-pdf-compare-frame':''});
        output.append(download,frame);output.hidden=false;
        status.textContent=w('Comparación lista. Revisa las páginas y descarga el resultado si quieres conservarlo.','Comparison ready. Review the pages and download the result to keep it.','Comparação pronta. Revise as páginas e baixe o resultado para mantê-lo.');
      }catch(e){if(!closed&&current===generation&&!controller.signal.aborted){error.textContent=e.message;status.textContent='';}}
      finally{if(!closed&&current===generation){comparisonController=null;busy=false;updateControls();}}
    }
    for(const input of [before,after])input.addEventListener('change',()=>{clearOutput();error.textContent='';status.textContent='';updateControls();});
    compare.addEventListener('click',run);cancel.addEventListener('click',cancelled);retry.addEventListener('click',loadCapabilities);
    dialog.addEventListener('close',cleanup);
    dialog.addEventListener('cancel',event=>{event.preventDefault();dialog.close();});
    document.body.append(dialog);dialog.showModal();before.focus();loadCapabilities();
  }
  return {open};
})();
