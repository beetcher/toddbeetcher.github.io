// router-endpoints.spec.js
// Tests for the settings gear (Part 1) and Router Endpoints popup (Part 2).
// No Router dependency — all assertions use localStorage and getRouterBaseUrl() directly.

const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

// ── Part 1: Settings gear opens Config Editor ─────────────────────────────────

test('settings gear icon is visible in developer controls', async ({ page }) => {
  await expect(page.locator('#settings-gear-btn')).toBeVisible();
});

test('clicking settings gear opens Config Editor modal', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await expect(page.locator('#config-modal')).toHaveClass(/open/);
});

test('Ctrl+Shift+C still opens Config Editor modal', async ({ page }) => {
  await page.keyboard.down('Control');
  await page.keyboard.down('Shift');
  await page.keyboard.press('C');
  await page.keyboard.up('Shift');
  await page.keyboard.up('Control');
  await expect(page.locator('#config-modal')).toHaveClass(/open/);
});

// ── Part 2: Endpoints gear is only reachable via modal ────────────────────────

test('endpoints gear is not visible in the main UI (only inside the closed modal)', async ({ page }) => {
  // Modal is closed by default — its gear must not be accessible
  await expect(page.locator('#endpoints-gear-btn')).not.toBeVisible();
});

test('endpoints gear inside modal footer opens Router Endpoints popup', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await expect(page.locator('#config-modal')).toHaveClass(/open/);
  await page.click('#endpoints-gear-btn');
  await expect(page.locator('#endpoints-popup')).toHaveClass(/open/);
});

// ── Auto-detect default ───────────────────────────────────────────────────────

test('Auto-detect entry is present and active by default', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');

  const autoEntry = page.locator('.endpoint-entry[data-id="auto-detect"]');
  await expect(autoEntry).toBeVisible();
  await expect(autoEntry).toHaveClass(/active/);
});

test('getRouterBaseUrl returns emulator URL on localhost by default', async ({ page }) => {
  const url = await page.evaluate(() => getRouterBaseUrl());
  expect(url).toBe('http://127.0.0.1:5001/test-phone-router/us-central1/router');
});

// ── Adding endpoints ──────────────────────────────────────────────────────────

test('adding a new endpoint saves it to the list', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');

  await page.fill('#endpoint-label-input', 'Staging');
  await page.fill('#endpoint-url-input', 'https://staging.example.com/router');
  await page.click('#endpoint-add-btn');

  await expect(page.locator('.endpoint-entry:not([data-id="auto-detect"]) .endpoint-label')).toHaveText('Staging');

  const list = await page.evaluate(() =>
    JSON.parse(localStorage.getItem('testphone_router_endpoints') || '[]')
  );
  expect(list.some(e => e.label === 'Staging' && e.url === 'https://staging.example.com/router')).toBe(true);
});

// ── Active selection persists and drives router calls ─────────────────────────

test('selecting a custom endpoint persists across reload and is used for router calls', async ({ page }) => {
  // Seed a custom endpoint directly in localStorage
  await page.evaluate(() => {
    const list = [{ id: 'ep_test', label: 'Custom', url: 'https://custom.example.com/router' }];
    localStorage.setItem('testphone_router_endpoints', JSON.stringify(list));
    localStorage.setItem('testphone_active_router_endpoint', 'ep_test');
  });
  await page.reload();

  // Active selection survives reload
  const activeId = await page.evaluate(() => localStorage.getItem('testphone_active_router_endpoint'));
  expect(activeId).toBe('ep_test');

  // getRouterBaseUrl() returns the custom URL
  const url = await page.evaluate(() => getRouterBaseUrl());
  expect(url).toBe('https://custom.example.com/router');
});

test('selecting an endpoint via the popup UI takes effect immediately', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');

  // Add a custom endpoint
  await page.fill('#endpoint-label-input', 'Prod');
  await page.fill('#endpoint-url-input', 'https://prod.example.com/router');
  await page.click('#endpoint-add-btn');

  // Get the generated id from localStorage
  const list = await page.evaluate(() =>
    JSON.parse(localStorage.getItem('testphone_router_endpoints') || '[]')
  );
  const entry = list.find(e => e.label === 'Prod');

  // Select it
  await page.locator(`.endpoint-entry[data-id="${entry.id}"]`).click();

  // Verify getRouterBaseUrl() now returns the selected URL (no reload needed)
  const url = await page.evaluate(() => getRouterBaseUrl());
  expect(url).toBe('https://prod.example.com/router');
});

// ── Deletion ──────────────────────────────────────────────────────────────────

test('Auto-detect entry cannot be deleted (no delete button)', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');

  const autoEntry = page.locator('.endpoint-entry[data-id="auto-detect"]');
  await expect(autoEntry.locator('.endpoint-delete-btn')).toHaveCount(0);
});

test('deleting a non-default entry removes it from the list', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');

  await page.fill('#endpoint-label-input', 'ToDelete');
  await page.fill('#endpoint-url-input', 'https://todelete.example.com');
  await page.click('#endpoint-add-btn');

  // Auto-detect + 1 user entry
  await expect(page.locator('.endpoint-entry')).toHaveCount(2);

  await page.locator('.endpoint-entry:not([data-id="auto-detect"]) .endpoint-delete-btn').click();

  // Only auto-detect remains
  await expect(page.locator('.endpoint-entry')).toHaveCount(1);
  await expect(page.locator('.endpoint-entry[data-id="auto-detect"]')).toBeVisible();

  const list = await page.evaluate(() =>
    JSON.parse(localStorage.getItem('testphone_router_endpoints') || '[]')
  );
  expect(list.length).toBe(0);
});

test('deleting the active entry resets selection to Auto-detect', async ({ page }) => {
  await page.evaluate(() => {
    const list = [{ id: 'ep_gone', label: 'Gone', url: 'https://gone.example.com' }];
    localStorage.setItem('testphone_router_endpoints', JSON.stringify(list));
    localStorage.setItem('testphone_active_router_endpoint', 'ep_gone');
  });
  await page.reload();

  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');

  await page.locator('.endpoint-entry:not([data-id="auto-detect"]) .endpoint-delete-btn').click();

  // Active resets to auto-detect
  const activeId = await page.evaluate(() =>
    localStorage.getItem('testphone_active_router_endpoint')
  );
  expect(activeId).toBe('auto-detect');

  // getRouterBaseUrl() falls back to emulator URL on localhost
  const url = await page.evaluate(() => getRouterBaseUrl());
  expect(url).toBe('http://127.0.0.1:5001/test-phone-router/us-central1/router');
});

// ── Validation ────────────────────────────────────────────────────────────────

test('invalid URL is rejected with an error message and entry is not added', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');

  await page.fill('#endpoint-label-input', 'Bad');
  await page.fill('#endpoint-url-input', 'not-a-url');
  await page.click('#endpoint-add-btn');

  await expect(page.locator('#endpoint-add-error')).toContainText('http');
  // Only auto-detect in the list
  await expect(page.locator('.endpoint-entry')).toHaveCount(1);
});

test('non-http/https scheme is rejected', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');

  await page.fill('#endpoint-label-input', 'FTP');
  await page.fill('#endpoint-url-input', 'ftp://example.com/router');
  await page.click('#endpoint-add-btn');

  await expect(page.locator('#endpoint-add-error')).toContainText('http');
  await expect(page.locator('.endpoint-entry')).toHaveCount(1);
});

test('missing label is rejected with an error message', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');

  await page.fill('#endpoint-url-input', 'https://example.com/router');
  await page.click('#endpoint-add-btn');

  await expect(page.locator('#endpoint-add-error')).toContainText('Label');
  await expect(page.locator('.endpoint-entry')).toHaveCount(1);
});

// ── Switch back to Auto-detect ────────────────────────────────────────────────

test('switching back to Auto-detect reverts to auto-detection behavior', async ({ page }) => {
  // Start with a custom endpoint active
  await page.evaluate(() => {
    const list = [{ id: 'ep_custom', label: 'Custom', url: 'https://custom.example.com' }];
    localStorage.setItem('testphone_router_endpoints', JSON.stringify(list));
    localStorage.setItem('testphone_active_router_endpoint', 'ep_custom');
  });
  await page.reload();

  // Confirm custom is active
  let url = await page.evaluate(() => getRouterBaseUrl());
  expect(url).toBe('https://custom.example.com');

  // Open popup and select Auto-detect
  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');
  await page.locator('.endpoint-entry[data-id="auto-detect"]').click();

  // Auto-detect is now active — on localhost returns the emulator URL
  url = await page.evaluate(() => getRouterBaseUrl());
  expect(url).toBe('http://127.0.0.1:5001/test-phone-router/us-central1/router');
});

// ── Popup close behavior ──────────────────────────────────────────────────────

test('clicking outside the endpoint popup closes it', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');
  await expect(page.locator('#endpoints-popup')).toHaveClass(/open/);

  await page.locator('#endpoints-popup').click({ position: { x: 5, y: 5 } });
  await expect(page.locator('#endpoints-popup')).not.toHaveClass(/open/);
});

test('Escape closes the endpoint popup', async ({ page }) => {
  await page.click('#settings-gear-btn');
  await page.click('#endpoints-gear-btn');
  await expect(page.locator('#endpoints-popup')).toHaveClass(/open/);

  await page.keyboard.press('Escape');
  await expect(page.locator('#endpoints-popup')).not.toHaveClass(/open/);
});
