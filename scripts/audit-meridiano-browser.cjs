/* Real Meridiano UI acceptance for 0.38: diagnostic locations, native DOCX and
 * structural PDF privacy. Reports are generated only by report-gen. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process'),{createHash}=require('node:crypto'),{isDeepStrictEqual}=require('node:util');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),opt=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const out=path.resolve(opt('--output','out/meridiano-browser')),bundle=opt('--bundle'),projectDir=opt('--project-dir'),pdfInput=opt('--pdf');
const slug=opt('--slug','meridiano-browser'),python=process.env.RG_PYTHON||'python3',engine=opt('--browser','chromium');
const playwright=require('playwright'),hash=value=>createHash('sha256').update(value).digest('hex');
for(const [name,file] of [['--bundle',bundle],['--pdf',pdfInput]])assert.ok(file&&fs.statSync(file).isFile(),name+' is required');
assert.ok(projectDir&&fs.statSync(path.join(projectDir,'engagement.yaml')).isFile(),'--project-dir is required');
fs.mkdirSync(out,{recursive:true});
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-meridiano-'));
fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const sourcePaths=['scripts/audit-meridiano-browser.cjs','webapp/static/app.js','webapp/static/transport.js','webapp/static/progress.js','webapp/static/diagnostics-ui.js','webapp/static/docx-preview.js','webapp/static/annexes.js','diagnostic_locations.py','finding_imports.py','scanner_imports.py','export_contract.py','export_semantics.py','docx_preview.py','pdf_attachment_inspection.py','attachments.py','export_jobs.py','webapp/docx_preview_api.py'];
const sourceHashes=()=>Object.fromEntries(sourcePaths.map(name=>[name,hash(fs.readFileSync(path.join(root,name)))]));
const results={schema:'report-gen-meridiano-browser/1',started:new Date().toISOString(),engine,checks:[],screens:[],downloads:[],coverage:[],pageErrors:[],apiErrors:[],expectedApiErrors:[],externalRequests:[],sourceStart:sourceHashes(),input:{bundle_sha256:hash(fs.readFileSync(bundle)),pdf_sha256:hash(fs.readFileSync(pdfInput))},limits:['Only report-gen generates reports and the derived native PDF.','The fixture is fictional; no external systems are contacted.','LibreOffice preview is not Microsoft Word acceptance.','Browser assertions and screenshots are not a human visual approval.','PDF privacy is bounded structural inspection, without OCR or an assertion that no secrets exist.']};
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2)+'\n');
function check(name,passed,detail){results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name+': '+JSON.stringify(detail));console.log('PASS '+name);}
const clean=page=>page.waitForFunction(()=>typeof S!=='undefined'&&!projectStore.loading&&!projectBusyCount&&!projectStore.dirty&&!projectStore.saving&&!document.querySelector('#splash'),null,{timeout:60000});
const snapshot=page=>page.evaluate(()=>JSON.stringify({data:S.data,revision:projectStore.revision,etag:projectStore.etag,dirty:projectStore.dirty}));
const data=page=>page.evaluate(()=>JSON.parse(JSON.stringify(S.data)));
const labels={es:{close:'Cerrar',format:'Formato',review:'Revisar selección',download:'Descargar',native:'Vista DOCX con LibreOffice',annex:'Inventario de anexos',upload:'Cargar anexo',scan:'Analizar posibles secretos',record:'Registro',line:'Línea',through:'Hasta línea',column:'Columna',field:'Campo',limits:'Alcance y límites de privacidad'},en:{close:'Close',format:'Format',review:'Review selection',download:'Download',native:'DOCX preview with LibreOffice',annex:'Annex inventory',upload:'Upload annex',scan:'Check for possible secrets',record:'Record',line:'Line',through:'Through line',column:'Column',field:'Field',limits:'Privacy scope and limits'},pt:{close:'Fechar',format:'Formato',review:'Revisar seleção',download:'Baixar',native:'Visualização DOCX com LibreOffice',annex:'Inventário de anexos',upload:'Enviar anexo',scan:'Verificar possíveis segredos',record:'Registro',line:'Linha',through:'Até a linha',column:'Coluna',field:'Campo',limits:'Escopo e limites de privacidade'}};
async function expose(page,selector){const target=page.locator(selector).first(),ancestors=await target.evaluate(el=>{let d=el.parentElement?.closest('details'),list=[];while(d){if(!d.open)list.unshift(d.id||null);d=d.parentElement?.closest('details');}return list;});for(const id of ancestors){assert.ok(id,'Stable disclosure ID');await page.locator('#'+id+' > summary').click();}return target;}
async function click(page,selector){await (await expose(page,selector)).click();}
async function closeDrawer(page){if(await page.locator('#exportDrawer').count())await page.locator('#exportDrawer .experience-heading button').click();}
async function language(page,lang){await closeDrawer(page);await (await expose(page,'#langToggle')).selectOption(lang);if(await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();await clean(page);}
async function screen(page,name){await page.evaluate(()=>document.fonts.ready);const file=path.join(out,name+'.png');await page.screenshot({path:file,fullPage:false});results.screens.push({name,path:file,sha256:hash(fs.readFileSync(file)),viewport:page.viewportSize()});save();}
async function download(page,trigger,name,kind){const event=page.waitForEvent('download',{timeout:180000});await trigger();const item=await event,file=path.join(out,name);await item.saveAs(file);check(name+' downloads',await item.failure()===null&&fs.statSync(file).size>0);results.downloads.push({name,path:file,kind,size:fs.statSync(file).size,sha256:hash(fs.readFileSync(file))});save();return file;}
async function workflow(page,name){await click(page,'[data-workflow="'+name+'"]');await page.locator('[data-workflow-view="'+name+'"]').waitFor();await clean(page);}
const expectedFailures=[];
function expectFailure(method,pathname,status){const entry={method,pathname,status,consumed:false};expectedFailures.push(entry);return entry;}
function responseFor(page,method,pathname){return page.waitForResponse(response=>response.request().method()===method&&new URL(response.url()).pathname===pathname,{timeout:240000});}
let server,browser,page,timer;

async function diagnostics(lang){
 const before=await snapshot(page),text='title,severity,description_md\nFirst,low,Valid\n\nSecond,UNKNOWN,"Line one\nline two"\n',l=labels[lang];
 await click(page,'#intakeBtn');let dialog=page.locator('dialog.progress-dialog');await dialog.getByLabel(l.format,{exact:true}).selectOption('csv');
 await dialog.locator('input[type=file]').setInputFiles({name:'meridiano-diagnostic.csv',mimeType:'text/csv',buffer:Buffer.from(text)});
 await dialog.locator('[data-import-panel="2"]').waitFor({state:'visible'});
 const previewResponse=responseFor(page,'POST','/api/projects/'+slug+'/intake/preview');await dialog.getByRole('button',{name:l.review,exact:true}).click();
 const preview=await (await previewResponse).json();await dialog.locator('[data-import-panel="3"]').waitFor({state:'visible'});
 const expected={operation:'import',format:'csv',record:2,line:4,line_end:5,field:'severity',column:2};
 check(lang+' CSV preview returns exact multiline coordinates',isDeepStrictEqual(preview.rows[1].diagnostics[0].location,expected));
 const invalid=dialog.locator('.intake-rows > article').nth(1),location=await invalid.locator('[data-diagnostic-locations]').innerText();
 check(lang+' CSV coordinates are visible and localized',[l.record+': 2',l.line+': 4',l.through+': 5',l.column+': 2',l.field+': severity'].every(part=>location.includes(part)),location);
 check(lang+' invalid CSV row cannot be selected',await invalid.locator('[data-intake-row]').isDisabled());
 await invalid.scrollIntoViewIfNeeded();await screen(page,'diagnostics-csv-'+lang);await dialog.getByRole('button',{name:l.close,exact:true}).click();
 check(lang+' CSV review preserves exact project and revision',await snapshot(page)===before);
 await click(page,'#intakeBtn');dialog=page.locator('dialog.progress-dialog');await dialog.getByLabel(l.format,{exact:true}).selectOption('nuclei');
 const raw=JSON.stringify({'template-id':'meridiano-ui','matched-at':'https://example.test/',info:{name:'Synthetic observation',severity:{private:'MERIDIANO_UI_PRIVATE_CANARY'}}});
 const pathName='/api/projects/'+slug+'/intake/preview',failure=expectFailure('POST',pathName,422),rejected=responseFor(page,'POST',pathName);
 await dialog.locator('input[type=file]').setInputFiles({name:'meridiano-invalid.jsonl',mimeType:'application/x-ndjson',buffer:Buffer.from(raw)});
 const response=await rejected,body=await response.json();await dialog.locator('[data-diagnostic-locations]').waitFor();
 check(lang+' invalid Nuclei is explicitly rejected with precise field',response.status()===422&&failure.consumed&&body.diagnostics[0].location.field==='info.severity');
 const terminalLocation=await dialog.locator('[data-diagnostic-locations]').innerText();check(lang+' terminal location is visible in the import dialog',terminalLocation.includes(l.field+': info.severity')&&terminalLocation.includes(l.line+': 1'));
 check(lang+' private invalid field value is absent from error UI',!(await dialog.innerText()).includes('MERIDIANO_UI_PRIVATE_CANARY'));
 await screen(page,'diagnostics-invalid-'+lang);await dialog.getByRole('button',{name:l.close,exact:true}).click();
 check(lang+' failed import preserves exact project and revision',await snapshot(page)===before);
}

async function createDocxJob(){
 await language(page,'es');await (await expose(page,'#exportFormat')).selectOption('docx');
 const submitted=responseFor(page,'POST','/api/projects/'+slug+'/jobs');await page.locator('#downloadBtn').click();const response=await submitted,job=await response.json();
 check('DOCX export is queued by its visible control',response.status()===202);await page.waitForFunction(id=>['done','error'].includes(document.querySelector('[data-job="'+id+'"]')?.dataset.stage),job.id,{timeout:240000});
 const status=await page.evaluate(id=>api.get('/api/jobs/'+id),job.id);check('Complex Meridiano DOCX finishes native export checks',status.stage==='done',status);
 const row=page.locator('[data-job="'+job.id+'"]'),file=await download(page,()=>row.getByRole('button',{name:'Descargar',exact:true}).click(),'meridiano-ui.docx','report-gen DOCX');
 await closeDrawer(page);return {job:status,file,sha256:hash(fs.readFileSync(file))};
}

async function nativePreview(lang,exported){
 const before=await snapshot(page),l=labels[lang];await click(page,'#jobsBtn');const row=page.locator('[data-job="'+exported.job.id+'"]');await row.getByRole('button',{name:l.native,exact:true}).click();
 const dialog=page.locator('[data-docx-preview]');await dialog.waitFor();await page.waitForFunction(()=>!document.querySelector('[data-docx-preview-run]')?.disabled,{timeout:30000});
 const submitted=responseFor(page,'POST','/api/jobs/'+exported.job.id+'/docx-preview');await dialog.locator('[data-docx-preview-run]').click();const response=await submitted,preview=await response.json();
 check(lang+' native conversion is an accepted real request',response.status()===202);
 await dialog.locator('[data-docx-preview-output]').waitFor({state:'visible',timeout:240000});check(lang+' native preview names LibreOffice',await dialog.locator('[data-docx-preview-engine]').innerText().then(text=>text.includes('LibreOffice')));
 const pdf=await download(page,()=>dialog.locator('a[download="docx-libreoffice-preview.pdf"]').click(),'meridiano-native-'+lang+'.pdf','report-gen native DOCX derivative');
 const receiptFile=await download(page,()=>dialog.locator('a[download="docx-libreoffice-preview.json"]').click(),'meridiano-native-'+lang+'.json','report-gen native preview receipt'),receipt=JSON.parse(fs.readFileSync(receiptFile));
 check(lang+' native receipt binds the exact DOCX, revision and PDF',receipt.source_docx_sha256===exported.sha256&&receipt.source_revision===exported.job.revision&&receipt.pdf_sha256===hash(fs.readFileSync(pdf)),receipt);
 check(lang+' native renderer is stable LibreOffice rather than a development build',/^LibreOffice\s+\d/.test(receipt.engine.version),receipt.engine.version);
 check(lang+' native preview explicitly excludes Microsoft Word acceptance',receipt.word_verified===false&&receipt.pages>0&&(await dialog.innerText()).includes('Microsoft Word'));
 check(lang+' preview iframe contains the locally generated PDF',await dialog.locator('[data-docx-preview-frame]').getAttribute('src').then(value=>value.startsWith('blob:')));
 await screen(page,'native-docx-'+lang);const removed=responseFor(page,'DELETE','/api/docx-preview/'+preview.id);await dialog.getByRole('button',{name:l.close,exact:true}).click();check(lang+' closing removes the temporary preview',(await removed).status()===200);await dialog.waitFor({state:'detached'});
 check(lang+' native preview preserves exact project and revision',await snapshot(page)===before);
 results.coverage.push({area:'Native DOCX preview '+lang,mode:'UI',details:'Real export job and local LibreOffice conversion; downloaded source/derivative hashes, saved revision, Word limitation and explicit temporary cleanup.'});
}

async function openAnnex(lang){await click(page,'[data-studio-nav="deliver"]');await page.getByRole('button',{name:labels[lang].annex,exact:true}).click();await page.locator('dialog.annex-dialog').waitFor();}
async function uploadPDF(){
 await language(page,'es');await openAnnex('es');const uploaded=responseFor(page,'POST','/api/projects/'+slug+'/attachments/upload');
 await page.locator('dialog.annex-dialog').getByLabel(labels.es.upload,{exact:true}).setInputFiles({name:'meridiano-native-inspection.pdf',mimeType:'application/pdf',buffer:fs.readFileSync(pdfInput)});
 const response=await uploaded;check('PDF annex upload uses the existing report-gen PDF',response.status()===200);
 await clean(page);await page.locator('dialog.annex-dialog [data-annex]').filter({hasText:'meridiano-native-inspection.pdf'}).waitFor();
 const annex=(await data(page)).attachments.find(item=>item.name==='meridiano-native-inspection.pdf');check('Uploaded PDF starts excluded and unreviewed',!!annex&&!annex.include&&!annex.reviewed,annex);
 await page.locator('dialog.annex-dialog').getByRole('button',{name:labels.es.close,exact:true}).click();return annex;
}
async function privacyPDF(lang,annex){
 const before=await snapshot(page),l=labels[lang];await openAnnex(lang);const dialog=page.locator('dialog.annex-dialog'),item=dialog.locator('[data-annex="'+annex.uid+'"]');
 const scanned=page.waitForResponse(response=>response.request().method()==='GET'&&new URL(response.url()).pathname==='/api/projects/'+slug+'/attachments/scan'&&new URL(response.url()).searchParams.get('uid')===annex.uid,{timeout:120000});
 await item.getByRole('button',{name:l.scan,exact:true}).click();const response=await scanned,scan=await response.json();await item.locator('.annex-pdf-scope').waitFor();
 check(lang+' PDF privacy inspects exact original bytes',response.status()===200&&scan.sha256===results.input.pdf_sha256&&scan.bytes===fs.statSync(pdfInput).size);
 check(lang+' PDF privacy reports incomplete bounded structural scope',scan.scope==='pdf_structural'&&scan.complete===false&&scan.manual_review_required===true&&scan.pdf.pages_inspected>0&&['inspected','partial'].includes(scan.pdf.status),{status:scan.pdf.status,pages:scan.pdf.pages_inspected,limitations:scan.pdf.limitations});
 await item.getByText(l.limits,{exact:true}).click();const text=await item.locator('.annex-pdf-scope').innerText();check(lang+' PDF privacy exposes no OCR and resource limits',text.includes('OCR')&&text.includes(String(scan.pdf.limits.pages))&&text.includes(String(scan.pdf.limits.timeout_seconds)));
 const locations=scan.alerts.flatMap(alert=>alert.locations||[]);check(lang+' PDF alerts expose only structural locations',locations.every(value=>Object.keys(value).every(key=>['category','page','object','generation'].includes(key))));
 if(locations.length)check(lang+' PDF structural alert locations are rendered',await item.locator('.annex-scan-locations li').count()===locations.length);
 check(lang+' scanning does not approve inclusion or review',!(await item.locator('.annex-include').isChecked())&&await snapshot(page)===before);
 await item.locator('.annex-pdf-scope').scrollIntoViewIfNeeded();await screen(page,'pdf-privacy-'+lang);fs.writeFileSync(path.join(out,'pdf-privacy-'+lang+'.json'),JSON.stringify(scan,null,2)+'\n');
 await dialog.getByRole('button',{name:l.close,exact:true}).click();check(lang+' closing privacy scan preserves exact project',await snapshot(page)===before);
 results.coverage.push({area:'PDF annex privacy '+lang,mode:'UI',details:'Actual report-gen PDF uploaded by file input, scanned by visible action, structural locations and limits displayed without changing review/inclusion or source revision.'});
}

(async()=>{try{
 server=spawn(python,[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:process.env});server.stderr.on('data',part=>fs.appendFileSync(path.join(out,'server.log'),part));
 const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server startup timeout')),60000);server.stdout.on('data',part=>{text+=part;for(const line of text.split('\n'))try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});server.once('error',reject);server.once('exit',code=>reject(Error('Server exit '+code)));});
 const executable=opt('--executable',engine==='chromium'?(process.env.RG_CHROMIUM_EXECUTABLE||process.env.REPORT_GEN_CHROMIUM):undefined);
 browser=await playwright[engine].launch({headless:true,...(executable?{executablePath:executable}:{})});results.browser=browser.version();
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
 await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){results.externalRequests.push(url);return route.abort();}return route.continue();});
 await context.addInitScript(()=>{if(window!==window.top)return;localStorage.setItem('rg.uiLang','es');localStorage.setItem('rg.previewVisible','0');});
 page=await context.newPage();page.on('pageerror',error=>{results.pageErrors.push(String(error));save();});
 page.on('response',response=>{const url=new URL(response.url());if(response.status()>=400&&url.pathname.startsWith('/api/')){const row={method:response.request().method(),pathname:url.pathname,status:response.status()},expected=expectedFailures.find(value=>!value.consumed&&value.method===row.method&&value.pathname===row.pathname&&value.status===row.status);if(expected){expected.consumed=true;results.expectedApiErrors.push(row);}else results.apiErrors.push(row);save();}});
 const response=await page.goto(base);await clean(page);check('Local editor exposes CSP',!!response.headers()['content-security-policy']);
 page.once('dialog',dialog=>dialog.accept(slug));const chooser=page.waitForEvent('filechooser');await click(page,'#importProjectBtn');await (await chooser).setFiles(bundle);await page.waitForFunction(value=>S.slug===value&&!projectStore.loading&&!projectBusyCount,slug,{timeout:60000});await clean(page);if(await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();
 const baseline=await data(page),expected=JSON.parse(execFileSync(python,['-c','import json,yaml,sys;print(json.dumps(yaml.safe_load(open(sys.argv[1]))))',path.join(projectDir,'engagement.yaml')],{encoding:'utf8',maxBuffer:16*1024*1024}));
 check('Native import preserves exact complete Meridiano source',isDeepStrictEqual(baseline,expected));check('Complex case contains all expected records',baseline.findings.length===34&&baseline.assets.length===16&&baseline.evidence.length===32,{findings:baseline.findings.length,assets:baseline.assets.length,evidence:baseline.evidence.length});
 await screen(page,'01-meridiano-dashboard');
 for(const view of ['assets','coverage','evidence','root_causes','retest','retest_matrix','retest_diff','review','history','backup','remediation_tasks']){await workflow(page,view);check('Complete-case '+view+' view renders',await page.locator('[data-workflow-view="'+view+'"] [role="alert"]').count()===0);if(view==='evidence')await screen(page,'02-meridiano-evidence');}
 const unchanged=await snapshot(page);
 for(const lang of ['es','en','pt']){await language(page,lang);await click(page,'#guideBtn');await page.locator('[data-guide-page]').waitFor();for(let step=0;step<6;step++){await page.locator('[data-guide-step="'+step+'"]').click();const images=page.locator('.tutorial-screenshot img');await images.evaluateAll(nodes=>Promise.all(nodes.map(node=>node.decode())));check(lang+' tutorial step '+(step+1)+' uses localized images',await images.evaluateAll((nodes,value)=>nodes.length>0&&nodes.every(node=>node.naturalWidth>500&&node.src.endsWith('-'+value+'.webp')&&node.alt.length>50),lang));if(step===0)await screen(page,'tutorial-'+lang);}await click(page,'#navHome');await diagnostics(lang);}
 check('Tutorial and rejected imports preserve the complete source',await snapshot(page)===unchanged);
 const exported=await createDocxJob(),capabilities=await page.evaluate(()=>api.get('/api/docx-preview/capabilities'));
 check('Required native LibreOffice preview is available',capabilities.available,capabilities);
 for(const lang of ['es','en','pt']){await language(page,lang);await nativePreview(lang,exported);}
 check('Native preview source DOCX still downloads unchanged',await page.evaluate(async id=>{const response=await appFetch('/api/jobs/'+id+'/download'),bytes=await response.arrayBuffer();return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(value=>value.toString(16).padStart(2,'0')).join('');},exported.job.id)===exported.sha256);
 const annex=await uploadPDF();for(const lang of ['es','en','pt']){await language(page,lang);await privacyPDF(lang,annex);await click(page,'#navHome');await screen(page,'dashboard-'+lang);}
 results.sourceEnd=sourceHashes();check('Application source remains unchanged during browser acceptance',isDeepStrictEqual(results.sourceStart,results.sourceEnd));check('No JavaScript application errors',results.pageErrors.length===0,results.pageErrors);check('Only the three deliberately invalid import responses failed',results.expectedApiErrors.length===3&&expectedFailures.every(value=>value.consumed)&&results.apiErrors.length===0,{expected:results.expectedApiErrors,unexpected:results.apiErrors});check('No external network requests',results.externalRequests.length===0,results.externalRequests);
 results.passed=true;results.finished=new Date().toISOString();save();console.log('PASS '+results.checks.length+' Meridiano browser checks');
 }catch(error){results.passed=false;results.failure=String(error.stack||error);save();if(page&&!page.isClosed())await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});console.error(error);process.exitCode=1;}
 finally{clearTimeout(timer);await browser?.close();server?.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}
})();
