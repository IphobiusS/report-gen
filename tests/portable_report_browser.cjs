const assert = require('node:assert/strict');
const {pathToFileURL} = require('node:url');
let chromium;
try {
  ({chromium} = require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE || 'playwright'));
} catch (_) {
  console.error('Provide Node Playwright via REPORT_GEN_PLAYWRIGHT_MODULE or NODE_PATH');
  process.exit(77);
}
const scenario = process.argv[2], url = pathToFileURL(process.argv[3]).href;
const settle = page => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
const visible = page => page.locator('.finding:visible').evaluateAll(items => items.map(item => item.id));
let browser;
(async () => {
  browser = await chromium.launch({executablePath: process.env.REPORT_GEN_CHROMIUM, headless: true, args: ['--no-sandbox']});
  const page = await browser.newPage({viewport: {width: 1366, height: 850}}), errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const open = async (hash = '') => {
    await page.goto(url + hash);
    await page.evaluate(() => document.fonts.ready);
    await settle(page);
  };
  await open();
  if (scenario === 'layout') {
    for (const width of [320, 360, 390, 601, 768, 1366]) {
      await page.setViewportSize({width, height: 850});await settle(page);
      const layout = await page.evaluate(() => {
        const controls = [...document.querySelectorAll('.report-toolbar input,.report-toolbar select,.report-toolbar button')];
        return {
          width: document.documentElement.scrollWidth, viewport: innerWidth,
          controls: controls.map(el => ({id: el.id, left: el.getBoundingClientRect().left, right: el.getBoundingClientRect().right, height: el.getBoundingClientRect().height})),
          overflow: [document.documentElement, document.body, document.querySelector('main')].map(el => getComputedStyle(el).overflowX),
        };
      });
      assert.ok(layout.width <= layout.viewport, `horizontal overflow at ${width}px: ${JSON.stringify(layout)}`);
      assert.ok(layout.controls.every(control => control.left >= 0 && control.right <= width && control.height >= 44), JSON.stringify(layout.controls));
      assert.ok(layout.overflow.every(value => value !== 'hidden' && value !== 'clip'), 'reflow must not clip report content');
    }
    assert.ok((await page.locator('#F01 pre').textContent()).includes('C'.repeat(900)), 'long literal command retained');
  } else if (scenario === 'same_hash') {
    const link = page.locator('.sumlink[href="#F01"]');
    await link.click();await settle(page);
    assert.equal(await page.evaluate(() => location.hash), '#F01');
    await page.locator('#query').fill('beta sentinel');
    assert.deepEqual(await visible(page), ['F02']);
    await link.click();await settle(page);
    assert.equal(await page.locator('#query').inputValue(), '', 'same-hash link clears incompatible search');
    assert.deepEqual(await visible(page), ['F01', 'F02', 'F03', 'M01']);
    await page.locator('#view').selectOption('executive');
    assert.deepEqual(await visible(page), []);
    await link.click();await settle(page);
    assert.equal(await page.locator('#view').inputValue(), 'technical', 'same-hash link restores technical view');
    assert.equal(await page.locator('#F01').isVisible(), true);
  } else if (scenario === 'anchors') {
    for (const width of [601, 768, 1366]) {
      await page.setViewportSize({width, height: 850});await settle(page);
      await page.locator('.sumlink[href="#F01"]').click();await settle(page);
      const bounds = await page.evaluate(() => ({target: document.getElementById('F01').getBoundingClientRect().top, toolbar: document.querySelector('.report-toolbar').getBoundingClientRect().bottom}));
      assert.ok(bounds.target >= bounds.toolbar + 12, `target under sticky toolbar at ${width}px: ${JSON.stringify(bounds)}`);
      assert.ok(bounds.target < 850, 'anchor target remains in viewport');
    }
    await page.setViewportSize({width: 601, height: 850});await page.goto('about:blank');await open('#F01');
    const initial = await page.evaluate(() => ({target: document.getElementById('F01').getBoundingClientRect().top, toolbar: document.querySelector('.report-toolbar').getBoundingClientRect().bottom}));
    assert.ok(initial.target >= initial.toolbar + 12, `initial deep link respects toolbar: ${JSON.stringify(initial)}`);
  } else if (scenario === 'unicode') {
    for (const query of ['café', 'cafe\u0301', 'CAFÉ', 'CAFE\u0301']) {
      await page.locator('#query').fill(query);
      assert.deepEqual(await visible(page), ['F02', 'F03'], 'canonically equivalent Unicode search: ' + query);
      assert.equal(await page.locator('#results').textContent(), '2 / 4');
    }
    await page.locator('#query').fill('cafe');
    assert.deepEqual(await visible(page), [], 'Unicode normalization keeps meaningful accents');
    await page.locator('#clear-filters').click();
    assert.deepEqual(await visible(page), ['F01', 'F02', 'F03', 'M01']);
  } else if (scenario === 'behavior') {
    await page.keyboard.press('Tab');
    assert.equal(await page.locator('#view').evaluate(el => el === document.activeElement), true, 'view is first keyboard control');
    assert.equal(await page.locator('#view').evaluate(el => getComputedStyle(el).outlineStyle), 'solid', 'keyboard focus has visible outline');
    await page.keyboard.press('ArrowDown');
    assert.deepEqual(await visible(page), [], 'keyboard changes executive view');
    await page.keyboard.press('ArrowUp');
    await page.keyboard.press('Tab');
    assert.equal(await page.locator('#kind').evaluate(el => el === document.activeElement), true);
    await page.keyboard.press('Tab');
    assert.equal(await page.locator('#query').evaluate(el => el === document.activeElement), true);
    await page.keyboard.type('ALPHA SENTINEL');
    assert.deepEqual(await visible(page), ['F01']);
    assert.equal(await page.locator('#results').textContent(), '1 / 4');
    await page.locator('#query').fill('missing sentinel');
    assert.equal(await page.locator('#empty-results').isVisible(), true);
    await page.locator('#clear-filters').click();
    assert.equal(await page.locator('#query').evaluate(el => el === document.activeElement), true, 'clear returns focus to search');
    await page.locator('#severity').selectOption('high');
    assert.deepEqual(await visible(page), ['F01']);
    await page.locator('#kind').selectOption('machine');
    assert.deepEqual(await visible(page), ['M01']);
    assert.equal(await page.locator('#severity').isDisabled(), true);
    assert.equal(await page.locator('#severity').inputValue(), '');
    await page.locator('#clear-filters').click();
    assert.equal(await page.locator('#severity').isDisabled(), false);
    await page.locator('#severity').selectOption('pending');
    assert.deepEqual(await visible(page), ['F03']);
    await page.evaluate(() => {window.print = () => {window.printCalls = (window.printCalls || 0) + 1;};});
    await page.locator('#print').click();
    assert.equal(await page.evaluate(() => window.printCalls), 1, 'print button invokes browser print');
    await page.emulateMedia({media: 'print'});
    assert.equal(await page.locator('.report-toolbar').isVisible(), false);
    assert.deepEqual(await visible(page), ['F03'], 'print preserves current filtered view');
    await page.emulateMedia({media: 'screen'});
    await page.locator('#clear-filters').click();
    await page.locator('#view').selectOption('executive');
    await page.emulateMedia({media: 'print'});
    assert.deepEqual(await visible(page), []);
    assert.equal(await page.locator('.sumtable').isVisible(), true, 'executive print keeps summary');
    const context = await browser.newContext({javaScriptEnabled: false, viewport: {width: 320, height: 850}});
    const fallback = await context.newPage();await fallback.goto(url);
    assert.equal(await fallback.locator('.report-toolbar').isVisible(), false);
    assert.deepEqual(await visible(fallback), ['F01', 'F02', 'F03', 'M01']);
    assert.equal(await fallback.evaluate(() => document.documentElement.scrollWidth), 320);
    await context.close();
  } else throw Error('Unknown portable browser scenario ' + scenario);
  assert.deepEqual(errors, [], 'portable script runs under its actual CSP');
  console.log(JSON.stringify({scenario, passed: true}));
})().catch(error => {console.error(error);process.exitCode = 1;}).finally(async () => {await browser?.close();});
