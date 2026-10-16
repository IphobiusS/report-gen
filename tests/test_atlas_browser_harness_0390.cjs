/* DOM-only regression for the actual Atlas harness. No browser is launched. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {JSDOM}=require('jsdom');
const source=fs.readFileSync(path.join(__dirname,'../scripts/audit-atlas-browser.cjs'),'utf8');
const between=(start,end)=>source.slice(source.indexOf(start),source.indexOf(end,source.indexOf(start)));
const functions=between('async function expose(page,selector)','async function closeDrawer(page)')+
  between('async function disclosure(id,open)','async function sidebarGeometry(');
const groups=['workspaceSections','workspaceFindings','workspaceResearch','workspaceFollowup','workspaceTools'];
const checks=[];
async function fixture(width){
 const dom=new JSDOM('<button id="sidebarToggle" aria-expanded="false">Navigation</button><aside id="workspaceSidebar">'+
  groups.map(id=>'<details id="'+id+'"><summary>'+id+'</summary><button>Action</button></details>').join('')+'</aside>');
 const doc=dom.window.document,clicks=[];
 doc.querySelector('#sidebarToggle').addEventListener('click',event=>{
  event.currentTarget.setAttribute('aria-expanded','true');
  // The application reveals its current index when mobile navigation opens.
  doc.querySelector('#workspaceFindings').open=true;
 });
 const page={viewportSize:()=>({width,height:1000}),locator(selector){
  const node=doc.querySelector(selector);assert.ok(node,'Harness addresses an existing control: '+selector);
  const locator={first:()=>locator,evaluate:async fn=>fn(node),getAttribute:async name=>node.getAttribute(name),
   click:async()=>{clicks.push(selector);node.click();}};return locator;
 }};
 const harness=vm.runInNewContext(functions+';({disclosure});',{page,assert});
 return{dom,doc,clicks,harness};
}
(async()=>{
 for(const width of [1440,390]){
  const {dom,doc,clicks,harness}=await fixture(width);
  try{
   for(const id of groups){
    const node=doc.getElementById(id);node.open=false;clicks.length=0;
    await harness.disclosure(id,true);
    assert.equal(node.open,true,id+' must remain open after one requested opening');
    assert.equal(clicks.filter(selector=>selector==='#'+id+' > summary').length,1,id+' opens with one summary activation');
    checks.push(width+' '+id+' opens once');
    clicks.length=0;await harness.disclosure(id,true);
    assert.equal(node.open,true);assert.equal(clicks.length,0,'An already open disclosure is not toggled');
    checks.push(width+' '+id+' repeated opening is a no-op');
    clicks.length=0;await harness.disclosure(id,false);
    assert.equal(node.open,false);assert.deepEqual(clicks,['#'+id+' > summary']);
    checks.push(width+' '+id+' closes once');
   }
  }finally{dom.window.close();}
 }
 const {dom,doc,clicks,harness}=await fixture(390);
 try{
  await harness.disclosure('workspaceFindings',false);
  assert.equal(doc.getElementById('workspaceFindings').open,false,'Mobile selection auto-reveal must not override the requested closed state');
  assert.deepEqual(clicks,['#sidebarToggle','#workspaceFindings > summary']);
  checks.push('Mobile navigation is opened before deciding whether to toggle the current index');
 }finally{dom.window.close();}
 console.log(JSON.stringify({passed:checks.length,scope:'DOM/VM of actual harness helpers; not real browser acceptance',checks},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
