const assert=require('node:assert/strict'),{pathToFileURL}=require('node:url');
let chromium;try{({chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||'playwright'))}catch(e){console.error('Provide Playwright via REPORT_GEN_PLAYWRIGHT_MODULE');process.exit(77)}
let browser,states=0;
(async()=>{try{
 browser=await chromium.launch({executablePath:process.env.REPORT_GEN_CHROMIUM,headless:true,args:['--no-sandbox']});
 const page=await browser.newPage();
 let baseline;
 for(const width of [1440,320,390])for(const scale of [1,2]){
  await page.setViewportSize({width,height:1000});await page.goto(pathToFileURL(process.argv[2]).href);await page.evaluate(()=>document.fonts.ready);
  if(scale===2)await page.evaluate(()=>{const els=[...document.querySelectorAll('body,body *')],sizes=els.map(e=>parseFloat(getComputedStyle(e).fontSize));els.forEach((e,i)=>e.style.fontSize=sizes[i]*2+'px');});
  const fidelity=await page.locator('#F01').evaluate(e=>({text:e.textContent,links:[...e.querySelectorAll('a')].map(a=>[a.textContent,a.getAttribute('href')])}));
  if(!baseline)baseline=fidelity;assert.deepEqual(fidelity,baseline);
  const assets=await page.locator('#F01 .report-fields code').evaluate(e=>{const n=e.firstChild,t=e.textContent;return [...t.matchAll(/(?:\d{1,3}\.){3}\d{1,3}/g)].map(m=>{const ys=[];for(let i=m.index;i<m.index+m[0].length;i++){const r=document.createRange();r.setStart(n,i);r.setEnd(n,i+1);ys.push(r.getBoundingClientRect().y)}return {token:m[0],lines:new Set(ys).size}})});
  assert.equal(assets.length,3);assert.ok(assets.every(x=>x.lines===1),`IPv4 split at ${width}/${scale}: ${JSON.stringify(assets)}`);
  const literals=await page.locator('#F01 p > code.report-literal-url,#F01 a.report-literal-url,#F01 pre').evaluateAll(es=>es.map(e=>{const rows=new Map(),w=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let n;while(n=w.nextNode())for(let i=0;i<n.length;i++){if(n.textContent[i]==='\n')continue;const r=document.createRange();r.setStart(n,i);r.setEnd(n,i+1);const q=r.getBoundingClientRect(),row=rows.get(q.y)||[];row.push({ch:n.textContent[i],right:q.right,width:q.width});rows.set(q.y,row)}const c=getComputedStyle(e),box=(e.tagName==='PRE'?e:e.parentElement).getBoundingClientRect(),right=box.right-(e.tagName==='PRE'?parseFloat(c.paddingRight)+parseFloat(c.borderRightWidth):0);return {text:e.textContent,rows:[...rows.values()].map(row=>({unused:right-row.at(-1).right,glyph:Math.max(...row.map(x=>x.width))}))}}));
  assert.equal(literals.length,3);for(const block of literals)for(const row of block.rows.slice(0,-1))assert.ok(row.unused<=row.glyph+2&&row.unused>=-2,`Underfilled literal at ${width}/${scale}: ${block.text.slice(0,60)} ${JSON.stringify(row)}`);
  const long=await page.locator('#F01 p > code').filter({hasText:/^A{220}$/}).evaluate(e=>{const r=document.createRange();r.selectNodeContents(e);const s=getSelection();s.removeAllRanges();s.addRange(r);const copied=s.toString();s.removeAllRanges();return {text:e.textContent,copied,rects:[...r.getClientRects()].map(x=>({left:x.left,right:x.right}))}});
  assert.equal(long.text,'A'.repeat(220));assert.equal(long.copied,long.text);assert.ok(long.rects.length>1);assert.ok(long.rects.every(r=>r.left>=0&&r.right<=width+1));
  assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`Page overflow ${width}/${scale}`);
  states++;
 }
 console.log(JSON.stringify({states,passed:true}));
}finally{if(browser)await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
