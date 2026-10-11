const assert=require('node:assert/strict'),{pathToFileURL}=require('node:url');
let chromium;try{({chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||'playwright'))}catch(e){console.error('Provide Playwright via REPORT_GEN_PLAYWRIGHT_MODULE');process.exit(77)}
const URL='https://long-audit.example.test/api/v1/treasury/approvals/abcdefghijklmnopqrs?authorization_mode=pending&transaction_id=0123456789abcdef';
let browser,states=0;
(async()=>{try{
 browser=await chromium.launch({executablePath:process.env.REPORT_GEN_CHROMIUM,headless:true,args:['--no-sandbox']});
 for(const scripts of [true,false]){
  const context=await browser.newContext({javaScriptEnabled:scripts}),page=await context.newPage();
  for(const width of [320,390,1440])for(const zoom of [1,2]){
   await page.setViewportSize({width,height:1000});await page.goto(pathToFileURL(process.argv[2]).href);await page.evaluate(()=>document.fonts.ready);await page.evaluate(z=>document.body.style.zoom=z,zoom);
   const result=await page.locator('pre').evaluateAll(nodes=>nodes.map(e=>{
    const expected=e.textContent,range=document.createRange();range.selectNodeContents(e);const selection=getSelection();selection.removeAllRanges();selection.addRange(range);const selected=selection.toString();selection.removeAllRanges();
    const rows=new Map(),walker=document.createTreeWalker(e,NodeFilter.SHOW_TEXT);let node;
    while(node=walker.nextNode())for(let i=0;i<node.length;i++){
     if(node.textContent[i]==='\n')continue;const r=document.createRange();r.setStart(node,i);r.setEnd(node,i+1);const rect=r.getBoundingClientRect(),row=rows.get(rect.y)||[];row.push({char:node.textContent[i],left:rect.left,right:rect.right,width:rect.width});rows.set(rect.y,row);
    }
    const css=getComputedStyle(e),box=e.getBoundingClientRect(),scale=box.width/e.offsetWidth,right=box.right-parseFloat(css.paddingRight)*scale-parseFloat(css.borderRightWidth)*scale;
    return{expected,selected,rows:[...rows.values()].map(chars=>({text:chars.map(x=>x.char).join(''),unused:right-(chars.findLast(x=>x.char!==' '&&x.char!=='\t')||chars.at(-1)).right,glyph:Math.max(...chars.map(x=>x.width))}))};
   }));
   assert.equal(result.length,3);assert.ok(result.every(x=>x.expected.replace(/\n$/,'')===x.selected.replace(/\n$/,'')),`selection changed at ${width}/${zoom}`);
   assert.equal(result[0].expected.replace(/\n$/,''),'curl --silent --show-error '+URL);
   assert.equal(result[1].expected.replace(/\n$/,''),'  first line\n\tsecond line\nmañana café café 中文 🙂');
   for(const block of [result[0],result[2]])for(const line of block.rows.slice(0,-1))assert.ok(line.unused<=line.glyph+2&&line.unused>=-2,`underfilled intermediate code line at ${width}/${zoom}: ${JSON.stringify(line)}`);
   const links=await page.locator('#F01 a').evaluateAll(as=>as.map(a=>({href:a.getAttribute('href'),text:a.textContent,wordBreak:getComputedStyle(a).wordBreak})));
   assert.deepEqual(links.map(a=>a.href),[URL,URL]);assert.equal(links[0].text,URL);assert.equal(links[0].wordBreak,'break-all');assert.equal(links[1].wordBreak,'normal');
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`overflow at ${width}/${zoom}`);
   states++;
  }await context.close();
 }console.log(JSON.stringify({states,passed:true,browser:browser.version()}));
}finally{if(browser)await browser.close()}})().catch(e=>{console.error(e);process.exitCode=1});
