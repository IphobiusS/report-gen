/* Native onboarding acceptance, against a disposable fictional Flask workspace. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {isDeepStrictEqual}=require('node:util');
const {spawn}=require('node:child_process');
const {apiResponseHeaders}=require('./browser-api-headers.cjs');
const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'));
const args=process.argv.slice(2),out=path.resolve(args.includes('--output')?args[args.indexOf('--output')+1]:'out/onboarding-0430');
const {chromium}=require(require.resolve('playwright',{paths:[root]}));
const axeSource=fs.readFileSync(require.resolve('axe-core/axe.min.js',{paths:[root]}),'utf8');
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-onboarding-'));
fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
fs.mkdirSync(out,{recursive:true});
const results={started:new Date().toISOString(),checks:[],errors:[],external:[],screenshots:[],accessibility:[],sidebarTargets:[],limitations:['Automated Chromium acceptance does not replace human usability sessions or a human screen reader.','Every project used in this harness is fictional and disposable.']};
const save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
function check(name,condition,detail){results.checks.push({name,passed:!!condition,...(detail===undefined?{}:{detail})});save();assert.ok(condition,name+(detail===undefined?'':': '+JSON.stringify(detail)));console.log('PASS '+name);}
const server=spawn(process.env.RG_PYTHON||'python',[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:{...process.env,PYTHONPATH:root+path.delimiter+path.join(root,'webapp')}});
server.stderr.on('data',data=>fs.appendFileSync(path.join(out,'server.log'),data));
let browser,page,base,timer;
async function ready(target){await target.waitForFunction(()=>!document.querySelector('#splash')&&typeof OnboardingUI!=='undefined'&&!projectStore.loading&&!projectBusyCount);}
async function settled(target){await ready(target);await target.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));}
async function reloadProject(target){const slug=await target.evaluate(()=>S.slug);await target.reload();await settled(target);if(slug&&await target.evaluate(()=>S.slug)!==slug){await target.locator('#projectSelect').selectOption(slug);await settled(target);}}
async function launch(language='es',storage='normal'){
  const context=await browser.newContext({viewport:{width:1366,height:1000},reducedMotion:'reduce'});
  await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){results.external.push(url);return route.abort();}return route.continue();});
  await context.addInitScript({content:axeSource});
  await context.addInitScript(({language,storage})=>{
    localStorage.setItem('rg.uiLang',language);localStorage.setItem('rg.previewVisible','0');
    if(storage!=='normal'){
      const get=Storage.prototype.getItem,set=Storage.prototype.setItem;
      Storage.prototype.getItem=function(key){if(String(key).startsWith('rg.onboarding.v1')){if(storage==='blocked')throw new DOMException('Synthetic denied storage','SecurityError');if(storage==='corrupt'&&!get.call(this,key))return '{broken';}return get.call(this,key);};
      Storage.prototype.setItem=function(key,value){if(storage==='blocked'&&String(key).startsWith('rg.onboarding.v1'))throw new DOMException('Synthetic denied storage','SecurityError');return set.call(this,key,value);};
    }
  },{language,storage});
  const target=await context.newPage();target.on('pageerror',error=>results.errors.push(String(error)));
  await target.goto(base);await settled(target);return {context,page:target};
}
const snapshot=target=>target.evaluate(()=>({slug:S.slug,data:S.data,revision:projectStore.revision,etag:projectStore.etag,dirty:projectStore.dirty}));
const current=target=>target.locator('#onboardingPanel').getAttribute('data-onboarding-current');
async function accessibleControl(target,selector){
  const control=target.locator(selector).first();
  if(await target.locator('#sidebarToggle').isVisible()&&await target.locator('#sidebarToggle').getAttribute('aria-expanded')==='true'&&!await control.evaluate(node=>!!node.closest('#workspaceSidebar')))await target.locator('#sidebarToggle').click();
  if(!await control.isVisible()&&await target.locator('#sidebarToggle').isVisible())await target.locator('#sidebarToggle').click();
  await control.waitFor({state:'visible'});return control;
}
async function clickControl(target,selector){await(await accessibleControl(target,selector)).click();await settled(target);}
async function setMode(target,value){await(await accessibleControl(target,'#onboardingMode')).selectOption(value);await settled(target);}
async function ensureRoute(target){if(!await target.evaluate(()=>OnboardingUI.state().active))await clickControl(target,'#onboardingRouteBtn');await target.locator('[data-onboarding-step="0"]').waitFor({state:'visible'});}
async function routeStep(target,index){await clickControl(target,'[data-onboarding-step="'+index+'"]');check('Route selects step '+index,await current(target)===String(index));}
async function capture(target,label){const file=path.join(out,label+'.png');await target.screenshot({path:file});results.screenshots.push(file);save();}
async function accessibility(target,label,selectors){
  const result=await target.evaluate(async selectors=>axe.run({include:selectors},{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}),selectors);
  results.accessibility.push({label,incomplete:result.incomplete.map(value=>value.id)});
  check(label+' has no automatic accessibility violations',result.violations.length===0,result.violations.map(value=>({id:value.id,nodes:value.nodes.map(node=>node.target)})));
}
async function geometry(target,label,selector){
  const bounds=await target.locator(selector).evaluate(node=>{const r=node.getBoundingClientRect();return {left:r.left,right:r.right,client:node.clientWidth,scroll:node.scrollWidth,root:document.documentElement.scrollWidth,viewport:innerWidth};});
  check(label+' fits the viewport and enlarged text',bounds.scroll<=bounds.client+1&&bounds.root<=bounds.viewport+1&&bounds.left>=-1&&bounds.right<=bounds.viewport+1,bounds);
}
async function sidebarTargets(target,label){
  if(await target.locator('#sidebarToggle').isVisible()&&await target.locator('#sidebarToggle').getAttribute('aria-expanded')!=='true')await target.locator('#sidebarToggle').click();
  const geometry=await target.locator('#workspaceSidebar').evaluate(sidebar=>({
    viewport:innerWidth,
    controls:[...sidebar.querySelectorAll('button,select,summary')]
      .filter(node=>node.getClientRects().length&&getComputedStyle(node).visibility!=='hidden')
      .map(node=>{const box=node.getBoundingClientRect();return {id:node.id||node.dataset.workflow||node.tagName,tag:node.tagName,name:node.getAttribute('aria-label')||node.textContent.trim(),height:box.height,width:box.width};})
  }));
  const minimum=geometry.viewport<=760?44:40;
  results.sidebarTargets.push({label,minimum,...geometry});
  check(label+' measures all three onboarding sidebar controls',['onboardingMode','onboardingRouteBtn','onboardingHelpBtn'].every(id=>geometry.controls.some(control=>control.id===id)),geometry.controls);
  check(label+' every rendered sidebar button, select and summary is at least '+minimum+'px high',geometry.controls.every(control=>control.height>=minimum),geometry.controls);
}
(async()=>{try{
  base=await new Promise((resolve,reject)=>{let buffer='';timer=setTimeout(()=>reject(Error('Server timeout')),30000);server.stdout.on('data',data=>{buffer+=data;for(const line of buffer.split('\n'))try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});server.on('exit',code=>reject(Error('Server exited '+code)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined});results.browser=browser.version();
  for(const language of ['es','en','pt']){
    const visit=await launch(language);page=visit.page;
    const writes=[];page.on('request',request=>{if(!['GET','HEAD'].includes(request.method()))writes.push({method:request.method(),url:request.url()});});
    check(language+' first-use choice is optional and nonmodal',await page.locator('[data-onboarding-chooser]').isVisible()&&await page.locator('dialog[open]').count()===0);
    check(language+' choice describes working style without seniority labels',await page.locator('[data-onboarding-choice="guided"]').isEnabled()&&await page.locator('[data-onboarding-choice="complete"]').isEnabled()&&!/junior|júnior|senior|sênior/i.test(await page.locator('[data-onboarding-chooser]').innerText()));
    await accessibility(page,language+' initial choice',['[data-onboarding-chooser]']);
    await capture(page,language+'-01-first-use');
    const before=await snapshot(page);
    await page.locator('[data-onboarding-choice="guided"]').focus();await page.keyboard.press('Enter');await settled(page);
    check(language+' keyboard choice activates Guided with a six-step route',await page.locator('#onboardingMode').inputValue()==='guided'&&await page.locator('[data-onboarding-step]').count()===6&&await current(page)==='0');
    const navigation=await page.locator('#workspaceSidebar [id]').evaluateAll(nodes=>nodes.map(node=>node.id));
    await setMode(page,'complete');
    check(language+' Complete keeps every existing navigation control',isDeepStrictEqual(await page.locator('#workspaceSidebar [id]').evaluateAll(nodes=>nodes.map(node=>node.id)),navigation));
    await page.reload();await settled(page);
    check(language+' the saved choice survives reload without another first-use prompt',await page.locator('#onboardingMode').inputValue()==='complete'&&await page.locator('[data-onboarding-chooser]').count()===0);
    await setMode(page,'guided');
    check(language+' choosing a working style does not modify project data or revision',isDeepStrictEqual(await snapshot(page),before));
    check(language+' choosing a working style makes no modifying requests',writes.length===0,writes);
    // Fixture setup uses the normal project API, without the reserved practice prefix.
    await page.evaluate(async language=>{
      const slug='onboarding-customer-'+language;
      await requireOk(await api.post('/api/projects',{slug,title:'Fictional customer assessment '+language,client:'Fictional Example Bank'}));
      await refreshProjects();await loadProject(slug);S.data.meta.lang=language;
      S.data.findings=[{uid:crypto.randomUUID(),id:'F1',mode:'vuln',title:'Synthetic role comparison',severity:'high',description_md:'A fictional reader received another fictional account.',impact_md:'Synthetic account information exposure.',remediation_md:'Verify the resource owner.',status:'reported_fixed',verification:'unverified',walkthrough:[]},{uid:crypto.randomUUID(),id:'F2',mode:'vuln',title:'Synthetic transport setting',severity:'low',description_md:'Documented synthetic configuration.',impact_md:'Synthetic impact.',remediation_md:'Review the configuration.',status:'open',verification:'unverified',walkthrough:[]}];
      S.data.finding_sequence=2;scheduleSave();if(!await doSave())throw Error('Could not save synthetic fixture');
    },language);await settled(page);
    await ensureRoute(page);
    const baseline=await snapshot(page);writes.length=0;
    for(let index=0;index<6;index++){
      await routeStep(page,index);
      await clickControl(page,'[data-onboarding-action="open"]');
      const highlighted=page.locator('.onboarding-target');
      await page.waitForFunction(()=>{const nodes=document.querySelectorAll('.onboarding-target');return nodes.length===1&&nodes[0].matches('button,input,textarea,select,summary,a,[tabindex]')&&nodes[0].getClientRects().length>0;});
      check(language+' step '+(index+1)+' highlights an actual application control with its explanation',await highlighted.count()===1&&await highlighted.evaluate(node=>!node.closest('#onboardingPanel')&&node.matches('button,input,textarea,select,summary,a,[tabindex]')&&(node.getAttribute('aria-describedby')||'').split(/\s+/).includes('onboardingStepPurpose')));
      check(language+' step '+(index+1)+' is the only current guide step',await page.locator('[data-onboarding-step][aria-current="step"]').count()===1);
      await clickControl(page,'#onboardingHelpBtn');
      const help=page.locator('[data-onboarding-help]');await help.waitFor({state:'visible'});
      check(language+' step '+(index+1)+' explains the real current section',await help.innerText().then(text=>text.trim().length>100));
      if(index===2){await page.keyboard.press('Escape');await settled(page);check(language+' Escape closes contextual help and restores its trigger',await page.locator('[data-onboarding-help]').count()===0&&await page.locator('#onboardingHelpBtn').evaluate(node=>node===document.activeElement));}
      else await clickControl(page,'[data-onboarding-action="close-help"]');
      check(language+' step '+(index+1)+' help closes without changing the project',await page.locator('[data-onboarding-help]').count()===0&&isDeepStrictEqual(await snapshot(page),baseline));
    }
    await routeStep(page,3);await clickControl(page,'[data-onboarding-action="back"]');
    check(language+' Back returns to the previous learning step',await current(page)==='2');
    await clickControl(page,'[data-onboarding-action="next"]');await clickControl(page,'[data-onboarding-action="pause"]');
    check(language+' pausing leaves the real editor usable',await page.locator('.onboarding-target').count()===0&&await page.locator('dialog[open]').count()===0);
    await reloadProject(page);await ensureRoute(page);
    check(language+' route resumes at its saved step after reload',await current(page)==='3');
    await clickControl(page,'[data-onboarding-action="restart"]');
    check(language+' restart returns to the first learning step',await current(page)==='0');
    for(let index=0;index<6;index++)await clickControl(page,'[data-onboarding-action="next"]');
    check(language+' final reading action records completion only in learning preferences',await page.evaluate(()=>OnboardingUI.state().completed&&!OnboardingUI.state().active));
    check(language+' completing learning preserves all report, evidence and review data',isDeepStrictEqual((await snapshot(page)).data,baseline.data));
    check(language+' route, navigation, help and completion make no modifying requests',writes.length===0,writes);
    await ensureRoute(page);await clickControl(page,'[data-onboarding-action="restart"]');await routeStep(page,0);await clickControl(page,'[data-onboarding-action="open"]');
    // Work with a pending real-project draft: failing its save must not create a practice copy.
    const originalSlug=await page.evaluate(()=>S.slug),field=page.locator('[data-field="report_title"]').first();
    await field.waitFor({state:'visible'});
    const title='Preserved fictional customer draft '+language;
    const projectURL=base+'/api/projects/'+encodeURIComponent(originalSlug);
    const responseHeaders=await apiResponseHeaders(visit.context,base);
    const rejectSave=route=>route.request().method()==='PUT'?route.fulfill({status:409,headers:responseHeaders,contentType:'application/json',body:JSON.stringify({error:'Synthetic draft save conflict'})}):route.continue();
    await page.route(projectURL,rejectSave);writes.length=0;
    await field.fill(title);
    const retainedField=await field.elementHandle();await field.evaluate(node=>node.setSelectionRange(2,8));
    await setMode(page,'complete');await setMode(page,'guided');await clickControl(page,'#onboardingHelpBtn');await clickControl(page,'[data-onboarding-action="close-help"]');
    check(language+' changing view and contextual help retain the live unsaved field and selection',await page.evaluate(({node,title})=>document.querySelector('[data-field="report_title"]')===node&&node.value===title&&node.selectionStart===2&&node.selectionEnd===8&&S.data.meta.report_title===title&&projectStore.dirty,{node:retainedField,title}));
    await retainedField.dispose();await clickControl(page,'[data-onboarding-action="practice"]');
    await page.waitForFunction(()=>!!projectStore.lastError&&!projectBusyCount);
    check(language+' failed save preserves the dirty original and creates no practice project',await page.evaluate(({slug,title})=>S.slug===slug&&S.data.meta.report_title===title&&projectStore.dirty,{slug:originalSlug,title})&&!writes.some(request=>request.url.endsWith('/api/demo')),writes);
    const expectedOriginal=await page.evaluate(()=>S.data);
    await page.unroute(projectURL,rejectSave);await clickControl(page,'[data-onboarding-action="practice"]');
    await page.waitForFunction(slug=>S.slug!==slug&&!projectStore.loading&&!projectBusyCount,originalSlug);
    const firstPractice=await page.evaluate(()=>S.slug);
    check(language+' practice creates a separate fictional editable copy in the selected language',firstPractice!==originalSlug&&await page.locator('[data-practice-notice]').isVisible()&&await page.evaluate(language=>S.data.meta.lang===language,language));
    const savedOriginal=await page.evaluate(slug=>api.get('/api/projects/'+encodeURIComponent(slug)),originalSlug);
    check(language+' entering practice saves the original draft exactly',isDeepStrictEqual(savedOriginal,expectedOriginal));
    await capture(page,language+'-02-practice');
    await clickControl(page,'[data-practice-action="return"]');
    check(language+' returning from practice restores the original project and data',await page.evaluate(slug=>S.slug===slug,originalSlug)&&isDeepStrictEqual((await snapshot(page)).data,expectedOriginal));
    await ensureRoute(page);await routeStep(page,0);
    await clickControl(page,'[data-onboarding-action="practice"]');
    await page.waitForFunction(slug=>S.slug!==slug&&!projectBusyCount,originalSlug);
    check(language+' repeating practice creates a fresh copy instead of resetting prior work',await page.evaluate(slug=>S.slug!==slug,firstPractice));
    await reloadProject(page);
    check(language+' practice notice remains visible after reload',await page.locator('[data-practice-notice]').isVisible());
    // The global mode and help controls must stay usable at mobile sizes and larger text.
    for(const sample of [{width:1440,zoom:100,theme:'dark'},{width:1366,zoom:100,theme:'dark'},{width:390,zoom:100,theme:'light'},{width:320,zoom:200,theme:'dark'}]){
      await page.setViewportSize({width:sample.width,height:1000});
      await page.evaluate(sample=>{document.documentElement.style.fontSize=sample.zoom+'%';applyUiTheme(sample.theme);},sample);
      const label=language+'-'+sample.width+'-'+sample.zoom+'-'+sample.theme;
      for(const mode of ['complete','guided']){
        await setMode(page,mode);await sidebarTargets(page,label+'-'+mode);
      }
      await ensureRoute(page);
      await routeStep(page,0);await clickControl(page,'[data-onboarding-action="open"]');
      await geometry(page,label+' route','#onboardingPanel');
      await clickControl(page,'#onboardingHelpBtn');
      await geometry(page,label+' help','[data-onboarding-help]');
      await accessibility(page,label,['#onboardingPanel','[data-onboarding-help]']);
      await capture(page,label);
      await page.locator('[data-onboarding-action="close-help"]').focus();await page.keyboard.press('Enter');await settled(page);
      check(label+' help closes by keyboard',await page.locator('[data-onboarding-help]').count()===0);
      await setMode(page,'complete');await setMode(page,'guided');
    }
    check(language+' composing onboarding creates no duplicate DOM IDs',await page.locator('[id]').evaluateAll(nodes=>new Set(nodes.map(node=>node.id)).size===nodes.length));
    await visit.context.close();
  }
  const complete=await launch('en');page=complete.page;
  const completeBefore=await snapshot(page),completeWrites=[];
  page.on('request',request=>{if(!['GET','HEAD'].includes(request.method()))completeWrites.push(request.url());});
  await page.locator('[data-onboarding-choice="complete"]').focus();await page.keyboard.press('Enter');await settled(page);
  check('Choosing Complete directly offers expanded tools without starting a walkthrough',await page.evaluate(()=>OnboardingUI.state().mode==='complete'&&!OnboardingUI.state().active&&['workspaceResearch','workspaceFollowup','workspaceTools'].every(id=>document.getElementById(id).open)));
  await reloadProject(page);
  check('The direct Complete choice remains remembered and changes no project data',await page.locator('[data-onboarding-chooser]').count()===0&&await page.locator('#onboardingMode').inputValue()==='complete'&&isDeepStrictEqual(await snapshot(page),completeBefore)&&completeWrites.length===0,completeWrites);
  await complete.context.close();
  for(const storage of ['blocked','corrupt']){
    const visit=await launch('es',storage);page=visit.page;
    const before=await snapshot(page);
    await page.locator('[data-onboarding-choice="guided"]').click();await settled(page);
    await routeStep(page,2);await clickControl(page,'[data-onboarding-action="pause"]');await ensureRoute(page);
    check(storage+' preference storage still supports resuming within the tab',await current(page)==='2');
    await setMode(page,'complete');await setMode(page,'guided');
    check(storage+' preference storage never changes report data',isDeepStrictEqual(await snapshot(page),before));
    check(storage+' preference storage does not force a blocking prompt',await page.locator('dialog[open]').count()===0);
    await visit.context.close();
  }
  check('Onboarding sends no external requests',results.external.length===0,results.external);
  check('Onboarding raises no browser runtime errors',results.errors.length===0,results.errors);
  results.status='passed';
}catch(error){results.status='failed';results.error=String(error.stack||error);if(page&&!page.isClosed())await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});throw error;}
finally{clearTimeout(timer);results.finished=new Date().toISOString();save();await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{console.error(error);process.exitCode=1;});
