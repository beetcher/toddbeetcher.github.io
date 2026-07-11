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
