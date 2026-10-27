// Writes docs/screenshots/web-*.png with fake residents and the two fixture plates.
import { expect, test, type Page } from '@playwright/test';
import { openApp, readFixture } from './helpers';

const out = (name: string) => new URL(`../../docs/screenshots/${name}`, import.meta.url).pathname;
const go = async (page: Page, tab: string) => {
  await page.locator(`a[href="#${tab}"]`).click();
  await expect(page.locator(`a[href="#${tab}"]`)).toHaveAttribute('aria-current', 'page');
};
const shot = (page: Page, name: string) => page.screenshot({ path: out(name), animations: 'disabled' });

test('screenshots', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 800 });
  await openApp(page, { lang: 'fa', precision: 'fp32' });

  // Resident A through the form, Resident B through CSV import
  await go(page, 'residents');
  await page.locator('.page-head .primary').click();
  const dialog = page.locator('dialog');
  await dialog.locator('input').nth(0).fill('Resident A');
  await dialog.locator('input').nth(1).fill('12');
  await dialog.locator('input').nth(2).fill('Peugeot 206');
  const plate = dialog.locator('.plate-field');
  await plate.nth(0).locator('input').fill('34');
  await plate.nth(1).locator('select').selectOption('D');
  await plate.nth(2).locator('input').fill('319');
  await plate.nth(3).locator('input').fill('66');
  await dialog.locator('button.primary').click();
  await page.getByTestId('csv-input').setInputFiles({
    name: 'residents.csv', mimeType: 'text/csv',
    buffer: Buffer.from('name,unit,car,plate,allowed\r\nResident B,7,Kia Pride,87Y16111,false\r\n'),
  });
  await expect(page.locator('.resident-row')).toHaveCount(2);

  await go(page, 'live');
  await readFixture(page, '87Y16111');
  await page.getByTestId('result').evaluate((el) => el.setAttribute('data-key', ''));
  expect((await readFixture(page, '34D31966')).key).toBe('34D31966');
  await expect(page.getByTestId('status')).toContainText('Resident A');
  await shot(page, 'web-live-desktop.png');

  await page.setViewportSize({ width: 390, height: 844 });
  await shot(page, 'web-live-mobile.png');
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(390);

  await page.setViewportSize({ width: 1280, height: 800 });
  await go(page, 'log');
  await expect(page.locator('.log-row')).toHaveCount(2);
  await shot(page, 'web-log.png');

  await page.locator('.topbar .ghost').click(); // switch to English
  await go(page, 'residents');
  await expect(page.locator('h1')).toHaveText('Residents');
  await shot(page, 'web-residents.png');
  // Extra views for review only (gitignored test output)
  await page.locator('.resident-row button').first().click();
  await page.screenshot({ path: test.info().outputPath('dialog.png') });
  await page.keyboard.press('Escape');
  await go(page, 'settings');
  await page.screenshot({ path: test.info().outputPath('settings.png'), fullPage: true });
  await page.locator('.topbar .ghost').click(); // back to Persian

  await page.emulateMedia({ colorScheme: 'dark' });
  await go(page, 'live');
  await readFixture(page, '87Y16111');
  await shot(page, 'web-dark.png');

  // Phone widths: no page should scroll sideways
  await page.setViewportSize({ width: 375, height: 812 });
  for (const tab of ['live', 'log', 'residents', 'settings']) {
    await go(page, tab);
    expect(await page.evaluate(() => document.documentElement.scrollWidth), tab).toBeLessThanOrEqual(375);
    await page.screenshot({ path: test.info().outputPath(`m-${tab}.png`), fullPage: true });
  }
});
