/* Reach sidebar controls through their visible disclosure buttons in browser tests. */
'use strict';
const assert = require('node:assert/strict');

async function exposeNavigationControl(page, selector) {
  const target = typeof selector === 'string' ? page.locator(selector).first() : selector;
  const inSidebar = await target.evaluate(el => !!el.closest('#workspaceSidebar'));
  if (inSidebar && await page.locator('#sidebarToggle').isVisible()
      && await page.locator('#sidebarToggle').getAttribute('aria-expanded') !== 'true') {
    await page.locator('#sidebarToggle').click();
  }
  const ancestors = await target.evaluate(el => {
    const ids = [];
    for (let parent = el.parentElement?.closest('details'); parent; parent = parent.parentElement?.closest('details')) {
      if (!parent.open) ids.unshift(parent.id);
    }
    return ids;
  });
  for (const id of ancestors) {
    assert.ok(id, 'A closed navigation disclosure has a stable ID');
    await page.locator('[id=' + JSON.stringify(id) + '] > summary').click();
  }
  return target;
}

async function clickNavigationControl(page, selector) {
  await (await exposeNavigationControl(page, selector)).click();
}

module.exports = {exposeNavigationControl, clickNavigationControl};
