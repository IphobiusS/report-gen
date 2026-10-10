/* Private pending inputs. Recovery always opens a form; it never publishes or attaches data. */
const PendingUI=(()=>{
'use strict';const w=(es,en)=>S.uiLang==='en'?en:es,journal=new PendingJournal(),active=new Map();
const pack=value=>JSON.parse(JSON.stringify(value,(_,v)=>v instanceof Set?{__pendingSet:[...v]}:v instanceof Map?{__pendingMap:[...v]}:v));
const unpack=value=>JSON.parse(JSON.stringify(value),(_,v)=>v&&Array.isArray(v.__pendingSet)?new Set(v.__pendingSet):v&&Array.isArray(v.__pendingMap)?new Map(v.__pendingMap):v);
function track(key,label,read,options={}){
 const slug=S.slug,id=slug+'|'+key,previous=active.get(id);
 if(previous){previous.read=read;if(options.origin){previous.origin=options.origin;previous.etag=projectStore.etag;}return previous;}
 const handle={slug,key,label,read,etag:projectStore.etag,revision:0,persisted:0,record:null,error:null,nodes:new Set(),origin:options.origin||null};active.set(id,handle);return handle;
}
function paint(handle){for(const node of handle.nodes){if(!node.isConnected){handle.nodes.delete(node);continue;}node.textContent=handle.error?w('Solo en esta pestaña: ','Only in this tab: ')+handle.error.message:handle.revision===0?w('Se protegerá localmente al editar.','Protected locally when edited.'):handle.persisted===handle.revision?w('Pendiente recuperable en este navegador · 30 días · sin cifrar','Pending input recoverable in this browser · 30 days · unencrypted'):w('Protegiendo contenido pendiente…','Protecting pending input…');}}
function status(handle){const node=h('p',{role:'status','data-pending-status':handle.key});handle.nodes.add(node);queueMicrotask(()=>paint(handle));return node;}
function changed(handle){
 const revision=++handle.revision,snapshot=handle.read();handle.error=null;paint(handle);
 const job=journal.put({slug:handle.slug,key:handle.key,label:handle.label,etag:handle.etag,data:pack(snapshot.data),file:snapshot.file||null});
 handle.job=job.then(async row=>{handle.record=row;handle.persisted=revision;if(revision===handle.revision)handle.error=null;if(handle.origin){await journal.removeUnchanged(handle.origin);handle.origin=null;}paint(handle);return row;}).catch(error=>{if(revision===handle.revision)handle.error=error;paint(handle);return null;});return handle.job;
}
async function clear(handle,revision=handle.revision){
 await handle.job;if(revision!==handle.revision)return false;
 if(handle.record&&!await journal.removeUnchanged(handle.record))throw Error(w('La copia cambió; vuelve a revisarla.','The copy changed; review it again.'));
 if(handle.origin&&!await journal.removeUnchanged(handle.origin))throw Error(w('El original cambió; vuelve a revisarlo.','The original changed; review it again.'));
 if(revision!==handle.revision)return false;
 active.delete(handle.slug+'|'+handle.key);handle.revision=0;handle.persisted=0;handle.record=null;handle.origin=null;paint(handle);return true;
}
async function committed(handle,revision){
 try{return {finished:await clear(handle,revision),warning:null};}
 catch(error){const finished=revision===handle.revision;if(finished){active.delete(handle.slug+'|'+handle.key);handle.nodes.clear();}return {finished,warning:error};}
}
function missingReference(row){
 const data=unpack(row.data),findings=new Set((S.data.findings||[]).map(x=>x.uid)),evidence=new Set((S.data.evidence||[]).map(x=>x.uid));
 if(data.finding_uid&&!findings.has(data.finding_uid))return true;
 if((data.evidence_uids||[]).some(uid=>!evidence.has(uid)))return true;
 if(data.uid&&row.key.startsWith('insights:claim-')&&!(S.data.insights?.claims||[]).some(item=>item.uid===data.uid))return true;
 if(data.uid&&row.key.startsWith('insights:risk-')&&!(S.data.insights?.risks||[]).some(item=>item.uid===data.uid))return true;
 if(row.key.startsWith('insights:resolve-')&&!(S.data.insights?.comments||[]).some(item=>item.uid===row.key.slice('insights:resolve-'.length)&&item.status==='open'))return true;
 if(data.selected instanceof Set&&[...data.selected].some(uid=>!findings.has(uid)))return true;
 return false;
}
async function list(slug){return journal.list(slug);}
function recoverySection(row,onRemoved){
 const section=h('section',{class:'card','data-pending-record':row.id}),details=h('details',{},h('summary',{},w('Revisar contenido pendiente','Review pending content')));
 details.append(h('pre',{class:'publication-text',tabindex:0},JSON.stringify(row.data,null,2)));
 if(row.file){details.append(h('p',{},(row.file.name||'image')+' · '+row.file.size+' bytes'));let url=null;details.addEventListener('toggle',()=>{if(details.open&&!url){url=URL.createObjectURL(row.file);details.append(h('img',{class:'imgprev',src:url,alt:w('Imagen pendiente, todavía sin incorporar','Pending image, not yet incorporated')}));}else if(!details.open&&url){URL.revokeObjectURL(url);url=null;details.querySelector('img')?.remove();}});section.release=()=>{if(url)URL.revokeObjectURL(url);};}
 section.append(h('h3',{},row.label),h('p',{},new Date(row.updated).toLocaleString()),details);
 const presentedRevision=projectStore.etag,stale=row.etag!==presentedRevision,review=h('input',{type:'checkbox'});
 if(stale)section.append(h('p',{},w('El proyecto cambió desde esta copia. Revisa sus datos actuales antes de recuperar.','The project changed since this copy. Review its current data before recovering.')),h('label',{class:'wf-check'},review,w('Revisé la versión actual; recuperaré solo el formulario pendiente.','I reviewed the current version; recover the pending form only.')));
 const action=(label,run)=>{const b=h('button',{type:'button',class:'btn'},label);b.addEventListener('click',async()=>{b.disabled=true;try{await run();}catch(e){toast(e.message,'err');}finally{b.disabled=false;}});return b;};
 const buttons=h('div',{class:'studio-actions'});section.append(buttons);
 buttons.append(action(w('Recuperar formulario','Recover form'),async()=>{
  if(row.slug!==S.slug)throw Error(w('Abre el proyecto original.','Open the original project.'));
  const fresh=(await list(row.slug)).find(item=>item.id===row.id);if(row.slug!==S.slug||fresh?.token!==row.token)throw Error(w('La copia cambió; vuelve a abrir la recuperación.','The copy changed; reopen recovery.'));
  if(projectStore.etag!==presentedRevision)throw Error(w('La revisión cambió; vuelve a abrir la recuperación.','The revision changed; reopen recovery.'));
  if(stale&&!review.checked)throw Error(w('Revisa y confirma la versión actual.','Review and confirm the current version.'));
  if(missingReference(row))throw Error(w('Una referencia ya no existe. Conserva el texto mostrado y elige un destino válido; no se incorporó nada.','A reference no longer exists. Keep the displayed text and choose a valid target; nothing was incorporated.'));
  if(active.get(row.slug+'|'+row.key)?.revision)throw Error(w('Este formulario ya tiene cambios en la pestaña. Consérvalos o descártalos antes de recuperar otra copia.','This form already has changes in this tab. Keep or discard them before recovering another copy.'));
  if(row.format!=='report-gen-pending'||row.version!==1)throw Error(w('Versión de copia no compatible.','Unsupported copy version.'));
  if(row.key==='capture'){section.closest('dialog')?.close();WorkbenchUI.capture(row);}
  else if(row.key.startsWith('insights:')){section.closest('dialog')?.close();InsightsUI.restorePending(row);}
 }),action(w('Eliminar copia pendiente','Delete pending copy'),async()=>{if(row.slug!==S.slug)throw Error(w('El proyecto cambió.','The project changed.'));if(!confirm(w('¿Eliminar esta copia local pendiente?','Delete this pending local copy?')))return;if(!await journal.removeUnchanged(row))throw Error(w('La copia cambió; vuelve a abrir la recuperación.','The copy changed; reopen recovery.'));const handle=active.get(row.slug+'|'+row.key);if(handle?.record?.id===row.id&&handle.record.token===row.token){handle.record=null;handle.persisted=0;handle.error=Error(w('Copia local eliminada. El formulario sigue en esta pestaña.','Local copy deleted. The form remains in this tab.'));paint(handle);}section.release?.();section.remove();onRemoved?.();}));return section;
}
window.addEventListener('beforeunload',event=>{if([...active.values()].some(handle=>handle.revision>handle.persisted||handle.error)){event.preventDefault();event.returnValue='';}});
function reset(slug){for(const id of active.keys())if(id.startsWith(slug+'|'))active.delete(id);}
return{journal,track,status,changed,clear,committed,list,recoverySection,pack,unpack,active,reset};
})();
