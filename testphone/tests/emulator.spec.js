// emulator.spec.js
// Layout, phone identity, display formatting, send/receive, auto-reply, flash, empty-send validation.
// Tests in the "with routing configured" block and some others require the Fake Twilio Router
// (Firebase Emulator). Without it, those tests are skipped.
// To run all: cd router && npm run serve, then USE_ROUTER=1 npx playwright test

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

// Each test gets a clean localStorage so it starts from a known state.
// A reload after clearing ensures the app initialises from scratch.
test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
});

// ── Layout ────────────────────────────────────────────────────────────────────

test('phone frame and developer controls are visible', async ({ page }) => {
  await expect(page.locator('.phone-frame')).toBeVisible();
  await expect(page.locator('#my-number')).toBeVisible();
  await expect(page.locator('#dest-number')).toBeVisible();
  await expect(page.locator('#send-btn')).toBeVisible();
  await expect(page.locator('#message-input')).toBeVisible();
  await expect(page.locator('.controls-title')).toHaveText('Test Phone');
});

// ── Empty state ───────────────────────────────────────────────────────────────

test('conversation shows prompt before a phone number is entered', async ({ page }) => {
  await expect(page.locator('.conversation-empty'))
    .toHaveText('Enter My Phone Number to get started.');
});

// ── Phone identity & formatting ───────────────────────────────────────────────

test('My Phone Number normalizes and formats to (xxx) xxx-xxxx on blur', async ({ page }) => {
  await page.fill('#my-number', '5551234567');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');
});

test('entering a phone number transitions conversation to empty state', async ({ page }) => {
  await page.fill('#my-number', '5551234567');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');
  await expect(page.locator('.conversation-empty')).toHaveText('No messages yet.');
});

test('Destination Phone Number formats to (xxx) xxx-xxxx on blur', async ({ page }) => {
  await page.fill('#dest-number', '5559876543');
  await page.press('#dest-number', 'Tab');
  await expect(page.locator('#dest-number')).toHaveValue('(555) 987-6543');
});

// ── Empty send validation ─────────────────────────────────────────────────────

test('empty send shows validation error and does not add a message', async ({ page }) => {
  await page.fill('#my-number', '5551234567');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');

  await page.fill('#dest-number', '5559876543');
  await page.press('#dest-number', 'Tab');

  // Send with empty body
  await page.click('#send-btn');

  await expect(page.locator('#status-area')).toHaveText('Type a message first.');
  await expect(page.locator('#status-area')).toHaveClass(/status-error/);
  await expect(page.locator('.message')).toHaveCount(0);
});

// ── Last-used number persistence ─────────────────────────────────────────────

test('pre-fills both fields and restores conversation on reload', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');

  // Seed routing table directly (bypasses SSRF guard — localhost webhook requires direct-seed).
  await page.evaluate(async (url) => {
    await fetch(`${url}/test/direct-seed`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify([{ phoneNumber: '+15559876543', webhookUrl: 'http://127.0.0.1:3099/webhook' }]),
    });
  }, ROUTER_URL);

  await page.fill('#my-number', '5551234567');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');

  await page.fill('#dest-number', '5559876543');
  await page.press('#dest-number', 'Tab');
  await expect(page.locator('#dest-number')).toHaveValue('(555) 987-6543');

  await page.fill('#message-input', 'Remember this');
  await page.click('#send-btn');
  await page.waitForSelector('.message.outgoing');

  // Reload without clearing localStorage
  await page.reload();

  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');
  await expect(page.locator('#dest-number')).toHaveValue('(555) 987-6543');
  await expect(page.locator('.message.outgoing .message-body')).toHaveText('Remember this');
});

test('clearing a field to empty removes it from stored values', async ({ page }) => {
  // Set both numbers
  await page.fill('#my-number', '5551234567');
  await page.press('#my-number', 'Tab');
  await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');

  await page.fill('#dest-number', '5559876543');
  await page.press('#dest-number', 'Tab');
  await expect(page.locator('#dest-number')).toHaveValue('(555) 987-6543');

  // Clear my-number explicitly
  await page.fill('#my-number', '');
  await page.press('#my-number', 'Tab');

  // Reload — my-number was cleared so should not reappear; dest was not cleared
  await page.reload();

  await expect(page.locator('#my-number')).toHaveValue('');
  await expect(page.locator('#dest-number')).toHaveValue('(555) 987-6543');
  await expect(page.locator('.conversation-empty'))
    .toHaveText('Enter My Phone Number to get started.');
});

// ── Send / receive ────────────────────────────────────────────────────────────
// These tests require the Router (Firebase Emulator) to be running.
// routerClient now calls the Router instead of reading localStorage for routing.

test.describe('with routing configured', () => {
  test.beforeEach(async ({ page }) => {
    // Seed routing directly (bypasses SSRF guard — localhost webhook for auto-reply support).
    // Silently skips if Router is not running; individual tests check routerAvailable().
    await page.evaluate(async (url) => {
      try {
        await fetch(`${url}/test/direct-seed`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify([{ phoneNumber: '+15559876543', webhookUrl: 'http://127.0.0.1:3099/webhook' }]),
        });
      } catch {
        // Router not running
      }
    }, ROUTER_URL);

    await page.fill('#my-number', '5551234567');
    await page.press('#my-number', 'Tab');
    await expect(page.locator('#my-number')).toHaveValue('(555) 123-4567');
    await page.fill('#dest-number', '5559876543');
    await page.press('#dest-number', 'Tab');
    await expect(page.locator('#dest-number')).toHaveValue('(555) 987-6543');
  });

  test('send shows Sent status and outgoing bubble', async ({ page }) => {
    test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');
    await page.fill('#message-input', 'Hello from emulator test');
    await page.click('#send-btn');

    await expect(page.locator('#status-area')).toHaveText('Sent');
    await expect(page.locator('#status-area')).toHaveClass(/status-success/);
    await expect(page.locator('.message.outgoing')).toHaveCount(1);
    await expect(page.locator('.message.outgoing .message-body'))
      .toHaveText('Hello from emulator test');
  });

  test('auto-reply arrives as an incoming message', async ({ page }) => {
    test.skip(!await routerAvailable(page), 'Requires Router + webhook: see router.spec.js for full round-trip');
    await page.fill('#message-input', 'Ping');
    await page.click('#send-btn');

    // Mock router delivers reply after ~1.5s + up to 1s polling interval
    await page.waitForSelector('.message.incoming', { timeout: 5000 });
    await expect(page.locator('.message')).toHaveCount(2);
  });

  test('incoming message sender displays in (xxx) xxx-xxxx format', async ({ page }) => {
    test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');
    await page.fill('#message-input', 'Ping');
    await page.click('#send-btn');

    await page.waitForSelector('.message.incoming', { timeout: 5000 });
    const meta = await page.locator('.message.incoming .message-meta').textContent();
    expect(meta).toMatch(/\(555\) 987-6543/);
  });

  test('incoming-flash CSS animation is registered', async ({ page }) => {
    const animName = await page.evaluate(() => {
      const el = document.createElement('div');
      el.className = 'message incoming flash';
      document.body.appendChild(el);
      const name = getComputedStyle(el).animationName;
      el.remove();
      return name;
    });
    expect(animName).toBe('incoming-flash');
  });
});
