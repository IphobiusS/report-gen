const assert=require('node:assert/strict'),{pathToFileURL}=require('node:url');
let chromium;try{({chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||'playwright'))}catch(_){console.error('Provide Playwright via REPORT_GEN_PLAYWRIGHT_MODULE');process.exit(77)}
let browser,states=0;
(async()=>{try{
 browser=await chromium.launch({executablePath:process.env.REPORT_GEN_CHROMIUM,headless:true,args:['--no-sandbox']});
 // Retain CSS-zoom coverage and add actual text enlargement at each width.
 const modes=[...[320,390,1440].flatMap(width=>[1,2].map(zoom=>({width,zoom}))),
  ...[320,390,1440].map(width=>({width,zoom:1,text200:true}))];
 for(const scripts of[true,false]){
  const context=await browser.newContext({javaScriptEnabled:scripts}),page=await context.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  for(const {width,zoom,text200} of modes){
   await page.setViewportSize({width,height:1000});await page.goto(pathToFileURL(process.argv[2]).href);await page.evaluate(()=>document.fonts.ready);await page.evaluate(z=>document.body.style.zoom=z,zoom);
   if(text200)await page.evaluate(()=>{const nodes=[document.body,...document.body.querySelectorAll('*')],sizes=nodes.map(e=>parseFloat(getComputedStyle(e).fontSize));nodes.forEach((e,i)=>e.style.fontSize=sizes[i]*2+'px');});
   const result=await page.locator('#F01').evaluate(finding=>{
    const field=finding.querySelector('.finding-field'),rect=e=>e.getBoundingClientRect(),pre=field.querySelector('pre'),range=document.createRange();
    range.selectNodeContents(pre);getSelection().removeAllRanges();getSelection().addRange(range);const selected=getSelection().toString();getSelection().removeAllRanges();
    return{pageWidth:document.documentElement.scrollWidth,viewport:innerWidth,text:field.textContent,
     source:pre.textContent,selected,
     nodes:[...field.querySelectorAll('blockquote,ol li')].filter(e=>!e.closest('.report-list-region')).map(e=>({width:rect(e).width,left:rect(e).left,right:rect(e).right})),
     tableRows:[...field.querySelectorAll('table tbody tr')].map(r=>[...r.cells].map(c=>c.textContent))};
   });
   assert.ok(result.pageWidth<=result.viewport+1,`page overflow at ${width}/${zoom}, JS=${scripts}`);
   const brand=await page.locator('.profile-identity').evaluate(e=>{const svg=e.querySelector('svg'),r=svg.getBoundingClientRect(),parent=e.getBoundingClientRect();return{left:r.left,right:r.right,width:r.width,height:r.height,parentLeft:parent.left,parentRight:parent.right,viewBox:svg.viewBox.baseVal.width/svg.viewBox.baseVal.height,label:e.querySelector('.provider-logo').getAttribute('aria-label'),certificate:e.querySelector('.profile-certificate').textContent}});
   assert.ok(brand.left>=brand.parentLeft-1&&brand.right<=brand.parentRight+1&&brand.right<=width+1,`provider logo escapes its cover at ${width}/${zoom}: ${JSON.stringify(brand)}`);
   assert.ok(brand.width/zoom>=80,'provider logo remains large enough to identify');
   assert.ok(Math.abs(brand.width/brand.height-brand.viewBox)<.01,'provider SVG retains its intrinsic aspect ratio');
   assert.ok(brand.label&&brand.certificate,'provider identity and accessible label remain present');
   // Exercise the declared fallback font too: its classification label is
   // wider than the embedded font in a fresh/cold browser context.
   await page.locator('.cover-top').evaluate(e=>e.style.fontFamily='Arial,sans-serif');
   const top=await page.locator('.cover-top').evaluate(e=>({parent:e.getBoundingClientRect().toJSON(),fields:[...e.children].map(n=>{const walker=document.createTreeWalker(n,NodeFilter.SHOW_TEXT),words=[];let text;while(text=walker.nextNode())for(const m of text.textContent.matchAll(/\S+/g)){const range=document.createRange();range.setStart(text,m.index);range.setEnd(text,m.index+m[0].length);words.push({word:m[0],lines:range.getClientRects().length});}return{rect:n.getBoundingClientRect().toJSON(),words};})}));
   assert.ok(top.fields.every(f=>f.rect.left>=top.parent.left-1&&f.rect.right<=top.parent.right+1),'wordmark and classification stay inside cover');
   assert.ok(top.fields.every(f=>f.words.every(w=>w.lines===1)),`cover words wrap unnecessarily at ${width}/${zoom}: ${JSON.stringify(top)}`);
   if(width<=390&&(zoom===2||text200))assert.ok(top.fields[1].rect.top>=top.fields[0].rect.bottom,'cover labels use separate rows when their natural widths do not fit');
   if(width===1440&&zoom===1)assert.equal(top.fields[0].rect.top,top.fields[1].rect.top,'desktop cover labels keep a single row');
   assert.equal(result.nodes.length,9,'two quote levels, three nested list levels and four ordinary-counter items retain native hierarchy');
   assert.ok(result.nodes.every(n=>n.width/zoom>=30&&n.left>=0&&n.right<=width+1),`nested content collapsed at ${width}/${zoom}: ${JSON.stringify(result.nodes)}`);
   for(const marker of['QUOTE-ONE','QUOTE-TWO','LIST-ONE','LIST-TWO','LIST-THREE','TABLE-END','NARRATIVE-END'])assert.ok(result.text.includes(marker),`lost ${marker}`);
   assert.equal(result.source.replace(/\n$/,''),result.selected.replace(/\n$/,''),'visual reflow preserves selected command');
   assert.equal(result.tableRows.length,1);assert.equal(result.tableRows[0].length,8);assert.equal(result.tableRows[0][7],'TABLE-END');
   // Range/element overflow checks cannot see native outside marker glyphs.
   // Measure the loaded font's marker advance against actual list geometry.
   for(const [start,prefix] of [[73,'TWO-DIGIT'],[973,'THREE-DIGIT']]){
    const ordered=page.locator(`#F01 ol[start="${start}"]`);
    const ordinary=await ordered.evaluate(ol=>{
     const box=ol.getBoundingClientRect(),scale=parseFloat(getComputedStyle(document.body).zoom)||1;
     const ctx=document.createElement('canvas').getContext('2d');
     return{start:ol.start,wrapped:!!ol.closest('.report-list-region'),left:box.left,
      items:[...ol.children].map((li,i)=>{const css=getComputedStyle(li,'::marker');
       ctx.font=`${css.fontStyle} ${css.fontWeight} ${css.fontSize} ${css.fontFamily}`;
       return{ordinal:ol.start+i,type:getComputedStyle(li).listStyleType,text:li.textContent.trim(),
        markerLeft:li.getBoundingClientRect().left-ctx.measureText((ol.start+i)+'. ').width*scale};})};
    });
    assert.equal(ordinary.start,start);assert.equal(ordinary.items.length,2);
    assert.equal(ordinary.wrapped,false,'ordinary counters do not require a scroll region');
    assert.deepEqual(ordinary.items.map(i=>i.ordinal),[start,start+1]);
    assert.ok(ordinary.items.every(i=>i.type==='decimal'&&i.text.startsWith(prefix)),'native ordinal semantics and source text are retained');
    assert.ok(ordinary.items.every(i=>i.markerLeft>=0),`ordinary marker leaves the viewport at ${width}/${zoom}, text200=${!!text200}, JS=${scripts}: ${JSON.stringify(ordinary)}`);
    assert.equal(await ordered.getByRole('listitem').count(),2,'native list item roles remain available');
   }
   const counter=page.locator('#F01 .report-list-region');
   const numbers=await counter.evaluate(region=>{
    const ordered=region.querySelector('ol'),first=ordered.children[0],css=getComputedStyle(first),canvas=document.createElement('canvas'),ctx=canvas.getContext('2d');
    ctx.font=`${css.fontStyle} ${css.fontWeight} ${css.fontSize} ${css.fontFamily}`;
    const scale=region.getBoundingClientRect().width/region.offsetWidth;
    return{start:ordered.start,count:ordered.children.length,style:getComputedStyle(first).listStyleType,
     values:[...ordered.children].map(e=>e.textContent),label:region.getAttribute('aria-label'),tab:region.tabIndex,
     // Native outside markers are not DOM range boxes; their measured text
     // must fit the reserved leading space of the scrolling content.
     markerLeft:first.getBoundingClientRect().left-ctx.measureText(ordered.start+'. ').width*scale,
     regionLeft:region.getBoundingClientRect().left,scroll:region.scrollWidth,client:region.clientWidth};
   });
   assert.equal(numbers.start,1234567890);assert.equal(numbers.count,2);assert.equal(numbers.style,'decimal');
   assert.ok(numbers.values[0].startsWith('LARGE-COUNTER-ONE')&&numbers.values[1].startsWith('LARGE-COUNTER-TWO'));
   assert.ok(numbers.markerLeft>=numbers.regionLeft-1,`large native marker escapes its scrollable content: ${JSON.stringify(numbers)}`);
   assert.ok(numbers.label);assert.equal(numbers.tab,0);
   assert.equal(await page.getByRole('list').filter({has:page.getByText('LARGE-COUNTER-ONE retains its complete native number.',{exact:true})}).count(),1,'native list semantics remain available');
   if(width===320&&(zoom===2||text200)){await counter.focus();await page.keyboard.press('ArrowRight');await page.waitForTimeout(150);assert.ok(await counter.evaluate(e=>e.scrollLeft)>0,'oversized native counters remain reachable by keyboard');}
   const region=page.locator('#F01 .report-table-region');
   assert.ok(await region.evaluate(e=>e.scrollWidth>e.clientWidth),'wide table uses a local scrolling region');
   assert.equal(await region.getAttribute('tabindex'),'0');assert.ok(await region.getAttribute('aria-label'));
   if(width===320&&zoom===1){await region.focus();await page.keyboard.press('ArrowRight');await page.waitForTimeout(150);assert.ok(await region.evaluate(e=>e.scrollLeft)>0,'keyboard can reach overflowing columns');}
   states++;
  }
  assert.deepEqual(errors,[]);await context.close();
 }
 console.log(JSON.stringify({states,passed:true,browser:browser.version()}));
}finally{if(browser)await browser.close()}})().catch(error=>{console.error(error);process.exitCode=1});
