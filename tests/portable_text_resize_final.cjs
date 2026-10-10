const assert=require('node:assert/strict'),{pathToFileURL}=require('node:url');
let chromium;try{({chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||'playwright'))}catch(e){console.error('Provide Playwright via REPORT_GEN_PLAYWRIGHT_MODULE');process.exit(77)}
let browser;let states=0;
(async()=>{try{browser=await chromium.launch({executablePath:process.env.REPORT_GEN_CHROMIUM,headless:true,args:['--no-sandbox']});
for(const scripts of [true,false]){const c=await browser.newContext({javaScriptEnabled:scripts});const p=await c.newPage();
for(const width of [280,320,390,600,768,1024,1366])for(const mode of ['normal','rem400','text200']){
await p.setViewportSize({width,height:900});await p.goto(pathToFileURL(process.argv[2]).href);await p.evaluate(()=>document.fonts.ready);
if(mode==='rem400')await p.evaluate(()=>document.documentElement.style.fontSize='400%');
if(mode==='text200')await p.evaluate(()=>{const els=[document.body,...document.body.querySelectorAll('*')],sizes=els.map(e=>parseFloat(getComputedStyle(e).fontSize));for(let i=0;i<els.length;i++)els[i].style.fontSize=2*sizes[i]+'px'});
await p.waitForTimeout(20);
assert.ok(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`page overflow at ${width}, ${mode}, scripts=${scripts}`);
assert.equal(await p.locator('#F01').isVisible(),true);
assert.equal(await p.locator('#F01 table.meta').getAttribute('role'),'table');
assert.ok(await p.getByRole('rowheader').count()>=3);
assert.ok((await p.locator('#F01').innerText()).includes('SOURCE-PROSE-END'));
assert.ok((await p.locator('#F01').innerText()).includes('PENDING-DECISION-END'));
const regions=await p.locator('.report-table-region').evaluateAll(es=>es.map(e=>({label:e.getAttribute('aria-label'),tab:e.tabIndex,x:getComputedStyle(e).overflowX})));assert.ok(regions.length>=1);assert.ok(regions.every(e=>e.label&&e.tab===0&&e.x==='auto'));
states++;
}await c.close();}console.log(JSON.stringify({states,browser:browser.version(),passed:true}));}finally{if(browser)await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
