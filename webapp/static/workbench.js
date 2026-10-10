/* Workflow-oriented UI. Preferences never rewrite report content. */
const UndoUI = (() => {
  const stack=[];
  function contains(root, target) {
    if(root===target)return true;
    return !!root&&typeof root==='object'&&Object.values(root).some(v=>contains(v,target));
  }
  function remember(action) {
    stack.push({...action,slug:S.slug});if(stack.length>20)stack.shift();update();
  }
  function remove(array,index) {
    if(array===S.data.findings)ensureFindingIds();
    const value=array[index], before=array[index-1], after=array[index+1];
    remember({array,value,index,before,after,kind:'remove'});array.splice(index,1);
  }
  function move(array,from,to) {
    if(from===to||from<0||to<0||from>=array.length||to>=array.length)return;
    const value=array[from];remember({array,value,index:from,before:array[from-1],after:array[from+1],kind:'move'});
    array.splice(to,0,array.splice(from,1)[0]);
  }
  function clear(){stack.length=0;update();}
  function update(){
    const b=document.querySelector('#undoAction');if(b)b.disabled=!stack.length||projectBusyCount>0;
    let notice=document.querySelector('#undoNotice');
    if(!stack.length){notice?.remove();return;}
    if(!notice){notice=h('div',{id:'undoNotice',class:'undo-notice'},h('span',{role:'status'}),h('button',{type:'button',class:'btn sm',onclick:undo}));document.querySelector('.topbar').after(notice);}
    notice.querySelector('span').textContent=S.uiLang==='en'?'An action can be undone without reverting other edits.':'Puedes deshacer la acción sin revertir las demás ediciones.';
    notice.querySelector('button').textContent=S.uiLang==='en'?'Undo action':'Deshacer acción';notice.querySelector('button').disabled=projectBusyCount>0;
  }
  function undo(){
    const a=stack.at(-1);if(!a)return;
    if(a.slug!==S.slug||!contains(S.data,a.array)){clear();toast(S.uiLang==='en'?'The project was reloaded. Use Versions to recover older changes.':'El proyecto se recargó. Usa Versiones para recuperar cambios anteriores.','err');return;}
    stack.pop();
    if(a.kind==='move'){const i=a.array.indexOf(a.value);if(i<0){update();return;}a.array.splice(i,1);}
    const next=a.array.indexOf(a.after),prev=a.array.indexOf(a.before);
    a.array.splice(next>=0?next:prev>=0?prev+1:Math.min(a.index,a.array.length),0,a.value);
    const selected=S.sel.type==='finding'?S.data.findings[S.sel.idx]?.uid:null;
    ensureFindingIds();
    if(a.array===S.data.findings){const idx=S.data.findings.findIndex(f=>f.uid===(a.value?.uid||selected));S.sel={type:idx>=0?'finding':'report',idx};}
    scheduleSave();renderSidebar();renderMain();update();document.querySelector('#editor').focus({preventScroll:true});
    toast(S.uiLang==='en'?'Action undone. Other edits are preserved.':'Acción deshecha. Se conservan las demás ediciones.','ok');
  }
  return {remove,move,undo,clear,update};
})();

const WorkbenchUI = (() => {
  'use strict';
  const w=(es,en)=>S.uiLang==='en'?en:es;
  const verification=[['','Sin registrar','Not recorded'],['unverified','Sin verificar','Unverified'],['confirmed','Confirmado','Confirmed'],['not_reproduced','No reproducido','Not reproduced'],['inconclusive','Inconcluso','Inconclusive']];
  const status=[['open','Abierto','Open'],['in_progress','En corrección','In progress'],['reported_fixed','Corrección comunicada','Reported fixed'],['verified_fixed','Corregido y verificado','Verified fixed'],['accepted','Riesgo aceptado','Risk accepted'],['not_verified','No verificable','Not verifiable']];
  const kinds=[['note','Nota','Note'],['command','Comando','Command'],['http','Petición / respuesta HTTP','HTTP request / response'],['image','Captura de pantalla','Screenshot']];
  let renderedKey=null,previewStale=false,previewSnapshot=null,positionTimer,restoring=false,dialogTrigger=null,shortcutSaving=false;
  let filters={status:'',asset:'',owner:'',verification:''};
  const findingTabs=new Map();
  function read(key,fallback){try{return JSON.parse(localStorage.getItem('rg.wb.'+key))??fallback;}catch(_){return fallback;}}
  function write(key,value){try{localStorage.setItem('rg.wb.'+key,JSON.stringify(value));}catch(_){}}
  function b(text,run,primary=false){const el=h('button',{type:'button',class:'btn'+(primary?' primary':'')},text);el.addEventListener('click',async()=>{dialogTrigger=el;el.disabled=true;try{await run(el);}catch(e){toast(e.message,'err');}finally{if(el.isConnected)el.disabled=false;UndoUI.update();}});return el;}
  function labelOf(list,value){const row=list.find(x=>x[0]===value);return row?w(row[1],row[2]):value;}
  function selector(label,items,value,change){const s=h('select',{'aria-label':label},...items.map(x=>h('option',{value:x[0]},x.length===3?w(x[1],x[2]):x[1])));s.value=value;s.addEventListener('change',()=>change(s.value));return h('label',{},label,s);}
  function dialog(title){const trigger=document.activeElement===document.body?dialogTrigger:document.activeElement,d=h('dialog',{class:'experience-dialog workbench-dialog','aria-label':title});const body=h('div',{class:'experience-body'});d.append(h('div',{class:'experience-heading'},h('h2',{},title),b(w('Cerrar','Close'),()=>d.close())),body);d.addEventListener('close',()=>{d.remove();const focus=trigger?.closest('details:not([open])')?.querySelector('summary')||trigger;(focus?.isConnected&&!focus.disabled?focus:$('#editor'))?.focus({preventScroll:true});});document.body.append(d);d.showModal();return {d,body};}
  function position(){
    if(restoring||!S.slug||!['finding','section','report'].includes(S.sel.type))return;
    const entry={...S.sel,scroll:$('#editor').scrollTop,windowScroll:scrollY};
    if(S.sel.type==='finding')entry.uid=S.data.findings[S.sel.idx]?.uid;
    if(S.sel.type==='finding'&&!entry.uid)return;
    write('resume.'+S.slug,entry);
    if(entry.uid){const recent=read('recent.'+S.slug,[]).filter(x=>x!==entry.uid);write('recent.'+S.slug,[entry.uid,...recent].slice(0,12));}
  }
  function resume(){
    const p=read('resume.'+S.slug,{});
    let type=p.type||'report',value=p.key??p.idx??-1;
    if(type==='finding'){value=S.data.findings.findIndex(f=>f.uid===p.uid);if(value<0){type='report';value=-1;}}
    if(type==='section'&&!S.data.report.sections.some(s=>s.key===p.key)){type='report';value=-1;}
    select(type,value);restoring=true;
    requestAnimationFrame(()=>{requestAnimationFrame(()=>{$('#editor').scrollTop=Number(p.scroll)||0;if(innerWidth<=760)window.scrollTo(0,Number(p.windowScroll)||0);$('#editor').focus({preventScroll:true});restoring=false;});});
  }
  function projectChanged(){UndoUI.clear();WorkflowUI.resetReview?.();filters=read('filters.'+S.slug,{status:'',asset:'',owner:'',verification:''});renderedKey=null;previewStale=false;previewSnapshot=null;}
  function dirty(){previewStale=true;updatePreview();const title=$('#editor .finding-context-title strong');if(title&&S.sel.type==='finding'){const f=S.data.findings.find(item=>item.uid===renderedFindingUid());title.textContent=f?.title||w('Sin título','Untitled');const chips=$('#editor .finding-chips');if(chips&&f)chips.replaceWith(findingChips(f));}}
  function previewReady(revision=projectStore.revision,snapshot=null){if(snapshot)previewSnapshot={...snapshot,revision};previewStale=revision!==projectStore.revision;updatePreview();followPreview();}
  function hasLivePreview(){return previewSnapshot?.slug===S.slug&&previewSnapshot.document===$('#pdfPreview')?.contentDocument&&previewSnapshot.revision===projectStore.revision;}
  function updatePreview(){const el=$('#previewFreshness');if(el){el.textContent=previewStale?w('Cambios sin reflejar','Preview has older content'):w('Revisión actual','Current revision');el.dataset.stale=String(previewStale);}}
  function followPreview(){
    if(S.previewMode!=='live'||!previewPaneVisible()||previewSnapshot?.slug!==S.slug)return;
    try {
      const doc=$('#pdfPreview').contentDocument;
      if(!doc||doc!==previewSnapshot.document)return;
      doc.querySelectorAll('[data-rg-preview-current]').forEach(el=>el.removeAttribute('data-rg-preview-current'));
      const finding=S.sel.type==='finding'?S.data.findings[S.sel.idx]:null;
      const id=finding?previewSnapshot.findingIds.get(finding.uid):S.sel.type==='section'?S.sel.key:null;
      if(!id)return;
      const target=doc.getElementById(id);if(!target)return;
      if(finding){
        if(!doc.getElementById('rg-preview-selection-style')){
          const style=doc.createElement('style');style.id='rg-preview-selection-style';
          style.textContent='[data-rg-preview-current]{scroll-margin-top:16px}[data-rg-preview-current]>.finding-intro>.f-head{outline:3px solid var(--accent,#0d9488);outline-offset:4px;border-radius:4px}';
          doc.head.append(style);
        }
        target.setAttribute('data-rg-preview-current','');
      }
      // Selection never transfers focus to the read-only, script-free iframe.
      target.scrollIntoView({block:'start',behavior:'instant'});
    }catch(_){}
  }
  function afterRender(){
    update();
    const key=JSON.stringify([S.slug,S.sel]);
    const changed=key!==renderedKey;
    if(changed){$('#editor').scrollTop=0;renderedKey=key;}
    if(S.sel.type==='capture')$('#workspaceContext').textContent=w('Bandeja de captura','Capture inbox');
    if(S.sel.type==='findings')$('#workspaceContext').textContent=w('Hallazgos','Findings');
    $('.layout').classList.toggle('workbench-board',['capture','findings'].includes(S.sel.type));
    if(changed)followPreview();
    ensureLivePreview();
    $('#navFindings')?.classList.toggle('active',S.sel.type==='findings');
    $('#navFindings')?.setAttribute('aria-current',S.sel.type==='findings'?'page':'false');
    requestAnimationFrame(()=>{
      const sticky=$('#editor .finding-context');if(sticky)$('#editor').style.scrollPaddingTop=(sticky.offsetHeight+20)+'px';else $('#editor').style.scrollPaddingTop='24px';
    });
  }
  function update(){
    const pairs={densityBtn:[read('density','comfortable')==='compact'?'Densidad compacta':'Densidad cómoda',read('density','comfortable')==='compact'?'Compact density':'Comfortable density'],
      focusBtn:[read('focus',false)?'Salir de concentración':'Concentración',read('focus',false)?'Exit focus mode':'Focus mode'],
      undoAction:['Deshacer acción','Undo action'],captureBtn:['Captura rápida','Quick capture'],navFindings:['Hallazgos','Findings'],navCaptures:['Bandeja de captura','Capture inbox'],aboutBtn:['Acerca de','About'],shortcutsBtn:['Atajos','Shortcuts'],navWork:['Trabajo del informe','Report work'],navReview:['Revisión y entrega','Review and delivery'],navTools:['Herramientas','Tools']};
    for(const [id,pair] of Object.entries(pairs)){const el=$('#'+id);if(el)el.textContent=w(...pair);}
    const density=$('#densityBtn');if(density){const compact=read('density','comfortable')==='compact',value=compact?w('Compacta','Compact'):w('Cómoda','Comfortable');density.title=w(...pairs.densityBtn);density.setAttribute('aria-label',density.title);density.replaceChildren(...(S.uiLang==='en'?[value,h('span',{class:'density-label'},' density')]:[h('span',{class:'density-label'},'Densidad '),value]));}
    $('#navFindings')?.toggleAttribute('disabled',!S.slug||projectBusyCount>0);$('#captureBtn')?.toggleAttribute('disabled',!S.slug||projectBusyCount>0);$('#navCaptures')?.toggleAttribute('disabled',!S.slug||projectBusyCount>0);
    $('#focusBtn')?.setAttribute('aria-pressed',String(read('focus',false)));$('#densityBtn')?.setAttribute('aria-pressed',String(read('density','comfortable')==='compact'));
    document.body.dataset.density=read('density','comfortable');document.body.classList.toggle('focus-mode',read('focus',false)&&S.sel.type!=='home');
    const nav=$('#navCaptures');if(nav){nav.classList.toggle('active',S.sel.type==='capture');nav.setAttribute('aria-current',S.sel.type==='capture'?'page':'false');}
    const input=$('#globalSearch');if(input){input.placeholder=w('Buscar o ejecutar una acción…','Search or run an action…');input.setAttribute('aria-label',w('Buscar o ejecutar una acción','Search or run an action'));}
    const handle=$('#previewWidth');if(handle)handle.setAttribute('aria-label',w('Ancho de la vista previa','Preview width'));
    const notes=$('#previewFreshness');if(notes)updatePreview();UndoUI.update();
  }
  async function attention(box){
    const slug=S.slug,serial=projectStore.revision;
    box.append(h('h2',{},w('Requiere atención','Needs attention')));
    const items=h('div',{class:'attention-list'}),info=h('p',{role:'status'},w('Comprobando la revisión guardada…','Checking the saved revision…'));box.append(info,items);
    function task(title,description,run){const el=b('',run);el.className='attention-task';el.append(h('strong',{},title),h('span',{},description));items.append(el);}
    const fs=S.data.findings||[],allEvidence=new Set(fs.flatMap(f=>[...(f.evidence_uids||[]),...(f.retests||[]).flatMap(r=>r.evidence_uids||[])]));
    const imports=fs.filter(f=>f.import_source&&!f.import_source.reviewed);
    if(imports.length)task(imports.length+' '+(imports.length===1?w('importación por revisar','import to review'):w('importaciones por revisar','imports to review')),imports[0].id+' / '+imports[0].title,()=>{select('finding',S.data.findings.findIndex(f=>f.uid===imports[0].uid));WorkflowUI.navigateIssue({finding_uid:imports[0].uid,path:'import_source'});});
    const unlinked=(S.data.evidence||[]).filter(e=>!allEvidence.has(e.uid));
    if(unlinked.length)task(unlinked.length+' '+w('evidencias sin vincular','unlinked evidence items'),w('Asócialas a un hallazgo o revisa si son necesarias.','Link them to a finding or review whether they are needed.'),()=>select('workflow','evidence'));
    const retests=fs.filter(f=>f.status==='reported_fixed');
    if(retests.length)task(retests.length+' '+(retests.length===1?w('corrección por verificar','reported fix to verify'):w('correcciones por verificar','reported fixes to verify')),w('El cliente comunicó una corrección. Falta comprobarla.','A fix was reported. Verification is still pending.'),()=>{S.retestFinding=retests[0].uid;select('workflow','retest');});
    const pending=(S.data.capture_inbox||[]).filter(c=>!S.data.findings.some(f=>f.uid===c.finding_uid));
    if(pending.length)task(pending.length+' '+w('capturas por incorporar','captures to triage'),w('Notas privadas fuera del informe.','Private notes outside the report.'),()=>select('capture'));
    try {
      if(!await doSave())throw Error(w('Guarda los cambios para revisar la entrega.','Save changes to review the delivery.'));
      const r=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+'/review?lang='+S.uiLang));const report=await r.json();
      if(!box.isConnected||slug!==S.slug||serial!==projectStore.revision)return;
      const issues=report.issues.filter(i=>!i.path.endsWith('.import_source'));
      const blockers=issues.filter(i=>i.level==='error');
      if(blockers.length)task(blockers.length+' '+w('problemas que bloquean la entrega','delivery blockers'),w('Abrir el primer campo que requiere corrección.','Open the first field requiring correction.'),()=>WorkflowUI.navigateIssue(blockers[0]));
      const warnings=issues.filter(i=>i.level!=='error');
      if(warnings.length)task(warnings.length+' '+w('avisos de revisión','review warnings'),w('Comprobar campos, pasos, cobertura y referencias.','Check fields, steps, coverage and references.'),()=>select('workflow','review'));
      info.textContent=items.children.length?w('Pendientes concretos de este proyecto.','Actionable items in this project.'):w('Estas comprobaciones no detectaron pendientes. La revisión técnica sigue a tu cargo.','No pending items were detected by these checks. Technical review remains your responsibility.');
    }catch(e){if(box.isConnected){info.textContent=e.message;items.append(b(w('Reintentar','Retry'),()=>renderMain()));}}
  }
  function recentFindings(){const order=read('recent.'+S.slug,[]);return [...S.data.findings].sort((a,b)=>{const ai=order.indexOf(a.uid),bi=order.indexOf(b.uid);return (ai<0?999:ai)-(bi<0?999:bi);}).slice(0,6);}
  function findingChips(f){
    const list=h('ul',{class:'finding-chips','aria-label':w('Contexto registrado del hallazgo','Recorded finding context')});
    const assets=new Map((S.data.assets||[]).map(a=>[a.uid,a])),evidence=new Set((S.data.evidence||[]).map(e=>e.uid));
    const refs=[...new Set(f.asset_uids||[])],names=refs.filter(uid=>assets.has(uid)).map(uid=>{const a=assets.get(uid);return a.name||a.target||w('Sin nombre','Unnamed');}),missing=refs.filter(uid=>!assets.has(uid)).length;
    const evidenceRefs=[...new Set(f.evidence_uids||[])],linked=evidenceRefs.filter(uid=>evidence.has(uid)).length,missingEvidence=evidenceRefs.length-linked;
    const assetText=(names.join(' · ')||w('Sin activos vinculados','No linked assets'))+(missing?' · '+missing+' '+w('referencias inexistentes','missing references'):'');
    const statusText=f.status?labelOf(status,f.status):w('Abierto (predeterminado)','Open (default)');
    const rows=[['assets',w('Activos','Assets'),assetText],['owner',w('Responsable','Owner'),f.owner||w('Sin asignar','Unassigned')],['status',w('Estado','Status'),statusText],['evidence',w('Evidencias vinculadas','Linked evidence'),String(linked)+(missingEvidence?' · '+missingEvidence+' '+w('referencias inexistentes','missing references'):'')]];
    for(const [key,label,value] of rows)list.append(h('li',{'data-finding-chip':key},h('span',{},label+': '),h('strong',{},value)));
    return list;
  }
  function renderedFindingUid(){return $('#editor .finding-context')?.dataset.findingContextUid||null;}
  function moveFinding(offset,expectedUid=renderedFindingUid(),expectedSlug=S.slug){
    if(S.sel.type!=='finding'||S.slug!==expectedSlug||projectBusyCount>0||projectStore.loading)return false;
    const current=S.data.findings.findIndex(item=>item.uid===expectedUid);
    if(current<0){toast(w('Este hallazgo ya no está en el proyecto.','This finding is no longer in the project.'),'err');select('report',-1);$('#editor').focus();return false;}
    const next=S.data.findings[current+offset];if(!next)return false;
    const uid=next.uid;select('finding',current+offset);
    requestAnimationFrame(()=>{if(S.slug===expectedSlug&&S.sel.type==='finding'&&S.data.findings[S.sel.idx]?.uid===uid)$('#editor .finding-context-title strong')?.focus();});
    return true;
  }
  async function saveAndNext(){
    if(shortcutSaving||!S.slug||S.sel.type!=='finding'||projectBusyCount>0||projectStore.loading)return;
    const slug=S.slug,uid=renderedFindingUid(),revision=projectStore.revision,selection=JSON.stringify(S.sel);
    if(!uid)return;
    shortcutSaving=true;
    try{
      if(!await doSave())return;
      if(S.slug!==slug||selection!==JSON.stringify(S.sel)||renderedFindingUid()!==uid||!S.data.findings.some(f=>f.uid===uid)||projectStore.revision!==revision||projectStore.dirty){toast(w('La selección o el contenido cambió mientras se guardaba. Repite el atajo para continuar.','Selection or content changed while saving. Repeat the shortcut to continue.'),'err');return;}
      if(!moveFinding(1,uid,slug))toast(w('Guardado. Este es el último hallazgo.','Saved. This is the last finding.'),'ok');
    }finally{shortcutSaving=false;}
  }
  function shortcutHelp(){
    const {body}=dialog(w('Atajos de teclado','Keyboard shortcuts'));
    body.append(h('p',{},w('j y k recorren el orden completo del proyecto con un hallazgo abierto. No se activan al escribir. Ctrl+Enter guarda el hallazgo y avanza solo si el guardado finaliza sin conflicto y la selección sigue igual.','j and k follow the complete project order with a finding open. They do not run while typing. Ctrl+Enter saves the finding and advances only after a successful save with an unchanged selection.')));
    const list=h('dl',{class:'shortcut-list'});
    for(const [key,es,en] of [['j','Siguiente hallazgo','Next finding'],['k','Hallazgo anterior','Previous finding'],['Ctrl+Enter / ⌘+Enter','Guardar y siguiente (dentro del editor de hallazgo)','Save and next (inside the finding editor)'],['?','Abrir esta ayuda fuera de campos','Open this help outside fields'],['Ctrl+K / ⌘+K','Buscar o ejecutar una acción','Search or run an action'],['Ctrl+S / ⌘+S','Guardar proyecto','Save project']])list.append(h('dt',{},h('kbd',{},key)),h('dd',{},w(es,en)));
    body.append(list,h('p',{},w('Los atajos de hallazgo y la ayuda quedan suspendidos en diálogos, búsquedas abiertas y operaciones del proyecto.','Finding shortcuts and help are suspended in dialogs, open search results and project operations.')));
  }
  function shortcut(event){
    if(event.defaultPrevented||event.isComposing||event.repeat||event.altKey||projectBusyCount>0||projectStore.loading||document.querySelector('dialog[open],.modal.open:not(dialog)')||$('#searchResults')?.classList.contains('open'))return;
    const target=event.target,editable=target?.closest('input,textarea,select,[contenteditable]:not([contenteditable="false"]),[role="textbox"]');
    if((event.ctrlKey||event.metaKey)&&event.key==='Enter'&&!event.shiftKey){
      if(target?.closest('[data-finding-decisions]')){event.preventDefault();return;}
      if(S.sel.type==='finding'&&$('#editor')?.contains(target)&&!target?.closest('[contenteditable]:not([contenteditable="false"])')){event.preventDefault();saveAndNext().catch(e=>toast(e.message,'err'));}return;
    }
    if(editable||event.ctrlKey||event.metaKey)return;
    if(event.key==='?'){event.preventDefault();shortcutHelp();return;}
    if(event.shiftKey||S.sel.type!=='finding'||!['j','k'].includes(event.key))return;
    event.preventDefault();moveFinding(event.key==='j'?1:-1);
  }
  function findingWorkspace(part,f){
    const slug=S.slug, key=slug+'|'+f.uid, id='finding-workspace-'+f.uid;
    const evidence=h('div',{role:'tabpanel',id:id+'-evidence','aria-labelledby':id+'-tab-evidence','data-finding-panel':'evidence',tabindex:'0'});
    while(part.firstChild)evidence.append(part.firstChild);
    const gallery=h('div',{'data-finding-gallery':f.uid});evidence.append(gallery);
    evidence.querySelector('[data-field="evidence_uids"]')?.addEventListener('change',()=>{
      if(gallery.isConnected&&S.slug===slug&&renderedFindingUid()===f.uid){gallery.replaceChildren();WorkflowUI.findingEvidence?.(gallery,f.uid);}
    });
    const decisions=h('div',{role:'tabpanel',id:id+'-decisions','aria-labelledby':id+'-tab-decisions','data-finding-panel':'decisions','data-workpart':'decisions',tabindex:'0'});
    const content=h('div',{'data-finding-decisions':f.uid});decisions.append(h('h3',{},w('Decisiones del hallazgo','Finding decisions')),content);
    part.dataset.findingWorkspaceUid=f.uid;
    const tabs=h('div',{class:'finding-workspace-tabs',role:'tablist','aria-label':w('Evidencia y decisiones del hallazgo','Finding evidence and decisions')});
    let evidenceLoaded=false,decisionsLoaded=false;
    function load(panel){
      requestAnimationFrame(()=>{
        if(!part.isConnected||S.slug!==slug||renderedFindingUid()!==f.uid)return;
        if(panel==='evidence'&&!evidenceLoaded){evidenceLoaded=true;WorkflowUI.findingEvidence?.(gallery,f.uid);}
        if(panel==='decisions'&&!decisionsLoaded){decisionsLoaded=true;InsightsUI.renderFinding(content,f.uid);}
      });
    }
    function activate(panel,focus=false){
      if(!['evidence','decisions'].includes(panel))return;
      findingTabs.set(key,panel);if(findingTabs.size>500)findingTabs.delete(findingTabs.keys().next().value);
      for(const button of tabs.children){const active=button.dataset.findingTab===panel;button.setAttribute('aria-selected',String(active));button.tabIndex=active?0:-1;}
      evidence.hidden=panel!=='evidence';decisions.hidden=panel!=='decisions';load(panel);
      if(focus)tabs.querySelector('[data-finding-tab="'+panel+'"]')?.focus({preventScroll:true});
    }
    for(const [panel,es,en]of [['evidence','Evidencias','Evidence'],['decisions','Decisiones','Decisions']]){
      const button=h('button',{type:'button',role:'tab',id:id+'-tab-'+panel,'aria-controls':id+'-'+panel,'data-finding-tab':panel,onclick:()=>activate(panel)},w(es,en));
      button.addEventListener('keydown',event=>{
        const list=[...tabs.children],index=list.indexOf(button);let next;
        if(event.key==='ArrowRight')next=(index+1)%list.length;else if(event.key==='ArrowLeft')next=(index+list.length-1)%list.length;else if(event.key==='Home')next=0;else if(event.key==='End')next=list.length-1;else return;
        event.preventDefault();list[next].focus({preventScroll:true});
      });tabs.append(button);
    }
    part.append(h('h3',{},w('Evidencia y decisiones','Evidence and decisions')),h('details',{class:'finding-workspace-help'},h('summary',{},w('Cómo usar estas pestañas','How to use these tabs')),h('p',{},w('Las pestañas conservan los campos del hallazgo y los borradores de decisiones. Usa las flechas para elegir una pestaña y Enter o Espacio para abrirla. Consultar datos no guarda ni confirma una vulnerabilidad. Las decisiones usan su botón de guardar; Ctrl+Enter o ⌘+Enter no guarda ni cambia de hallazgo mientras editas esos formularios.','Tabs preserve finding fields and decision drafts. Use arrow keys to choose a tab and Enter or Space to open it. Reading data does not save or confirm a vulnerability. Decisions use their own save button; Ctrl+Enter or ⌘+Enter does not save or change findings while editing those forms.'))),tabs,evidence,decisions);
    part.addEventListener('report-gen:finding-tab',event=>activate(event.detail?.panel,event.detail?.focus));
    activate(findingTabs.get(key)||'evidence');
  }
  function revealFindingPart(key){
    const part=$('#editor [data-finding-workspace-uid]');
    if(part&&['evidence','decisions'].includes(key))part.dispatchEvent(new CustomEvent('report-gen:finding-tab',{detail:{panel:key}}));
    return $('#editor [data-workpart="'+key+'"]');
  }
  function revealFindingField(field){
    const panel=field?.closest('[data-finding-panel]');if(panel)revealFindingPart(panel.dataset.findingPanel);
  }
  function findingNavigation(wrap,f){
    const original=wrap.firstElementChild;original.classList.add('finding-actions');
    const head=h('div',{class:'finding-context','data-finding-context-uid':f.uid},h('div',{class:'finding-context-title'},h('span',{class:'mono'},f.id),h('strong',{tabindex:'-1'},f.title||w('Sin título','Untitled')),h('span',{class:'workspace-severity'},f.mode==='machine'?w('Máquina','Machine'):labelOf(status,f.status||'open'))));
    const slug=S.slug,index=S.data.findings.findIndex(item=>item.uid===f.uid),total=S.data.findings.length;
    const sequence=h('nav',{class:'finding-sequence','aria-label':w('Hallazgos en el orden del proyecto','Findings in project order')});
    const move=offset=>moveFinding(offset,f.uid,slug);
    for(const [offset,es,en] of [[-1,'Anterior','Previous'],[1,'Siguiente','Next']]){
      const target=S.data.findings[index+offset],label=w(es,en);
      sequence.append(h('button',{type:'button',class:'btn','data-finding-step':String(offset),disabled:!target||projectBusyCount>0||projectStore.loading?'':null,'aria-label':label+' '+w('hallazgo','finding')+(target?' '+target.id:''),onclick:()=>move(offset)},offset<0?'‹ '+label:label+' ›'));
    }
    sequence.append(h('span',{class:'finding-sequence-position',role:'status','data-finding-position-label':''},(index+1)+' '+w('de','of')+' '+total+' · '+w('orden del proyecto','project order')));
    head.append(findingChips(f),sequence);
    if(typeof WorkflowUI!=='undefined')WorkflowUI.reviewControls?.(head);
    const nav=h('nav',{class:'finding-tabs','aria-label':w('Apartados del hallazgo','Finding sections')});
    for(const [key,es,en] of [['description','Descripción','Description'],['reproduction','Reproducción','Reproduction'],['evidence','Evidencias','Evidence'],['decisions','Decisiones','Decisions'],['remediation','Remediación','Remediation']]){
      const target=wrap.querySelector('[data-workpart="'+key+'"]');if(!target)continue;
      nav.append(b(w(es,en),()=>{revealFindingPart(key);target.scrollIntoView({block:'start'});target.querySelector('input,textarea,select,button')?.focus({preventScroll:true});}));
    }
    head.append(nav);wrap.prepend(head);
  }
  function filterRows(rows){return rows.filter(({f})=>(!filters.status||(f.status||'open')===filters.status)&&(!filters.owner||f.owner===filters.owner)&&(!filters.asset||(f.asset_uids||[]).includes(filters.asset))&&(!filters.verification||(f.verification||'')===filters.verification));}
  function filterBar(){
    const box=h('div',{class:'finding-filters'});const all=[['',w('Todos','All')]];
    const apply=(key,value)=>{filters[key]=value;write('filters.'+S.slug,filters);renderMain();};
    box.append(selector(w('Estado','Status'),[...all,...status],filters.status,v=>apply('status',v)),selector(w('Activo','Asset'),[...all,...S.data.assets.map(a=>[a.uid,a.name||a.target])],filters.asset,v=>apply('asset',v)),selector(w('Responsable','Owner'),[...all,...[...new Set(S.data.findings.map(f=>f.owner).filter(Boolean))].sort().map(o=>[o,o])],filters.owner,v=>apply('owner',v)),selector(w('Verificación técnica','Technical verification'),[...all,...verification.slice(1)],filters.verification,v=>apply('verification',v)));
    const views=read('views.'+S.slug,[]);const controls=h('div',{class:'filter-actions'});
    controls.append(selector(w('Vistas guardadas','Saved views'),[['',w('Elegir vista','Choose view')],...views.map((v,i)=>[String(i),v.name])],'',v=>{if(v==='')return;filters={...views[Number(v)].filters};S.dashFilter=views[Number(v)].severity||null;write('filters.'+S.slug,filters);renderMain();}),b(w('Guardar vista','Save view'),()=>{const {d,body}=dialog(w('Guardar vista','Save view'));const name=h('input',{maxlength:80,'aria-label':w('Nombre de la vista','View name')});body.append(h('label',{},w('Nombre','Name'),name),b(w('Guardar','Save'),()=>{if(!name.value.trim())throw Error(w('Escribe un nombre.','Enter a name.'));const current=read('views.'+S.slug,[]).filter(v=>v.name!==name.value.trim());write('views.'+S.slug,[...current,{name:name.value.trim(),filters:{...filters},severity:S.dashFilter}].slice(-20));d.close();renderMain();},true));name.focus();}),b(w('Limpiar filtros','Clear filters'),()=>{filters={status:'',asset:'',owner:'',verification:''};S.dashFilter=null;write('filters.'+S.slug,filters);renderMain();}));
    if(views.length)controls.append(b(w('Gestionar vistas','Manage views'),()=>{const {body}=dialog(w('Vistas guardadas','Saved views'));views.forEach((v,i)=>body.append(h('div',{class:'row'},h('span',{},v.name),b(w('Eliminar','Delete'),el=>{const list=read('views.'+S.slug,[]).filter(x=>x.name!==v.name);write('views.'+S.slug,list);el.parentElement.remove();}))));}));
    box.append(controls);return box;
  }
  function commands(){return [
    [w('Crear hallazgo','Create finding'),()=>addFinding('blank')],
    [w('Captura rápida','Quick capture'),capture],
    [w('Ir a evidencias','Go to evidence'),()=>select('workflow','evidence')],
    [w('Comparar entregas','Compare deliveries'),()=>select('workflow','history')],
    [w('Revisar entrega','Review delivery'),()=>select('workflow','review')],
    [w('Importar resultados','Import results'),()=>ProgressUI.intake()],
    [w('Continuar informe','Continue report'),resume],
    [w('Abrir bandeja de captura','Open capture inbox'),()=>select('capture')]
  ];}
  function search(query){
    const box=$('#searchResults');box.replaceChildren();if(!S.data){box.classList.remove('open');return;}
    const q=query.trim().toLowerCase();box.classList.add('open');
    function result(title,detail,run){const el=b('',()=>{box.classList.remove('open');$('#globalSearch').value='';return run();});el.className='search-item';el.append(h('strong',{},title),h('span',{},detail));box.append(el);}
    commands().filter(([name])=>!q||name.toLowerCase().includes(q)).forEach(([name,run])=>result(name,w('Acción','Action'),run));
    searchProject(q).slice(0,20).forEach(r=>result(r.where,r.snippet.pre+r.snippet.mid+r.snippet.post,()=>navTo(r.nav)));
    if(!box.childNodes.length)box.append(h('p',{},t('search_none')));
  }
  async function mutate(path,body){
    const slug=S.slug;busyProject(true);
    try {if(!await doSave())throw Error(w('No se pudo guardar.','Could not save.'));
      const r=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(slug)+path,{method:'POST',headers:{'Content-Type':'application/json','If-Match':projectStore.etag},body:JSON.stringify(body)}));
      const result=await r.json();S.data=result.data;projectStore.data=S.data;projectStore.base=JSON.parse(JSON.stringify(S.data));projectStore.etag=r.headers.get('ETag');projectStore.lastSavedAt=new Date();UndoUI.clear();ProgressUI.saveState('saved');renderSidebar();renderMain();dirty();if(S.previewMode==='live')refreshLivePreview();return result;
    }finally{busyProject(false);}
  }
  function capture(recovered=null){
    if(recovered?.format!=='report-gen-pending')recovered=null;
    if(!S.slug)return;const slug=S.slug,enabled=typeof PendingUI!=='undefined',retained=enabled?PendingUI.active.get(slug+'|capture')?.read():null;
    const initial=recovered?{data:recovered.data,file:recovered.file}:retained||{data:{kind:'note',title:'',note:'',raw_text:''},file:null};
    const {d,body}=dialog(w('Captura rápida','Quick capture'));let kind=initial.data.kind,imageFile=initial.file;
    const title=h('input',{value:initial.data.title,maxlength:300,'data-capture-title':'','aria-label':w('Título','Title')}),note=h('textarea',{rows:2,maxlength:8000,'data-capture-note':''}),text=h('textarea',{rows:8,maxlength:131072,'data-capture-text':'',spellcheck:'false'});note.value=initial.data.note;text.value=initial.data.raw_text;
    const imageInput=h('input',{type:'file',accept:'image/png,image/jpeg,image/webp,image/gif','data-capture-image':''});
    const imageState=h('p',{role:'status'},imageFile?.name||''),imageBox=h('div',{},h('label',{},w('Imagen','Image'),imageInput),imageState),textBox=h('label',{},w('Contenido original','Original content'),text);imageBox.hidden=kind!=='image';textBox.hidden=kind==='image';
    const choose=selector(w('Tipo','Type'),kinds,kind,v=>{kind=v;imageBox.hidden=v!=='image';textBox.hidden=v==='image';});choose.querySelector('select').dataset.captureKind='';
    body.append(h('p',{},w('Se guarda en la bandeja privada. Solo pasa al informe cuando lo incorporas a un hallazgo.','Saved to the private inbox. It enters the report only when you link it to a finding.')),choose,h('label',{},w('Título','Title'),title),textBox,imageBox,h('label',{},w('Contexto / nota','Context / note'),note));
    const read=()=>({data:{kind,title:title.value,note:note.value,raw_text:text.value},file:imageFile});
    const captureActions=h('div',{class:'studio-actions'});
    const pending=enabled?PendingUI.track('capture',w('Captura rápida pendiente','Pending quick capture'),read,{origin:recovered}):null;
    if(pending){body.append(PendingUI.status(pending));captureActions.append(b(w('Descartar formulario pendiente','Discard pending form'),async()=>{if(!confirm(w('¿Descartar el formulario y su copia local?','Discard the form and its local copy?')))return;if(await PendingUI.clear(pending))d.close();}));if(recovered)PendingUI.changed(pending);}
    const protect=()=>{if(pending)PendingUI.changed(pending);};
    imageInput.addEventListener('change',()=>{imageFile=imageInput.files[0];imageState.textContent=imageFile?.name||'';});
    body.addEventListener('input',protect);body.addEventListener('change',protect);
    d.addEventListener('paste',e=>{const file=[...(e.clipboardData?.files||[])].find(f=>f.type.startsWith('image/'));if(file){e.preventDefault();imageFile=file;kind='image';choose.querySelector('select').value='image';imageBox.hidden=false;textBox.hidden=true;imageState.textContent=w('Imagen pegada: ','Pasted image: ')+file.name;if(!title.value)title.value=w('Captura de pantalla','Screenshot');protect();}});
    body.append(captureActions);captureActions.append(b(w('Guardar en bandeja','Save to inbox'),async()=>{
      if(slug!==S.slug)throw Error(w('El proyecto cambió.','The project changed.'));if(!title.value.trim())throw Error(w('Escribe un título.','Enter a title.'));
      const snapshot=read(),revision=pending?.revision,payload={kind:snapshot.data.kind,title:snapshot.data.title.trim(),note:snapshot.data.note,raw_text:snapshot.data.kind==='image'?'':snapshot.data.raw_text};
      busyProject(true);try{if(!await doSave())throw Error(w('No se pudo guardar.','Could not save.'));if(slug!==S.slug)throw Error(w('El proyecto cambió.','The project changed.'));
        if(payload.kind==='image'){if(!snapshot.file)throw Error(w('Selecciona o pega una imagen.','Select or paste an image.'));const upload=await sendImage(snapshot.file);if(!upload)throw Error(w('No se pudo subir la imagen.','Image upload failed.'));payload.src=upload.src;}
        if(slug!==S.slug)throw Error(w('El proyecto cambió.','The project changed.'));await mutate('/captures',payload);
        const cleanup=pending?await PendingUI.committed(pending,revision):{finished:true};if(cleanup.finished)d.close();toast(cleanup.warning?w('Captura guardada. No se pudo eliminar su copia local; revísala en Datos privados guardados.','Capture saved. Its local copy could not be deleted; review Stored private data.'):w('Captura guardada en la bandeja.','Capture saved to inbox.'),'ok');
      }finally{busyProject(false);}
    },true));title.focus();
  }
  function inbox(el){
    el.append(h('h2',{},w('Bandeja de captura','Capture inbox')),h('p',{},w('Notas, comandos y capturas privadas. Revisa el contenido antes de incorporarlo al informe. Los respaldos editables incluyen la bandeja y sus originales.','Private notes, commands and screenshots. Review content before adding it to the report. Editable backups include the inbox and its originals.')),b(w('Nueva captura','New capture'),capture,true));
    const rows=S.data.capture_inbox||[];const list=h('div',{class:'capture-list'});let showAll=false;
    el.append(h('label',{class:'wf-check'},h('input',{type:'checkbox',onchange:e=>{showAll=e.target.checked;draw();}}),w('Mostrar también las incorporadas','Also show linked captures')),list);
    function draw(){list.replaceChildren();rows.forEach((item,index)=>{
      const liveLink=S.data.findings.some(f=>f.uid===item.finding_uid);if(liveLink&&!showAll)return;
      const c=h('article',{class:'card capture-card','data-capture':item.uid},h('h3',{},item.title),h('small',{},labelOf(kinds,item.kind)+' / '+item.created));
      c.append(h('p',{},item.note));
      if(item.kind==='image')c.append(h('img',{src:'/api/projects/'+encodeURIComponent(S.slug)+'/'+item.src,alt:item.title,loading:'lazy'}));
      else c.append(h('pre',{},item.raw_text));
      const provenance=h('details',{},h('summary',{},w('Procedencia','Provenance')),h('code',{},'SHA-256 '+item.sha256));c.append(provenance);
      if(liveLink){const f=S.data.findings.find(f=>f.uid===item.finding_uid);c.append(f?b(w('Abrir hallazgo: ','Open finding: ')+f.id,()=>select('finding',S.data.findings.indexOf(f))):h('p',{},w('El hallazgo vinculado fue eliminado. La captura original se conserva.','The linked finding was deleted. The original capture is retained.')));}
      else {let selected='';const options=[['',w('Seleccionar hallazgo','Choose finding')],...S.data.findings.map(f=>[f.uid,f.id+' / '+f.title])];c.append(selector(w('Incorporar a','Add to'),options,'',v=>selected=v),b(w('Incorporar al hallazgo','Add to finding'),async()=>{if(!selected)throw Error(w('Selecciona un hallazgo.','Choose a finding.'));await mutate('/captures/'+item.uid+'/link',{finding_uid:selected});},true));}
      c.append(b(w('Retirar de la bandeja','Remove from inbox'),()=>{UndoUI.remove(rows,index);scheduleSave();renderMain();}));list.append(c);
    });if(!list.childNodes.length)list.append(h('p',{},w('No hay capturas pendientes. Pega una imagen o guarda un comando con Captura rápida.','No pending captures. Paste an image or save a command using Quick capture.')));}
    draw();
  }
  function about(){const {body}=dialog(w('Acerca de report-gen','About report-gen'));body.append(h('img',{src:'/static/brand-mark.webp',width:240,height:160,alt:'Prometeo & Evaristo'}),h('p',{},'report-gen '+S.version),h('p',{},w('Desarrollado por Sebastián Latorre Muñoz / IphobiusS.','Developed by Sebastián Latorre Muñoz / IphobiusS.')),h('a',{href:'https://github.com/IphobiusS/',target:'_blank',rel:'noopener noreferrer'},'GitHub'),h('p',{},w('Trabajo local. Las capturas se incorporan al informe solo cuando tú lo decides.','Local workspace. Captures enter the report only when you choose.')));}
  function bind(){
    $('.brand-logo').src='/static/brand-symbol.svg';$('.app-credit')?.remove();
    const preferences=$('.workspace-preferences');for(const [id,run] of [['densityBtn',()=>{write('density',read('density','comfortable')==='compact'?'comfortable':'compact');update();}],['focusBtn',()=>{write('focus',!read('focus',false));update();}],['shortcutsBtn',shortcutHelp],['aboutBtn',about]]){const el=b('',run);el.id=id;preferences.append(el);}
    const quick=b('',capture,true);quick.id='captureBtn';$('#projectActionsList').prepend(quick);
    const undo=b('',()=>UndoUI.undo());undo.id='undoAction';$('#projectActionsList').prepend(undo);
    const board=b('',()=>select('findings'));board.id='navFindings';board.className='navitem';$('#navReport').after(board);
    const nav=b('',()=>select('capture'));nav.id='navCaptures';nav.className='navitem';$('#workflowNav').prepend(nav);
    const sidebar=$('.sidebar');
    const work=h('section',{class:'navigation-group'},h('h2',{id:'navWork',class:'side-head'}));
    [...sidebar.children].filter(x=>x.classList.contains('side-sec')&&x.id!=='workflowNav').forEach(x=>work.append(x));
    [nav,...['evidence','assets','coverage'].map(k=>$('[data-workflow="'+k+'"]'))].forEach(x=>work.append(x));
    const review=h('section',{class:'navigation-group'},h('h2',{id:'navReview',class:'side-head'}));['review','history','retest','retest_diff','retest_matrix'].forEach(k=>review.append($('[data-workflow="'+k+'"]')));
    const util=$('.workspace-utilities');util.querySelector('.side-head').id='navTools';util.querySelector('.side-head').removeAttribute('data-workspace-text');util.prepend($('[data-workflow="backup"]'));sidebar.prepend(work,review);$('#workflowNav').remove();
    const fresh=h('span',{id:'previewFreshness',role:'status'});$('.preview-head').append(fresh);
    const range=h('input',{type:'range',id:'previewWidth',min:25,max:55,value:read('previewWidth',36)});range.addEventListener('input',()=>{document.documentElement.style.setProperty('--preview-width',range.value+'%');write('previewWidth',Number(range.value));});$('.preview-head').append(range);document.documentElement.style.setProperty('--preview-width',range.value+'%');
    window.addEventListener('resize',()=>{followPreview();ensureLivePreview();});
    $('#editor').addEventListener('scroll',()=>{clearTimeout(positionTimer);positionTimer=setTimeout(position,150);});window.addEventListener('scroll',()=>{clearTimeout(positionTimer);positionTimer=setTimeout(position,150);});
    window.addEventListener('pagehide',position);
    $('#globalSearch').addEventListener('focus',()=>search($('#globalSearch').value));
    document.addEventListener('keydown',e=>{const box=$('#searchResults');if(box.classList.contains('open')&&(e.target===$('#globalSearch')||box.contains(e.target))){const items=[...box.querySelectorAll('button')];let index=items.indexOf(document.activeElement);if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();index=(index+(e.key==='ArrowDown'?1:-1)+items.length)%items.length;items[index]?.focus();}if(e.key==='Enter'&&e.target===$('#globalSearch')){e.preventDefault();items[0]?.click();}}});
    document.addEventListener('keydown',shortcut);
    update();
  }
  return {bind,update,afterRender,position,resume,projectChanged,dirty,previewReady,hasLivePreview,followPreview,attention,recentFindings,findingNavigation,findingWorkspace,revealFindingPart,revealFindingField,renderedFindingUid,findingChips,filterRows,filterBar,search,capture,inbox,verification,labelOf,status};
})();
