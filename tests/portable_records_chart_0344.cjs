'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),{pathToFileURL}=require('node:url');
let chromium,firefox;try{({chromium,firefox}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||'playwright'))}catch(_){process.exit(77)}
let browser,server,deadline;
(async()=>{try{
 const useFirefox=process.env.REPORT_GEN_BROWSER==='firefox';
 const launch={executablePath:useFirefox?process.env.REPORT_GEN_FIREFOX:process.env.REPORT_GEN_CHROMIUM,headless:true,args:useFirefox?[]:['--no-sandbox'],...(useFirefox?{env:{...process.env,MOZ_DISABLE_CONTENT_SANDBOX:'1'}}:{})};
 if(useFirefox){server=await firefox.launchServer(launch);browser=await firefox.connect(server.wsEndpoint())}else browser=await chromium.launch(launch);
 deadline=setTimeout(()=>{console.error('Browser acceptance exceeded 90 seconds');(server?server.kill():browser.close()).finally(()=>process.exit(1))},90000);
 const hash=p=>require('node:crypto').createHash('sha256').update(fs.readFileSync(p)).digest('hex');
 const result={browser:browser.version(),engine:useFirefox?'firefox':'chromium',script_sha256:hash(__filename),input:{path:process.argv[2],sha256:hash(process.argv[2])},states:[],svg:[]};
 for(const scripts of[true,false])for(const [width,mode]of[[1440,'normal'],[320,'normal'],[320,'text200'],[390,'zoom200']]){
  console.log('STATE '+JSON.stringify({scripts,width,mode}));
  const context=await browser.newContext({javaScriptEnabled:scripts,viewport:{width,height:1000}}),page=await context.newPage();
  await page.goto(pathToFileURL(process.argv[2]).href);
  // Firefox disables promise callbacks in a JavaScript-disabled document.
  // Force native layout, then poll its synchronous font status from Node.
  await page.locator('body').boundingBox();
  if(scripts)await page.evaluate(()=>document.fonts.ready);else{const start=Date.now();while(await page.evaluate(()=>document.fonts.status)!=='loaded'){if(Date.now()-start>10000)throw Error('Native fonts did not finish loading');await new Promise(r=>setTimeout(r,50))}}
  if(mode==='text200')await page.evaluate(()=>{const sizes=[...document.querySelectorAll('*')].filter(e=>e instanceof HTMLElement&&!['SCRIPT','STYLE'].includes(e.tagName)).map(e=>[e,parseFloat(getComputedStyle(e).fontSize),parseFloat(getComputedStyle(e).lineHeight)]);for(const[e,f,l]of sizes){if(f)e.style.fontSize=f*2+'px';if(l)e.style.lineHeight=l*2+'px'}});
  if(mode==='zoom200')await page.evaluate(()=>document.body.style.zoom='2');
  const data=await page.evaluate(()=>({page:[document.documentElement.scrollWidth,innerWidth],tables:[...document.querySelectorAll('.report-records')].map(t=>({role:t.getAttribute('role'),headings:[...t.querySelectorAll('thead th')].map(h=>({text:h.textContent,role:h.getAttribute('role')})),rows:[...t.querySelectorAll('tbody tr')].map(r=>[...r.cells].map(c=>({text:c.textContent,label:c.dataset.columnLabel,role:c.getAttribute('role'),index:c.getAttribute('aria-colindex')}))),display:getComputedStyle(t).display,scroll:t.parentElement.scrollWidth,width:t.parentElement.clientWidth})),lists:[...document.querySelectorAll('.report-list-region')].map(r=>({start:r.querySelector('ol').start,scroll:r.scrollWidth,width:r.clientWidth,type:getComputedStyle(r.querySelector('li')).listStyleType,marker:getComputedStyle(r.querySelector('li'),'::marker').content}))}));
  assert.ok(data.page[0]<=data.page[1]+1);assert.ok(data.tables.length>=1);
  for(const table of data.tables){assert.equal(table.role,'table');assert.ok(table.headings.every(h=>h.role==='columnheader'));
   for(const row of table.rows)for(let i=0;i<row.length;i++){assert.equal(row[i].role,'cell');assert.equal(row[i].index,String(i+1));assert.equal(row[i].label,table.headings[i].text.trim()||String(i+1));}
   if(width<600){assert.equal(table.display,'block');assert.ok(table.scroll<=table.width+1,'record text fits without horizontal scrolling');}
  }
  for(const list of data.lists){assert.equal(list.type,'decimal');if(width<600)assert.ok(list.scroll<=list.width+1,'native extreme counter and prose fit');}
  // Roles and accessible cell names survive CSS display remapping; visual
  // column labels have empty CSS alternative text and do not rename the data.
  const table=page.locator('.report-records').first();
  assert.ok(await table.getByRole('row').count()>1);assert.ok(await table.getByRole('columnheader').count()>1);
  for(const candidate of await page.locator('.report-records').all()){
   assert.equal(await candidate.getAttribute('aria-colcount'),null);assert.equal(await candidate.getAttribute('aria-rowcount'),null);
   const visibleColumns=await candidate.locator('thead th').evaluateAll(headers=>headers.filter(h=>getComputedStyle(h).display!=='none').length);
   assert.equal(await candidate.getByRole('columnheader').count(),visibleColumns,'AX exposes every visible header and excludes the hidden PDF page column');
   if((await candidate.getAttribute('class')).split(' ').includes('sumtable'))assert.equal(visibleColumns,3);
   const body=candidate.locator('tbody');
   assert.equal(await body.getByRole('cell').count()+await body.getByRole('rowheader').count(),visibleColumns*await body.locator('tr').count(),'AX preserves all visible data cells');
  }
  const cell=table.getByRole('cell').first();assert.equal((await cell.ariaSnapshot()).trim(),'- cell "'+(await cell.textContent()).trim()+'"');
  const svg=await page.evaluate(()=>{
   const rgba=s=>{const m=s.match(/^rgba?\(([^)]+)\)$/);if(!m)throw Error('Unsupported paint '+s);const a=m[1].split(',').map(Number);return a.length===3?[...a,1]:a};
   const over=(a,b)=>{const alpha=a[3]+b[3]*(1-a[3]);return[...a.slice(0,3).map((v,i)=>(v*a[3]+b[i]*b[3]*(1-a[3]))/alpha),alpha]};
   const lum=c=>c.slice(0,3).reduce((sum,v,i)=>{v/=255;return sum+[.2126,.7152,.0722][i]*(v<=.04045?v/12.92:((v+.055)/1.055)**2.4)},0);
   const reference=1.05/(lum([119,119,119,1])+.05);if(Math.abs(reference-4.478089453577214)>1e-10)throw Error('sRGB gamma reference failed');
   window.__qaChartPaints=()=>[...document.querySelectorAll('svg.sevchart text')].map(text=>{
    const css=getComputedStyle(text),box=text.getBBox(),svg=text.closest('svg'),anc=[];let bg=[255,255,255,1];
    for(let n=text;n;n=n.parentElement){const c=getComputedStyle(n);if(c.backgroundImage!=='none'||c.filter!=='none'||c.mixBlendMode!=='normal'||Number(c.opacity)!==1)throw Error('Unsupported chart backdrop');anc.push({tag:n.tagName,background:c.backgroundColor,opacity:c.opacity});}
    for(const a of anc.reverse())bg=over(rgba(a.background),bg);
    const fill=rgba(css.fill);fill[3]*=Number(css.fillOpacity);const effective=over(fill,bg);const l=[lum(effective),lum(bg)].sort((a,b)=>a-b),ratio=(l[1]+.05)/(l[0]+.05);
    const overlaps=[...svg.querySelectorAll('rect,line,path,image')].filter(shape=>{const r=shape.getBBox();return r.width&&r.height&&r.x<box.x+box.width&&r.x+r.width>box.x&&r.y<box.y+box.height&&r.y+r.height>box.y}).map(s=>s.outerHTML);
    return{text:text.textContent,fill:css.fill,fillOpacity:css.fillOpacity,background:bg,ratio,overlaps,box:{x:box.x,y:box.y,width:box.width,height:box.height},accessibleName:svg.getAttribute('aria-label')};
   });
   return window.__qaChartPaints();
  });
  assert.ok(svg.length>=7);for(const text of svg){assert.ok(text.ratio>=4.5,JSON.stringify(text));assert.deepEqual(text.overlaps,[],'text paints over the resolved section background, not a bar/image');assert.ok(text.accessibleName.includes(': 0')||text.accessibleName.includes(': 1'),'chart alternative includes numeric counts');}
  let negative=null;if(scripts&&width===1440){negative=await page.evaluate(()=>{const text=document.querySelector('svg.sevchart text'),before=text.getAttribute('fill');text.setAttribute('fill','#ffffff');const low=window.__qaChartPaints()[0].ratio;if(before===null)text.removeAttribute('fill');else text.setAttribute('fill',before);const restored=window.__qaChartPaints()[0].ratio;return{low,restored,passed:low<4.5&&restored>=4.5}});assert.ok(negative.passed,'actual fill negative control must fail then recover');}
  result.states.push({scripts,width,mode,passed:true,tables:data.tables.length,lists:data.lists.length,negative});result.svg.push({scripts,width,mode,text:svg});
  await context.close();
 }
 result.passed=true;if(process.argv[3])fs.writeFileSync(process.argv[3],JSON.stringify(result,null,2));console.log(JSON.stringify({states:result.states.length,svg_instances:result.svg.reduce((n,s)=>n+s.text.length,0),passed:true}));
}finally{clearTimeout(deadline);if(server)await server.kill();else await browser?.close()}})().catch(e=>{console.error(e);process.exitCode=1});
