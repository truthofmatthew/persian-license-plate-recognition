// Proves the TypeScript port reads the same plates as the Python engine (tests/test_core.py).
import { expect, test } from '@playwright/test';
import { FIXTURES, openApp, readFixture } from './helpers';

for (const precision of ['fp32', 'fp16'] as const) {
  test(`reads both fixture plates on WASM ${precision}`, async ({ page }) => {
    await openApp(page, { precision });
    await expect(page.getByTestId('backend')).toHaveText(`WASM · ${precision}`);
    for (const key of FIXTURES) {
      await page.getByTestId('result').evaluate((el) => el.setAttribute('data-key', ''));
      expect((await readFixture(page, key)).key).toBe(key);
    }
    // Each still image is logged once
    await page.getByRole('link', { name: 'Log' }).click();
    await expect(page.locator('.log-row')).toHaveCount(2);
  });
}

test('second visit works offline', async ({ page, context }) => {
  await openApp(page, { precision: 'fp32' });
  await page.evaluate(async () => { await navigator.serviceWorker.ready; });
  await context.setOffline(true);
  await page.reload();
  await expect(page.getByTestId('backend')).toHaveAttribute('data-load-ms', /\d+/, { timeout: 60_000 });
  expect((await readFixture(page, '87Y16111')).key).toBe('87Y16111');
});
