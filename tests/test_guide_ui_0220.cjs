/* Optional first-report guide: real navigation, read-only learning and graceful failure. */
'use strict';
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');

const root = path.resolve(process.env.REPORT_GEN_TOOL_ROOT || path.join(__dirname, '..'));
const args = process.argv.slice(2);
const option = (name, fallback) => args.includes(name) ? args[args.indexOf(name) + 1] : fallback;
const output = path.resolve(option('--output', 'out/guide-ui-0220'));
const contract = option('--contract', 'all');
const {chromium} = require(require.resolve('playwright', {
  paths: [root, process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES || root]
}));
fs.mkdirSync(output, {recursive: true});
const results = {contract, checks: [], errors: [], geometry: [], accessibility: []};
let browser, server, workspace, base;
const digest = value => crypto.createHash('sha256').update(value).digest('hex');
function check(name, condition, detail, defer = false) {
  results.checks.push({name, passed: Boolean(condition), ...(detail === undefined ? {} : {detail})});
  if (!defer) assert.ok(condition, name + (detail === undefined ? '' : ': ' + JSON.stringify(detail)));
  console.log((condition ? 'PASS ' : 'FAIL ') + name);
  return Boolean(condition);
}
async function ready(page) {
  await page.waitForFunction(() => typeof S !== 'undefined' && Boolean(document.querySelector('.workspace-dashboard')));
}
async function settled(page) {
  await page.waitForFunction(() => !projectStore.loading && !projectStore.saving && !projectStore.dirty && !projectStore.lastError && projectBusyCount === 0);
}
async function contextPage({width = 1366, language = 'es', blockGuide = false} = {}) {
  const context = await browser.newContext({viewport: {width, height: 1000}, reducedMotion: 'reduce', acceptDownloads: true});
  const page = await context.newPage();
  page.on('pageerror', error => results.errors.push({url: page.url(), message: error.message}));
  await page.addInitScript(language => {
    localStorage.setItem('rg.previewVisible', '0');
    localStorage.setItem('rg.uiLang', language);
  }, language);
  if (blockGuide) await page.route('**/static/guide.js', route => route.abort());
  await page.goto(base);
  await ready(page);
  return {context, page};
}
async function createOwnProject(page, slug) {
  if (!await page.locator('#newProjectBtn').isVisible()) await page.locator('#studioMore > summary').click();
  await page.locator('#newProjectBtn').click();
  const modal = page.locator('#newModal');
  await modal.waitFor({state: 'visible'});
  await modal.locator('#mTitle').fill('Synthetic first report');
  await modal.locator('#mClient').fill('Synthetic Client .example');
  await modal.locator('#mSlug').fill(slug);
  await modal.locator('#mCreate').click();
  await page.waitForFunction(slug => S.slug === slug && !projectStore.loading && projectBusyCount === 0, slug);
  await settled(page);
}
async function emptyFindingContract(page, slug) {
  await createOwnProject(page, slug);
  await page.locator('#navFindings').click();
  await page.waitForFunction(() => S.sel.type === 'findings');
  const create = page.locator('[data-finding-create="blank"]');
  check('Empty findings exposes a reachable native add action', await create.isVisible() && await create.isEnabled());
  const before = await page.evaluate(() => S.data.findings.length);
  await create.focus();
  await page.keyboard.press('Enter');
  await page.waitForFunction(before => S.sel.type === 'finding' && S.data.findings.length === before + 1, before);
  const focus = await page.evaluate(() => ({type: S.sel.type, id: document.activeElement.id, tag: document.activeElement.tagName, inside: document.querySelector('#editor').contains(document.activeElement)}));
  check('Explicit add from empty findings opens the new editor and focuses its content', focus.type === 'finding' && focus.inside, focus);
  await settled(page);
  check('Explicit new finding is persisted in the own project', /findings:/.test(fs.readFileSync(path.join(workspace, 'projects', slug, 'engagement.yaml'), 'utf8')) && await page.evaluate(() => S.data.findings.length === 1));
}
async function openGuide(page) {
  const launcher = page.locator('#guideBtn');
  if (!await launcher.isVisible()) {
    const more = page.locator('#studioMore > summary');
    if (await more.isVisible()) await more.click();
    else {
      const navigation = page.locator('#sidebarToggle');
      if (await navigation.isVisible()) await navigation.click();
    }
  }
  await launcher.click();
  await page.locator('[data-guide-page]').waitFor({state: 'visible'});
  await page.waitForFunction(() => S.sel.type === 'guide');
}
async function snapshot(page) {
  const state = await page.evaluate(() => ({
    slug: S.slug, data: JSON.stringify(S.data), revision: projectStore.revision,
    savedRevision: projectStore.savedRevision, etag: projectStore.etag, dirty: projectStore.dirty
  }));
  return {...state, yaml: state.slug ? digest(fs.readFileSync(path.join(workspace, 'projects', state.slug, 'engagement.yaml'))) : null};
}
async function selectStep(page, index) {
  await page.locator('[data-guide-step="' + index + '"]').click();
  await page.locator('.guide-stage[data-guide-current="' + index + '"]').waitFor({state: 'visible'});
}
async function preference(page, id) {
  if (!await page.locator('#' + id).isVisible()) {
    if (!await page.locator('#studioMore').evaluate(element => element.open)) await page.locator('#studioMore > summary').click();
    if (!await page.locator('#studioPreferences').evaluate(element => element.open)) await page.locator('#studioPreferences > summary').click();
  }
  await page.locator('#' + id).click();
  if (await page.locator('#studioMore').evaluate(element => element.open)) await page.locator('#studioMore > summary').click();
}
async function guideFocusContract(page) {
  results.focusGeometry ||= [];
  const passed = [];
  for (const width of [320, 390, 1366]) for (const textPercent of [100, 200]) {
    await page.setViewportSize({width, height: 720});
    await page.evaluate(value => { document.documentElement.style.fontSize = value + '%'; }, textPercent);
    await openGuide(page);
    await selectStep(page, 0);
    for (const action of ['step', 'next', 'previous']) {
      if (action === 'next') await page.locator('#guideNext').click();
      if (action === 'previous') await page.locator('#guidePrev').click();
      const geometry = await page.locator('#guideStepTitle').evaluate(element => {
        const bounds = element.getBoundingClientRect();
        return {top: bounds.top, bottom: bounds.bottom, viewportHeight: innerHeight, scrollY, focused: document.activeElement === element};
      });
      const label = width + '/root-text-' + textPercent + '/' + action;
      results.focusGeometry.push({label, ...geometry});
      passed.push(check(label + ' focuses the current step heading inside the real viewport', geometry.focused && geometry.top >= -1 && geometry.bottom <= geometry.viewportHeight + 1, geometry, true));
    }
  }
  assert.ok(passed.every(Boolean), 'Every guide step focus must be visible in the real viewport after selection, Next and Previous.');
}
async function axeGuide(page, label) {
  const candidate = process.env.RG_AXE_PATH;
  if (!candidate || !fs.existsSync(candidate)) {
    if (!results.accessibility.some(entry => entry.status === 'not-run')) results.accessibility.push({status: 'not-run', reason: 'Set RG_AXE_PATH to a local axe-core script to run automated guide checks.'});
    return;
  }
  if (!await page.evaluate(() => typeof window.axe !== 'undefined')) {
    // Keep the real CSP active. The disposable browser supplies a same-origin QA script.
    await page.route('**/__qa__/axe-core.js', route => route.fulfill({contentType: 'application/javascript', body: fs.readFileSync(candidate)}));
    await page.addScriptTag({url: base + '/__qa__/axe-core.js'});
    results.axe = {source: candidate, sha256: digest(fs.readFileSync(candidate))};
  }
  const audit = await page.evaluate(async () => {
    const report = await axe.run('[data-guide-page]', {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}});
    return {
      violations: report.violations.map(item => ({id: item.id, impact: item.impact, nodes: item.nodes.map(node => ({target: node.target, summary: node.failureSummary}))})),
      incomplete: report.incomplete.map(item => ({id: item.id, nodes: item.nodes.length}))
    };
  });
  results.accessibility.push({label, ...audit});
  check(label + ' automated guide accessibility has no violations', audit.violations.length === 0, audit.violations);
}

(async () => {
  workspace = fs.mkdtempSync(path.join(os.tmpdir(), 'report-gen-acceptance-0211-'));
  fs.writeFileSync(path.join(workspace, '.test-only'), 'synthetic acceptance workspace');
  server = spawn(process.env.RG_PYTHON || 'python3', [path.join(root, 'scripts/browser-server-0211.py'), '--workspace', workspace], {cwd: root, stdio: ['ignore', 'pipe', 'pipe']});
  server.stderr.pipe(fs.createWriteStream(path.join(output, 'server.log')));
  base = await new Promise((resolve, reject) => {
    let text = '';
    const timer = setTimeout(() => reject(Error('Acceptance server startup timeout')), 25000);
    server.stdout.on('data', data => {
      text += data;
      if (text.includes('\n')) {
        clearTimeout(timer);
        try { resolve(JSON.parse(text.split('\n')[0]).url); } catch (error) { reject(error); }
      }
    });
    server.once('exit', code => { clearTimeout(timer); reject(Error('Acceptance server exited: ' + code)); });
  });
  browser = await chromium.launch({headless: true, executablePath: process.env.REPORT_GEN_CHROMIUM || process.env.RG_CHROMIUM_EXECUTABLE || undefined});
  results.browser = browser.version();
  results.input = root;
  results.server = base;
  fs.writeFileSync(path.join(output, 'server.json'), JSON.stringify({url: base, workspace}, null, 2));
  const first = await contextPage();
  const page = first.page;

  if (contract === 'empty-finding') {
    await emptyFindingContract(page, 'guide-empty-negative');
    await first.context.close();
    return;
  }
  if (contract === 'read-only-editors') {
    await createOwnProject(page, 'guide-read-only-editors');
    const original = await snapshot(page);
    await page.locator('#navReport').click();
    await page.locator('[data-workflow="coverage"]').click();
    await page.getByRole('textbox', {name: 'Limitaciones del trabajo', exact: true}).waitFor();
    await page.locator('#sectionList .finding-nav').filter({hasText: /Alcance|Scope/}).first().click();
    await page.locator('[data-workflow="retest"]').click();
    await page.waitForFunction(() => S.sel.type === 'workflow' && S.sel.idx === 'retest');
    const afterReading = await snapshot(page);
    fs.writeFileSync(path.join(output, 'read-only-editor-snapshots.json'), JSON.stringify({before: original, after: afterReading}, null, 2));
    check('Opening report, coverage, scope and retest editors preserves exact data, YAML and revision', JSON.stringify(afterReading) === JSON.stringify(original), {
      dataUnchanged: afterReading.data === original.data, yamlUnchanged: afterReading.yaml === original.yaml,
      revisionUnchanged: afterReading.revision === original.revision
    });
    await page.locator('#sectionList .finding-nav').filter({hasText: /Alcance|Scope/}).first().click();
    await page.getByRole('textbox', {name: 'Objetivos', exact: true}).fill('Synthetic objective: evaluate the authorized .example portal.');
    await settled(page);
    check('An explicit scope objective edit initializes and saves its field', await page.evaluate(() => S.data.report.sections.find(section => section.key === 'scope').objectives === 'Synthetic objective: evaluate the authorized .example portal.') && fs.readFileSync(path.join(workspace, 'projects', 'guide-read-only-editors', 'engagement.yaml'), 'utf8').includes('Synthetic objective: evaluate the authorized .example portal.'));
    await page.locator('[data-workflow="coverage"]').click();
    await page.getByRole('textbox', {name: 'Limitaciones del trabajo', exact: true}).fill('Synthetic explicit limitation; no production access.');
    await settled(page);
    check('An explicit edit initializes and saves the absent Markdown field', await page.evaluate(() => S.data.limitations_md === 'Synthetic explicit limitation; no production access.') && fs.readFileSync(path.join(workspace, 'projects', 'guide-read-only-editors', 'engagement.yaml'), 'utf8').includes('Synthetic explicit limitation; no production access.'));
    await page.getByRole('checkbox', {name: 'Incluir cobertura y limitaciones', exact: true}).uncheck();
    await settled(page);
    check('An explicit report option change initializes and persists its configuration', await page.evaluate(() => S.data.report.workflow.include_coverage === false) && fs.readFileSync(path.join(workspace, 'projects', 'guide-read-only-editors', 'engagement.yaml'), 'utf8').includes('include_coverage: false'));
    await first.context.close();
    return;
  }

  check('First use remains the normal dashboard without a forced tutorial or dialog', await page.evaluate(() => !S.slug && S.sel.type !== 'guide' && !document.querySelector('dialog[open]') && Boolean(document.querySelector('.workspace-dashboard'))));
  const beforeEmpty = await snapshot(page);
  await openGuide(page);
  check('Guide opens from an empty workspace as a page without creating a demo or project', await page.evaluate(() => !S.slug && S.sel.type === 'guide' && !document.querySelector('dialog[open]')));
  check('Guide has six native keyboard reachable steps and exactly one current step', await page.locator('[data-guide-nav] button[data-guide-step]').count() === 6 && await page.locator('[data-guide-nav] [aria-current="step"]').count() === 1);
  check('Tutorial status is separate from report completion', await page.locator('[data-guide-page] [role="progressbar"]').count() === 0);
  check('Guide is the current page without misidentifying a report workflow screen', await page.locator('#guideBtn').getAttribute('aria-current') === 'page' && await page.locator('[data-studio-nav][aria-current="page"]').count() === 0);
  if (contract === 'guide-entry') return;
  if (contract === 'guide-focus') {
    await guideFocusContract(page);
    await first.context.close();
    return;
  }

  for (let index = 0; index < 6; index++) {
    await selectStep(page, index);
    check('Step ' + (index + 1) + ' focuses the visible heading after keyboard or click navigation', await page.locator('#guideStepTitle').evaluate(element => document.activeElement === element && element.getBoundingClientRect().height > 0));
    check('Step ' + (index + 1) + ' exposes the same active state in navigation and content', await page.locator('[data-guide-step="' + index + '"]').getAttribute('aria-current') === 'step' && await page.evaluate(index => S.sel.idx === index, index));
    check('Step ' + (index + 1) + ' identifies its position as tutorial steps rather than report completion', (await page.locator('.guide-position').innerText()).includes('Paso ' + (index + 1) + ' de 6') && (await page.locator('.guide-position').innerText()).includes('no avance del proyecto'));
    if (index > 0) check('Step ' + (index + 1) + ' explains why report actions require a project', await page.locator('.guide-prerequisite').isVisible() && (await page.locator('.guide-prerequisite').innerText()).includes('sin proyecto') && (await page.locator('.guide-actions [data-guide-action]').evaluateAll(buttons => buttons.every(button => button.disabled))));
  }
  check('Reading all six steps preserves an empty workspace', JSON.stringify(await snapshot(page)) === JSON.stringify(beforeEmpty));
  await selectStep(page, 0);
  const next = page.locator('#guideNext');
  await next.focus();
  await page.keyboard.press('Enter');
  await page.locator('.guide-stage[data-guide-current="1"]').waitFor();
  check('Next accepts Enter and moves focus to the new step heading', await page.locator('#guideStepTitle').evaluate(element => document.activeElement === element));
  await page.locator('#guidePrev').focus();
  await page.keyboard.press('Space');
  await page.locator('.guide-stage[data-guide-current="0"]').waitFor();
  check('Previous accepts Space and moves focus to the prior step heading', await page.locator('#guideStepTitle').evaluate(element => document.activeElement === element));

  // The own-project path is deliberately independent of the seeded Nimbus demo.
  await page.locator('[data-guide-action="new"]').click();
  check('Explicit create action opens the native project dialog', await page.locator('#newModal').evaluate(element => element.open && element.matches(':modal')));
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('dialog[open]'));
  check('Cancelling project creation from the guide does not create report data', JSON.stringify(await snapshot(page)) === JSON.stringify(beforeEmpty));
  await page.locator('[data-guide-action="home"]').click();
  await emptyFindingContract(page, 'guide-own-project');
  const ownSnapshot = await snapshot(page);
  let projectWrites = 0;
  page.on('request', request => {
    if (request.method() === 'PUT' && /\/api\/projects\/[^/?]+$/.test(new URL(request.url()).pathname)) projectWrites++;
  });
  await openGuide(page);
  for (let index = 0; index < 6; index++) await selectStep(page, index);
  const spanishHeading = await page.locator('#guideStepTitle').innerText();
  await preference(page, 'langToggle');
  check('Changing interface language translates the open guide without resetting its step', await page.evaluate(() => S.uiLang === 'en' && S.sel.type === 'guide' && S.sel.idx === 5) && await page.locator('#guideStepTitle').innerText() !== spanishHeading);
  await preference(page, 'langToggle');
  await preference(page, 'themeToggle');
  await preference(page, 'themeToggle');
  check('Opening, reading, translating and theming the guide preserves report revision and exact YAML', JSON.stringify(await snapshot(page)) === JSON.stringify(ownSnapshot) && projectWrites === 0, {projectWrites});

  // Project backup and import are intentional user actions, never triggered by reading the guide.
  await page.evaluate(() => select('workflow', 'backup'));
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', {name: 'Descargar respaldo ZIP', exact: true}).click();
  const backup = await downloadPromise;
  const backupPath = path.join(output, 'synthetic-guide-project.zip');
  await backup.saveAs(backupPath);
  check('Native project backup produces a nonempty ZIP', fs.statSync(backupPath).size > 0 && fs.readFileSync(backupPath).subarray(0, 2).toString() === 'PK');
  await openGuide(page);
  await selectStep(page, 0);
  const filePromise = page.waitForEvent('filechooser');
  await page.locator('[data-guide-action="import"]').click();
  const chooser = await filePromise;
  page.once('dialog', dialog => dialog.accept('guide-restored-project'));
  await chooser.setFiles(backupPath);
  await page.waitForFunction(() => S.slug === 'guide-restored-project' && !projectStore.loading && projectBusyCount === 0);
  await settled(page);
  check('Explicit guide import opens a copy of an own project with its finding intact', await page.evaluate(() => S.slug === 'guide-restored-project' && S.data.findings.length === 1 && !S.slug.includes('nimbus')));

  const restored = await snapshot(page);
  const destinations = [
    [1, 'metadata', 'report'], [1, 'assets', 'workflow', 'assets'],
    [1, 'coverage', 'workflow', 'coverage'], [2, 'findings', 'findings'],
    [3, 'evidence', 'workflow', 'evidence'], [3, 'capture', 'capture'],
    [4, 'review', 'workflow', 'review'], [5, 'delivery-screen', 'studio', 'deliver'],
    [5, 'backup', 'workflow', 'backup'], [5, 'retest', 'workflow', 'retest']
  ];
  for (const [step, action, type, index] of destinations) {
    await openGuide(page);
    await selectStep(page, step);
    await page.locator('[data-guide-action="' + action + '"]').click();
    await page.waitForFunction(({type, index}) => S.sel.type === type && (index === undefined || S.sel.idx === index), {type, index});
    check('Guide action ' + action + ' opens the actual destination for the imported own project', await page.evaluate(() => S.slug === 'guide-restored-project' && document.activeElement.id === 'editor') && await page.locator('[data-guide-page]').count() === 0);
  }
  await openGuide(page);
  await selectStep(page, 1);
  const hasScope = await page.evaluate(() => S.data.report.sections.some(section => section.key === 'scope'));
  if (hasScope) {
    await page.locator('[data-guide-action="scope"]').click();
    await page.waitForFunction(() => S.sel.type === 'section' && S.sel.key === 'scope');
    check('Guide scope action opens the real enabled scope section', await page.locator('[data-guide-page]').count() === 0 && await page.evaluate(() => S.slug === 'guide-restored-project'));
  } else check('Guide does not pretend to open a disabled scope section', await page.locator('[data-guide-action="scope"]').count() === 0 && (await page.locator('[data-guide-page]').innerText()).includes('no está activada'));
  await openGuide(page);
  await selectStep(page, 4);
  await page.locator('[data-guide-action="inspector"]').click();
  const inspector = page.getByRole('dialog', {name: 'Inspector de publicación', exact: true});
  await inspector.waitFor({state: 'visible'});
  check('Guide publication action opens the native inspector without applying changes', await inspector.evaluate(element => element.matches(':modal')));
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('dialog[open]'));
  await selectStep(page, 5);
  await page.locator('[data-guide-action="delivery"]').click();
  const delivery = page.getByRole('dialog', {name: 'Preparar entrega', exact: true});
  await delivery.waitFor({state: 'visible'});
  check('Guide delivery action opens format selection without silently generating files', await delivery.evaluate(element => element.matches(':modal')) && await delivery.locator('[data-delivery-format]').count() === 4);
  await page.keyboard.press('Escape');
  await page.waitForFunction(() => !document.querySelector('dialog[open]'));
  await settled(page);
  const afterDestinations = await snapshot(page);
  fs.writeFileSync(path.join(output, 'destination-snapshots.json'), JSON.stringify({before: restored, after: afterDestinations}, null, 2));
  check('Following guide destinations and dismissing review dialogs preserves exact report data and revision', JSON.stringify(afterDestinations) === JSON.stringify(restored), {
    yamlUnchanged: afterDestinations.yaml === restored.yaml,
    dataUnchanged: afterDestinations.data === restored.data,
    revisionBefore: restored.revision, revisionAfter: afterDestinations.revision,
    etagUnchanged: afterDestinations.etag === restored.etag
  });

  await guideFocusContract(page);

  // Check the tutorial itself at narrow widths and enlarged root text, in both UI languages.
  for (const language of ['es', 'en']) for (const width of [280, 320, 390, 1366]) for (const textPercent of [100, 200]) {
    await page.setViewportSize({width, height: 1000});
    await page.evaluate(({language, textPercent}) => {
      document.documentElement.style.fontSize = textPercent + '%';
      if (S.uiLang !== language) setUiLang(language);
    }, {language, textPercent});
    if (await page.locator('[data-guide-page]').count() === 0) await openGuide(page);
    const label = language + '/' + width + '/root-text-' + textPercent;
    const state = await snapshot(page);
    for (let index = 0; index < 6; index++) {
      await selectStep(page, index);
      const geometry = await page.locator('[data-guide-page]').evaluate(element => {
        const rect = element.getBoundingClientRect();
        const buttons = [...element.querySelectorAll('button')].filter(button => button.getClientRects().length).map(button => {
          const bounds = button.getBoundingClientRect();
          return {name: button.textContent.trim(), width: bounds.width, height: bounds.height};
        });
        return {left: rect.left, right: rect.right, clientWidth: element.clientWidth, scrollWidth: element.scrollWidth, documentWidth: document.documentElement.scrollWidth, innerWidth, buttons};
      });
      results.geometry.push({label, step: index, ...geometry});
      check(label + '/step-' + (index + 1) + ' guide fits without hidden or horizontal overflowing content', geometry.left >= -1 && geometry.right <= width + 1 && geometry.scrollWidth <= geometry.clientWidth + 1, geometry);
      check(label + '/step-' + (index + 1) + ' guide actions retain 44px targets', geometry.buttons.every(button => button.width >= 43.5 && button.height >= 43.5), geometry.buttons.filter(button => button.width < 43.5 || button.height < 43.5));
      check(label + '/step-' + (index + 1) + ' reduced motion has no running guide animation', await page.locator('[data-guide-page]').evaluate(element => element.getAnimations({subtree: true}).filter(animation => animation.playState === 'running').length === 0));
    }
    check(label + ' guide traversal never edits the imported project', JSON.stringify(await snapshot(page)) === JSON.stringify(state));
    if (textPercent === 100 && [320, 1366].includes(width)) {
      await selectStep(page, 2);
      await axeGuide(page, label);
      await page.screenshot({path: path.join(output, 'guide-' + language + '-' + width + '.png'), fullPage: true});
      await preference(page, 'themeToggle');
      await axeGuide(page, label + '/alternate-theme');
      await page.screenshot({path: path.join(output, 'guide-' + language + '-' + width + '-alternate-theme.png'), fullPage: true});
      await preference(page, 'themeToggle');
    }
  }
  await first.context.close();

  const failed = await contextPage({blockGuide: true});
  check('A missing optional guide script leaves the loaded application responsive', await failed.page.locator('#newProjectBtn').isEnabled() && !await failed.page.locator('#splash').count());
  check('A missing optional guide script exposes no dead tutorial launcher', await failed.page.locator('#guideBtn').count() === 0 || !await failed.page.locator('#guideBtn').isVisible() || !await failed.page.locator('#guideBtn').isEnabled());
  if (!await failed.page.locator('#newProjectBtn').isVisible()) await failed.page.locator('#studioMore > summary').click();
  await failed.page.locator('#newProjectBtn').click();
  check('A missing guide script still allows a real new-project dialog', await failed.page.locator('#newModal').evaluate(element => element.open && element.matches(':modal')));
  await failed.context.close();
  check('Guide acceptance run has no JavaScript exceptions', results.errors.length === 0, results.errors);
})().catch(error => {
  results.failure = error.stack;
  console.error(error);
  process.exitCode = 1;
}).finally(async () => {
  await browser?.close();
  server?.kill('SIGTERM');
  results.finished = new Date().toISOString();
  fs.writeFileSync(path.join(output, 'results.json'), JSON.stringify(results, null, 2));
});
