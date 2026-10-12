/* Independent R8 acceptance. Synthetic disposable projects only. */
'use strict';
const fs=require('node:fs'), path=require('node:path'), os=require('node:os'), {spawn}=require('node:child_process');
const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'));
const args=process.argv.slice(2),out=path.resolve(args.includes('--output')?args[args.indexOf('--output')+1]:process.env.R8_EXPERIENCE_OUT||'out/project-gallery-0330');
const {chromium}=require(require.resolve('playwright',{paths:[root]}));
const axeSource=fs.readFileSync(require.resolve('axe-core/axe.min.js',{paths:[root]}),'utf8');
const {apiResponseHeaders}=require(path.join(root,'tests/browser-api-headers.cjs'));
fs.mkdirSync(out,{recursive:true});
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-r8-experience-'));
fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const {createHash}=require('node:crypto');
const sourcePaths=['webapp/static/design-library.js','webapp/static/app.js','webapp/static/style.css','webapp/static/studio.css','webapp/static/index.html','webapp/design_api.py','designs/certifications.json'];
const sourceHashes=()=>Object.fromEntries(sourcePaths.map(p=>[p,createHash('sha256').update(fs.readFileSync(path.join(root,p))).digest('hex')]));
const results={sourceStart:sourceHashes(),started:new Date().toISOString(),checks:[],states:[],errors:[],external:[],requests:[],workspace,limitations:['Chromium local application only.','No human screen reader.','Screenshots require a separate visual-review receipt.']};
function save(){fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));}
function check(name,passed,detail,critical=false){results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();console.log((passed?'PASS ':'FAIL ')+name);if(!passed&&critical)throw Error(name);}
const server=spawn(process.env.RG_PYTHON||'python',[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:{...process.env,PYTHONPATH:root+path.delimiter+path.join(root,'webapp')}});
server.stderr.on('data',data=>fs.appendFileSync(path.join(out,'server.log'),data));
let browser,page,context,base,timer;
async function idle(){await page.waitForFunction(()=>!projectStore.loading&&!projectBusyCount);}
async function openNew(){
  const hero=page.getByRole('button',{name:/^(Crear mi proyecto|Create my project)$/});
  if(await hero.isVisible()){await hero.focus();await page.keyboard.press('Enter');}
  else{const menu=page.locator('#studioMore');if(!await menu.evaluate(el=>el.open))await menu.locator('summary').first().click();await page.locator('#newProjectBtn').focus();await page.keyboard.press('Enter');}
  await page.locator('dialog.design-dialog[open]').waitFor();
}
async function selectCategory(id){const dialog=page.locator('dialog.design-dialog[open]'),mobile=dialog.locator('[data-design-category-select]');if(await mobile.isVisible())await mobile.selectOption(id);else await dialog.locator('[data-design-category="'+id+'"]').click();}
async function closeAll(){await page.evaluate(()=>document.querySelectorAll('dialog[open]').forEach(d=>d.close()));await page.waitForFunction(()=>!document.querySelector('dialog[open]'));}
async function inspectState(name,selector='dialog[open]'){
  const modal=page.locator(selector).last();
  await modal.waitFor();await page.evaluate(()=>document.fonts.ready);
  await modal.evaluate(el=>el.scrollTop=0);
  const state=await modal.evaluate(el=>{
    const rect=n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,right:r.right,bottom:r.bottom,width:r.width,height:r.height};};
    const visible=n=>{const s=getComputedStyle(n);return n.getClientRects().length&&s.visibility!=='hidden'&&s.display!=='none';};
    const controls=[...el.querySelectorAll('button,input,select,textarea,summary,a')].filter(visible).map(n=>({tag:n.tagName,id:n.id,text:(n.getAttribute('aria-label')||n.textContent||'').trim().slice(0,100),...rect(n),scrollWidth:n.scrollWidth,clientWidth:n.clientWidth,focusable:n.tabIndex>=0}));
    const r=rect(el), horizontal=[];
    for(const n of [...el.querySelectorAll('*')].filter(visible)){const t=n.tagName;if(['OPTION','SCRIPT','STYLE','IMG','IFRAME'].includes(t))continue;const nr=rect(n);if(nr.right>r.right+1||nr.x<r.x-1)horizontal.push({tag:t,class:n.className,text:n.textContent.trim().slice(0,75),...nr});}
    return {width:innerWidth,height:innerHeight,rootOverflow:document.documentElement.scrollWidth-innerWidth,modal:r,controls,horizontal,activeWithin:el.contains(document.activeElement),modalScrollWidth:el.scrollWidth,modalClientWidth:el.clientWidth};
  });
  check(name+' modal and visible content fit horizontally',state.modal.x>=-1&&state.modal.right<=state.width+1&&state.rootOverflow<=1&&state.modalScrollWidth<=state.modalClientWidth+1&&state.horizontal.length===0,state);
  check(name+' actionable controls have unclipped width',state.controls.every(c=>c.scrollWidth<=c.clientWidth+1||['SELECT','INPUT'].includes(c.tag)),state.controls.filter(c=>c.scrollWidth>c.clientWidth+1));

  const a=await page.evaluate(selector=>axe.run(document.querySelectorAll(selector)[document.querySelectorAll(selector).length-1],{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}),selector);
  check(name+' automated accessibility has no violations',a.violations.length===0,a.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})));
  state.name=name;state.axe={violations:a.violations.length,incomplete:a.incomplete.map(x=>({id:x.id,nodes:x.nodes.length})),passes:a.passes.length};
  await page.screenshot({path:path.join(out,name+'.png')});results.states.push(state);save();return state;
}
async function exportViaUI(format,label){
 const menu=page.locator('#studioMore');if(!await menu.evaluate(el=>el.open))await menu.locator('summary').first().click();
 const exportMenu=page.locator('#exportMenu');if(!await exportMenu.evaluate(el=>el.open))await exportMenu.locator('summary').first().click();
 const previousIds=await page.evaluate(async()=>(await api.get('/api/jobs')).map(j=>j.id));
 await page.locator('#exportFormat').selectOption(format);await page.locator('#downloadBtn').click();
 await page.waitForFunction(previous=>[...document.querySelectorAll('.job-card')].some(row=>!previous.includes(row.dataset.job)&&['done','error'].includes(row.dataset.stage)),previousIds,{timeout:120000});
 const rows=await page.locator('.job-card').evaluateAll(rows=>rows.map(r=>({id:r.dataset.job,stage:r.dataset.stage,text:r.innerText})));
 const row=rows.find(r=>!previousIds.includes(r.id)&&r.stage==='done');check(label+' UI export completes',!!row,rows,true);
 const download=page.waitForEvent('download');await page.locator('[data-job="'+row.id+'"] button.primary').click();const file=await download;
 const target=path.join(out,label+'-'+file.suggestedFilename());await file.saveAs(target);results.exports??=[];results.exports.push({label,format,path:target,bytes:fs.statSync(target).size});
 await page.locator('#exportDrawer .experience-heading button').click();
}
(async()=>{try{
 base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server timeout')),30000);server.stdout.on('data',data=>{text+=data;for(const line of text.split('\n'))try{const j=JSON.parse(line);if(j.url){clearTimeout(timer);resolve(j.url);}}catch{}});server.on('exit',code=>reject(Error('Server exited '+code)));});
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']});results.browser=browser.version();
 context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});
 await context.route('**/*',route=>{const u=route.request().url();if(/^https?:/.test(u)&&!u.startsWith(base+'/')){results.external.push(u);return route.abort();}return route.continue();});
 await context.addInitScript({content:axeSource});
 page=await context.newPage();page.on('pageerror',e=>results.errors.push(String(e)));
 page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))results.requests.push({method:r.method(),url:r.url().replace(base,''),postData:r.postData()});});
 await page.addInitScript(()=>{localStorage.setItem('rg.previewVisible','0');localStorage.setItem('rg.uiLang','es');});
 await page.goto(base);await page.waitForFunction(()=>typeof DesignLibraryUI!=='undefined'&&!document.getElementById('splash')&&!projectStore.loading&&!projectBusyCount);await page.locator('.workspace-dashboard').waitFor();
 await openNew();
 check('New project starts with a gallery rather than the final form',await page.locator('dialog.design-dialog[open]').count()===1&&!await page.locator('#newModal').evaluate(el=>el.open),undefined,true);
 results.initialGallery=await page.locator('dialog.design-dialog[open]').innerText();
 const d=page.locator('dialog.design-dialog[open]');
 await inspectState('initial-es-desktop');
 await d.locator('[data-design-category="personal"]').focus();await page.keyboard.press('Enter');
 check('Empty personal category announces no matches and clears selected card',await d.locator('.design-empty').isVisible()&&await d.locator('.design-card[aria-pressed="true"]').count()===0&&await d.getByRole('button',{name:'Continuar con esta plantilla',exact:true}).count()===0);
 await page.keyboard.press('Escape');await page.waitForFunction(()=>!document.querySelector('dialog[open]'));
 check('Escape returns focus to a visible enabled trigger',await page.evaluate(()=>{const e=document.activeElement;const r=e.getBoundingClientRect();return e!==document.body&&!e.disabled&&r.width>0&&r.height>0;}));
 await openNew();
 check('Reopening an empty category cannot offer a hidden stale template',await d.locator('.design-empty').isVisible()&&await d.getByRole('button',{name:'Continuar con esta plantilla',exact:true}).count()===0,await d.locator('.design-detail').innerText());
 await d.getByRole('button',{name:'Ver todas las plantillas',exact:true}).click();
 check('Empty-state recovery exposes actual designs and resets search',await d.locator('.design-card').count()>6&&await d.locator('input[type="search"]').inputValue()==='');
 await d.locator('input[type="search"]').fill('NO-MATCH-R8-968512');
 check('Unmatched search clears selection and creation action',await d.locator('.design-empty').isVisible()&&await d.getByRole('button',{name:'Continuar con esta plantilla',exact:true}).count()===0);
 await d.locator('.experience-heading button').click();await openNew();
 check('Reopening unmatched search does not restore a stale creation action',await d.locator('.design-empty').isVisible()&&await d.getByRole('button',{name:'Continuar con esta plantilla',exact:true}).count()===0,await d.locator('.design-detail').innerText());
 await d.getByRole('button',{name:'Ver todas las plantillas',exact:true}).click();
 await selectCategory('general');
 await d.locator('[data-design="laboratorio"]').focus();await page.keyboard.press('Space');
 check('Keyboard Space selects a single visible design',await d.locator('[data-design="laboratorio"]').getAttribute('aria-pressed')==='true'&&await d.locator('.design-card[aria-pressed="true"]').count()===1);
 await d.getByRole('button',{name:'Continuar con esta plantilla',exact:true}).click();await page.locator('#newModal[open]').waitFor();
 await page.locator('#mTitle').fill('Informe de validación sintética R8');await page.locator('#mClient').fill('Entidad ficticia');await page.locator('#mSlug').fill('qa-r8-general');await page.locator('#mLang').selectOption('corporativo-en');
 await page.locator('#mPresetOptions > summary').click();
 const presetValue=await page.locator('#mPreset option').evaluateAll(options=>options.find(o=>o.value!=='base'&&!o.value.startsWith('family:'))?.value);
 check('There is a representative non-default structure option',!!presetValue,presetValue,true);await page.locator('#mPreset').selectOption(presetValue);
 const expected=await page.evaluate(()=>({title:$('#mTitle').value,client:$('#mClient').value,slug:$('#mSlug').value,lang:$('#mLang').value,preset:$('#mPreset').value}));
 await page.locator('#newProjectLibrary button').click();await d.waitFor();
 check('Back retains gallery selection and starter language',await d.locator('[data-design="laboratorio"]').getAttribute('aria-pressed')==='true'&&await d.locator('[data-design-sample-language]').inputValue()==='en');
 await d.locator('[data-design="ejecutivo"]').click();await d.getByRole('button',{name:'Continuar con esta plantilla',exact:true}).click();
 check('Changing design retains all typed details, language and non-default preset',await page.evaluate(expected=>JSON.stringify(expected)===JSON.stringify({title:$('#mTitle').value,client:$('#mClient').value,slug:$('#mSlug').value,lang:$('#mLang').value,preset:$('#mPreset').value}),expected));
 await inspectState('details-es-desktop','#newModal[open]');
 await page.locator('#mCancel').focus();await page.keyboard.press('Enter');await openNew();await d.getByRole('button',{name:'Continuar con esta plantilla',exact:true}).click();
 check('Cancel and reopening preserve unfinished details',await page.evaluate(expected=>JSON.stringify(expected)===JSON.stringify({title:$('#mTitle').value,client:$('#mClient').value,slug:$('#mSlug').value,lang:$('#mLang').value,preset:$('#mPreset').value}),expected));
 await page.mouse.click(2,2);
 check('Backdrop does not discard the in-progress form',await page.locator('#newModal').evaluate(el=>el.open));
 await closeAll();
 check('Browsing and canceling do not create or save projects',results.requests.filter(r=>r.method==='POST'||r.method==='PUT').length===0,results.requests);

 // Catalog failure must be recoverable without creating a project.
 const responseHeaders=await apiResponseHeaders(context,base);
 let failedCatalog=false;
 const catalogFailure=async route=>{if(!failedCatalog){failedCatalog=true;await route.fulfill({status:503,json:{error:'Synthetic catalog unavailable'},headers:responseHeaders});}else await route.continue();};
 await page.route('**/api/design-library',catalogFailure);
 const hero=page.getByRole('button',{name:'Crear mi proyecto',exact:true});await hero.click();
 await page.waitForFunction(()=>!!document.querySelector('.toast.toast-err'));
 check('Catalog failure shows a recoverable error without opening a broken dialog',await page.locator('.toast.toast-err').isVisible()&&await page.locator('dialog[open]').count()===0);
 await page.unroute('**/api/design-library',catalogFailure);await openNew();
 check('Catalog request recovers through the same visible entry point',await d.isVisible());
 await closeAll();
 // Small directed geometry matrix, no project writes.
 for(const [width,lang,theme] of [[320,'es','dark'],[390,'en','light'],[768,'es','light'],[1440,'en','dark']]){
   await page.setViewportSize({width,height:1000});await page.evaluate(({lang,theme})=>{setUiLang(lang);applyUiTheme(theme);},{lang,theme});
   await openNew();await selectCategory('general');await d.locator('[data-design="corporativo"]').click();
   await inspectState('gallery-'+width+'-'+lang+'-'+theme);
   await d.locator('.design-detail').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'gallery-detail-'+width+'-'+lang+'-'+theme+'.png')});
   // Trap check does not rely on one particular button order.
   const tabSteps=await d.locator('button,input,select,summary,a').count()+3,focusTrail=[];
   for(let n=0;n<tabSteps;n++){await page.keyboard.press('Tab');focusTrail.push(await d.evaluate(el=>{const a=document.activeElement;return {within:el.contains(a),browserChrome:a===document.body||a===document.documentElement,tag:a.tagName,id:a.id,label:(a.getAttribute('aria-label')||a.textContent).trim().slice(0,80)};}));}
   check('Tab never focuses the inert background at '+width+'/'+lang,focusTrail.every(x=>x.within||x.browserChrome),focusTrail);
   await d.getByRole('button',{name:/^(Continuar con esta plantilla|Continue with this design)$/}).click();
   await page.locator('#mTitle').fill('Synthetic extended project title — '+('bounded review '.repeat(12)));
   await page.locator('#mClient').fill('Synthetic long client name '+('operational validation '.repeat(7)));
   await inspectState('form-'+width+'-'+lang+'-'+theme,'#newModal[open]');await page.locator('#mCancel').click();
 }
 await page.setViewportSize({width:1440,height:1000});await page.evaluate(()=>{setUiLang('es');applyUiTheme('dark');});
 await openNew();await selectCategory('general');await d.locator('[data-design="ejecutivo"]').click();await d.getByRole('button',{name:'Continuar con esta plantilla',exact:true}).click();
 await page.locator('#mTitle').fill('Informe de validación sintética R8');await page.locator('#mClient').fill('Entidad ficticia');await page.locator('#mSlug').fill('qa-r8-general');await page.locator('#mLang').selectOption('corporativo-en');
 if(!await page.locator('#mPresetOptions').evaluate(el=>el.open))await page.locator('#mPresetOptions > summary').click();
 await page.locator('#mPreset').selectOption(presetValue);
 const createSnapshot=await page.evaluate(()=>({title:$('#mTitle').value,client:$('#mClient').value,slug:$('#mSlug').value,lang:$('#mLang').value,preset:$('#mPreset').value}));
 let failedCreate=false,actualCreates=0;
 const createFailure=async route=>{if(route.request().method()!=='POST')return route.continue();if(!failedCreate){failedCreate=true;await route.fulfill({status:503,json:{error:'Synthetic creation unavailable'},headers:responseHeaders});}else{actualCreates++;await new Promise(r=>setTimeout(r,300));await route.continue();}};
 await page.route('**/api/projects',createFailure);await page.locator('#mCreate').click();await page.locator('#newProjectError').waitFor();
 check('Creation failure announces an error and preserves every typed field',await page.locator('#newProjectError').getAttribute('role')==='alert'&&await page.evaluate(expected=>JSON.stringify(expected)===JSON.stringify({title:$('#mTitle').value,client:$('#mClient').value,slug:$('#mSlug').value,lang:$('#mLang').value,preset:$('#mPreset').value}),createSnapshot));
 await page.locator('#mCreate').dblclick();await page.waitForFunction(()=>S.slug==='qa-r8-general'&&!projectStore.loading&&!projectBusyCount);
 check('Double confirmation creates exactly one actual project',actualCreates===1,actualCreates);await page.unroute('**/api/projects',createFailure);
 const general=await page.evaluate(()=>({slug:S.slug,meta:S.data.meta,sections:S.data.report.sections,expectedPreset:S.presets.find(p=>p.id===selectedPresetId())}));results.generalProject=general;
 check('Saved general design overrides the old preset appearance without dropping client/language',general.meta.theme==='ejecutivo'&&general.meta.lang==='en'&&general.meta.client==='Entidad ficticia'&&general.meta.report_title==='Informe de validación sintética R8',general.meta);
 const editIndex=await page.evaluate(()=>S.data.report.sections.findIndex(s=>(S.catBy[s.key]?.fields||[]).some(f=>f.type==='markdown')));
 check('Representative general project exposes an editable authored section',editIndex>=0,editIndex,true);await page.locator('#navReport').click();await page.locator('#sectionList .finding-nav').nth(editIndex).click();
 const ta=page.locator('#editor .mded textarea').first(),literalUrl='https://evidence.example/review/r8/segment_(retained)/'+('long-component-'.repeat(8))+'?asset=server-x&scope=%2Fbank%2Fidentity&trace=R8%20sample';
 await ta.fill(literalUrl);await ta.focus();await page.keyboard.press('ControlOrMeta+A');await page.getByRole('button',{name:'Enlace',exact:true}).first().click();
 const linkDialog=page.locator('dialog[data-link-dialog]');await linkDialog.waitFor();
 check('Link editor prefills selected literal URL without normalization',await linkDialog.locator('[data-link-url]').inputValue()===literalUrl&&await linkDialog.locator('[data-link-name]').inputValue()==='');
 await page.setViewportSize({width:320,height:1000});await inspectState('link-dialog-320-es','dialog[data-link-dialog]');
 await linkDialog.locator('[data-link-name]').fill('Evidence register R8');await linkDialog.getByRole('button',{name:'Insertar enlace',exact:true}).click();
 check('Explicit descriptive link insertion preserves complete exact destination',await ta.inputValue()==='[Evidence register R8](<'+literalUrl+'>)');
 await page.setViewportSize({width:1440,height:1000});results.literalUrl=literalUrl;

 await exportViaUI('html','general');
 const htmlExport=fs.readFileSync(results.exports.find(x=>x.label==='general').path,'utf8');const {JSDOM}=require(require.resolve('jsdom',{paths:[root]}));const exportDOM=new JSDOM(htmlExport);check('HTML export keeps descriptive link text and literal href',Array.from(exportDOM.window.document.querySelectorAll('a')).some(a=>a.textContent==='Evidence register R8'&&a.getAttribute('href')===literalUrl));exportDOM.window.close();
 await page.reload();await idle();await page.waitForFunction(()=>S.slug==='qa-r8-general');
 check('Selected appearance, title and client survive a real reload',await page.evaluate(()=>S.data.meta.theme==='ejecutivo'&&S.data.meta.client==='Entidad ficticia'&&S.data.meta.report_title==='Informe de validación sintética R8'));
 await page.evaluate(()=>setUiLang('en'));await openNew();await selectCategory('corporate');
 const editorialCard=d.locator('[data-design="enterprise-control-review"]');await editorialCard.waitFor();await editorialCard.click();await d.locator('[data-design-variant]').selectOption('quiet');await editorialCard.click();check('Re-selecting the same profile preserves quiet variant',await d.locator('[data-design-variant]').inputValue()==='quiet');
 await d.locator('[data-design-sample-language]').selectOption('es');await d.getByRole('button',{name:'Continue with this design',exact:true}).click();
 await page.locator('#mTitle').fill('Revisión editorial de controles R8');await page.locator('#mClient').fill('Organización ficticia');await page.locator('#mSlug').fill('qa-r8-editorial');
 check('Specialized profile discloses its structure and does not expose an unrelated preset selector',await page.locator('#mPresetOptions').isHidden()&&await page.locator('#mDesignSelected').innerText().then(t=>/Control Review/.test(t)&&/Quiet/.test(t)));
 await page.locator('#newProjectLibrary button').click();check('Profile quiet variant and ES report language survive Back',await d.locator('[data-design-variant]').inputValue()==='quiet'&&await d.locator('[data-design-sample-language]').inputValue()==='es');
 await d.getByRole('button',{name:'Continue with this design',exact:true}).click();await page.locator('#mCreate').click();await page.waitForFunction(()=>S.slug==='qa-r8-editorial'&&!projectStore.loading&&!projectBusyCount);
 const editorial=await page.evaluate(()=>({slug:S.slug,meta:S.data.meta,sections:S.data.report.sections}));results.editorialProject=editorial;
 check('Editorial project stores profile identity, variant, client and authored language',editorial.meta.design?.id==='enterprise-control-review'&&editorial.meta.design?.variant==='quiet'&&editorial.meta.design?.layout==='editorial'&&editorial.meta.lang==='es'&&editorial.meta.client==='Organización ficticia',editorial.meta);
 await exportViaUI('docx','editorial');
 // Duplicating from a purpose category or a previous search must reveal the saved design.
 // A renamed personal design deliberately does not match the original OSCP search.
 let lastPersonal;
 for(const filter of ['category','search','edit']){
   await closeAll();const before=await page.evaluate(()=>({data:JSON.stringify(S.data),etag:projectStore.etag}));
   await page.evaluate(()=>DesignLibraryUI.gallery(document.getElementById('designLibraryBtn')));
   if(filter==='category')await selectCategory('certification');else await d.locator('input[type="search"]').fill(filter==='edit'?lastPersonal.name:'OSCP');
   await d.locator('[data-design="'+(filter==='edit'?lastPersonal.id:'offsec-oscp')+'"]').click();await d.locator('[data-design-variant]').selectOption('quiet');
   await d.getByRole('button',{name:filter==='edit'?'Edit design':'Duplicate and customize',exact:true}).click();
   const custom=page.locator('dialog.experience-dialog:not(.design-dialog)').last(),name='Synthetic '+filter+' board format';
   await custom.locator('[data-design-field="name"]').fill(name);
   const saved=page.waitForResponse(r=>r.url().endsWith('/api/design-library/personal'+(filter==='edit'?'/'+lastPersonal.id:''))&&r.request().method()===(filter==='edit'?'PUT':'POST')&&r.request().postDataJSON()?.name===name);
   await custom.getByRole('button',{name:'Save design',exact:true}).click();const response=await saved,entry=await response.json();
   check(filter+' personal design is saved successfully',response.ok()&&entry.name===name,entry.id,true);lastPersonal=entry;
   await custom.waitFor({state:'hidden'});const card=d.locator('[data-design="'+entry.id+'"]');
   // Editing keeps the ID: its old card can remain visible until the catalog
   // refresh finishes. Wait for the saved name, not only the pre-existing node.
   await page.waitForFunction(({id,name})=>document.querySelector('dialog.design-dialog[open] [data-design="'+id+'"] strong')?.textContent===name,{id:entry.id,name},{timeout:10000});
   const visible=await card.waitFor({state:'visible',timeout:10000}).then(()=>true,()=>false);
   check(filter+' renamed personal design is visible and selected',visible&&await card.getAttribute('aria-pressed')==='true'&&await card.locator('strong').textContent()===name,{name,id:entry.id},true);
   const savedState={search:await d.locator('input[type="search"]').inputValue(),category:await d.locator('[data-design-category][aria-pressed="true"]').getAttribute('data-design-category'),variant:await d.locator('[data-design-variant]').inputValue()};
   check(filter+' saved design resets incompatible filters and preserves its quiet variant',savedState.search===''&&savedState.category==='personal'&&savedState.variant==='quiet',savedState);
   check(filter+' saving personal design preserves the open report and revision',await page.evaluate(before=>JSON.stringify(S.data)===before.data&&projectStore.etag===before.etag,before));
   await d.locator('.design-preview iframe').waitFor();await page.screenshot({path:path.join(out,'saved-personal-'+filter+'.png')});await closeAll();
 }
 // Async personal previews: delayed old responses cannot overwrite newer selection.
 const personal=await page.evaluate(async()=>{
   let r=await requireOk(await appFetch('/api/design-library'));const cat=await r.json();let etag=r.headers.get('ETag');const p=cat.profiles.find(x=>x.id==='enterprise-control-review')||cat.profiles[0],ids=[];
   for(const [name,accent] of [['Synthetic preview A','#125a9c'],['Synthetic preview B','#9c3412']]){r=await requireOk(await appFetch('/api/design-library/personal',{method:'POST',headers:{'Content-Type':'application/json','If-Match':etag},body:JSON.stringify({name,design:{...p.design,accent},sections:p.sections})}));etag=r.headers.get('ETag');ids.push((await r.json()).id);}
   return ids;
 });
 results.syntheticPreviewFixtureIds=personal;
 let gate=null,delayedSeen=false;
 const latePreview=async route=>{const body=route.request().postDataJSON(),response=await route.fetch();const html=await response.text();if(body.id===personal[0]&&gate){delayedSeen=true;await gate.promise;}
   await route.fulfill({response,body:html.replace('</head>','<meta name="qa-preview-id" content="'+body.id+'"></head>')});};
 await page.route('**/api/design-library/preview',latePreview);
 for(const transition of ['select-b','search','category']){
   await openNew();await d.locator('input[type="search"]').fill('');await selectCategory('personal');let release;gate={promise:new Promise(r=>release=r)};delayedSeen=false;
   await d.locator('[data-design="'+personal[0]+'"]').click();for(let n=0;n<100&&!delayedSeen;n++)await new Promise(r=>setTimeout(r,20));check('Delayed preview starts for '+transition,delayedSeen,undefined,true);
   if(transition==='select-b'){await d.locator('[data-design="'+personal[1]+'"]').click();await page.waitForFunction(id=>document.querySelector('.design-preview iframe')?.srcdoc.includes('content="'+id+'"'),personal[1]);}
   else if(transition==='search')await d.locator('input[type="search"]').fill('NO-MATCH-DELAYED-881');
   else await selectCategory('general');
   const finished=page.waitForResponse(r=>r.url().endsWith('/api/design-library/preview')&&r.request().postDataJSON()?.id===personal[0]);release();await finished;gate=null;
   await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
   check('Late preview A cannot replace current '+transition,transition==='select-b'?await page.locator('.design-preview iframe').evaluate((f,id)=>f.srcdoc.includes('content="'+id+'"'),personal[1]):await d.locator('.design-preview iframe').count()===0);
   await closeAll();
 }
 await page.unroute('**/api/design-library/preview',latePreview);

 check('No runtime errors',results.errors.length===0,results.errors);
 check('No external requests',results.external.length===0,results.external);
 results.sourceEnd=sourceHashes();check('Product source stayed fixed during this acceptance run',JSON.stringify(results.sourceStart)===JSON.stringify(results.sourceEnd));
 results.completed=new Date().toISOString();results.passed=results.checks.every(c=>c.passed);if(!results.passed)process.exitCode=1;save();
}catch(e){results.error=String(e.stack||e);save();if(page)await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});process.exitCode=1;}
finally{clearTimeout(timer);await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})();
