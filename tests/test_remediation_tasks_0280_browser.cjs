/* Real browser acceptance: selected fields, exact preview, local exports and reflow. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn,execFileSync}=require('node:child_process');
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const root=path.resolve(option('--tool',process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'))),out=path.resolve(option('--output','out/remediation-tasks-0280'));
const python=process.env.RG_PYTHON||'python',axe=option('--axe',process.env.AXE_CORE_PATH)||require.resolve('axe-core/axe.min.js',{paths:[root]});
const axeSource=fs.readFileSync(axe,'utf8');
const {chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
fs.mkdirSync(out,{recursive:true});
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-remediation-'));fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const results={checks:[],pageErrors:[],externalRequests:[]},save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
function check(name,passed,detail){results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name);console.log('PASS '+name);}
const server=spawn(python,[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:{...process.env,PYTHONPATH:root+path.delimiter+path.join(root,'webapp')}});
server.stderr.on('data',value=>fs.appendFileSync(path.join(out,'server.log'),value));
let timer,browser,page;
(async()=>{try{
 const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server timeout')),20000);server.stdout.on('data',value=>{text+=value;for(const line of text.split('\n'))try{const parsed=JSON.parse(line);if(parsed.url){clearTimeout(timer);resolve(parsed.url);}}catch{}});server.on('exit',code=>reject(Error('Server exited '+code)));});
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||undefined,args:['--no-sandbox']});results.browser=browser.version();
 const context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
 await context.route('**/*',route=>{if(/^https?:/.test(route.request().url())&&!route.request().url().startsWith(base+'/')){results.externalRequests.push(route.request().url());return route.abort();}return route.continue();});
 page=await context.newPage();page.on('pageerror',error=>results.pageErrors.push(String(error)));let writes=0,previews=0;
 page.on('request',request=>{if(['PUT','DELETE'].includes(request.method()))writes++;if(request.url().endsWith('/remediation-tasks/preview'))previews++;});
 await page.goto(base);await page.waitForFunction(()=>typeof RemediationUI!=='undefined'&&!document.getElementById('splash'));
 await page.evaluate(async()=>{
  await requireOk(await api.post('/api/projects',{slug:'tasks-fixture',title:'Synthetic tasks'}));await refreshProjects();await loadProject('tasks-fixture');
  const asset={uid:WorkflowUI.uid(),name:'INTERNAL ASSET',target:'https://private.invalid',kind:'URL',notes:'OMITTED NOTES'};
  const group={uid:WorkflowUI.uid(),name:'Shared authorization cause',cause_md:'OMITTED ROOT CAUSE',remediation_md:'Shared remediation action'};
  S.data.assets=[asset];S.data.root_cause_groups=[group];S.data.finding_sequence=2;
  S.data.findings=[{uid:WorkflowUI.uid(),id:'F1',mode:'vuln',title:'<img src=x onerror=alert(1)>',severity:'high',description_md:'OMITTED DESCRIPTION',impact_md:'OMITTED IMPACT',remediation_md:'=CMD("test")',owner:'PRIVATE OWNER',due_date:'2026-11-20',status:'reported_fixed',root_cause_uid:group.uid,asset_uids:[asset.uid],closure_criteria_md:'Unauthorized user: 403; authorized user: 200.'},
    {uid:WorkflowUI.uid(),id:'F2',mode:'vuln',title:'Second task',severity:'low',remediation_md:'',root_cause_uid:group.uid}];
  scheduleSave();await doSave();select('findings');
 });
 await page.locator('#workspaceFollowup > summary').click();await page.locator('[data-workflow="remediation_tasks"]').click();
 await page.locator('[data-remediation-view]').waitFor();
 const before=await page.evaluate(()=>({json:JSON.stringify(S.data),etag:projectStore.etag})),writesBefore=writes;
 check('Visible navigation opens tasks with no implicit private-content request',previews===0&&await page.locator('[data-remediation-field="owner"]').isChecked()===false&&await page.locator('[data-remediation-private]').isChecked()===false&&await page.locator('[data-remediation-download="csv"]').isDisabled());
 await page.locator('[data-remediation-preview-button]').click();await page.waitForFunction(()=>document.querySelector('[data-remediation-preview] details'));
 check('Default preview includes stable IDs and no private narratives',await page.locator('.rt-card').count()===2&&await page.locator('[data-remediation-preview]').textContent().then(value=>value.includes('F1')&&!value.includes('PRIVATE OWNER')&&!value.includes('INTERNAL ASSET')&&!value.includes('OMITTED')));
 await page.locator('[data-remediation-field="owner"]').check();
 check('Adding a private field invalidates preview and requires explicit acknowledgement',await page.locator('.rt-card').count()===0&&await page.locator('[data-remediation-preview-button]').isDisabled()&&await page.locator('[data-remediation-download="csv"]').isDisabled());
 for(const key of ['title','assets','action','closure_criteria','group_name','group_uid','shared_action'])await page.locator('[data-remediation-field="'+key+'"]').check();
 await page.locator('[data-remediation-private]').check();await page.locator('[data-remediation-preview-button]').click();await page.waitForFunction(()=>document.querySelectorAll('.rt-card').length===2);
 await page.locator('.rt-card').nth(1).locator('summary').click();
 check('Explicit preview preserves independent tasks with individual and shared actions, closure criteria and escaped markup',await page.locator('[data-remediation-preview]').textContent().then(value=>value.includes('PRIVATE OWNER')&&value.includes('=CMD("test")')&&value.includes('Shared remediation action')&&value.includes('Unauthorized user: 403')&&value.includes('<img src=x onerror=alert(1)>'))&&await page.locator('[data-remediation-preview] img').count()===0);
 const csvDownload=page.waitForEvent('download');await page.locator('[data-remediation-download="csv"]').click();const csvFile=await csvDownload;await csvFile.saveAs(path.join(out,'tasks.csv'));
 const parsed=JSON.parse(execFileSync(python,['-c','import csv,json,sys;print(json.dumps(list(csv.reader(open(sys.argv[1],encoding="utf-8-sig",newline="")))))',path.join(out,'tasks.csv')],{encoding:'utf8'}));
 check('Downloaded CSV contains the exact previewed columns and neutralizes spreadsheet formulas',parsed.length===3&&parsed[0].length===12&&parsed[1].includes('\'=CMD("test")')&&parsed[1].includes('PRIVATE OWNER')&&!JSON.stringify(parsed).includes('OMITTED'));
 const zipDownload=page.waitForEvent('download');await page.locator('[data-remediation-download="cards"]').click();const zipFile=await zipDownload;await zipFile.saveAs(path.join(out,'tasks.zip'));
 const cards=JSON.parse(execFileSync(python,['-c','import zipfile,json,sys;z=zipfile.ZipFile(sys.argv[1]);print(json.dumps({n:z.read(n).decode() for n in z.namelist()}))',path.join(out,'tasks.zip')],{encoding:'utf8'}));
 check('Downloaded task ZIP uses permanent identifiers and static escaped HTML without extra content',Object.keys(cards).length===2&&Object.keys(cards).every(name=>/^task-[a-f0-9-]{36}\.html$/.test(name))&&Object.values(cards).some(text=>text.includes('&lt;img src=x onerror=alert(1)&gt;'))&&Object.values(cards).every(text=>!text.includes('<img ')&&!text.includes('OMITTED')&&text.includes('Content-Security-Policy')));
 check('Preview and export do not save or change the project',writes===writesBefore&&await page.evaluate(value=>JSON.stringify(S.data)===value.json&&projectStore.etag===value.etag,before));
 await page.locator('[data-remediation-private]').uncheck();check('Withdrawing private-field consent removes previews and disables downloads',await page.locator('.rt-card').count()===0&&await page.locator('[data-remediation-download="cards"]').isDisabled());
 await page.locator('[data-remediation-private]').check();await page.locator('[data-remediation-preview-button]').click();await page.waitForFunction(()=>document.querySelectorAll('.rt-card').length===2);
 await page.evaluate(()=>{S.data.findings[0].owner='CHANGED OWNER';scheduleSave();projectStore.timers.clearTimeout(projectStore.timer);projectStore.timer=null;});
 check('An unsaved edit immediately invalidates preview and download',await page.locator('.rt-card').count()===0&&await page.locator('[data-remediation-download="csv"]').isDisabled());
 await page.evaluate(async()=>{await doSave();select('workflow','remediation_tasks');});
 let received=false,release;const pending=new Promise(resolve=>release=resolve);
 await context.route(base+'/api/projects/tasks-fixture/remediation-tasks/preview',async route=>{const response=await route.fetch();received=true;await pending;await route.fulfill({response});});
 await page.locator('[data-remediation-preview-button]').click();for(let n=0;!received&&n<200;n++)await page.waitForTimeout(10);assert.ok(received);
 await page.locator('[data-remediation-field="owner"]').check();release();await page.waitForTimeout(150);
 check('A late preview cannot reinstate previously selected fields after options change',await page.locator('.rt-card').count()===0&&await page.locator('[data-remediation-download="csv"]').isDisabled());
 await context.unroute(base+'/api/projects/tasks-fixture/remediation-tasks/preview');
 const views=[];
 for(const lang of ['es','en'])for(const theme of ['dark','light'])for(const width of [320,1440])for(const growth of [1,2]){
  await page.setViewportSize({width,height:1000});await page.evaluate(({lang,theme})=>{document.querySelectorAll('[data-task-test-growth]').forEach(element=>{element.style.removeProperty('font-size');element.removeAttribute('data-task-test-growth');});setUiLang(lang);applyUiTheme(theme);select('workflow','remediation_tasks');},{lang,theme});
  for(const key of ['title','action','owner','closure_criteria'])await page.locator('[data-remediation-field="'+key+'"]').check();
  await page.locator('[data-remediation-private]').check();await page.locator('[data-remediation-preview-button]').click();await page.waitForFunction(()=>document.querySelectorAll('.rt-card').length===2);
  const sizes=await page.evaluate(growth=>{const node=document.querySelector('[data-remediation-view]'),before=parseFloat(getComputedStyle(node).fontSize);if(growth===2){const entries=[...document.querySelectorAll('*')].filter(node=>node instanceof HTMLElement).map(node=>[node,parseFloat(getComputedStyle(node).fontSize)]);for(const[node,size]of entries){node.style.fontSize=size*2+'px';node.setAttribute('data-task-test-growth','');}}return{before,after:parseFloat(getComputedStyle(node).fontSize)};},growth);
  const layout=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth,controls:[...document.querySelectorAll('[data-remediation-view] button,[data-remediation-view] input')].map(node=>({left:node.getBoundingClientRect().left,right:node.getBoundingClientRect().right,width:node.getBoundingClientRect().width}))}));
  await page.evaluate(axeSource);const violations=await page.evaluate(async()=>{const result=await axe.run(document.querySelector('[data-remediation-view]'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return result.violations.map(item=>({id:item.id,nodes:item.nodes.map(node=>node.target)}));});
  const view={lang,theme,width,growth,sizes,layout,violations};views.push(view);
  check('Tasks language/theme/reflow/axe '+[lang,theme,width,growth*100+'%'].join('/'),sizes.after===sizes.before*growth&&layout.scroll<=width+1&&layout.controls.every(control=>control.width>=17&&control.left>=-1&&control.right<=width+1)&&violations.length===0,view);
  if(width===320&&growth===2)await page.screenshot({path:path.join(out,'tasks-'+lang+'-'+theme+'-mobile-200.png'),fullPage:true});
 }
 results.views=views;results.axeExecuted=true;
 check('Language switching does not change report language or saved project',await page.evaluate(()=>S.data.meta.lang==='es'&&!projectStore.dirty));
 check('No browser errors or external requests',results.pageErrors.length===0&&results.externalRequests.length===0);save();
 }catch(error){if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw error;}finally{clearTimeout(timer);await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{results.error=String(error.stack||error);save();console.error(error);process.exitCode=1;});
