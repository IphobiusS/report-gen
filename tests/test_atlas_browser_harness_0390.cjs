/* DOM-only regression for the actual Atlas harness and shared navigation helper.
 * This proves activation semantics, not browser layout or keyboard acceptance. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const {exposeNavigationControl,clickNavigationControl}=require('./browser-navigation.cjs');
const source=fs.readFileSync(path.join(__dirname,'../scripts/audit-atlas-browser.cjs'),'utf8');
const between=(start,end)=>{const first=source.indexOf(start),last=source.indexOf(end,first);assert.ok(first>=0&&last>first,'Actual harness function boundaries exist');return source.slice(first,last);};
const functions=between('async function expose(page,selector)','async function closeDrawer(page)')+
  between('async function disclosure(id,open)','async function sidebarGeometry(');
const recoverySource=fs.readFileSync(path.join(__dirname,'../scripts/audit-horizonte-recovery.cjs'),'utf8');
const recoveryStart=recoverySource.indexOf('async function expose(page,selector)'),recoveryEnd=recoverySource.indexOf('async function closeMore(page)',recoveryStart);
assert.ok(recoveryStart>=0&&recoveryEnd>recoveryStart,'Actual recovery harness navigation boundaries exist');
const recoveryFunctions=recoverySource.slice(recoveryStart,recoveryEnd);
const groups=['workspaceResearch','workspaceFollowup','workspaceTools'],checks=[];
async function fixture(width,revealResearch=false){
 const dom=new JSDOM('<button id="sidebarToggle" aria-expanded="false">Navigation</button><aside id="workspaceSidebar">'+
  '<button id="workspaceSections">Sections</button><button id="workspaceFindings">Findings</button>'+
  groups.map(id=>'<details id="'+id+'"><summary>'+id+'</summary><button id="'+id+'Action">Action</button></details>').join('')+'</aside>'+
  '<button id="contextIndexToggle">Index</button><aside id="contextIndex" hidden><button id="contextSectionsTab" aria-pressed="true">Sections</button><button id="contextFindingsTab" aria-pressed="false">Findings</button><ul id="sectionList"></ul><ul id="findingList" hidden></ul><details id="contextIndexActions"><summary>Actions</summary><div id="contextIndexSectionActions"><button id="manageSections">Manage</button></div><div id="contextIndexFindingActions" hidden><button id="importFindingsBtn">Import</button></div></details></aside>');
 const doc=dom.window.document,clicks=[];let mode='sections';
 const render=()=>{
  for(const [key,list] of [['sections','sectionList'],['findings','findingList']]){
   doc.getElementById(list).hidden=mode!==key;
   doc.getElementById(list).innerHTML=mode===key?'<li><button class="finding-nav">'+key+'</button></li>':'';
   doc.getElementById(key==='sections'?'contextSectionsTab':'contextFindingsTab').setAttribute('aria-pressed',String(mode===key));
  }
  doc.getElementById('contextIndexSectionActions').hidden=mode!=='sections';
  doc.getElementById('contextIndexFindingActions').hidden=mode!=='findings';
 };
 const open=next=>{mode=next;doc.getElementById('contextIndex').hidden=false;if(width<=760)doc.getElementById('sidebarToggle').setAttribute('aria-expanded','false');render();};
 doc.querySelector('#sidebarToggle').addEventListener('click',event=>{
  event.currentTarget.setAttribute('aria-expanded','true');doc.querySelector('#contextIndex').hidden=true;
  if(revealResearch)doc.querySelector('#workspaceResearch').open=true;
 });
 for(const [id,next] of [['workspaceSections','sections'],['workspaceFindings','findings'],['contextSectionsTab','sections'],['contextFindingsTab','findings']])doc.getElementById(id).addEventListener('click',()=>open(next));
 doc.getElementById('contextIndexToggle').addEventListener('click',()=>open(mode));render();
 const visible=node=>!!node&&!node.closest('[hidden]')&&!(node.id==='sidebarToggle'&&width>760)&&!(width<=760&&node.closest('#workspaceSidebar')&&doc.querySelector('#sidebarToggle').getAttribute('aria-expanded')!=='true')&&![...doc.querySelectorAll('details:not([open])')].some(details=>details.contains(node)&&node!==details&&node!==details.querySelector(':scope > summary'));
 const page={viewportSize:()=>({width,height:1000}),locator(selector){
  const get=()=>{const node=doc.querySelector(selector);assert.ok(node,'Harness resolves an existing control after opening its collection: '+selector);return node;};
  const locator={first:()=>locator,evaluate:async fn=>fn(get()),getAttribute:async name=>get().getAttribute(name),isVisible:async()=>visible(doc.querySelector(selector)),click:async()=>{const node=get();assert.ok(visible(node),'Harness activates a visible control: '+selector);clicks.push(selector);node.click();}};return locator;
 }};
 const harness=vm.runInNewContext(functions+';({disclosure,expose,click});',{page,assert,exposeNavigationControl,clickNavigationControl});
 const recovery=vm.runInNewContext(recoveryFunctions+';({expose,click});',{assert,exposeNavigationControl,clickNavigationControl});
 return{dom,doc,clicks,harness,recovery,page};
}
(async()=>{
 for(const width of [1440,390]){
  const {dom,doc,clicks,harness,recovery,page}=await fixture(width);
  try{
   for(const id of groups){
    const node=doc.getElementById(id);node.open=false;clicks.length=0;
    await harness.disclosure(id,true);
    assert.equal(node.open,true,id+' remains open after one requested opening');
    assert.equal(clicks.filter(selector=>selector==='#'+id+' > summary').length,1,id+' opens with one summary activation');checks.push(width+' '+id+' opens once');
    clicks.length=0;await harness.disclosure(id,true);assert.equal(node.open,true);assert.equal(clicks.length,0,'Already open disclosure is not toggled');checks.push(width+' '+id+' repeated opening is a no-op');
    clicks.length=0;await harness.disclosure(id,false);assert.equal(node.open,false);assert.deepEqual(clicks,['#'+id+' > summary']);checks.push(width+' '+id+' closes once');
   }
   for(const id of groups){
    clicks.length=0;await harness.click(page,'#'+id+' > summary');assert.equal(doc.getElementById(id).open,true);assert.equal(clicks.filter(selector=>selector.includes('summary')).length,1,'Exposing a summary never activates itself');checks.push(width+' shared helper activates '+id+' summary exactly once');
   }
   assert.equal(doc.querySelector('#findingList li'),null,'Inactive collection has no rows');
   await harness.click(page,'#findingList .finding-nav');assert.equal(doc.querySelector('#contextFindingsTab').getAttribute('aria-pressed'),'true');assert.equal(doc.querySelector('#contextIndex').hidden,false);checks.push(width+' string finding row opens its collection before resolution');
   await harness.click(page,'#sectionList .finding-nav');assert.equal(doc.querySelector('#contextSectionsTab').getAttribute('aria-pressed'),'true');checks.push(width+' string section row changes collection before resolution');
   await harness.click(page,'#importFindingsBtn');assert.equal(doc.querySelector('#contextFindingsTab').getAttribute('aria-pressed'),'true');assert.equal(doc.querySelector('#contextIndexActions').open,true);checks.push(width+' finding action opens its collection and actual disclosure');
   await harness.click(page,'#workspaceSections');await harness.click(page,page.locator('#sectionList .finding-nav'));checks.push(width+' Locator caller explicitly opens its collection');
   doc.querySelector('#workspaceTools').open=false;clicks.length=0;await harness.click(page,'#workspaceToolsAction');assert.equal(clicks.filter(selector=>selector.includes('summary')).length,1);checks.push(width+' nested tool action opens its ancestor once');
   assert.equal(doc.querySelector('#findingList li'),null,'Recovery starts without rendered finding rows');await recovery.click(page,'#findingList .finding-nav');assert.equal(doc.querySelector('#contextFindingsTab').getAttribute('aria-pressed'),'true');assert.equal(doc.querySelector('#contextIndex').hidden,false);checks.push(width+' actual recovery helper opens finding mode before resolving the first row');
  }finally{dom.window.close();}
 }
 const {dom,doc,clicks,harness}=await fixture(390,true);
 try{
  await harness.disclosure('workspaceResearch',false);
  assert.equal(doc.getElementById('workspaceResearch').open,false,'Mobile reveal must not override a requested closed disclosure');
  assert.deepEqual(clicks,['#sidebarToggle','#workspaceResearch > summary']);checks.push('Mobile global navigation opens before deciding the disclosure state');
 }finally{dom.window.close();}
 console.log(JSON.stringify({passed:checks.length,scope:'DOM/VM of actual harness helpers; not real browser acceptance',checks},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
