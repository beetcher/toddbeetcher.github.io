// persistence.spec.js
// Conversation history and routing table survive page reload.
// Phone number identity: each number has its own isolated conversation.

const { test, expect } = require('@playwright/test');

const ROUTING = JSON.stringify([
  { phoneNumber: '+15559876543', webhookUrl: 'https://example.com/sms' },
]);

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

test('conversation survives page reload', async ({ page }) => {
  // Set routing so the send can succeed
  await page.evaluate((r) => localStorage.setItem('testphone_routing_table', r), ROUTING);

  await page.fill('#my-number', '5551234567');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');

  await page.fill('#dest-number', '5559876543');
  await page.press('#dest-number', 'Tab');

  await page.fill('#message-input', 'Persist me!');
  await page.click('#send-btn');
  await page.waitForSelector('.message.outgoing');
  await expect(page.locator('.message.outgoing .message-body')).toHaveText('Persist me!');

  // Reload WITHOUT clearing localStorage
  await page.reload();

  // Re-enter the same number to load history
  await page.fill('#my-number', '5551234567');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');

  await expect(page.locator('.message.outgoing')).toHaveCount(1);
  await expect(page.locator('.message.outgoing .message-body')).toHaveText('Persist me!');
});

test('each phone number has its own isolated conversation', async ({ page }) => {
  await page.evaluate((r) => localStorage.setItem('testphone_routing_table', r), ROUTING);

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
  // Write routing table to localStorage
  await page.evaluate((r) => localStorage.setItem('testphone_routing_table', r), ROUTING);

  // Reload without clearing
  await page.reload();

  // Open config editor and verify the entry was restored
  await page.keyboard.down('Control');
  await page.keyboard.down('Shift');
  await page.keyboard.press('C');
  await page.keyboard.up('Shift');
  await page.keyboard.up('Control');
  await expect(page.locator('#config-modal')).toHaveClass(/open/);

  await expect(page.locator('input[data-field="phoneNumber"]')).toHaveValue('+15559876543');
  await expect(page.locator('input[data-field="webhookUrl"]')).toHaveValue('https://example.com/sms');
});
