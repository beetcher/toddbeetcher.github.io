// help.spec.js
// Tests for the in-app help modal.
// NOTE: This file is not covered by any existing targeted test run (emulator.spec.js,
// config-editor.spec.js, etc.). Add it to whatever regression scope you use.

const { test, expect } = require('@playwright/test');

test.beforeEach(async ({ page }) => {
  await page.goto('/');
});

async function openHelp(page) {
  await page.click('#help-btn');
  await expect(page.locator('#help-modal')).toHaveClass(/open/);
}

// ── Index view ────────────────────────────────────────────────────────────────

test('help icon opens index view with Overview first and all four group headers', async ({ page }) => {
  await openHelp(page);

  const modal = page.locator('#help-modal');
  await expect(modal).toBeVisible();

  // Overview must be the first topic item
  const items = page.locator('#help-modal-body .help-topic-item');
  await expect(items.first()).toContainText('Overview');

  // Four group headers present in order
  const headers = page.locator('#help-modal-body .help-group-header');
  await expect(headers).toHaveCount(4);
  await expect(headers.nth(0)).toContainText('Getting Started');
  await expect(headers.nth(1)).toContainText('Configuration');
  await expect(headers.nth(2)).toContainText('Managing Conversations');
  await expect(headers.nth(3)).toContainText('Reference');
});

test('Overview appears above the first group header in DOM order', async ({ page }) => {
  await openHelp(page);

  const body = page.locator('#help-modal-body');
  const children = body.locator(':scope > *');
  const count = await children.count();

  // First child should be the Overview topic item, not a group
  const firstChild = children.nth(0);
  await expect(firstChild).toHaveClass(/help-topic-item/);
  await expect(firstChild).toContainText('Overview');

  // Second child should be the first group (Getting Started)
  const secondChild = children.nth(1);
  await expect(secondChild).toHaveClass(/help-group/);
});

// ── Topic → blurb navigation ──────────────────────────────────────────────────

test('clicking a topic shows its blurb', async ({ page }) => {
  await openHelp(page);

  // Click "Routing Configuration" in the Configuration group
  await page.locator('#help-modal-body .help-topic-item', { hasText: 'Routing Configuration' }).click();

  // Modal title updates to topic name
  await expect(page.locator('#help-modal-title')).toHaveText('Routing Configuration');

  // Group headers are gone — index is no longer shown
  await expect(page.locator('#help-modal-body .help-group-header')).toHaveCount(0);

  // Blurb content is present
  await expect(page.locator('#help-modal-body .help-blurb-text')).toBeVisible();

  // Back button is present
  await expect(page.locator('#help-modal-body .help-back-btn')).toBeVisible();
});

test('clicking Overview shows its blurb', async ({ page }) => {
  await openHelp(page);

  await page.locator('#help-modal-body .help-topic-item').first().click();

  await expect(page.locator('#help-modal-title')).toHaveText('Overview');
  await expect(page.locator('#help-modal-body .help-blurb-text')).toBeVisible();
  await expect(page.locator('#help-modal-body .help-back-btn')).toBeVisible();
});

test('Icon Glossary blurb renders as a list, not prose', async ({ page }) => {
  await openHelp(page);

  await page.locator('#help-modal-body .help-topic-item', { hasText: 'Icon Glossary' }).click();

  await expect(page.locator('#help-modal-title')).toHaveText('Icon Glossary');
  await expect(page.locator('#help-modal-body .help-icon-list')).toBeVisible();
  // Should have 6 list items
  await expect(page.locator('#help-modal-body .help-icon-list li')).toHaveCount(6);
});

// ── Back navigation ───────────────────────────────────────────────────────────

test('back button returns to index view', async ({ page }) => {
  await openHelp(page);

  // Navigate into a blurb
  await page.locator('#help-modal-body .help-topic-item', { hasText: 'Keyboard Shortcuts' }).click();
  await expect(page.locator('#help-modal-title')).toHaveText('Keyboard Shortcuts');

  // Go back
  await page.locator('#help-modal-body .help-back-btn').click();

  // Index should be restored
  await expect(page.locator('#help-modal-title')).toHaveText('Help');
  await expect(page.locator('#help-modal-body .help-group-header')).toHaveCount(4);
  await expect(page.locator('#help-modal-body .help-topic-item').first()).toContainText('Overview');
});

// ── Modal close ───────────────────────────────────────────────────────────────

test('X button closes the modal', async ({ page }) => {
  await openHelp(page);

  await page.click('#help-modal-close');
  await expect(page.locator('#help-modal')).not.toHaveClass(/open/);
});

test('clicking outside the modal box closes it', async ({ page }) => {
  await openHelp(page);

  // Click the overlay backdrop (the element itself, not the inner box)
  await page.locator('#help-modal').click({ position: { x: 10, y: 10 } });
  await expect(page.locator('#help-modal')).not.toHaveClass(/open/);
});

test('Escape closes the modal from the index view', async ({ page }) => {
  await openHelp(page);

  await page.keyboard.press('Escape');
  await expect(page.locator('#help-modal')).not.toHaveClass(/open/);
});

test('Escape closes the modal from a blurb view', async ({ page }) => {
  await openHelp(page);

  await page.locator('#help-modal-body .help-topic-item').first().click();
  await expect(page.locator('#help-modal-title')).toHaveText('Overview');

  await page.keyboard.press('Escape');
  await expect(page.locator('#help-modal')).not.toHaveClass(/open/);
});

// ── Router Endpoints exclusion ────────────────────────────────────────────────

test('Router Endpoints switcher is not present in the help modal', async ({ page }) => {
  await openHelp(page);

  const helpModal = page.locator('#help-modal');

  // No text about Router Endpoints appears in the index
  await expect(helpModal).not.toContainText('Router Endpoints');

  // The endpoints gear control does not exist inside the help modal
  await expect(helpModal.locator('#endpoints-gear-btn')).toHaveCount(0);
  await expect(helpModal.locator('.modal-endpoints-gear')).toHaveCount(0);
});
