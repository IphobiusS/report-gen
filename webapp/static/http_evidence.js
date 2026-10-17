/* HTTP evidence stays private until a separate technical copy is reviewed. */
const HttpEvidenceUI=(()=>{
 'use strict';
 const w=(es,en,pt)=>uiText(es,en,pt),clone=x=>JSON.parse(JSON.stringify(x));
 const words={title:['Título','Title','Título'],notes:['Anotaciones privadas','Private annotations','Anotações privadas'],identity:['Identidad / rol observado','Observed identity / role','Identidade / função observada'],request:['Petición','Request','Requisição'],response:['Respuesta','Response','Resposta']};
 const errorText=()=>w('El proyecto cambió. Conserva el formulario y vuelve a abrirlo.','The project changed. Keep this form and reopen it.','O projeto mudou. Guarde o formulário e reabra-o.');
 function rows(){return S.data?.http_evidence||[];}
 function button(label,run,primary=false,attrs={}){return h('button',{type:'button',class:'btn'+(primary?' primary':''),onclick:run,...attrs},label);}
 function input(label,value='',attrs={}){const el=h(attrs.rows?'textarea':'input',{type:attrs.rows?null:'text',...attrs});el.value=value;return {el,node:h('label',{class:'http-field'},h('span',{},label),el)};}
 function wire(msg,isRequest){
  if(!msg)return '';
  let body=msg.body||'';
  if(msg.body_encoding==='base64')try{const bytes=Uint8Array.from(atob(body),c=>c.charCodeAt(0));body=new TextDecoder('utf-8',{fatal:true}).decode(bytes);if(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/.test(body))throw Error();}catch(_){body='[binary body; base64]\n'+msg.body;}
  return (isRequest?msg.method+' '+msg.url+' '+msg.http_version:msg.http_version+' '+msg.status)+'\n'+(msg.headers||[]).map(x=>x.name+': '+x.value).join('\n')+'\n\n'+body;
 }
 function dialog(title){
  const previous=document.activeElement,el=h('dialog',{class:'experience-dialog http-dialog','aria-label':title}),content=h('div',{class:'experience-body'}),error=h('p',{role:'alert','data-http-error':''});
  const close=button(w('Cerrar','Close','Fechar'),()=>el.close());
  el.append(h('div',{class:'experience-heading'},h('h2',{},title),close),content,error);
  el.addEventListener('close',()=>{el.remove();if(previous?.isConnected)previous.focus({preventScroll:true});});
  document.body.append(el);el.showModal();return{el,content,error,close};
 }
 async function mutate(state,path,payload,form){
  if(state.slug!==S.slug||state.workspace!==S.workspace_id)throw Error(errorText());
  if(!await doSave())throw Error(w('Guarda primero el informe.','Save the report first.','Salve primeiro o relatório.'));
  if(state.slug!==S.slug||state.workspace!==S.workspace_id)throw Error(errorText());
  const before=S.data,revision=projectStore.revision,json=JSON.stringify(S.data),etag=projectStore.etag;
  busyProject(true);if(form)form.disabled=true;
  try{
   const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(state.slug)+'/http-evidence'+path,{method:'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify(payload)})),result=await response.json();
   if(state.slug!==S.slug||state.workspace!==S.workspace_id||S.data!==before||revision!==projectStore.revision||JSON.stringify(S.data)!==json||projectStore.dirty)throw Error(errorText());
   if(result.data){await adoptSavedProject(result.data,response.headers.get('ETag'));renderSidebar();renderMain();if(S.previewMode==='live')refreshLivePreview();}
   return result;
  }finally{if(form)form.disabled=false;busyProject(false);}
 }
 function choiceSet(label,pool,selected){
  const el=h('select',{multiple:'',size:Math.min(5,Math.max(2,pool.length)),'aria-label':label},pool.map(row=>h('option',{value:row.uid,selected:selected.includes(row.uid)?'':null},(row.id?row.id+' · ':'')+(row.title||row.name||row.target||row.uid))));
  return {el,node:h('label',{class:'http-field'},h('span',{},label),el),read:()=>[...el.selectedOptions].map(x=>x.value)};
 }
 function metadata(data){
  const title=input(w(...words.title),data.title,{maxlength:500,'data-http-field':'title'}),notes=input(w(...words.notes),data.notes,{rows:3,maxlength:16000,'data-http-field':'notes'});
  const findings=choiceSet(w('Hallazgos vinculados','Linked findings','Achados vinculados'),S.data.findings||[],data.finding_uids||[]),assets=choiceSet(w('Activos vinculados','Linked assets','Ativos vinculados'),S.data.assets||[],data.asset_uids||[]);
  return {node:h('div',{},title.node,notes.node,h('div',{class:'http-grid'},findings.node,assets.node)),read:()=>({title:title.el.value,notes:notes.el.value,finding_uids:findings.read(),asset_uids:assets.read()})};
 }
 function headerRows(value){
  return value.split(/\r?\n/).filter(line=>line.trim()).map(line=>{const i=line.indexOf(':');if(i<1)throw Error(w('Cada cabecera debe tener nombre: valor.','Each header must use name: value.','Cada cabeçalho deve usar nome: valor.'));return{name:line.slice(0,i).trim(),value:line.slice(i+1).trim()};});
 }
 function messageForm(initial,request){
  const defaults={http_version:'HTTP/1.1',headers:[],body:'',body_encoding:'utf-8',...(request?{method:'GET',url:'https://example.test/'}:{status:200})},value={...defaults,...initial};
  const root=h('fieldset',{class:'http-message'},h('legend',{},w(...words[request?'request':'response']))),controls={};
  for(const [key,label,attrs]of(request?[['method','Method',{maxlength:40}],['url','URL',{maxlength:16000}],['http_version','HTTP',{maxlength:20}]]:[['status','Status',{type:'number',min:100,max:599}],['http_version','HTTP',{maxlength:20}]])){const f=input(label,value[key],{'data-http-message-field':(request?'request.':'response.')+key,...attrs});controls[key]=f.el;root.append(f.node);}
  const headers=input(w('Cabeceras · una por línea','Headers · one per line','Cabeçalhos · um por linha'),value.headers.map(x=>x.name+': '+x.value).join('\n'),{rows:5,'data-http-message-field':request?'request.headers':'response.headers'});
  const body=input(w('Cuerpo','Body','Corpo'),value.body,{rows:8,'data-http-message-field':request?'request.body':'response.body'});
  const encoding=h('select',{'aria-label':w('Codificación del cuerpo','Body encoding','Codificação do corpo')},h('option',{value:'utf-8'},'UTF-8'),h('option',{value:'base64'},'Base64'));encoding.value=value.body_encoding;
  root.append(headers.node,body.node,encoding);
  return {node:root,raw:()=>({fields:Object.fromEntries(Object.entries(controls).map(([k,v])=>[k,v.value])),headers:headers.el.value,body:body.el.value,body_encoding:encoding.value}),read:()=>({...Object.fromEntries(Object.entries(controls).map(([k,v])=>[k,k==='status'?Number(v.value):v.value])),headers:headerRows(headers.el.value),body:body.el.value,body_encoding:encoding.value}),restore:raw=>{if(!raw)return;for(const[k,v]of Object.entries(raw.fields||{}))if(controls[k])controls[k].value=v;headers.el.value=raw.headers||'';body.el.value=raw.body||'';encoding.value=raw.body_encoding||'utf-8';}};
 }
 function restoreData(row){
  const d=row.data;if(!d||d.schema!==1||!['new','edit'].includes(d.kind)||typeof d.uid!=='string'||!d.meta||typeof d.meta.title!=='string'||typeof d.meta.notes!=='string'||!Array.isArray(d.meta.finding_uids)||!Array.isArray(d.meta.asset_uids))throw Error(w('Formulario HTTP no compatible.','Unsupported HTTP form.','Formulário HTTP incompatível.'));return d;
 }
 function edit(uid=null,recovered=null){
  if(!S.slug||projectBusyCount)return;
  if(document.querySelector('[data-http-editor]')){document.querySelector('[data-http-editor]')?.focus();return;}
  const row=uid?rows().find(x=>x.uid===uid):null;if(uid&&!row)return;
  const key='http:'+(uid||'new'),retained=recovered?restoreData(recovered):PendingUI.retained(key)?.data;
  const formdata=retained||{schema:1,kind:row?'edit':'new',uid:uid||'',meta:row?clone(row):{title:'',notes:'',finding_uids:[],asset_uids:[]}};
  const d=dialog(row?w('Revisar evidencia HTTP','Review HTTP evidence','Revisar evidência HTTP'):w('Capturar evidencia HTTP','Capture HTTP evidence','Capturar evidência HTTP'));
  d.el.setAttribute('data-http-editor',uid||'new');
  d.el.setAttribute('data-http-project',S.slug);
  const state={slug:S.slug,workspace:S.workspace_id},form=h('fieldset',{}),meta=metadata(formdata.meta);form.append(meta.node);
  let requestForm,responseForm,identity,captured,hasResponse,publish,requestCopy,responseCopy,caption,review;
  if(!row){
   identity=input(w(...words.identity),formdata.identity||'',{maxlength:500});captured=input(w('Fecha/hora observada','Observed date/time','Data/hora observada'),formdata.captured_at||'',{maxlength:100});
   requestForm=messageForm(null,true);responseForm=messageForm(null,false);requestForm.restore(formdata.request);responseForm.restore(formdata.response);
   hasResponse=h('input',{type:'checkbox',checked:formdata.has_response===false?null:'',onchange:()=>{responseForm.node.disabled=!hasResponse.checked;}});responseForm.node.disabled=!hasResponse.checked;
   form.append(h('div',{class:'http-grid'},identity.node,captured.node),h('div',{class:'http-grid'},requestForm.node,responseForm.node),h('label',{class:'wf-check'},hasResponse,w('Se capturó una respuesta','A response was captured','Uma resposta foi capturada')));
  }else{
   form.append(h('p',{},w('Original privado · ','Private original · ','Original privado · '),h('code',{},row.sha256)),h('p',{},row.original.identity+' · '+row.original.captured_at+' · '+row.original.source));
   form.append(h('details',{},h('summary',{},w('Ver petición y respuesta originales','View original request and response','Ver requisição e resposta originais')),h('div',{class:'http-grid'},h('pre',{class:'http-wire'},wire(row.original.request,true)),h('pre',{class:'http-wire'},wire(row.original.response,false)))));
   const pub=formdata.publication===undefined?row.publication:formdata.publication;
   publish=h('input',{type:'checkbox',checked:pub?'':null,'data-http-publish':''});
   requestCopy=input(w('Petición publicable','Publishable request','Requisição publicável'),pub?.request_text||'',{rows:9,maxlength:262144,'data-http-publication':'request'});
   responseCopy=input(w('Respuesta publicable','Publishable response','Resposta publicável'),pub?.response_text||'',{rows:9,maxlength:262144,'data-http-publication':'response'});
   caption=input(w('Descripción revisada para el informe','Reviewed report caption','Legenda revisada para o relatório'),pub?.caption||'',{rows:3,maxlength:8000,'data-http-publication':'caption'});
   review=h('input',{type:'checkbox','data-http-reviewed':''});
   const publication=h('div',{'data-http-publication-editor':''},h('p',{},w('Esta copia aparece en el informe técnico de los hallazgos vinculados. Revisa credenciales, datos personales y fragmentos antes de aprobarla. El original permanece privado.','This copy appears in linked findings in the technical report. Review credentials, personal data and excerpts before approving it. The original stays private.','Esta cópia aparece nos achados vinculados do relatório técnico. Revise credenciais, dados pessoais e trechos antes de aprová-la. O original permanece privado.')),
    button(w('Copiar original para editar','Copy original for editing','Copiar original para editar'),()=>{requestCopy.el.value=wire(row.original.request,true);responseCopy.el.value=wire(row.original.response,false);review.checked=false;form.dispatchEvent(new Event('input',{bubbles:true}));}),
    h('div',{class:'http-grid'},requestCopy.node,responseCopy.node),caption.node,h('label',{class:'wf-check'},review,w('Revisé el contenido exacto de esta copia para el informe técnico.','I reviewed the exact contents of this copy for the technical report.','Revisei o conteúdo exato desta cópia para o relatório técnico.')));
   function show(){publication.hidden=!publish.checked;review.checked=false;}publish.addEventListener('change',show);show();publication.addEventListener('input',event=>{if(event.target!==review)review.checked=false;});
   form.append(h('label',{class:'wf-check'},publish,w('Incluir una copia revisada en el informe técnico','Include a reviewed copy in the technical report','Incluir uma cópia revisada no relatório técnico')),publication);
  }
  const read=()=>({data:{schema:1,kind:row?'edit':'new',uid:uid||'',meta:meta.read(),...(row?{publication:publish.checked?{request_text:requestCopy.el.value,response_text:responseCopy.el.value,caption:caption.el.value}:null}:{identity:identity.el.value,captured_at:captured.el.value,request:requestForm.raw(),response:responseForm.raw(),has_response:hasResponse.checked})}});
  d.content.append(form);
  const pending=PendingUI.attach(key,w('Evidencia HTTP pendiente','Pending HTTP evidence','Evidência HTTP pendente'),read,{container:d.content,events:form,origin:recovered,onDiscard:()=>d.el.close()});
  let busy=false;
  const submit=button(w('Guardar evidencia','Save evidence','Salvar evidência'),async()=>{
   if(busy)return;busy=true;submit.disabled=true;d.close.disabled=true;pending.setBusy(true);d.error.textContent='';
   try{
    const metaData=meta.read();let path='',payload;
    if(row){if(JSON.stringify(rows().find(current=>current.uid===uid))!==JSON.stringify(row))throw Error(errorText());payload={...metaData,publication:publish.checked?{request_text:requestCopy.el.value,response_text:responseCopy.el.value,caption:caption.el.value}:null,ack_reviewed:review.checked};path='/'+encodeURIComponent(uid)+'/edit';if(publish.checked&&!review.checked)throw Error(w('Revisa y confirma la copia publicable.','Review and confirm the publication copy.','Revise e confirme a cópia publicável.'));}
    else{payload={finding_uids:metaData.finding_uids,asset_uids:metaData.asset_uids,records:[{title:metaData.title,notes:metaData.notes,original:{request:requestForm.read(),response:hasResponse.checked?responseForm.read():null,captured_at:captured.el.value,identity:identity.el.value,source:'manual'}}]};}
    const pendingRevision=pending.handle.revision;await mutate(state,path,payload,form);await pending.committed(pendingRevision);d.el.close();
   }catch(e){d.error.textContent=e.message;}finally{busy=false;submit.disabled=false;d.close.disabled=false;pending.setBusy(false);}
  },true,{'data-http-save':''});
  d.el.addEventListener('cancel',event=>{if(busy)event.preventDefault();});d.content.append(submit);meta.node.querySelector('input')?.focus();
 }
 function inspector(row,container){
  container.append(h('p',{},row.original.identity||w('Identidad no registrada','Identity not recorded','Identidade não registrada')),h('p',{},row.original.request.method+' '+row.original.request.url),h('pre',{class:'http-wire'},wire(row.original.request,true)),h('pre',{class:'http-wire'},wire(row.original.response,false)),button(w('Anotar / revisar copia','Annotate / review copy','Anotar / revisar cópia'),()=>edit(row.uid)));
 }
 async function compare(){
  if(rows().length<2)return;
  const d=dialog(w('Comparar evidencia HTTP','Compare HTTP evidence','Comparar evidência HTTP')),state={slug:S.slug,workspace:S.workspace_id};
  const options=()=>rows().map(r=>h('option',{value:r.uid},r.title+' · '+r.original.identity));
  const a=h('select',{'aria-label':'A'},options()),b=h('select',{'aria-label':'B'},options());b.selectedIndex=1;
  let generation=0;
  const result=h('div',{}),run=button(w('Comparar A → B','Compare A → B','Comparar A → B'),async()=>{
   const token=++generation,left=a.value,right=b.value,current=()=>d.el.isConnected&&token===generation&&a.value===left&&b.value===right;
   run.disabled=true;d.error.textContent='';result.replaceChildren();try{
    if(!await doSave()||state.slug!==S.slug||state.workspace!==S.workspace_id)throw Error(errorText());
    if(!current())return;
    const tag=projectStore.etag,params=new URLSearchParams({left,right,revision:tag});
    const response=await requireOk(await appFetch('/api/projects/'+encodeURIComponent(state.slug)+'/http-evidence/compare?'+params));const data=await response.json();
    if(!current())return;
    if(state.slug!==S.slug||state.workspace!==S.workspace_id||tag!==projectStore.etag||projectStore.dirty)throw Error(errorText());
    result.replaceChildren();for(const key of ['request','response'])result.append(h('h3',{},w(...words[key])),h('pre',{class:'http-wire'},data[key].truncated?w('Comparación extensa: revisa ambos originales en sus fichas.','Large comparison: review both originals in their records.','Comparação extensa: revise os dois originais em suas fichas.'):data[key].equal?w('Sin diferencias','No differences','Sem diferenças'):data[key].diff));
   }catch(e){if(current())d.error.textContent=e.message;}finally{run.disabled=false;}
  },true);for(const selector of [a,b])selector.addEventListener('change',()=>{generation++;result.replaceChildren();d.error.textContent='';});d.content.append(h('p',{},w('Compara roles o antes/después. Las diferencias no determinan por sí solas una vulnerabilidad o corrección.','Compare roles or before/after. Differences alone do not establish a vulnerability or a fix.','Compare funções ou antes/depois. Diferenças isoladas não comprovam uma vulnerabilidade ou correção.')),h('div',{class:'http-grid'},a,b),run,result);
 }
 function importHar(){
  const d=dialog(w('Importar selección HAR','Import selected HAR entries','Importar entradas HAR selecionadas')),state={slug:S.slug,workspace:S.workspace_id},form=h('fieldset',{class:'http-har-form'}),list=h('div',{class:'http-har-list'}),selected=new Set();let har=null,generation=0,importing=false;
  const file=h('input',{type:'file',accept:'.har,.json,application/json','aria-label':'HAR (4 MiB / 100 entries)'});
  const current=token=>d.el.isConnected&&token===generation&&state.slug===S.slug&&state.workspace===S.workspace_id;
  const apply=button(w('Importar entradas seleccionadas','Import selected entries','Importar entradas selecionadas'),async()=>{
   if(importing||!har||!selected.size)return;
   importing=true;form.disabled=true;d.close.disabled=true;apply.disabled=true;d.error.textContent='';
   const payload={har,indices:[...selected]};
   try{await mutate(state,'/har',payload);d.el.close();}catch(e){if(d.el.isConnected)d.error.textContent=e.message;}
   finally{importing=false;form.disabled=false;d.close.disabled=false;apply.disabled=!har||!selected.size;}
  },true,{'data-http-har-import':'',disabled:''});
  d.el.addEventListener('cancel',event=>{if(importing)event.preventDefault();});
  file.addEventListener('change',async()=>{
   if(importing)return;
   const token=++generation;har=null;selected.clear();list.replaceChildren();apply.disabled=true;d.error.textContent='';
   try{
    const f=file.files[0];if(!f)return;if(f.size>4*1024*1024)throw Error(w('Máximo 4 MiB.','Maximum 4 MiB.','Máximo de 4 MiB.'));
    const candidate=JSON.parse(await f.text());if(!current(token))return;
    const result=await mutate(state,'/har-preview',{har:candidate});if(!current(token))return;
    har=candidate;
    for(const entry of result.entries){const check=h('input',{type:'checkbox',onchange:()=>{if(importing)return;if(check.checked)selected.add(entry.index);else selected.delete(entry.index);apply.disabled=!selected.size;}});list.append(h('label',{class:'wf-check'},check,entry.method+' '+entry.url+' · '+(entry.status||'—')));}
   }catch(e){if(current(token)){har=null;d.error.textContent=e.message;}}
  });
  form.append(file,list,apply);d.content.append(h('p',{},w('Máximo 4 MiB, 100 entradas y 256 KiB por cuerpo. Solo se importan las entradas que marques; permanecen privadas.','Maximum 4 MiB, 100 entries and 256 KiB per body. Only checked entries are imported; they remain private.','Máximo de 4 MiB, 100 entradas e 256 KiB por corpo. Somente as entradas marcadas são importadas; permanecem privadas.')),form);
 }
 function pairing(){
  const d=dialog(w('Vincular Burp Suite','Pair Burp Suite','Parear Burp Suite')),state={slug:S.slug,workspace:S.workspace_id},form=h('fieldset',{}),findings=choiceSet(w('Destino: hallazgos','Destination: findings','Destino: achados'),S.data.findings||[],[]),assets=choiceSet(w('Destino: activos','Destination: assets','Destino: ativos'),S.data.assets||[],[]),output=h('div',{});
  const generate=button(w('Generar código de un uso','Generate one-use code','Gerar código de uso único'),async()=>{generate.disabled=true;d.error.textContent='';try{const data=await mutate(state,'/pairing',{finding_uids:findings.read(),asset_uids:assets.read()},form);const code=input(w('Código de vinculación','Pairing code','Código de pareamento'),data.code,{rows:4,readonly:'','data-http-pair-code':''});output.replaceChildren(h('p',{},w('Caduca en 15 minutos o cuando cambie el proyecto. Copia este código en la extensión y envía solo los mensajes seleccionados. Después del envío, recarga el proyecto para verlos.','Expires in 15 minutes or when the project changes. Copy this code into the extension and send only selected messages. Reload the project after sending to see them.','Expira em 15 minutos ou quando o projeto muda. Copie este código na extensão e envie apenas as mensagens selecionadas. Recarregue o projeto após o envio para vê-las.')),code.node,button(w('Revocar código','Revoke code','Revogar código'),async()=>{try{await mutate(state,'/pairing/revoke',{});output.replaceChildren();}catch(e){d.error.textContent=e.message;}}));code.el.select();}catch(e){d.error.textContent=e.message;}finally{generate.disabled=false;}},true);
  form.append(findings.node,assets.node);d.content.append(h('p',{},w('La extensión local no ejecuta peticiones a objetivos ni recorre el historial. El envío entra como evidencia privada y conserva el destino elegido aquí.','The local extension does not send target requests or traverse history. Selected messages arrive as private evidence at the destination chosen here.','A extensão local não envia requisições aos alvos nem percorre o histórico. As mensagens selecionadas entram como evidência privada no destino escolhido aqui.')),form,generate,output);
 }
 function render(host){
  const list=h('div',{class:'http-records'}),search=h('input',{type:'search','aria-label':w('Buscar evidencia HTTP','Search HTTP evidence','Pesquisar evidência HTTP'),placeholder:w('URL, rol, título o anotación','URL, role, title or annotation','URL, função, título ou anotação')});
  host.replaceChildren(h('section',{class:'http-workspace','aria-label':w('Evidencia HTTP','HTTP evidence','Evidência HTTP')},h('p',{},w('Peticiones y respuestas privadas, vínculos y copias técnicas revisadas.','Private requests and responses, links and reviewed technical copies.','Requisições e respostas privadas, vínculos e cópias técnicas revisadas.')),h('div',{class:'studio-actions'},button(w('Capturar HTTP','Capture HTTP','Capturar HTTP'),()=>edit(),true,{'data-http-new':''}),button(w('Importar HAR','Import HAR','Importar HAR'),importHar),button(w('Comparar','Compare','Comparar'),compare,false,{disabled:rows().length<2?'':null}),button(w('Vincular Burp','Pair Burp','Parear Burp'),pairing)),search,list));
  function draw(){const q=search.value.toLocaleLowerCase();list.replaceChildren();const visible=rows().filter(row=>[row.title,row.notes,row.original.request.url,row.original.identity].join(' ').toLocaleLowerCase().includes(q));for(const row of visible)list.append(h('article',{class:'http-record','data-http-record':row.uid},h('div',{},h('h3',{},row.title),h('code',{},row.original.request.method+' '+row.original.request.url),h('p',{},row.original.identity||w('Identidad no registrada','Identity not recorded','Identidade não registrada')),h('p',{},row.publication?w('Copia técnica revisada','Reviewed technical copy','Cópia técnica revisada'):w('Solo privado','Private only','Somente privado'))),button(w('Abrir evidencia','Open evidence','Abrir evidência'),()=>edit(row.uid))));if(!visible.length)list.append(h('p',{},w('No hay evidencias que coincidan.','No matching evidence.','Nenhuma evidência correspondente.')));}
  search.addEventListener('input',draw);draw();
 }
 PendingUI.register('http:',{validate:row=>restoreData(row),missingReference:row=>{const d=restoreData(row);return !!d.uid&&!rows().some(r=>r.uid===d.uid)||d.meta.finding_uids.some(uid=>!(S.data.findings||[]).some(f=>f.uid===uid))||d.meta.asset_uids.some(uid=>!(S.data.assets||[]).some(a=>a.uid===uid));},restore:row=>edit(restoreData(row).uid||null,row)});
 window.ReportGenReviewHooks=window.ReportGenReviewHooks||{};
 const previousItems=window.ReportGenReviewHooks.inspectorItems;
 window.ReportGenReviewHooks.inspectorItems=finding=>[...(previousItems?.(finding)||[]),...rows().filter(row=>row.finding_uids.includes(finding.uid)).map(row=>({uid:'http:'+row.uid,title:row.title,render:container=>inspector(row,container)}))];
 function forgetPending(slug,key){
  const uid=key?.startsWith('http:')?key.slice(5):null;
  for(const dialog of document.querySelectorAll('[data-http-editor]'))if(dialog.dataset.httpProject===slug&&(uid===null||dialog.dataset.httpEditor===uid))dialog.close();
 }
 return{render,open:uid=>edit(uid),wire,forgetPending};
})();
