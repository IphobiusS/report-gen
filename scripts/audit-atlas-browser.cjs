/* Real Atlas UI acceptance for 0.39: diagnostic locations, native DOCX and
 * structural PDF privacy. Reports are generated only by report-gen. */
'use strict';
const {exposeNavigationControl,clickNavigationControl}=require('../tests/browser-navigation.cjs');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {spawn,execFileSync}=require('node:child_process'),{createHash}=require('node:crypto'),{isDeepStrictEqual}=require('node:util');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),opt=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const out=path.resolve(opt('--output','out/atlas-browser')),bundles=opt('--bundles'),projects=opt('--projects'),pdfInput=opt('--pdf'),comparePDF=opt('--compare-pdf'),compareOtherPDF=opt('--compare-other-pdf');
let slug='atlas-browser';
const python=process.env.RG_PYTHON||'python3',engine=opt('--browser','chromium');
const headed=args.includes('--headed');
const playwright=require('playwright'),hash=value=>createHash('sha256').update(value).digest('hex');
for(const [name,file] of [['--pdf',pdfInput],['--compare-pdf',comparePDF],['--compare-other-pdf',compareOtherPDF]])assert.ok(file&&fs.statSync(file).isFile(),name+' is required');
for(const lang of ['es','en','pt']){assert.ok(bundles&&fs.statSync(path.join(bundles,'atlas-'+lang+'.zip')).isFile(),'--bundles requires atlas-'+lang+'.zip');assert.ok(projects&&fs.statSync(path.join(projects,lang,'engagement.yaml')).isFile(),'--projects requires '+lang+'/engagement.yaml');}
fs.mkdirSync(out,{recursive:true});
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-atlas-'));
fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const sourcePaths=['tests/browser-navigation.cjs','webapp/static/context-index.js','webapp/static/context-index.css','webapp/static/onboarding.js','webapp/static/onboarding.css','scripts/audit-atlas-browser.cjs','webapp/static/index.html','webapp/static/workspace.js','webapp/static/workspace.css','webapp/static/workbench.js','webapp/static/workbench.css','webapp/static/studio.js','webapp/static/studio.css','webapp/static/app.js','webapp/static/transport.js','webapp/static/progress.js','webapp/static/diagnostics-ui.js','webapp/static/docx-preview.js','webapp/static/annexes.js','diagnostic_locations.py','finding_imports.py','scanner_imports.py','export_contract.py','export_semantics.py','docx_preview.py','pdf_attachment_inspection.py','attachments.py','export_jobs.py','webapp/docx_preview_api.py'];
const sourceHashes=()=>Object.fromEntries(sourcePaths.map(name=>[name,hash(fs.readFileSync(path.join(root,name)))]));
const results={schema:'report-gen-atlas-browser/1',started:new Date().toISOString(),engine,launch_mode:headed?'headed':'headless',checks:[],screens:[],downloads:[],coverage:[],pageErrors:[],consoleDiagnostics:[],nativeViewer:[],apiErrors:[],expectedApiErrors:[],externalRequests:[],sourceStart:sourceHashes(),input:{bundles:Object.fromEntries(['es','en','pt'].map(lang=>[lang,hash(fs.readFileSync(path.join(bundles,'atlas-'+lang+'.zip')))])),pdf_sha256:hash(fs.readFileSync(pdfInput)),compare_pdf_sha256:hash(fs.readFileSync(comparePDF)),compare_other_pdf_sha256:hash(fs.readFileSync(compareOtherPDF))},limits:['Only report-gen generates reports and the derived native PDF.','The fixture is fictional; no external systems are contacted.','LibreOffice preview is not Microsoft Word acceptance.','Browser assertions and screenshots are not a human visual approval.','PDF privacy is bounded structural inspection, without OCR or an assertion that no secrets exist.','Native PDF painting is checked only in explicitly headed runs; a blob URL alone does not establish painted pages.','PDF comparison uses complete report-gen sample PDFs; reports beyond the existing 80-page comparison limit are deliberate negative controls, not generation failures.']};
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2)+'\n');
function check(name,passed,detail){results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name+': '+JSON.stringify(detail));console.log('PASS '+name);}
const clean=page=>page.waitForFunction(()=>typeof S!=='undefined'&&!projectStore.loading&&!projectBusyCount&&!projectStore.dirty&&!projectStore.saving&&!document.querySelector('#splash'),null,{timeout:60000});
const snapshot=page=>page.evaluate(()=>JSON.stringify({data:S.data,revision:projectStore.revision,etag:projectStore.etag,dirty:projectStore.dirty}));
const data=page=>page.evaluate(()=>JSON.parse(JSON.stringify(S.data)));
const labels={es:{close:'Cerrar',format:'Formato',review:'Revisar selección',download:'Descargar',native:'Vista DOCX con LibreOffice',annex:'Inventario de anexos',upload:'Cargar anexo',scan:'Analizar posibles secretos',record:'Registro',line:'Línea',through:'Hasta línea',column:'Columna',field:'Campo',limits:'Alcance y límites de privacidad'},en:{close:'Close',format:'Format',review:'Review selection',download:'Download',native:'DOCX preview with LibreOffice',annex:'Annex inventory',upload:'Upload annex',scan:'Check for possible secrets',record:'Record',line:'Line',through:'Through line',column:'Column',field:'Field',limits:'Privacy scope and limits'},pt:{close:'Fechar',format:'Formato',review:'Revisar seleção',download:'Baixar',native:'Visualização DOCX com LibreOffice',annex:'Inventário de anexos',upload:'Enviar anexo',scan:'Verificar possíveis segredos',record:'Registro',line:'Linha',through:'Até a linha',column:'Coluna',field:'Campo',limits:'Escopo e limites de privacidade'}};
async function expose(page,selector){return exposeNavigationControl(page,selector);}
async function sidebarVisible(){if(page.viewportSize().width<=760&&await page.locator('#sidebarToggle').getAttribute('aria-expanded')!=='true')await page.locator('#sidebarToggle').click();}
async function click(page,selector){await clickNavigationControl(page,selector);}
async function closeDrawer(page){if(await page.locator('#exportDrawer').count())await page.locator('#exportDrawer .experience-heading button').click();}
async function language(page,lang){await closeDrawer(page);await (await expose(page,'#langToggle')).selectOption(lang);if(await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();await clean(page);}
async function screen(page,name){await boundedDiagnostic(page.evaluate(()=>document.fonts.ready),5000,'Screenshot fonts');const file=path.join(out,name+'.png');await page.screenshot({path:file,fullPage:false,timeout:10000});results.screens.push({name,path:file,sha256:hash(fs.readFileSync(file)),viewport:page.viewportSize()});save();}
async function download(page,trigger,name,kind){const event=page.waitForEvent('download',{timeout:180000});await trigger();const item=await event,file=path.join(out,name);await item.saveAs(file);check(name+' downloads',await item.failure()===null&&fs.statSync(file).size>0);results.downloads.push({name,path:file,kind,size:fs.statSync(file).size,sha256:hash(fs.readFileSync(file))});save();return file;}
async function boundedDiagnostic(promise,milliseconds,label){
 let timeout;
 try{return await Promise.race([promise,new Promise((_,reject)=>{timeout=setTimeout(()=>reject(Error(label+' diagnostic unavailable after '+milliseconds+' ms')),milliseconds);})]);}
 finally{clearTimeout(timeout);}
}
async function nativeViewerProbe(lang,dialog){
 const frame=dialog.locator('[data-docx-preview-frame]'),file=path.join(out,'native-docx-'+lang+'-frame.png');
 const record={language:lang,mode:headed?'headed':'headless',frames:[],paint_scope:headed?'visible_atlas_cover_pixels':'not_checked_headless',diagnostic_timeout_ms:2000,frame_limit:8};
 results.nativeViewer.push(record);save();
 try{record.navigator=await boundedDiagnostic(page.evaluate(()=>({pdfViewerEnabled:navigator.pdfViewerEnabled,plugins:[...navigator.plugins].map(p=>p.name)})),2000,'PDF navigator');}
 catch(error){record.navigator={status:'unavailable_diagnostic',error:String(error)};}save();
 const browserFrames=page.frames();record.frames_total=browserFrames.length;save();
 for(const browserFrame of browserFrames.slice(0,record.frame_limit)){
  try{record.frames.push(await boundedDiagnostic(browserFrame.evaluate(()=>({url:location.href,contentType:document.contentType,readyState:document.readyState,pdfViewer:!!document.querySelector('pdf-viewer'),embeds:[...document.querySelectorAll('embed,object')].map(node=>({tag:node.tagName,type:node.getAttribute('type'),src:node.getAttribute('src'),data:node.getAttribute('data')})),csp:window.__reportGenCsp||[]})),2000,'PDF frame'));}
  catch(error){record.frames.push({url:browserFrame.url(),status:'unavailable_diagnostic',inspection_error:String(error)});}save();
 }
 // Collect bounded frame/CSP diagnostics before touching the PDF compositor.
 await screen(page,'native-docx-metadata-'+lang);
 if(headed){
  // The exact generated cover has a large navy block. A blank iframe, grey
  // viewer toolbar, CSP error page or PDF plug-in placeholder cannot satisfy
  // this positive content test. No report is regenerated or edited here.
  const inspect='import json,sys;from PIL import Image;im=Image.open(sys.argv[1]).convert("RGB");pixels=list(im.getdata());navy=sum(10<=r<50 and 15<=g<70 and 35<=b<110 and b>=g+12 and g>=r+4 for r,g,b in pixels);print(json.dumps({"width":im.width,"height":im.height,"navy_pixels":navy,"pixels":len(pixels),"navy_fraction":navy/len(pixels)}))';
  const deadline=Date.now()+20000,remaining=()=>Math.max(1,Math.min(5000,deadline-Date.now()));
  try{
   await frame.scrollIntoViewIfNeeded({timeout:remaining()});
   while(Date.now()<deadline){
    await frame.screenshot({path:file,timeout:remaining()});
    if(Date.now()>=deadline)throw Error('PDF paint deadline exceeded before pixel inspection');
    record.pixels=JSON.parse(execFileSync(python,['-c',inspect,file],{encoding:'utf8',timeout:remaining()}));
    record.screenshot={file:path.basename(file),sha256:hash(fs.readFileSync(file))};save();
    if(record.pixels.navy_fraction>.05)break;
    await new Promise(resolve=>setTimeout(resolve,Math.min(250,Math.max(0,deadline-Date.now()))));
   }
  }catch(error){record.paint_error=String(error);}save();
 }
 if(headed)check(lang+' native PDF viewer paints the generated Atlas cover',!record.paint_error&&record.pixels?.navy_fraction>.05,record);
}
async function workflow(page,name){await click(page,'[data-workflow="'+name+'"]');await page.locator('[data-workflow-view="'+name+'"]').waitFor();await clean(page);}
async function tutorialImages(lang,step){
 const images=page.locator('.tutorial-screenshot img'),count=await images.count();
 for(let index=0;index<count;index++){
  const image=images.nth(index);
  results.tutorialImageProgress={language:lang,step:step+1,image:index+1,count,stage:'scroll'};save();
  // Reach every lazy image as a user would; do not rewrite loading or src.
  await image.scrollIntoViewIfNeeded({timeout:10000});
  results.tutorialImageProgress.stage='load';save();
  await page.waitForFunction(index=>{const node=document.querySelectorAll('.tutorial-screenshot img')[index];return !!node?.complete&&node.naturalWidth>0;},index,{timeout:10000});
  results.tutorialImageProgress.stage='decode';save();
  await boundedDiagnostic(image.evaluate(node=>node.decode()),10000,lang+' tutorial step '+(step+1)+' image '+(index+1));
 }
 check(lang+' tutorial step '+(step+1)+' uses localized images',await boundedDiagnostic(images.evaluateAll((nodes,value)=>nodes.length>0&&nodes.every(node=>node.complete&&node.naturalWidth>500&&node.src.endsWith('-'+value+'.webp')&&node.alt.length>50),lang),10000,'Tutorial image attributes'));
 results.tutorialImageProgress={language:lang,step:step+1,count,stage:'complete'};save();
}
const expectedFailures=[];
function expectFailure(method,pathname,status){const entry={method,pathname,status,consumed:false};expectedFailures.push(entry);return entry;}
function responseFor(page,method,pathname){return page.waitForResponse(response=>response.request().method()===method&&new URL(response.url()).pathname===pathname,{timeout:240000});}
let server,browser,page,timer,forcedExit;
const processBudgetMs=30*60*1000;
results.process_budget_ms=processBudgetMs;
const processDeadline=setTimeout(()=>{
 results.passed=false;results.failure='Atlas browser process exceeded '+processBudgetMs+' ms';results.finished=new Date().toISOString();save();console.error(results.failure);
 process.exitCode=1;server?.kill('SIGTERM');browser?.close().catch(()=>{});
 forcedExit=setTimeout(()=>process.exit(1),5000);
},processBudgetMs);

async function diagnostics(lang){
 const before=await snapshot(page),text='title,severity,description_md\nFirst,low,Valid\n\nSecond,UNKNOWN,"Line one\nline two"\n',l=labels[lang];
 await click(page,'#intakeBtn');let dialog=page.locator('dialog.progress-dialog');await dialog.getByLabel(l.format,{exact:true}).selectOption('csv');
 await dialog.locator('input[type=file]').setInputFiles({name:'atlas-diagnostic.csv',mimeType:'text/csv',buffer:Buffer.from(text)});
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
 const raw=JSON.stringify({'template-id':'atlas-ui','matched-at':'https://example.test/',info:{name:'Synthetic observation',severity:{private:'ATLAS_UI_PRIVATE_CANARY'}}});
 const pathName='/api/projects/'+slug+'/intake/preview',failure=expectFailure('POST',pathName,422),rejected=responseFor(page,'POST',pathName);
 await dialog.locator('input[type=file]').setInputFiles({name:'atlas-invalid.jsonl',mimeType:'application/x-ndjson',buffer:Buffer.from(raw)});
 const response=await rejected,body=await response.json();await dialog.locator('[data-diagnostic-locations]').waitFor();
 check(lang+' invalid Nuclei is explicitly rejected with precise field',response.status()===422&&failure.consumed&&body.diagnostics[0].location.field==='info.severity');
 const terminalLocation=await dialog.locator('[data-diagnostic-locations]').innerText();check(lang+' terminal location is visible in the import dialog',terminalLocation.includes(l.field+': info.severity')&&terminalLocation.includes(l.line+': 1'));
 check(lang+' private invalid field value is absent from error UI',!(await dialog.innerText()).includes('ATLAS_UI_PRIVATE_CANARY'));
 await screen(page,'diagnostics-invalid-'+lang);await dialog.getByRole('button',{name:l.close,exact:true}).click();
 check(lang+' failed import preserves exact project and revision',await snapshot(page)===before);
}

async function createDocxJob(lang){
 await language(page,lang);await (await expose(page,'#exportFormat')).selectOption('docx');
 const submitted=responseFor(page,'POST','/api/projects/'+slug+'/jobs');await page.locator('#downloadBtn').click();const response=await submitted,job=await response.json();
 check('DOCX export is queued by its visible control',response.status()===202);await page.waitForFunction(id=>['done','error'].includes(document.querySelector('[data-job="'+id+'"]')?.dataset.stage),job.id,{timeout:240000});
 const status=await page.evaluate(id=>api.get('/api/jobs/'+id),job.id);check('Complex Atlas DOCX finishes native export checks',status.stage==='done',status);
 const row=page.locator('[data-job="'+job.id+'"]'),file=await download(page,()=>row.getByRole('button',{name:labels[lang].download,exact:true}).click(),'atlas-ui-'+lang+'.docx','report-gen DOCX');
 await closeDrawer(page);return {job:status,file,sha256:hash(fs.readFileSync(file))};
}

async function nativePreview(lang,exported){
 const before=await snapshot(page),l=labels[lang];await click(page,'#jobsBtn');const row=page.locator('[data-job="'+exported.job.id+'"]');await row.getByRole('button',{name:l.native,exact:true}).click();
 const dialog=page.locator('[data-docx-preview]');await dialog.waitFor();await page.waitForFunction(()=>!document.querySelector('[data-docx-preview-run]')?.disabled,null,{timeout:30000});
 const submitted=responseFor(page,'POST','/api/jobs/'+exported.job.id+'/docx-preview');await dialog.locator('[data-docx-preview-run]').click();const response=await submitted,preview=await response.json();
 check(lang+' native conversion is an accepted real request',response.status()===202);
 await dialog.locator('[data-docx-preview-output]').waitFor({state:'visible',timeout:240000});check(lang+' native preview names LibreOffice',await dialog.locator('[data-docx-preview-engine]').innerText().then(text=>text.includes('LibreOffice')));
 const pdf=await download(page,()=>dialog.locator('a[download="docx-libreoffice-preview.pdf"]').click(),'atlas-native-'+lang+'.pdf','report-gen native DOCX derivative');
 const receiptFile=await download(page,()=>dialog.locator('a[download="docx-libreoffice-preview.json"]').click(),'atlas-native-'+lang+'.json','report-gen native preview receipt'),receipt=JSON.parse(fs.readFileSync(receiptFile));
 check(lang+' native receipt binds the exact DOCX, revision and PDF',receipt.source_docx_sha256===exported.sha256&&receipt.source_revision===exported.job.revision&&receipt.pdf_sha256===hash(fs.readFileSync(pdf)),receipt);
 check(lang+' native renderer is stable LibreOffice rather than a development build',/^LibreOffice\s+\d/.test(receipt.engine.version),receipt.engine.version);
 check(lang+' native preview explicitly excludes Microsoft Word acceptance',receipt.word_verified===false&&receipt.pages>0&&(await dialog.innerText()).includes('Microsoft Word'));
 check(lang+' preview iframe references the locally generated PDF',await dialog.locator('[data-docx-preview-frame]').getAttribute('src').then(value=>value.startsWith('blob:')));
 await nativeViewerProbe(lang,dialog);
 await screen(page,'native-docx-'+lang);const removed=responseFor(page,'DELETE','/api/docx-preview/'+preview.id);await dialog.getByRole('button',{name:l.close,exact:true}).click();check(lang+' closing removes the temporary preview',(await removed).status()===200);await dialog.waitFor({state:'detached'});
 check(lang+' native preview preserves exact project and revision',await snapshot(page)===before);
 results.coverage.push({area:'Native DOCX preview '+lang,mode:'UI',details:'Real export job and local LibreOffice conversion; downloaded source/derivative hashes, saved revision, Word limitation and explicit temporary cleanup.'});
}

async function openAnnex(lang){await click(page,'[data-studio-nav="deliver"]');await page.getByRole('button',{name:labels[lang].annex,exact:true}).click();await page.locator('dialog.annex-dialog').waitFor();}
async function uploadPDF(lang){
 await language(page,lang);await openAnnex(lang);const uploaded=responseFor(page,'POST','/api/projects/'+slug+'/attachments/upload');
 await page.locator('dialog.annex-dialog').getByLabel(labels[lang].upload,{exact:true}).setInputFiles({name:'atlas-native-inspection.pdf',mimeType:'application/pdf',buffer:fs.readFileSync(pdfInput)});
 const response=await uploaded;check('PDF annex upload uses the existing report-gen PDF',response.status()===200);
 await clean(page);await page.locator('dialog.annex-dialog [data-annex]').filter({hasText:'atlas-native-inspection.pdf'}).waitFor();
 const annex=(await data(page)).attachments.find(item=>item.name==='atlas-native-inspection.pdf');check('Uploaded PDF starts excluded and unreviewed',!!annex&&!annex.include&&!annex.reviewed,annex);
 await page.locator('dialog.annex-dialog').getByRole('button',{name:labels[lang].close,exact:true}).click();return annex;
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

async function importLanguage(lang){
 slug='atlas-browser-'+lang;await page.setViewportSize({width:1440,height:1000});
 page.once('dialog',dialog=>dialog.accept(slug));const chooser=page.waitForEvent('filechooser');await click(page,'#importProjectBtn');await (await chooser).setFiles(path.join(bundles,'atlas-'+lang+'.zip'));
 await page.waitForFunction(value=>S.slug===value&&!projectStore.loading&&!projectBusyCount,slug,{timeout:60000});await clean(page);
 if(await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();
 const baseline=await data(page),expected=JSON.parse(execFileSync(python,['-c','import json,yaml,sys;print(json.dumps(yaml.safe_load(open(sys.argv[1]))))',path.join(projects,lang,'engagement.yaml')],{encoding:'utf8',maxBuffer:32*1024*1024}));
 check(lang+' native import preserves exact complete localized Atlas source',isDeepStrictEqual(baseline,expected));
 check(lang+' case starts with sixty or more vulnerabilities plus machine notebooks',baseline.findings.filter(row=>row.mode!=='machine').length>=60&&baseline.findings.some(row=>row.mode==='machine')&&baseline.meta.lang===lang,{findings:baseline.findings.length,assets:baseline.assets.length,evidence:baseline.evidence.length,sections:baseline.report.sections.length,report_language:baseline.meta.lang});
 await click(page,'#navHome');await screen(page,'01-atlas-overview-'+lang);
}
async function setTheme(theme){
 const current=await page.locator('html').getAttribute('data-theme');if(current!==theme)await click(page,'#themeToggle');
 if(await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();
 check(theme+' theme is selected through the visible control',await page.locator('html').getAttribute('data-theme')===theme);
}
async function disclosure(id,open){
 await sidebarVisible();const node=page.locator('#'+id);
 // A summary is already the visible disclosure control. Passing it through
 // expose() would open its own details and then immediately toggle it closed.
 if(await node.evaluate(el=>el.open)!==open)await page.locator('#'+id+' > summary').click();
 assert.equal(await node.evaluate(el=>el.open),open,id+' reaches the requested disclosure state');
}
async function sidebarGeometry(lang,width,theme,state){
 const geometry=await page.evaluate(()=>{
  const sidebar=document.querySelector('#workspaceSidebar'),bounds=sidebar.getBoundingClientRect(),visible=el=>el.getClientRects().length&&getComputedStyle(el).visibility!=='hidden';
  const controls=[...sidebar.querySelectorAll('button,summary,select')].filter(visible).map(el=>{const box=el.getBoundingClientRect();return {id:el.id||el.dataset.workflow||el.tagName,name:el.getAttribute('aria-label')||el.textContent.trim(),left:box.left,right:box.right,height:box.height,width:box.width,clippedX:box.left<bounds.left-1||box.right>bounds.right+1};});
  const groups=[...sidebar.querySelectorAll(':scope > [data-sidebar-group]')].map(el=>({name:el.dataset.sidebarGroup,height:el.getBoundingClientRect().height,padding:getComputedStyle(el).paddingBlock}));
  return {viewport:innerWidth,root:document.documentElement.scrollWidth,sidebarWidth:bounds.width,sidebarClient:sidebar.clientWidth,sidebarScroll:sidebar.scrollWidth,controls,groups};
 });
 check(lang+' '+width+' '+theme+' '+state+' sidebar stays inside viewport without horizontal overflow',geometry.root<=width+1&&geometry.sidebarScroll<=geometry.sidebarClient+1,geometry);
 check(lang+' '+width+' '+theme+' '+state+' visible sidebar controls have labels and are not clipped',geometry.controls.every(control=>control.name&&control.width>0&&!control.clippedX),geometry.controls);
 check(lang+' '+width+' '+theme+' '+state+' sidebar touch and keyboard controls retain minimum height',geometry.controls.every(control=>control.height>=(width<=760?44:39)),geometry.controls);
 const contrast=await page.evaluate(()=>{
  const rgb=value=>(value.match(/[\d.]+/g)||[]).map(Number),luminance=values=>values.slice(0,3).map(x=>x/255).map(x=>x<=.04045?x/12.92:((x+.055)/1.055)**2.4).reduce((sum,x,i)=>sum+x*[.2126,.7152,.0722][i],0);
  return [...document.querySelectorAll('#workspaceSidebar .navitem,#workspaceSidebar summary')].filter(el=>el.getClientRects().length).map(el=>{let bg;for(let parent=el;parent;parent=parent.parentElement){const color=rgb(getComputedStyle(parent).backgroundColor);if(color.length===3||color[3]===1){bg=color;break;}}if(!bg)bg=[255,255,255];const fg=luminance(rgb(getComputedStyle(el).color)),back=luminance(bg);return{name:el.textContent.trim(),ratio:(Math.max(fg,back)+.05)/(Math.min(fg,back)+.05)};});
 });
 check(lang+' '+width+' '+theme+' '+state+' navigation text meets 4.5 to 1 contrast',contrast.every(row=>row.ratio>=4.5),contrast);
 results.sidebarGeometry??=[];results.sidebarGeometry.push({language:lang,width,theme,state,...geometry,contrast});save();
}
// Observation only: never scroll, focus or click the row before this check.
// The sole list scrollport, panel and viewport must all contain the selected row.
async function selectedIndexGeometry(lang,scenario){
 await boundedDiagnostic(page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))),5000,'Selected index layout');
 const geometry=await page.evaluate(()=>{
  const selected=document.querySelector('#contextIndex ul:not([hidden]) [aria-current="page"]'),index=selected?.closest('.context-index-list-scroll'),panel=document.querySelector('#contextIndex');
  const box=el=>{if(!el)return null;const r=el.getBoundingClientRect();return {top:r.top,bottom:r.bottom,left:r.left,right:r.right,width:r.width,height:r.height,scrollTop:el.scrollTop,clientHeight:el.clientHeight};};
  const row=box(selected),ports=[{kind:'index',...box(index)},{kind:'panel',...box(panel)}],viewport={top:0,bottom:innerHeight,left:0,right:innerWidth};
  const inside=parent=>!!row&&row.width>0&&row.height>0&&parent.height>0&&row.top>=parent.top-1&&row.bottom<=parent.bottom+1&&row.left>=parent.left-1&&row.right<=parent.right+1;
  return {row,ports,viewport,inside_index:inside(ports[0]),inside_panel:inside(ports[1]),single_list_scrollport:document.querySelectorAll('#contextIndex .context-index-list-scroll').length===1,inside_viewport:!!row&&row.top>=-1&&row.bottom<=innerHeight+1&&row.left>=-1&&row.right<=innerWidth+1,focus:document.activeElement?.id||document.activeElement?.tagName,editor_scroll_top:document.querySelector('#editor').scrollTop};
 });
 check(lang+' '+scenario+' selected row is revealed in the sole list scrollport, panel and viewport without assisted scrolling',geometry.inside_index&&geometry.inside_panel&&geometry.inside_viewport&&geometry.single_list_scrollport,geometry);
 results.selectedIndexGeometry??=[];results.selectedIndexGeometry.push({language:lang,scenario,...geometry});save();
}
async function sidebarAcceptance(lang){
 const original=await snapshot(page),baseline=await data(page),total=baseline.findings.length;
 await click(page,'#navHome');const groups=await page.locator('#workspaceSidebar > [data-sidebar-group]').evaluateAll(nodes=>nodes.map(node=>node.dataset.sidebarGroup));
 check(lang+' sidebar exposes five ordered task groups',isDeepStrictEqual(groups,['project','content','evidence','analysis','delivery']),groups);
 const expectedLabels={es:['Proyecto','Contenido','Evidencia y alcance','Análisis y seguimiento','Entrega'],en:['Project','Content','Evidence and scope','Analysis and follow-up','Delivery'],pt:['Projeto','Conteúdo','Evidências e escopo','Análise e acompanhamento','Entrega']}[lang],actualLabels=await page.locator('#navProject,#navWork,#navEvidence,#navReview,#navDelivery').allTextContents();
 check(lang+' sidebar group names are fully localized',isDeepStrictEqual(actualLabels,expectedLabels),actualLabels);
 check(lang+' sidebar counts match the complete report',Number(await page.locator('#workspaceSections [data-sidebar-count]').innerText())===baseline.report.sections.length&&Number(await page.locator('#workspaceFindings [data-sidebar-count]').innerText())===total);
 check(lang+' content launchers are buttons and both collections live outside global navigation',await page.evaluate(()=>['workspaceSections','workspaceFindings'].every(id=>document.getElementById(id).tagName==='BUTTON'&&document.getElementById(id).getAttribute('aria-controls')==='contextIndex')&&['sectionList','findingList'].every(id=>document.getElementById(id).closest('#contextIndex')&&!document.getElementById(id).closest('#workspaceSidebar'))));
 for(const id of ['workspaceResearch','workspaceFollowup','workspaceTools'])await disclosure(id,false);
 for(const theme of ['dark','light']){
  await setTheme(theme);
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1000});await sidebarVisible();await page.locator('#navHome').scrollIntoViewIfNeeded();
   await sidebarGeometry(lang,width,theme,'collapsed');await screen(page,'sidebar-'+lang+'-'+width+'-'+theme);
   for(const id of ['workspaceResearch','workspaceFollowup','workspaceTools'])await disclosure(id,true);
   await sidebarGeometry(lang,width,theme,'expanded');await screen(page,'sidebar-expanded-'+lang+'-'+width+'-'+theme);
   for(const id of ['workspaceResearch','workspaceFollowup','workspaceTools'])await disclosure(id,false);
  }
 }
 await page.setViewportSize({width:1440,height:1000});await setTheme('dark');
 // Native details keyboard behavior: opening/closing must retain focus.
 for(const id of ['workspaceResearch','workspaceFollowup','workspaceTools']){
  await disclosure(id,false);const summary=page.locator('#'+id+' > summary');await summary.focus();await page.keyboard.press('Enter');
  check(lang+' '+id+' opens with Enter and keeps keyboard focus',await page.locator('#'+id).evaluate(el=>el.open&&document.activeElement===el.querySelector('summary')));
  await page.keyboard.press('Space');check(lang+' '+id+' closes with Space and keeps keyboard focus',await page.locator('#'+id).evaluate(el=>!el.open&&document.activeElement===el.querySelector('summary')));
 }
 await click(page,'#sectionList .finding-nav');await clean(page);
 check(lang+' selected section is current and its index stays open',await page.locator('#contextIndex').isVisible()&&await page.locator('#contextSectionsTab').getAttribute('aria-pressed')==='true'&&await page.locator('#sectionList [aria-current="page"]').count()===1);
 await selectedIndexGeometry(lang,'section selection');await screen(page,'section-selected-'+lang);
 await click(page,'#navFindings');await clean(page);
 check(lang+' full findings board uses bounded first page',await page.locator('.dash-row').count()===50,{total});
 await page.locator('[data-workspace-pagination="board"] select').selectOption('1');
 check(lang+' second board page exposes remaining original records',await page.locator('.dash-row').count()===Math.min(50,total-50));
 await screen(page,'findings-page-2-'+lang);await page.locator('.dash-toolbar .dash-tab').nth(1).click();
 const owner=baseline.findings.find(row=>row.owner)?.owner;assert.ok(owner,'Fixture includes a finding owner');
 await page.locator('.finding-filters > label').nth(2).locator('select').selectOption(owner);
 const expected=baseline.findings.filter(row=>row.owner===owner).slice(0,50).map(row=>row.uid),actual=await page.locator('.dash-row').evaluateAll(nodes=>nodes.map(node=>node.dataset.findingUid));
 check(lang+' owner filter resets pagination and returns exact matching records',isDeepStrictEqual(actual,expected),{owner,expected,actual});
 await page.locator('.finding-filters').getByRole('button',{name:{es:'Limpiar filtros',en:'Clear filters',pt:'Limpar filtros'}[lang],exact:true}).click();
 check(lang+' clearing filters restores the bounded first page',await page.locator('.dash-row').count()===50);
 const lastPage=Math.floor((total-1)/50);await click(page,'#workspaceFindings');await page.locator('[data-workspace-pagination="context"] select').selectOption(String(lastPage));
 check(lang+' context index final page exposes actual records beyond fifty',await page.locator('#findingList > li').count()===total-lastPage*50);
 const target=baseline.findings[total-1];await click(page,'#findingList [data-finding-uid="'+target.uid+'"] .finding-nav');await clean(page);
 check(lang+' exact last finding is selected and current in its open index',await page.evaluate(uid=>S.sel.type==='finding'&&S.data.findings[S.sel.idx].uid===uid&&!document.querySelector('#contextIndex').hidden&&document.querySelector('#contextFindingsTab').getAttribute('aria-pressed')==='true'&&document.querySelector('#findingList [aria-current="page"]')?.closest('li').dataset.findingUid===uid,target.uid));
 check(lang+' selected finding preserves its full accessible title',await page.locator('#findingList [aria-current="page"]').innerText().then(value=>value.includes(target.title)));
 await selectedIndexGeometry(lang,'last finding selection');await screen(page,'finding-selected-'+lang);
 await page.locator('#contextIndexClose').click();await click(page,'#navHome');
 await (await expose(page,'#globalSearch')).fill(target.id);await page.keyboard.press('Enter');await clean(page);
 check(lang+' keyboard search selects the exact record beyond the first index page while preserving a closed index',await page.evaluate(uid=>S.sel.type==='finding'&&S.data.findings[S.sel.idx].uid===uid&&document.querySelector('#contextIndex').hidden,target.uid));
 await click(page,'#workspaceFindings');
 await selectedIndexGeometry(lang,'keyboard search beyond fifty');
 await page.setViewportSize({width:390,height:1000});
 // Reopen the contextual index from its toolbar, then observe unassisted geometry.
 if(await page.locator('#sidebarToggle').getAttribute('aria-expanded')==='true')await page.locator('#sidebarToggle').click();
 await page.locator('#contextIndexClose').click();await page.locator('#contextIndexToggle').click();
 await selectedIndexGeometry(lang,'mobile reopening');await screen(page,'finding-selected-'+lang+'-390');
 await page.keyboard.press('Escape');check(lang+' mobile Escape closes the context index and returns focus to its toggle',await page.locator('#contextIndex').isHidden()&&await page.locator('#contextIndexToggle').evaluate(el=>el===document.activeElement));
 await page.locator('#contextIndexToggle').click();await page.locator('#findingList [aria-current="page"]').click();
 check(lang+' mobile contextual selection closes its panel and focuses the editor',await page.locator('#contextIndex').isHidden()&&await page.locator('#editor').evaluate(el=>el===document.activeElement));
 await sidebarVisible();await page.locator('#navHome').focus();await page.keyboard.press('Escape');
 check(lang+' mobile Escape closes global navigation and returns focus to its toggle',await page.locator('#sidebarToggle').getAttribute('aria-expanded')==='false'&&await page.locator('#sidebarToggle').evaluate(el=>el===document.activeElement));
 await click(page,'#navHome');check(lang+' mobile route selection closes navigation and focuses the editor',await page.locator('#sidebarToggle').getAttribute('aria-expanded')==='false'&&await page.locator('#editor').evaluate(el=>el===document.activeElement));
 await page.setViewportSize({width:1440,height:1000});
 for(const [route,disclosureId] of [['assets','workspaceResearch'],['root_causes','workspaceFollowup']]){
  await disclosure(disclosureId,false);await workflow(page,route);check(lang+' '+route+' navigation identifies and reveals its selected group',await page.locator('#'+disclosureId).evaluate(el=>el.open)&&await page.locator('[data-workflow="'+route+'"]').getAttribute('aria-current')==='page');await screen(page,'sidebar-'+route+'-'+lang);
 }
 check(lang+' sidebar navigation, themes, filters and keyboard never edit authored data or revision',await snapshot(page)===original);
 results.coverage.push({area:'Sidebar '+lang,mode:'real headed UI',details:'Five grouped regions, data counts, three real disclosures with Enter/Space, contextual section/finding launchers, bounded index beyond fifty, filters, keyboard search respecting a closed index, dark/light 1440px/390px collapsed/expanded screenshots, labeled controls, mobile route/context focus return and unassisted selected-row geometry in its sole list scrollport, panel and viewport.'});
}
async function compareSamples(lang){
 const original=await snapshot(page);await workflow(page,'history');await page.getByRole('button',{name:{es:'Comparar archivos PDF',en:'Compare PDF files',pt:'Comparar arquivos PDF'}[lang],exact:true}).click();
 const dialog=page.locator('[data-pdf-compare]');await dialog.locator('[data-pdf-before]').setInputFiles(comparePDF);await dialog.locator('[data-pdf-after]').setInputFiles(compareOtherPDF);await dialog.locator('[data-pdf-compare-submit]').click();
 const frame=dialog.frameLocator('[data-pdf-compare-frame]');await frame.locator('#comparison-summary').waitFor({timeout:90000});const manifest=JSON.parse(await frame.locator('#comparison-manifest').textContent());
 check(lang+' PDF comparison uses exact report-gen sample bytes within its declared limit',manifest.before_sha256===results.input.compare_pdf_sha256&&manifest.after_sha256===results.input.compare_other_pdf_sha256&&manifest.before_pages<=80&&manifest.after_pages<=80&&manifest.pairing_mode==='positional',manifest);
 await download(page,()=>dialog.locator('[data-pdf-compare-download]').click(),'atlas-comparison-'+lang+'.html','report-gen PDF comparison of localized samples');await screen(page,'pdf-comparison-'+lang);
 await dialog.getByRole('button',{name:labels[lang].close,exact:true}).click();check(lang+' comparing samples preserves exact project',await snapshot(page)===original);
 const fullPages=Number(execFileSync(python,['-c','import fitz,sys;print(len(fitz.open(sys.argv[1])))',pdfInput],{encoding:'utf8'}));
 if(fullPages>80){
  await page.getByRole('button',{name:{es:'Comparar archivos PDF',en:'Compare PDF files',pt:'Comparar arquivos PDF'}[lang],exact:true}).click();const negative=page.locator('[data-pdf-compare]');
  await negative.locator('[data-pdf-before]').setInputFiles(pdfInput);await negative.locator('[data-pdf-after]').setInputFiles(comparePDF);
  const failure=expectFailure('POST','/api/pdf-compare',422),rejected=responseFor(page,'POST','/api/pdf-compare');await negative.locator('[data-pdf-compare-submit]').click();const response=await rejected;
  const message={es:'Cada PDF debe tener entre 1 y 80 páginas.',en:'Each PDF must contain between 1 and 80 pages.',pt:'Cada PDF deve conter entre 1 e 80 páginas.'}[lang];await page.waitForFunction(message=>document.querySelector('[data-pdf-compare-error]')?.textContent===message,message,{timeout:60000});
  check(lang+' complete report beyond comparison limit is rejected explicitly and locally',response.status()===422&&failure.consumed&&await negative.locator('[data-pdf-compare-error]').innerText()===message,{full_pages:fullPages,comparison_max_pages:80,expected_negative:true});
  check(lang+' comparison limit rejection leaves retry usable and produces no output',await negative.locator('[data-pdf-compare-submit]').isEnabled()&&!await negative.locator('[data-pdf-compare-output]').isVisible());await screen(page,'pdf-comparison-limit-'+lang);
  await negative.getByRole('button',{name:labels[lang].close,exact:true}).click();check(lang+' rejected oversized comparison preserves exact project',await snapshot(page)===original);
 }
 results.coverage.push({area:'PDF comparison '+lang,mode:'UI',details:'Complete report-gen sample PDFs compared without external slicing; complete wide report rejected when it exceeds the existing 80-page limit. The limit is intentional; it is not a report-generation failure.'});
}

(async()=>{try{
 server=spawn(python,[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:process.env});server.stderr.on('data',part=>fs.appendFileSync(path.join(out,'server.log'),part));
 const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server startup timeout')),60000);server.stdout.on('data',part=>{text+=part;for(const line of text.split('\n'))try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});server.once('error',reject);server.once('exit',code=>reject(Error('Server exit '+code)));});
 const executable=opt('--executable',engine==='chromium'?(process.env.RG_CHROMIUM_EXECUTABLE||process.env.REPORT_GEN_CHROMIUM):undefined);
 browser=await playwright[engine].launch({headless:!headed,...(executable?{executablePath:executable}:{})});results.browser=browser.version();
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
 context.setDefaultTimeout(30000);context.setDefaultNavigationTimeout(60000);
 await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){results.externalRequests.push(url);return route.abort();}return route.continue();});
 await context.addInitScript(()=>{window.__reportGenCsp=[];document.addEventListener('securitypolicyviolation',event=>window.__reportGenCsp.push({effectiveDirective:event.effectiveDirective,blockedURI:event.blockedURI,originalPolicy:event.originalPolicy}));if(window!==window.top)return;localStorage.setItem('rg.uiLang','es');localStorage.setItem('rg.previewVisible','0');});
 page=await context.newPage();page.on('pageerror',error=>{results.pageErrors.push(String(error));save();});
 page.on('console',entry=>{if(['error','warning'].includes(entry.type())&&/content.security|refused|pdf|mime|plug.?in/i.test(entry.text())){results.consoleDiagnostics.push({type:entry.type(),text:entry.text().slice(0,2000)});save();}});
 page.on('response',response=>{const url=new URL(response.url());if(response.status()>=400&&url.pathname.startsWith('/api/')){const row={method:response.request().method(),pathname:url.pathname,status:response.status()},expected=expectedFailures.find(value=>!value.consumed&&value.method===row.method&&value.pathname===row.pathname&&value.status===row.status);if(expected){expected.consumed=true;results.expectedApiErrors.push(row);}else results.apiErrors.push(row);save();}});
 const response=await page.goto(base);await clean(page);check('Local editor exposes CSP',!!response.headers()['content-security-policy']);
 const capabilities=await page.evaluate(()=>api.get('/api/docx-preview/capabilities'));
 check('Required native LibreOffice preview is available',capabilities.available,capabilities);
 for(const lang of ['es','en','pt']){
  await importLanguage(lang);await language(page,lang);const original=await snapshot(page);
  await sidebarAcceptance(lang);
  for(const view of ['assets','coverage','evidence','root_causes','retest','retest_matrix','retest_diff','review','history','backup','remediation_tasks']){await workflow(page,view);check(lang+' complete-case '+view+' view renders',await page.locator('[data-workflow-view="'+view+'"] [role="alert"]').count()===0);if(view==='evidence')await screen(page,'evidence-'+lang);}
  await click(page,'#guideBtn');await page.locator('[data-guide-page]').waitFor();for(let step=0;step<6;step++){await page.locator('[data-guide-step="'+step+'"]').click();await tutorialImages(lang,step);await screen(page,'tutorial-'+lang+'-'+(step+1));}
  await click(page,'#navHome');await diagnostics(lang);
  check(lang+' navigation, tutorial and rejected imports preserve exact source',await snapshot(page)===original);
  const exported=await createDocxJob(lang);await nativePreview(lang,exported);
  check(lang+' native preview source DOCX still downloads unchanged',await page.evaluate(async id=>{const response=await appFetch('/api/jobs/'+id+'/download'),bytes=await response.arrayBuffer();return [...new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))].map(value=>value.toString(16).padStart(2,'0')).join('');},exported.job.id)===exported.sha256);
  await compareSamples(lang);
  check(lang+' native export and comparison preserve exact source',await snapshot(page)===original);
  const annex=await uploadPDF(lang);await privacyPDF(lang,annex);await click(page,'#navHome');await screen(page,'dashboard-'+lang);
 }
 results.sourceEnd=sourceHashes();check('Application source remains unchanged during browser acceptance',isDeepStrictEqual(results.sourceStart,results.sourceEnd));check('No JavaScript application errors',results.pageErrors.length===0,results.pageErrors);check('Only explicitly declared negative import and PDF-limit controls failed',results.expectedApiErrors.length===expectedFailures.length&&expectedFailures.length>=3&&expectedFailures.every(value=>value.consumed)&&results.apiErrors.length===0,{expected:results.expectedApiErrors,unexpected:results.apiErrors});check('No external network requests',results.externalRequests.length===0,results.externalRequests);check('No browser PDF, CSP or MIME diagnostics',results.consoleDiagnostics.length===0,results.consoleDiagnostics);check('No CSP violations',await page.evaluate(()=>window.__reportGenCsp.length)===0);
 if(forcedExit)throw Error('Atlas browser process exceeded '+processBudgetMs+' ms');
 results.passed=true;results.finished=new Date().toISOString();save();console.log('PASS '+results.checks.length+' Atlas browser checks');
 }catch(error){results.passed=false;results.failure=String(error.stack||error);save();if(page&&!page.isClosed())await page.screenshot({path:path.join(out,'failure.png'),timeout:5000}).catch(()=>{});console.error(error);process.exitCode=1;}
 finally{clearTimeout(timer);server?.kill('SIGTERM');let closeFailed=false;try{if(browser)await boundedDiagnostic(browser.close(),5000,'Browser shutdown');}catch(error){closeFailed=true;results.cleanup_error=String(error);results.passed=false;save();process.exitCode=1;}fs.rmSync(workspace,{recursive:true,force:true});clearTimeout(processDeadline);if(forcedExit||closeFailed)process.exit(1);}
})();
