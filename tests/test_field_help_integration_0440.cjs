/* Field guidance must be attached to real views and preserve working report content. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {isDeepStrictEqual}=require('node:util'),{JSDOM}=require('jsdom');
const transport=require('./flask_transport.cjs')(),root=path.resolve(__dirname,'..'),checks=[];
const check=(name,value)=>{assert.ok(value,name);checks.push(name);};
const plain=value=>JSON.parse(JSON.stringify(value));
const equal=(left,right)=>isDeepStrictEqual(plain(left),plain(right));
async function until(predicate){for(let i=0;i<800;i++){if(predicate())return;await new Promise(resolve=>setTimeout(resolve,25));}throw Error('UI timeout: '+predicate);}
let dom;
(async()=>{
  const html=fs.readFileSync(path.join(root,'webapp/static/index.html'),'utf8');
  dom=new JSDOM(html,{url:'http://127.0.0.1/',runScripts:'outside-only',pretendToBeVisual:true});
  const w=dom.window,doc=w.document,errors=[],writes=[];let pending=0;
  w.addEventListener('error',event=>errors.push(event.message));
  w.fetch=(url,options={})=>{pending++;if(!['GET','HEAD'].includes(options.method||'GET'))writes.push({url:String(url),method:options.method});return transport.fetch(url,options).finally(()=>pending--);};
  w.confirm=()=>true;w.alert=()=>{};w.structuredClone=structuredClone;w.AbortController=AbortController;w.AbortSignal=AbortSignal;
  w.CSS={escape:value=>Array.from(String(value),character=>'\\'+character.codePointAt(0).toString(16)+' ').join('')};
  w.matchMedia=()=>({matches:false,addEventListener(){},removeEventListener(){}});
  w.ResizeObserver=class{observe(){}disconnect(){}};w.HTMLElement.prototype.scrollIntoView=()=>{};
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;this.querySelector('button')?.focus();};
  w.HTMLDialogElement.prototype.close=function(){this.open=false;this.dispatchEvent(new w.Event('close'));};
  w.HTMLAnchorElement.prototype.click=function(){};w.URL.createObjectURL=()=> 'blob:field-help-integration';w.URL.revokeObjectURL=()=>{};
  w.localStorage.setItem('rg.previewVisible','0');
  const sources=[...html.matchAll(/<script src="\/static\/([^"/]+)"/g)].map(match=>fs.readFileSync(path.join(root,'webapp/static',match[1]),'utf8'));
  w.eval(sources.join('\n')+'\nwindow.qa={S,projectStore,api,requireOk,select,setUiLang,loadProject,refreshProjects,doSave,scheduleSave};');
  const q=w.qa;
  const settle=async()=>{await until(()=>pending===0&&!q.projectStore.loading);await new Promise(resolve=>w.requestAnimationFrame(resolve));await until(()=>pending===0);};
  const snapshot=()=>plain({slug:q.S.slug,data:q.S.data,etag:q.projectStore.etag,revision:q.projectStore.revision,dirty:q.projectStore.dirty});
  await until(()=>doc.querySelector('.workspace-dashboard')&&doc.getElementById('onboardingMode'));await settle();
  await q.requireOk(await q.api.post('/api/projects',{slug:'field-help-integration',title:'Fictional field-help regression'}));
  await q.refreshProjects();await q.loadProject('field-help-integration');await settle();
  q.S.data.findings=[{uid:'12345678-1234-4234-8234-123456789012',id:'F1',mode:'vuln',title:'Fictional observation',description_md:'Pending technical description.',impact_md:'Bounded impact.',remediation_md:'Adapted correction.',verification:'unverified',status:'open',walkthrough:[]}];
  q.scheduleSave();assert.ok(await q.doSave());await settle();
  for(const lang of ['es','en','pt']){
    q.setUiLang(lang);q.select('finding',0);await settle();
    const description=doc.querySelector('[data-field="description_md"]'),snapshotBefore=snapshot();description.focus();description.setSelectionRange(2,8);writes.length=0;
    for(const key of ['description_md','impact_md','severity','remediation_md','evidence','closure_criteria_md']){
      const node=doc.querySelector('[data-help="'+key+'"]');check(lang+' '+key+' is attached to the real finding editor',!!node);
      node.open=true;node.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));check(lang+' '+key+' closes without rebuilding the editor',!node.open&&doc.querySelector('[data-field="description_md"]')===description);
    }
    await settle();check(lang+' opening field help leaves exact model, revision and ETag unchanged',equal(snapshotBefore,snapshot())&&writes.length===0&&description.selectionStart===2&&description.selectionEnd===8);
    const scopeKey=Object.keys(q.S.catBy).find(key=>q.S.catBy[key].special==='scope');assert.ok(scopeKey,'Scope schema exists');q.select('section',scopeKey);await settle();
    check(lang+' scope guidance is attached to the actual scope target editor',!!doc.querySelector('[data-help="scope"]')&&!!doc.querySelector('.list-card,.card'));
    q.select('workflow','coverage');await until(()=>doc.querySelector('[data-help="limitations_md"]'));await settle();check(lang+' limitations guidance is attached to its actual Markdown textarea',!!doc.querySelector('[data-field="limitations_md"]')&&!!doc.querySelector('[data-help="limitations_md"]'));
  }
  check('No runtime errors in real field help integration',errors.length===0);
  console.log(JSON.stringify({passed:checks.length,checks,scope:'Eight guidance topics mounted in real application views with Flask bridge, ES/EN/PT; model and ETag preservation'},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(()=>{dom?.window.close();transport.close();});
