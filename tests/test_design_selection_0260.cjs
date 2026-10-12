/* First design selection, same-page comparison and preservation of saved/draft content. */
'use strict';
const {apiResponseHeaders}=require('./browser-api-headers.cjs');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const root=path.resolve(__dirname,'..'),args=process.argv.slice(2),outputIndex=args.indexOf('--output'),out=path.resolve(outputIndex>=0?args[outputIndex+1]:'out/design-selection-0260');
const {chromium}=require('playwright');fs.mkdirSync(out,{recursive:true});
const result={checks:[],errors:[],external:[]},save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(result,null,2));
function check(name,value){result.checks.push({name,passed:!!value});save();assert.ok(value,name);console.log('PASS '+name);}
let browser,page,server,base;
async function ready(){await page.waitForFunction(()=>S.slug&&!projectStore.loading&&projectBusyCount===0);}
async function saved(){await page.waitForFunction(()=>!projectStore.dirty&&!projectStore.saving&&!projectStore.lastError);}
async function newProject(){await page.evaluate(()=>document.getElementById('studioMore').open=true);await page.locator('#newProjectBtn').click();await page.locator('dialog[data-design-mode=create] .experience-actions .primary').click();await page.locator('#newModal').waitFor({state:'visible'});}
async function gallery(){await page.evaluate(()=>DesignLibraryUI.gallery(document.getElementById('designLibraryBtn')));return page.locator('dialog.design-dialog');}
(async()=>{
 server=spawn(process.env.RG_PYTHON||'python',[path.join(root,'scripts/browser-server-0212.py')],{cwd:root,env:process.env,stdio:['ignore','pipe','pipe']});server.stderr.pipe(fs.createWriteStream(path.join(out,'server.log')));
 base=(await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Server timeout')),30000);server.stdout.on('data',chunk=>{text+=chunk;for(const line of text.split('\n'))try{const data=JSON.parse(line);if(data.url){clearTimeout(timer);resolve(data);}}catch{}});server.once('exit',code=>reject(Error('Server exited '+code)));})).url;
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']});
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce'});await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){result.external.push(url);return route.abort();}return route.continue();});
 const apiHeaders=await apiResponseHeaders(context,base);
 page=await context.newPage();page.on('pageerror',error=>result.errors.push(String(error)));await page.goto(base);await page.locator('#splash').waitFor({state:'hidden'});
 let gal=await gallery();
 check('No-project gallery recommends Serious first without creating a project',await gal.locator('[data-design="serio"]').getAttribute('aria-pressed')==='true'&&await gal.locator('.design-card').first().getAttribute('data-design')==='serio'&&await page.evaluate(()=>!S.slug));
 check('Specialized catalog starts collapsed while six general designs are available',!await gal.locator('[data-design-catalog]').evaluate(e=>e.open)&&await gal.locator('.design-card').count()===6);
 await gal.locator('[data-design-compare-page]').selectOption('technical');
 check('All six thumbnails compare the same technical page',await gal.locator('.design-card img').evaluateAll(images=>images.length===6&&images.every(image=>image.src.endsWith('brand-technical.webp'))));
 await gal.locator('[data-design="corporativo"]').click();
 check('Selecting another appearance retains comparison page and keyboard focus',await gal.locator('.design-preview img').getAttribute('src').then(src=>src.endsWith('brand-technical.webp'))&&await gal.locator('[data-design="corporativo"]').evaluate(e=>e===document.activeElement));
 await gal.locator('[data-design-sample-language]').selectOption('en');
 check('Comparison uses English sample assets consistently',await gal.locator('.design-card img').evaluateAll(images=>images.every(image=>image.src.includes('/en/')))&&await gal.locator('.design-preview img').getAttribute('src').then(src=>src.includes('/en/')));
 for(const width of [320,390,768,1440]){await page.setViewportSize({width,height:1000});check('Gallery fits viewport '+width,await gal.evaluate(e=>e.scrollWidth<=e.clientWidth+1&&document.documentElement.scrollWidth<=innerWidth+1));}
 await page.setViewportSize({width:390,height:844});await gal.screenshot({path:path.join(out,'gallery-mobile.png')});await page.setViewportSize({width:1440,height:1000});await gal.screenshot({path:path.join(out,'gallery-desktop.png')});
 await page.keyboard.press('Escape');await gal.waitFor({state:'hidden'});
 await newProject();
 check('New project retains Base default with optional profiles collapsed and selected summary visible',await page.locator('#mPreset').inputValue()==='base'&&!await page.locator('#mPresetOptions').evaluate(e=>e.open)&&await page.locator('#mPresetSelected').innerText().then(text=>text.includes('Base')));
 await page.locator('#mPresetOptions>summary').focus();await page.keyboard.press('Space');
 check('Native specialized disclosure opens from the keyboard',await page.locator('#mPresetOptions').evaluate(e=>e.open));
 const presetCount=await page.locator('#mPreset option').count();check('All original preset choices remain selectable',presetCount>3);
 await page.locator('#mPreset').selectOption('client');await page.locator('#mPresetOptions>summary').click();
 check('Selected optional profile remains visible when its controls close',await page.locator('#mPresetSelected').innerText().then(text=>text.includes('cliente')));
 await page.locator('#mCancel').click();await newProject();check('Cancelled creation preserves the chosen structure',await page.locator('#mPreset').inputValue()==='client');await page.locator('#mPresetOptions>summary').click();await page.locator('#mPreset').selectOption('base');await page.locator('#mPresetOptions>summary').click();await page.locator('#mTitle').fill('Design selection acceptance');await page.locator('#mSlug').fill('design-selection');await page.locator('#mCreate').click();await ready();
 check('Recommended route preserves original Base preset and report defaults',await page.evaluate(()=>S.data.meta.theme==='serio'&&S.data.meta.lang==='es'));
 await page.evaluate(async()=>{S.data.meta.theme='laboratorio';S.data.findings=[{id:'F001',uid:WorkflowUI.uid(),mode:'vuln',title:'Preserve existing finding',severity:'low',description_md:'Synthetic existing content',impact_md:'Synthetic impact',remediation_md:'Synthetic remediation',status:'open',evidence_uids:[],asset_uids:[]}];scheduleSave();await doSave();});await saved();
 const before=await page.evaluate(()=>({data:JSON.stringify(S.data),etag:projectStore.etag,revision:projectStore.revision}));gal=await gallery();
 check('Existing appearance stays selected instead of being replaced by recommendation',await gal.locator('[data-design="laboratorio"]').getAttribute('aria-pressed')==='true'&&await gal.locator('[data-design-current]').innerText().then(text=>text.includes('Laboratorio')));
 await gal.locator('[data-design-catalog]>summary').click();await gal.locator('[data-family="OffSec"]').click();await gal.locator('[data-design="offsec-oscp"]').click();await gal.locator('[data-design-variant]').selectOption('quiet');
 check('Specialized variant selection preserves keyboard focus',await gal.locator('[data-design-variant]').evaluate(e=>e===document.activeElement));
 check('Browsing appearances never writes project content or revisions',await page.evaluate(value=>JSON.stringify(S.data)===value.data&&projectStore.etag===value.etag&&projectStore.revision===value.revision,before));
 await gal.getByRole('button',{name:'Aplicar apariencia',exact:true}).click();await ready();await gal.waitFor({state:'hidden'});
 check('Explicit appearance application preserves authored findings',await page.evaluate(()=>S.data.meta.design.id==='offsec-oscp'&&S.data.meta.design.variant==='quiet'&&S.data.findings[0].title==='Preserve existing finding'));
 gal=await gallery();check('Existing specialized design opens its family and selected variant',await gal.locator('[data-design-catalog]').evaluate(e=>e.open)&&await gal.locator('[data-design="offsec-oscp"]').getAttribute('aria-pressed')==='true'&&await gal.locator('[data-design-variant]').inputValue()==='quiet');await page.keyboard.press('Escape');
 // A rejected pending save must not create a new project or discard the local draft.
 let created=0;const countCreate=request=>{if(request.url()===base+'/api/projects'&&request.method()==='POST')created++;};page.on('request',countCreate);
 await context.route(base+'/api/projects/design-selection',route=>route.request().method()==='PUT'?route.fulfill({headers:apiHeaders,status:503,contentType:'application/json',body:JSON.stringify({error:'Synthetic pending save failure'})}):route.continue());
 await page.evaluate(()=>{S.data.meta.report_title='Pending draft remains';scheduleSave();});await newProject();await page.locator('#mTitle').fill('Must not create while save fails');await page.locator('#mCreate').click();await page.waitForFunction(()=>!creatingProject);
 check('Creation waits for a successful save, preserves the draft and explains failure inside the modal',created===0&&await page.evaluate(()=>S.slug==='design-selection'&&S.data.meta.report_title==='Pending draft remains'&&projectStore.dirty)&&await page.locator('#newModal').evaluate(e=>e.open)&&await page.locator('#newModal [role="alert"]').isVisible());
 await page.locator('#mCancel').click();await context.unroute(base+'/api/projects/design-selection');page.off('request',countCreate);await page.evaluate(()=>doSave());await saved();
 await page.evaluate(()=>setUiLang('en'));await newProject();
 check('New-project recommendation and gallery entry localize to English',await page.locator('#mPresetSelected').innerText().then(text=>text.includes('Recommended starting point'))&&await page.locator('#newProjectLibrary button').innerText()==='Back to gallery');
 await page.locator('#newProjectLibrary button').click();gal=page.locator('dialog.design-dialog');await gal.waitFor({state:'visible'});check('Opening gallery releases the old modal instead of stacking it',!await page.locator('#newModal').evaluate(e=>e.open));await gal.getByRole('button',{name:'Close',exact:true}).click();await page.waitForFunction(()=>document.activeElement.id==='newProjectBtn');
 check('Gallery returns focus to the reachable original new-project opener',await page.locator('#newProjectBtn').evaluate(e=>e===document.activeElement));
 check('No JavaScript errors or external requests',!result.errors.length&&!result.external.length);
})().catch(async error=>{result.error=error.stack;console.error(error);try{await page?.screenshot({path:path.join(out,'failure.png')});}catch{}process.exitCode=1;}).finally(async()=>{await browser?.close();server?.kill('SIGTERM');save();});
