/* Repeatable local Chromium benchmark. All projects and evidence are synthetic. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const {spawn, spawnSync, execFile} = require('node:child_process');
const {promisify} = require('node:util');
const runFile = promisify(execFile);
const {performance} = require('node:perf_hooks');
const root = path.resolve(process.env.REPORT_GEN_TOOL_ROOT || path.join(__dirname, '..'));
const args = process.argv.slice(2);
if (args.includes('--help')) {
  console.log('Synthetic local benchmark: --counts 50,250,1000 --rounds 1 --evidence-limit 50 (0 = one per finding) --image-mode tiny|distinct --export-formats pdf,docx,md,html --export-timeout-seconds 600 --assert-bounded --output <empty directory>. Timings are observations, never universal thresholds. Distinct mode creates unique 800x450 synthetic screenshots; exports use the saved revision and verify all public content.');
  process.exit(0);
}
const opt = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const output = path.resolve(opt('--output', 'out/workspace-scale-0230'));
const counts = opt('--counts', '50,250,1000').split(',').map(Number);
const rounds = Number(opt('--rounds', '1'));
const evidenceLimit = Number(opt('--evidence-limit', '50'));
const imageMode = opt('--image-mode', 'tiny');
const exportFormats = opt('--export-formats', '').split(',').filter(Boolean);
const exportTimeoutSeconds = Number(opt('--export-timeout-seconds', '600'));
const assertBounded = args.includes('--assert-bounded');
const legacyRecords = args.includes('--legacy-records');
const insightsRecords = Number(opt('--insights-records','0'));
const visiblePreview = args.includes('--visible-preview-check');
const unregisteredImages = Number(opt('--unregistered-images','0'));
const python = process.env.RG_PYTHON || (process.platform==='win32'?'python':'python3');
const {chromium} = require(require.resolve('playwright', {paths: [root, process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES || root]}));
const canonical = value => JSON.stringify((function sort(v){return Array.isArray(v)?v.map(sort):v&&typeof v==='object'?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sort(v[k])])):v;})(value));
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
if (fs.existsSync(output) && fs.readdirSync(output).length) throw Error('Use an empty benchmark output directory; previous results are preserved.');
fs.mkdirSync(output, {recursive:true});
const report = {format:'report-gen-workspace-benchmark-2', counts, rounds, evidenceLimit, imageMode, exportFormats, started:new Date().toISOString(), hardware:{platform:os.platform(), arch:os.arch(), cpu:os.cpus()[0]?.model, logicalCpus:os.cpus().length, totalMemoryBytes:os.totalmem()}, scope:'Shared execution machine: other QA may run concurrently. Local loopback server; fresh Chromium context per size/round; preview hidden; synthetic text with '+(imageMode==='distinct'?'distinct 800x450 synthetic PNG screenshots':'one reused tiny PNG')+'. Timings include browser automation and HTTP waits and are not universal speed guarantees. Seed generation is excluded. Memory is the sampled server/browser process tree RSS, not every system allocation. Export worker timings separate snapshot preparation, actual generation, and content verification; no native Word or human visual approval is implied.', runtime:{node:process.version,python:spawnSync(python,['--version'],{encoding:'utf8'}).stdout.trim()}, sourceHashes:{}, samples:[], errors:[], checks:[]};
const runtimeFiles = () => ['scripts/benchmark-workspace-0230.cjs','scripts/benchmark-workspace.py','requirements-audited.txt','package-lock.json',
  ...fs.readdirSync(path.join(root,'webapp/static')).filter(file=>file.endsWith('.js')).map(file=>'webapp/static/'+file),
  ...fs.readdirSync(root).filter(file=>file.endsWith('.py')),
  ...fs.readdirSync(path.join(root,'exporters')).filter(file=>file.endsWith('.py')).map(file=>'exporters/'+file),
  ...fs.readdirSync(path.join(root,'webapp')).filter(file=>file.endsWith('.py')).map(file=>'webapp/'+file)].sort();
const hashes = () => Object.fromEntries(runtimeFiles().map(file=>[file,sha(fs.readFileSync(path.join(root,file)))]));
report.sourceHashes = hashes();
report.commit = spawnSync('git',['rev-parse','HEAD'],{cwd:root,encoding:'utf8'}).stdout.trim();
report.sourceState = spawnSync('git',['status','--porcelain'],{cwd:root,encoding:'utf8'}).stdout.trim()?'worktree_modified':'committed';
const versions = spawnSync(python,['-c','import importlib.metadata,json;print(json.dumps({name:importlib.metadata.version(name) for name in ("Pillow","Flask","PyYAML","python-docx","weasyprint","pypdf")}))'],{encoding:'utf8'});
report.runtime.packages = versions.status===0?JSON.parse(versions.stdout):{status:'unavailable'};
const worker = path.join(root, 'scripts/benchmark-workspace.py');
function uid(group, number) { return '00000000-0000-4000-8000-'+String(group*100000+number).padStart(12,'0'); }
function fixture(size,evidenceCount){
  const evidence=Array.from({length:evidenceCount},(_,i)=>({uid:uid(2,i+1),title:'Synthetic evidence '+(i+1),caption:imageMode==='distinct'?'Fictional 800x450 screenshot. No real pentest.':'Fictional one-pixel image. No real pentest.',src:'img/synthetic.png'}));
  const findings=Array.from({length:size},(_,i)=>({uid:uid(1,i+1),id:'F'+(i+1),mode:'vuln',title:i===size-1?'needle-tail-'+size:'Synthetic finding '+(i+1),severity:i%2?'low':'high',cvss:i%2?3.1:7.5,cvss_version:'3.1',cwe:'CWE-200',affected:'portal.example',description_md:'Synthetic observation and boundary. '.repeat(12),impact_md:'Fictional business impact; not executed.',remediation_md:'Proposed synthetic remediation.',references:[],walkthrough:[],remediation_summary:{},status:'open',verification:'unverified',owner:'Synthetic team',asset_uids:[],evidence_uids:evidenceCount?[evidence[i%evidenceCount].uid]:[],retests:[]}));
  return {schema_version:2,finding_sequence:size,meta:{lang:'es',theme:'corporativo',report_title:'Synthetic scale '+size,report_subtitle:'SIMULATION',client:'Synthetic Client .example',assessor:'Synthetic QA',assessor_title:'QA',date:'2026-10-08',version:'1.0',contacts:{client:[],assessor:[]},scope:[],branding:{wordmark:'SYNTHETIC',byline:'Local QA',accent:'#1f5fa8',confidential_text:'SIMULATION'}},report:{sections:[{key:'findings'}],workflow:{}},findings,assets:[],evidence,coverage:[]};
}
function procTable(){
  const rows=[];
  try{for(const name of fs.readdirSync('/proc').filter(value=>/^[0-9]+$/.test(value))){try{const status=fs.readFileSync('/proc/'+name+'/status','utf8');rows.push({pid:Number(name),parent:Number(status.match(/^PPid:\s+(\d+)/m)?.[1]),namespacePid:Number(status.match(/^NSpid:\s+(.+)/m)?.[1]?.trim().split(/\s+/).at(-1)),rss:Number(status.match(/^VmRSS:\s+(\d+)/m)?.[1]||0)*1024,peak:Number(status.match(/^VmHWM:\s+(\d+)/m)?.[1]||0)*1024});}catch(_){}}}catch(_){}return rows;
}
function processTreeMemory(pid){
  if(!pid)return {status:'unavailable',reason:'Process identity unavailable in this runtime'};
  const table=procTable();let rss=0,peak=0,count=0,pending=[pid];
  while(pending.length){const current=pending.pop(),row=table.find(value=>value.pid===current);if(!row)continue;rss+=row.rss;peak+=row.peak;count++;pending.push(...table.filter(value=>value.parent===current).map(value=>value.pid));}
  return count?{rssBytes:rss,sumProcessHighWaterBytes:peak,processes:count}:{status:'unavailable',reason:'Process RSS unavailable in this runtime'};
}
function check(name, passed, detail){report.checks.push({name,passed:Boolean(passed),detail});if(!passed)throw Error(name+': '+JSON.stringify(detail));}
async function sample(size,round){
  const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-'));
  fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
  const slug='synthetic-scale-'+size;
  const evidenceCount=evidenceLimit===0?size:Math.min(size,evidenceLimit);
  const initial=fixture(size,evidenceCount);
  if(insightsRecords){
    const count=Math.min(size,insightsRecords);
    initial.insights={version:1,
      claims:Array.from({length:count},(_,i)=>({uid:uid(3,i+1),finding_uid:uid(1,i+1),statement:'Synthetic claim '+(i+1),kind:'observed',demonstrates:'Synthetic observation only',does_not_demonstrate:'No real execution',evidence_uids:evidenceCount?[uid(2,i%evidenceCount+1)]:[]})),
      risks:Array.from({length:count},(_,i)=>({uid:uid(4,i+1),finding_uid:uid(1,i+1),service:'Synthetic service '+(i+1),objective:'Fictional continuity',consequence:'Synthetic consequence',tolerance:'Not agreed',source:'Synthetic scope note',assumptions:'Simulation only',priority:'P1',rationale:'Synthetic prioritization example',owner:'Synthetic team'})),
      comments:Array.from({length:count},(_,i)=>({uid:uid(5,i+1),finding_uid:uid(1,i+1),field:'description_md',body:'Synthetic review note '+(i+1),author:'Synthetic reviewer',visibility:'private',created:'2026-10-08T12:00:00+00:00',revision:'0'.repeat(64),status:'open'})),reviews:[]};
  }
  if(legacyRecords){
    for(const key of ['references','walkthrough','remediation_summary','cvss_version'])delete initial.findings.at(-1)[key];
    Object.assign(initial.findings[0],{mode:'machine',host:{name:'Synthetic legacy machine .example'},phases:[{name:'Synthetic empty legacy phase'}]});
    delete initial.findings[0].proof;
  }
  const seed=spawnSync(python,[worker,'seed',workspace],{cwd:root,input:JSON.stringify({slug,data:initial,unregistered_images:unregisteredImages,image_mode:imageMode}),encoding:'utf8',maxBuffer:20*1024*1024});
  if(seed.status!==0)throw Error('Synthetic seed failed: '+seed.stderr);
  const corpus=JSON.parse(seed.stdout);
  const initialData=corpus.data;
  const yaml=path.join(workspace,'projects',slug,'engagement.yaml');
  const sourceHash=sha(fs.readFileSync(yaml));
  let server,browser,context;
  const current={size,evidenceCount,unregisteredImages,round,imageMode,imageBytes:corpus.imageBytes,uniqueImageHashes:corpus.uniqueImageHashes,corpusSha256:corpus.corpusSha256,loadAverageStart:os.loadavg(),sourceBytes:fs.statSync(yaml).size,sourceSha256:sourceHash,timings:{},exports:[],states:[],http:[],httpHeaders:[],requests:[],errors:[]};
  report.samples.push(current);
  try{
    server=spawn(python,[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root,stdio:['ignore','pipe','pipe']});
    server.stderr.pipe(fs.createWriteStream(path.join(output,'server-'+size+'-'+round+'.log')));
    const serverStart=performance.now();
    const base=await new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Server startup timeout')),25000);server.stdout.on('data',data=>{text+=data;if(text.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(text.split('\n')[0]).url);}catch(error){reject(error);}}});server.once('exit',code=>{clearTimeout(timer);reject(Error('Server exited: '+code));});});
    current.timings.serverStartupMs=performance.now()-serverStart;
    browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined});
    report.browser=browser.version();
    let hostSelf=null;try{hostSelf=Number(fs.readlinkSync('/proc/self'));}catch(_){}
    const table=procTable();
    const serverPid=table.find(row=>row.parent===hostSelf&&row.namespacePid===server.pid)?.pid;
    const browserPid=table.filter(row=>row.parent===hostSelf).find(row=>{try{return /chromium|chrome/.test(fs.readFileSync('/proc/'+row.pid+'/cmdline','utf8'));}catch(_){return false;}})?.pid;
    context=await browser.newContext({viewport:{width:1366,height:1000},reducedMotion:'reduce'});
    const page=await context.newPage();page.setDefaultTimeout(60000);
    const cdp=await context.newCDPSession(page);await cdp.send('Performance.enable');
    await page.addInitScript(()=>{localStorage.setItem('rg.previewVisible','0');localStorage.setItem('rg.uiLang','es');window.__scaleLongTasks=[];try{new PerformanceObserver(list=>window.__scaleLongTasks.push(...list.getEntries().map(e=>({start:e.startTime,duration:e.duration})))).observe({type:'longtask',buffered:true});}catch(_){};});
    page.on('pageerror',error=>current.errors.push(error.message));
    const requests=new Map();page.on('request',request=>{requests.set(request,performance.now());if(request.url().includes('/api/'))current.requests.push({path:new URL(request.url()).pathname,method:request.method()});});page.on('requestfinished',request=>{if(request.url().includes('/api/'))current.http.push({path:new URL(request.url()).pathname,method:request.method(),elapsedMs:performance.now()-(requests.get(request)||performance.now())});});
    page.on('response',response=>{const request=response.request();if(request.url().includes('/api/'))current.httpHeaders.push({path:new URL(request.url()).pathname,method:request.method(),status:response.status(),elapsedMs:performance.now()-(requests.get(request)||performance.now())});});
    const state=async label=>{const perf=await cdp.send('Performance.getMetrics');const metrics=Object.fromEntries(perf.metrics.map(row=>[row.name,row.value]));current.states.push({label,...await page.evaluate(()=>({documentNodes:document.querySelectorAll('*').length,sidebarFindings:document.querySelectorAll('#findingList li').length,dashboardRows:document.querySelectorAll('.dash-row').length,galleryCards:document.querySelectorAll('.wf-gallery:not([data-unregistered-evidence])>.card').length,unregisteredGalleryCards:document.querySelectorAll('[data-unregistered-evidence]>.card').length,findings:S.data?.findings.length,longTasks:window.__scaleLongTasks})),jsHeapUsedBytes:metrics.JSHeapUsedSize,taskDurationSeconds:metrics.TaskDuration,layoutDurationSeconds:metrics.LayoutDuration,serverMemory:processTreeMemory(serverPid),browserMemory:processTreeMemory(browserPid)});};
    const timed=async(name,run)=>{const started=performance.now();await run();current.timings[name]=performance.now()-started;await state(name);};
    await timed('startupOpenHomeMs',async()=>{await page.goto(base);await page.waitForFunction(slug=>typeof S!=='undefined'&&S.slug===slug&&!projectStore.loading&&projectBusyCount===0,slug);await page.locator('.workspace-dashboard').waitFor();});
    check(size+'/'+round+' loads every finding',await page.evaluate(size=>S.data.findings.length===size,size),size);
    await timed('openFindingsBoardMs',async()=>{await page.locator('#navFindings').click();await page.waitForFunction(()=>S.sel.type==='findings');});
    if(assertBounded){
      check(size+'/'+round+' dashboard and sidebar DOM are bounded',await page.evaluate(()=>document.querySelectorAll('.dash-row').length<=50&&document.querySelectorAll('#findingList li').length<=50),current.states.at(-1));
      if(size>50){
        const pages=Math.ceil(size/50),pager=page.locator('[data-workspace-pagination="board"] select');
        await pager.selectOption(String(pages-1));
        check(size+'/'+round+' final dashboard page exposes the tail UID',await page.locator('.dash-row[data-finding-uid="'+uid(1,size)+'"]').count()===1);
        await pager.selectOption('0');
      }
    }
    await timed('searchTailMs',async()=>{await page.locator('#globalSearch').fill('needle-tail-'+size);await page.locator('#searchResults button').filter({hasText:'needle-tail-'+size}).first().waitFor();});
    await timed('navigateTailFindingMs',async()=>{await page.locator('#searchResults button').filter({hasText:'needle-tail-'+size}).first().click();await page.waitForFunction(size=>S.sel.type==='finding'&&S.data.findings[S.sel.idx]?.id==='F'+size,size);});
    if(assertBounded&&size>50){
      check(size+'/'+round+' search navigation reveals the selected tail on its sidebar page',await page.locator('#findingList [data-finding-uid="'+uid(1,size)+'"] .finding-nav').getAttribute('aria-current')==='page');
      await page.locator('[data-workspace-pagination="sidebar"] select').selectOption('0');
      check(size+'/'+round+' paging sidebar keeps the current finding unchanged',await page.evaluate(size=>S.data.findings[S.sel.idx].id==='F'+size,size));
      await page.locator('#findingList [data-finding-uid="'+uid(1,1)+'"] button').click();
      check(size+'/'+round+' first sidebar page opens the original first UID',await page.evaluate(expected=>S.data.findings[S.sel.idx].uid===expected,uid(1,1)));
      await page.locator('#globalSearch').fill('needle-tail-'+size);
      await page.locator('#searchResults button').filter({hasText:'needle-tail-'+size}).first().click();
    }
    if(legacyRecords){
      await page.locator('#findingList li button').first().click();
      check(size+'/'+round+' legacy machine navigation does not attach optional defaults',canonical(await page.evaluate(()=>S.data))===canonical(initialData));
      await page.locator('#globalSearch').fill('needle-tail-'+size);
      await page.locator('#searchResults button').filter({hasText:'needle-tail-'+size}).first().click();
    }
    check(size+'/'+round+' read-only journey preserves canonical project',sha(fs.readFileSync(yaml))===sourceHash&&canonical(await page.evaluate(()=>S.data))===canonical(initialData),sourceHash);
    if(legacyRecords){
      await page.locator('#editor input[data-field="short_md"]').fill('Explicit remediation edit');
      await page.waitForFunction(()=>!projectStore.dirty&&!projectStore.lastError);
      check(size+'/'+round+' explicit edit persists a previously absent remediation field',await page.evaluate(()=>S.data.findings.at(-1).remediation_summary?.short_md==='Explicit remediation edit'));
    }
    await timed('typeTenCharactersMs',async()=>{const title=page.locator('#editor input[data-field="title"]').first();await title.focus();await title.press('End');await title.pressSequentially('-qa-change',{delay:0});});
    await timed('saveIncludingDebounceMs',async()=>{await page.waitForFunction(()=>!projectStore.loading&&!projectStore.dirty&&!projectStore.lastError&&projectBusyCount===0);});
    const persisted=spawnSync(python,['-c','import sys,json;sys.path.insert(0,sys.argv[1]);from input_guard import load_yaml_file;print(json.dumps(load_yaml_file(sys.argv[2])))',root,yaml],{encoding:'utf8',maxBuffer:20*1024*1024});
    if(persisted.status!==0)throw Error(persisted.stderr);
    const data=JSON.parse(persisted.stdout);
    check(size+'/'+round+' saved tail keeps all identities and records',data.findings.length===size&&data.findings.every((f,i)=>f.uid===initialData.findings[i].uid&&f.id===initialData.findings[i].id)&&data.findings.at(-1).title==='needle-tail-'+size+'-qa-change',{count:data.findings.length,tail:data.findings.at(-1).title});
    await timed('openFilteredBoardMs',async()=>{await page.locator('#navFindings').click();await page.locator('.dash-pill.sev-low').click();await page.waitForFunction(()=>S.dashFilter==='low');});
    check(size+'/'+round+' filter does not discard source findings',await page.evaluate(size=>S.data.findings.length===size,size),size);
    await timed('openEvidenceGalleryMs',async()=>{await page.locator('[data-workflow="evidence"]').click();await page.locator('.wf-gallery:not([data-unregistered-evidence])').waitFor();await page.locator('.wf-gallery:not([data-unregistered-evidence])>.card').first().waitFor();});
    if(assertBounded){
      check(size+'/'+round+' gallery DOM is bounded',await page.evaluate(({size,evidenceCount})=>document.querySelectorAll('.wf-gallery:not([data-unregistered-evidence])>.card').length<=(evidenceCount>50?20:50)&&document.querySelectorAll('.wf-gallery input[type="checkbox"]').length<=(size>50?0:2500),{size,evidenceCount}),current.states.at(-1));
      if(evidenceCount>50){
        const pages=Math.ceil(evidenceCount/20);
        await page.locator('[data-workspace-pagination="evidence"] select').selectOption(String(pages-1));
        const card=page.locator('.wf-gallery [data-evidence-uid="'+uid(2,evidenceCount)+'"]');
        check(size+'/'+round+' last gallery page exposes the tail evidence UID',await card.count()===1);
        const associations=card.locator('[data-evidence-associations]');await associations.locator('summary').click();
        await associations.locator('input[data-finding-uid]').first().waitFor();
        check(size+'/'+round+' opened association editor has bounded fifty finding checkboxes',await associations.locator('input[data-finding-uid]').count()<=50);
        await associations.locator('input[type="search"]').fill('Synthetic finding 1');
        const link=associations.locator('input[data-finding-uid="'+uid(1,1)+'"]');
        await link.check();
        await page.waitForFunction(()=>!projectStore.dirty&&!projectStore.lastError);
        check(size+'/'+round+' linking tail evidence preserves the existing evidence reference',await page.evaluate(({first,last})=>S.data.findings[0].evidence_uids.includes(first)&&S.data.findings[0].evidence_uids.includes(last),{first:uid(2,1),last:uid(2,evidenceCount)}));
        await link.uncheck();await page.waitForFunction(()=>!projectStore.dirty&&!projectStore.lastError);
        check(size+'/'+round+' unlinking affects only the selected association',await page.evaluate(first=>S.data.findings[0].evidence_uids.length===1&&S.data.findings[0].evidence_uids[0]===first,uid(2,1)));
      }
    }
    if(unregisteredImages){
      check(size+'/'+round+' unregistered gallery renders at most twenty cards',await page.locator('[data-unregistered-evidence]>.card').count()<=20);
      const pages=Math.ceil(unregisteredImages/20);await page.locator('[data-workspace-pagination="unregistered-evidence"] select').selectOption(String(pages-1));
      check(size+'/'+round+' final unregistered image remains reachable',await page.locator('[data-unregistered-evidence] img').last().getAttribute('alt').then(alt=>alt==='img/unregistered-'+String(unregisteredImages).padStart(4,'0')+'.png'));
    }
    if(assertBounded)check(size+'/'+round+' hidden preview made no background render requests',!current.requests.some(row=>row.path.endsWith('/preview')),current.requests.filter(row=>row.path.endsWith('/preview')));
    const markup=await page.evaluate(async slug=>{const response=await appFetch('/api/projects/'+encodeURIComponent(slug)+'/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(S.data)});return {status:response.status,text:await response.text()};},slug);
    check(size+'/'+round+' preview exports all finding anchors despite UI filter',markup.status===200&&Array.from({length:size},(_,i)=>'id="F'+(i+1)+'"').every(anchor=>markup.text.includes(anchor)),{status:markup.status,bytes:Buffer.byteLength(markup.text)});
    if(assertBounded&&size>50){
      await page.locator('#navFindings').click();
      if(await page.locator('.dash-pill.sev-low').evaluate(el=>el.classList.contains('active')))await page.locator('.dash-pill.sev-low').click();
      await page.locator('.dash-tab').filter({hasText:'Manual'}).click();
      const mover=page.locator('[data-finding-move="'+uid(1,1)+'"]');
      await mover.click();await page.locator('dialog[open] [data-finding-position]').fill('0');
      await page.locator('dialog[open] [data-finding-move-apply]').click();
      check(size+'/'+round+' invalid cross-page position leaves order unchanged',await page.evaluate(first=>S.data.findings[0].uid===first&&!projectStore.dirty,uid(1,1)));
      await page.keyboard.press('Escape');
      check(size+'/'+round+' move dialog Escape restores its native opener focus',await mover.evaluate(el=>document.activeElement===el));
      await mover.click();await page.locator('dialog[open] [data-finding-position]').fill(String(size));
      await page.locator('dialog[open] [data-finding-move-apply]').click();
      await page.waitForFunction(()=>!projectStore.dirty&&!projectStore.lastError);
      check(size+'/'+round+' manual move reaches a different page without renumbering identities',await page.evaluate(({size,first})=>S.data.findings.length===size&&S.data.findings.at(-1).uid===first&&S.data.findings.at(-1).id==='F1'&&S.data.findings[0].id==='F2',{size,first:uid(1,1)}));
      await page.locator('#undoNotice button').click();await page.waitForFunction(()=>!projectStore.dirty&&!projectStore.lastError);
      check(size+'/'+round+' undo cross-page move preserves tail edits and original identity order',await page.evaluate(({size,first})=>S.data.findings[0].uid===first&&S.data.findings.at(-1).id==='F'+size&&S.data.findings.at(-1).title==='needle-tail-'+size+'-qa-change',{size,first:uid(1,1)}));
    }
    if(insightsRecords){
      const before=canonical(await page.evaluate(()=>S.data)),beforeETag=await page.evaluate(()=>projectStore.etag),beforeYaml=sha(fs.readFileSync(yaml));
      await timed('openClaimsWorkspaceMs',async()=>{await page.locator('#insightsBtn').click();await page.locator('[data-insights-action="save-claim"]').waitFor();});
      check(size+'/'+round+' optional claim collection is bounded to thirty records',await page.locator('[data-insights-action="edit-claim"]').count()<=30&&await page.locator('[data-insights-action="open-finding"]').count()<=20);
      await timed('openRiskWorkspaceMs',async()=>{await page.locator('[data-insights-tab="risk"]').click();await page.locator('[data-insights-action="save-risk"]').waitFor();});
      check(size+'/'+round+' optional risk collection is bounded to thirty records',await page.locator('[data-insights-action="edit-risk"]').count()<=30);
      await timed('openReviewWorkspaceMs',async()=>{await page.locator('[data-insights-tab="review"]').click();await page.locator('[data-insights-action="record-review"]').waitFor();});
      check(size+'/'+round+' optional comment collection is bounded to thirty records',await page.locator('[data-insights-action="resolve-comment"]').count()<=30);
      check(size+'/'+round+' optional-workspace navigation preserves source, draft and revision',before===canonical(await page.evaluate(()=>S.data))&&beforeETag===await page.evaluate(()=>projectStore.etag)&&beforeYaml===sha(fs.readFileSync(yaml))&&!await page.evaluate(()=>projectStore.dirty));
    }
    if(visiblePreview){
      if(!await page.locator('#previewToggle').isVisible()){
        if(!await page.locator('#studioMore').evaluate(el=>el.open))await page.locator('#studioMore > summary').click();
        if(!await page.locator('#exportMenu').evaluate(el=>el.open))await page.locator('#exportMenu > summary').click();
      }
      const response=page.waitForResponse(response=>response.url().endsWith('/preview')&&response.status()===200);
      await page.locator('#previewToggle').click();await response;
      await page.waitForFunction(()=>S.previewVisible&&document.querySelector('#pdfPreview').getAttribute('srcdoc')?.includes('-qa-change'));
      check(size+'/'+round+' explicitly showing preview generates the current saved content',await page.locator('#pdfPreview').getAttribute('srcdoc').then(html=>html.includes('needle-tail-'+size+'-qa-change')));
    }
    check(size+'/'+round+' browser has no page errors',current.errors.length===0,current.errors);
    for (const format of exportFormats) {
      const started = performance.now();
      const folder = path.join(output, 'exports-'+size+'-'+round);
      const generated = await runFile(python, [worker,'export',yaml,format,folder], {cwd:root,env:process.env,encoding:'utf8',maxBuffer:20*1024*1024,timeout:exportTimeoutSeconds*1000});
      const item = JSON.parse(generated.stdout);
      item.processElapsedMs = performance.now() - started;
      current.exports.push(item);
      check(size+'/'+round+' '+format+' actual export and content verification completed',item.bytes>0&&Boolean(item.checks),{bytes:item.bytes,sha256:item.sha256});
      fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(report,null,2));
    }
    current.loadAverageEnd=os.loadavg();current.status='passed';
  }finally{await context?.close().catch(()=>{});await browser?.close().catch(()=>{});server?.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}
}
(async()=>{try{if(!['tiny','distinct'].includes(imageMode)||exportFormats.some(f=>!['pdf','docx','md','html'].includes(f))||new Set(exportFormats).size!==exportFormats.length||!Number.isInteger(exportTimeoutSeconds)||exportTimeoutSeconds<1||exportTimeoutSeconds>3600)throw Error('Use image-mode tiny/distinct, unique export formats pdf/docx/md/html and timeout 1..3600 seconds.');if(!counts.every(n=>Number.isInteger(n)&&n>0&&n<=1000)||!Number.isInteger(rounds)||rounds<1||rounds>10||!Number.isInteger(evidenceLimit)||evidenceLimit<0||evidenceLimit>1000||!Number.isInteger(insightsRecords)||insightsRecords<0||insightsRecords>1000||!Number.isInteger(unregisteredImages)||unregisteredImages<0||unregisteredImages>1000)throw Error('Use counts 1..1000, rounds 1..10 and evidence-limit 0..1000.');for(const size of counts)for(let round=1;round<=rounds;round++)await sample(size,round);report.status='passed';}catch(error){report.status='failed';report.errors.push(error.stack);process.exitCode=1;}finally{report.finished=new Date().toISOString();report.sourceHashesAfter=hashes();report.sourceChangedDuringRun=canonical(report.sourceHashes)!==canonical(report.sourceHashesAfter);fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(report,null,2));console.log(JSON.stringify({status:report.status,samples:report.samples.map(s=>({size:s.size,evidenceCount:s.evidenceCount,uniqueImageHashes:s.uniqueImageHashes,imageBytes:s.imageBytes,timings:s.timings,exports:s.exports.map(e=>({format:e.format,exportMs:e.exportMs,verificationMs:e.verificationMs,bytes:e.bytes})),status:s.status})),checks:report.checks.length,errors:report.errors}));}})();
