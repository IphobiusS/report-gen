const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
const fs = require('node:fs'), http = require('node:http');
let chromium;
try { ({chromium} = require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE || 'playwright')); }
catch (_) { console.error('Provide Playwright via REPORT_GEN_PLAYWRIGHT_MODULE or NODE_PATH'); process.exit(77); }
const scenario = process.argv[2], url = pathToFileURL(process.argv[3]).href;
// Native reflow is measurable with script execution disabled as well. RAF
// callbacks do not run in that fallback, so do not await one from page.evaluate.
const settle = page => page.waitForTimeout(20);
const numberRects = cell => cell.evaluate(el => {
  const range = document.createRange();range.selectNodeContents(el);
  return [...range.getClientRects()].filter(r => r.width > 0 && r.height > 0).map(r => ({width:r.width,top:r.top}));
});
let browser, streamServer;
const streamResponses=new Set();
async function streamingContract() {
 const body=fs.readFileSync(process.argv[3],'utf8');
 const cut=body.indexOf('</section>',body.indexOf('<main>'))+10;
 assert.ok(cut>10,'stream split includes the complete cover');
 const gates=new Map();let gateSequence=0;
 streamServer=http.createServer((request,response)=>{
   const requested=new URL(request.url,'http://127.0.0.1');
   if(requested.pathname!=='/report.html') {response.writeHead(404);response.end();return;}
   const token=requested.searchParams.get('gate'),gate=token?gates.get(token):null;
   if(token&&!gate) {response.writeHead(404);response.end();return;}
   response.writeHead(200,{'Content-Type':'text/html;charset=utf-8','Cache-Control':'no-store'});
   response.write(body.slice(0,cut));
   if(gate) {
     gate.response=response;streamResponses.add(response);
     response.on('close',()=>streamResponses.delete(response));
   } else response.end(body.slice(cut));
 });
 await new Promise(resolve=>streamServer.listen(0,'127.0.0.1',resolve));
 const streamed='http://127.0.0.1:'+streamServer.address().port+'/report.html';
 for(const width of [390,1366]) {
  const token='stream-'+width+'-'+(++gateSequence),gate={response:null};gates.set(token,gate);
  const context=await browser.newContext({viewport:{width,height:900}});
  const page=await context.newPage(),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{
   window.reportShifts=[];
   new PerformanceObserver(list=>{
     for(const entry of list.getEntries())if(!entry.hadRecentInput)window.reportShifts.push(entry.value);
   }).observe({type:'layout-shift',buffered:true});
  });
  await page.goto(streamed+'?gate='+token,{waitUntil:'commit'});
  await page.locator('main .cover').waitFor();
  // The embedded font deliberately replaces fallback text (font-display:swap).
  // Measure activation after that independent font phase, while the response
  // is still held open. A font metric change is not movement caused by wiring
  // the reading controls; their reserved geometry must remain unchanged.
  await page.evaluate(async()=>{
    await document.fonts.ready;
    await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
    window.reportFontPhaseCLS=window.reportShifts.reduce((sum,value)=>sum+value,0);
    window.reportShifts=[];
  });
  const initial=await page.locator('.report-toolbar').evaluate(el=>({
    height:el.getBoundingClientRect().height,visibility:getComputedStyle(el).visibility,hidden:el.hidden,
    contentTop:document.querySelector('.report-content').getBoundingClientRect().top}));
  assert.ok(initial.height>=44,`toolbar does not reserve space while streaming at ${width}`);
  assert.equal(initial.visibility,'hidden','unwired controls remain invisible during download');
  assert.equal(initial.hidden,true);
  assert.ok(gate.response&&!gate.response.writableEnded,'response stays open until the initial state is checked');
  gate.response.end(body.slice(cut));gates.delete(token);
  await page.waitForLoadState('load');await page.evaluate(()=>document.fonts.ready);await settle(page);
  const final=await page.locator('.report-toolbar').evaluate(el=>({
    height:el.getBoundingClientRect().height,visibility:getComputedStyle(el).visibility,hidden:el.hidden,
    contentTop:document.querySelector('.report-content').getBoundingClientRect().top}));
  assert.ok(Math.abs(final.height-initial.height)<=1,'readiness keeps the reserved toolbar height');
  assert.equal(final.hidden,false);assert.equal(final.visibility,'visible');
  assert.ok(Math.abs(final.contentTop-initial.contentTop)<=1,'activating controls does not move the report');
  const cls=await page.evaluate(()=>window.reportShifts.reduce((sum,value)=>sum+value,0));
  assert.ok(cls<=.01,`activating controls moves the report at ${width}: CLS=${cls}`);
  console.log(JSON.stringify({width,fontPhaseCLS:await page.evaluate(()=>window.reportFontPhaseCLS),activationCLS:cls}));
  await page.locator('#query').fill('no-matching-sentinel');
  assert.equal(await page.locator('#empty-results').isVisible(),true,'visible controls have their listeners');
  assert.deepEqual(errors,[],'both inline scripts execute under their hashes');
  await context.close();
 }
 const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:900}});
 const page=await nojs.newPage();await page.goto(streamed);
 assert.equal(await page.locator('.report-toolbar').evaluate(el=>el.getBoundingClientRect().height),0,
   'without JavaScript the toolbar leaves no reserved gap');
 assert.equal(await page.locator('#F01').isVisible(),true);
 await nojs.close();
}
(async () => {
 browser = await chromium.launch({executablePath:process.env.REPORT_GEN_CHROMIUM,headless:true,args:['--no-sandbox']});
 if(scenario==='streaming') {
   await streamingContract();console.log(JSON.stringify({scenario,passed:true,browser:browser.version()}));return;
 }
 const context = await browser.newContext({viewport:{width:1366,height:850},reducedMotion:'reduce'});
 const page = await context.newPage(), errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(url);await page.evaluate(()=>document.fonts.ready);await settle(page);
 const fallbackContext = await browser.newContext({javaScriptEnabled:false,viewport:{width:320,height:850}});
 const fallback = await fallbackContext.newPage();await fallback.goto(url);await fallback.evaluate(()=>document.fonts.ready);
 for (const [name,p] of [['normal',page],['nojs',fallback]]) {
  if (scenario === 'fields') {
   for (const width of [1366,320,390]) {
    await p.setViewportSize({width,height:850});await settle(p);
    const titleRects=await p.locator('#F01 h2.f-title').evaluate(el=>{
      const word='Autoaprobación',walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);
      for(let node;node=walker.nextNode();) {
        const start=node.textContent.indexOf(word);if(start<0)continue;
        const range=document.createRange();range.setStart(node,start);range.setEnd(node,start+word.length);
        return [...range.getClientRects()].filter(r=>r.width>0&&r.height>0).length;
      }
      return 0;
    });
    assert.equal(titleRects,1,`${name}: mobile heading splits Autoaprobación inside the word at ${width}`);
    const dimensions = await p.locator('#F01 table.meta').evaluate(table => {
      const row=[...table.tBodies[0].rows].find(r=>r.cells[1]?.textContent.includes('srv.example.test'));
      const label=row.cells[0].getBoundingClientRect(),value=row.cells[1].getBoundingClientRect();
      return {table:table.getBoundingClientRect().width,label:{width:label.width,bottom:label.bottom},
              value:{width:value.width,top:value.top},role:table.getAttribute('role'),
              scope:row.cells[0].getAttribute('scope'),labelRole:row.cells[0].getAttribute('role')};
    });
    if (width>600) {
      assert.ok(dimensions.label.width<=240,`${name}: excessive field label at ${width}: ${JSON.stringify(dimensions)}`);
      assert.ok(dimensions.value.width>=dimensions.label.width*2,`${name}: value is starved at ${width}: ${JSON.stringify(dimensions)}`);
    } else {
      assert.ok(dimensions.value.width>=dimensions.table-2,`${name}: mobile value does not use table width: ${JSON.stringify(dimensions)}`);
      assert.ok(dimensions.value.top>=dimensions.label.bottom-2,`${name}: field value is not stacked below its label`);
    }
    assert.equal(dimensions.role,'table','stacked fields retain explicit native table role');
    assert.equal(dimensions.scope,'row');assert.equal(dimensions.labelRole,'rowheader');
    assert.ok(await p.getByRole('table').count()>=2,'table remains in the accessibility tree');
    assert.ok(await p.getByRole('rowheader').count()>=2,'row labels remain accessible');
    const narrative=await p.locator('#F01 .finding-field').first().evaluate(el=>{
      const finding=el.closest('.finding'),style=getComputedStyle(finding);
      return {nestedInTable:!!el.closest('table'),width:el.getBoundingClientRect().width,
        findingWidth:finding.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight),
        prose:el.querySelector('p')?.textContent,heading:el.querySelector('h3')?.textContent};});
    assert.equal(narrative.nestedInTable,false,'narrative is not an indivisible metadata row');
    assert.ok(narrative.width>=narrative.findingWidth-2,'narrative uses the available finding width');
    assert.ok(narrative.prose?.includes('Descripción con una tabla comparativa.'));
    assert.ok(narrative.heading?.trim(),'narrative retains its visible field heading');
    assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no page overflow');
   }
  } else if (scenario === 'comparison') {
   for (const width of [320,390,1366]) {
    await p.setViewportSize({width,height:850});await settle(p);
    const table=p.locator('xpath=//table[thead/tr/th[normalize-space(.)="Inherente"]]');
    const region=table.locator('..');
    const expression=table.locator('tbody tr').first().locator('td').nth(1);
    assert.equal((await expression.textContent()).trim(),'4×5=20');
    assert.equal((await numberRects(expression)).length,1,`${name}: risk expression breaks across lines at ${width}`);
    assert.equal(await region.getAttribute('role'),'region','wide table has a semantic scroll region');
    assert.equal(await region.getAttribute('tabindex'),'0','scroll region can receive keyboard focus');
    assert.ok((await region.getAttribute('aria-label'))?.trim(),'scroll region has a readable name');
    const bounds=await region.evaluate(el=>({width:el.clientWidth,content:el.scrollWidth,overflow:getComputedStyle(el).overflowX}));
    assert.equal(bounds.overflow,'auto','table can scroll locally');
    if(width===320) {
      assert.ok(await region.evaluate(el=>getComputedStyle(el,'::before').content.includes(el.dataset.scrollHint)),
        'mobile scrolling instruction is visibly rendered without adding report prose');
      assert.ok(bounds.content>bounds.width,'mobile comparison has genuinely scrollable columns');
      await region.focus();await p.keyboard.press('ArrowRight');await p.waitForTimeout(200);
      assert.ok(await region.evaluate(el=>el.scrollLeft)>0,'arrow key moves the focused scroll region');
      assert.equal(await region.evaluate(el=>getComputedStyle(el).outlineStyle),'solid','keyboard focus is visible');
    }
    const twoColumns=p.locator('xpath=//table[thead/tr/th[normalize-space(.)="Dimensión"]]');
    const twoRegion=twoColumns.locator('..');
    for (const [row,word] of [[0,'Disponibilidad'],[1,'Fraude']]) {
      const cell=twoColumns.locator('tbody tr').nth(row).locator('td').first();
      assert.equal((await cell.textContent()).trim(),word);
      assert.equal((await numberRects(cell)).length,1,`${name}: two-column data splits ${word} at ${width}`);
    }
    assert.equal(await twoRegion.getAttribute('role'),'region','two-column data has a semantic scroll region');
    assert.equal(await twoRegion.getAttribute('tabindex'),'0','two-column data scrolls by keyboard');
    assert.ok((await twoRegion.getAttribute('aria-label'))?.trim(),'two-column region has a readable name');
    if(width===320) {
      assert.ok(await twoRegion.evaluate(el=>el.scrollWidth>el.clientWidth),'two-column data can scroll locally');
      await twoRegion.focus();await p.keyboard.press('ArrowRight');await p.waitForTimeout(200);
      assert.ok(await twoRegion.evaluate(el=>el.scrollLeft)>0,'arrow key moves the two-column region');
    }
    assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'scrolling table does not overflow the page');
   }
  } else throw Error('Unknown scenario '+scenario);
  // Printing restores the native layout and removes the screen-only width floor.
  await p.emulateMedia({media:'print'});
  for (const width of [794,320]) {
   await p.setViewportSize({width,height:1123});await settle(p);
   const printing=await p.evaluate(()=>({
    fields:[...document.querySelectorAll('table.report-fields')].map(t=>getComputedStyle(t).display),
    regions:[...document.querySelectorAll('.report-table-region')].map(r=>({overflow:getComputedStyle(r).overflowX,
      width:r.getBoundingClientRect().width,table:r.querySelector('table').getBoundingClientRect().width})),
    width:document.documentElement.scrollWidth,viewport:innerWidth
   }));
   assert.ok(printing.fields.every(display=>display==='table'),'print retains native field tables');
   assert.ok(printing.regions.every(r=>r.overflow==='visible'&&r.table<=r.width+1),
     `${name}: print expands every table inside its page width at ${width}: ${JSON.stringify(printing)}`);
   assert.ok(printing.width<=printing.viewport,'print content is not horizontally clipped');
   assert.ok(await p.locator('#F01').isVisible(),'all finding content remains printable');
  }
 }
 assert.deepEqual(errors,[],'actual portable CSP and script remain valid');
 console.log(JSON.stringify({scenario,passed:true,browser:browser.version()}));
 await context.close();await fallbackContext.close();
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{
 await browser?.close();
 for(const response of streamResponses)response.destroy();streamResponses.clear();
 streamServer?.closeAllConnections();streamServer?.close();
});
