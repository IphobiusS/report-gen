const {JSDOM} = require('jsdom');
const fs = require('fs'), path = require('path'), assert = require('node:assert/strict');
const base=process.argv[2], root=path.resolve(__dirname,'..');
let cookie='';const downloads=[], requests=[];
async function request(url,options={}) {
  requests.push({url,options});
  const headers={...options.headers};if(cookie)headers.Cookie=cookie;
  const response=await fetch(new URL(url,base),{...options,headers});
  const set=response.headers.get('set-cookie');if(set)cookie=set.split(';')[0];
  return response;
}
async function until(predicate) {
  for(let i=0;i<150;i++){if(predicate())return;await new Promise(r=>setTimeout(r,20));}
  throw new Error('UI timeout');
}
(async()=>{
  const dom=new JSDOM(fs.readFileSync(path.join(root,'webapp/static/index.html'),'utf8'),{url:base,runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window;w.fetch=request;w.confirm=()=>true;w.alert=()=>{};
  w.HTMLElement.prototype.scrollIntoView=()=>{};
  w.HTMLAnchorElement.prototype.click=function(){downloads.push(this.download);};
  w.URL.createObjectURL=()=> 'blob:report-test';w.URL.revokeObjectURL=()=>{};
  const sources=[];
  for(const name of ['cvss40.js','save-manager.js','workflow.js','app.js']) {
    let source=fs.readFileSync(path.join(root,'webapp/static',name),'utf8');
    if(name==='app.js')source+='\nwindow.qa={S,projectStore,scheduleSave,doSave,loadProject,exportFile,runValidation,WorkflowUI,select,renderMain,renumberFindings,saveToLibrary};';
    sources.push(source);
  }
  w.eval(sources.join('\n'));
  await until(()=>w.qa.S.slug==='a'&&!w.qa.projectStore.loading);
  const q=w.qa;
  q.S.data.meta.report_title='A edited';q.scheduleSave();await q.loadProject('b');
  assert.equal(q.S.slug,'b');
  assert.equal((await request('/api/projects/a').then(r=>r.json())).meta.report_title,'A edited');
  assert.equal((await request('/api/projects/b').then(r=>r.json())).meta.report_title,'B');
  w.document.querySelector('#exportFormat').value='md';await q.exportFile();
  assert.equal(downloads.at(-1),'b.zip');
  const previewCount = requests.filter(r=>r.url==='/api/projects/b/preview').length;
  q.S.data.meta.report_title='Autosaved B';q.scheduleSave();
  await until(()=>!q.projectStore.dirty);
  await until(()=>requests.filter(r=>r.url==='/api/projects/b/preview').length>previewCount);
  assert.ok(w.document.querySelector('#projectSelect').selectedOptions[0].textContent.includes('Autosaved B'));

  // Exercise the new editor flows against the real API, including detached DOM updates.
  const clickText=(text,within=w.document)=>{const b=[...within.querySelectorAll('button')].find(b=>b.textContent.trim()===text);assert.ok(b,'Button '+text);b.click();};
  const setField=(key,value,within=w.document.querySelector('#editor'))=>{const el=within.querySelector(`[data-field="${key}"]`);assert.ok(el,'Field '+key);el.value=value;el.dispatchEvent(new w.Event(el.tagName==='SELECT'?'change':'input',{bubbles:true}));};
  const view=async kind=>{q.select('workflow',kind);await until(()=>w.document.querySelector(`[data-workflow-view="${kind}"]`)?.childNodes.length>0);};
  w.document.querySelector('[data-add="blank"]').click();
  setField('title','Control de acceso');setField('description_md','TODO describir');
  const stable=q.S.data.findings[0].uid;assert.ok(stable);
  await view('assets');clickText('Añadir activo');await until(()=>w.document.querySelector('[data-field="target"]'));
  setField('name','Portal');setField('target','https://portal.test/api');await q.doSave();
  await view('coverage');clickText('Añadir prueba');await until(()=>w.document.querySelector('[data-field="test"]'));
  setField('test','Autorización');setField('status','done');setField('asset_uid',q.S.data.assets[0].uid);setField('limitations_md','Sin pruebas destructivas');await q.doSave();
  q.select('finding',0);const link=w.document.querySelector('[data-field="asset_uids"] input');link.click();await q.doSave();assert.equal(q.S.data.findings[0].asset_uids[0],q.S.data.assets[0].uid);
  await view('review');assert.ok(w.document.querySelector('#editor').textContent.includes('Texto pendiente: TODO'));
  const issue=[...w.document.querySelectorAll('.wf-card')].find(c=>c.textContent.includes('Texto pendiente: TODO'));clickText('Ir al campo',issue);
  await until(()=>w.document.activeElement.dataset.field==='description_md');
  setField('description_md','Respuesta sin comprobar permisos');setField('impact_md','Lectura de datos de otro usuario');setField('remediation_md','Verificar permisos en el servidor');await q.doSave();
  await view('retest');setField('owner','Equipo App');setField('due_date','2026-10-01');setField('result','fixed');setField('notes_md','El acceso devuelve 403.');clickText('Guardar comprobación');
  await until(()=>q.S.data.findings[0].retests?.length===1);assert.equal(q.S.data.findings[0].status,'verified_fixed');
  await view('history');setField('label','Entrega UI');setField('stage','delivered');clickText('Crear versión');
  await until(()=>w.document.querySelector('#editor').textContent.includes('Entrega UI'));
  const named=[...w.document.querySelectorAll('.wf-card')].find(c=>c.textContent.includes('Entrega UI'));clickText('Comparar',named);await until(()=>w.document.querySelector('.wf-diff')?.textContent.includes('Cambios'));
  await q.saveToLibrary(q.S.data.findings[0]);await until(()=>w.document.querySelector('[role="dialog"]'));
  let dialog=w.document.querySelector('[role="dialog"]');
  const reusable=JSON.parse(dialog.querySelector('[data-field="json"]').value);assert.equal(reusable.uid,undefined);assert.equal(reusable.retests,undefined);assert.equal(reusable.owner,undefined);
  dialog.querySelector('input[type="checkbox"]').click();clickText('Guardar versión de plantilla',dialog);await until(()=>!dialog.isConnected);
  await view('library');clickText('Insertar');await until(()=>w.document.querySelector('[role="dialog"] [data-field="objetivo"]'));
  dialog=w.document.querySelector('[role="dialog"]');setField('objetivo','https://another.test',dialog);clickText('Insertar en el proyecto',dialog);
  await until(()=>q.S.data.findings.length===2);assert.notEqual(q.S.data.findings[1].uid,stable);assert.equal(q.S.data.findings[0].uid,stable);assert.equal(q.S.data.findings[1].affected,'https://another.test');
  q.S.data.findings.reverse();q.renumberFindings();await q.doSave();assert.equal(q.S.data.findings[1].uid,stable);
  await view('backup');clickText('Descargar respaldo ZIP');await until(()=>downloads.at(-1)==='b-project.zip');
  // Register an uploaded image through HTTP, then perform redaction from the actual dialog.
  const token2=(await request('/api/session').then(r=>r.json())).csrf;
  const multipart=new FormData();multipart.append('file',new Blob([Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8z8DAwMDAxMDAwMDAAAANHQEDasKb6QAAAABJRU5ErkJggg==','base64')],{type:'image/png'}),'evidence.png');
  const upload=await request('/api/projects/b/image',{method:'POST',headers:{'X-CSRF-Token':token2},body:multipart});assert.equal(upload.status,200);
  const image=await upload.json();
  const registration=await request('/api/projects/b/evidence',{method:'POST',headers:{'X-CSRF-Token':token2,'Content-Type':'application/json','If-Match':q.projectStore.etag},body:JSON.stringify({src:image.src,title:'Evidencia UI'})});assert.equal(registration.status,200);
  await q.loadProject('b');await view('evidence');assert.ok(w.document.querySelector('.wf-gallery img'));clickText('Anotar / censurar');
  dialog=w.document.querySelector('[role="dialog"]');clickText('Añadir zona con coordenadas',dialog);assert.ok(dialog.querySelector('.wf-overlay.redact'));clickText('Aplicar y guardar copia',dialog);
  await until(()=>!dialog.isConnected);assert.notEqual(q.S.data.evidence[0].src,image.src);
  await view('history');const delivered=[...w.document.querySelectorAll('.wf-card')].find(c=>c.textContent.includes('Entrega UI'));assert.ok(delivered);clickText('Restaurar',delivered);
  await until(()=>q.S.data.findings.length===1&&q.S.data.evidence.length===0);assert.equal(q.S.data.findings[0].uid,stable);
  q.select('report',-1);
  q.S.data.findings=[{id:'F1',title:'Mismatch',cvss:'1.0',severity:'low',cvss_vector:'CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H'}];
  await q.runValidation();assert.ok(w.document.querySelectorAll('.val-item').length>0);
  q.S.data.findings=[];
  const current=await request('/api/projects/b');const other=await current.json();other.meta.report_title='Other tab';
  const token=(await request('/api/session').then(r=>r.json())).csrf;
  await request('/api/projects/b',{method:'PUT',headers:{'Content-Type':'application/json','X-CSRF-Token':token,'If-Match':current.headers.get('etag')},body:JSON.stringify(other)});
  q.S.data.meta.report_title='Unsaved local';q.scheduleSave();
  assert.equal(await q.doSave(),false);assert.equal(q.projectStore.dirty,true);
  assert.equal((await request('/api/projects/b').then(r=>r.json())).meta.report_title,'Other tab');
  dom.window.close();
  console.log('PASS: full editor + real Flask API: load, save/switch, CSRF, Markdown ZIP, validation, conflict retention, assets, coverage, review navigation, retest, history, library, backup, evidence redaction and full restore');
})().catch(error=>{console.error(error);process.exitCode=1;});
