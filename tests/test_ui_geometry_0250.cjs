/* Browser geometry, saved facts and fit-width behavior. All input is synthetic. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const {clickNavigationControl}=require('./browser-navigation.cjs');
const args=process.argv.slice(2),opt=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const root=path.resolve(opt('--tool',process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'))),out=path.resolve(opt('--output','out/ui-geometry-0250'));
const {chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
fs.mkdirSync(out,{recursive:true});
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-ui0250-'));fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const results={checks:[],geometry:[],preview:[],errors:[],external:[]},save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
function check(name,passed,detail){results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name);console.log('PASS '+name);}
const server=spawn(process.env.RG_PYTHON||'python',[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,env:{...process.env,PYTHONPATH:root+path.delimiter+path.join(root,'webapp')}});
server.stderr.on('data',data=>fs.appendFileSync(path.join(out,'server.log'),data));let browser,page,timer;
async function geometry(){return page.evaluate(()=>{
  const rect=node=>{const r=node.getBoundingClientRect();return {x:r.x,y:r.y,width:r.width,height:r.height,right:r.right,bottom:r.bottom};};
  const textRect=node=>{const range=document.createRange();range.selectNodeContents(node);return rect(range);};
  return {width:innerWidth,overflow:document.documentElement.scrollWidth-innerWidth,rows:[...document.querySelectorAll('[data-retest-result-count]')].map(row=>({key:row.dataset.retestResultCount,count:Number(row.querySelector('strong').textContent),row:rect(row),label:rect(row.querySelector('.rm-count-label')),value:rect(row.querySelector('strong')),valueText:textRect(row.querySelector('strong')),track:rect(row.querySelector('.rm-chart-track')),bar:rect(row.querySelector('.rm-chart-bar'))}))};
});}
function validGeometry(g){const max=Math.max(1,...g.rows.map(row=>row.count));return g.overflow<=1&&g.rows.length>0&&g.rows.every(row=>{
  const inside=['label','value','track','bar'].every(key=>row[key].y>=row.row.y-1&&row[key].bottom<=row.row.bottom+1&&row[key].right<=row.row.right+1);
  const proportion=Math.abs(row.bar.width-Math.max(0,row.track.width-2)*row.count/max)<=1.1;
  return inside&&proportion&&row.track.height>=14&&row.value.width>0&&row.label.width>0&&row.valueText.x>=row.value.x-1&&row.valueText.right<=row.value.right+1;
});}
async function previewMetrics(){return page.evaluate(()=>{const f=$('#pdfPreview'),d=f.contentDocument,r=d.querySelector('.cover').getBoundingClientRect();return {mode:f.dataset.previewZoomMode,zoom:Number(f.dataset.previewZoom),frameWidth:f.clientWidth,docWidth:d.documentElement.clientWidth,scrollWidth:d.documentElement.scrollWidth,coverLeft:r.left,coverRight:r.right,coverWidth:r.width,title:d.title,selected:$('#previewZoom').value};});}
async function showPreview(label){
  // At these desktop widths the index and preview share space. Request the
  // visible preview through its public control, including after project loads.
  if(!await page.locator('.layout > .preview').isVisible())await clickNavigationControl(page,'#previewToggle');
  if(await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();
  check(label,await page.locator('.layout > .preview').isVisible()&&!await page.locator('#contextIndex').isVisible());
}
(async()=>{try{
  const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server timeout')),30000);server.stdout.on('data',data=>{text+=data;for(const line of text.split('\n'))try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});server.on('exit',code=>reject(Error('Server exited '+code)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined,args:['--no-sandbox']});results.browser=browser.version();
  const context=await browser.newContext({viewport:{width:1440,height:1100},reducedMotion:'reduce'});
  await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)&&!url.startsWith(base+'/')){results.external.push(url);return route.abort();}return route.continue();});
  page=await context.newPage();page.on('pageerror',e=>results.errors.push(String(e)));page.on('dialog',d=>d.accept());
  await page.goto(base);await page.waitForFunction(()=>typeof ExperienceUI!=='undefined'&&!document.getElementById('splash'));
  await page.evaluate(async()=>{
    await requireOk(await api.post('/api/projects',{slug:'ui-geometry',title:'Synthetic UI geometry',client:'Synthetic entity'}));
    await requireOk(await api.post('/api/projects',{slug:'ui-preview',title:'Synthetic preview fit',client:'Synthetic entity'}));
    await requireOk(await api.post('/api/projects',{slug:'ui-other',title:'Synthetic other preview',client:'Synthetic entity'}));
    await refreshProjects();await loadProject('ui-geometry');S.data.report.sections=[];
    S.data.findings=Array.from({length:500},(_,index)=>({id:'F'+String(index+1).padStart(3,'0'),uid:WorkflowUI.uid(),mode:'vuln',title:'Synthetic finding '+index,severity:'low',description_md:'Synthetic finding.',impact_md:'Synthetic impact.',remediation_md:'Synthetic remediation.',status:'open',evidence_uids:[],asset_uids:[],retests:index<2?[{uid:WorkflowUI.uid(),tested_on:'2026-10-09',result:index?'fixed':'open',assessor:'Synthetic assessor',notes_md:'Synthetic check.',evidence_uids:[]}]:[]}));
    S.data.finding_sequence=500;scheduleSave();await doSave();select('workflow','retest_matrix');
  });
  await page.locator('[data-retest-matrix]').waitFor();
  if(args.includes('--reproduce-baseline')){
    const measurements=await page.evaluate(()=>{const labels=[...document.querySelectorAll('[data-retest-result-count]')],bars=[...document.querySelectorAll('[data-retest-chart] rect')];return labels.map((label,index)=>{const lr=label.getBoundingClientRect(),br=bars[index].getBoundingClientRect();return {label:label.textContent,labelY:lr.y,labelHeight:lr.height,barY:br.y,barHeight:br.height,centerDifference:Math.abs(lr.y+lr.height/2-br.y-br.height/2)};});});
    results.baselineDefect={measurements,reproduced:measurements.some(row=>row.centerDifference>10)};
    await page.locator('.rm-executive').screenshot({path:path.join(out,'retest-baseline-defect.png')});
    check('Baseline visually separates bars from their semantic label rows',results.baselineDefect.reproduced,measurements);save();return;
  }
  for(const lang of ['es','en'])for(const theme of ['dark','light']){
    await page.evaluate(({lang,theme})=>{setUiLang(lang);applyUiTheme(theme);select('workflow','retest_matrix');},{lang,theme});await page.locator('[data-retest-matrix]').waitFor();
    for(const width of [320,390,768,1440])for(const growth of [1,2]){
      await page.setViewportSize({width,height:1100});
      await page.evaluate(growth=>{for(const node of document.querySelectorAll('.rm-counts li *'))node.style.fontSize=growth*16+'px';},growth);
      const g=await geometry();results.geometry.push({lang,theme,width,growth,...g});
      check('Retest rows and bars remain associated '+[lang,theme,width,growth].join('/'),validGeometry(g)&&g.rows.some(row=>row.count===498)&&g.rows.some(row=>row.count===1)&&g.rows.some(row=>row.count===0));
      if(lang==='es'&&theme==='dark'&&((width===320&&growth===2)||(width===1440&&growth===1)))await page.locator('.rm-executive').screenshot({path:path.join(out,'retest-'+width+'-'+growth+'.png')});
    }
  }
  await page.locator('[data-retest-filter="outcome"]').selectOption('fixed');let g=await geometry();check('Filtering recalculates both readable count and bar proportion',validGeometry(g)&&g.rows.reduce((sum,row)=>sum+row.count,0)===1);
  await page.locator('[data-retest-filter="outcome"]').selectOption('partial');g=await geometry();check('Empty filters render zero bars with zero counts',validGeometry(g)&&g.rows.every(row=>row.count===0&&row.bar.width===0));
  await page.locator('[data-retest-filter="outcome"]').selectOption('');await page.emulateMedia({media:'print'});g=await geometry();check('Print media keeps each bar with its label and count',validGeometry(g));await page.emulateMedia({media:'screen'});
  await page.evaluate(async()=>{await loadProject('ui-preview');select('studio','deliver');});
  await page.waitForFunction(()=>document.querySelector('[data-delivery-readiness]')?.dataset.readinessCurrent==='true');
  check('Readiness counter counts checked facts and keeps manual review required',await page.evaluate(()=>{const rows=[...document.querySelectorAll('[data-readiness-check]')],n=rows.filter(row=>row.dataset.readinessStatus==='checked').length;return rows.length===5&&document.querySelector('[data-readiness-progress]').textContent.startsWith(n+' ')&&document.querySelector('[data-readiness-check="human_review"]').dataset.readinessStatus==='manual'&&rows.every(row=>row.querySelector('.readiness-icon[aria-hidden="true"]')&&row.querySelector('[data-readiness-action]'));}));
  for(const key of ['review','annexes','secrets','associations','human_review']){
    await page.locator('[data-readiness-action="'+key+'"]').click();
    const destination=key=>key==='review'?S.sel.type==='workflow'&&S.sel.idx==='review':key==='annexes'?!!document.querySelector('dialog.annex-dialog[open]'):key==='secrets'?!!document.querySelector('dialog.studio-dialog[open]'):key==='associations'?S.sel.type==='workflow'&&S.sel.idx==='evidence':S.sel.type==='insights'&&S.sel.idx==='visual';
    await page.waitForFunction(destination,key);
    const target=await page.evaluate(destination,key);
    check('Readiness direct destination '+key,target);
    await page.evaluate(()=>{document.querySelectorAll('dialog[open]').forEach(d=>d.close());select('studio','deliver');});await page.waitForFunction(()=>document.querySelector('[data-delivery-readiness]')?.dataset.readinessCurrent==='true');
  }
  for(const width of [320,390,768,1440]){
    await page.setViewportSize({width,height:1100});check('Readiness reflows at '+width,await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1&&[...document.querySelectorAll('[data-readiness-check]')].every(row=>row.getBoundingClientRect().right<=innerWidth+1)));
  }
  await page.locator('[data-readiness-summary]').screenshot({path:path.join(out,'readiness-desktop.png')});
  await page.evaluate(()=>{setUiLang('es');select('report',-1);});
  await showPreview('The visible preview is restored before fit-width geometry checks');
  await page.waitForFunction(()=>WorkbenchUI.hasLivePreview()&&$('#pdfPreview').dataset.previewZoomMode==='fit');
  for(const theme of ['serio','corporativo','offsec','htb','ejecutivo','laboratorio']){
    await page.evaluate(async theme=>{S.data.meta.theme=theme;delete S.data.meta.design;scheduleSave();await doSave();refreshLivePreview();},theme);
    await page.waitForFunction(()=>WorkbenchUI.hasLivePreview());
    for(const width of [1280,1440]){
      await page.setViewportSize({width,height:1100});await page.waitForFunction(()=>{const f=$('#pdfPreview'),d=f.contentDocument,r=d.querySelector('.cover').getBoundingClientRect();return r.right<=d.documentElement.clientWidth+1;});
      const metric=await previewMetrics();results.preview.push({theme,width,...metric});check('Fit width shows entire cover '+theme+'/'+width,metric.mode==='fit'&&metric.coverLeft>=-1&&metric.coverRight<=metric.docWidth+1&&metric.scrollWidth<=metric.docWidth+1);
    }
  }
  await page.locator('.preview').screenshot({path:path.join(out,'preview-fit.png')});
  const beforeZoom=await page.evaluate(()=>({data:JSON.stringify(S.data),etag:projectStore.etag,revision:projectStore.revision}));let zoomWrites=0;
  const countZoomWrites=request=>{if(!['GET','HEAD'].includes(request.method()))zoomWrites++;};page.on('request',countZoomWrites);
  await page.locator('#previewZoom').selectOption('125');await page.setViewportSize({width:1280,height:1100});
  check('Manual zoom survives resizing',Math.abs((await previewMetrics()).zoom-1.25)<.001);
  check('Changing zoom does not write or alter report data',zoomWrites===0&&await page.evaluate(before=>JSON.stringify(S.data)===before.data&&projectStore.etag===before.etag&&projectStore.revision===before.revision,beforeZoom));page.off('request',countZoomWrites);
  await page.evaluate(async()=>{await loadProject('ui-other');select('report',-1);refreshLivePreview();});
  await showPreview('The visible preview is restored after switching projects');
  await page.waitForFunction(()=>WorkbenchUI.hasLivePreview());
  check('Manual zoom survives project changes and preview refreshes',(await previewMetrics()).selected==='125'&&Math.abs((await previewMetrics()).zoom-1.25)<.001);
  await page.locator('#previewZoom').selectOption('fit');await page.locator('#previewWidth').fill('55');
  await page.waitForFunction(()=>{const f=$('#pdfPreview'),d=f.contentDocument;return d.querySelector('.cover').getBoundingClientRect().right<=d.documentElement.clientWidth+1;});
  check('Fit width recalculates after pane width changes',(await previewMetrics()).scrollWidth<=(await previewMetrics()).docWidth+1);
  await page.evaluate(()=>setUiLang('en'));check('Zoom control is localized without changing report language',await page.locator('#previewZoom option[value="fit"]').textContent()==='Fit width'&&await page.evaluate(()=>S.data.meta.lang==='es'));
  for(const width of [320,390,768]){await page.setViewportSize({width,height:1000});check('Narrow editor retains its existing hidden preview layout '+width,await page.locator('.preview').isHidden()&&await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));}
  const fallback=await context.newPage();fallback.on('pageerror',e=>results.errors.push(String(e)));
  await fallback.route('**/static/insights.js',route=>route.abort());await fallback.goto(base);
  await fallback.waitForFunction(()=>typeof ExperienceUI!=='undefined'&&!document.getElementById('splash')&&!projectStore.loading&&projectBusyCount===0&&!!S.slug);
  await fallback.evaluate(async()=>{await loadProject('ui-preview');select('studio','deliver');});
  await fallback.waitForFunction(()=>document.querySelector('[data-delivery-readiness]')?.dataset.readinessCurrent==='true');
  await fallback.locator('[data-readiness-action="human_review"]').click();
  check('Missing optional insights module keeps human review navigation usable',await fallback.evaluate(()=>typeof InsightsUI==='undefined'&&S.sel.type==='workflow'&&S.sel.idx==='review'&&!document.querySelector('.toast')));await fallback.close();
  check('No JavaScript errors or external requests',results.errors.length===0&&results.external.length===0,{errors:results.errors,external:results.external});results.passed=true;save();
}catch(error){results.error=String(error.stack||error);save();if(page)await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});throw error;}finally{clearTimeout(timer);await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{console.error(error);process.exitCode=1;});
