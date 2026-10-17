const {clickNavigationControl}=require('../tests/browser-navigation.cjs');
/* Real browser recovery/retention acceptance. Only disposable synthetic projects. */
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const out=path.resolve(option('--output','out/browser-0211')),engine=option('--browser','chromium');
const playwright=require(require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
if(!['chromium','firefox','webkit'].includes(engine))throw Error('Use chromium, firefox or webkit');
fs.mkdirSync(out,{recursive:true});const workspaces=[],servers=[],checks=[],errors=[],screens=[];let browser,page,base,server,info;
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({release:JSON.parse(fs.readFileSync(path.join(root,'package.json'))).version,engine,version:browser?.version(),checks,errors,screens},null,2));
const check=(name,condition,detail)=>{checks.push({name,passed:!!condition,detail});save();assert.ok(condition,name);console.log('PASS '+name);};
const workspace=()=>{const dir=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-'));fs.writeFileSync(path.join(dir,'.test-only'),'synthetic acceptance workspace');workspaces.push(dir);return dir;};
const watchdog=setTimeout(()=>{errors.push('Acceptance timeout: browser did not finish in 180 seconds');save();browser?.close().catch(()=>{});},180000);
async function start(dir,port=0){
 const child=spawn(process.env.RG_PYTHON||'python3',[path.join(root,'scripts/browser-server-0211.py'),'--workspace',dir,'--port',String(port)],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});servers.push(child);
 child.stderr.pipe(fs.createWriteStream(path.join(out,'server-'+servers.length+'.log')));
 const details=await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Server startup timeout')),20000);child.stdout.on('data',chunk=>{text+=chunk;if(text.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(text.split('\n')[0]));}catch(e){reject(e);}}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Server exited '+code));});});
 return {child,...details};
}
async function api(p,method,uri,body){return p.evaluate(async({method,uri,body})=>{const r=await appFetch(uri,{method,...(body!==undefined?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});return{status:r.status,data:await r.json()};},{method,uri,body});}
async function newPage(context){let timer;try{return await Promise.race([context.newPage(),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Browser could not create a page within 30 seconds')),30000);})]);}finally{clearTimeout(timer);}}
async function ready(p=page){await p.waitForFunction(()=>S.slug&&!projectStore.loading&&projectBusyCount===0);}
async function saved(p=page){await p.waitForFunction(()=>!projectStore.dirty&&!projectStore.lastError);}
async function edit(p,field,value){await p.evaluate(()=>select('finding',0));await p.locator('[data-field="'+field+'"]').fill(value);}
async function shot(name,p=page){await p.screenshot({path:path.join(out,name+'.png'),fullPage:false});screens.push({file:name+'.png',url:p.url(),viewport:p.viewportSize(),captured_at:new Date().toISOString()});save();}
async function fault(mode){check('Inyección controlada '+(mode||'desactivada'),(await api(page,'POST','/api/__test__/fault',{mode,slug:'audit-0211'})).status===200);}
(async()=>{
 const dir=workspace();info=await start(dir);server=info.child;base=info.url;
 browser=await playwright[engine].launch({headless:true,timeout:30000,...(engine==='chromium'&&process.env.RG_CHROMIUM_EXECUTABLE?{executablePath:process.env.RG_CHROMIUM_EXECUTABLE}:{})});
 const context=await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true,reducedMotion:'reduce'});
 context.on('page',p=>p.on('pageerror',e=>errors.push(String(e))));
 page=await newPage(context);await page.goto(base);await page.getByRole('button',{name:'Crear mi proyecto',exact:true}).click();
 await page.locator('dialog[data-design-mode=create] .experience-actions .primary').click();await page.locator('#mTitle').fill('Aurora: recuperación y privacidad [FICTICIO]');await page.locator('#mClient').fill('Cooperativa Aurora [FICTICIA]');await page.locator('#mSlug').fill('audit-0211');await page.locator('#mCreate').click();await ready();
 await page.getByRole('button',{name:'Añadir hallazgo',exact:true}).click();await page.locator('[data-field="title"]').fill('Hallazgo sintético 0.21.1');
 await page.locator('[data-field="description_md"]').fill('Caso ficticio para comprobar recuperación.');await page.locator('[data-field="impact_md"]').fill('Impacto inicial');await page.locator('[data-field="remediation_md"]').fill('Remediación inicial');await saved();
 // Both tabs start from exactly the same saved revision.
 const other=await newPage(context);await other.goto(base);await ready(other);
 const same=await other.evaluate(()=>projectStore.etag);check('Dos pestañas parten de la misma revisión',same===await page.evaluate(()=>projectStore.etag));
 await edit(page,'impact_md','Impacto guardado por pestaña A');await saved();
 await other.evaluate(()=>select('finding',0));
 await other.locator('[data-field="impact_md"]').fill('Impacto local de pestaña B');await other.locator('[data-field="remediation_md"]').fill('Remediación independiente de pestaña B');
 await other.getByRole('button',{name:'Resolver con versión guardada',exact:true}).waitFor();
 check('Conflicto 409 conserva ambos cambios de B',await other.evaluate(()=>projectStore.dirty&&projectStore.lastError.status===409&&S.data.findings[0].impact_md.includes('local')&&S.data.findings[0].remediation_md.includes('independiente')));
 await other.getByRole('button',{name:'Resolver con versión guardada',exact:true}).click();
 const merge=other.getByRole('dialog',{name:'Recuperar y resolver cambios'});await merge.waitFor();
 await merge.getByRole('radio',{name:'Guardado en disco',exact:true}).check();await shot('01-conflicto-dos-pestanas',other);
 await merge.getByRole('button',{name:'Aplicar selección y guardar',exact:true}).click();await saved(other);
 const merged=(await api(other,'GET','/api/projects/audit-0211')).data;
 check('Elección explícita conserva A y combina la remediación de B',merged.findings[0].impact_md==='Impacto guardado por pestaña A'&&merged.findings[0].remediation_md==='Remediación independiente de pestaña B');
 await other.close();await page.reload();await ready();
 // OSError faults happen inside the actual atomic storage write, not in a proxy.
 for(const mode of ['disk_full','permission']){
  const before=(await api(page,'GET','/api/projects/audit-0211')).data.findings[0].impact_md;
  await fault(mode);await edit(page,'impact_md','Edición recuperable '+mode);
  await page.getByRole('button',{name:'Reintentar guardado',exact:true}).waitFor();
  await page.waitForFunction(()=>projectStore.recoverableRevision===projectStore.revision);
  check(mode+': revisión anterior en disco y borrador recuperable', (await api(page,'GET','/api/projects/audit-0211')).data.findings[0].impact_md===before&&await page.evaluate(()=>projectStore.dirty&&projectStore.lastError.status===503));
  if(mode==='disk_full')await shot('02-disco-lleno-recuperable');
  await fault(null);await page.getByRole('button',{name:'Reintentar guardado',exact:true}).click();await saved();
  check(mode+': reintento guardado', (await api(page,'GET','/api/projects/audit-0211')).data.findings[0].impact_md==='Edición recuperable '+mode);
 }
 // Required annex + contextual feedback + bounded, non-disclosing scan.
 await page.locator('[data-studio-nav="deliver"]').click();await page.getByRole('button',{name:'Inventario de anexos',exact:true}).click();
 await page.locator('.annex-dialog details>summary').click();await page.getByRole('textbox',{name:'Nombre del anexo previsto'}).fill('../invalido.txt');
 await page.getByRole('button',{name:'Agregar al inventario',exact:true}).click();await page.locator('.annex-error').filter({hasText:'Nombre'}).waitFor();
 await page.getByRole('textbox',{name:'Nombre del anexo previsto'}).fill('evidencia.txt');check('El error del nombre desaparece al corregirlo',await page.locator('.annex-error').textContent()==='');
 await page.locator('[data-annex-declare-required]').check();await page.getByRole('button',{name:'Agregar al inventario',exact:true}).click();await page.getByText('Pendiente de cargar',{exact:true}).waitFor();
 const blocked=await page.evaluate(async()=>{const r=await appFetch('/api/projects/'+S.slug+'/jobs',{method:'POST',headers:{'Content-Type':'application/json','If-Match':projectStore.etag},body:JSON.stringify({kind:'delivery',formats:['html'],label:'Debe bloquearse',acknowledge_warnings:true})});return {status:r.status,text:await r.text()};});
 check('Anexo obligatorio ausente bloquea incluso aceptando avisos',blocked.status===422);
 await page.locator('.annex-dialog input[type=file]').setInputFiles({name:'evidencia.txt',mimeType:'text/plain',buffer:Buffer.from('token=SYNTHETIC_SECRET_0211\n')});await page.locator('.annex-item .annex-include').waitFor();
 check('Tamaño pequeño mostrado en bytes y no 0.0 KiB',await page.locator('.annex-size').textContent().then(x=>x==='28 bytes'));
 await page.getByRole('button',{name:'Analizar posibles secretos',exact:true}).click();await page.locator('.annex-scan').getByText('Posible credencial: 1',{exact:true}).waitFor();
 check('La vista del análisis no revela el secreto',!await page.locator('.annex-scan').textContent().then(t=>t.includes('SYNTHETIC_SECRET_0211')));
 await shot('03-anexo-obligatorio-y-analisis');
 await page.locator('.annex-item .annex-include').check();await page.getByText('Se incluirá en el paquete',{exact:true}).waitFor();
 await page.getByRole('button',{name:'Retirar del inventario',exact:true}).click();await page.getByText('No has declarado anexos.',{exact:false}).waitFor();await page.locator('.annex-dialog').getByRole('button',{name:'Cerrar',exact:true}).click();
 // Explicit retention cleanup preserves current data and original copy semantics.
 await clickNavigationControl(page,'#privacyBtn');await page.getByRole('dialog',{name:'Datos privados guardados'}).waitFor();await shot('04-datos-privados');
 check('Inventario muestra anexo retirado e historial',await page.locator('[data-privacy-category="unused_annexes"]').textContent().then(t=>t.includes('1 archivo')));
 await page.locator('[data-prune="unused_annexes"]').check();await page.locator('[data-prune="history"]').check();await page.getByRole('textbox',{name:'Identificador del proyecto para limpiar'}).fill('audit-0211');
 const oldData=(await api(page,'GET','/api/projects/audit-0211')).data;
 await page.getByRole('button',{name:'Limpiar lo seleccionado',exact:true}).click();await page.locator('[data-privacy-category="unused_annexes"]').filter({hasText:'0 archivos'}).waitFor();
 const priv=(await api(page,'GET','/api/projects/audit-0211/privacy')).data;
 check('Limpieza conserva datos actuales y un punto de recuperación',priv.versions===1&&JSON.stringify((await api(page,'GET','/api/projects/audit-0211')).data)===JSON.stringify(oldData));
 await page.locator('.privacy-dialog').getByRole('button',{name:'Cerrar',exact:true}).click();
 // Actual abrupt process termination between journaled renames.
 await fault('crash_after_move');const terminated=new Promise(resolve=>server.once('exit',resolve));
 await edit(page,'impact_md','RECUPERADO_TRAS_CIERRE_ABRUPTO');await page.getByRole('button',{name:'Reintentar guardado',exact:true}).waitFor();check('Proceso terminado en el punto de commit inyectado',await terminated===92);
 await page.waitForFunction(()=>projectStore.recoverableRevision===projectStore.revision);
 info=await start(dir,info.port);server=info.child;await page.reload();await ready();
 const recovered=page.getByRole('dialog',{name:'Hay borradores recuperables'});await recovered.waitFor();await shot('05-borrador-tras-reinicio');
 check('Reinicio recupera la última revisión completa del disco',(await api(page,'GET','/api/projects/audit-0211')).data.findings[0].impact_md==='Edición recuperable permission');
 await recovered.getByRole('button',{name:'Comparar y recuperar',exact:true}).first().click();await page.getByRole('button',{name:'Aplicar selección y guardar',exact:true}).click();await page.getByRole('dialog',{name:'Recuperar y resolver cambios'}).waitFor({state:'hidden'});await saved();
 check('Borrador del cierre abrupto recuperado y guardado',(await api(page,'GET','/api/projects/audit-0211')).data.findings[0].impact_md==='RECUPERADO_TRAS_CIERRE_ABRUPTO');
 // Real backup download, restored through the UI into a separate empty workspace.
 await clickNavigationControl(page,'#workspaceBackupBtn');const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Descargar ZIP sin cifrado',exact:true}).click();const backup=await downloaded;const backupPath=path.join(out,'respaldo-sintetico.zip');await backup.saveAs(backupPath);
 await context.close();
 if(server.exitCode===null){const stopped=new Promise(resolve=>server.once('exit',resolve));server.kill('SIGTERM');await stopped;}
 const destination=await start(workspace());const restoredContext=await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true});const restored=await newPage(restoredContext);restored.on('pageerror',e=>errors.push(String(e)));await restored.goto(destination.url);
 await clickNavigationControl(restored,'#workspaceBackupBtn');await restored.locator('[data-workspace-file="backup"]').setInputFiles(backupPath);await restored.getByRole('button',{name:'Restaurar espacio de trabajo',exact:true}).click();await ready(restored);
 const restoredData=(await api(restored,'GET','/api/projects/audit-0211')).data;
 check('Respaldo posterior a fallos restaurado en instalación vacía',restoredData.findings[0].impact_md==='RECUPERADO_TRAS_CIERRE_ABRUPTO'&&restoredData.findings[0].remediation_md==='Remediación independiente de pestaña B');
 await clickNavigationControl(restored,'#privacyBtn');await restored.locator('.privacy-dialog').waitFor();await restored.setViewportSize({width:390,height:844});await shot('06-privacidad-movil',restored);
 check('Vista de privacidad móvil dentro de la pantalla',await restored.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1&&document.querySelector('.privacy-dialog').getBoundingClientRect().width<=innerWidth));
 check('Sin excepciones JavaScript',errors.length===0,errors);
})().catch(async error=>{errors.push(String(error.stack||error));save();try{await page?.screenshot({path:path.join(out,'failure.png')});fs.writeFileSync(path.join(out,'failure-dom.html'),await page.content());}catch(_){}console.error(error);process.exitCode=1;}).finally(async()=>{
 clearTimeout(watchdog);await browser?.close();for(const child of servers){if(child.exitCode===null){child.kill('SIGTERM');await new Promise(resolve=>{child.once('exit',resolve);setTimeout(resolve,3000);});}}
 for(const directory of workspaces)fs.rmSync(directory,{recursive:true,force:true});save();
});
