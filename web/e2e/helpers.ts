import { expect, type Page } from '@playwright/test';
import { readFileSync } from 'node:fs';

export const FIXTURES = ['34D31966', '87Y16111'] as const;
const fixture = (key: string) => readFileSync(new URL(`../../tests/fixtures/plate_${key}.jpg`, import.meta.url)).toString('base64');

/** Open the app in English with the given engine settings, wait for models. */
export async function openApp(page: Page, settings: Record<string, unknown> = {}) {
  await page.goto('./');
  await page.evaluate(async (s) => {
    const db = await new Promise<IDBDatabase>((res, rej) => {
      const r = indexedDB.open('plpr', 1);
      r.onupgradeneeded = () => {
        r.result.createObjectStore('residents', { keyPath: 'id', autoIncrement: true }).createIndex('plate', 'plate');
        r.result.createObjectStore('log', { keyPath: 'id', autoIncrement: true });
        r.result.createObjectStore('kv');
      };
      r.onsuccess = () => res(r.result);
      r.onerror = () => rej(r.error);
    });
    await new Promise((res) => {
      const tx = db.transaction('kv', 'readwrite');
      tx.objectStore('kv').put({ lang: 'en', backend: 'wasm', ...s }, 'settings');
      tx.oncomplete = res;
    });
    db.close();
  }, settings);
  await page.reload();
  await expect(page.getByTestId('backend')).toHaveAttribute('data-load-ms', /\d+/, { timeout: 120_000 });
}

/** Upload a fixture plate on a 300px grey border (as tests/test_core.py does) and wait for the read. */
export async function readFixture(page: Page, key: string) {
  await page.getByTestId('mode-image').click();
  await page.evaluate(async ({ b64, name }) => {
    const img = await createImageBitmap(await (await fetch(`data:image/jpeg;base64,${b64}`)).blob());
    const c = new OffscreenCanvas(img.width + 600, img.height + 600);
    const ctx = c.getContext('2d')!;
    ctx.fillStyle = 'rgb(90,90,90)';
    ctx.fillRect(0, 0, c.width, c.height);
    ctx.drawImage(img, 300, 300);
    const file = new File([await c.convertToBlob({ type: 'image/png' })], `${name}.png`, { type: 'image/png' });
    const input = document.querySelector<HTMLInputElement>('[data-testid=file-input]')!;
    const dt = new DataTransfer();
    dt.items.add(file);
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }, { b64: fixture(key), name: key });
  await expect(page.getByTestId('result')).toHaveAttribute('data-key', /.+/, { timeout: 60_000 });
  return {
    key: await page.getByTestId('result').getAttribute('data-key'),
    ms: Number(await page.getByTestId('latency').getAttribute('data-ms')),
  };
}
