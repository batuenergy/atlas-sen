const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => { try { localStorage.setItem('atlasIntroSeen', '1'); } catch (e) {} });
  await page.goto('/index.html');
  await page.waitForFunction(() => typeof window.__ATLAS_DATA__ !== 'undefined', null, { timeout: 15000 });
});

// Regression: off-canvas panels used to extend the document and let the page scroll,
// which made the fixed UI drift off-screen.
test('no horizontal page overflow', async ({ page }) => {
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(1);
});

// Regression: the "Capas y filtros" pill drifted away when the page scrolled
// (it was position:absolute; now position:fixed).
test('layer pill stays put when the page is scrolled', async ({ page }) => {
  const before = await page.locator('#pill-ctrl').boundingBox();
  await page.evaluate(() => window.scrollTo(400, 400));
  const after = await page.locator('#pill-ctrl').boundingBox();
  expect(Math.round(after.x)).toBe(Math.round(before.x));
  expect(Math.round(after.y)).toBe(Math.round(before.y));
});

// Regression: opening the filters sheet over the expanded demand lane used to trap the
// user with no reachable close control.
test('panels never deadlock', async ({ page }) => {
  await page.waitForSelector('#pill-demand', { state: 'visible', timeout: 15000 });
  await page.click('#pill-demand');
  await page.click('#d_big'); // expand
  await expect(page.locator('#dlane')).toHaveClass(/open/);

  await page.click('#pill-ctrl'); // open filters sheet
  await expect(page.locator('#sheet')).toHaveClass(/open/);
  await expect(page.locator('#dlane')).not.toHaveClass(/open/); // mutual exclusivity

  await page.click('#sheet-x'); // explicit close button exists and works
  await expect(page.locator('#sheet')).not.toHaveClass(/open/);
});
