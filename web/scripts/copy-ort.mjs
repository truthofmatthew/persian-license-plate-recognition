// Serves the onnxruntime-web runtime from our own origin instead of a CDN.
// onnxruntime-web/webgpu loads the "asyncify" build, which runs both the WebGPU and WASM backends.
import { cpSync, mkdirSync } from 'node:fs';

const src = new URL('../node_modules/onnxruntime-web/dist/', import.meta.url);
const dst = new URL('../public/ort/', import.meta.url);
mkdirSync(dst, { recursive: true });
for (const f of ['ort-wasm-simd-threaded.asyncify.mjs', 'ort-wasm-simd-threaded.asyncify.wasm']) cpSync(new URL(f, src), new URL(f, dst));
