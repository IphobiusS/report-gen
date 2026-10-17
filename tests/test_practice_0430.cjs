/* Practice uses the normal save/create/load boundaries and never annotates report data. */
'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync(path.join(__dirname,'../webapp/static/experience.js'),'utf8');
const checks=[];
function check(name,value){assert.ok(value,name);checks.push(name);}
function harness({storage=null}={}){
  const dom=new JSDOM('<!doctype html><body><main id="editor" tabindex="-1"></main><input data-catalog-search></body>',{url:'http://127.0.0.1/',runScripts:'outside-only'});
  const w=dom.window,events=[],models=new Map();
  const real={meta:{report_title:'Customer draft',lang:'es'},findings:[{uid:'real-finding',status:'open',retest:{status:'pending'}}],coverage:[{status:'planned'}],evidence:[{uid:'real-evidence',approval:'pending'}]};
  models.set('customer',real);
  const S={slug:'customer',data:real,projects:[{slug:'customer'}],workspace_id:'workspace-a',uiLang:'es'};
  let save=async()=>true,post=async(_url,{lang})=>({slug:'nimbus-demo-'+String(++index).padStart(12,'0'),lang}),index=0,load=true;
  w.S=S;w.projectStore={loading:false};w.projectBusyCount=0;
  if(storage)Object.defineProperty(w,'localStorage',{value:storage});
  w.uiText=(...values)=>values[{es:0,en:1,pt:2}[S.uiLang]];
  w.h=(tag,attrs={},...children)=>{const node=w.document.createElement(tag);for(const [key,value]of Object.entries(attrs)){if(value!=null)node.setAttribute(key,String(value));}for(const child of children.flat())if(child!=null)node.append(child);return node;};
  w.$=selector=>w.document.querySelector(selector);
  w.toast=(message,kind)=>events.push(['toast',message,kind]);
  w.busyProject=active=>{w.projectBusyCount+=active?1:-1;events.push(['busy',active]);};
  w.doSave=async()=>{events.push(['save',S.slug]);return save();};
  w.api={post:async(url,body)=>{events.push(['post',url,body]);const result=await post(url,body);if(result.slug){const data={meta:{report_title:'Nimbus fictitious',lang:body.lang},findings:[{uid:'practice-finding',status:'open'}]};models.set(result.slug,data);S.projects.push({slug:result.slug,practice:true});}return {json:async()=>result};}};
  w.requireOk=async response=>response;
  w.refreshProjects=async()=>events.push(['refresh']);
  w.loadProject=async slug=>{events.push(['load',slug]);if(load){S.slug=slug;S.data=models.get(slug);}};
  w.select=type=>{S.sel={type};events.push(['select',type]);};
  w.DesignLibraryUI={newProject:async opener=>events.push(['new',opener.dataset.practiceAction])};
  w.eval(source+'\nwindow.ui=ExperienceUI;');
  return {dom,w,S,real,events,models,ui:w.ui,setSave:fn=>{save=fn;},setPost:fn=>{post=fn;},setLoad:value=>{load=value;}};
}
async function settle(){await new Promise(resolve=>setImmediate(resolve));}
(async()=>{
  const x=harness(),{ui,S,w,events}=x,original=JSON.stringify(x.real);
  S.projects.push({slug:'nimbus-demo-abcdef012345',practice:false});
  check('A normal project matching the demo slug is never classified as practice',!ui.isPractice('nimbus-demo-abcdef012345')&&!ui.isPractice('customer'));
  S.projects.push({slug:'verified-copy',practice:true});
  check('Practice identity follows server provenance regardless of its name',ui.isPractice('verified-copy'));
  w.projectStore.loading=true;check('Loading a project blocks another practice request',await ui.createPractice()===false&&events.length===0);w.projectStore.loading=false;
  w.projectBusyCount=1;check('A different busy operation blocks practice creation',await ui.createPractice()===false&&events.length===0);w.projectBusyCount=0;
  x.setSave(async()=>false);
  check('Failed current save prevents practice creation',await ui.createPractice()===false&&!events.some(e=>e[0]==='post')&&S.slug==='customer'&&JSON.stringify(S.data)===original&&w.projectBusyCount===0);
  let release;
  x.setSave(()=>new Promise(resolve=>{release=resolve;}));
  const before=events.filter(e=>e[0]==='save').length,creating=ui.createPractice();
  check('Workspace is busy before awaiting save',w.projectBusyCount===1&&typeof release==='function');
  check('Concurrent entry point creates no second request',await ui.createPractice()===false&&events.filter(e=>e[0]==='save').length===before+1);
  release(true);check('One creation succeeds after save',await creating===true&&events.filter(e=>e[0]==='post').length===1&&w.projectBusyCount===0);
  const first=S.slug;
  check('Practice never changes the source technical state',JSON.stringify(x.real)===original&&S.data!==x.real);
  check('Selected language reaches the existing demo endpoint',events.find(e=>e[0]==='post')[1]==='/api/demo'&&events.find(e=>e[0]==='post')[2].lang==='es');
  const beforeNotice=JSON.stringify(S.data),notice=ui.practiceNotice();w.document.querySelector('#editor').append(notice);
  check('Practice is clearly labeled and offers real project actions',notice.textContent.includes('Proyecto de práctica · Nimbus')&&notice.querySelector('[data-practice-action="return"]')&&notice.querySelector('[data-practice-action="new"]')&&notice.querySelector('[data-practice-action="projects"]'));
  check('Notice is read only',JSON.stringify(S.data)===beforeNotice);
  const guide=w.document.createElement('div');ui.guide(guide);w.document.body.append(guide);[...guide.querySelectorAll('button')].find(button=>button.textContent==='Ocultar guía').click();await settle();
  const hidden=w.document.createElement('div');ui.guide(hidden);
  check('Hiding the legacy walkthrough keeps the fictional label',!hidden.childElementCount&&!!ui.practiceNotice()&&JSON.stringify(S.data)===beforeNotice);
  x.setSave(async()=>false);notice.querySelector('[data-practice-action="return"]').click();await settle();
  check('Failed practice save stops return without losing its draft',S.slug===first&&JSON.stringify(S.data)===beforeNotice&&w.projectBusyCount===0);
  x.setSave(async()=>true);notice.querySelector('[data-practice-action="return"]').click();await settle();
  check('Return reopens the original saved project',S.slug==='customer'&&S.data===x.real&&!ui.practiceNotice());
  S.uiLang='pt';check('A repeated practice is a distinct translated copy',await ui.createPractice()===true&&S.slug!==first&&S.data.meta.lang==='pt');
  const second=S.slug;
  const persisted=Object.fromEntries(Object.keys(w.localStorage).map(key=>[key,w.localStorage.getItem(key)]));
  const y=harness({storage:{getItem:key=>persisted[key]||null,setItem:(key,value)=>{persisted[key]=value;}}});y.S.slug=second;y.S.data=S.data;y.S.projects.push({slug:second,practice:true});
  check('Return target survives a new page instance',!!y.ui.practiceNotice().querySelector('[data-practice-action="return"]'));
  y.S.workspace_id='workspace-b';
  check('Another workspace cannot inherit a return target',!y.ui.practiceNotice().querySelector('[data-practice-action="return"]'));
  y.S.workspace_id='workspace-a';
  check('Returning to the workspace preserves its own target',!!y.ui.practiceNotice().querySelector('[data-practice-action="return"]'));
  for(const [lang,label]of [['es','Proyecto de práctica · Nimbus'],['en','Practice project · Nimbus'],['pt','Projeto de prática · Nimbus']]){S.uiLang=lang;check('Practice notice is localized: '+lang,ui.practiceNotice().textContent.includes(label));}
  const current=JSON.stringify(S.data);ui.practiceNotice().querySelector('[data-practice-action="projects"]').click();await settle();
  check('Project navigation does not alter practice data',S.sel.type==='home'&&JSON.stringify(S.data)===current);
  ui.practiceNotice().querySelector('[data-practice-action="new"]').click();await settle();
  check('New real project uses the normal creation gallery',events.some(e=>e[0]==='new'&&e[1]==='new'));
  x.setPost(async()=>{throw Error('Synthetic API failure');});await assert.rejects(()=>ui.createPractice(),/Synthetic API failure/);
  check('API failure releases the creation guard',w.projectBusyCount===0&&S.slug===second);
  x.setPost(async()=>({slug:'nimbus-demo-abcdef012345'}));x.setLoad(false);await assert.rejects(()=>ui.createPractice(),/could not be opened|no se pudo abrir|não pôde ser aberta/);
  check('A failed load is never reported as success',w.projectBusyCount===0&&S.slug===second);
  for(const [name,storage]of [['denied',{getItem(){throw Error('denied');},setItem(){throw Error('denied');}}],['corrupt',{getItem(){return '{broken';},setItem(){}}]]){
    const z=harness({storage});check('Practice works with '+name+' preference storage',await z.ui.createPractice()===true&&!!z.ui.practiceNotice());
    check('In-session return survives '+name+' storage',!!z.ui.practiceNotice().querySelector('[data-practice-action="return"]'));z.dom.window.close();
  }
  y.dom.window.close();x.dom.window.close();
  console.log(JSON.stringify({passed:checks.length,checks},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
