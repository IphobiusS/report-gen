/* Portuguese is exercised through production modules and the real Flask API.
   Locale changes must never rewrite authored content or confirm a finding. */
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {JSDOM,VirtualConsole}=require('jsdom');
const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..'));
const read=name=>fs.readFileSync(path.join(root,'webapp/static',name),'utf8');
const workspace='a'.repeat(64);
function transportFixture(language,fetch){
  const ctx=vm.createContext({fetch,Error,URL});
  vm.runInContext(read('drafts.js')+'\n'+read('transport.js')+`\nBrowserWorkspace.bind(${JSON.stringify(workspace)});const client=ReportTransport.create({fetch,workspace:BrowserWorkspace,getLanguage:()=>${JSON.stringify(language)},getETag:()=> '"revision"',baseURL:()=> 'http://localhost/'});`,ctx);
  return expression=>vm.runInContext(expression,ctx);
}
for(const language of ['pt','pt-BR','PT-br'])test(language+': transport sends canonical Portuguese without rewriting the payload',async()=>{
  const calls=[],run=transportFixture(language,async(url,options)=>{calls.push({url,options});return {ok:true,status:200,headers:{get:()=>workspace},json:async()=>({csrf:'token'})};});
  const payload={meta:{lang:'en',title:'Authored Español Português English'},finding:'SELECT * FROM retained;'};
  await run(`client.api.post('/api/projects',${JSON.stringify(payload)})`);
  assert.equal(calls.length,2);
  assert.ok(calls.every(call=>call.options.headers['X-UI-Language']==='pt'));
  assert.deepEqual(JSON.parse(calls[1].options.body),payload);
});
test('Portuguese session and workspace errors preserve transport safety',async()=>{
  const badSession=transportFixture('pt',async()=>({ok:false,status:403,headers:{get:()=>workspace},json:async()=>{throw Error('invalid JSON');}}));
  await assert.rejects(badSession("client.api.post('/api/projects',{})"),/Não foi possível iniciar a sessão local/);
  let count=0;
  const switched=transportFixture('pt',async()=>{count++;return {ok:true,status:200,headers:{get:()=> 'b'.repeat(64)},json:async()=>({})};});
  await assert.rejects(switched("client.api.get('/api/projects')"),/O servidor mudou de espaço de trabalho/);
  await assert.rejects(switched("client.api.post('/api/projects',{})"),/Baixe seu rascunho/);
  assert.equal(count,1,'a blocked workspace cannot send another request');
});
test('Portuguese storage errors use current UI preference rather than report language',()=>{
  const app=read('app.js'),ctx=vm.createContext({Error});
  vm.runInContext(app.slice(0,app.indexOf('// ---- shared transport'))+"\nconst S={uiLang:'pt',data:{meta:{lang:'en'}}};\n"+read('drafts.js'),ctx);
  assert.throws(()=>vm.runInContext('BrowserWorkspace.current()',ctx),/Identidade do espaço de trabalho indisponível/);
  vm.runInContext(`BrowserWorkspace.bind('${workspace}');S.uiLang='en';`,ctx);
  assert.throws(()=>vm.runInContext("BrowserWorkspace.bind('"+'b'.repeat(64)+"')",ctx),/This tab workspace changed/);
});

test('Portuguese modules expose complete labels and preserve the Spanish report through every workspace',async t=>{
  const bridge=require('./flask_transport.cjs')();let dom,pending=0;const errors=[],missing=[],checks=[];
  t.after(()=>{dom?.window.close();bridge.close();});
  const console=new VirtualConsole();console.on('jsdomError',error=>{if(!error.message.includes('HTMLCanvasElement.prototype.getContext'))errors.push(error.message);});
  dom=new JSDOM(read('index.html'),{url:'http://127.0.0.1/',runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:console});
  const win=dom.window,doc=win.document;
  win.fetch=async(...args)=>{pending++;try{return await bridge.fetch(...args);}finally{pending--;}};
  win.AbortController=AbortController;win.AbortSignal=AbortSignal;
  win.structuredClone=structuredClone;win.confirm=()=>true;win.alert=()=>{};
  win.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});
  win.ResizeObserver=class{observe(){}disconnect(){}};
  win.HTMLElement.prototype.scrollIntoView=()=>{};
  win.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  win.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new win.Event('close'));};
  win.HTMLAnchorElement.prototype.click=function(){};win.URL.createObjectURL=()=> 'blob:language-contract';win.URL.revokeObjectURL=()=>{};
  win.localStorage.setItem('rg.previewVisible','0');
  win.__missing=missing;
  const files=[...doc.querySelectorAll('script[src]')].map(el=>path.basename(el.getAttribute('src')));
  win.eval(files.map(read).join('\n')+`\nconst originalUiText=uiText;uiText=function(es,en,pt,language=S.uiLang){if(normalizeUiLanguage(language)==='pt'&&typeof pt!=='string')window.__missing.push({es,en,stack:new Error().stack});return originalUiText(es,en,pt,language);};window.qa={S,projectStore,select,doSave,setUiLang,api,requireOk,refreshProjects,loadProject,InsightsUI,WorkbenchUI,WorkspaceUI,StudioUI,AnnexUI,PrivacyUI,UpdateUI,BulkUI,ProgressUI,BackupRoutineUI};`);
  const q=win.qa;
  async function until(fn){for(let i=0;i<400;i++){if(fn())return;await new Promise(resolve=>setTimeout(resolve,15));}throw Error('UI condition timed out: '+fn);}
  async function settled(){await new Promise(resolve=>setTimeout(resolve,30));await until(()=>pending===0);await new Promise(resolve=>setTimeout(resolve,20));}
  function check(name,condition){assert.ok(condition,name);checks.push(name);}
  function closeDialogs(){doc.querySelectorAll('dialog[open]').forEach(dialog=>dialog.close());}
  await until(()=>doc.querySelector('.workspace-dashboard'));
  const response=await q.requireOk(await q.api.post('/api/demo',{})),created=await response.json();await q.refreshProjects();await q.loadProject(created.slug);await settled();
  const pristine=JSON.stringify(q.S.data),revision=q.projectStore.etag;
  await q.setUiLang('pt-BR');await settled();
  check('canonical selection and document locale',q.S.uiLang==='pt'&&doc.documentElement.lang==='pt-BR');
  check('Portuguese overview controls',doc.querySelector('#navHome').textContent==='Visão geral'&&doc.querySelector('#workspaceBackupBtn').textContent==='Backup do espaço de trabalho');
  q.select('finding',0);await settled();
  check('CVSS metric labels and options are Portuguese',doc.querySelector('.cvss-metrics-title')?.textContent==='Métricas principais'&&doc.querySelector('.cvssbox').textContent.includes('Rede'));
  check('finding verification and status have explicit Portuguese options',[...doc.querySelectorAll('select[data-field="verification"] option')].some(option=>option.textContent==='Não verificado')&&[...doc.querySelectorAll('select[data-field="status"] option')].some(option=>option.textContent==='Aberto'));
  for(const kind of ['review','history','evidence','assets','coverage','root_causes','remediation_tasks','retest','retest_diff','retest_matrix','backup','library']){
    q.select('workflow',kind);await settled();
    const view=doc.querySelector('[data-workflow-view="'+kind+'"]');
    check('workflow renders '+kind,!!view&&view.children.length>0&&!view.querySelector('[role="alert"]'));
  }
  for(const tab of ['claims','risk','review','audiences','visual','editorial']){
    q.InsightsUI.open(tab);await settled();
    const content=doc.querySelector('[data-insights-content]');
    check('decision workspace renders '+tab,!!content&&content.children.length>0&&!content.querySelector('[role="alert"]'));
  }
  q.InsightsUI.open('claims');await settled();
  check('claim helper parameter order is preserved',doc.querySelector('[data-insights-action="save-claim"]').textContent==='Salvar afirmação'&&doc.querySelector('[data-insights-field="kind"]').textContent.includes('Hipótese'));
  q.InsightsUI.open('audiences');await settled();
  const profile=doc.querySelector('[data-insights-field="profile"]');profile.value='public';profile.dispatchEvent(new win.Event('change'));await settled();
  check('public audience consent labels are Portuguese',doc.querySelector('[data-insights-check="review_confirmed"]')?.parentElement.textContent.includes('Revisei o texto')||doc.querySelector('[data-insights-content]').textContent.includes('Revisei o texto'));
  q.select('findings');await settled();q.BulkUI.open();await settled();
  check('bulk assignment has Portuguese labels',doc.querySelector('[data-bulk-dialog]')?.getAttribute('aria-label')==='Editar achados em lote');closeDialogs();
  await q.AnnexUI.open();await settled();check('annex dialog is Portuguese',doc.querySelector('dialog[open]')?.textContent.includes('Inventário de anexos'));closeDialogs();
  await q.PrivacyUI.open();await settled();check('privacy dialog is Portuguese',doc.querySelector('dialog[open]')?.textContent.includes('Dados privados armazenados'));closeDialogs();
  await q.UpdateUI.open();await settled();check('updater consent is Portuguese',doc.querySelector('dialog[open]')?.textContent.includes('Permitir verificação e download do GitHub.'));closeDialogs();
  q.WorkbenchUI.capture();await settled();check('capture form is Portuguese',doc.querySelector('dialog[open]')?.textContent.includes('Captura rápida'));closeDialogs();
  q.ProgressUI.jobs();await settled();check('export drawer is Portuguese',doc.querySelector('#exportDrawer')?.textContent.includes('Exportações'));doc.querySelector('#exportDrawer button')?.click();
  q.select('home');await q.setUiLang('en');await settled();await q.setUiLang('pt');await settled();
  check('changing interface and reading every panel leaves report bytes intact',JSON.stringify(q.S.data)===pristine);
  check('reading and locale changes retain saved revision',q.projectStore.etag===revision&&!q.projectStore.dirty);
  assert.deepEqual(missing,[],'every exercised Portuguese branch has an explicit label');
  assert.deepEqual(errors,[],'no application exceptions while navigating');
  t.diagnostic(JSON.stringify({checks:checks.length,labelsComplete:true,authoredContentPreserved:true}));
});
