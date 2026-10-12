const assert = require('node:assert/strict'), {pathToFileURL} = require('node:url');
let chromium;
try { ({chromium} = require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE || 'playwright')); }
catch (_) { console.error('Provide Playwright via REPORT_GEN_PLAYWRIGHT_MODULE'); process.exit(77); }
let browser;
(async () => {
 try {
  browser = await chromium.launch({executablePath:process.env.REPORT_GEN_CHROMIUM,headless:true,args:['--no-sandbox']});
  const page = await browser.newPage();
  const expected = ['Synthetic bank','review@example.com','Example reviewer','2026-10-12','1.0'];
  for (const mode of [{width:1440,zoom:1,stacked:false},{width:320,zoom:1,stacked:false},
                     {width:320,zoom:2,stacked:true},{width:320,zoom:1,stacked:true,text200:true}]) {
   await page.setViewportSize({width:mode.width,height:1000});
   await page.goto(pathToFileURL(process.argv[2]).href);
   await page.evaluate(() => document.fonts.ready);
   await page.evaluate(zoom => document.body.style.zoom=zoom,mode.zoom);
   if(mode.text200) await page.evaluate(() => {
    const nodes=[document.body,...document.body.querySelectorAll('*')],sizes=nodes.map(e=>parseFloat(getComputedStyle(e).fontSize));
    nodes.forEach((e,i)=>e.style.fontSize=sizes[i]*2+'px');
   });
   const observed = await page.locator('.cover-grid').evaluate(table => ({
    rows:table.rows.length,cells:[...table.querySelectorAll('td')].map(e=>({
     value:e.querySelector('.cv-field-value')?.textContent??null,
     label:e.querySelector('.cv-field-label')?.textContent??null,
     height:e.getBoundingClientRect().height,display:getComputedStyle(e).display,
    })),overflow:document.documentElement.scrollWidth>innerWidth+1,
   }));
   assert.equal(observed.rows,3,'the desktop grid structure retains three authored rows');
   assert.equal(observed.cells.length,6,'the source grid keeps its alignment cell');
   assert.deepEqual(observed.cells.filter(c=>c.value!==null).map(c=>c.value),expected,'all five fields retain reading order');
   assert.ok(observed.cells.filter(c=>c.value!==null).every(c=>c.height>0&&c.label),'no authored field disappears');
   assert.equal(observed.overflow,false,'the complete cover stays in the viewport');
   const blank=observed.cells.find(c=>c.value===null);
   if(mode.stacked) assert.equal(blank.height,0,'a layout-only cell must not reserve a blank stacked row');
   else assert.ok(blank.height>0&&blank.display==='table-cell','desktop and ordinary mobile retain their balanced grid');
   // A cell holding a label is content, even if its value has not been filled.
   await page.locator('.cover-grid td').last().evaluate(e=>{
    e.innerHTML='<span class="cv-field-label">Additional field</span><span class="cv-field-value"></span>';
   });
   assert.ok(await page.locator('.cover-grid td').last().evaluate(e=>e.getBoundingClientRect().height>0),
             'a labelled cell with an empty value is not mistaken for layout padding');
  }
  console.log('4 cover states passed');
 } finally { if(browser) await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
