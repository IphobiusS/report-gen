/* Guided delivery uses the existing review, publication and export APIs.
 * Opening a step never saves, publishes, or records an approval. */
const DeliveryFlowUI = (() => {
  'use strict';
  const w=(es,en,pt)=>uiText(es,en,pt),choices=new Map(),recovering=new Map();
  let active=null;
  const revision=value=>String(value||'').replace(/^"|"$/g,'');
  const labels=[['Revisión','Review','Revisão'],['Destinatario','Audience','Público'],['Vista previa','Preview','Prévia'],['Exportación','Export','Exportação']];
  function button(text,run,key,primary=false){
    const b=h('button',{type:'button',class:'btn'+(primary?' primary':''),'data-delivery-action':key},text);
    b.addEventListener('click',async()=>{b.disabled=true;try{await run();}catch(error){toast(error.message,'err');if(active?.shell.isConnected)active.status.textContent=error.message;}finally{if(b.isConnected)b.disabled=false;active?.refresh();}});return b;
  }
  function knownLocation(issue,source=true){
    if(typeof issue.path!=='string'||!issue.path)return false;
    if(issue.finding_uid)return S.data.findings?.some(row=>row.uid===issue.finding_uid);
    if(!source)return false; // Audience paths may refer to reordered derivatives.
    return /^(meta\.|report\.|(?:assets|coverage|evidence|attachments|capture_inbox|root_cause_groups)(?:\[|\.|$))/.test(issue.path);
  }
  function issueNode(issue,source=true){
    const node=h('div',{class:'delivery-flow-issue '+(issue.level==='error'?'wf-error':'wf-warning')},h('p',{},issue.message));
    if(issue.help)node.append(h('p',{class:'wf-hint'},issue.help));
    if(knownLocation(issue,source))node.append(button(w('Ir al campo','Go to field','Ir para o campo'),()=>WorkflowUI.navigateIssue(issue),'issue'));
    return node;
  }
  function render(el){
    const slug=S.slug,scope=(S.workspace_id||'')+'|'+slug;
    if(!slug){el.append(h('p',{},w('Abre un proyecto primero.','Open a project first.','Abra um projeto primeiro.')));return;}
    if(!choices.has(scope))choices.set(scope,{kind:'full',label:(S.data.meta.client||slug)+' - '+(S.data.meta.version||'1.0'),formats:new Set(['pdf','docx','md'])});
    const settings=choices.get(scope),shell=h('section',{class:'delivery-flow studio-stage','data-delivery-flow':'','aria-labelledby':'deliveryFlowTitle'});
    const status=h('p',{class:'delivery-flow-status',role:'status','aria-live':'polite'}),nav=h('nav',{'aria-label':w('Pasos de la entrega','Delivery steps','Etapas da entrega'),class:'delivery-flow-nav'}),panels=[];
    let step=0,review=null,plan=null,confirmed=false,audience=null,audienceRevision=null,loadGeneration=0,previewGeneration=0,busy=false,lastSignature=null,pending=null;
    const buttons=labels.map((label,index)=>{const b=button(String(index+1).padStart(2,'0')+' / '+w(...label),()=>show(index),'step-'+index);b.setAttribute('aria-controls','deliveryPanel'+index);nav.append(b);return b;});
    shell.append(h('p',{class:'workspace-path'},'~/'+slug+'/delivery'),h('h1',{id:'deliveryFlowTitle',tabindex:'-1'},w('Prepara una entrega revisada','Prepare a reviewed delivery','Prepare uma entrega revisada')),h('p',{},w('Revisa el contenido, elige quién lo recibirá y comprueba la copia antes de generar archivos.','Review the content, choose its audience, and check the snapshot before generating files.','Revise o conteúdo, escolha o público e confira a cópia antes de gerar os arquivos.')),nav,status);
    labels.forEach((label,index)=>{const panel=h('section',{id:'deliveryPanel'+index,class:'delivery-flow-panel','data-delivery-step':index,'aria-labelledby':'deliveryStep'+index},h('h2',{id:'deliveryStep'+index,tabindex:'-1'},(index+1)+'. '+w(...label)));panels.push(panel);shell.append(panel);});
    el.append(shell);
    const current=()=>!!review&&S.slug===slug&&!projectStore.dirty&&!projectStore.loading&&review.revision===revision(projectStore.etag);
    const blockers=()=>review?.issues.filter(issue=>issue.level==='error')||[];
    const warnings=()=>review?.issues.filter(issue=>issue.level!=='error')||[];
    const planCurrent=()=>current()&&!!plan&&plan.etag===projectStore.etag&&plan.kind===settings.kind&&(settings.kind==='full'||audience?.isCurrent());
    const requireReview=()=>{if(!current())throw Error(w('Guarda y vuelve a comprobar esta revisión.','Save and check this revision again.','Salve e verifique esta revisão novamente.'));};
    function requirePlan(){requireReview();if(!planCurrent()||!confirmed)throw Error(w('Revisa y confirma la vista previa actual.','Review and confirm the current preview.','Revise e confirme a prévia atual.'));if(blockers().length||plan.errors)throw Error(w('Corrige los bloqueos antes de exportar.','Fix the blockers before exporting.','Corrija os impedimentos antes de exportar.'));}
    function show(index,focus=true){
      if(index===2){requireReview();if(settings.kind==='audience'&&!audience)throw Error(w('Espera a que cargue el destinatario.','Wait for the audience to load.','Aguarde o carregamento do público.'));}
      if(index===3)requirePlan();
      step=index;refresh();if(focus){const heading=panels[index].querySelector('h2');heading.focus({preventScroll:true});heading.scrollIntoView?.({block:'nearest'});}
    }
    function invalidate(message){
      plan=null;confirmed=false;previewGeneration++;confirmInput.checked=false;ack.checked=false;
      if(audience?.isCurrent())audience.invalidate();
      previewStatus.textContent=message||w('La selección o el contenido cambió. Vuelve a comprobar la vista previa.','The selection or content changed. Check the preview again.','A seleção ou o conteúdo mudou. Verifique a prévia novamente.');
      fullPreview.replaceChildren();refresh();
    }
    function refresh(){
      shell.dataset.deliveryCurrent=String(current());shell.dataset.deliveryPreviewCurrent=String(planCurrent());
      panels.forEach((panel,index)=>{panel.hidden=index!==step;buttons[index].setAttribute('aria-current',index===step?'step':'false');});
      buttons[2].disabled=!current()||busy;buttons[3].disabled=!planCurrent()||!confirmed||blockers().length>0||!!plan?.errors||busy;
      reviewNext.disabled=!current()||busy;fullOptions.hidden=settings.kind!=='full';audienceHost.hidden=settings.kind!=='audience';
      previewAction.hidden=settings.kind!=='full';fullPreview.hidden=settings.kind!=='full';audiencePreview.hidden=settings.kind!=='audience';
      fullExport.hidden=settings.kind!=='full';audienceExport.hidden=settings.kind!=='audience';confirmLabel.hidden=!planCurrent();
      confirmationNext.disabled=buttons[3].disabled;generate.disabled=buttons[3].disabled||!settings.formats.size||!labelInput.value.trim()||(warnings().length>0&&!ack.checked);
      if(audience)audience.exportButton.disabled=buttons[3].disabled||!!plan?.errors;
      ackLabel.hidden=!warnings().length;
    }
    const reviewContent=h('div',{'data-delivery-review':''});
    const reviewNext=button(w('Continuar al destinatario','Continue to audience','Continuar para o público'),()=>show(1),'review-next',true);
    const check=button(w('Guardar y revisar entrega','Save and review delivery','Salvar e revisar entrega'),async()=>{busy=true;refresh();try{if(await doSave())await loadReview();}finally{busy=false;refresh();}},'check',true);
    panels[0].append(h('p',{},w('Los bloqueos impiden generar la entrega. Las recomendaciones requieren lectura y confirmación; ninguna comprobación automática constituye aprobación técnica o editorial.','Blockers prevent delivery generation. Recommendations require reading and acknowledgement; no automatic check constitutes technical or editorial approval.','Os impedimentos bloqueiam a geração da entrega. As recomendações exigem leitura e confirmação; nenhuma verificação automática constitui aprovação técnica ou editorial.')),check,reviewContent,
      h('div',{class:'delivery-flow-actions'},button(w('Inspector de publicación','Publication inspector','Inspetor de publicação'),()=>StudioUI.inspector(),'inspector'),button(w('Inventario de anexos','Annex inventory','Inventário de anexos'),()=>AnnexUI.open(),'review-attachments'),button(w('Mesa de revisión editorial','Editorial review desk','Mesa de revisão editorial'),()=>InsightsUI.open('review'),'editorial')),ExperienceUI.deliveryChecklist(),reviewNext);
    async function loadReview(){
      const generation=++loadGeneration;review=null;invalidate();reviewContent.replaceChildren(h('p',{role:'status'},w('Leyendo la revisión guardada…','Reading the saved revision…','Lendo a revisão salva…')));
      try{const data=await api.get('/api/projects/'+encodeURIComponent(slug)+'/review?lang='+S.uiLang);
        if(!shell.isConnected||S.slug!==slug||generation!==loadGeneration)return;
        if(projectStore.dirty||data.revision!==revision(projectStore.etag))throw Error(w('Hay cambios pendientes. Guarda y revisa la entrega.','There are pending changes. Save and review the delivery.','Há alterações pendentes. Salve e revise a entrega.'));
        review=data;
        if(audience&&audienceRevision!==projectStore.etag){audience=null;audienceRevision=null;audienceHost.replaceChildren();audiencePreview.replaceChildren();audienceExport.replaceChildren();if(settings.kind==='audience')loadAudience();}
        reviewContent.replaceChildren(h('p',{class:'hash'},w('Revisión guardada: ','Saved revision: ','Revisão salva: ')+data.revision));
        for(const [level,title,items]of [['error',w('Bloqueos','Blockers','Impedimentos'),blockers()],['warning',w('Recomendaciones','Recommendations','Recomendações'),warnings()]]){
          const group=h('details',{class:'delivery-flow-issues',open:level==='error'&&items.length?'':null,'data-delivery-issues':level},h('summary',{},title+' · '+items.length));
          if(!items.length)group.append(h('p',{},w('No se detectaron en estas comprobaciones.','None detected by these checks.','Nenhum detectado nestas verificações.')));
          items.forEach(issue=>group.append(issueNode(issue)));reviewContent.append(group);
        }
        status.textContent=w('Comprobación de la revisión guardada disponible.','Saved revision checks are available.','As verificações da revisão salva estão disponíveis.');
      }catch(error){if(shell.isConnected&&generation===loadGeneration){reviewContent.replaceChildren(h('p',{role:'alert'},error.message));status.textContent=error.message;}}
      refresh();
    }
    const audienceHost=h('div',{'data-delivery-audience':''}),audiencePreview=h('div',{}),audienceExport=h('div',{}),fullOptions=h('div',{});
    const destination=h('fieldset',{class:'delivery-flow-choice'},h('legend',{},w('Contenido para el destinatario','Audience content','Conteúdo para o público')));
    for(const [value,title,description]of [
      ['full',['Informe completo','Complete report','Relatório completo'],['Conserva todas las secciones, los hallazgos y los anexos habilitados.','Retains every enabled section, finding and attachment.','Mantém todas as seções, achados e anexos habilitados.']],
      ['audience',['Entrega por destinatario','Audience delivery','Entrega por público'],['Elige un perfil técnico, ejecutivo o público y revisa qué se excluye.','Choose a technical, executive or public profile and review what is excluded.','Escolha um perfil técnico, executivo ou público e revise o que será excluído.']]
    ]){
      const input=h('input',{type:'radio',name:'delivery-destination',value,checked:settings.kind===value?'':null});input.addEventListener('change',()=>{if(!input.checked)return;settings.kind=value;invalidate();if(value==='audience')loadAudience();refresh();});
      destination.append(h('label',{},input,h('span',{},h('strong',{},w(...title)),h('small',{},w(...description)))));
    }
    fullOptions.append(h('p',{},w('El informe completo usa la copia de publicación existente. Las capturas privadas, los originales y el respaldo editable no forman parte de la entrega.','The complete report uses the existing publication snapshot. Private captures, originals and the editable backup are excluded from the delivery.','O relatório completo usa a cópia de publicação existente. Capturas privadas, originais e o backup editável não fazem parte da entrega.')),button(w('Inventario de anexos','Annex inventory','Inventário de anexos'),()=>AnnexUI.open(),'attachments'));
    panels[1].append(destination,fullOptions,audienceHost,button(w('Continuar a la vista previa','Continue to preview','Continuar para a prévia'),()=>show(2),'audience-next',true));
    let audienceLoading=false;
    async function loadAudience(){
      if(audience||audienceLoading)return;audienceLoading=true;audienceHost.replaceChildren(h('p',{role:'status'},w('Leyendo destinatarios…','Loading audience options…','Carregando opções de público…')));
      try{const etag=projectStore.etag,data=await api.get('/api/projects/'+encodeURIComponent(slug)+'/insights?lang='+S.uiLang);if(!shell.isConnected||S.slug!==slug)return;
        if(etag!==projectStore.etag||projectStore.dirty)throw Error(w('El contenido cambió. Guarda y revisa la entrega antes de configurar el destinatario.','The content changed. Save and review the delivery before configuring its audience.','O conteúdo mudou. Salve e revise a entrega antes de configurar o público.'));
        audienceRevision=etag;audienceHost.replaceChildren();
        audience=InsightsUI.mountAudience(audienceHost,{findings:data.map?.findings||[],issueNode:issue=>issueNode(issue,false),
          onInvalidate:()=>{plan=null;confirmed=false;confirmInput.checked=false;refresh();},beforeExport:requirePlan,
          onPreview:result=>{plan={etag:result.revision,kind:'audience',errors:result.errors};confirmed=false;confirmInput.checked=false;moveAudience();previewStatus.textContent=w('Comprueba el plan y el texto de esta copia.','Check the plan and text of this snapshot.','Confira o plano e o texto desta cópia.');show(2);},
          onExported:()=>{status.textContent=w('Paquete descargado. Revisa los archivos antes de compartir.','Package downloaded. Review the files before sharing.','Pacote baixado. Revise os arquivos antes de compartilhar.');}});
        moveAudience();
      }catch(error){if(shell.isConnected)audienceHost.replaceChildren(h('p',{role:'alert'},error.message),button(w('Reintentar','Retry','Tentar novamente'),loadAudience,'retry-audience'));}
      finally{audienceLoading=false;refresh();}
    }
    function moveAudience(){if(!audience)return;audiencePreview.append(audience.previewButton,audience.results);audienceExport.append(audience.ackLabel,audience.formatBox,audience.exportButton);}
    const previewStatus=h('p',{role:'status'}),fullPreview=h('div',{'data-delivery-publication':''});
    const previewAction=button(w('Comprobar copia de publicación','Check publication snapshot','Verificar cópia de publicação'),async()=>{
      requireReview();invalidate();const generation=previewGeneration,etag=projectStore.etag,data=await api.get('/api/projects/'+encodeURIComponent(slug)+'/publication');
      if(!shell.isConnected||S.slug!==slug||generation!==previewGeneration||!current()||projectStore.etag!==etag||data.revision!==revision(etag))return;
      fullPreview.replaceChildren(h('p',{class:'hash'},w('Revisión: ','Revision: ','Revisão: ')+data.revision),h('p',{},(data.images||[]).length+' '+w('imágenes de publicación','publication images','imagens de publicação')+' · '+data.private_captures+' '+w('capturas privadas excluidas','private captures excluded','capturas privadas excluídas')),
        h('details',{open:''},h('summary',{},w('Texto que se publicará','Outgoing text','Texto de saída')),h('pre',{class:'delivery-flow-text',tabindex:'0'},data.text)),
        button(w('Revisar imágenes y posibles secretos','Review images and possible secrets','Revisar imagens e possíveis segredos'),()=>StudioUI.inspector(),'inspect-preview'));
      plan={etag,kind:'full',errors:false};previewStatus.textContent=w('Revisa el texto y las imágenes de esta copia antes de continuar.','Review the text and images of this snapshot before continuing.','Revise o texto e as imagens desta cópia antes de continuar.');refresh();
    },'preview',true);
    const confirmInput=h('input',{type:'checkbox','data-delivery-preview-confirm':''}),confirmLabel=h('label',{class:'wf-check delivery-flow-confirm'},confirmInput,w('He revisado la copia de publicación actual. Esto no registra una aprobación técnica ni editorial.','I reviewed the current publication snapshot. This does not record technical or editorial approval.','Revisei a cópia de publicação atual. Isto não registra aprovação técnica nem editorial.'));
    confirmInput.addEventListener('change',()=>{confirmed=confirmInput.checked&&planCurrent();refresh();});
    const confirmationNext=button(w('Continuar a exportación','Continue to export','Continuar para a exportação'),()=>show(3),'preview-next',true);
    panels[2].append(h('p',{},w('Esta vista muestra el contenido de salida; no sustituye la revisión visual de los archivos generados.','This preview shows outgoing content; it does not replace visual review of generated files.','Esta prévia mostra o conteúdo de saída; não substitui a revisão visual dos arquivos gerados.')),previewStatus,previewAction,fullPreview,audiencePreview,confirmLabel,confirmationNext);
    const fullExport=h('div',{}),labelInput=h('input',{value:settings.label,maxlength:120,'data-flow-delivery':'label'}),formats=h('fieldset',{class:'delivery-formats'},h('legend',{},w('Formatos de entrega','Delivery formats','Formatos de entrega'))),ack=h('input',{type:'checkbox','data-flow-delivery':'ack'}),ackLabel=h('label',{class:'wf-check'},ack,w('He revisado las recomendaciones y acepto incluirlas en esta entrega.','I reviewed the recommendations and agree to include them in this delivery.','Revisei as recomendações e aceito incluí-las nesta entrega.'));
    labelInput.addEventListener('input',()=>{settings.label=labelInput.value;refresh();});
    for(const spec of S.formats){const input=h('input',{type:'checkbox',value:spec.key,checked:settings.formats.has(spec.key)?'':null,'data-flow-delivery-format':spec.key});input.addEventListener('change',()=>{if(input.checked)settings.formats.add(spec.key);else settings.formats.delete(spec.key);refresh();});formats.append(h('label',{class:'wf-check'},input,spec['label_'+S.uiLang]));}
    ack.addEventListener('change',refresh);
    const generate=button(w('Generar paquete','Generate package','Gerar pacote'),async()=>{
      requirePlan();if(warnings().length&&!ack.checked)throw Error(w('Revisa y confirma las recomendaciones.','Review and acknowledge the recommendations.','Revise e confirme as recomendações.'));
      if(!settings.formats.size||!labelInput.value.trim())throw Error(w('Indica un nombre y al menos un formato.','Enter a name and select at least one format.','Informe um nome e selecione pelo menos um formato.'));
      const etag=plan.etag,pendingRevision=pending?.handle.revision;busy=true;pending?.setBusy(true);refresh();try{await ProgressUI.enqueue(slug,etag,{kind:'delivery',formats:[...settings.formats],label:labelInput.value,acknowledge_warnings:ack.checked},false);if(pending&&(await pending.committed(pendingRevision)).finished)attachSettings();status.textContent=w('Entrega en cola desde la revisión comprobada.','Delivery queued from the checked revision.','Entrega na fila a partir da revisão verificada.');ProgressUI.jobs();}finally{busy=false;pending?.setBusy(false);refresh();}
    },'generate',true);
    fullExport.append(h('label',{},w('Nombre de la entrega','Delivery name','Nome da entrega'),labelInput),formats,ackLabel,generate);
    panels[3].append(h('p',{},w('Los formatos se generan desde la revisión comprobada. Descarga y revisa los archivos antes de compartirlos.','Formats are generated from the checked revision. Download and review the files before sharing them.','Os formatos são gerados a partir da revisão verificada. Baixe e revise os arquivos antes de compartilhá-los.')),fullExport,audienceExport,h('div',{class:'delivery-flow-actions'},button(w('Exportaciones y descargas','Exports and downloads','Exportações e downloads'),()=>ProgressUI.jobs(),'downloads'),button(w('Revisión visual de archivos','Visual file review','Revisão visual dos arquivos'),()=>InsightsUI.open('visual'),'visual')));
    function attachSettings(origin=null){
      if(typeof PendingUI==='undefined')return;pending?.dispose();
      pending=PendingUI.attach('delivery:settings',w('Configuración de entrega pendiente','Pending delivery settings','Configuração de entrega pendente'),()=>({data:{kind:settings.kind,label:settings.label,formats:[...settings.formats]}}),{container:fullExport,events:shell,origin,onDiscard:()=>{choices.delete(scope);recovering.delete(scope);renderMain();}});
    }
    attachSettings(recovering.get(scope));recovering.delete(scope);
    active={shell,status,refresh,update(){
      const signature=[S.slug,projectStore.etag,projectStore.revision,projectStore.dirty,projectStore.loading].join('|');if(signature===lastSignature)return;lastSignature=signature;
      if(plan&&!planCurrent())invalidate();if(review&&!current())status.textContent=w('El contenido cambió. Guarda y vuelve a revisar la entrega.','The content changed. Save and review the delivery again.','O conteúdo mudou. Salve e revise a entrega novamente.');refresh();
    }};
    show(0,false);loadReview();if(settings.kind==='audience')loadAudience();
  }
  function update(){if(active?.shell.isConnected)active.update();else active=null;}
  if(typeof PendingUI!=='undefined')PendingUI.register('delivery:',{
    validate(row){const value=row.data;if(row.key!=='delivery:settings'||!value||Object.keys(value).sort().join()!=='formats,kind,label'||!['full','audience'].includes(value.kind)||typeof value.label!=='string'||value.label.length>120||!Array.isArray(value.formats)||new Set(value.formats).size!==value.formats.length||value.formats.some(format=>!['pdf','docx','md','html'].includes(format)))throw Error(w('Configuración de entrega no compatible.','Unsupported delivery settings.','Configuração de entrega não compatível.'));},
    restore(row){const scope=(S.workspace_id||'')+'|'+S.slug;choices.set(scope,{kind:row.data.kind,label:row.data.label,formats:new Set(row.data.formats)});recovering.set(scope,row);select('studio','deliver');$('#deliveryFlowTitle')?.focus();}
  });
  return {render,update};
})();
