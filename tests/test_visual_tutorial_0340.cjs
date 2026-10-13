/* Real-browser tutorial contract. Uses only a disposable fictional workspace. */
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {spawn} = require('node:child_process');
const root = path.resolve(process.env.REPORT_GEN_TOOL_ROOT || path.join(__dirname, '..'));
const args = process.argv.slice(2);
const out = path.resolve(args.includes('--output') ? args[args.indexOf('--output') + 1] : 'out/visual-tutorial-0340');
const {chromium} = require(require.resolve('playwright', {paths:[root]}));
const axeSource = fs.readFileSync(require.resolve('axe-core/axe.min.js', {paths:[root]}), 'utf8');
const workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'report-gen-acceptance-0211-tutorial-'));
fs.writeFileSync(path.join(workspace, '.test-only'), 'synthetic acceptance workspace');
fs.mkdirSync(out, {recursive:true});
const results = {checks:[], errors:[], external:[], screenshots:[], limitations:['Automated Chromium checks do not replace visual review or a human screen reader.']};
const save = () => fs.writeFileSync(path.join(out, 'results.json'), JSON.stringify(results, null, 2));
function check(name, condition, detail) {
  results.checks.push({name, passed:!!condition, ...(detail === undefined ? {} : {detail})}); save();
  assert.ok(condition, name + (detail === undefined ? '' : ': ' + JSON.stringify(detail)));
  console.log('PASS ' + name);
}
const server = spawn(process.env.RG_PYTHON || 'python', [path.join(root, 'scripts/browser-server-0211.py'), '--workspace', workspace], {cwd:root, env:{...process.env, PYTHONPATH:root + path.delimiter + path.join(root, 'webapp')}});
server.stderr.on('data', data => fs.appendFileSync(path.join(out, 'server.log'), data));
let browser, page, base, timer;
async function ready(target) { await target.waitForFunction(() => !document.querySelector('#splash') && typeof GuideUI !== 'undefined' && !projectStore.loading && !projectBusyCount); }
async function launch(language='es', blocked=false, corrupt=false) {
  const context = await browser.newContext({viewport:{width:1366,height:1000}, reducedMotion:'reduce'});
  await context.route('**/*', route => { const url=route.request().url(); if (/^https?:/.test(url) && !url.startsWith(base + '/')) {results.external.push(url); return route.abort();} return route.continue(); });
  await context.addInitScript({content:axeSource});
  await context.addInitScript(({language,blocked,corrupt}) => {
    localStorage.setItem('rg.uiLang', language); localStorage.setItem('rg.previewVisible', '0');
    if (corrupt) localStorage.setItem('rg.visualTutorial.v1', '{broken');
    if (blocked) {
      const get=Storage.prototype.getItem, set=Storage.prototype.setItem;
      Storage.prototype.getItem=function(key){if(key==='rg.visualTutorial.v1')throw new DOMException('Synthetic denied storage','SecurityError');return get.call(this,key);};
      Storage.prototype.setItem=function(key,value){if(key==='rg.visualTutorial.v1')throw new DOMException('Synthetic denied storage','SecurityError');return set.call(this,key,value);};
    }
  }, {language,blocked,corrupt});
  const target = await context.newPage(); target.on('pageerror', error => results.errors.push(String(error)));
  await target.goto(base); await ready(target); return {context,page:target};
}
async function open(target) {
  if (!await target.locator('#guideBtn').isVisible()) await target.locator('#studioMore > summary').click();
  await target.locator('#guideBtn').click(); await target.locator('[data-guide-page]').waitFor();
}
async function state(target) { return target.evaluate(() => JSON.stringify({slug:S.slug,data:S.data,revision:projectStore.revision,etag:projectStore.etag,dirty:projectStore.dirty})); }
(async()=>{try {
  base = await new Promise((resolve,reject) => {let text=''; timer=setTimeout(()=>reject(Error('Server timeout')),30000); server.stdout.on('data',data=>{text+=data;for(const line of text.split('\n'))try{const value=JSON.parse(line);if(value.url){clearTimeout(timer);resolve(value.url);}}catch{}});server.on('exit',code=>reject(Error('Server exited '+code)));});
  browser = await chromium.launch({headless:true, executablePath:process.env.REPORT_GEN_CHROMIUM || process.env.RG_CHROMIUM_EXECUTABLE || undefined});
  results.browser=browser.version();
  const first=await launch(); page=first.page;
  check('First visit invites without blocking the dashboard', await page.locator('[data-tutorial-invite]').isVisible() && await page.locator('dialog[open]').count()===0 && await page.locator('.workspace-hero-actions .primary').isEnabled());
  await page.locator('[data-tutorial-dismiss]').click(); await page.reload(); await ready(page);
  check('Not now survives reload and leaves the menu available', await page.locator('[data-tutorial-invite]').count()===0 && await page.locator('#guideBtn').isEnabled());
  const empty=await state(page), mutations=[];
  page.on('request', request=>{if(!['GET','HEAD'].includes(request.method()))mutations.push(request.url());});
  await open(page);
  for(const language of ['es','en','pt']) {
    await page.evaluate(language=>setUiLang(language),language);
    await page.locator('[data-guide-step="0"]').click();
    const createTrigger=page.locator('[data-guide-action="new"]');
    for(const route of ['escape','cancel','back']) {
      await createTrigger.focus();await page.keyboard.press('Enter');
      await page.locator('dialog.design-dialog[open]').waitFor();
      if(route!=='escape') {
        await page.getByRole('button',{name:({es:'Continuar con esta plantilla',en:'Continue with this design',pt:'Continuar com este modelo'})[language],exact:true}).click();
        await page.locator('#newModal[open]').waitFor();
        if(route==='back') {
          await page.locator('#newProjectLibrary button').click();
          await page.locator('dialog.design-dialog[open]').waitFor();
        }
      }
      if(route==='cancel') await page.locator('#mCancel').click();
      else await page.keyboard.press('Escape');
      await page.waitForFunction(()=>!document.querySelector('dialog[open]'));
      await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
      check(language+' tutorial project '+route+' restores its actual trigger',await createTrigger.evaluate(node=>node===document.activeElement));
    }
    for(let step=0;step<6;step++) {
      await page.locator('[data-guide-step="'+step+'"]').click();
      const images=page.locator('.tutorial-screenshot img');
      await images.evaluateAll(nodes=>Promise.all(nodes.map(node=>node.decode())));
      check(language+' step '+(step+1)+' uses real local locale images and useful alternatives', await images.evaluateAll((nodes,lang)=>nodes.every(node=>node.naturalWidth>500&&node.src.endsWith('-'+lang+'.webp')&&node.alt.length>50),language));
      check(language+' step '+(step+1)+' keeps exactly one current navigation step', await page.locator('[data-guide-step][aria-current="step"]').count()===1 && await page.locator('#guideStepTitle').evaluate(node=>node===document.activeElement));
    }
  }
  await page.locator('[data-tutorial-complete]').click();
  check('Completion explicitly records only tutorial progress', await page.locator('[data-tutorial-progress]').innerText()==='Tutorial concluído. Você pode revisitar qualquer etapa.' && await state(page)===empty);
  await page.reload(); await ready(page); await open(page);
  check('Completed tutorial can be reopened at the saved step after reload', await page.locator('[data-guide-current="5"]').count()===1 && await page.locator('[data-tutorial-complete]').isDisabled());
  await page.locator('[data-tutorial-reset]').click();
  check('Restart returns to the first step without changing the project', await page.locator('[data-guide-current="0"]').count()===1 && await page.evaluate(()=>JSON.parse(localStorage.getItem('rg.visualTutorial.v1')).completed===false) && await state(page)===empty);
  await page.locator('#studioMore > summary').click();
  await page.locator('#studioPreferences > summary').click();
  await page.locator('#focusBtn').click();
  await page.locator('#studioMore > summary').click();
  check('Desktop focus mode hides the sidebar',await page.locator('body').evaluate(node=>node.classList.contains('focus-mode'))&&!await page.locator('#workspaceSidebar').isVisible());
  await open(page);
  check('The single tutorial menu entry stays reachable in desktop focus mode',await page.locator('[data-guide-page]').isVisible()&&await page.locator('#guideBtn').count()===1);
  await page.locator('#studioMore > summary').click();await page.locator('#focusBtn').click();await page.locator('#studioMore > summary').click();
  const imageButton=page.locator('[data-tutorial-image="gallery"]');await imageButton.focus();await page.keyboard.press('Enter');
  await page.locator('dialog.tutorial-image-dialog[open]').waitFor();
  check('Screenshot opens as a native modal with a focused close control', await page.locator('[data-tutorial-close]').evaluate(node=>node===document.activeElement)&&await page.locator('dialog.tutorial-image-dialog').evaluate(node=>node.matches(':modal')));
  await page.locator('[data-tutorial-scale]').click();
  check('Actual size is explicit and accessible', await page.locator('[data-tutorial-scale]').getAttribute('aria-pressed')==='true' && await page.locator('[data-tutorial-image-region]').getAttribute('tabindex')==='0');
  await page.keyboard.press('Escape'); await page.locator('dialog.tutorial-image-dialog').waitFor({state:'detached'});
  check('Escape restores screenshot trigger focus', await imageButton.evaluate(node=>node===document.activeElement));
  for(const sample of [{width:1366,zoom:100,lang:'es',theme:'dark'},{width:390,zoom:100,lang:'en',theme:'light'},{width:320,zoom:200,lang:'en',theme:'dark'},{width:1440,zoom:100,lang:'pt',theme:'light'},{width:320,zoom:200,lang:'pt',theme:'dark'}]) {
    await page.setViewportSize({width:sample.width,height:1000});
    await page.evaluate(sample=>{document.documentElement.style.fontSize=sample.zoom+'%';setUiLang(sample.lang);applyUiTheme(sample.theme);},sample);
    const label=sample.lang+'-'+sample.width+'-'+sample.zoom;
    for(let step=0;step<6;step++) {
      await page.locator('[data-guide-step="'+step+'"]').click();
      const bounds=await page.locator('[data-guide-page]').evaluate(node=>({client:node.clientWidth,scroll:node.scrollWidth,root:document.documentElement.scrollWidth,viewport:innerWidth}));
      check(label+' step '+step+' fits at enlarged text',bounds.scroll<=bounds.client+1&&bounds.root<=bounds.viewport+1,bounds);
    }
    await page.locator('[data-guide-step="0"]').click();
    await page.locator('[data-tutorial-image]').first().click();
    const geometry=await page.locator('dialog.tutorial-image-dialog').evaluate(node=>{const r=node.getBoundingClientRect();return{left:r.left,right:r.right,viewport:innerWidth,scroll:node.scrollWidth,client:node.clientWidth};});
    check(label+' image modal fits the viewport',geometry.left>=0&&geometry.right<=geometry.viewport+1&&geometry.scroll<=geometry.client+1,geometry);
    const axe=await page.evaluate(()=>axe.run(document.querySelector('dialog.tutorial-image-dialog'),{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21aa']}}));
    check(label+' screenshot dialog has no automatic accessibility violations',axe.violations.length===0,axe.violations.map(v=>({id:v.id,nodes:v.nodes.map(n=>n.target)})));
    results.accessibility??=[];results.accessibility.push({label,incomplete:axe.incomplete.map(v=>v.id)});
    const capture=path.join(out,label+'.png');await page.screenshot({path:capture});results.screenshots.push(capture);
    await page.keyboard.press('Escape');
  }
  check('Reading, completion, restart and images make no modifying API requests',mutations.length===0,mutations);
  await first.context.close();
  for(const language of ['es','en','pt']) {
    const missing=await launch(language);page=missing.page;
    await page.route('**/static/tutorial/*.webp', route=>route.abort());
    await open(page);
    await page.waitForFunction(()=>document.querySelector('.tutorial-screenshot-button')?.disabled);
    const fallback=({es:'Captura no disponible. Las instrucciones siguen debajo.',en:'Screenshot unavailable. The instructions remain below.',pt:'Captura indisponível. As instruções continuam abaixo.'})[language];
    check(language+' missing screenshot leaves a readable fallback and a 44px control', await page.locator('.tutorial-screenshot-button').evaluate((node,text)=>node.getBoundingClientRect().height>=44&&node.textContent.includes(text),fallback) && await page.locator('.tutorial-screenshot figcaption').isVisible());
    check(language+' missing screenshot accessible name matches its visible fallback', await page.locator('.tutorial-screenshot-button').getAttribute('aria-label')===fallback);
    await page.locator('#guideNext').click();
    check(language+' missing screenshots do not block tutorial navigation',await page.locator('[data-guide-current="1"]').count()===1);
    await missing.context.close();
  }
  for(const mode of ['blocked','corrupt']) {
    const next=await launch('es',mode==='blocked',mode==='corrupt');page=next.page;
    await page.locator('[data-tutorial-start]').click();await page.locator('#guideNext').click();
    await page.locator('[data-guide-action="home"]').click();
    check(mode+' storage keeps the invitation dismissed in this tab', await page.locator('[data-tutorial-invite]').count()===0);
    await open(page);
    check(mode+' storage supports reopening at the last step', await page.locator('[data-guide-current="1"]').count()===1);
    if(mode==='blocked')check('Denied storage is explained without a blocking prompt', (await page.locator('.tutorial-storage-note').innerText()).includes('no permite guardar')&&await page.locator('dialog[open]').count()===0);
    await next.context.close();
  }
  check('Tutorial works without external requests',results.external.length===0,results.external);
  check('No browser runtime errors',results.errors.length===0,results.errors);
} catch(error) {results.error=String(error.stack||error);if(page&&!page.isClosed())await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});throw error;}
finally {clearTimeout(timer);save();await browser?.close();server.kill('SIGTERM');fs.rmSync(workspace,{recursive:true,force:true});}})().catch(error=>{console.error(error);process.exitCode=1;});
