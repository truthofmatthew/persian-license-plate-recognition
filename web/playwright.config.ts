import { defineConfig } from '@playwright/test';

// Browsers: npx playwright install chromium. Headless Chromium has no WebGPU, so these runs use WASM.
export default defineConfig({
  testDir: 'e2e',
  timeout: 180_000,
  workers: 1,
  use: { baseURL: 'http://localhost:4173/', browserName: 'chromium' },
  webServer: {
    command: 'npm run build && npm run preview -- --port 4173 --strictPort',
    url: 'http://localhost:4173/',
    reuseExistingServer: true,
    timeout: 240_000,
  },
});
