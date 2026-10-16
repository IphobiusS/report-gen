/* Reach navigation controls through the visible global or contextual index UI. */
'use strict';
const assert = require('node:assert/strict');

async function exposeNavigationControl(page, selector) {
  const openMode = async mode => {
    const tab = page.locator(mode === 'sections' ? '#contextSectionsTab' : '#contextFindingsTab');
    if (await page.locator('#contextIndex').isVisible()) {
      if (await tab.getAttribute('aria-pressed') !== 'true') await tab.click();
    } else {
      await clickNavigationControl(page, mode === 'sections' ? '#workspaceSections' : '#workspaceFindings');
    }
  };
  // Only the active collection has rows. Open its public launcher before
  // resolving a string selector; Locator callers open their mode explicitly.
  if (typeof selector === 'string') {
    if (/#sectionList\b|#manageSections\b|#contextIndexSectionActions\b/.test(selector)) await openMode('sections');
    else if (/#findingList\b|#(?:libBtn|importFindingsBtn|exportFindingsBtn|contextIndexFindingActions)\b|\[data-add(?:=|\])/.test(selector)) await openMode('findings');
  }
  const target = typeof selector === 'string' ? page.locator(selector).first() : selector;
  const location = await target.evaluate(el => ({
    sidebar: !!el.closest('#workspaceSidebar'),
    context: !!el.closest('#contextIndex'),
    mode: el.closest('#sectionList,#contextIndexSectionActions') ? 'sections'
      : el.closest('#findingList,#contextIndexFindingActions') ? 'findings' : null,
  }));
  if (location.sidebar && await page.locator('#sidebarToggle').isVisible()
      && await page.locator('#sidebarToggle').getAttribute('aria-expanded') !== 'true') {
    await page.locator('#sidebarToggle').click();
  }
  if (location.context) {
    if (location.mode) await openMode(location.mode);
    else if (!await page.locator('#contextIndex').isVisible()) {
      await page.locator('#contextIndexToggle').click();
    }
  }
  const ancestors = await target.evaluate(el => {
    const ids = [];
    let parent = el.parentElement?.closest('details');
    // A summary is itself the disclosure action; expose only its ancestors.
    if (parent && el.tagName === 'SUMMARY' && parent.querySelector(':scope > summary') === el) {
      parent = parent.parentElement?.closest('details');
    }
    for (; parent; parent = parent.parentElement?.closest('details')) {
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
