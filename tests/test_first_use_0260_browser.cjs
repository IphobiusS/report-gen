/* Real-browser first-use actions, secondary navigation and readable suggestions. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawn}=require('node:child_process');
const args=process.argv.slice(2),option=(key,fallback)=>args.includes(key)?args[args.indexOf(key)+1]:fallback;
const root=path.resolve(process.env.REPORT_GEN_TOOL_ROOT||path.join(__dirname,'..')),out=path.resolve(option('--output','out/first-use-0260'));
const {chromium}=require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE||require.resolve('playwright',{paths:[root,process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||root]}));
fs.mkdirSync(out,{recursive:true});
const workspace=fs.mkdtempSync(path.join(os.tmpdir(),'report-gen-acceptance-0211-first-use-'));
fs.writeFileSync(path.join(workspace,'.test-only'),'synthetic acceptance workspace');
const results={checks:[],pageErrors:[]},save=()=>fs.writeFileSync(path.join(out,'results.json'),JSON.stringify(results,null,2));
function check(name,passed,detail){results.checks.push({name,passed:!!passed,...(detail===undefined?{}:{detail})});save();assert.ok(passed,name);console.log('PASS '+name);}
const server=spawn(process.env.RG_PYTHON||'python',[path.join(root,'scripts/browser-server-0211.py'),'--workspace',workspace],{cwd:root});
server.stderr.on('data',data=>fs.appendFileSync(path.join(out,'server.log'),data));
let browser,timer,page;
(async()=>{try{
  const base=await new Promise((resolve,reject)=>{let text='';timer=setTimeout(()=>reject(Error('Server timeout')),20000);server.stdout.on('data',data=>{text+=data;if(text.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(text.split('\n')[0]).url);}catch(error){reject(error);}}});server.on('exit',code=>reject(Error('Server exited '+code)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.REPORT_GEN_CHROMIUM||process.env.RG_CHROMIUM_EXECUTABLE||undefined});
  results.browser=browser.version();
  const context=await browser.newContext({viewport:{width:1366,height:1000},reducedMotion:'reduce'});
  page=await context.newPage();page.on('pageerror',error=>results.pageErrors.push(String(error)));
  await page.addInitScript(()=>localStorage.setItem('rg.previewVisible','0'));
  await page.goto(base);await page.locator('.workspace-dashboard').waitFor();
  await page.locator('.workspace-hero-actions .primary').focus();await page.keyboard.press('Enter');
  await page.waitForFunction(()=>S.slug&&S.data?.findings?.length&&!projectStore.loading&&!projectBusyCount);
  check('Nimbus starts through the visible primary keyboard action',await page.evaluate(()=>S.sel.type==='home'&&S.data.findings.length===12));
  const original=await page.evaluate(()=>JSON.stringify({data:S.data,revision:projectStore.revision,etag:projectStore.etag}));
  await page.locator('[data-guide-action="suggested-guide"]').click();
  check('The next-action guide control opens the matching real guide step',await page.evaluate(()=>S.sel.type==='guide'&&S.sel.idx===GuideUI.nextAction(S.data,WorkflowUI.reviewSnapshot()).step));
  await page.locator('[data-guide-action="home"]').click();
  await page.locator('#workspaceResearch > summary').focus();await page.keyboard.press('Enter');
  check('Secondary navigation opens with the keyboard',await page.locator('#workspaceResearch').evaluate(node=>node.open));
  await page.locator('[data-workflow="coverage"]').click();
  check('Coverage remains reachable from its disclosed group',await page.evaluate(()=>S.sel.type==='workflow'&&S.sel.idx==='coverage'));
  await page.locator('#navHome').click();
  check('The round trip preserves the exact report and saved revision',await page.evaluate(value=>value===JSON.stringify({data:S.data,revision:projectStore.revision,etag:projectStore.etag}),original));
  for(const sample of [{width:1366,lang:'es',theme:'dark',zoom:100},{width:390,lang:'en',theme:'light',zoom:100},{width:320,lang:'en',theme:'dark',zoom:200}]){
    await page.setViewportSize({width:sample.width,height:1000});
    await page.evaluate(sample=>{setUiLang(sample.lang);applyUiTheme(sample.theme);document.documentElement.style.fontSize=sample.zoom+'%';select('home');},sample);
    const label=sample.width+'-'+sample.lang+'-'+sample.theme+'-'+sample.zoom;
    const bounds=await page.locator('[data-first-use-state]').evaluate(el=>({left:el.getBoundingClientRect().left,right:el.getBoundingClientRect().right,width:innerWidth,scrollWidth:document.documentElement.scrollWidth,clientWidth:document.documentElement.clientWidth,controls:[...el.querySelectorAll('button')].map(button=>({w:button.getBoundingClientRect().width,h:button.getBoundingClientRect().height,sw:button.scrollWidth,cw:button.clientWidth}))}));
    check(label+' suggestion fits the viewport without horizontal overflow',bounds.left>=0&&bounds.right<=bounds.width+1&&bounds.scrollWidth<=bounds.clientWidth+1,bounds);
    check(label+' suggestions keep readable 44px controls',bounds.controls.every(button=>button.w>=44&&button.h>=44&&button.sw<=button.cw+1),bounds.controls);
    await page.screenshot({path:path.join(out,label+'.png'),fullPage:true});
  }
  check('No browser runtime errors',results.pageErrors.length===0,results.pageErrors);
  save();
}catch(error){results.error=String(error.stack||error);save();if(page)await page.screenshot({path:path.join(out,'failure.png'),fullPage:true}).catch(()=>{});throw error;}
finally{clearTimeout(timer);await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{console.error(error);process.exitCode=1;});
