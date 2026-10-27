// Model load time and per-frame latency (both models, one plate) on WASM in headless Chromium.
import { expect, test } from '@playwright/test';
import { FIXTURES, openApp, readFixture } from './helpers';

const median = (xs: number[]) => [...xs].sort((a, b) => a - b)[Math.floor(xs.length / 2)];

for (const precision of ['fp32', 'fp16'] as const) {
  test(`bench WASM ${precision}`, async ({ page }) => {
    await openApp(page, { precision });
    const loadMs = Number(await page.getByTestId('backend').getAttribute('data-load-ms'));
    const isolated = await page.evaluate(() => crossOriginIsolated);
    const webgpu = await page.evaluate(async () => !!(await (navigator as any).gpu?.requestAdapter?.()));
    const ms: number[] = [];
    for (let i = 0; i < 6; i++) {
      const key = FIXTURES[i % 2];
      await page.getByTestId('result').evaluate((el) => el.setAttribute('data-key', ''));
      const r = await readFixture(page, key);
      expect(r.key).toBe(key);
      if (i > 0) ms.push(r.ms); // first run includes warm-up
    }
    const line = `WASM ${precision}: load ${loadMs} ms, frame median ${median(ms).toFixed(0)} ms (min ${Math.min(...ms).toFixed(0)}, max ${Math.max(...ms).toFixed(0)}), threads=${isolated}, webgpuAdapter=${webgpu}`;
    console.log(line);
    test.info().annotations.push({ type: 'bench', description: line });
  });
}
