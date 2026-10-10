/* Same origin and project slug, different real server workspaces: no draft crossover. */
'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const root=path.resolve(option('--tool',process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'))),out=path.resolve(option('--output','out/workspace-browser-isolation-0290'));
const python=process.env.RG_PYTHON||'python';
const {chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
fs.mkdirSync(out,{recursive:true});
const roots=['A','B'].map(name=>{const directory=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-isolation-'+name+'-'));fs.writeFileSync(path.join(directory,'.test-only'),'synthetic acceptance workspace');return directory;});
const results={checks:[],pageErrors:[],externalRequests:[]},save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
function check(name,passed,detail){results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name);console.log('PASS '+name);}
let server,browser,context,pageA,pageB,returnA,currentPage;
const otherPng=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+yV1cAAAAASUVORK5CYII=','base64');
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAFklEQVR4nGP8//8/AwMDEwMDAwMDAwAkBgMB/DXemwAAAABJRU5ErkJggg==','base64');
async function stopServer(){if(!server)return;const process=server;server=null;if(process.exitCode===null){const stopped=new Promise(resolve=>process.once('exit',resolve));process.kill('SIGTERM');await stopped;}}
async function startServer(workspace,port=0){
 const process=server=spawn(python,[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace,'--port',String(port)],{cwd:root,env:{...global.process.env,REPORT_GEN_WORKSPACE:workspace,PYTHONPATH:root+path.delimiter+path.join(root,'webapp')}});
 process.stderr.on('data',value=>fs.appendFileSync(path.join(out,'server.log'),value));
 return new Promise((resolve,reject)=>{let text='';const timer=setTimeout(()=>reject(Error('Server timeout')),20000);process.stdout.on('data',value=>{text+=value;for(const line of text.split('\n'))try{const parsed=JSON.parse(line);if(parsed.url){clearTimeout(timer);resolve(parsed);}}catch{}});process.once('exit',code=>{clearTimeout(timer);reject(Error('Server exited '+code));});});
}
async function openPage(url,label){const page=currentPage=await context.newPage();page.on('pageerror',error=>results.pageErrors.push(label+': '+String(error)));page.on('dialog',dialog=>dialog.accept());await page.goto(url);await page.waitForFunction(()=>typeof PendingUI!=='undefined'&&typeof StudioUI!=='undefined'&&!document.getElementById('splash')&&!projectStore.loading&&projectBusyCount===0);return page;}
async function closeDialogs(page){await page.evaluate(async()=>{await StudioUI.recovery();for(const dialog of document.querySelectorAll('dialog[open]'))dialog.close();});}
async function records(page){return page.evaluate(async()=>({saved:S.data,recovery:projectStore.recovery,drafts:await projectStore.journal.list('shared-project'),pending:await PendingUI.list('shared-project')}));}
(async()=>{try{
 const first=await startServer(roots[0]);results.origin=first.url;
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||undefined,args:['--no-sandbox']});context=await browser.newContext({viewport:{width:1440,height:1000},reducedMotion:'reduce',acceptDownloads:true});
 await context.addInitScript(()=>localStorage.setItem('rg.previewVisible','0'));
 await context.route('**/*',route=>{if(/^https?:/.test(route.request().url())&&!route.request().url().startsWith(first.url+'/')){results.externalRequests.push(route.request().url());return route.abort();}return route.continue();});
 pageA=await openPage(first.url,'A');
 const savedA=await pageA.evaluate(async()=>{
   await requireOk(await api.post('/api/projects',{slug:'shared-project',title:'Workspace A saved',client:'A_SAVED_PRIVATE'}));await refreshProjects();await loadProject('shared-project');
   const data=JSON.parse(JSON.stringify(S.data));S.data.meta.client='A_DRAFT_PRIVATE';scheduleSave();projectStore.timers.clearTimeout(projectStore.timer);projectStore.timer=null;
   await projectStore.journal.tail;await WorkbenchUI.capture();return data;
 });
 await pageA.waitForFunction(()=>projectStore.recoverableRevision===projectStore.revision&&projectStore.dirty);
 await pageA.locator('[data-capture-title]').fill('A_PENDING_PRIVATE');await pageA.locator('[data-capture-note]').fill('A_PENDING_CONTEXT');await pageA.locator('[data-capture-kind]').selectOption('image');
 await pageA.locator('[data-capture-image]').setInputFiles({name:'A_PRIVATE.png',mimeType:'image/png',buffer:png});
 await pageA.waitForFunction(()=>{const handle=PendingUI.active.get(S.slug+'|capture');return handle?.revision>0&&handle.revision===handle.persisted;});await closeDialogs(pageA);
 check('Workspace A really stores an unsaved draft and pending image in IndexedDB',await pageA.evaluate(async()=>{const d=await projectStore.journal.list(S.slug),p=await PendingUI.list(S.slug);return d.some(row=>row.data.meta.client==='A_DRAFT_PRIVATE')&&p.some(row=>row.data.title==='A_PENDING_PRIVATE'&&row.file.size>0)&&projectStore.dirty;}));
 fs.mkdirSync(path.join(roots[0],'projects','shared-project','img'),{recursive:true});fs.writeFileSync(path.join(roots[0],'projects','shared-project','img','proof.png'),png);
 const oldImageURL=await pageA.evaluate(()=>{const image=h('img',{src:'/api/projects/shared-project/img/proof.png',alt:'Synthetic original image'});document.body.append(image);return image.src;});
 const imageA=await pageA.evaluate(async url=>{const response=await fetch(url,{cache:'no-store'});return {status:response.status,body:btoa(String.fromCharCode(...new Uint8Array(await response.arrayBuffer())))};},oldImageURL);
 check('A real rendered image URL is bound to A and serves only A image bytes',imageA.status===200&&imageA.body===png.toString('base64')&&oldImageURL.includes('workspace_id='));
 const initialA=await records(pageA),idA=await pageA.evaluate(()=>BrowserWorkspace.current());
 check('A browser identity is opaque and every new journal record is explicitly bound',/^[a-f0-9]{64}$/.test(idA)&&[...initialA.drafts,...initialA.pending].every(row=>row.workspace_id===idA));
 const dataB=structuredClone(savedA);dataB.meta.report_title='Workspace B saved';dataB.meta.client='B_SAVED_PRIVATE';fs.mkdirSync(path.join(roots[1],'projects','shared-project'),{recursive:true});fs.writeFileSync(path.join(roots[1],'projects','shared-project','engagement.yaml'),JSON.stringify(dataB,null,2));
 fs.mkdirSync(path.join(roots[1],'projects','shared-project','img'),{recursive:true});fs.writeFileSync(path.join(roots[1],'projects','shared-project','img','proof.png'),otherPng);
 await stopServer();const second=await startServer(roots[1],first.port);check('Both independent workspaces use exactly the same browser origin and slug',second.url===first.url&&path.basename(path.join(roots[1],'projects','shared-project'))==='shared-project');
 pageB=await openPage(second.url,'B');await pageB.evaluate(()=>loadProject('shared-project'));
 const b=await records(pageB),idB=await pageB.evaluate(()=>BrowserWorkspace.current());
 check('A and B have distinct workspace identities at the same origin',/^[a-f0-9]{64}$/.test(idB)&&idA!==idB);
 check('Workspace B neither displays nor offers A drafts or pending images',b.saved.meta.client==='B_SAVED_PRIVATE'&&b.drafts.length===0&&b.pending.length===0&&b.recovery.length===0&&!(await pageB.locator('body').textContent()).includes('A_PENDING_PRIVATE')&&!(await pageB.locator('body').textContent()).includes('A_DRAFT_PRIVATE'));
 const imageB=await pageB.evaluate(async old=>{const attempt=async url=>{const r=await fetch(url,{cache:'no-store'});return {status:r.status,body:btoa(String.fromCharCode(...new Uint8Array(await r.arrayBuffer())))};};return {old:await attempt(old),current:await attempt(scopedResourceURL('/api/projects/shared-project/img/proof.png'))};},oldImageURL);
 check('Old native image URLs cannot load a different workspace image at the same path',imageB.old.status===409&&imageB.old.body!==otherPng.toString('base64')&&imageB.current.status===200&&imageB.current.body===otherPng.toString('base64'));
 const stale=await pageA.evaluate(async()=>{
   const attempt=async options=>{try{const response=await appFetch('/api/projects/shared-project',options);return {status:response.status,body:await response.text()};}catch(error){return {error:String(error),blocked:typeof BrowserWorkspace!=='undefined'&&BrowserWorkspace.blocked()};}};
   return {read:await attempt(),write:await attempt({method:'PUT',headers:{'Content-Type':'application/json','If-Match':projectStore.etag},body:JSON.stringify(S.data)})};
 });
 check('The old A tab cannot read or mutate B through application requests',([409,412,423].includes(stale.read.status)||stale.read.blocked)&&([403,409,412,423].includes(stale.write.status)||stale.write.blocked)&&!JSON.stringify(stale).includes('B_SAVED_PRIVATE')&&JSON.stringify(await records(pageB)).includes('B_SAVED_PRIVATE'),stale);
 const bDisk=fs.readFileSync(path.join(roots[1],'projects','shared-project','engagement.yaml'),'utf8');check('Rejected old-tab writes leave B project bytes unchanged',bDisk===JSON.stringify(dataB,null,2));
 await pageB.evaluate(()=>{S.data.meta.client='B_DRAFT_PRIVATE';scheduleSave();projectStore.timers.clearTimeout(projectStore.timer);projectStore.timer=null;});await pageB.waitForFunction(()=>projectStore.recoverableRevision===projectStore.revision&&projectStore.dirty);
 const afterA=await records(pageA);check('A tab continues protecting its own draft namespace while B creates another draft',afterA.drafts.some(row=>row.data.meta.client==='A_DRAFT_PRIVATE')&&!JSON.stringify(afterA.drafts).includes('B_DRAFT_PRIVATE')&&afterA.pending.length===initialA.pending.length);
 await stopServer();const again=await startServer(roots[0],first.port);returnA=await openPage(again.url,'A restarted');await returnA.evaluate(()=>loadProject('shared-project'));
 const restored=await records(returnA);
 check('Workspace identity survives a real server restart',await returnA.evaluate(()=>BrowserWorkspace.current())===idA);
 check('Restarting workspace A recovers only its original draft and pending image',restored.saved.meta.client==='A_SAVED_PRIVATE'&&restored.drafts.some(row=>row.data.meta.client==='A_DRAFT_PRIVATE')&&restored.pending.some(row=>row.data.title==='A_PENDING_PRIVATE')&&!JSON.stringify(restored).includes('B_DRAFT_PRIVATE'));
 await closeDialogs(returnA);await returnA.evaluate(()=>StudioUI.recovery());await returnA.locator('[data-pending-record]').waitFor();
 check('A pending image is offered for explicit recovery without automatic insertion',await returnA.locator('[data-pending-record]').textContent().then(text=>text.includes('A_PENDING_PRIVATE'))&&await returnA.evaluate(()=>!S.data.capture_inbox?.length&&!S.data.evidence?.length&&S.data.meta.client==='A_SAVED_PRIVATE'));
 await returnA.locator('[data-pending-record]').getByRole('button',{name:'Recuperar formulario',exact:true}).click();await returnA.locator('[data-capture-title]').waitFor();
 check('Explicit recovery restores A text and original image bytes',await returnA.locator('[data-capture-title]').inputValue().then(text=>text==='A_PENDING_PRIVATE')&&await returnA.evaluate(async expected=>{const file=PendingUI.active.get(S.slug+'|capture').read().file;return btoa(String.fromCharCode(...new Uint8Array(await file.arrayBuffer())))===expected;},png.toString('base64')));
 await closeDialogs(returnA);
 // Legacy stores deliberately have no workspace identity. Seed a retained old
 // row and verify automatic recovery does not silently assign or delete it.
 const legacy=await returnA.evaluate(async encoded=>{
   const draft={id:'legacy-tab:shared-project',format:'report-gen-draft',version:1,slug:'shared-project',updated:Date.now()-45*86400000,revision:2,base:JSON.parse(JSON.stringify(S.data)),data:JSON.parse(JSON.stringify(S.data)),etag:projectStore.etag};draft.data.meta.client='LEGACY_UNASSIGNED_PRIVATE';
   await new Promise((resolve,reject)=>{const open=indexedDB.open('report-gen-drafts',1);open.onupgradeneeded=()=>open.result.createObjectStore('drafts',{keyPath:'id'});open.onerror=()=>reject(open.error);open.onsuccess=()=>{const db=open.result,tx=db.transaction('drafts','readwrite');tx.objectStore('drafts').put(draft);tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>reject(tx.error);};});
   const pending={id:'legacy-pending:shared-project:capture',format:'report-gen-pending',version:1,slug:'shared-project',key:'capture',label:'Legacy pending image',etag:projectStore.etag,token:'legacy-image-token',updated:Date.now()-45*86400000,data:{title:'LEGACY_PENDING_PRIVATE',kind:'image',note:'Unassigned old capture'},file:new File([Uint8Array.from(atob(encoded),char=>char.charCodeAt(0))],'legacy-private.png',{type:'image/png'})};pending.bytes=JSON.stringify(pending.data).length+pending.file.size;
   await new Promise((resolve,reject)=>{const open=indexedDB.open('report-gen-pending',1);open.onupgradeneeded=()=>open.result.createObjectStore('pending',{keyPath:'id'});open.onerror=()=>reject(open.error);open.onsuccess=()=>{const db=open.result,tx=db.transaction('pending','readwrite');tx.objectStore('pending').put(pending);tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>reject(tx.error);};});
   return {draft,pending:{...pending,file:{name:pending.file.name,type:pending.file.type,size:pending.file.size}}};
 },png.toString('base64'));
 await returnA.reload();await returnA.waitForFunction(()=>typeof PendingUI!=='undefined'&&!document.getElementById('splash')&&!projectStore.loading&&projectBusyCount===0);await returnA.evaluate(()=>loadProject('shared-project'));await closeDialogs(returnA);
 const current=await records(returnA);
 check('Unassigned legacy copies are excluded from automatic workspace recovery',!JSON.stringify(current.drafts).includes('LEGACY_UNASSIGNED_PRIVATE')&&!JSON.stringify(current.recovery).includes('LEGACY_UNASSIGNED_PRIVATE')&&!JSON.stringify(current.pending).includes('LEGACY_PENDING_PRIVATE')&&!(await returnA.locator('body').textContent()).includes('LEGACY_UNASSIGNED_PRIVATE'));
 // Explicit legacy review selectors are supplied by the production UI contract.
 // The action must reveal/download the retained copy without auto-importing it.
 if(!await returnA.locator('#studioMore').evaluate(node=>node.open))await returnA.locator('#studioMore > summary').click();await returnA.locator('[data-legacy-copies]').click();
 check('Opening legacy recovery initially displays a warning without private records',await returnA.locator('[data-legacy-record]').count()===0&&!(await returnA.locator('dialog[open]').textContent()).includes('LEGACY_UNASSIGNED_PRIVATE'));
 await returnA.locator('[data-legacy-review]').click();await returnA.locator('[data-legacy-record]').first().waitFor();
 check('Legacy private content becomes available only after its explicit review action',(await returnA.locator('dialog[open]').textContent()).includes('LEGACY_UNASSIGNED_PRIVATE')&&await returnA.evaluate(()=>S.data.meta.client==='A_SAVED_PRIVATE'&&!projectStore.dirty));
 const retained=await returnA.evaluate(()=>new Promise((resolve,reject)=>{const open=indexedDB.open('report-gen-drafts',1);open.onerror=()=>reject(open.error);open.onsuccess=()=>{const db=open.result,tx=db.transaction('drafts','readonly'),request=tx.objectStore('drafts').get('legacy-tab:shared-project');request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);tx.oncomplete=()=>db.close();};}));
 check('Reading legacy recovery never deletes, rewrites or assigns the original record',JSON.stringify(retained)===JSON.stringify(legacy.draft));
 const pendingSection=returnA.locator('[data-legacy-record="legacy-pending:shared-project:capture"]');
 const pendingDownload=returnA.waitForEvent('download');await pendingSection.getByRole('button',{name:'Descargar copia privada',exact:true}).click();const jsonFile=await pendingDownload;const jsonPath=path.join(out,'legacy-pending.json');await jsonFile.saveAs(jsonPath);
 const legacyImageDownload=returnA.waitForEvent('download');await pendingSection.getByRole('button',{name:'Descargar imagen original pendiente',exact:true}).click();const imageFile=await legacyImageDownload;const imagePath=path.join(out,'legacy-private.png');await imageFile.saveAs(imagePath);
 check('Explicit legacy downloads preserve pending metadata and every original image byte',JSON.stringify(JSON.parse(fs.readFileSync(jsonPath,'utf8')))===JSON.stringify(legacy.pending)&&fs.readFileSync(imagePath).equals(png));
 const pendingRetained=await returnA.evaluate(async()=>{const rows=await LegacyBrowserCopies.list();const row=rows.find(item=>item.kind==='pending'&&item.row.id==='legacy-pending:shared-project:capture')?.row;return {data:row?.data,workspace_id:row?.workspace_id||null,image:row?.file?btoa(String.fromCharCode(...new Uint8Array(await row.file.arrayBuffer()))):null};});
 check('Legacy image remains unassigned and intact after review and downloads',pendingRetained.data.title==='LEGACY_PENDING_PRIVATE'&&pendingRetained.workspace_id===null&&pendingRetained.image===png.toString('base64'));
 await returnA.screenshot({path:path.join(out,'legacy-review.png'),fullPage:true});
 await returnA.setViewportSize({width:320,height:1000});
 const grown=await returnA.evaluate(()=>{const dialog=document.querySelector('dialog[open]'),before=parseFloat(getComputedStyle(dialog).fontSize);const nodes=[dialog,...dialog.querySelectorAll('*')].map(node=>[node,parseFloat(getComputedStyle(node).fontSize)]);for(const [node,size]of nodes)node.style.fontSize=size*2+'px';return {before,after:parseFloat(getComputedStyle(dialog).fontSize)};});
 const layout=await returnA.evaluate(()=>{const dialog=document.querySelector('dialog[open]'),box=dialog.getBoundingClientRect();return {width:innerWidth,pageWidth:document.documentElement.scrollWidth,dialog:{left:box.left,right:box.right,client:dialog.clientWidth,scroll:dialog.scrollWidth},controls:[...dialog.querySelectorAll('button,input,summary')].filter(node=>node.getClientRects().length).map(node=>{const box=node.getBoundingClientRect();return {left:box.left,right:box.right};})};});
 check('Legacy recovery actions reflow at 320 px with text enlarged to 200%',grown.after===grown.before*2&&layout.pageWidth<=321&&layout.dialog.left>=-1&&layout.dialog.right<=321&&layout.dialog.scroll<=layout.dialog.client+1&&layout.controls.every(node=>node.left>=-1&&node.right<=321),{grown,layout});
 const axeSource=fs.readFileSync(process.env.AXE_CORE_PATH||require.resolve('axe-core/axe.min.js',{paths:[root]}),'utf8');await returnA.evaluate(axeSource);
 const accessibility=await returnA.evaluate(async()=>{const report=await axe.run(document.querySelector('dialog[open]'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa','wcag22aa']}});return {violations:report.violations.map(row=>({id:row.id,nodes:row.nodes.map(node=>node.target)})),incomplete:report.incomplete.map(row=>row.id)};});
 check('Legacy recovery dialog has no automatic accessibility violations',accessibility.violations.length===0,accessibility);
 await returnA.screenshot({path:path.join(out,'legacy-review-mobile-200.png'),fullPage:true});
 await returnA.locator('[data-legacy-record]').last().getByRole('button',{name:'Eliminar esta copia anterior',exact:true}).scrollIntoViewIfNeeded();
 await returnA.locator('dialog[open]').screenshot({path:path.join(out,'legacy-actions-mobile-200.png')});
 check('No page errors or external requests',results.pageErrors.length===0&&results.externalRequests.length===0);save();
 }catch(error){if(currentPage)await currentPage.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw error;}finally{await browser?.close();await stopServer();for(const directory of roots)fs.rmSync(directory,{recursive:true,force:true});}})().catch(error=>{results.error=String(error.stack||error);save();console.error(error);process.exitCode=1;});
