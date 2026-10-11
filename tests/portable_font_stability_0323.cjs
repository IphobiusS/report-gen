const assert = require('node:assert/strict');
const fs = require('node:fs');
let chromium;
try {
  ({chromium} = require(process.env.REPORT_GEN_PLAYWRIGHT_MODULE || 'playwright'));
} catch (_) {
  console.error('Provide Playwright via REPORT_GEN_PLAYWRIGHT_MODULE');
  process.exit(77);
}

// Keep the exported font bytes and display policy. Isolate Report so a valid
// native Calibri installation cannot bypass the embedded-font path under test.
const exported = fs.readFileSync(process.argv[2], 'utf8');
const embedded = exported.match(/data:font\/ttf;base64,([A-Za-z0-9+/=]+)/);
assert.ok(embedded, 'the fixture must contain the actual exported font');
const fontBytes = Buffer.from(embedded[1], 'base64');
const isolated = exported.replace('</head>',
  '<style>body,.cover h1,.f-title{font-family:Report,monospace!important}</style></head>');
const origin = 'http://report-font.test';
const selectors = ['.cover h1', '#F01 .f-title'];
let browser;
const observations = [];

(async () => {
  try {
    browser = await chromium.launch({
      executablePath: process.env.REPORT_GEN_CHROMIUM,
      headless: true,
      args: ['--no-sandbox'],
    });
    // The delayed transport deterministically exercises the display timeout.
    // No live network is used. The page retains the product's font-display
    // descriptor; only the test font URL and its CSP permission are replaced.
    for (const delayed of [false, true]) {
      const context = await browser.newContext({viewport: {width: 375, height: 1000}});
      try {
        const page = await context.newPage();
        const errors = [];
        page.on('pageerror', error => errors.push(error.message));
        let fontRequests = 0;
        const html = delayed ? isolated
          .replace(embedded[0], `${origin}/Carlito-Regular.ttf`)
          .replace('font-src data:', `font-src data: ${origin}`) : isolated;
        await context.route('**/*', async route => {
          const url = route.request().url();
          if (url === `${origin}/report.html`) {
            await route.fulfill({status: 200, contentType: 'text/html; charset=utf-8', body: html});
          } else if (delayed && url === `${origin}/Carlito-Regular.ttf`) {
            fontRequests++;
            await new Promise(resolve => setTimeout(resolve, 800));
            await route.fulfill({status: 200, contentType: 'font/ttf', body: fontBytes});
          } else {
            await route.abort('blockedbyclient');
          }
        });
        const cdp = await context.newCDPSession(page);
        await cdp.send('DOM.enable');
        await cdp.send('CSS.enable');
        await page.goto(`${origin}/report.html`, {waitUntil: 'domcontentloaded'});
        // Force layout while the controlled font response is still pending.
        await page.locator('#F01 .f-title').evaluate(element => element.getBoundingClientRect().height);
        await page.evaluate(async () => {
          await document.fonts.ready;
          await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
        });
        const faces = await page.evaluate(() => [...document.fonts].map(font => ({
          family: font.family, status: font.status,
        })));
        const {root} = await cdp.send('DOM.getDocument');
        const rendered = [];
        for (const selector of selectors) {
          const {nodeId} = await cdp.send('DOM.querySelector', {nodeId: root.nodeId, selector});
          assert.ok(nodeId, `font probe missing: ${selector}`);
          const {fonts} = await cdp.send('CSS.getPlatformFontsForNode', {nodeId});
          rendered.push({selector, fonts});
        }
        observations.push({transport: delayed ? 'controlled-late-font' : 'embedded',
                           fontRequests, faces, rendered});
        assert.deepEqual(errors, [], 'report JavaScript remains valid');
        if (delayed) assert.equal(fontRequests, 1, 'late-font path must actually be requested');
        assert.ok(faces.some(font => font.family === 'Report' && font.status === 'loaded'),
                  'the real exported font finished loading');
        for (const {selector, fonts} of rendered) {
          const used = fonts.filter(font => font.glyphCount > 0);
          assert.ok(used.length > 0 && used.every(font => font.isCustomFont && font.familyName === 'Carlito'),
                    `${selector} kept a fallback after fonts.ready: ${JSON.stringify({delayed, fonts})}`);
        }
      } finally {
        await context.close();
      }
    }
    console.log(JSON.stringify({passed: true, browser: browser.version(), observations}));
  } finally {
    if (browser) await browser.close();
  }
})().catch(error => {
  console.error(JSON.stringify({passed: false, observations}));
  console.error(error);
  process.exitCode = 1;
});
