// config-editor.spec.js
// Modal open/close, CRUD, save validation, unsaved-changes guard.
// Save/validation tests require the Fake Twilio Router (Firebase Emulator).
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

async function openModal(page) {
  await page.keyboard.down('Control');
  await page.keyboard.down('Shift');
  await page.keyboard.press('C');
  await page.keyboard.up('Shift');
  await page.keyboard.up('Control');
  await expect(page.locator('#config-modal')).toHaveClass(/open/);
}

// Clear the routing table before each test so the Config Editor always opens
// to a known-empty state regardless of seed data or prior test state.
async function clearRouter(page) {
  await page.evaluate(async (url) => {
    try {
      await fetch(`${url}/config`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: '[]',
      });
    } catch {
      // Router not running — Config Editor falls back to empty state automatically
    }
  }, ROUTER_URL);
}

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await clearRouter(page);
});

// ── Open / close ──────────────────────────────────────────────────────────────

test('opens on Ctrl+Shift+C', async ({ page }) => {
  await openModal(page);
  await expect(page.locator('#config-modal')).toBeVisible();
});

test('shows empty-table message when no entries exist', async ({ page }) => {
  await openModal(page);
  await expect(page.locator('.config-empty-row')).toBeVisible();
  await expect(page.locator('.config-empty-row td')).toContainText('No entries');
});

test('Cancel button closes modal without saving', async ({ page }) => {
  await openModal(page);
  await page.click('#config-cancel-btn');
  await expect(page.locator('#config-modal')).not.toHaveClass(/open/);
});

// ── CRUD ─────────────────────────────────────────────────────────────────────

test('Add Row button creates an editable row', async ({ page }) => {
  await openModal(page);
  await page.click('#add-row-btn');
  await expect(page.locator('input[data-field="phoneNumber"]')).toHaveCount(1);
  await expect(page.locator('input[data-field="webhookUrl"]')).toHaveCount(1);
});

test('Enter in phone field moves focus to URL field in same row', async ({ page }) => {
  await openModal(page);
  await page.click('#add-row-btn');
  await page.fill('input[data-field="phoneNumber"]', '5551234567');
  await page.press('input[data-field="phoneNumber"]', 'Enter');

  const urlFocused = await page.evaluate(() =>
    document.activeElement === document.querySelector('input[data-field="webhookUrl"]')
  );
  expect(urlFocused).toBe(true);
});

test('Enter in last name field appends a new row (phone → url → name → new row)', async ({ page }) => {
  await openModal(page);
  await page.click('#add-row-btn');
  // Enter in URL moves to name field (new Task-2 tab order)
  await page.press('input[data-field="webhookUrl"]', 'Enter');
  const nameFocused = await page.evaluate(() =>
    document.activeElement === document.querySelector('input[data-field="name"]')
  );
  expect(nameFocused).toBe(true);
  // Enter in name (last row) appends a second row
  await page.press('input[data-field="name"]', 'Enter');
  await expect(page.locator('input[data-field="phoneNumber"]')).toHaveCount(2);
});

test('Delete row button removes that row', async ({ page }) => {
  await openModal(page);
  await page.click('#add-row-btn');
  await page.click('#add-row-btn');
  await expect(page.locator('input[data-field="phoneNumber"]')).toHaveCount(2);
  await page.locator('.delete-row-btn').first().click();
  await expect(page.locator('input[data-field="phoneNumber"]')).toHaveCount(1);
});

// ── Save ─────────────────────────────────────────────────────────────────────

test('Save closes modal and persists valid routing entry', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');
  await openModal(page);
  await page.click('#add-row-btn');
  await page.fill('input[data-field="phoneNumber"]', '5551234567');
  await page.fill('input[data-field="webhookUrl"]', 'https://example.com/sms');
  await page.click('#config-save-btn');

  await expect(page.locator('#config-modal')).not.toHaveClass(/open/);
  // Routing table is now stored in Firestore via the Router — verify by reading back
  const config = await page.evaluate(async (url) => {
    const r = await fetch(`${url}/config`);
    return r.json();
  }, ROUTER_URL);
  const entry = config.find(e => e.phoneNumber === '+15551234567');
  expect(entry).toBeDefined();
  expect(entry.webhookUrl).toBe('https://example.com/sms');
});

test('Save shows inline error for invalid phone number', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');
  await openModal(page);
  await page.click('#add-row-btn');
  await page.fill('input[data-field="phoneNumber"]', 'not-a-phone');
  await page.fill('input[data-field="webhookUrl"]', 'https://example.com');
  await page.click('#config-save-btn');

  await expect(page.locator('#config-modal')).toHaveClass(/open/);
  await expect(page.locator('.field-error').first()).toContainText('Invalid phone');
  await expect(page.locator('input[data-field="phoneNumber"]').first()).toHaveClass(/has-error/);
});

test('Save shows inline error for invalid webhook URL', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');
  await openModal(page);
  await page.click('#add-row-btn');
  await page.fill('input[data-field="phoneNumber"]', '5551234567');
  await page.fill('input[data-field="webhookUrl"]', 'not-a-url');
  await page.click('#config-save-btn');

  await expect(page.locator('#config-modal')).toHaveClass(/open/);
  await expect(page.locator('.field-error').first()).toContainText('http');
  await expect(page.locator('input[data-field="webhookUrl"]').first()).toHaveClass(/has-error/);
});

test('Save shows inline error for duplicate phone number', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');
  await openModal(page);
  // Row 0
  await page.click('#add-row-btn');
  await page.fill('input[data-field="phoneNumber"]', '5551234567');
  await page.fill('input[data-field="webhookUrl"]', 'https://example.com');
  // Row 1 — same number
  await page.click('#add-row-btn');
  await page.locator('input[data-field="phoneNumber"]').nth(1).fill('5551234567');
  await page.locator('input[data-field="webhookUrl"]').nth(1).fill('https://other.com');
  await page.click('#config-save-btn');

  await expect(page.locator('#config-modal')).toHaveClass(/open/);
  await expect(page.locator('.field-error')).toContainText('Duplicate');
});

// ── Unsaved changes guard ─────────────────────────────────────────────────────

test('Escape with unsaved changes shows discard dialog; Cancel keeps modal open', async ({ page }) => {
  await openModal(page);
  await page.click('#add-row-btn'); // makes dirty

  let dialogSeen = false;
  page.once('dialog', async (dialog) => {
    dialogSeen = true;
    await dialog.dismiss(); // Cancel
  });
  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);

  expect(dialogSeen).toBe(true);
  await expect(page.locator('#config-modal')).toHaveClass(/open/);
});

test('Escape with unsaved changes, Confirm discards and closes modal', async ({ page }) => {
  await openModal(page);
  await page.click('#add-row-btn');

  page.once('dialog', async (dialog) => await dialog.accept()); // Confirm
  await page.keyboard.press('Escape');
  await page.waitForTimeout(200);

  await expect(page.locator('#config-modal')).not.toHaveClass(/open/);
});

test('Close button with unsaved changes shows discard dialog', async ({ page }) => {
  await openModal(page);
  await page.click('#add-row-btn');

  let dialogSeen = false;
  page.once('dialog', async (dialog) => {
    dialogSeen = true;
    await dialog.accept();
  });
  await page.click('#modal-close');
  await page.waitForTimeout(200);

  expect(dialogSeen).toBe(true);
});

// ── Task 1: Tagline ───────────────────────────────────────────────────────────

test('tagline "Nebagamon Development" is visible in controls header', async ({ page }) => {
  await expect(page.locator('.controls-byline')).toHaveText('Nebagamon Development');
});

// ── Task 2: App Name column in config editor ──────────────────────────────────

test('config table header has App Name column', async ({ page }) => {
  await openModal(page);
  const headers = page.locator('.config-table th');
  await expect(headers).toContainText(['App Name']);
});

test('Add Row creates a row with phone, webhook, and name inputs', async ({ page }) => {
  await openModal(page);
  await page.click('#add-row-btn');
  await expect(page.locator('input[data-field="phoneNumber"]')).toHaveCount(1);
  await expect(page.locator('input[data-field="webhookUrl"]')).toHaveCount(1);
  await expect(page.locator('input[data-field="name"]')).toHaveCount(1);
});

test('Enter in webhook URL field moves focus to name field', async ({ page }) => {
  await openModal(page);
  await page.click('#add-row-btn');
  await page.fill('input[data-field="webhookUrl"]', 'https://example.com/sms');
  await page.press('input[data-field="webhookUrl"]', 'Enter');

  const nameFocused = await page.evaluate(() =>
    document.activeElement === document.querySelector('input[data-field="name"]')
  );
  expect(nameFocused).toBe(true);
});

test('config editor saves entry with name and recalls it on reopen', async ({ page }) => {
  test.skip(!await routerAvailable(page), 'Requires Router: cd router && npm run serve');
  await openModal(page);
  await page.click('#add-row-btn');
  await page.fill('input[data-field="phoneNumber"]', '5551239999');
  await page.fill('input[data-field="webhookUrl"]', 'https://example.com/sms');
  await page.fill('input[data-field="name"]', 'My Test App');
  await page.click('#config-save-btn');
  await expect(page.locator('#config-modal')).not.toHaveClass(/open/);

  // Reopen and verify name was stored and returned by router
  await openModal(page);
  const nameInput = page.locator('input[data-field="name"]').first();
  await expect(nameInput).toHaveValue('My Test App');
});

// ── Task 3: Download button ───────────────────────────────────────────────────

test('download button is present in compose area', async ({ page }) => {
  await expect(page.locator('#download-btn')).toBeVisible();
});

test('download exports conversation JSON with required fields', async ({ page }) => {
  // Set up a conversation in localStorage then reload so app picks it up
  await page.evaluate(() => {
    localStorage.setItem('testphone_conv_+15559990001', JSON.stringify([
      { direction: 'outgoing', body: 'Hello export', timestamp: 1700000000000 },
      { direction: 'incoming', from: '+15550000001', body: 'Reply', timestamp: 1700000001000 },
    ]));
    localStorage.setItem('testphone_last_numbers', JSON.stringify({ my: '+15559990001', dest: null }));
  });
  await page.reload();

  const downloadPromise = page.waitForEvent('download');
  await page.click('#download-btn');
  const download = await downloadPromise;

  const fs = require('fs').promises;
  const content = await fs.readFile(await download.path(), 'utf8');
  const data = JSON.parse(content);

  expect(data.myPhoneNumber).toBe('+15559990001');
  expect(data.messages).toHaveLength(2);
  expect(data.messages[0]).toMatchObject({ direction: 'outgoing', sender: '+15559990001', body: 'Hello export' });
  expect(data.messages[1]).toMatchObject({ direction: 'incoming', sender: '+15550000001', body: 'Reply' });
  expect(data.messages[0].timestamp).toBeDefined();
});

test('download succeeds with raw phone numbers when router is unavailable', async ({ page }) => {
  await page.evaluate(() => {
    localStorage.setItem('testphone_conv_+15559990002', JSON.stringify([
      { direction: 'outgoing', body: 'Offline msg', timestamp: 1700000000000 },
      { direction: 'incoming', from: '+15550000001', body: 'Offline reply', timestamp: 1700000001000 },
    ]));
    localStorage.setItem('testphone_last_numbers', JSON.stringify({ my: '+15559990002', dest: null }));
  });
  await page.reload();

  // Block all router /config calls to simulate router being unreachable
  await page.route('**\/config**', route => route.abort());

  const downloadPromise = page.waitForEvent('download');
  await page.click('#download-btn');
  const download = await downloadPromise;

  const fs = require('fs').promises;
  const content = await fs.readFile(await download.path(), 'utf8');
  const data = JSON.parse(content);

  // Download must succeed even without router
  expect(data.myPhoneNumber).toBe('+15559990002');
  expect(data.messages).toHaveLength(2);
  // Incoming message counterpart falls back to raw phone number
  expect(data.messages[1].resolvedApplicationName).toBe('+15550000001');
});

// ── Task 4: Reset button ──────────────────────────────────────────────────────

test('reset button is present in compose area', async ({ page }) => {
  await expect(page.locator('#reset-btn')).toBeVisible();
});

test('reset archives conversation and starts fresh without clearing other settings', async ({ page }) => {
  await page.evaluate(() => {
    localStorage.setItem('testphone_conv_+15559990003', JSON.stringify([
      { direction: 'outgoing', body: 'To be reset', timestamp: 1700000000000 },
    ]));
    localStorage.setItem('testphone_last_numbers', JSON.stringify({ my: '+15559990003', dest: '+15559997000' }));
    localStorage.setItem('testphone_number_history', JSON.stringify({ my: ['+15559990003'], dest: ['+15559997000'] }));
    localStorage.setItem('testphone_panel_collapsed', 'false');
  });
  await page.reload();

  // Conversation should be loaded
  await expect(page.locator('.message')).toHaveCount(1);

  // Accept the confirm dialog
  page.once('dialog', dialog => dialog.accept());
  await page.click('#reset-btn');

  // Conversation should be cleared
  await expect(page.locator('.conversation-empty')).toBeVisible();
  await expect(page.locator('.message')).toHaveCount(0);

  // An archive key should exist
  const archiveKeys = await page.evaluate(() =>
    Object.keys(localStorage).filter(k => k.startsWith('testphone_archive_'))
  );
  expect(archiveKeys.length).toBeGreaterThan(0);

  // Conversation storage should now be empty array
  const convRaw = await page.evaluate(() => localStorage.getItem('testphone_conv_+15559990003'));
  expect(JSON.parse(convRaw)).toEqual([]);

  // Other settings must be untouched
  const lastNums = await page.evaluate(() => localStorage.getItem('testphone_last_numbers'));
  expect(JSON.parse(lastNums)).toMatchObject({ my: '+15559990003' });

  const history = await page.evaluate(() => localStorage.getItem('testphone_number_history'));
  expect(history).not.toBeNull();

  const panelState = await page.evaluate(() => localStorage.getItem('testphone_panel_collapsed'));
  expect(panelState).toBe('false');
});

test('reset confirm cancel keeps conversation intact', async ({ page }) => {
  await page.evaluate(() => {
    localStorage.setItem('testphone_conv_+15559990004', JSON.stringify([
      { direction: 'outgoing', body: 'Keep me', timestamp: 1700000000000 },
    ]));
    localStorage.setItem('testphone_last_numbers', JSON.stringify({ my: '+15559990004', dest: null }));
  });
  await page.reload();

  await expect(page.locator('.message')).toHaveCount(1);

  page.once('dialog', dialog => dialog.dismiss()); // Cancel
  await page.click('#reset-btn');

  // Conversation must still be there
  await expect(page.locator('.message')).toHaveCount(1);
});

// ── Task 5: Number history combo box ─────────────────────────────────────────

test('number history dropdown appears after a number has been used', async ({ page }) => {
  // Pre-populate history
  await page.evaluate(() => {
    localStorage.setItem('testphone_number_history', JSON.stringify({
      my: ['+15559991234'],
      dest: [],
    }));
  });
  await page.reload();

  // Focus my-number — dropdown should appear
  await page.click('#my-number');
  await expect(page.locator('#my-number-dropdown')).toBeVisible();
  await expect(page.locator('#my-number-dropdown .number-dropdown-item').first())
    .toContainText('(555) 999-1234');
});

test('selecting from history dropdown populates the field', async ({ page }) => {
  await page.evaluate(() => {
    localStorage.setItem('testphone_number_history', JSON.stringify({
      my: ['+15559991234'],
      dest: [],
    }));
  });
  await page.reload();

  await page.click('#my-number');
  await expect(page.locator('#my-number-dropdown')).toBeVisible();
  await page.locator('#my-number-dropdown .number-dropdown-item').first().click();

  await expect(page.locator('#my-number')).toHaveValue('(555) 999-1234');
});

test('entering a new number adds it to history for next time', async ({ page }) => {
  await page.fill('#my-number', '5558887766');
  await page.press('#my-number', 'Tab');

  const history = await page.evaluate(() => {
    const raw = localStorage.getItem('testphone_number_history');
    return raw ? JSON.parse(raw) : {};
  });
  expect(history.my).toContain('+15558887766');
});

// ── Task 6: Collapsible panel ─────────────────────────────────────────────────

test('panel toggle collapses and expands developer controls', async ({ page }) => {
  await expect(page.locator('#controls-col')).toBeVisible();

  await page.click('#panel-toggle-btn');
  await expect(page.locator('#controls-col')).toBeHidden();

  await page.click('#panel-toggle-btn');
  await expect(page.locator('#controls-col')).toBeVisible();
});

test('panel collapsed state persists across reloads', async ({ page }) => {
  await page.click('#panel-toggle-btn');
  await expect(page.locator('#controls-col')).toBeHidden();

  await page.reload();
  await expect(page.locator('#controls-col')).toBeHidden();

  // Clean up: restore to expanded for other tests
  await page.click('#panel-toggle-btn');
  await page.reload();
  await expect(page.locator('#controls-col')).toBeVisible();
});

test('panel toggle button remains visible when panel is collapsed', async ({ page }) => {
  await page.click('#panel-toggle-btn');
  await expect(page.locator('#controls-col')).toBeHidden();

  // Toggle button must still be visible as the way back in
  await expect(page.locator('#panel-toggle-btn')).toBeVisible();
});

test('clicking panel toggle when collapsed restores settings gear access', async ({ page }) => {
  await page.click('#panel-toggle-btn');
  await expect(page.locator('#controls-col')).toBeHidden();
  await expect(page.locator('#settings-gear-btn')).toBeHidden();

  // Restore via toggle
  await page.click('#panel-toggle-btn');
  await expect(page.locator('#controls-col')).toBeVisible();
  await expect(page.locator('#settings-gear-btn')).toBeVisible();
});
