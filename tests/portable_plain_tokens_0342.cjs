const assert=require('node:assert/strict'),{pathToFileURL}=require('node:url');
let chromium;try{({chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||'playwright'))}catch(e){console.error('Provide Playwright via REPORT_GEN_PLAYWRIGHT_MODULE');process.exit(77)}
let browser,states=0;
(async()=>{try{
 browser=await chromium.launch({executablePath:process.env.REPORT_GEN_CHROMIUM,headless:true,args:['--no-sandbox']});
 for(const scripts of [true,false]){
  const context=await browser.newContext({javaScriptEnabled:scripts}),page=await context.newPage();
  for(const width of [320,390,1440])for(const zoom of [1,2]){
   await page.setViewportSize({width,height:1000});await page.goto(pathToFileURL(process.argv[2]).href);await page.evaluate(()=>document.fonts.ready);await page.evaluate(z=>document.body.style.zoom=z,zoom);
   const result=await page.locator('#F01 .report-literal-token').evaluateAll(spans=>spans.map(span=>{
    const parent=span.closest('p,li,td'),range=document.createRange();range.selectNodeContents(parent);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);const selected=selection.toString();selection.removeAllRanges();
    const walker=document.createTreeWalker(parent,NodeFilter.SHOW_TEXT),node=walker.nextNode();range.setStart(node,0);range.setEnd(node,1);const label=range.getBoundingClientRect();
    range.setStart(span.firstChild,0);range.setEnd(span.firstChild,1);const first=range.getBoundingClientRect();
    const bounds=parent.getBoundingClientRect(),css=getComputedStyle(parent),scale=bounds.width/parent.offsetWidth,left=bounds.left+(parseFloat(css.paddingLeft)+parseFloat(css.borderLeftWidth))*scale,right=bounds.right-(parseFloat(css.paddingRight)+parseFloat(css.borderRightWidth))*scale;
    let overflow=false;for(let i=0;i<span.firstChild.length;i++){range.setStart(span.firstChild,i);range.setEnd(span.firstChild,i+1);const r=range.getBoundingClientRect();if(r.left<left-2||r.right>right+2)overflow=true}
    const nfd=span.textContent.indexOf('e\u0301');let grapheme=true;if(nfd>=0){range.setStart(span.firstChild,nfd);range.setEnd(span.firstChild,nfd+1);const base=range.getBoundingClientRect();range.setStart(span.firstChild,nfd+1);range.setEnd(span.firstChild,nfd+2);grapheme=Math.abs(base.y-range.getBoundingClientRect().y)<1}
    return{text:parent.textContent,selected,labelY:label.y,firstY:first.y,overflow,grapheme};
   }));
   assert.equal(result.length,6);for(const item of result){assert.equal(item.selected,item.text,`copy changed ${width}/${zoom}`);assert.ok(Math.abs(item.labelY-item.firstY)<1,`early break ${width}/${zoom}: ${JSON.stringify(item)}`);assert.ok(!item.overflow,`literal clipped ${width}/${zoom}`);assert.ok(item.grapheme,`NFD cluster split ${width}/${zoom}`)}
   const normal=await page.locator('#F01 p').filter({hasText:/^NORMAL:/}).evaluate(el=>{const range=document.createRange();range.selectNodeContents(el);const before=[...range.getClientRects()].map(r=>[r.x,r.y,r.width,r.height]);const marker=document.createElement('style');marker.textContent='.report-literal-token{word-break:normal!important;overflow-wrap:normal!important}';document.head.append(marker);const after=[...range.getClientRects()].map(r=>[r.x,r.y,r.width,r.height]);marker.remove();return {before:before.map(r=>[r[0],r[2],r[3]]),after:after.map(r=>[r[0],r[2],r[3]]),hasSpan:!!el.querySelector('span')};});
   assert.deepEqual(normal.before,normal.after);assert.equal(normal.hasSpan,false);
   assert.equal(await page.locator('pre .report-literal-token,code .report-literal-token').count(),0);
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`page overflow ${width}/${zoom}`);states++;
  }await context.close();
 }console.log(JSON.stringify({states,passed:true,browser:browser.version()}));
}finally{if(browser)await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
