// Click-through of the controls the read test does not cover.
import { expect, test } from '@playwright/test';
import { openApp, readFixture } from './helpers';

test.use({ launchOptions: { args: ['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'] } });

test('camera, log, residents and settings controls work', async ({ page }) => {
  page.on('dialog', (d) => void d.accept());
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  await openApp(page, { precision: 'fp32' });

  // Camera: Chromium's fake device has no plate, so frames are read and nothing is found
  await page.getByRole('button', { name: 'Start camera' }).click();
  await expect(page.getByTestId('latency')).not.toHaveAttribute('data-ms', '0.0', { timeout: 30_000 });
  await expect(page.getByTestId('result')).toContainText('No plate in view');
  await page.getByRole('button', { name: 'Stop' }).click();
  await expect(page.getByRole('button', { name: 'Start camera' })).toBeVisible();

  await readFixture(page, '34D31966');
  await page.getByTestId('result').evaluate((el) => el.setAttribute('data-key', ''));
  await readFixture(page, '87Y16111');

  // Log: search, export, clear
  await page.getByRole('link', { name: 'Log' }).click();
  await page.getByPlaceholder('Search plate or name').fill('87Y');
  await expect(page.locator('.log-row')).toHaveCount(1);
  await page.getByPlaceholder('Search plate or name').fill('zzz');
  await expect(page.getByText('Nothing matches this search.')).toBeVisible();
  const dl = page.waitForEvent('download');
  await page.getByRole('button', { name: 'Export CSV' }).click();
  expect((await dl).suggestedFilename()).toMatch(/^plpr-log-.*\.csv$/);
  await page.getByRole('button', { name: 'Clear log' }).click();
  await expect(page.getByText(/No plates logged yet/)).toBeVisible();

  // Residents: invalid CSV, add via keyboard, toggle, delete
  await page.getByRole('link', { name: 'Residents' }).click();
  await page.getByTestId('csv-input').setInputFiles({ name: 'x.csv', mimeType: 'text/csv', buffer: Buffer.from('name,plate\nX,nope\n') });
  await expect(page.getByText('This file has no rows with a valid plate.')).toBeVisible();
  await page.getByRole('button', { name: 'Add resident' }).click();
  await page.keyboard.press('Escape');
  await expect(page.locator('dialog')).not.toBeVisible();
  await page.getByRole('button', { name: 'Add resident' }).click();
  await page.keyboard.type('Resident A');
  for (const v of ['', '', '12', 'D', '345', '67']) { await page.keyboard.press('Tab'); if (v && v !== 'D') await page.keyboard.type(v); }
  await page.getByRole('button', { name: 'Save resident' }).click();
  await expect(page.locator('.resident-row')).toHaveCount(1);
  await expect(page.locator('.resident-row [data-key]')).toHaveAttribute('data-key', '12B34567');
  await page.locator('.resident-row input[type=checkbox]').click();
  await expect(page.locator('.resident-row .switch')).toContainText('Not allowed');
  await page.getByRole('button', { name: 'Delete' }).click();
  await expect(page.locator('.resident-row')).toHaveCount(0);

  // Settings: theme applies, focus ring is visible on keyboard focus
  await page.getByRole('link', { name: 'Settings' }).click();
  await page.getByLabel('Theme').selectOption('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'dark');
  await page.getByLabel('Theme').focus();
  await page.keyboard.press('Shift+Tab');
  const outline = await page.evaluate(() => getComputedStyle(document.activeElement!).outlineStyle);
  expect(outline).toBe('solid');

  expect(errors).toEqual([]);
});
