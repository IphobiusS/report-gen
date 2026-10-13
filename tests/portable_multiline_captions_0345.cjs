'use strict';
const assert=require('node:assert/strict'),{pathToFileURL}=require('node:url');
let chromium;try{({chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||'playwright'))}catch(_){process.exit(77)}
let browser;
(async()=>{try{
 browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM,args:['--no-sandbox']});
 for(const [width,mode]of [[1440,'normal'],[320,'normal'],[320,'text200'],[1440,'print']]){
  const page=await browser.newPage({viewport:{width,height:1000}});await page.goto(pathToFileURL(process.argv[2]).href);await page.evaluate(()=>document.fonts.ready);
  if(mode==='print')await page.emulateMedia({media:'print'});
  if(mode==='text200')await page.evaluate(()=>{const sizes=[...document.querySelectorAll('*')].filter(el=>el instanceof HTMLElement).map(el=>[el,parseFloat(getComputedStyle(el).fontSize),parseFloat(getComputedStyle(el).lineHeight)]);for(const[el,font,line]of sizes){if(font)el.style.fontSize=font*2+'px';if(line)el.style.lineHeight=line*2+'px'}});
  const measure=()=>page.locator('figcaption').evaluateAll(captions=>captions.map(caption=>{const lines=[],walker=document.createTreeWalker(caption,NodeFilter.SHOW_TEXT);let node;while(node=walker.nextNode())for(const match of node.textContent.matchAll(/(?:CAP|TWO)-\d{2}/g)){const r=document.createRange();r.setStart(node,match.index);r.setEnd(node,match.index+match[0].length);lines.push({text:match[0],top:r.getBoundingClientRect().top});}return{whiteSpace:getComputedStyle(caption).whiteSpace,text:caption.textContent,lines}}));
  const captions=await measure();assert.equal(captions.length,3);assert.ok(captions.every(c=>c.whiteSpace==='pre-line'));assert.deepEqual(captions.map(c=>c.lines.length),[0,2,60]);
  for(const caption of captions)assert.ok(caption.lines.every((line,index)=>!index||line.top>caption.lines[index-1].top),'Every explicit line starts below its predecessor');
  assert.equal(await page.locator('figure img').count(),3);assert.ok(await page.locator('figure img').evaluateAll(images=>images.every(i=>i.complete&&i.naturalWidth===480&&i.getBoundingClientRect().width>32)));
  if(width===1440&&mode==='normal'){
   const rule=await page.addStyleTag({content:'figcaption{white-space:normal!important}'}),collapsed=await measure();
   assert.ok(collapsed[2].lines.some((line,index)=>index&&line.top===collapsed[2].lines[index-1].top),'Negative control must detect collapsed authored lines');
   assert.deepEqual(collapsed.map(c=>c.text),captions.map(c=>c.text),'The negative keeps identical text, isolating visual layout');await rule.evaluate(el=>el.remove());
  }
  await page.close();
 }
 console.log('PASS 4 portable caption layouts and visual negative control');
}finally{await browser?.close()}})().catch(e=>{console.error(e);process.exitCode=1});
