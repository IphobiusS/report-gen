const assert=require('node:assert/strict'),{pathToFileURL}=require('node:url');
let chromium;try{({chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||'playwright'))}catch(_){console.error('Provide Playwright via REPORT_GEN_PLAYWRIGHT_MODULE');process.exit(77)}
let browser,states=0;
(async()=>{try{
 browser=await chromium.launch({executablePath:process.env.REPORT_GEN_CHROMIUM,headless:true,args:['--no-sandbox']});
 for(const scripts of[true,false]){
  const context=await browser.newContext({javaScriptEnabled:scripts}),page=await context.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  for(const mode of [...[320,375,768,1440].flatMap(width=>[1,2].map(zoom=>({width,zoom}))),{width:320,zoom:1,text200:true},{width:1440,zoom:1,text200:true}]){
   const{width,zoom}=mode,factor=mode.text200?2:1;
   await page.setViewportSize({width,height:1000});await page.goto(pathToFileURL(process.argv[2]).href);await page.evaluate(()=>document.fonts.ready);await page.evaluate(z=>document.body.style.zoom=z,zoom);if(mode.text200)await page.evaluate(()=>{const nodes=[document.body,...document.body.querySelectorAll('*')],sizes=nodes.map(e=>parseFloat(getComputedStyle(e).fontSize));for(let i=0;i<nodes.length;i++)nodes[i].style.fontSize=sizes[i]*2+'px';});
   const coverImages=await page.locator('.cover img').evaluateAll(es=>es.map(e=>{const r=e.getBoundingClientRect(),parent=e.parentElement.getBoundingClientRect();return{left:r.left,right:r.right,width:r.width,height:r.height,parentLeft:parent.left,parentRight:parent.right,ratio:e.naturalWidth/e.naturalHeight,loaded:e.complete&&e.naturalWidth>0};}));
   assert.equal(coverImages.length,3,'logo, client logo and cover art remain present');
   assert.ok(coverImages.every(im=>im.loaded&&im.width>0&&im.left>=im.parentLeft-1&&im.right<=im.parentRight+1&&im.right<=width+1),`custom branding escapes its cover at ${width}/${zoom}: ${JSON.stringify(coverImages)}`);
   assert.ok(coverImages.every(im=>Math.abs(im.width/im.height-im.ratio)<.001),'all three branding images retain intrinsic aspect ratios');
   const coverFields=await page.locator('.cover .cv-field-value').evaluateAll(es=>es.map(e=>({text:e.textContent,width:e.getBoundingClientRect().width,display:getComputedStyle(e.parentElement).display,tag:e.parentElement.tagName})));
   assert.deepEqual(coverFields.map(e=>e.text),['Bank client','Report reviewer','2026-10-11','1.0'],'all cover metadata values retain reading order');
   if(width/zoom<=190||mode.text200&&width===320)assert.ok(coverFields.every(e=>e.width>=width*.7&&e.display==='block'&&e.tag==='TD'),`cover metadata columns consume readable space at ${width}/${zoom}: ${JSON.stringify(coverFields)}`);
   const result=await page.locator('#F01').evaluate(finding=>{
    const scale=parseFloat(document.body.style.zoom),box=e=>e.getBoundingClientRect().width/scale;
    const title=finding.querySelector('.f-title'),caption=finding.querySelector('figcaption'),description=finding.querySelector('.finding-field'),code=finding.querySelector('pre'),remediation=finding.querySelector('.remsum dd');
    const walker=document.createTreeWalker(title,NodeFilter.SHOW_TEXT),words=[];let text;
    while(text=walker.nextNode())for(const m of text.textContent.matchAll(/\b[A-Za-z]{3,8}\b/g)){const r=document.createRange();r.setStart(text,m.index);r.setEnd(text,m.index+m[0].length);words.push({word:m[0],lines:r.getClientRects().length});}
    const selection=document.createRange();selection.selectNodeContents(code);getSelection().removeAllRanges();getSelection().addRange(selection);const selected=getSelection().toString();getSelection().removeAllRanges();
    return{page:document.documentElement.scrollWidth,viewport:innerWidth,effective:innerWidth/scale,
      title:{width:box(title),font:parseFloat(getComputedStyle(title).fontSize),words},
      caption:{width:box(caption),font:parseFloat(getComputedStyle(caption).fontSize)},
      description:{width:box(description),font:parseFloat(getComputedStyle(description).fontSize)},
      remediation:box(remediation),code:code.textContent,selected,
      codeRight:code.querySelector('code').getBoundingClientRect().right,
      anchors:[...finding.querySelectorAll('a[href]')].map(a=>[a.textContent,a.getAttribute('href')]),
      image:[finding.querySelector('img').getBoundingClientRect().width,finding.querySelector('img').getBoundingClientRect().height],
      table:[...finding.querySelector('table.report-data').rows].map(r=>[...r.cells].map(c=>c.textContent)),
      fields:[...finding.querySelectorAll('.report-fields tr')].map(r=>[...r.cells].map(c=>({role:c.getAttribute('role'),display:getComputedStyle(c).display}))),
      list:[...finding.querySelectorAll('.finding-field ol')].map(e=>({start:e.start,style:getComputedStyle(e).listStyleType,width:box(e)}))};
   });
   assert.ok(result.page<=result.viewport+1,`page overflow ${width}/${zoom}`);
   assert.equal(result.caption.font,17*factor,'caption is not shrunk to force it into a narrow box');
   assert.equal(result.description.font,17*factor,'narrative font remains readable');
   assert.equal(result.title.font,(width<=600?22.4:26.4)*factor,'heading font remains unchanged');
   if(width/zoom<=190||mode.text200&&width===320){
    assert.ok(result.title.width>=result.effective*.75,`nested frames consume the heading line at ${width}/${zoom}: ${JSON.stringify(result.title)}`);
    assert.ok(result.caption.width>=result.effective*.7,`step inset consumes the caption line at ${width}/${zoom}: ${JSON.stringify(result.caption)}`);
    assert.ok(result.remediation>=result.effective*.7,`definition indent consumes the remedy line at ${width}/${zoom}: ${result.remediation}`);
    assert.ok(result.title.words.every(w=>w.lines===1),`ordinary heading words split at ${width}/${zoom}: ${JSON.stringify(result.title.words)}`);
   }
   assert.ok(result.codeRight<=width+1,'preserved tabs stay within the reading area');
   assert.equal(result.code.replace(/\n$/,''),result.selected.replace(/\n$/,''),'selected command remains literal');
   assert.ok(result.anchors.every(([label,href])=>label===href),'literal URLs preserve exact labels and targets');
   assert.equal(result.image[0]/result.image[1],2,'image retains its source aspect ratio');
   assert.deepEqual(result.table,[['ID','Owner','Decision'],['F01','Treasury','TABLE-END']]);
   assert.deepEqual(result.list.map(l=>[l.start,l.style]),[[1,'decimal'],[1,'decimal'],[1,'decimal']]);
   if(width/zoom<=600)assert.ok(result.fields.every(r=>r.every(c=>c.display==='block')),'metadata remains stacked');
   if(scripts&&width/zoom<=600)assert.equal(await page.locator('.report-toolbar').evaluate(e=>getComputedStyle(e).position),'static','a narrow enlarged page must not reserve a sticky control panel');
   states++;
  }
  await page.goto(pathToFileURL(process.argv[2]).href);await page.emulateMedia({media:'print'});
  assert.equal(await page.locator('.report-toolbar').isVisible(),false,'reading controls are absent from print');
  assert.equal(await page.locator('#F01').evaluate(e=>getComputedStyle(e).paddingLeft),'0px','screen-only compact framing must not leak into print');
  assert.deepEqual(errors,[]);await context.close();
 }
 console.log(JSON.stringify({states,passed:true,browser:browser.version()}));
}finally{if(browser)await browser.close()}})().catch(error=>{console.error(error);process.exitCode=1});
