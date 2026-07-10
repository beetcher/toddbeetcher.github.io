// config-editor.spec.js
// Modal open/close, CRUD, save validation, unsaved-changes guard.

const { test, expect } = require('@playwright/test');

async function openModal(page) {
  await page.keyboard.down('Control');
  await page.keyboard.down('Shift');
  await page.keyboard.press('C');
  await page.keyboard.up('Shift');
  await page.keyboard.up('Control');
  await expect(page.locator('#config-modal')).toHaveClass(/open/);
}

test.beforeEach(async ({ page }) => {
  await page.goto('/');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
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

test('Enter in last URL field appends a new row', async ({ page }) => {
  await openModal(page);
  await page.click('#add-row-btn');
  await page.press('input[data-field="webhookUrl"]', 'Enter');
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
  await openModal(page);
  await page.click('#add-row-btn');
  await page.fill('input[data-field="phoneNumber"]', '5551234567');
  await page.fill('input[data-field="webhookUrl"]', 'https://example.com/sms');
  await page.click('#config-save-btn');

  await expect(page.locator('#config-modal')).not.toHaveClass(/open/);
  const stored = await page.evaluate(() => localStorage.getItem('testphone_routing_table'));
  expect(stored).toContain('+15551234567');
  expect(stored).toContain('https://example.com/sms');
});

test('Save shows inline error for invalid phone number', async ({ page }) => {
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
