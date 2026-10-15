/* Real UI: reviewed SARIF intake and local, read-only PDF comparisons. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process'),{createHash}=require('node:crypto');
const {chromium}=require('playwright'),{JSDOM}=require('jsdom');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),opt=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const out=path.resolve(opt('--output','out/features-0360'));
fs.mkdirSync(out,{recursive:true});
const results={checks:[],pageErrors:[],externalRequests:[],screens:[],comparisons:[],source_hashes:{}};
for(const name of ['pdf-compare.js','pdf-compare.css','progress.js','workflow.js','workbench.js','index.html'])results.source_hashes[name]=createHash('sha256').update(fs.readFileSync(path.join(root,'webapp/static',name))).digest('hex');
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
const check=(name,passed,detail)=>{results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name);console.log('PASS '+name);};
const labels={
 es:{format:'Formato',review:'Revisar selección',apply:'Importar selección como pendiente',close:'Cerrar',compare:'Comparar archivos PDF',origin:'Origen SARIF conservado',excluded:'1 excluidas',cancelled:'Espera cancelada.'},
 en:{format:'Format',review:'Review selection',apply:'Import selection for review',close:'Close',compare:'Compare PDF files',origin:'Preserved SARIF provenance',excluded:'1 excluded',cancelled:'Waiting cancelled.'},
 pt:{format:'Formato',review:'Revisar seleção',apply:'Importar seleção para revisão',close:'Fechar',compare:'Comparar arquivos PDF',origin:'Origem SARIF preservada',excluded:'1 excluídas',cancelled:'Espera cancelada.'},
};
const observation={ruleId:'SYN001',level:'warning',message:{text:'Synthetic observation <img src=x onerror=alert(1)>; https://example.test/source'},locations:[{physicalLocation:{artifactLocation:{uri:'https://example.test/source.js'},region:{startLine:12,startColumn:3}}}],partialFingerprints:{primaryLocationLineHash:'synthetic-only'}};
const sarif=JSON.stringify({version:'2.1.0',runs:[{tool:{driver:{name:'Synthetic scanner',version:'1.0',rules:[{id:'SYN001',shortDescription:{text:'Synthetic finding <img src=x onerror=alert(1)>'}}]}},results:[observation,observation,{...observation,level:'note',message:{text:'Synthetic informational observation'}},{...observation,message:{text:'Suppressed synthetic observation'},suppressions:[{kind:'external',status:'accepted'}]}]}]});

// Small valid PDFs authored independently of the comparison renderer.
function pdf(lines){
 const objects=['<< /Type /Catalog /Pages 2 0 R >>','', '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>'];
 const children=[];
 for(const text of lines){const page=objects.length+1,stream=page+1;children.push(page+' 0 R');const content='BT /F1 14 Tf 20 240 Td ('+text.replace(/[\\()]/g,'\\$&')+') Tj ET';objects.push('<< /Type /Page /Parent 2 0 R /MediaBox [0 0 240 300] /Resources << /Font << /F1 3 0 R >> >> /Contents '+stream+' 0 R >>','<< /Length '+Buffer.byteLength(content)+' >>\nstream\n'+content+'\nendstream');}
 objects[1]='<< /Type /Pages /Kids ['+children.join(' ')+'] /Count '+lines.length+' >>';
 let text='%PDF-1.4\n',offsets=[0];for(const [index,object]of objects.entries()){offsets.push(Buffer.byteLength(text));text+=(index+1)+' 0 obj\n'+object+'\nendobj\n';}
 const xref=Buffer.byteLength(text);text+='xref\n0 '+(objects.length+1)+'\n0000000000 65535 f \n'+offsets.slice(1).map(n=>String(n).padStart(10,'0')+' 00000 n \n').join('')+'trailer\n<< /Size '+(objects.length+1)+' /Root 1 0 R >>\nstartxref\n'+xref+'\n%%EOF\n';return Buffer.from(text);
}
const earlier=pdf(['Stable header','Before remediation']),later=pdf(['Stable header','After remediation','Additional page']);
const snapshot=page=>page.evaluate(()=>JSON.stringify({data:S.data,revision:projectStore.revision,etag:projectStore.etag,dirty:projectStore.dirty}));
async function screenshot(page,name){const file=path.join(out,name+'.png');await page.screenshot({path:file,fullPage:true});results.screens.push({name,path:file,sha256:createHash('sha256').update(fs.readFileSync(file)).digest('hex')});save();}
async function intake(page,lang){
 if(!await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();
 if(!await page.locator('#projectActions').evaluate(el=>el.open))await page.locator('#projectActions > summary').click();
 await page.locator('#intakeBtn').click();const dialog=page.locator('dialog.progress-dialog');await dialog.waitFor();
 await dialog.getByLabel(labels[lang].format,{exact:true}).selectOption('sarif');
 await dialog.locator('input[type=file]').setInputFiles({name:'synthetic.sarif',mimeType:'application/sarif+json',buffer:Buffer.from(sarif)});
 await dialog.locator('[data-import-panel="2"]').waitFor({state:'visible'});
 await dialog.getByRole('button',{name:labels[lang].review,exact:true}).click();
 await dialog.locator('[data-import-panel="3"]').waitFor({state:'visible'});return dialog;
}
async function fit(page,dialog,label){
 const geometry=await dialog.evaluate(el=>{const rect=el.getBoundingClientRect();return {viewport:innerWidth,document:document.documentElement.scrollWidth,width:rect.width,scroll:el.scrollWidth,client:el.clientWidth,controls:[...el.querySelectorAll('button:not([hidden]),input:not([type=checkbox]),a.btn')].filter(n=>n.getClientRects().length).map(n=>{const r=n.getBoundingClientRect();return {left:r.left,right:r.right,height:r.height};})};});
 check(label,geometry.document<=geometry.viewport+1&&geometry.width<=geometry.viewport&&geometry.scroll<=geometry.client+1&&geometry.controls.every(c=>c.left>=0&&c.right<=geometry.viewport+1&&c.height>=40),geometry);
}
let browser,page,server,timer;
(async()=>{try{
 server=spawn(process.env.RG_PYTHON||'python3',[path.join(root,'scripts/browser-server-0212.py')],{cwd:root,env:process.env});
 server.stderr.on('data',value=>fs.appendFileSync(path.join(out,'server.log'),value));
 const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server startup timeout')),30000);server.stdout.on('data',part=>{text+=part;if(text.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(text.split('\n')[0]).url);}catch(error){reject(error);}}});server.once('error',reject);server.once('exit',code=>reject(Error('Server exited '+code)));});
 const executable=opt('--executable',process.env.RG_CHROMIUM_EXECUTABLE||process.env.REPORT_GEN_CHROMIUM);
 browser=await chromium.launch({headless:true,...(executable?{executablePath:executable}:{})});results.browser=browser.version();
 for(const lang of ['es','en','pt']){
  const l=labels[lang],context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
  await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){results.externalRequests.push(url);return route.abort();}return route.continue();});
  await context.addInitScript(lang=>{if(window!==window.top)return;localStorage.setItem('rg.uiLang',lang);localStorage.setItem('rg.previewVisible','0');const create=URL.createObjectURL.bind(URL),revoke=URL.revokeObjectURL.bind(URL);window.pdfObjectURLs={created:[],revoked:[]};URL.createObjectURL=blob=>{const url=create(blob);window.pdfObjectURLs.created.push(url);return url;};URL.revokeObjectURL=url=>{window.pdfObjectURLs.revoked.push(url);return revoke(url);};},lang);
  page=await context.newPage();page.on('pageerror',error=>results.pageErrors.push(String(error)));
  await page.goto(base);await page.locator('.workspace-dashboard').waitFor();
  await page.evaluate(async lang=>{const slug='features-'+lang;await requireOk(await api.post('/api/projects',{slug,title:'Synthetic features '+lang}));await refreshProjects();await loadProject(slug);},lang);
  await page.waitForFunction(()=>S.slug&&!projectStore.loading&&!projectBusyCount);
  const original=await snapshot(page),count=await page.evaluate(()=>S.data.findings.length);
  let dialog=await intake(page,lang);
  check(lang+' SARIF preview preserves exact project',await snapshot(page)===original);
  check(lang+' SARIF preview selects two distinct candidates, omits duplicate and excludes suppression',await dialog.locator('[data-intake-row="0"]').isChecked()&&!await dialog.locator('[data-intake-row="1"]').isChecked()&&await dialog.locator('[data-intake-row="2"]').isChecked()&&await dialog.locator('[data-intake-row="3"]').isDisabled()&&!await dialog.locator('[data-intake-row="3"]').isChecked());
  check(lang+' SARIF exclusion count and literal hostile text are visible',(await dialog.innerText()).includes(l.excluded)&&(await dialog.innerText()).includes('<img src=x')&&await dialog.locator('.intake-rows img').count()===0);
  await dialog.locator('.intake-rows>article').first().locator('details').first().locator('summary').first().click();
  await dialog.getByText(l.origin,{exact:true}).first().click();
  check(lang+' SARIF source level, tool, path and hash survive preview',(await dialog.innerText()).includes('warning')&&(await dialog.innerText()).includes('Synthetic scanner')&&(await dialog.innerText()).includes('https://example.test/source.js')&&(await dialog.innerText()).includes('SHA-256:'));
  await screenshot(page,'sarif-provenance-'+lang);
  await dialog.locator('.intake-rows>article').first().locator('details').first().locator('summary').first().click();
  await dialog.evaluate(el=>{el.scrollTop=0;});await screenshot(page,'sarif-review-'+lang);
  await page.setViewportSize({width:320,height:1000});await fit(page,dialog,lang+' SARIF review fits320px');
  await dialog.getByRole('button',{name:l.apply,exact:true}).click();await dialog.waitFor({state:'detached'});
  check(lang+' SARIF apply imports exactly two informational, unverified observations',await page.evaluate(count=>{const added=S.data.findings.slice(count);return added.length===2&&added.every(f=>f.severity==='info'&&f.verification==='unverified'&&f.import_source.format==='sarif'&&f.import_source.reviewed===false)&&added.map(f=>f.import_source.level).join(',')==='warning,note';},count));
  await page.setViewportSize({width:1440,height:1000});dialog=await intake(page,lang);
  check(lang+' SARIF reimport disables every existing or excluded candidate',await dialog.locator('[data-intake-row]:not(:disabled)').count()===0&&await dialog.getByRole('button',{name:l.apply,exact:true}).isDisabled());
  await dialog.getByRole('button',{name:l.close,exact:true}).click();await dialog.waitFor({state:'detached'});
  if(await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();
  await page.evaluate(()=>select('workflow','history'));
  const entry=page.getByRole('button',{name:l.compare,exact:true});await entry.waitFor();await entry.click();
  dialog=page.locator('[data-pdf-compare]');await dialog.waitFor();const beforeComparison=await snapshot(page);
  await dialog.locator('[data-pdf-before]').setInputFiles({name:'earlier.pdf',mimeType:'application/pdf',buffer:earlier});
  await dialog.locator('[data-pdf-after]').setInputFiles({name:'later.pdf',mimeType:'application/pdf',buffer:later});
  await dialog.locator('[data-pdf-compare-submit]').click();
  const frame=dialog.frameLocator('[data-pdf-compare-frame]');await frame.locator('#comparison-summary').waitFor({timeout:60000});
  const comparisonURLs=[await dialog.locator('[data-pdf-compare-frame]').getAttribute('src')];
  const manifest=JSON.parse(await frame.locator('#comparison-manifest').textContent());
  check(lang+' PDF comparison identifies unchanged, changed and added pages',manifest.summary.unchanged===1&&manifest.summary.changed===1&&manifest.summary.added===1&&manifest.summary.total_pages===3,manifest.summary);
  check(lang+' PDF comparison stays sandboxed without scripts',await dialog.locator('iframe').getAttribute('sandbox')===''&&await frame.locator('script').count()===0);
  check(lang+' PDF comparison leaves exact project and saved revision unchanged',await snapshot(page)===beforeComparison);
  const downloadPromise=page.waitForEvent('download');await dialog.locator('[data-pdf-compare-download]').click();const download=await downloadPromise;
  const downloaded=path.join(out,'comparison-'+lang+'.html');await download.saveAs(downloaded);
  const downloadedBytes=fs.readFileSync(downloaded),downloadedHTML=downloadedBytes.toString('utf8');
  const downloadedDocument=new JSDOM(downloadedHTML);const downloadedManifest=JSON.parse(downloadedDocument.window.document.querySelector('#comparison-manifest').textContent);downloadedDocument.window.close();
  check(lang+' downloaded comparison contains the same manifest and embedded images',download.suggestedFilename()==='report-gen-pdf-comparison.html'&&downloadedHTML.includes('data:image/png;base64,')&&JSON.stringify(downloadedManifest)===JSON.stringify(manifest));
  results.comparisons.push({language:lang,path:downloaded,sha256:createHash('sha256').update(downloadedBytes).digest('hex'),summary:manifest.summary});save();
  await dialog.locator('[data-pdf-compare-download]').scrollIntoViewIfNeeded();await screenshot(page,'pdf-comparison-'+lang);
  await frame.locator('#page-2').scrollIntoViewIfNeeded();await frame.locator('#page-2').evaluate(el=>Promise.all([...el.querySelectorAll('img')].map(img=>img.decode())));
  await screenshot(page,'pdf-differences-'+lang);
  await frame.locator('#comparison-summary').scrollIntoViewIfNeeded();
  await page.setViewportSize({width:320,height:1000});await fit(page,dialog,lang+' PDF comparison fits320px');await dialog.locator('[data-pdf-compare-download]').scrollIntoViewIfNeeded();await screenshot(page,'pdf-comparison-mobile-'+lang);
  const currentURL=await dialog.locator('[data-pdf-compare-frame]').getAttribute('src');
  await dialog.locator('[data-pdf-after]').setInputFiles({name:'earlier-again.pdf',mimeType:'application/pdf',buffer:earlier});
  check(lang+' changing a selected PDF removes stale preview and revokes its URL',await dialog.locator('iframe').count()===0&&await page.evaluate(url=>window.pdfObjectURLs.revoked.includes(url),currentURL));
  if(lang==='es'){
   await dialog.locator('[data-pdf-before]').setInputFiles({name:'later.pdf',mimeType:'application/pdf',buffer:later});
   await dialog.locator('[data-pdf-compare-submit]').click();await frame.locator('#comparison-summary').waitFor({timeout:60000});
   comparisonURLs.push(await dialog.locator('[data-pdf-compare-frame]').getAttribute('src'));
   const reversed=JSON.parse(await frame.locator('#comparison-manifest').textContent());check('Reversed PDF comparison identifies the removed page',reversed.summary.removed===1&&reversed.summary.added===0,reversed.summary);
  }
  await dialog.getByRole('button',{name:l.close,exact:true}).click();
  // Native dialog.close queues its close event; cleanup and focus restoration
  // finish when the production listener removes the dialog.
  await dialog.waitFor({state:'detached'});
  const cleanup=await entry.evaluate((el,urls)=>({focusRestored:document.activeElement===el,activeElement:{tag:document.activeElement?.tagName,id:document.activeElement?.id,text:document.activeElement?.textContent?.slice(0,100)},comparisonURLs:urls,created:window.pdfObjectURLs.created,revoked:window.pdfObjectURLs.revoked,allCreated:urls.every(url=>window.pdfObjectURLs.created.includes(url)),allRevoked:urls.every(url=>window.pdfObjectURLs.revoked.includes(url))}),comparisonURLs);
  check(lang+' closing comparison restores entry focus and revokes all comparison URLs',cleanup.focusRestored&&cleanup.allCreated&&cleanup.allRevoked,cleanup);
  await page.setViewportSize({width:1440,height:1000});
  // Delay only this request; cancellation must not leave a preview or download.
  let release,started;const held=new Promise(resolve=>release=resolve),requestStarted=new Promise(resolve=>started=resolve);
  const hold=async route=>{started();await held;await route.abort('aborted').catch(()=>{});};await context.route(base+'/api/pdf-compare',hold);
  await entry.click();dialog=page.locator('[data-pdf-compare]');
  await dialog.locator('[data-pdf-before]').setInputFiles({name:'earlier.pdf',mimeType:'application/pdf',buffer:earlier});await dialog.locator('[data-pdf-after]').setInputFiles({name:'later.pdf',mimeType:'application/pdf',buffer:later});
  await dialog.locator('[data-pdf-compare-submit]').click();await requestStarted;
  await dialog.locator('[data-pdf-compare-cancel]').click();
  check(lang+' cancelling restores usable controls without a result',(await dialog.locator('[data-pdf-compare-status]').innerText()).startsWith(l.cancelled)&&!await dialog.locator('[data-pdf-compare-submit]').isDisabled()&&await dialog.locator('iframe').count()===0);
  release();await context.unroute(base+'/api/pdf-compare',hold);await dialog.getByRole('button',{name:l.close,exact:true}).click();await dialog.waitFor({state:'detached'});
  check(lang+' cancelled comparison keeps exact project content',await snapshot(page)===beforeComparison);
  await context.close();
 }
 check('No scanner target or external network requests',results.externalRequests.length===0,results.externalRequests);
 check('No application JavaScript errors',results.pageErrors.length===0,results.pageErrors);
 results.passed=true;save();
}catch(error){results.passed=false;results.error=String(error.stack||error);save();if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});console.error(error);process.exitCode=1;}
finally{clearTimeout(timer);await browser?.close();server?.kill('SIGTERM');}})();
