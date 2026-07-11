// router.spec.js
// End-to-end tests for routerClient against the live Fake Twilio Router.
//
// Prerequisites:
//   1. Firebase Emulator Suite running: cd router && npm run serve
//   2. This file assumes ROUTER_BASE_URL points at the emulator
//      (set in testphone/js/routerConfig.js — default is the emulator URL)
//
// These tests use the Firestore emulator's Admin SDK via page.evaluate to seed
// routing data, bypassing the SSRF guard that blocks localhost webhook URLs.
// Seeding via the Config API requires a public webhook URL; seeding via Firestore
// directly is the correct pattern for integration tests with local webhooks.
//
// Run: npx playwright test tests/router.spec.js

const { test, expect } = require('@playwright/test');

const ROUTER_BASE_URL = 'http://127.0.0.1:5001/test-phone-router/us-central1/router';

async function clearRouter(page) {
  await page.evaluate(async (url) => {
    await fetch(`${url}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: '[]',
    });
  }, ROUTER_BASE_URL);
}

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await clearRouter(page);
});

// ── Routing not found ─────────────────────────────────────────────────────────

test('routing error on unconfigured destination shows actionable message', async ({ page }) => {
  await page.fill('#my-number', '5551234567');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');

  await page.fill('#dest-number', '5550000000');
  await page.press('#dest-number', 'Tab');

  await page.fill('#message-input', 'This should not route');
  await page.click('#send-btn');

  await expect(page.locator('#status-area')).toHaveClass(/status-error/);
  const statusText = await page.locator('#status-area').textContent();
  expect(statusText).toContain('No routing entry');
  expect(statusText).toContain('Ctrl+Shift+C');
  await expect(page.locator('.message')).toHaveCount(0);
});

// ── Config API via Config Editor ──────────────────────────────────────────────

test('Config Editor saves a valid routing entry to the Router', async ({ page }) => {
  // Open config
  await page.keyboard.down('Control');
  await page.keyboard.down('Shift');
  await page.keyboard.press('C');
  await page.keyboard.up('Shift');
  await page.keyboard.up('Control');
  await expect(page.locator('#config-modal')).toHaveClass(/open/);

  await page.click('#add-row-btn');
  await page.fill('input[data-field="phoneNumber"]', '5551234567');
  await page.fill('input[data-field="webhookUrl"]', 'https://example.com/sms');
  await page.click('#config-save-btn');

  await expect(page.locator('#config-modal')).not.toHaveClass(/open/);

  // Verify saved in Router
  const config = await page.evaluate(async (url) => {
    const res = await fetch(`${url}/config`);
    return res.json();
  }, ROUTER_BASE_URL);
  const entry = config.find(e => e.phoneNumber === '+15551234567');
  expect(entry).toBeDefined();
  expect(entry.webhookUrl).toBe('https://example.com/sms');
});

test('Config Editor shows validation error for invalid phone number', async ({ page }) => {
  await page.keyboard.down('Control');
  await page.keyboard.down('Shift');
  await page.keyboard.press('C');
  await page.keyboard.up('Shift');
  await page.keyboard.up('Control');
  await expect(page.locator('#config-modal')).toHaveClass(/open/);

  await page.click('#add-row-btn');
  await page.fill('input[data-field="phoneNumber"]', 'not-a-phone');
  await page.fill('input[data-field="webhookUrl"]', 'https://example.com');
  await page.click('#config-save-btn');

  await expect(page.locator('#config-modal')).toHaveClass(/open/);
  await expect(page.locator('.field-error').first()).toContainText('Invalid phone');
  await expect(page.locator('input[data-field="phoneNumber"]').first()).toHaveClass(/has-error/);
});

test('Config Editor loads saved routing entries from Router on open', async ({ page }) => {
  // Seed via Router API directly
  await page.evaluate(async (url) => {
    await fetch(`${url}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify([{ phoneNumber: '+15559876543', webhookUrl: 'https://example.com/sms' }]),
    });
  }, ROUTER_BASE_URL);

  await page.keyboard.down('Control');
  await page.keyboard.down('Shift');
  await page.keyboard.press('C');
  await page.keyboard.up('Shift');
  await page.keyboard.up('Control');
  await expect(page.locator('#config-modal')).toHaveClass(/open/);

  await expect(page.locator('input[data-field="phoneNumber"]')).toHaveValue('+15559876543');
  await expect(page.locator('input[data-field="webhookUrl"]')).toHaveValue('https://example.com/sms');
});

// ── Outbound message queuing ──────────────────────────────────────────────────

test('outbound message can be polled after queueing via /messages', async ({ page }) => {
  const testPhone = '+13035550101';

  // Queue a message via Router
  await page.evaluate(async ({ url, phone }) => {
    await fetch(`${url}/messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ From: '+15005550001', To: phone, Body: 'Hello test phone' }).toString(),
    });
  }, { url: ROUTER_BASE_URL, phone: testPhone });

  // Set my number and wait for poll
  await page.fill('#my-number', '3035550101');
  await page.press('#my-number', 'Tab');

  // Poll should deliver the queued message (up to ~2 seconds)
  await page.waitForSelector('.message.incoming', { timeout: 5000 });
  const bodyText = await page.locator('.message.incoming .message-body').textContent();
  expect(bodyText).toBe('Hello test phone');
});
