/* Contextual navigation is a UI preference. It never writes report data. */
const ContextIndexUI = (() => {
  'use strict';
  const PAGE_SIZE=50, modes=['sections','findings'];
  const w=(es,en,pt)=>uiText(es,en,pt);
  let bound=false,scope=null,prefs=null,sorting=false,lastSelection=null,trigger=null,renderSerial=0;
  const defaults=()=>({open:true,width:280,mode:'sections',sections:{query:'',page:0},findings:{query:'',severity:'',kind:'',page:0}});
  function normalizeQuery(value){return String(value??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();}
  function widthValue(value){const n=Number(value);return Number.isFinite(n)?Math.max(220,Math.min(420,Math.round(n/20)*20)):280;}
  function storageKey(){return S.workspace_id&&S.slug?'rg.wb.workspace.'+S.workspace_id+'.context-index.'+encodeURIComponent(S.slug):null;}
  function sanitize(value){
    const clean=defaults();
    if(!value||typeof value!=='object')return clean;
    if(typeof value.open==='boolean')clean.open=value.open;
    if(modes.includes(value.mode))clean.mode=value.mode;
    clean.width=widthValue(value.width??280);
    for(const mode of modes){
      const row=value[mode];
      if(!row||typeof row!=='object')continue;
      if(typeof row.query==='string')clean[mode].query=row.query.slice(0,300);
      if(Number.isSafeInteger(row.page)&&row.page>=0)clean[mode].page=row.page;
      if(mode==='findings'){
        if(['','critical','high','medium','low','info','pending'].includes(row.severity))clean.findings.severity=row.severity;
        if(['','vuln','machine'].includes(row.kind))clean.findings.kind=row.kind;
      }
    }
    return clean;
  }
  function ensureScope(){
    const key=storageKey();
    if(prefs&&key===scope)return;
    scope=key;sorting=false;lastSelection=null;
    let stored=null;try{if(key)stored=JSON.parse(localStorage.getItem(key));}catch(_){}
    prefs=sanitize(stored);
  }
  function persist(){if(!scope)return;try{localStorage.setItem(scope,JSON.stringify(prefs));}catch(_){}}
  function projectChanged(){scope=null;prefs=null;sorting=false;lastSelection=null;}
  function eligible(){return !!S.slug&&!!S.data&&['report','section','finding','findings'].includes(S.sel.type);}
  function mobile(){return window.matchMedia('(max-width:760px)').matches;}
  function selection(){
    if(S.sel.type==='section')return {type:'section',key:S.sel.key};
    if(S.sel.type==='finding'){const finding=S.data?.findings?.[S.sel.idx];return finding?{type:'finding',uid:finding.uid,id:finding.id}:null;}
    return null;
  }
  function rowsFor(mode){
    if(mode==='sections')return (S.data?.report?.sections||[]).map((section,index)=>({identity:section.key,index,id:section.key,title:sectionTitle(section),section}));
    return (S.data?.findings||[]).map((finding,index)=>({identity:finding.uid,index,id:finding.id||'',title:finding.title||t('untitled'),finding}));
  }
  function matches(row,mode){
    const f=prefs[mode],query=normalizeQuery(f.query);
    if(query&&!normalizeQuery(row.id+' '+row.title).includes(query))return false;
    if(mode==='findings'){
      const kind=row.finding.mode==='machine'?'machine':'vuln';
      if(f.kind&&kind!==f.kind)return false;
      if(f.severity&&(row.finding.severity||'pending')!==f.severity)return false;
    }
    return true;
  }
  function selectedIdentity(mode){
    const current=selection();
    return mode==='sections'&&current?.type==='section'?current.key:mode==='findings'&&current?.type==='finding'?current.uid:null;
  }
  function view(){
    ensureScope();const mode=prefs.mode,all=rowsFor(mode),rows=all.filter(row=>matches(row,mode)),identity=selectedIdentity(mode);
    return {mode,all,rows,identity,selectedIndex:rows.findIndex(row=>row.identity===identity)};
  }
  function state(){
    const v=view(),current=selection();
    return {mode:prefs.mode,open:prefs.open,visible:prefs.open&&eligible(),width:prefs.width,...prefs[prefs.mode],severity:prefs[prefs.mode].severity||'',kind:prefs[prefs.mode].kind||'',sorting,total:v.all.length,matched:v.rows.length,selected:current?{...current,visible:v.selectedIndex>=0&&Math.floor(v.selectedIndex/PAGE_SIZE)===prefs[prefs.mode].page}:null};
  }
  function setWidth(value){ensureScope();prefs.width=widthValue(value);persist();applyVisibility();$('#contextIndexWidth').value=String(prefs.width);$('#contextIndexWidthValue').textContent=prefs.width+' px';}
  function setPage(value){
    const v=view(),n=Number(value),pages=Math.max(1,Math.ceil(v.rows.length/PAGE_SIZE));
    prefs[prefs.mode].page=Math.max(0,Math.min(pages-1,Number.isFinite(n)?Math.trunc(n):0));persist();render(undefined,{reveal:false});
  }
  function setFilters(value={}){
    ensureScope();const target=prefs[prefs.mode];
    if(typeof value.query==='string')target.query=value.query.slice(0,300);
    if(prefs.mode==='findings'){
      if(Object.hasOwn(value,'severity'))target.severity=['','critical','high','medium','low','info','pending'].includes(value.severity)?value.severity:'';
      if(Object.hasOwn(value,'kind'))target.kind=['','vuln','machine'].includes(value.kind)?value.kind:'';
    }
    target.page=0;persist();render(undefined,{reveal:false});$('#contextIndexListScroll').scrollTop=0;
  }
  function setSorting(value){ensureScope();sorting=!!value&&prefs.mode==='sections';render(undefined,{reveal:false});}
  function close({focus=true}={}){
    ensureScope();prefs.open=false;$('#contextIndexActions').open=false;persist();applyVisibility();
    if(focus){const usable=trigger?.isConnected&&!trigger.closest('[hidden],#contextIndex')&&!(mobile()&&trigger.closest('.sidebar'));const target=usable?trigger:$('#contextIndexToggle');target?.focus({preventScroll:true});}
    if(typeof ensureLivePreview==='function')ensureLivePreview();
  }
  function open(mode=prefs?.mode||'sections',{focus=true}={}){
    ensureScope();if(!modes.includes(mode))mode='sections';
    trigger=document.activeElement;const changed=mode!==prefs.mode;prefs.mode=mode;prefs.open=true;if(changed)sorting=false;persist();
    if(mobile()){$('.layout').classList.remove('navigation-open');$('#sidebarToggle').setAttribute('aria-expanded','false');}
    if(!eligible()){
      const first=S.data?.report?.sections?.[0];
      if(mode==='sections'&&first)select('section',first.key);
      else select(mode==='sections'?'report':'findings',-1);
    }else render(undefined,{reveal:true});
    if(focus)$('#contextIndexSearch').focus({preventScroll:true});
  }
  function toggle(){ensureScope();if(prefs.open&&eligible())close();else open();}
  function setMode(mode){ensureScope();if(!modes.includes(mode))return;if(prefs.mode!==mode)sorting=false;prefs.mode=mode;persist();render(undefined,{reveal:true});}
  function choose(mode,identity){
    const index=rowsFor(mode).findIndex(row=>row.identity===identity);if(index<0)return;
    if(mode==='sections')select('section',identity);else select('finding',index);
    if(mobile())close({focus:false});
    $('#editor').focus({preventScroll:true});
  }
  function revealSelection(){
    ensureScope();const current=selection();if(!current)return;
    prefs.mode=current.type==='section'?'sections':'findings';prefs.open=true;
    const f=prefs[prefs.mode];f.query='';if(prefs.mode==='findings'){f.severity='';f.kind='';}
    const v=view();f.page=Math.max(0,Math.floor(v.selectedIndex/PAGE_SIZE));persist();render(undefined,{reveal:true});
  }
  function revealSelectedRow(){
    if(!bound||$('#contextIndex').hidden)return;
    const v=view();if(v.selectedIndex<0)return;
    prefs[prefs.mode].page=Math.floor(v.selectedIndex/PAGE_SIZE);persist();render(undefined,{reveal:true});
  }
  function revealRow(){
    const panel=$('#contextIndex'),container=$('#contextIndexListScroll'),row=panel?.querySelector('ul:not([hidden]) .finding-nav[aria-current="page"]'),serial=renderSerial;
    if(!row||panel.hidden)return;
    requestAnimationFrame(()=>{if(serial!==renderSerial||!row.isConnected||panel.hidden)return;const item=row.getBoundingClientRect(),bounds=container.getBoundingClientRect();if(!bounds.height)return;if(item.top<bounds.top)container.scrollTop-=bounds.top-item.top;else if(item.bottom>bounds.bottom)container.scrollTop+=item.bottom-bounds.bottom;});
  }
  function applyVisibility(){
    if(!bound||!prefs)return;
    const active=eligible(),visible=active&&prefs.open;
    $('.layout').classList.toggle('context-index-available',active);$('.layout').classList.toggle('context-index-open',visible);
    $('.layout').style.setProperty('--context-index-width',prefs.width+'px');
    $('#contextIndex').hidden=!visible;$('#contextIndexToggle').hidden=!active;$('#contextIndexToggle').disabled=!S.slug||projectBusyCount>0;
    $('#contextIndexToggle').setAttribute('aria-expanded',String(visible));
    for(const [id,mode] of [['workspaceSections','sections'],['workspaceFindings','findings']]){
      const el=$('#'+id);if(el){el.disabled=!S.slug||projectBusyCount>0;el.setAttribute('aria-expanded',String(visible&&prefs.mode===mode));}
    }
    const previewToggle=$('#previewToggle'),obscured=obscuresPreview();
    if(previewToggle)previewToggle.textContent=S.previewVisible&&!obscured?t('hide_preview'):t('show_preview');
    const refresh=$('#previewBtn');if(refresh)refresh.style.display=S.previewVisible&&!obscured?'':'none';
  }
  function obscuresPreview(){return bound&&!!prefs?.open&&eligible()&&S.sel.type!=='findings'&&innerWidth>1100&&innerWidth<1500;}
  function togglePreview(){if(obscuresPreview()){close({focus:false});setPreviewVisible(true);}else setPreviewVisible(!S.previewVisible);update();}
  function labels(){
    $('#contextIndexTitle').textContent=w('Índice','Index','Índice');
    $('#contextIndexToggle').textContent=w('Índice','Index','Índice');
    $('#contextIndexToggle').setAttribute('aria-label',w('Abrir o cerrar el índice','Open or close index','Abrir ou fechar o índice'));
    $('#contextIndexToggle').title=w('Cierra el índice para ampliar el editor y la vista previa.','Close the index to give the editor and preview more space.','Feche o índice para ampliar o editor e a prévia.');
    $('#contextIndexClose').setAttribute('aria-label',w('Cerrar índice','Close index','Fechar índice'));
    $('#contextSectionsTab').textContent=w('Secciones','Sections','Seções');$('#contextFindingsTab').textContent=w('Hallazgos','Findings','Achados');
    $('#contextIndexSearchLabel').textContent=w('Buscar por ID o título','Search by ID or title','Pesquisar por ID ou título');
    $('#contextIndexSearch').placeholder=w('ID o título…','ID or title…','ID ou título…');
    $('#contextIndexSeverityLabel').textContent=w('Severidad','Severity','Severidade');$('#contextIndexKindLabel').textContent=w('Tipo','Type','Tipo');
    const severity=$('#contextIndexSeverity'),kind=$('#contextIndexKind');
    severity.options[0].textContent=w('Todas','All','Todas');for(const option of [...severity.options].slice(1))option.textContent=severityLabel(option.value==='pending'?'':option.value);
    for(const [index,label] of [w('Todos','All','Todos'),w('Vulnerabilidades','Vulnerabilities','Vulnerabilidades'),w('Máquinas','Machines','Máquinas')].entries())kind.options[index].textContent=label;
    $('#contextIndexActions > summary').textContent=w('Acciones','Actions','Ações');
    $('#contextIndexSort').textContent=sorting?w('Terminar orden','Finish ordering','Concluir ordenação'):w('Ordenar secciones','Order sections','Ordenar seções');
    $('#contextIndexSort').setAttribute('aria-pressed',String(sorting));
    $('#contextIndexWidthLabel').textContent=w('Ancho del índice','Index width','Largura do índice');
    $('#contextIndexWidth').setAttribute('aria-label',w('Ancho del índice en píxeles','Index width in pixels','Largura do índice em pixels'));
    $('#contextIndexWidthValue').textContent=prefs.width+' px';$('#contextIndexWidth').value=String(prefs.width);
    $('#contextIndexReveal').textContent=w('Mostrar selección','Show selection','Mostrar seleção');
  }
  function render(pageOverride,options={}){
    if(!bound)return;
    const focused=document.activeElement,focusedRow=focused?.closest('#sectionList li,#findingList li');
    const focusToken=focusedRow?{identity:focusedRow.dataset.findingUid||focusedRow.dataset.sectionKey,move:focused.hasAttribute('data-section-move')}:null;
    ensureScope();renderSerial++;
    const current=selection(),selectionKey=JSON.stringify([scope,current]),changed=selectionKey!==lastSelection;
    lastSelection=selectionKey;
    if(changed&&current){const next=current.type==='section'?'sections':'findings';if(prefs.mode!==next)sorting=false;prefs.mode=next;}
    const mode=prefs.mode,f=prefs[mode],v=view();
    if(Number.isInteger(pageOverride))f.page=pageOverride;
    else if(changed&&v.selectedIndex>=0)f.page=Math.floor(v.selectedIndex/PAGE_SIZE);
    f.page=Math.max(0,Math.min(Math.max(0,Math.ceil(v.rows.length/PAGE_SIZE)-1),f.page));
    persist();labels();applyVisibility();
    $('#contextSectionsTab').setAttribute('aria-pressed',String(mode==='sections'));$('#contextFindingsTab').setAttribute('aria-pressed',String(mode==='findings'));
    if($('#contextIndexSearch').value!==f.query)$('#contextIndexSearch').value=f.query;
    $('#contextIndexSeverity').value=f.severity||'';$('#contextIndexKind').value=f.kind||'';
    $('#contextIndexFilters').hidden=mode!=='findings';$('#contextIndexSort').hidden=mode!=='sections';
    $('#contextIndexSectionActions').hidden=mode!=='sections';$('#contextIndexFindingActions').hidden=mode!=='findings';
    $('#contextIndexSort').disabled=!S.slug||projectBusyCount>0;
    const sectionList=$('#sectionList'),findingList=$('#findingList');sectionList.replaceChildren();findingList.replaceChildren();sectionList.hidden=mode!=='sections';findingList.hidden=mode!=='findings';
    const list=mode==='sections'?sectionList:findingList;
    for(const row of v.rows.slice(f.page*PAGE_SIZE,(f.page+1)*PAGE_SIZE)){
      const description=mode==='findings'?[row.id,row.title,severityLabel(row.finding.severity),row.finding.mode==='machine'?w('Máquina','Machine','Máquina'):w('Vulnerabilidad','Vulnerability','Vulnerabilidade')].join(' · '):(row.index+1)+'. '+row.title;
      const active=row.identity===v.identity,button=h('button',{type:'button',class:'finding-nav','aria-current':active?'page':null,'aria-label':description,title:description,onclick:()=>choose(mode,row.identity)});
      if(mode==='findings')button.append(h('span',{class:'sev-dot sev-'+(row.finding.severity||'info'),'aria-hidden':'true'}),h('span',{class:'fid'},row.id));
      button.append(h('span',{class:'ftitle'},mode==='sections'?(row.index+1)+'. '+row.title:row.title));
      const li=h('li',{class:active?'active':'','data-finding-uid':mode==='findings'?row.identity:null,'data-section-key':mode==='sections'?row.identity:null},button);
      if(mode==='sections'&&sorting&&v.all.length>1)li.append(h('button',{type:'button',class:'btn sm','data-section-move':row.identity,'aria-label':w('Mover ','Move ','Mover ')+row.title,onclick:()=>moveFindingDialog(row.identity,true)},w('Mover','Move','Mover')));
      list.append(li);
    }
    $('#contextIndexCount').textContent=v.rows.length+' / '+v.all.length+' '+(mode==='sections'?w('secciones','sections','seções'):w('hallazgos','findings','achados'));
    const empty=$('#contextIndexEmpty');empty.hidden=!!v.rows.length;empty.textContent=v.all.length?w('No hay resultados con estos filtros.','No results match these filters.','Nenhum resultado corresponde a estes filtros.'):mode==='sections'?w('No hay secciones activas. Puedes añadirlas en Acciones.','No active sections. Add them from Actions.','Não há seções ativas. Adicione-as em Ações.'):w('No hay hallazgos. Añade el primero desde Acciones.','No findings yet. Add the first from Actions.','Não há achados. Adicione o primeiro em Ações.');
    const hiddenSelection=v.identity!==null&&v.selectedIndex<0;
    $('#contextIndexSelectionStatus').hidden=!hiddenSelection;$('#contextIndexSelectionText').textContent=w('La selección actual está fuera de estos filtros. El contenido sigue abierto.','The current selection is outside these filters. Its content remains open.','A seleção atual está fora destes filtros. O conteúdo continua aberto.');
    if(hiddenSelection&&changed)$('#contextIndexListScroll').scrollTop=0;
    const pager=$('#contextIndexPager');pager.replaceChildren();pager.hidden=v.rows.length<=PAGE_SIZE;
    if(v.rows.length>PAGE_SIZE)pager.append(workspacePageBar('context',v.rows.length,f.page,PAGE_SIZE,setPage));
    if(focusToken&&!$('#contextIndex').hidden){const replacement=[...list.children].find(row=>(row.dataset.findingUid||row.dataset.sectionKey)===focusToken.identity);(replacement?.querySelector(focusToken.move?'[data-section-move]':'.finding-nav')||$('#contextIndexSearch')).focus({preventScroll:true});}
    if(changed||options.reveal)revealRow();
  }
  function bind(){
    if(bound)return;
    const sections=$('#sectionList'),findings=$('#findingList'),sectionSource=sections.parentElement,findingSource=findings.parentElement;
    const search=h('input',{type:'search',id:'contextIndexSearch',maxlength:300,oninput:event=>setFilters({query:event.target.value})});
    const severity=h('select',{id:'contextIndexSeverity',onchange:event=>setFilters({severity:event.target.value})},...['','critical','high','medium','low','info','pending'].map(value=>h('option',{value},value)));
    const kind=h('select',{id:'contextIndexKind',onchange:event=>setFilters({kind:event.target.value})},...['','vuln','machine'].map(value=>h('option',{value},value)));
    const sectionActions=h('div',{id:'contextIndexSectionActions'},$('#manageSections'));
    const findingActions=h('div',{id:'contextIndexFindingActions'},findingSource.querySelector('.addfinding'));
    const actions=h('details',{id:'contextIndexActions'},h('summary',{}),h('div',{class:'context-index-action-body'},sectionActions,findingActions));
    const panel=h('aside',{id:'contextIndex',class:'context-index',hidden:true,'aria-labelledby':'contextIndexTitle'},
      h('div',{class:'context-index-head'},h('h2',{id:'contextIndexTitle'}),h('button',{type:'button',id:'contextIndexClose',class:'btn',onclick:()=>close()},'×')),
      h('div',{class:'context-index-tabs'},h('button',{type:'button',id:'contextSectionsTab',class:'btn','aria-pressed':'true',onclick:()=>setMode('sections')}),h('button',{type:'button',id:'contextFindingsTab',class:'btn','aria-pressed':'false',onclick:()=>setMode('findings')})),
      h('div',{class:'context-index-search'},h('label',{for:'contextIndexSearch'},h('span',{id:'contextIndexSearchLabel'}),search)),
      h('div',{id:'contextIndexFilters',class:'context-index-filters'},h('label',{for:'contextIndexSeverity'},h('span',{id:'contextIndexSeverityLabel'}),severity),h('label',{for:'contextIndexKind'},h('span',{id:'contextIndexKindLabel'}),kind)),
      h('p',{id:'contextIndexCount',role:'status','aria-live':'polite'}),
      h('div',{id:'contextIndexListScroll',class:'context-index-list-scroll'},h('div',{id:'contextIndexSelectionStatus',hidden:true,role:'status'},h('p',{id:'contextIndexSelectionText'}),h('button',{id:'contextIndexReveal',type:'button',class:'btn sm',onclick:revealSelection})),sections,findings,h('p',{id:'contextIndexEmpty',class:'context-index-empty'})),
      h('div',{id:'contextIndexPager'}),
      h('div',{class:'context-index-footer'},h('button',{type:'button',id:'contextIndexSort',class:'btn sm','aria-pressed':'false',onclick:()=>setSorting(!sorting)}),actions,
        h('div',{class:'context-index-width'},h('label',{for:'contextIndexWidth'},h('span',{id:'contextIndexWidthLabel'}),h('output',{id:'contextIndexWidthValue',for:'contextIndexWidth'})),h('input',{id:'contextIndexWidth',type:'range',min:220,max:420,step:20,value:280,oninput:event=>setWidth(event.target.value)}))));
    sectionSource.remove();findingSource.remove();$('#editor').before(panel);
    const toggleButton=h('button',{type:'button',id:'contextIndexToggle',class:'btn sm','aria-controls':'contextIndex','aria-expanded':'false',onclick:toggle});
    $('.workspace-toolbar').insertBefore(toggleButton,$('#saveState'));
    bound=true;
    $('#sidebarToggle').addEventListener('click',()=>{if(mobile()&&$('.layout').classList.contains('navigation-open')&&prefs?.open)close({focus:false});});
    document.addEventListener('click',event=>{if(actions.open&&!actions.contains(event.target))actions.open=false;});
    document.addEventListener('keydown',event=>{
      if(event.key!=='Escape'||document.querySelector('dialog[open],.modal.open'))return;
      if(actions.open&&panel.contains(event.target)){actions.open=false;actions.querySelector('summary').focus();event.preventDefault();return;}
      if(!panel.hidden&&(mobile()||panel.contains(event.target))){event.preventDefault();close();}
    });
    window.addEventListener('resize',()=>{if(prefs)applyVisibility();});
    render();
  }
  function update(){if(bound){ensureScope();labels();applyVisibility();}}
  return {bind,render,update,projectChanged,open,toggle,setMode,setFilters,setPage,setWidth,setSorting,revealSelection,revealSelectedRow,state,normalizeQuery,obscuresPreview,togglePreview};
})();
