/* Independent native acceptance of bundled knowledge, contextual help and work packs. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {isDeepStrictEqual}=require('node:util'),{spawn}=require('node:child_process');
const {apiResponseHeaders}=require('./browser-api-headers.cjs');
const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'));
const args=process.argv.slice(2),out=path.resolve(args.includes('--output')?args[args.indexOf('--output')+1]:'out/knowledge-0440');
const {chromium}=require(require.resolve('playwright',{paths:[root]}));
const axeSource=fs.readFileSync(require.resolve('axe-core/axe.min.js',{paths:[root]}),'utf8');
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-knowledge-'));
fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');fs.mkdirSync(out,{recursive:true});
const results={started:new Date().toISOString(),checks:[],errors:[],external:[],screenshots:[],accessibility:[],geometry:[],limitations:['Automated native Chromium acceptance; no claim of human usability or human screen-reader review.','All projects and client records are fictional. No security target is contacted.']};
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
function check(name,condition,detail){results.checks.push({name,passed:!!condition,...(detail===undefined?{}:{detail})});save();assert.ok(condition,name+(detail===undefined?'':': '+JSON.stringify(detail)));console.log('PASS '+name);}
const server=spawn(process.env.RG_PYTHON||'python',[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:{...process.env,PYTHONPATH:root+path.delimiter+path.join(root,'webapp')}});
server.stderr.on('data',data=>fs.appendFileSync(path.join(out,'server.log'),data));
let browser,page,base,timer;
async function settled(target){await target.waitForFunction(()=>!document.querySelector('#splash')&&typeof KnowledgeUI!=='undefined'&&!projectStore.loading&&!projectBusyCount);await target.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));}
async function reloadProject(target){const slug=await target.evaluate(()=>S.slug);await target.reload();await settled(target);if(slug&&await target.evaluate(()=>S.slug)!==slug){await target.locator('#projectSelect').selectOption(slug);await settled(target);}}
async function launch(language){
  const context=await browser.newContext({viewport:{width:1366,height:1000},reducedMotion:'reduce'});
  await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){results.external.push(url);return route.abort();}return route.continue();});
  await context.addInitScript({content:axeSource});
  await context.addInitScript(language=>{localStorage.setItem('rg.uiLang',language);localStorage.setItem('rg.previewVisible','0');},language);
  const target=await context.newPage();target.on('pageerror',error=>results.errors.push(String(error)));await target.goto(base);await settled(target);
  if(await target.locator('[data-onboarding-choice="complete"]').count())await target.locator('[data-onboarding-choice="complete"]').click();
  return {context,page:target};
}
const snapshot=target=>target.evaluate(()=>({slug:S.slug,data:S.data,revision:projectStore.revision,etag:projectStore.etag,dirty:projectStore.dirty}));
async function capture(target,label){const file=path.join(out,label+'.png');await target.screenshot({path:file});results.screenshots.push(file);save();}
async function closeDialogs(target){for(let n=0;n<6&&await target.locator('dialog[open]').count();n++)await target.keyboard.press('Escape');}
async function catalogReady(target){await target.locator('[data-knowledge-entry]').first().waitFor();await target.waitForFunction(()=>!document.querySelector('.knowledge-list[aria-busy]'));}
async function openEntry(target,id='RG-AI-001'){await target.locator('#knowledgeSearch').fill(id);await target.waitForFunction(id=>document.querySelectorAll('[data-knowledge-entry]').length===1&&document.querySelector('[data-knowledge-entry]')?.dataset.knowledgeEntry===id,id);await target.locator('[data-knowledge-entry="'+id+'"] [data-knowledge-action="detail"]').click();await target.locator('[data-knowledge-detail="'+id+'"] [data-knowledge-action="insert"]').waitFor();}
async function accessibility(target,label,selector){const report=await target.evaluate(async selector=>axe.run({include:[selector]},{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}),selector);results.accessibility.push({label,incomplete:report.incomplete.map(row=>row.id)});check(label+' has no automatic accessibility violations',!report.violations.length,report.violations.map(row=>({id:row.id,targets:row.nodes.map(node=>node.target)})));}
async function geometry(target,label,selector){
  const data=await target.locator(selector).evaluate(node=>{const r=node.getBoundingClientRect();return {left:r.left,right:r.right,client:node.clientWidth,scroll:node.scrollWidth,root:document.documentElement.scrollWidth,viewport:innerWidth,controls:[...node.querySelectorAll('button,input,select,summary')].filter(value=>value.getClientRects().length&&getComputedStyle(value).visibility!=='hidden'&&!['checkbox','radio'].includes(value.type)).map(value=>{const box=value.getBoundingClientRect();return {name:value.id||value.dataset.knowledgeAction||value.textContent.trim(),height:box.height,left:box.left,right:box.right};})};});
  const minimum=data.viewport<=760?44:40;results.geometry.push({label,minimum,...data});
  check(label+' fits the viewport without horizontal clipping',data.scroll<=data.client+1&&data.root<=data.viewport+1&&data.left>=-1&&data.right<=data.viewport+1,data);
  check(label+' controls meet the desktop/mobile target size',data.controls.length>0&&data.controls.every(control=>control.height>=minimum),data.controls);
  check(label+' controls stay inside the dialog horizontally',data.controls.every(control=>control.left>=data.left-1&&control.right<=data.right+1),data.controls);
  const headings=await target.locator(selector+' .knowledge-heading').evaluateAll(nodes=>nodes.map(node=>{const title=node.querySelector('h3').getBoundingClientRect(),button=node.querySelector('button'),close=button.getBoundingClientRect();return {title:{left:title.left,right:title.right,top:title.top,bottom:title.bottom},close:{left:close.left,right:close.right,top:close.top,bottom:close.bottom},buttonClient:button.clientWidth,buttonScroll:button.scrollWidth};}));
  if(headings.length)check(label+' title and complete close label do not overlap',headings.every(row=>(row.title.right<=row.close.left+1||row.close.right<=row.title.left+1||row.title.bottom<=row.close.top+1||row.close.bottom<=row.title.top+1)&&row.buttonScroll<=row.buttonClient+1),headings);
  const choices=await target.locator(selector+' .work-package-choice').evaluateAll(nodes=>nodes.map(node=>{const row=node.getBoundingClientRect(),box=node.querySelector('input').getBoundingClientRect(),text=node.querySelector('span').getBoundingClientRect();return {rowWidth:row.width,rowHeight:row.height,boxWidth:box.width,textWidth:text.width,boxRight:box.right,textLeft:text.left,textRight:text.right,rowRight:row.right};}));
  if(choices.length)check(label+' package choices retain readable text beside bounded checkboxes',choices.every(row=>row.rowHeight>=44&&row.boxWidth>=12&&row.boxWidth<=44&&row.textWidth>=row.rowWidth*0.65&&row.textLeft>=row.boxRight&&row.textRight<=row.rowRight+1),choices);
}
async function createFixture(target,uiLang,reportLang){await target.evaluate(async({uiLang,reportLang})=>{const slug='knowledge-customer-'+uiLang;await requireOk(await api.post('/api/projects',{slug,title:'VEGA fictional customer '+uiLang,client:'VEGA [FICTIONAL]'}));await refreshProjects();await loadProject(slug);S.data.meta.lang=reportLang;S.data.findings=[{uid:crypto.randomUUID(),id:'F1',mode:'vuln',title:'Original fictional observation',description_md:'Original client draft must remain intact.',impact_md:'Assessment pending.',remediation_md:'Review the actual condition.',verification:'unverified',status:'open',walkthrough:[]}];S.data.finding_sequence=1;scheduleSave();if(!await doSave())throw Error('Could not save fixture');},{uiLang,reportLang});await settled(target);}
(async()=>{try{
  base=await new Promise((resolve,reject)=>{let buffer='';timer=setTimeout(()=>reject(Error('Server timeout')),30000);server.stdout.on('data',data=>{buffer+=data;for(const line of buffer.split('\n'))try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});server.on('exit',code=>reject(Error('Server exited '+code)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined});results.browser=browser.version();
  for(const [uiLang,reportLang] of [['es','en'],['en','pt'],['pt','es']]){
    const visit=await launch(uiLang);page=visit.page;await createFixture(page,uiLang,reportLang);
    const original=await snapshot(page),writes=[];page.on('request',request=>{if(!['GET','HEAD'].includes(request.method()))writes.push({method:request.method(),url:request.url()});});
    await page.locator('#workspaceFindings').click();
    await page.locator('#contextIndex').waitFor({state:'visible'});
    if(!await page.locator('#contextIndexActions').evaluate(node=>node.open))await page.locator('#contextIndexActions>summary').click();
    await page.locator('#libBtn').click();await page.locator('[data-library-tab="personal"]').waitFor();
    check(uiLang+' existing personal library remains the initial tab',await page.locator('[data-library-tab="personal"]').getAttribute('aria-selected')==='true'&&await page.locator('[data-knowledge-catalog]').count()===0);
    await page.locator('[data-library-tab="personal"]').focus();await page.keyboard.press('ArrowRight');await catalogReady(page);
    check(uiLang+' catalog tab works by keyboard and defaults to the different report language',await page.locator('[data-library-tab="curated"]').getAttribute('aria-selected')==='true'&&await page.locator('#knowledgeLanguage').inputValue()===reportLang);
    check(uiLang+' all ninety bundled entries are reachable',await page.locator('.knowledge-status').innerText().then(text=>text.includes('90')));
    check(uiLang+' initial page is bounded to twelve cards with a next page',await page.locator('[data-knowledge-entry]').count()===12&&await page.locator('[data-knowledge-action="next"]').isEnabled());
    await page.locator('#knowledgeCategory').selectOption('ai');await catalogReady(page);
    check(uiLang+' AI category contains thirty entries',await page.locator('.knowledge-status').innerText().then(text=>text.includes('30'))&&await page.locator('[data-knowledge-entry]').evaluateAll(nodes=>nodes.every(node=>node.dataset.knowledgeEntry.startsWith('RG-AI-'))));
    const firstPage=await page.locator('[data-knowledge-entry]').evaluateAll(nodes=>nodes.map(node=>node.dataset.knowledgeEntry));await page.locator('[data-knowledge-action="next"]').click();await catalogReady(page);
    check(uiLang+' pagination advances without repeating first-page entries',await page.locator('[data-knowledge-entry]').evaluateAll((nodes,first)=>nodes.every(node=>!first.includes(node.dataset.knowledgeEntry)),firstPage));
    await page.locator('#knowledgeSearch').fill('no-match-VEGA-knowledge-zzzz');await page.waitForFunction(()=>!document.querySelector('.knowledge-list[aria-busy]')&&!document.querySelector('[data-knowledge-entry]'));
    check(uiLang+' no-match search leaves a readable status and disabled pagination',!!await page.locator('.knowledge-status').innerText()&&await page.locator('[data-knowledge-action="next"]').isDisabled());
    await openEntry(page);
    const expected=await page.evaluate(reportLang=>api.get('/api/knowledge/RG-AI-001?lang='+reportLang),reportLang),detail=page.locator('[data-knowledge-detail="RG-AI-001"]');
    check(uiLang+' detail displays all eight guidance sections in the selected entry language',await detail.locator('[data-knowledge-section]').count()===8&&(await detail.innerText()).includes(expected.title)&&(await detail.innerText()).includes(expected.false_positives));
    check(uiLang+' references retain real source versions and review date',await detail.locator('a[href^="https://"]').count()>0&&(await detail.innerText()).includes(expected.reviewed_on));
    check(uiLang+' browsing and reading guidance do not modify the open project',isDeepStrictEqual(await snapshot(page),original)&&writes.length===0,writes);
    const libraryBefore=await page.evaluate(()=>api.get('/api/library'));
    await detail.locator('[data-knowledge-action="copy"]').click();await page.waitForFunction(count=>document.querySelector('[data-knowledge-detail] [data-knowledge-action="copy"]')?.disabled&&document.querySelector('[data-knowledge-detail] .knowledge-status')?.textContent.length>20,libraryBefore.templates.length);
    const libraryAfter=await page.evaluate(()=>api.get('/api/library'));
    check(uiLang+' personal copy preserves all existing templates and creates one editable unrated entry',libraryAfter.templates.length===libraryBefore.templates.length+1&&isDeepStrictEqual(libraryAfter.templates.slice(0,-1),libraryBefore.templates)&&libraryAfter.templates.at(-1).name===expected.title&&libraryAfter.templates.at(-1).content.severity==null&&libraryAfter.templates.at(-1).versions.length===1);
    check(uiLang+' personal copy leaves the current project and bundled content unchanged',isDeepStrictEqual(await snapshot(page),original)&&isDeepStrictEqual(await page.evaluate(reportLang=>api.get('/api/knowledge/RG-AI-001?lang='+reportLang),reportLang),expected));
    await detail.locator('[data-knowledge-action="insert"]').click();await page.locator('[data-knowledge-insert]').waitFor();
    check(uiLang+' insertion defaults to report language without changing UI language',await page.locator('#knowledgeInsertLanguage').inputValue()===reportLang&&await page.evaluate(uiLang=>S.uiLang===uiLang,uiLang));
    await page.locator('[data-knowledge-action="confirm-insert"]').click();
    check(uiLang+' empty target validation creates no finding',await page.evaluate(()=>S.data.findings.length===1)&&await page.locator('#knowledgeTarget').evaluate(node=>document.activeElement===node));
    const target='https://ai.vega.example/recovery-'+uiLang;await page.locator('#knowledgeTarget').fill(target);
    await page.waitForFunction(()=>{const h=PendingUI.active.get(S.slug+'|knowledge:insert:RG-AI-001');return h?.revision&&h.persisted===h.revision;});
    await closeDialogs(page);await reloadProject(page);
    await page.locator('[data-pending-record]').waitFor();
    await page.locator('[data-pending-record]').getByRole('button',{name:{es:'Recuperar formulario',en:'Recover form',pt:'Recuperar formulário'}[uiLang],exact:true}).click();
    await page.locator('[data-knowledge-insert]').waitFor();
    check(uiLang+' explicit recovery restores the uncommitted target and language after reload',await page.locator('#knowledgeTarget').inputValue()===target&&await page.locator('#knowledgeInsertLanguage').inputValue()===reportLang&&await page.evaluate(()=>S.data.findings.length===1));
    await page.locator('[data-knowledge-action="confirm-insert"]').click();await page.waitForFunction(()=>S.data.findings.length===2&&!projectBusyCount);
    const inserted=await page.evaluate(()=>S.data.findings.at(-1));
    check(uiLang+' explicit insertion creates one unverified draft without scores, evidence or retest',inserted.title===expected.title&&inserted.verification==='unverified'&&inserted.severity==null&&inserted.cvss==null&&!inserted.cvss_vector&&!inserted.evidence_uids?.length&&!inserted.retests?.length&&inserted.affected===target&&!inserted.description_md.includes('{{objetivo}}'));
    check(uiLang+' insertion preserves the first finding and report language',isDeepStrictEqual(await page.evaluate(()=>S.data.findings[0]),original.data.findings[0])&&await page.evaluate(reportLang=>S.data.meta.lang===reportLang,reportLang));
    await reloadProject(page);check(uiLang+' inserted draft survives reload exactly once',await page.evaluate(uid=>S.data.findings.filter(finding=>finding.uid===uid).length===1,inserted.uid));
    // Native DOM/focus and save-conflict checks use the real editor with a rejected PUT.
    await page.evaluate(()=>select('finding',0));await settled(page);
    const field=page.locator('[data-field="description_md"]').first(),retained=await field.elementHandle();await field.waitFor({state:'visible'});
    const slug=await page.evaluate(()=>S.slug),projectURL=base+'/api/projects/'+encodeURIComponent(slug),headers=await apiResponseHeaders(visit.context,base);
    const rejectSave=route=>route.request().method()==='PUT'?route.fulfill({status:409,headers,contentType:'application/json',body:JSON.stringify({error:'Synthetic draft save conflict'})}):route.continue();await page.route(projectURL,rejectSave);writes.length=0;
    const draft='VEGA pending original description '+uiLang;await field.fill(draft);await field.evaluate(node=>node.setSelectionRange(2,9));
    for(const key of ['description_md','impact_md','severity','remediation_md','evidence','closure_criteria_md']){
      const help=page.locator('[data-help="'+key+'"]').first();await help.locator('summary').click();check(uiLang+' '+key+' explains writing without changing technical states',(await help.innerText()).length>180&&await page.evaluate(()=>S.data.findings.every(row=>row.verification==='unverified'&&!row.retests?.length)));await help.locator('summary').focus();await page.keyboard.press('Escape');check(uiLang+' '+key+' help closes with Escape and retains keyboard focus',!await help.evaluate(node=>node.open)&&await help.locator('summary').evaluate(node=>node===document.activeElement));
    }
    check(uiLang+' contextual guidance preserves the exact dirty field DOM and selection',await page.evaluate(({node,draft})=>document.querySelector('[data-field="description_md"]')===node&&node.value===draft&&node.selectionStart===2&&node.selectionEnd===9&&projectStore.dirty,{node:retained,draft}));await retained.dispose();
    await page.evaluate(()=>KnowledgeUI.open({category:'ai'}));await catalogReady(page);await openEntry(page,'RG-AI-002');await page.locator('[data-knowledge-detail] [data-knowledge-action="insert"]').click();await page.locator('#knowledgeTarget').fill('https://ai.vega.example/conflict');await page.locator('[data-knowledge-action="confirm-insert"]').click();await page.waitForFunction(()=>!!projectStore.lastError&&!projectBusyCount);
    check(uiLang+' a 409 on the open draft blocks catalog insertion and retains both forms',await page.evaluate(draft=>S.data.findings.length===2&&S.data.findings[0].description_md===draft&&projectStore.dirty,draft)&&await page.locator('#knowledgeTarget').inputValue()==='https://ai.vega.example/conflict'&&!writes.some(row=>row.url.includes('/knowledge/RG-AI-002')));
    await page.unroute(projectURL,rejectSave);await page.locator('[data-knowledge-action="confirm-insert"]').click();await page.waitForFunction(()=>S.data.findings.length===3&&!projectBusyCount);await closeDialogs(page);
    check(uiLang+' resolving the save conflict preserves the draft and inserts one entry',await page.evaluate(draft=>S.data.findings[0].description_md===draft&&S.data.findings.length===3,draft));
    for(const [key,type,selection] of [['scope','section','scope'],['limitations_md','workflow','coverage']]){
      await page.evaluate(({type,selection})=>select(type,selection),{type,selection});await page.locator('[data-help="'+key+'"]').waitFor();const baseline=await snapshot(page),help=page.locator('[data-help="'+key+'"]');await help.locator('summary').click();
      check(uiLang+' '+key+' guidance is translated, optional and read-only',(await help.innerText()).length>180&&isDeepStrictEqual(await snapshot(page),baseline));await accessibility(page,uiLang+' '+key+' help','[data-help="'+key+'"]');
    }
    await page.evaluate(()=>KnowledgeUI.open({category:'ai'}));await catalogReady(page);
    for(const sample of [{width:1440,zoom:100,theme:'dark'},{width:1366,zoom:100,theme:'dark'},{width:390,zoom:100,theme:'light'},{width:320,zoom:200,theme:'dark'}]){
      await page.setViewportSize({width:sample.width,height:1000});await page.evaluate(sample=>{document.documentElement.style.fontSize=sample.zoom+'%';applyUiTheme(sample.theme);},sample);
      const label=uiLang+'-'+sample.width+'-'+sample.zoom+'-'+sample.theme;
      await geometry(page,label+' catalog','dialog[open]');await accessibility(page,label+' catalog','[data-knowledge-catalog]');await capture(page,label+'-catalog');
      await openEntry(page);await geometry(page,label+' detail','[data-knowledge-detail]');await accessibility(page,label+' detail','[data-knowledge-detail]');await capture(page,label+'-detail');
      await page.locator('[data-knowledge-detail] [data-knowledge-action="close"]').click();await page.locator('#knowledgeSearch').fill('');await catalogReady(page);
      await page.locator('[data-knowledge-action="packs"]').click();await page.locator('[data-work-package="ai"]').click();
      await geometry(page,label+' AI package','[data-work-packages-dialog]');await accessibility(page,label+' AI package','[data-work-packages-dialog]');await capture(page,label+'-ai-package');
      await page.locator('.work-package-choice').first().scrollIntoViewIfNeeded();await capture(page,label+'-ai-package-choices');
      await page.keyboard.press('Escape');await page.locator('[data-work-packages-dialog]').waitFor({state:'detached'});
    }
    await closeDialogs(page);await page.setViewportSize({width:1366,height:1000});await page.evaluate(()=>{document.documentElement.style.fontSize='100%';applyUiTheme('dark');});
    const beforePackages=await snapshot(page);
    await page.evaluate(()=>WorkPackagesUI.openExample());await page.locator('[data-report-lesson]').first().waitFor();
    check(uiLang+' annotated report provides nine optional lessons',await page.locator('[data-report-lesson]').count()===9);
    for(const lesson of await page.locator('[data-report-lesson]').all())await lesson.locator('summary').click();
    check(uiLang+' reading every annotated lesson leaves the current report unchanged',isDeepStrictEqual(await snapshot(page),beforePackages));
    await accessibility(page,uiLang+' annotated report','[data-annotated-example-dialog]');await capture(page,uiLang+'-annotated-report');await closeDialogs(page);
    await page.evaluate(()=>WorkPackagesUI.open());await page.locator('[data-work-package="ai"]').click();
    check(uiLang+' AI work package does not preselect vulnerability drafts',await page.locator('[data-package-entry]').count()===30&&await page.locator('[data-package-entry]:checked').count()===0);
    await page.locator('[data-package-title]').fill('VEGA AI plan '+uiLang);await page.locator('[data-package-client]').fill('VEGA [FICTIONAL]');
    await accessibility(page,uiLang+' AI package preparation','[data-work-packages-dialog]');await page.locator('[data-package-create]').click();await page.waitForFunction(slug=>S.slug!==slug&&!projectBusyCount,beforePackages.slug);
    check(uiLang+' creating the default AI pack makes a separate project with thirty pending tests and no findings',await page.evaluate(uiLang=>S.data.meta.lang===uiLang&&S.data.findings.length===0&&S.data.test_cases.length===30&&S.data.test_cases.every(row=>row.status==='pending'&&!row.observed&&!row.evidence_uids?.length),uiLang));
    check(uiLang+' creating a package preserves the source project exactly',isDeepStrictEqual(await page.evaluate(slug=>api.get('/api/projects/'+encodeURIComponent(slug)),beforePackages.slug),beforePackages.data));
    const emptyPackSlug=await page.evaluate(()=>S.slug);await page.evaluate(()=>WorkPackagesUI.open());await page.locator('[data-work-package="ai"]').click();await page.locator('[data-package-entry="RG-AI-001"]').check();await page.locator('[data-package-create]').click();await page.waitForFunction(slug=>S.slug!==slug&&!projectBusyCount,emptyPackSlug);
    check(uiLang+' an explicitly selected package entry creates exactly one unverified unrated finding',await page.evaluate(()=>S.data.findings.length===1&&S.data.findings[0].verification==='unverified'&&S.data.findings[0].severity==null&&S.data.findings[0].cvss==null&&!S.data.findings[0].evidence_uids?.length&&S.data.test_cases.length===30&&S.data.test_cases.every(row=>row.status==='pending')));
    await reloadProject(page);check(uiLang+' work package and pending states survive reload',await page.evaluate(()=>S.data.findings.length===1&&S.data.test_cases.length===30&&S.data.findings[0].verification==='unverified'));
    check(uiLang+' no duplicate DOM IDs remain after catalog/dialog use',await page.locator('[id]').evaluateAll(nodes=>new Set(nodes.map(node=>node.id)).size===nodes.length));
    await visit.context.close();
  }
  check('Knowledge UI makes no external network requests',results.external.length===0,results.external);check('Knowledge UI raises no browser runtime errors',results.errors.length===0,results.errors);results.status='passed';
}catch(error){results.status='failed';results.error=String(error.stack||error);if(page&&!page.isClosed())await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});throw error;}
finally{clearTimeout(timer);results.finished=new Date().toISOString();save();await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{console.error(error);process.exitCode=1;});
