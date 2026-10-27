/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

// Cross-origin isolation lets onnxruntime-web use WASM threads. Static hosts that cannot set
// these headers still work, single-threaded.
const isolation = { 'Cross-Origin-Opener-Policy': 'same-origin', 'Cross-Origin-Embedder-Policy': 'require-corp' };

export default defineConfig({
  base: './',
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['fonts/vazir.ttf', 'icons/*'],
      manifest: {
        name: 'PLPR',
        short_name: 'PLPR',
        description: 'Reads Iranian license plates on this device. Nothing is uploaded.',
        lang: 'fa',
        dir: 'rtl',
        display: 'standalone',
        start_url: './',
        theme_color: '#1d4fb8',
        background_color: '#f3f4f1',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icons/icon.svg', sizes: 'any', type: 'image/svg+xml' },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ttf,mjs,wasm}'],
        maximumFileSizeToCacheInBytes: 40 * 1024 * 1024, // the ORT wasm is ~29 MB
        runtimeCaching: [
          {
            // Models may live on another host (VITE_MODEL_BASE), so match by file name, not origin.
            urlPattern: ({ url }) => /\/(plate|chars)(\.fp16)?\.onnx$|\/labels\.json$/.test(url.pathname),
            handler: 'CacheFirst',
            options: { cacheName: 'plpr-models', cacheableResponse: { statuses: [0, 200] }, rangeRequests: false },
          },
        ],
      },
    }),
  ],
  resolve: {
    // Load the ORT glue (.mjs) from /ort/ at runtime instead of inlining it into the bundle.
    conditions: ['onnxruntime-web-use-extern-wasm', 'module', 'browser', 'development|production'],
  },
  optimizeDeps: { exclude: ['onnxruntime-web'] },
  worker: { format: 'es' },
  server: { headers: isolation },
  preview: { headers: isolation },
  build: { target: 'es2022', chunkSizeWarningLimit: 1000 },
  test: { include: ['src/**/*.test.ts'] },
});
