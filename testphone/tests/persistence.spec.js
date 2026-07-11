// persistence.spec.js
// Conversation history and routing table survive page reload.
// Phone number identity: each number has its own isolated conversation.
// Tests that send messages or read the routing table require the Fake Twilio Router.
// Without it, those tests are skipped. To run: cd router && npm run serve

const { test, expect } = require('@playwright/test');

const ROUTER_URL = 'http://127.0.0.1:5001/test-phone-router/us-central1/router';

async function routerAvailable(page) {
  try {
    return await page.evaluate(async (url) => {
      const r = await fetch(`${url}/config`, { signal: AbortSignal.timeout(2000) });
      return r.ok;
    }, ROUTER_URL);
  } catch {
    return false;
  }
}

async function seedRouting(page) {
  await page.evaluate(async (url) => {
    await fetch(`${url}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify([{ phoneNumber: '+15559876543', webhookUrl: 'https://httpstat.us/200' }]),
    });
  }, ROUTER_URL);
}

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

test('conversation survives page reload', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');
  // Seed routing via Router API
  await seedRouting(page);

  await page.fill('#my-number', '5551234567');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');

  await page.fill('#dest-number', '5559876543');
  await page.press('#dest-number', 'Tab');

  await page.fill('#message-input', 'Persist me!');
  await page.click('#send-btn');
  await page.waitForSelector('.message.outgoing');
  await expect(page.locator('.message.outgoing .message-body')).toHaveText('Persist me!');

  // Reload without clearing localStorage
  await page.reload();

  // Pre-fill now restores both fields automatically — no need to re-enter
  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');
  await expect(page.locator('#dest-number')).toHaveValue('(555) 987-6543');
  await expect(page.locator('.message.outgoing')).toHaveCount(1);
  await expect(page.locator('.message.outgoing .message-body')).toHaveText('Persist me!');
});

test('each phone number has its own isolated conversation', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');
  // Seed routing via Router API
  await seedRouting(page);

  // Phone A sends a message
  await page.fill('#my-number', '5551111111');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 111-1111');

  await page.fill('#dest-number', '5559876543');
  await page.press('#dest-number', 'Tab');

  await page.fill('#message-input', 'From phone A');
  await page.click('#send-btn');
  await page.waitForSelector('.message.outgoing');

  // Switch to phone B — conversation should be empty
  await page.fill('#my-number', '5552222222');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 222-2222');
  await expect(page.locator('.message')).toHaveCount(0);
  await expect(page.locator('.conversation-empty')).toBeVisible();

  // Switch back to phone A — message should still be there
  await page.fill('#my-number', '5551111111');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 111-1111');
  await expect(page.locator('.message.outgoing')).toHaveCount(1);
});

test('routing table survives page reload', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');
  // Seed routing via Router API — localStorage routing is no longer read by routerClient
  await page.evaluate(async (url) => {
    await fetch(`${url}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify([{ phoneNumber: '+15559876543', webhookUrl: 'https://example.com/sms' }]),
    });
  }, ROUTER_URL);

  // Reload — getConfig() reads from Router, not localStorage
  await page.reload();

  // Open config editor and verify the entry was restored from the Router
  await page.keyboard.down('Control');
  await page.keyboard.down('Shift');
  await page.keyboard.press('C');
  await page.keyboard.up('Shift');
  await page.keyboard.up('Control');
  await expect(page.locator('#config-modal')).toHaveClass(/open/);

  await expect(page.locator('input[data-field="phoneNumber"]')).toHaveValue('+15559876543');
  await expect(page.locator('input[data-field="webhookUrl"]')).toHaveValue('https://example.com/sms');
});
