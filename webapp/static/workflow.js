/* Project workflows. All mutations share the existing revision/CSRF save contract. */
const WorkflowUI = (() => {
  'use strict';
  const w = (es, en) => S.uiLang === 'en' ? en : es;
  const uid = () => crypto.randomUUID();
  const clone = x => JSON.parse(JSON.stringify(x));
  const names = {review:['Revisión de entrega','Delivery review'], history:['Versiones','Versions'], evidence:['Evidencias','Evidence'], assets:['Activos','Assets'], coverage:['Cobertura','Coverage'], retest:['Correcciones y retest','Remediation and retest'], backup:['Respaldo del proyecto','Project backup'], library:['Biblioteca de hallazgos','Finding library']};
  const statuses = [['open','Abierto','Open'],['in_progress','En corrección','In progress'],['reported_fixed','Corrección comunicada','Reported fixed'],['verified_fixed','Corregido y verificado','Verified fixed'],['accepted','Riesgo aceptado','Risk accepted'],['not_verified','No verificable','Not verifiable']];
  const results = [['fixed','Corregido','Fixed'],['open','Sigue abierto','Still open'],['partial','Corrección parcial','Partially fixed'],['not_verified','No verificable','Not verifiable']];
  const cover = [['pending','Pendiente','Pending'],['done','Realizada','Performed'],['blocked','Bloqueada','Blocked'],['not_applicable','No aplica','Not applicable']];
  const stageNames = [['draft','Borrador','Draft'],['delivered','Entregado al cliente','Delivered to client'],['retest','Retest','Retest']];
  let libraryTag = null;
  function title(kind) { return w(...names[kind]); }
  function safe(fn) { return async event => { try { await fn(event); } catch (e) { toast(e.message, 'err'); } }; }
  function button(text, fn, primary=false) { const b=h('button', {class:'btn sm' + (primary?' primary':''), type:'button'}, text); b.addEventListener('click',safe(async event=>{b.disabled=true;try{await fn(event);}finally{b.disabled=false;}}));return b; }
  function hint(es,en) { return h('p',{class:'wf-hint'},w(es,en)); }
  function card(...children) { return h('div',{class:'card wf-card'},...children); }
  function row(...children) { return h('div',{class:'wf-row'},...children); }
  function localField(label,obj,key,type='text') {
    const input = h(type === 'textarea' ? 'textarea':'input', {type:type === 'textarea' ? null:type, rows:type==='textarea'?5:null, 'data-field':key, oninput:e=>{obj[key]=e.target.value;}});
    input.value=obj[key]||'';
    return h('label',{},label,input);
  }
  function selectField(label,obj,key,items,persist=true) {
    const input=h('select',{'data-field':key,onchange:e=>{obj[key]=e.target.value;if(persist)scheduleSave();}}, items.map(([value,es,en])=>h('option',{value},w(es,en||es))));
    input.value=obj[key]||items[0]?.[0]||'';
    return h('label',{},label,input);
  }
  function check(label,checked,fn) {return h('label',{class:'wf-check'},h('input',{type:'checkbox',checked:checked?'':null,onchange:e=>fn(e.target.checked)}),label);}
  function links(label,obj,key,items,persist=true) {
    const box=h('fieldset',{'data-field':key,class:'wf-links'},h('legend',{},label));
    if(!items.length) box.append(hint('No hay elementos registrados. Añádelos desde el menú del proyecto.','No registered items. Add them from the project menu.'));
    items.forEach(item=>box.append(check(item.name||item.title||item.target, (obj[key]||[]).includes(item.uid), checked=>{
      obj[key]=checked?[...new Set([...(obj[key]||[]),item.uid])]:(obj[key]||[]).filter(x=>x!==item.uid);
      if(persist)scheduleSave();
    })));
    return box;
  }
  async function requestJson(path,options) { const r=await requireOk(await appFetch(path,options)); return {body:await r.json(),etag:r.headers.get('ETag')}; }
  function url(path='',slug=S.slug) {return '/api/projects/'+encodeURIComponent(slug)+path;}
  async function mutate(path,body) {
    const slug=S.slug; busyProject(true);
    try {
      if(!await doSave())throw Error(w('No se pudo guardar el proyecto.','Could not save project.'));
      const r=await requestJson(url(path,slug),{method:'POST',headers:{'Content-Type':'application/json','If-Match':projectStore.etag},body:JSON.stringify(body)});
      if(S.slug===slug){
        if(r.body.data){S.data=r.body.data;projectStore.data=S.data;}
        if(r.etag)projectStore.etag=r.etag;
        renderSidebar();renderMain();if(S.previewMode==='live')refreshLivePreview();
      }
      return r.body;
    }finally{busyProject(false);}
  }
  async function download(path,name,options) {
    const r=await requireOk(await appFetch(path,options)); const blob=await r.blob();
    const link=URL.createObjectURL(blob); const a=h('a',{href:link,download:name});a.click();setTimeout(()=>URL.revokeObjectURL(link),1000);
  }
  function jsonDownload(value,name){const link=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'}));h('a',{href:link,download:name}).click();setTimeout(()=>URL.revokeObjectURL(link),1000);}
  function pick(accept,fn){const input=h('input',{type:'file',accept,onchange:safe(async()=>{if(input.files[0])await fn(input.files[0]);})});input.click();}
  function go(kind){select('workflow',kind);}
  function bind(){
    const section=h('div',{class:'side-sec',id:'workflowNav'},h('div',{class:'side-head'},w('Gestión del proyecto','Project management')));
    Object.keys(names).filter(k=>k!=='library').forEach(k=>section.append(h('button',{class:'navitem','data-workflow':k,onclick:()=>go(k)},title(k))));
    $('.sidebar').append(section);
    $('#importProjectBtn').addEventListener('click',safe(importProject));
  }
  function updateNav(){document.querySelectorAll('[data-workflow]').forEach(b=>{b.textContent=title(b.dataset.workflow);b.classList.toggle('active',S.sel.type==='workflow'&&S.sel.idx===b.dataset.workflow);});const b=$('#importProjectBtn');if(b)b.textContent=w('Abrir respaldo','Open backup');}
  function render(kind,el){
    el.append(h('h2',{},title(kind)));const box=h('div',{'data-workflow-view':kind});el.append(box);
    const slug=S.slug;
    Promise.resolve().then(()=>({review,history,evidence,assets,coverage,retest,backup,library}[kind])(box,slug)).catch(e=>{if(box.isConnected)box.append(card(h('p',{role:'alert'},e.message),button(w('Reintentar','Retry'),()=>renderMain())));});
  }
  function findingPanel(f){
    const box=card(h('h3',{},w('Seguimiento y vínculos','Tracking and links')));
    box.append(row(field(w('Responsable','Owner'),f,'owner'),field(w('Fecha objetivo','Due date'),f,'due_date',{type:'date'}),selectField(w('Estado','Status'),f,'status',statuses)));
    box.append(links(w('Activos afectados','Affected assets'),f,'asset_uids',S.data.assets||[]),links(w('Evidencias vinculadas','Linked evidence'),f,'evidence_uids',S.data.evidence||[]));
    box.append(button(w('Registrar / ver retest','Record / view retest'),()=>{S.retestFinding=f.uid;go('retest');}));
    box.append(h('details',{},h('summary',{},w('Referencia permanente','Permanent reference')),h('code',{},f.uid||'')));
    return box;
  }
  async function review(box,slug){
    if(!await doSave())return;
    const {body}=await requestJson(url('/review',slug));if(!box.isConnected||S.slug!==slug)return;
    const errors=body.issues.filter(x=>x.level==='error').length;
    box.append(card(h('h3',{},errors+' '+w('errores','errors')+' · '+(body.issues.length-errors)+' '+w('avisos','warnings')),hint('La revisión detecta omisiones; la validación técnica de los hallazgos corresponde al evaluador.','This review detects omissions; technical validation remains the assessor’s responsibility.'),button(w('Volver a revisar','Review again'),()=>renderMain())));
    if(!body.issues.length)box.append(card(w('No se detectaron omisiones en estas comprobaciones.','No omissions detected by these checks.')));
    body.issues.forEach(issue=>box.append(card(h('strong',{class:'wf-'+issue.level},issue.message),h('small',{},issue.path),button(w('Ir al campo','Go to field'),()=>navigateIssue(issue)))));
    box.append(button(w('Guardar versión de entrega','Save delivery version'),()=>{go('history');},true));
  }
  function navigateIssue(issue){
    let fieldKey=issue.path.split('.').pop().replace(/\[\d+\]/g,'');
    if(issue.finding_uid){const i=S.data.findings.findIndex(f=>f.uid===issue.finding_uid);if(i>=0)select('finding',i);}
    else if(issue.path.startsWith('coverage'))go('coverage');
    else if(issue.path.startsWith('evidence'))go('evidence');
    else if(issue.path.startsWith('assets'))go('assets');
    else if(issue.path.startsWith('report.sections[')){const i=Number(issue.path.match(/\[(\d+)\]/)[1]);select('section',S.data.report.sections[i]?.key);}
    else select('report',-1);
    let attempts=0;
    function focus(){
      const scope=$('#editor');const group=issue.path.match(/^(assets|coverage|evidence)\[(\d+)\]/);
      const step=issue.path.match(/(?:walkthrough|steps)\[(\d+)\]/);
      const container=(group?scope.querySelector(`[data-workflow-index="${group[2]}"]`):step?scope.querySelector(`[data-step-index="${step[1]}"]`):scope)||scope;
      let target=Array.from(container.querySelectorAll('[data-field]')).find(x=>x.dataset.field===fieldKey);
      if(!target&&issue.path.includes('walkthrough'))target=container.querySelector('[data-add-step]');
      if(target){target.scrollIntoView?.({block:'center'});(target.matches('input,textarea,select,button')?target:target.querySelector('input,textarea,select'))?.focus();target.classList.add('wf-focus');setTimeout(()=>target.classList.remove('wf-focus'),3000);}
      else if(++attempts<30)setTimeout(focus,100);
    }
    setTimeout(focus,50);
  }
  async function history(box,slug){
    if(!await doSave())return;
    const {body:records}=await requestJson(url('/history',slug));if(!box.isConnected||S.slug!==slug)return;
    const draft={label:'',stage:'draft'};
    box.append(card(hint('Se conservan los autoguardados y los archivos de cada versión. Usa un nombre para identificar una entrega o un retest.','Autosaves and each version’s files are retained. Name a checkpoint to identify a delivery or retest.'),row(localField(w('Nombre de versión','Version name'),draft,'label'),selectField(w('Etapa','Stage'),draft,'stage',stageNames,false)),button(w('Crear versión','Create version'),async()=>{if(!draft.label.trim())throw Error(w('Escribe un nombre.','Enter a name.'));await mutate('/history',draft);},true)));
    const chosen={to:''};const options=[['',w('Proyecto actual','Current project')],...records.map(r=>[r.id,r.label+' · '+new Date(r.created).toLocaleString()])];
    box.append(selectField(w('Comparar con','Compare with'),chosen,'to',options,false));
    const diff=h('div',{class:'wf-diff'});box.append(diff);
    const list=h('div',{});box.append(list);const filter={auto:false};
    const draw=()=>{list.replaceChildren();records.filter(r=>filter.auto||r.stage!=='auto').forEach(r=>list.append(card(row(h('strong',{},r.label),h('small',{},(stageNames.find(s=>s[0]===r.stage)?.slice(1)[S.uiLang==='en'?1:0]||w('Autoguardado','Autosave'))+' · '+new Date(r.created).toLocaleString())),row(button(w('Comparar','Compare'),async()=>{
      if(!await doSave())return;const {body:changes}=await requestJson(url('/history/'+r.id+'/compare'+(chosen.to?'?to='+encodeURIComponent(chosen.to):''),slug));if(!diff.isConnected)return;diff.replaceChildren(h('h3',{},w('Cambios','Changes')+' · '+changes.length));
      changes.forEach(c=>diff.append(card(h('strong',{},c.path),row(h('pre',{},JSON.stringify(c.before,null,2)??'—'),h('pre',{},JSON.stringify(c.after,null,2)??'—')))));diff.scrollIntoView?.({block:'start'});
    }),button(w('Restaurar','Restore'),async()=>{if(confirm(w('¿Restaurar esta versión y sus imágenes? El estado actual quedará en el historial.','Restore this version and its images? The current state will remain in history.')))await mutate('/history/'+r.id+'/restore',{});})))));};
    box.insertBefore(check(w('Mostrar autoguardados','Show autosaves'),false,v=>{filter.auto=v;draw();}),list);draw();
    if(!records.some(r=>r.stage!=='auto'))list.append(hint('Todavía no hay versiones nombradas. Los autoguardados ya están disponibles.','No named versions yet. Autosaves are already available.'));
  }
  function assets(box){
    const rows=S.data.assets||(S.data.assets=[]);
    box.append(hint('Registra URLs, endpoints, hosts o redes. Puedes vincular varios activos a un mismo hallazgo.','Register URLs, endpoints, hosts or networks. A finding can affect multiple assets.'));
    rows.forEach((a,i)=>box.append(card(row(field(w('Nombre','Name'),a,'name'),field(w('Objetivo','Target'),a,'target')),row(field(w('Tipo','Type'),a,'kind'),field(w('Notas de alcance','Scope notes'),a,'notes')),button(w('Eliminar activo','Delete asset'),()=>{
      if(!confirm(w('¿Eliminar el activo y sus vínculos con hallazgos y cobertura?','Delete the asset and its finding/coverage links?')))return;
      S.data.findings.forEach(f=>{f.asset_uids=(f.asset_uids||[]).filter(x=>x!==a.uid);});(S.data.coverage||[]).forEach(c=>{if(c.asset_uid===a.uid)c.asset_uid='';});rows.splice(i,1);scheduleSave();renderMain();
    }))));
    box.append(button(w('Añadir activo','Add asset'),()=>{rows.push({uid:uid(),name:'',target:'',kind:'URL',notes:''});scheduleSave();renderMain();},true));
    box.querySelectorAll(':scope > .wf-card').forEach((c,i)=>{c.dataset.workflowIndex=i;});
    reportOptions(box,['include_assets']);
  }
  function coverage(box){
    const rows=S.data.coverage||(S.data.coverage=[]);const targets=[['',w('General','General')],...(S.data.assets||[]).map(a=>[a.uid,a.name+' · '+a.target])];
    rows.forEach((c,i)=>box.append(card(field(w('Prueba / control','Test / control'),c,'test'),row(selectField(w('Activo','Asset'),c,'asset_uid',targets),selectField(w('Estado','Status'),c,'status',cover)),field(w('Resultado o impedimento','Result or blocker'),c,'notes',{area:true}),button(w('Eliminar prueba','Delete test'),()=>{rows.splice(i,1);scheduleSave();renderMain();}))));
    box.querySelectorAll(':scope > .wf-card').forEach((c,i)=>{c.dataset.workflowIndex=i;});
    box.append(button(w('Añadir prueba','Add test'),()=>{rows.push({uid:uid(),test:'',asset_uid:'',status:'pending',notes:''});scheduleSave();renderMain();},true),card(mdEditor(w('Limitaciones del trabajo','Engagement limitations'),S.data,'limitations_md')));reportOptions(box,['include_coverage']);
  }
  function retest(box){
    const findings=S.data.findings||[];
    box.append(hint('Una corrección comunicada por el cliente no equivale a una corrección verificada. Registra la comprobación y su evidencia.','A client-reported fix is distinct from a verified fix. Record the verification and its evidence.'));
    findings.forEach(f=>{
      const c=card(button(f.id+' · '+(f.title||''),()=>select('finding',findings.indexOf(f))),row(field(w('Responsable','Owner'),f,'owner'),field(w('Fecha objetivo','Due date'),f,'due_date',{type:'date'}),selectField(w('Estado','Status'),f,'status',statuses)));
      (f.retests||[]).forEach(r=>c.append(h('details',{},h('summary',{},r.tested_on+' · '+w(...(results.find(x=>x[0]===r.result)||['','—','—']).slice(1))+' · '+r.assessor),h('p',{},r.notes_md),...(r.evidence_uids||[]).map(id=>{const e=(S.data.evidence||[]).find(x=>x.uid===id);return e?h('img',{class:'wf-thumb',src:url('/'+e.src),alt:e.caption||e.title}):null;}))));
      const form={finding_uid:f.uid,tested_on:new Date().toISOString().slice(0,10),assessor:S.data.meta.assessor||'',result:'open',notes_md:'',evidence_uids:[]};
      const details=h('details',{open:S.retestFinding===f.uid?'':null},h('summary',{},w('Registrar retest','Record retest')),row(localField(w('Fecha','Date'),form,'tested_on','date'),localField(w('Evaluador','Assessor'),form,'assessor')),selectField(w('Resultado','Result'),form,'result',results,false),localField(w('Procedimiento y resultado observado','Procedure and observed result'),form,'notes_md','textarea'),links(w('Evidencias del retest','Retest evidence'),form,'evidence_uids',S.data.evidence||[],false),button(w('Guardar comprobación','Save verification'),async()=>{await mutate('/retest',form);},true));
      c.append(details);box.append(c);
    });
    if(!findings.length)box.append(hint('Añade un hallazgo para registrar correcciones.','Add a finding to track remediation.'));
    reportOptions(box,['include_retest']);
    box.append(button(w('Exportar informe con retest','Export report with retest'),async()=>{S.data.report.workflow=S.data.report.workflow||{};S.data.report.workflow.include_retest=true;scheduleSave();await exportFile($('#exportFormat').value);},true));
  }
  function reportOptions(box,keys){
    const cfg=(S.data.report.workflow=S.data.report.workflow||{});const labels={include_assets:['Incluir activos en el informe','Include assets in report'],include_coverage:['Incluir cobertura y limitaciones','Include coverage and limitations'],include_retest:['Incluir seguimiento y retest','Include tracking and retest']};
    box.append(card(...keys.map(k=>check(w(...labels[k]),cfg[k]!==false,v=>{cfg[k]=v;scheduleSave();}))));
  }
  async function evidence(box,slug){
    if(!await doSave())return;
    const {body}=await requestJson(url('/evidence',slug));if(!box.isConnected||S.slug!==slug)return;
    box.append(hint('Vincula cada evidencia a uno o varios hallazgos. Los informes usan la copia procesada. Los respaldos editables incluyen originales e historial.','Link evidence to one or more findings. Reports use the processed copy. Editable backups contain originals and history.'));
    box.append(button(w('Subir evidencia','Upload evidence'),()=>pick('image/png,image/jpeg,image/webp,image/gif',async file=>{
      const source=await sendImage(file);if(source)await mutate('/evidence',{src:source.src,title:file.name});
    }),true));
    const gallery=h('div',{class:'wf-gallery'});box.append(gallery);
    (S.data.evidence||[]).forEach((e,index)=>{
      const c=card(h('img',{class:'wf-thumb',src:url('/'+e.src,slug),alt:e.caption||e.title,loading:'lazy'}),field(w('Título','Title'),e,'title'),field(w('Pie de imagen','Caption'),e,'caption'));
      c.dataset.workflowIndex=index;
      const refs=h('fieldset',{class:'wf-links'},h('legend',{},w('Usada en hallazgos','Used in findings')));
      S.data.findings.forEach(f=>refs.append(check(f.id+' · '+f.title,(f.evidence_uids||[]).includes(e.uid),v=>{f.evidence_uids=v?[...new Set([...(f.evidence_uids||[]),e.uid])]:(f.evidence_uids||[]).filter(x=>x!==e.uid);scheduleSave();})));c.append(refs);
      c.append(row(button(w('Anotar / censurar','Annotate / redact'),()=>annotations(e)),button(w('Descargar original','Download original'),()=>download(url('/evidence/'+e.uid+'/original',slug),'original-'+e.src.split('/').pop()))));gallery.append(c);
    });
    if(body.unlinked.length){box.append(h('h3',{},w('Imágenes del proyecto sin registrar','Unregistered project images')));body.unlinked.forEach(e=>box.append(card(h('img',{class:'wf-thumb',src:url('/'+e.src,slug),alt:e.src,loading:'lazy'}),button(w('Registrar en la galería','Register in gallery'),()=>mutate('/evidence',{src:e.src,title:e.src.split('/').pop()})))));}
  }
  function modal(titleText,...children){
    const close=()=>m.remove();const m=h('div',{class:'modal open',role:'dialog','aria-modal':'true','aria-label':titleText},h('div',{class:'modal-box wide'},row(h('h3',{},titleText),button(w('Cerrar','Close'),close)),...children));document.body.append(m);return m;
  }
  function annotations(e){
    const slug=S.slug;const operations=[];let start=null;const mode={type:'redact',text:''};
    const area=h('div',{class:'wf-image-editor'});const image=h('img',{src:url('/'+e.src,slug),alt:e.title,draggable:'false'});area.append(image);const list=h('div',{});
    const redraw=()=>{
      area.querySelectorAll('.wf-overlay').forEach(n=>n.remove());list.replaceChildren();
      operations.forEach((op,i)=>{
        area.append(h('div',{class:'wf-overlay '+op.type,style:`left:${op.x*100}%;top:${op.y*100}%;width:${op.w*100}%;height:${op.h*100}%`},op.type==='text'?op.text:op.type==='arrow'?'↘':''));
        const r=row(h('strong',{},(i+1)+': '+op.type));['x','y','w','h'].forEach(k=>{const inp=h('input',{type:'number',value:(op[k]*100).toFixed(2),min:0,max:100,step:0.1,'aria-label':k+' %',onchange:ev=>{op[k]=Number(ev.target.value)/100;redraw();}});r.append(h('label',{},k+' %',inp));});r.append(button(w('Quitar','Remove'),()=>{operations.splice(i,1);redraw();}));list.append(r);
      });
    };
    function point(event){const rect=area.getBoundingClientRect();return{x:Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))};}
    area.addEventListener('pointerdown',ev=>{ev.preventDefault();start=point(ev);area.setPointerCapture?.(ev.pointerId);});
    area.addEventListener('pointerup',ev=>{if(!start)return;const end=point(ev);const op={type:mode.type,x:Math.min(start.x,end.x),y:Math.min(start.y,end.y),w:Math.abs(end.x-start.x),h:Math.abs(end.y-start.y),text:mode.text};start=null;if(op.w>.001&&op.h>.001){operations.push(op);redraw();}});
    const m=modal(w('Anotar y censurar evidencia','Annotate and redact evidence'),hint('Arrastra sobre la imagen para marcar una zona. La censura negra se aplica a los píxeles al guardar; no se puede quitar de esa copia. El original se conserva por separado.','Drag on the image to mark an area. Black redaction is applied to pixels on save and cannot be removed from that copy. The original is retained separately.'),row(selectField(w('Herramienta','Tool'),mode,'type',[['redact','Censura negra','Black redaction'],['box','Recuadro','Box'],['arrow','Flecha','Arrow'],['text','Texto','Text']],false),localField(w('Texto de anotación','Annotation text'),mode,'text')),area,button(w('Añadir zona con coordenadas','Add area by coordinates'),()=>{operations.push({type:mode.type,x:.1,y:.1,w:.3,h:.15,text:mode.text});redraw();}),list,button(w('Aplicar y guardar copia','Apply and save copy'),async()=>{
      if(S.slug!==slug)throw Error(w('Vuelve a abrir la evidencia del proyecto activo.','Reopen evidence in the active project.'));await mutate('/evidence/'+e.uid+'/edit',{operations});m.remove();
    },true));
  }
  function backup(box){
    box.append(card(h('h3',{},w('Proyecto editable completo','Complete editable project')),hint('Incluye YAML, imágenes, originales, configuración del informe y versiones. Este respaldo contiene información interna y no es el archivo de entrega al cliente.','Includes YAML, images, originals, report settings and versions. This backup contains internal information and is separate from the client deliverable.'),button(w('Descargar respaldo ZIP','Download ZIP backup'),async()=>{const slug=S.slug;if(await doSave())await download(url('/bundle',slug),slug+'-project.zip');},true),button(w('Importar como otro proyecto','Import as another project'),importProject)),hint('Límites: ZIP de 256 MiB; contenido descomprimido de 512 MiB y 20.000 archivos. La biblioteca global se exporta desde Biblioteca.','Limits: 256 MiB ZIP; 512 MiB expanded and 20,000 files. Export the global library from Finding library.'));
  }
  async function importProject(){pick('.zip,application/zip',async file=>{
    const slug=prompt(w('Nombre del proyecto importado (se creará una copia):','Imported project name (creates a copy):'),file.name.replace(/(-project)?\.zip$/i,''));if(slug===null)return;
    const data=new FormData();data.append('file',file);data.append('slug',slug);
    const {body}=await requestJson('/api/projects/import',{method:'POST',body:data});await refreshProjects();await loadProject(body.slug);toast(w('Proyecto importado','Project imported'),'ok');
  });}
  async function library(box){
    const {body,etag}=await requestJson('/api/library');libraryTag=etag;if(!box.isConnected)return;
    box.append(hint('Las plantillas se guardan junto a la herramienta. Revisa su texto para retirar datos del cliente antes de reutilizarlas. Variables: {{cliente}}, {{objetivo}}, {{evaluador}} o nombres propios.','Templates are saved with the tool. Review their text to remove client data before reuse. Variables: {{cliente}}, {{objetivo}}, {{evaluador}}, or custom names.'));
    const search=h('input',{type:'search',placeholder:w('Buscar por nombre, etiqueta o contenido','Search name, tag or content'),'aria-label':w('Buscar plantillas','Search templates')});const list=h('div',{});
    function draw(){const q=search.value.trim().toLowerCase();list.replaceChildren();body.templates.filter(e=>JSON.stringify([e.name,e.tags,e.content]).toLowerCase().includes(q)).forEach(e=>list.append(card(h('h3',{},e.name),h('p',{},e.tags.join(' · ')),h('small',{},'v'+e.versions.length+' · '+new Date(e.updated).toLocaleString()),row(button(w('Insertar','Insert'),()=>insertTemplate(e),true),button(w('Editar / versiones','Edit / versions'),()=>editTemplate(e)),button(w('Eliminar','Delete'),async()=>{if(confirm(w('¿Eliminar esta plantilla?','Delete this template?'))){await requestJson('/api/library/'+e.uid,{method:'DELETE',headers:{'If-Match':libraryTag}});renderMain();}})))));if(!list.childNodes.length)list.append(hint('No hay plantillas que coincidan. Guarda una desde el botón Plantilla de un hallazgo.','No matching templates. Save one using the Template button in a finding.'));}
    search.addEventListener('input',draw);box.append(search,row(button(w('Nueva plantilla','New template'),()=>editTemplate({name:'',tags:[],content:{mode:'vuln',title:'',severity:'info',description_md:'',impact_md:'',remediation_md:'',walkthrough:[]}})),button(w('Exportar biblioteca','Export library'),()=>jsonDownload(body,'report-gen-library.json')),button(w('Importar biblioteca','Import library'),()=>pick('.json,application/json',async file=>{await requestJson('/api/library/import',{method:'POST',headers:{'Content-Type':'application/json','If-Match':libraryTag},body:await file.text()});renderMain();}))),list);
    let old=[];try{old=JSON.parse(localStorage.getItem('rg.findingLib')||'[]');}catch(_){}
    if(Array.isArray(old)&&old.length)box.append(card(h('h3',{},w('Plantillas antiguas de este navegador','Legacy templates in this browser')),hint('Revisa y guarda cada plantilla. Los datos originales del navegador se mantienen hasta que tú los retires.','Review and save each template. Original browser data remains until you remove it.'),...old.map(e=>button(e.__name||e.title||w('Plantilla','Template'),()=>saveTemplate(e)))));
    draw();
  }
  async function saveTemplate(f){
    const context={cliente:S.data.meta.client||'',objetivo:f.affected||f.host?.ip||'',evaluador:S.data.meta.assessor||''};
    const {body}=await requestJson('/api/library/sanitize',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({finding:f,context})});
    await editTemplate({name:f.__name||f.title||'',tags:[],content:body.content});
  }
  async function editTemplate(entry){
    const {etag}=await requestJson('/api/library');const draft=clone(entry);draft.tagsText=(draft.tags||[]).join(', ');draft.json=JSON.stringify(draft.content,null,2);
    const editor=localField(w('Contenido reutilizable (JSON)','Reusable content (JSON)'),draft,'json','textarea');editor.querySelector('textarea').rows=15;
    const fields=row(localField(w('Nombre','Name'),draft,'name'),localField(w('Etiquetas, separadas por coma','Comma-separated tags'),draft,'tagsText'));
    const checked={value:false};
    const m=modal(w('Plantilla reutilizable','Reusable template'),hint('Se retiran imágenes, activos, responsables, retests y referencias internas. Revisa también descripciones, comandos y URLs: no se pueden anonimizar automáticamente todos los datos escritos.','Images, assets, owners, retests and internal references are removed. Also review descriptions, commands and URLs: automatic sanitization cannot remove all free-text client data.'),fields,editor,check(w('He revisado que no contenga datos de otro cliente','I reviewed it for other client data'),false,v=>{checked.value=v;}),button(w('Guardar versión de plantilla','Save template version'),async()=>{
      if(!checked.value)throw Error(w('Revisa el contenido antes de guardar la plantilla.','Review the content before saving.'));
      const payload={name:draft.name,tags:draft.tagsText.split(',').map(x=>x.trim()).filter(Boolean),content:JSON.parse(draft.json)};
      await requestJson('/api/library'+(entry.uid?'/'+entry.uid:''),{method:entry.uid?'PUT':'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify(payload)});m.remove();toast(w('Plantilla guardada','Template saved'),'ok');if(S.sel.type==='workflow'&&S.sel.idx==='library')renderMain();
    },true));
    if(entry.versions?.length){const version={v:String(entry.versions.length)};const field=selectField(w('Cargar versión anterior para editar','Load previous version to edit'),version,'v',entry.versions.map(v=>[String(v.version),'v'+v.version+' · '+v.created]),false);field.querySelector('select').addEventListener('change',()=>{const chosen=entry.versions.find(v=>String(v.version)===version.v);draft.json=JSON.stringify(chosen.content,null,2);editor.querySelector('textarea').value=draft.json;});editor.before(field);}
  }
  function insertTemplate(entry){
    if(!S.data)throw Error(w('Abre un proyecto.','Open a project.'));const slug=S.slug;
    const values={cliente:S.data.meta.client||'',objetivo:'',evaluador:S.data.meta.assessor||''};const keys=[...new Set(['objetivo',...(entry.variables||[])])];
    const m=modal(w('Insertar plantilla','Insert template'),...keys.map(k=>localField(k,values,k)),button(w('Insertar en el proyecto','Insert into project'),async()=>{
      if(S.slug!==slug)throw Error(w('El proyecto activo cambió.','The active project changed.'));
      const {body:f}=await requestJson('/api/library/'+entry.uid+'/instantiate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({values})});
      if(S.slug!==slug)return;f.id=nextFid();S.data.findings.push(f);renumberFindings();scheduleSave();select('finding',S.data.findings.length-1);m.remove();
    },true));
  }
  return {bind,updateNav,render,findingPanel,saveTemplate,openLibrary:()=>go('library'),navigateIssue,uid};
})();
