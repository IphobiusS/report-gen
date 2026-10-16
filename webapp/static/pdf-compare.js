/* PDF pixels and optional page pairing are transient; review records are explicit project mutations. */
const PDFComparisonUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt);
  const MAX_PDF_BYTES=16*1024*1024,MAX_OUTPUT_BYTES=32*1024*1024;
  const safeId=value=>typeof value==='string'&&/^[a-zA-Z0-9_-]{1,100}$/.test(value);
  let activeDialog=null;

  function open(trigger=document.activeElement){
    if(activeDialog?.isConnected){activeDialog.querySelector('input')?.focus();return;}
    const title=w('Comparar archivos PDF','Compare PDF files','Comparar arquivos PDF'),projectSlug=S.slug||null;
    const dialog=h('dialog',{class:'experience-dialog pdf-compare-dialog','aria-label':title,'data-pdf-compare':''});
    activeDialog=dialog;
    let capabilities=null,capabilityController=null,comparisonController=null,generation=0,objectURL=null,closed=false,busy=false,saving=false;
    let metadata=null,metadataFiles=null,mapping=null,receipt=null,listController=null,listGeneration=0;
    const downloadURLs=new Set();
    const status=h('p',{class:'pdf-compare-status',role:'status','aria-live':'polite','data-pdf-compare-status':''});
    const error=h('p',{class:'wf-error',role:'alert','data-pdf-compare-error':''});
    const output=h('section',{class:'pdf-compare-output','data-pdf-compare-output':'',hidden:''});
    const pairs=h('section',{class:'pdf-pairs','data-pdf-pairs':'',hidden:''});
    const pairSummary=h('p',{role:'status','aria-live':'polite','data-pdf-pair-summary':''});
    const pairRows=h('div',{class:'pdf-pair-rows'}),added=h('p',{'data-pdf-added-pages':''});
    const pairError=h('p',{class:'wf-error',role:'alert','data-pdf-pair-error':''});
    const before=h('input',{type:'file',accept:'.pdf,application/pdf','data-pdf-before':'','aria-label':w('PDF anterior','Earlier PDF','PDF anterior')});
    const after=h('input',{type:'file',accept:'.pdf,application/pdf','data-pdf-after':'','aria-label':w('PDF nuevo','Later PDF','PDF novo')});
    const pairButton=h('button',{type:'button',class:'btn','data-pdf-pair-open':''},w('Emparejar páginas','Pair pages','Emparelhar páginas'));
    const positional=h('button',{type:'button',class:'btn','data-pdf-pair-positional':''},w('Volver a comparar por posición','Return to positional comparison','Voltar à comparação por posição'));
    const reset=h('button',{type:'button',class:'btn','data-pdf-pair-reset':''},w('Restablecer pares por posición','Reset pairs by position','Redefinir pares por posição'));
    const compare=h('button',{type:'button',class:'btn primary','data-pdf-compare-submit':'',disabled:''},w('Comparar PDF','Compare PDFs','Comparar PDFs'));
    const cancel=h('button',{type:'button',class:'btn','data-pdf-compare-cancel':'',hidden:''},w('Cancelar espera','Stop waiting','Parar de esperar'));
    const retry=h('button',{type:'button',class:'btn',hidden:''},w('Comprobar de nuevo','Check again','Verificar novamente'));
    const close=h('button',{type:'button',class:'btn',onclick:()=>dialog.close()},w('Cerrar','Close','Fechar'));
    pairs.append(h('h3',{},w('Pares de páginas','Page pairs','Pares de páginas')),h('p',{class:'wf-hint'},w('Elige qué página nueva corresponde a cada página anterior. Las páginas nuevas sin asignar se incluyen como añadidas al final. Cada página se utiliza una sola vez.','Choose the later page corresponding to each earlier page. Unassigned later pages are included as added pages at the end. Each page is used exactly once.','Escolha a página nova correspondente a cada página anterior. Páginas novas não atribuídas são incluídas como adicionadas ao final. Cada página é usada uma única vez.')),pairSummary,pairRows,added,pairError,h('div',{class:'pdf-compare-actions'},reset,positional));
    const records=h('section',{class:'pdf-review-records','data-pdf-records':'',hidden:projectSlug?null:''});
    const recordStatus=h('p',{role:'status','aria-live':'polite','data-pdf-record-status':''}),recordList=h('div',{'data-pdf-record-list':''});
    const reload=h('button',{type:'button',class:'btn','data-pdf-record-reload':''},w('Cargar registros privados','Load private records','Carregar registros privados'));
    records.append(h('h3',{},w('Registros privados de revisión','Private review records','Registros privados de revisão')),h('p',{class:'wf-hint'},w('Guardar un registro es opcional. Conserva autor, decisión, nota, hashes y resumen; no conserva PDF, HTML ni imágenes. Permanece en el proyecto, su historial y respaldos hasta que los elimines; no se incluye por defecto en la entrega. La autoría es una declaración local, no una firma verificada.','Saving a record is optional. It keeps the author, decision, note, hashes and summary; no PDF, HTML or images. It remains in the project, its history and backups until you delete them; it is excluded from delivery by default. Authorship is a local declaration, not a verified signature.','Salvar um registro é opcional. Ele mantém autor, decisão, nota, hashes e resumo; não mantém PDF, HTML nem imagens. Permanece no projeto, no histórico e nos backups até que você os exclua; não é incluído na entrega por padrão. A autoria é uma declaração local, não uma assinatura verificada.')),reload,recordStatus,recordList);
    const body=h('div',{class:'experience-body'},
      h('p',{},w('Revisa cambios visibles, páginas añadidas o eliminadas y diferencias de tamaño. Compara por posición o empareja páginas si cambió el orden.','Review visible changes, added or removed pages and differences in page size. Compare by position or pair pages if their order changed.','Revise alterações visuais, páginas adicionadas ou removidas e diferenças no tamanho das páginas. Compare pela posição ou emparelhe as páginas se a ordem mudou.')),
      h('p',{class:'wf-hint'},w('Los PDF se procesan en el servidor local de report-gen y sus archivos temporales se eliminan al terminar. La comparación descargada contiene imágenes del contenido de ambos informes.','PDFs are processed by the local report-gen server and its temporary files are deleted when processing finishes. The downloaded comparison contains images of both reports’ content.','Os PDFs são processados pelo servidor local do report-gen e os arquivos temporários são excluídos ao concluir. A comparação baixada contém imagens do conteúdo de ambos os relatórios.')),
      h('p',{class:'wf-hint'},w('Hasta 16 MiB y 80 páginas por PDF. Comparar no modifica el proyecto. La comparación visual no verifica equivalencia semántica ni el documento Word original.','Up to 16 MiB and 80 pages per PDF. Comparing leaves the project unchanged. Visual comparison does not verify semantic equivalence or the original Word document.','Até 16 MiB e 80 páginas por PDF. Comparar mantém o projeto inalterado. A comparação visual não verifica equivalência semântica nem o documento Word original.')),
      h('div',{class:'pdf-compare-files'},h('label',{},w('PDF anterior','Earlier PDF','PDF anterior'),before),h('label',{},w('PDF nuevo','Later PDF','PDF novo'),after)),
      h('div',{class:'pdf-compare-actions'},compare,pairButton,cancel,retry),status,error,pairs,output,records);
    dialog.append(h('div',{class:'experience-heading'},h('h2',{},title),close),body);

    function releaseReceipt(id){if(safeId(id))appFetch('/api/pdf-compare/receipts/'+encodeURIComponent(id),{method:'DELETE'}).catch(()=>{});}
    function clearOutput(){
      output.replaceChildren();output.hidden=true;
      if(objectURL){URL.revokeObjectURL(objectURL);objectURL=null;}
      if(receipt){releaseReceipt(receipt);receipt=null;}
    }
    function currentFiles(){return [before.files?.[0],after.files?.[0]];}
    function filesMatch(files){return currentFiles().every((file,index)=>file===files[index]);}
    function validFiles(files){
      if(files.some(file=>!file)){error.textContent=w('Selecciona ambos archivos PDF.','Select both PDF files.','Selecione os dois arquivos PDF.');return false;}
      const limit=Math.min(MAX_PDF_BYTES,capabilities?.max_pdf_bytes||MAX_PDF_BYTES);
      if(files.some(file=>file.size===0||file.size>limit)){error.textContent=w('Cada PDF debe contener datos y pesar como máximo 16 MiB.','Each PDF must contain data and be no larger than 16 MiB.','Cada PDF deve conter dados e ter no máximo 16 MiB.');return false;}return true;
    }
    function mappingValid(){return mapping===null||(metadataFiles&&filesMatch(metadataFiles)&&mapping.every(n=>n===null||(Number.isInteger(n)&&n>=1&&n<=metadata.after.pages.length))&&new Set(mapping.filter(n=>n!==null)).size===mapping.filter(n=>n!==null).length);}
    function updateControls(){
      before.disabled=after.disabled=busy||saving;
      compare.disabled=busy||saving||!capabilities?.available||!before.files?.length||!after.files?.length||!mappingValid();
      pairButton.disabled=busy||saving||!capabilities?.available||!before.files?.length||!after.files?.length;
      pairButton.hidden=mapping!==null;reset.disabled=positional.disabled=busy||saving;
      pairRows.querySelectorAll('select').forEach(select=>{select.disabled=busy||saving;});
      close.disabled=saving;cancel.hidden=!busy;reload.disabled=saving||!!listController;
      output.querySelectorAll('button,input,select,textarea').forEach(el=>{el.disabled=saving;});
      dialog.setAttribute('aria-busy',String(busy||saving));
    }
    function invalidate(){++generation;comparisonController?.abort();comparisonController=null;busy=false;clearOutput();error.textContent='';status.textContent='';}
    function resetMapping(){mapping=metadata.before.pages.map(page=>page.number<=metadata.after.pages.length?page.number:null);}
    function pageLabel(number){return w('Página ','Page ','Página ')+number;}
    function pairsPayload(){const used=new Set(mapping.filter(n=>n!==null));return [...mapping.map((after,index)=>({before:index+1,after})),...metadata.after.pages.filter(page=>!used.has(page.number)).map(page=>({before:null,after:page.number}))];}
    function updatePairSummary(){
      const used=new Set(mapping.filter(n=>n!==null)),unassigned=metadata.after.pages.filter(page=>!used.has(page.number)).map(page=>page.number),duplicates=mapping.filter(n=>n!==null).length-used.size;
      pairSummary.textContent=w('Páginas anteriores: ','Earlier pages: ','Páginas anteriores: ')+mapping.length+' · '+w('Nuevas: ','Later pages: ','Páginas novas: ')+metadata.after.pages.length+' · '+w('Pares: ','Pairs: ','Pares: ')+used.size+' · '+w('Sin equivalente: ','Without counterpart: ','Sem equivalente: ')+mapping.filter(n=>n===null).length;
      added.textContent=w('Páginas nuevas añadidas explícitamente: ','Later pages explicitly added: ','Páginas novas adicionadas explicitamente: ')+(unassigned.length?unassigned.join(', '):w('ninguna','none','nenhuma'));
      pairError.textContent=duplicates?w('Una página nueva está asignada más de una vez. Corrige los pares para comparar.','A later page is assigned more than once. Correct the pairs to compare.','Uma página nova está atribuída mais de uma vez. Corrija os pares para comparar.'):w('Cobertura completa: todas las páginas aparecen una vez.','Complete coverage: every page appears exactly once.','Cobertura completa: todas as páginas aparecem uma única vez.');
      pairError.classList.toggle('wf-error',!!duplicates);pairError.setAttribute('role',duplicates?'alert':'status');
      pairRows.querySelectorAll('select').forEach(select=>{select.setAttribute('aria-invalid',String(select.value!==''&&mapping.filter(n=>n===Number(select.value)).length>1));});updateControls();
    }
    function renderPairs(){
      pairs.hidden=false;pairRows.replaceChildren();
      metadata.before.pages.forEach((page,index)=>{
        const label=pageLabel(page.number)+' '+w('anterior → página nueva','earlier → later page','anterior → página nova');
        const select=h('select',{'data-pdf-pair':String(page.number),'aria-label':label},h('option',{value:''},w('Sin equivalente (eliminada)','No counterpart (removed)','Sem equivalente (removida)')),metadata.after.pages.map(other=>h('option',{value:String(other.number)},pageLabel(other.number))));
        select.value=mapping[index]===null?'':String(mapping[index]);
        select.addEventListener('change',()=>{invalidate();mapping[index]=select.value===''?null:Number(select.value);updatePairSummary();});
        pairRows.append(h('label',{class:'pdf-pair-row'},h('span',{},label),select));
      });updatePairSummary();
    }
    function validMetadata(value,files){
      return value?.schema==='report-gen-pdf-metadata/1'&&['before','after'].every((side,index)=>{
        const item=value[side];return item&&/^[a-f0-9]{64}$/.test(item.sha256)&&Number.isInteger(item.bytes)&&item.bytes===files[index].size&&Array.isArray(item.pages)&&item.pages.length>=1&&item.pages.length<=80&&item.pages.every((page,i)=>page&&page.number===i+1&&Number.isFinite(page.width)&&page.width>0&&page.width<=20000&&Number.isFinite(page.height)&&page.height>0&&page.height<=20000);
      });
    }
    function formData(files){const data=new FormData();data.append('before',files[0]);data.append('after',files[1]);data.append('language',S.uiLang);return data;}
    async function inspect(){
      if(busy||saving||!capabilities?.available)return;
      const files=currentFiles();error.textContent='';if(!validFiles(files))return;invalidate();
      const current=++generation,controller=new AbortController();comparisonController=controller;busy=true;updateControls();
      status.textContent=w('Leyendo las páginas de ambos PDF…','Reading pages from both PDFs…','Lendo as páginas dos dois PDFs…');
      try{
        const response=await requireOk(await appFetch('/api/pdf-compare/metadata',{method:'POST',body:formData(files),signal:controller.signal}));
        const value=await response.json();if(closed||current!==generation||controller.signal.aborted||!filesMatch(files))return;
        if(!validMetadata(value,files))throw Error(w('La información de páginas recibida no es válida. Vuelve a seleccionar los PDF.','The received page information is invalid. Select the PDFs again.','As informações de páginas recebidas são inválidas. Selecione os PDFs novamente.'));
        metadata=value;metadataFiles=files;resetMapping();renderPairs();status.textContent=w('Ajusta los pares y compara cuando estén completos.','Adjust the pairs and compare when they are complete.','Ajuste os pares e compare quando estiverem completos.');
      }catch(e){if(!closed&&current===generation&&!controller.signal.aborted){error.textContent=e.message;status.textContent='';}}
      finally{if(!closed&&current===generation){comparisonController=null;busy=false;updateControls();if(mapping!==null)pairRows.querySelector('select')?.focus();}}
    }
    function cancelled(){
      invalidate();status.textContent=w('Espera cancelada. Si el procesamiento ya comenzó, finalizará y eliminará los archivos temporales en un máximo de 45 segundos.','Waiting cancelled. If processing already started, it will finish and remove temporary files within 45 seconds.','Espera cancelada. Se o processamento já começou, ele terminará e removerá os arquivos temporários em até 45 segundos.');updateControls();compare.focus();
    }
    function cleanup(){
      if(closed)return;
      closed=true;++generation;++listGeneration;capabilityController?.abort();comparisonController?.abort();listController?.abort();
      clearOutput();for(const url of downloadURLs)URL.revokeObjectURL(url);downloadURLs.clear();before.value=after.value='';metadata=null;metadataFiles=null;mapping=null;dialog.remove();
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
        status.textContent=value.available?w('Selecciona los dos PDF para comenzar.','Select both PDFs to begin.','Selecione os dois PDFs para começar.'):w('La comparación PDF no está disponible en esta instalación. Revisa la instalación del renderizador PDF.','PDF comparison is unavailable in this installation. Check the PDF renderer installation.','A comparação de PDF está indisponível nesta instalação. Verifique a instalação do renderizador PDF.');retry.hidden=!!value.available;
      }catch(e){if(!closed&&!controller.signal.aborted){error.textContent=e.message;status.textContent='';retry.hidden=false;}}
      finally{if(!closed&&!controller.signal.aborted)updateControls();}
    }
    const projectURL=()=>'/api/projects/'+encodeURIComponent(projectSlug)+'/pdf-comparisons';
    function assertProject(){if(!projectSlug||S.slug!==projectSlug||projectStore.loading)throw Error(w('El proyecto cambió. Vuelve a abrir el comparador.','The project changed. Reopen the comparator.','O projeto mudou. Reabra o comparador.'));}
    function decisionText(value){return value==='accepted'?w('Revisión aceptada','Review accepted','Revisão aceita'):w('Problemas observados','Issues observed','Problemas observados');}
    function renderRecords(values){
      if(!Array.isArray(values))throw Error(w('Lista de registros no válida.','Invalid record list.','Lista de registros inválida.'));
      recordList.replaceChildren();for(const value of values){
        if(!safeId(value?.uid))continue;
        const download=h('button',{type:'button',class:'btn','data-pdf-record-download':value.uid},w('Descargar registro JSON','Download JSON record','Baixar registro JSON'));
        download.addEventListener('click',async()=>{download.disabled=true;try{
          assertProject();const response=await requireOk(await appFetch(projectURL()+'/'+encodeURIComponent(value.uid)));const blob=await response.blob();if(closed||S.slug!==projectSlug)return;
          const url=URL.createObjectURL(blob);downloadURLs.add(url);const link=h('a',{href:url,download:'report-gen-pdf-review-'+value.uid+'.json'});document.body.append(link);link.click();link.remove();setTimeout(()=>{if(downloadURLs.delete(url))URL.revokeObjectURL(url);},1000);
        }catch(e){if(!closed)recordStatus.textContent=e.message;}finally{if(!closed)download.disabled=false;}});
        recordList.append(h('article',{class:'pdf-review-record','data-pdf-record':value.uid},h('h4',{},decisionText(value.decision)),h('p',{},String(value.author||'')+' · '+String(value.created||'')),h('p',{class:'pdf-review-note'},String(value.note||'')),h('p',{class:'wf-hint'},w('Pares registrados: ','Recorded pairs: ','Pares registrados: ')+String(value.page_pairs?.length||0)+' · '+w('Con cambios: ','Changed: ','Com alterações: ')+String(value.summary?.changed||0)),download));
      }
      recordStatus.textContent=values.length?w('Registros guardados: ','Saved records: ','Registros salvos: ')+values.length:w('Todavía no hay registros privados de comparación.','No private comparison records yet.','Ainda não há registros privados de comparação.');
    }
    async function loadRecords(){
      if(saving)return;const current=++listGeneration;listController?.abort();const controller=new AbortController();listController=controller;updateControls();
      recordStatus.textContent=w('Cargando registros…','Loading records…','Carregando registros…');
      try{assertProject();const response=await requireOk(await appFetch(projectURL(),{signal:controller.signal}));const value=await response.json();if(!closed&&current===listGeneration&&!controller.signal.aborted&&S.slug===projectSlug)renderRecords(value.records);}
      catch(e){if(!closed&&current===listGeneration&&!controller.signal.aborted)recordStatus.textContent=e.message;}
      finally{if(!closed&&current===listGeneration){listController=null;updateControls();}}
    }
    function reviewForm(id){
      const openForm=h('button',{type:'button',class:'btn','data-pdf-review-open':''},w('Guardar registro de revisión','Save review record','Salvar registro de revisão'));
      const form=h('form',{class:'pdf-review-form','data-pdf-review-form':'',hidden:''});
      const author=h('input',{type:'text',required:'',maxlength:'120','data-pdf-review-author':''});
      const decision=h('select',{'data-pdf-review-decision':''},h('option',{value:'accepted'},decisionText('accepted')),h('option',{value:'issues'},decisionText('issues')));
      const note=h('textarea',{rows:'3',maxlength:'4000','data-pdf-review-note':''});
      const formStatus=h('p',{role:'status','aria-live':'polite','data-pdf-review-status':''});
      const save=h('button',{type:'submit',class:'btn primary','data-pdf-review-save':''},w('Guardar registro privado','Save private record','Salvar registro privado'));
      const hide=h('button',{type:'button',class:'btn'},w('Cancelar registro','Cancel record','Cancelar registro'));
      form.append(h('h3',{},w('Decisión de revisión','Review decision','Decisão de revisão')),h('p',{class:'wf-hint'},w('El recibo temporal caduca en 30 minutos; se conservan hasta 8 comparaciones recientes. Al guardar, el registro permanece en el proyecto, su historial y respaldos hasta que los elimines. No se incluyen imágenes ni archivos PDF o HTML, ni se incorpora por defecto a la entrega.','The temporary receipt expires after 30 minutes; up to 8 recent comparisons are kept. Saving retains the record in the project, its history and backups until you delete them. It contains no images, PDF or HTML files and is excluded from delivery by default.','O recibo temporário expira em 30 minutos; até 8 comparações recentes são mantidas. Ao salvar, o registro permanece no projeto, no histórico e nos backups até que você os exclua. Não contém imagens nem arquivos PDF ou HTML e não é incluído na entrega por padrão.')),h('label',{},w('Autor (declaración local)','Author (local declaration)','Autor (declaração local)'),author),h('label',{},w('Decisión','Decision','Decisão'),decision),h('label',{},w('Nota (obligatoria si hay problemas)','Note (required for issues)','Nota (obrigatória se houver problemas)'),note),h('div',{class:'pdf-compare-actions'},save,hide),formStatus);
      decision.addEventListener('change',()=>{note.required=decision.value==='issues';});
      openForm.addEventListener('click',()=>{form.hidden=false;openForm.hidden=true;author.focus();});hide.addEventListener('click',()=>{form.hidden=true;openForm.hidden=false;openForm.focus();});
      form.addEventListener('submit',async event=>{
        event.preventDefault();if(saving||id!==receipt)return;const values={comparison_id:id,author:author.value.trim(),decision:decision.value,note:note.value.trim()};
        if(!values.author||values.author.length>120||values.note.length>4000||!['accepted','issues'].includes(values.decision)||(values.decision==='issues'&&!values.note)){formStatus.textContent=w('Completa el autor y la nota requerida.','Complete the author and required note.','Preencha o autor e a nota obrigatória.');return;}
        let saved=false;saving=true;updateControls();busyProject(true);formStatus.textContent=w('Guardando registro…','Saving record…','Salvando registro…');
        try{
          assertProject();if(!await doSave())throw Error(w('No se pudo guardar el proyecto.','Could not save project.','Não foi possível salvar o projeto.'));assertProject();
          const response=await requireOk(await appFetch(projectURL(),{method:'POST',headers:{'Content-Type':'application/json','If-Match':projectStore.etag},body:JSON.stringify(values)}));const value=await response.json();assertProject();
          await adoptSavedProject(value.data,response.headers.get('ETag'));++listGeneration;listController?.abort();listController=null;renderRecords(value.records);
          form.hidden=true;openForm.hidden=false;formStatus.textContent='';status.textContent=w('Registro privado guardado en el proyecto.','Private record saved in the project.','Registro privado salvo no projeto.');saved=true;
        }catch(e){formStatus.textContent=e.message;}
        finally{saving=false;busyProject(false);updateControls();if(saved)openForm.focus();}
      });return [openForm,form];
    }
    async function run(){
      if(busy||saving||!capabilities?.available||!mappingValid())return;
      const files=currentFiles();error.textContent='';clearOutput();if(!validFiles(files))return;
      const current=++generation,controller=new AbortController();comparisonController=controller;busy=true;updateControls();
      status.textContent=w('Comparando las páginas…','Comparing pages…','Comparando as páginas…');const data=formData(files);
      if(mapping!==null){data.append('page_pairs',JSON.stringify(pairsPayload()));data.append('expected_before_sha256',metadata.before.sha256);data.append('expected_after_sha256',metadata.after.sha256);}
      try{
        const response=await requireOk(await appFetch('/api/pdf-compare',{method:'POST',body:data,signal:controller.signal}));
        const responseId=response.headers.get('X-Report-Gen-Comparison-Id');
        if(closed||current!==generation||controller.signal.aborted||!filesMatch(files)){releaseReceipt(responseId);return;}
        if(safeId(responseId))receipt=responseId;
        if(!/\btext\/html\b/i.test(response.headers.get('Content-Type')||''))throw Error(w('La comparación recibida no es un archivo HTML válido.','The received comparison is not a valid HTML file.','A comparação recebida não é um arquivo HTML válido.'));
        const blob=await response.blob();if(closed||current!==generation||controller.signal.aborted||!filesMatch(files))return;
        if(!blob.size||blob.size>Math.min(MAX_OUTPUT_BYTES,capabilities.max_output_bytes||MAX_OUTPUT_BYTES))throw Error(w('La comparación supera el tamaño permitido o está vacía.','The comparison exceeds the size limit or is empty.','A comparação excede o tamanho permitido ou está vazia.'));
        objectURL=URL.createObjectURL(blob);
        const download=h('a',{class:'btn',href:objectURL,download:'report-gen-pdf-comparison.html','data-pdf-compare-download':''},w('Descargar comparación HTML','Download HTML comparison','Baixar comparação HTML'));
        const frame=h('iframe',{class:'pdf-compare-frame',src:objectURL,sandbox:'',referrerpolicy:'no-referrer',title:w('Resultado de la comparación PDF','PDF comparison result','Resultado da comparação PDF'),'data-pdf-compare-frame':''});
        output.append(download,...(receipt&&projectSlug?[h('div',{class:'pdf-review-entry'},...reviewForm(receipt))]:[]),frame);output.hidden=false;
        status.textContent=w('Comparación lista. Revisa las páginas y descarga el resultado si quieres conservarlo.','Comparison ready. Review the pages and download the result to keep it.','Comparação pronta. Revise as páginas e baixe o resultado para mantê-lo.');
      }catch(e){if(!closed&&current===generation&&!controller.signal.aborted){clearOutput();error.textContent=e.message;status.textContent='';}}
      finally{if(!closed&&current===generation){comparisonController=null;busy=false;updateControls();}}
    }
    for(const input of [before,after])input.addEventListener('change',()=>{invalidate();metadata=null;metadataFiles=null;mapping=null;pairs.hidden=true;pairRows.replaceChildren();updateControls();});
    pairButton.addEventListener('click',inspect);reset.addEventListener('click',()=>{invalidate();resetMapping();renderPairs();pairRows.querySelector('select')?.focus();});
    positional.addEventListener('click',()=>{invalidate();metadata=null;metadataFiles=null;mapping=null;pairs.hidden=true;pairRows.replaceChildren();updateControls();pairButton.focus();});
    compare.addEventListener('click',run);cancel.addEventListener('click',cancelled);retry.addEventListener('click',loadCapabilities);reload.addEventListener('click',loadRecords);
    dialog.addEventListener('close',cleanup);dialog.addEventListener('cancel',event=>{event.preventDefault();if(!saving)dialog.close();});
    document.body.append(dialog);dialog.showModal();before.focus();loadCapabilities();
  }
  return {open};
})();
