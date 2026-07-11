// routing.spec.js
// Routing error on unconfigured destination.
// This test requires the Fake Twilio Router (Firebase Emulator) to be running.
// Without it, the test is skipped. To run: cd router && npm run serve

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

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

async function clearRouter(page) {
  await page.evaluate(async (url) => {
    try {
      await fetch(`${url}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: '[]',
      });
    } catch {
      // Router not running — skip
    }
  }, ROUTER_URL);
}

test('routing error on unconfigured destination shows actionable message', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');

  await page.fill('#my-number', '5551234567');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');

  // Destination has no routing entry
  await page.fill('#dest-number', '5550000000');
  await page.press('#dest-number', 'Tab');

  await page.fill('#message-input', 'This should not route');
  await page.click('#send-btn');

  await expect(page.locator('#status-area')).toHaveClass(/status-error/);
  const statusText = await page.locator('#status-area').textContent();
  expect(statusText).toContain('No routing entry');
  expect(statusText).toContain('Ctrl+Shift+C'); // actionable: tells user how to fix it

  // No message should be added to the conversation
  await expect(page.locator('.message')).toHaveCount(0);
});

// ── Task 2: App name on phone screen ─────────────────────────────────────────

test('phone screen shows app name when dest number has a name configured', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');

  await clearRouter(page);

  // Seed a routing entry with a name via the Config API
  await page.evaluate(async (url) => {
    await fetch(`${url}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify([{ phoneNumber: '+15559991111', webhookUrl: 'https://example.com/sms', name: 'My Test App' }]),
    });
  }, ROUTER_URL);

  await page.fill('#dest-number', '5559991111');
  await page.press('#dest-number', 'Tab');

  await expect(page.locator('#phone-contact-header')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('.phone-contact-name')).toContainText('My Test App');
  await expect(page.locator('.phone-contact-sub')).toContainText('(555) 999-1111');
});

test('phone screen shows formatted phone number when no name is configured', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');

  await clearRouter(page);

  // Seed entry without name
  await page.evaluate(async (url) => {
    await fetch(`${url}/config`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify([{ phoneNumber: '+15559991112', webhookUrl: 'https://example.com/sms' }]),
    });
  }, ROUTER_URL);

  await page.fill('#dest-number', '5559991112');
  await page.press('#dest-number', 'Tab');

  await expect(page.locator('#phone-contact-header')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('.phone-contact-name')).toContainText('(555) 999-1112');
  // No sub-label when there's no app name
  await expect(page.locator('.phone-contact-sub')).toHaveCount(0);
});

test('phone screen hides contact header when destination is cleared', async ({ page }) => {
  await page.fill('#dest-number', '5559991112');
  await page.press('#dest-number', 'Tab');

  // Clear the dest field
  await page.fill('#dest-number', '');
  await page.press('#dest-number', 'Tab');

  await expect(page.locator('#phone-contact-header')).not.toHaveClass(/has-contact/);
});
