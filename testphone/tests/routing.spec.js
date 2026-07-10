// routing.spec.js
// Routing error on unconfigured destination.
// Add router.spec.js alongside this file when the Fake Twilio Router is wired in.

const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

test('routing error on unconfigured destination shows actionable message', async ({ page }) => {
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
