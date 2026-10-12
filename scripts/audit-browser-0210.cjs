/* Real browser acceptance over a disposable Flask server. No user projects. */
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn,spawnSync}=require('node:child_process'),{createHash}=require('node:crypto');
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const root=path.resolve(__dirname,'..'),out=path.resolve(option('--output','out/browser-0210')),engine=option('--browser','chromium');
const playwright=require(require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
if(!['chromium','firefox'].includes(engine))throw Error('Use chromium or firefox');
fs.mkdirSync(out,{recursive:true});const checks=[],errors=[],external=[],screens=[];let browser,server,page,base,fixture;const requireVersion=JSON.parse(fs.readFileSync(path.join(root,'package.json'),'utf8')).version;
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify({engine,version:browser?.version(),checks,errors,external,screens},null,2));
const check=(name,condition,detail)=>{checks.push({name,passed:!!condition,detail});save();assert.ok(condition,name);console.log('PASS '+name);};
async function screenshot(name){const file=name+'.png';await page.screenshot({path:path.join(out,file),fullPage:false});screens.push({file,url:page.url(),viewport:page.viewportSize(),captured_at:new Date().toISOString()});save();}
async function ready(){await page.waitForFunction(()=>S.slug&&!projectStore.loading&&projectBusyCount===0);}
async function saved(){await page.waitForFunction(()=>!projectStore.dirty&&!projectStore.saving&&!projectStore.lastError);}
async function more(){if(!await page.locator('#studioMore').getAttribute('open').then(x=>x!==null))await page.locator('#studioMore>summary').click();}
async function closeMore(){if(await page.locator('#studioMore').getAttribute('open')!==null)await page.locator('#studioMore>summary').click();}
async function api(method,uri,body){return page.evaluate(async ({method,uri,body})=>{const r=await appFetch(uri,{method,...(body!==undefined?{headers:{'Content-Type':'application/json'},body:JSON.stringify(body)}:{})});return {status:r.status,data:await r.json()};},{method,uri,body});}
(async()=>{
 server=spawn(process.env.RG_PYTHON||'python3',[path.join(root,'scripts/browser-server-0210.py')],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});
 const serverLog=fs.createWriteStream(path.join(out,'server.log'));server.stderr.pipe(serverLog);
 const info=await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Server startup timeout')),20000);server.stdout.on('data',chunk=>{text+=chunk;if(text.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(text.split('\n')[0]))}catch(e){reject(e)}}});server.once('exit',code=>reject(Error('Server exited '+code)));});
 base=info.url;fixture=info.fixture;
 browser=await playwright[engine].launch({headless:true,timeout:45000,...(engine==='chromium'&&process.env.RG_CHROMIUM_EXECUTABLE?{executablePath:process.env.RG_CHROMIUM_EXECUTABLE}:{})});
 const context=await browser.newContext({viewport:{width:1440,height:1050},acceptDownloads:true,reducedMotion:'reduce'});
 context.on('page',p=>p.on('pageerror',e=>errors.push(p.url()+': '+String(e))));
 await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){external.push(url);return route.abort();}return route.continue();});
 page=await context.newPage();
 await page.goto(base);await page.getByRole('button',{name:'Probar demo Nimbus',exact:true}).waitFor();
 check('Inicio sin proyecto y versión actual',await page.locator('.brand-caption').innerText().then(t=>t.includes(requireVersion)));
 await page.getByRole('button',{name:'Probar demo Nimbus',exact:true}).click();await ready();
 check('Demo real crea doce hallazgos',await page.evaluate(()=>S.data.findings.length===12));
 await screenshot('01-inicio-nimbus');
 await page.getByRole('button',{name:'Hallazgos',exact:true}).click();
 await screenshot('02-hallazgos');
 check('Sin desbordamiento horizontal en escritorio',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await more();await page.locator('#newProjectBtn').click();await page.locator('dialog[data-design-mode=create] .experience-actions .primary').click();
 await page.locator('#mTitle').fill('Aurora: informe ficticio de aceptación');await page.locator('#mClient').fill('Cooperativa Aurora [FICTICIA]');await page.locator('#mSlug').fill('aurora');await page.locator('#mCreate').click();await ready();await closeMore();
 await page.getByRole('button',{name:'Añadir hallazgo',exact:true}).click();
 await page.locator('[data-field="title"]').fill('Control de sesión [SIMULADO]');
 check('Severidad inicial pendiente, sin clasificación inventada',await page.locator('[data-workpart="description"] .grid2 select').inputValue()==='');
 await page.locator('[data-workpart="description"] .grid2 select').selectOption('');
 await page.locator('[data-field="description_md"]').fill('| Campo | Valor |\n| --- | --- |\n| Entorno | Ficticio |\n\n1. Primera acción\n2. Segunda acción\n\n```text\nCODIGO_SINTETICO_0210 <ejemplo> & ñ\n```');
 await page.locator('[data-field="impact_md"]').fill('Caso ficticio para comprobar integridad de exportación.');
 await page.locator('[data-field="remediation_md"]').fill('Remediación simulada.');
 await saved();
 const saveEndpoint=base+'/api/projects/aurora';
 // An intermediary failure deliberately has no workspace header. Its body is
 // unverified: preserve the draft and allow retry without displaying that body.
 await page.route(saveEndpoint,route=>route.request().method()==='PUT'?route.fulfill({status:503,contentType:'application/json',body:'{"error":"Fallo sintético de escritura"}'}):route.continue());
 await page.locator('[data-field="impact_md"]').fill('Impacto conservado después de un fallo sintético de guardado.');
 await page.getByRole('button',{name:'Reintentar guardado',exact:true}).waitFor();
 check('Fallo sin identidad conserva cambios, permite reintento y oculta el cuerpo sin verificar',await page.evaluate(()=>projectStore.dirty&&!!projectStore.lastError&&!BrowserWorkspace.blocked()&&!$('#saveError').textContent.includes('Fallo sintético de escritura')&&S.data.findings[0].impact_md.includes('conservado')));
 await screenshot('11-recuperacion-guardado');await page.unroute(saveEndpoint);
 await page.getByRole('button',{name:'Reintentar guardado',exact:true}).click();await saved();
 check('Reintento persiste el contenido recuperado',(await api('GET','/api/projects/aurora')).data.findings[0].impact_md.includes('conservado'));
 await page.reload();await ready();
 check('Edición persiste tras recargar',await page.evaluate(()=>S.data.findings[0].description_md.includes('CODIGO_SINTETICO_0210')));
 await page.getByRole('button',{name:'Informe',exact:true}).click();
 await page.locator('[data-field="report_density"]').selectOption('compact');await saved();
 check('Espaciado del informe guardado',await page.evaluate(()=>S.data.meta.report_density==='compact'));
 await page.locator('[data-studio-nav="deliver"]').click();await page.getByRole('button',{name:'Inventario de anexos',exact:true}).click();
 await page.locator('.annex-dialog details>summary').click();
 await page.getByRole('textbox',{name:'Nombre del anexo previsto'}).fill('../error.txt');
 const invalid=page.waitForResponse(r=>r.url().endsWith('/attachments/declare'));
 await page.getByRole('button',{name:'Agregar al inventario',exact:true}).click();
 check('Nombre de anexo inseguro rechazado sin ensuciar el proyecto',(await invalid).status()===422&&await page.evaluate(()=>!projectStore.dirty));
 await page.locator('.annex-dialog input[type="file"]').setInputFiles({name:'evidencia-redactada.json',mimeType:'application/json',buffer:Buffer.from('{"caso":"ficticio","control":"ANEXO_0210"}\n')});
 await page.locator('.annex-item').waitFor();check('Anexo cargado excluido por defecto',await page.locator('.annex-item .annex-include').isChecked().then(x=>!x));
 await page.locator('.annex-item .annex-include').check();await page.getByText('Se incluirá en el paquete',{exact:true}).waitFor();
 await screenshot('03-anexos-revisados');
 await page.locator('.annex-dialog').getByRole('button',{name:'Cerrar',exact:true}).click();
 // Record every individual download, requested by the real editor controls.
 const downloads=[];
 for(const fmt of ['pdf','docx','md','html']){
  await more();if(await page.locator('#exportMenu').getAttribute('open')===null)await page.locator('#exportMenu>summary').click();
  await page.locator('#exportFormat').selectOption(fmt);
  const submitted=page.waitForResponse(r=>r.url().endsWith('/aurora/jobs')&&r.request().method()==='POST');
  await page.locator('#downloadBtn').click();const response=await submitted;
  const submittedJob=await response.json();check('Solicitud de exportación '+fmt,response.status()===202,submittedJob);
  let job;
  for(let tries=0;tries<360;tries++){const result=await api('GET','/api/jobs');job=result.data.find(j=>j.id===submittedJob.id);if(job&&['done','error','cancelled'].includes(job.stage))break;await new Promise(r=>setTimeout(r,250));}
  check('Exportación individual '+fmt,job?.stage==='done',job);
  const row=page.locator('[data-job="'+job.id+'"]');await row.locator('button').first().waitFor();
  const event=page.waitForEvent('download');await row.getByRole('button',{name:'Descargar',exact:true}).click();const download=await event;await download.saveAs(path.join(out,'aurora.'+(fmt==='md'?'zip':fmt)));downloads.push(fmt);
  await row.getByRole('button',{name:'Ver comprobaciones',exact:true}).click();await page.getByRole('dialog',{name:'Comprobaciones de la exportación',exact:true}).waitFor();
  check('Comprobaciones visibles '+fmt,await page.getByText('SHA-256:',{exact:false}).count()>0);
  if(fmt==='html')await screenshot('04-comprobaciones-html');
  await page.getByRole('dialog',{name:'Comprobaciones de la exportación',exact:true}).getByRole('button',{name:'Cerrar',exact:true}).click();
 }
 check('Cuatro descargas reales',downloads.length===4);
 await closeMore();await page.locator('[data-studio-nav="deliver"]').click();await page.getByRole('button',{name:'Elegir formatos',exact:true}).click();
 for(const fmt of ['pdf','docx','md','html'])await page.locator('[data-delivery-format="'+fmt+'"]').check();
 if(await page.locator('[data-delivery="ack"]').count())await page.locator('[data-delivery="ack"]').check();
 await page.getByRole('button',{name:'Generar paquete',exact:true}).click();
 let joint;for(let tries=0;tries<360;tries++){joint=(await api('GET','/api/jobs')).data.find(j=>j.filename==='aurora-entrega.zip');if(joint&&['done','error'].includes(joint.stage))break;await new Promise(r=>setTimeout(r,250));}
 check('Paquete de entrega con anexo',joint?.stage==='done',joint);
 const dl=page.waitForEvent('download');await page.locator('[data-job="'+joint.id+'"]').getByRole('button',{name:'Descargar',exact:true}).click();await (await dl).saveAs(path.join(out,'entrega.zip'));
 const verification=await api('GET','/api/jobs/'+joint.id+'/verification');fs.writeFileSync(path.join(out,'verificacion.json'),JSON.stringify(verification.data,null,2));check('Anexo presente en el manifiesto',!!verification.data.files['anexos/evidencia-redactada.json']);
 await screenshot('05-entrega-lista');
 // Portable HTML is tested in the actual browser, including offline mode.
 const reportPage=await context.newPage();await reportPage.goto('file://'+path.join(out,'aurora.html'));await reportPage.locator('#severity').selectOption('pending');
 check('Filtro pendiente en HTML',await reportPage.locator('.finding:not([hidden])').count()===1);
 await reportPage.locator('#kind').selectOption('machine');check('Filtro máquina no mezcla pendientes',await reportPage.locator('.finding:not([hidden])').count()===0&&await reportPage.locator('#severity').isDisabled());
 check('Estado vacío comprensible en HTML',await reportPage.locator('#empty-results').isVisible());
 await reportPage.locator('#clear-filters').click();check('Limpiar filtros restaura el informe',await reportPage.locator('.finding:not([hidden])').count()===1);
 await reportPage.goto('file://'+info.portable);
 const trustedResult=spawnSync(process.env.RG_PYTHON||'python3',['-c','import json, portable_report; print(json.dumps([portable_report.BOOTSTRAP, portable_report.SCRIPT]))'],{cwd:root,env:process.env,encoding:'utf8'});
 assert.equal(trustedResult.status,0,trustedResult.stderr);
 const trustedScripts=JSON.parse(trustedResult.stdout),actualScripts=await reportPage.locator('script').allTextContents();
 const portableCsp=await reportPage.locator('meta[http-equiv="Content-Security-Policy"]').getAttribute('content');
 const onlyTrustedScripts=actualScripts.length===2&&actualScripts.every((script,index)=>script===trustedScripts[index]&&portableCsp.includes("'sha256-"+createHash('sha256').update(script).digest('base64')+"'"));
 check('Contenido de prueba HTML permanece inerte',await reportPage.evaluate(()=>window.__report_attack===undefined)&&onlyTrustedScripts);
 check('HTML no contiene la nota privada ni el secreto sintético',await reportPage.locator('main').innerText().then(t=>!t.includes('PRIVATE_CAPTURE_AUDIT_0210')&&!t.includes('SYNTHETIC_SECRET_AUDIT_0210')&&t.includes('[CENSURADO]')));
 await reportPage.locator('#kind').selectOption('machine');check('HTML rico conserva la máquina filtrada',await reportPage.locator('.finding:not([hidden])').count()===1);
 await reportPage.locator('#clear-filters').click();await reportPage.locator('#severity').selectOption('pending');check('HTML rico conserva el hallazgo pendiente',await reportPage.locator('.finding:not([hidden])').count()===1);
 await reportPage.close();
 await page.locator('[data-studio-nav="work"]').click();await more();await page.locator('#studioPreferences>summary').click();await page.locator('#themeToggle').click();await closeMore();await screenshot('06-tema-claro');
 await page.setViewportSize({width:390,height:844});await page.locator('[data-studio-nav="deliver"]').click();await screenshot('07-movil-entrega');
 check('Sin desbordamiento horizontal en móvil',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
 await page.getByRole('button',{name:'Inventario de anexos',exact:true}).click();await screenshot('08-movil-anexos');
 check('Diálogo dentro de pantalla',await page.locator('.annex-dialog').evaluate(el=>{const r=el.getBoundingClientRect();return r.x>=0&&r.right<=innerWidth+1&&r.height<=innerHeight;}));
 await page.keyboard.press('Escape');check('Escape cierra diálogo',await page.locator('dialog[open]').count()===0);
 await page.setViewportSize({width:1440,height:1050});
 async function importProject(file,slug){
   await more();if(await page.locator('#projectActions').getAttribute('open')===null)await page.locator('#projectActions>summary').click();
   page.once('dialog',d=>d.accept(slug));const choose=page.waitForEvent('filechooser');
   await page.locator('#importProjectBtn').click();await (await choose).setFiles(file);
   await page.waitForFunction(expected=>S.slug===expected&&!projectStore.loading&&projectBusyCount===0,slug);await closeMore();
 }
 await importProject(fixture,'quality-imported');
 check('Respaldo importado desde el editor conserva cinco entradas',await page.evaluate(()=>S.data.findings.length===5));
 for(const query of ['COMANDO_BUSCABLE_0210','TEXTO_MAQUINA_BUSCABLE_0210','FASE_BUSCABLE_0210']){
   await page.locator('#globalSearch').fill(query);await page.locator('#searchResults .search-item').filter({hasText:query}).first().waitFor();
   check('Búsqueda de reproducción: '+query,await page.locator('#searchResults').innerText().then(x=>x.includes(query)));
   await page.locator('#searchResults .search-item').first().click();
 }
 await screenshot('09-editor-maquina');
 await page.getByRole('button',{name:'Hallazgos',exact:true}).click();
 await page.locator('.dash-pill.sev-pending').click();
 check('Tablero separa valoración pendiente de máquinas',await page.locator('.dash-row').count()===1&&await page.locator('.dash-row').innerText().then(t=>t.includes('Valoración pendiente')));
 await screenshot('10-valoracion-pendiente');
 const historical=option('--project',null);
 if(historical){await importProject(path.resolve(historical),'fondos-imported');check('Importación del informe previo',await page.evaluate(()=>S.data.findings.length===2));}
 // Fixture setup via the same local API; rendering and search through the UI.
 const creation=await api('POST','/api/projects',{slug:'stress-ui',title:'Carga de interfaz con 500 hallazgos'});
 check('Proyecto de carga creado',creation.status===200);
 const populated=await page.evaluate(async()=>{const uri='/api/projects/stress-ui',response=await appFetch(uri),data=await response.json();
   data.findings=Array.from({length:500},(_,i)=>({id:'F'+String(i+1).padStart(4,'0'),mode:'vuln',title:'Caso sintético '+(i+1),description_md:'Texto de prueba '+(i+1),walkthrough:[{command:'BUSQUEDA_CARGA_'+String(i+1).padStart(4,'0')}]}));
   return (await appFetch(uri,{method:'PUT',headers:{'Content-Type':'application/json','If-Match':response.headers.get('ETag')},body:JSON.stringify(data)})).status;
 });check('Carga de 500 entradas guardada por API',populated===200);
 await page.reload();await ready();const loadStarted=Date.now();await page.locator('#projectSelect').selectOption('stress-ui');
 await page.waitForFunction(()=>S.slug==='stress-ui'&&!projectStore.loading&&projectBusyCount===0);
 await page.getByRole('button',{name:'Hallazgos',exact:true}).click();await page.locator('.dash-row').last().waitFor();
 const firstPageCount=await page.locator('.dash-row').count(),sourceCount=await page.evaluate(()=>S.data.findings.length);
 const boardPages=page.locator('[data-workspace-pagination="board"] select');await boardPages.selectOption('9');
 const lastPageCount=await page.locator('.dash-row').count(),lastReachable=await page.locator('.dash-row').last().innerText().then(text=>text.includes('Caso sintético 500'));
 check('Tablero pagina 500 hallazgos y conserva accesible el último',firstPageCount===50&&sourceCount===500&&lastPageCount===50&&lastReachable,{milliseconds:Date.now()-loadStarted});
 const searchStarted=Date.now();await page.locator('#globalSearch').fill('BUSQUEDA_CARGA_0500');await page.locator('#searchResults .search-item').filter({hasText:'BUSQUEDA_CARGA_0500'}).waitFor();
 check('Búsqueda entre 500 hallazgos',await page.locator('#searchResults .search-item').count()===1,{milliseconds:Date.now()-searchStarted});
 await page.keyboard.press('ArrowDown');await page.keyboard.press('Enter');
 check('Búsqueda accesible por teclado abre el resultado',await page.locator('[data-field="title"]').inputValue()==='Caso sintético 500');
 check('Sin errores JavaScript',errors.length===0,errors);check('Sin solicitudes externas',external.length===0,external);save();
})().catch(async error=>{errors.push(String(error.stack||error));save();try{await page?.screenshot({path:path.join(out,'failure.png')});fs.writeFileSync(path.join(out,'failure-dom.html'),await page.content());}catch(_){}console.error(error);process.exitCode=1;}).finally(async()=>{await browser?.close();server?.kill('SIGTERM');});
