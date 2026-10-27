// Runs both models off the main thread. Messages: init -> ready|error, run -> result|error.
import * as ort from 'onnxruntime-web/webgpu';
import { readPlates, type Infer, type PlateRead } from './lib';

export type Backend = 'webgpu' | 'wasm';
export type Precision = 'fp32' | 'fp16';
export interface InitMsg { type: 'init'; backend: 'auto' | Backend; precision: 'auto' | Precision; modelBase: string; ortBase: string }
export interface RunMsg { type: 'run'; id: number; frame: ImageBitmap; plateConf: number; charConf: number }
export interface ReadOut extends PlateRead { crop: ImageBitmap }
export type OutMsg =
  | { type: 'ready'; backend: Backend; precision: Precision; loadMs: number }
  | { type: 'result'; id: number; reads: ReadOut[]; ms: number; width: number; height: number }
  | { type: 'error'; id?: number; message: string };

let plate: Infer | null = null;
let chars: Infer | null = null;

const post = (m: OutMsg, transfer: Transferable[] = []) => (self as unknown as Worker).postMessage(m, transfer);

// Same cache the service worker's CacheFirst rule uses. Filling it here covers the first visit,
// when the service worker does not control the page yet and would not see these requests.
async function load(url: string): Promise<ArrayBuffer> {
  const cache = 'caches' in self ? await caches.open('plpr-models').catch(() => null) : null;
  let res = await cache?.match(url);
  if (!res) {
    res = await fetch(url);
    if (!res.ok) throw new Error(`${url}: HTTP ${res.status}`);
    await cache?.put(url, res.clone()).catch(() => undefined); // quota errors only cost offline use
  }
  return res.arrayBuffer();
}

function wrap(sess: ort.InferenceSession): Infer {
  return async (input, size) => {
    const out = await sess.run({ images: new ort.Tensor('float32', input, [1, 3, size, size]) });
    const t = out.output;
    const data = (await t.getData()) as Float32Array;
    t.dispose();
    return { data, dims: t.dims };
  };
}

async function hasWebGpu(): Promise<boolean> {
  const gpu = (navigator as Navigator & { gpu?: { requestAdapter(): Promise<unknown> } }).gpu;
  try { return !!gpu && !!(await gpu.requestAdapter()); } catch { return false; }
}

async function init(m: InitMsg) {
  const t0 = performance.now();
  ort.env.wasm.wasmPaths = m.ortBase;
  // Threads need cross-origin isolation (COOP/COEP headers); without it ORT runs single-threaded.
  ort.env.wasm.numThreads = self.crossOriginIsolated ? Math.min(4, navigator.hardwareConcurrency || 1) : 1;
  const order: Backend[] = m.backend === 'auto' ? ((await hasWebGpu()) ? ['webgpu', 'wasm'] : ['wasm']) : [m.backend];
  let lastErr: unknown;
  for (const backend of order) {
    // fp16 halves the download and suits GPUs; on WASM it measured about as fast, fp32 stays the conservative default.
    const precision: Precision = m.precision === 'auto' ? (backend === 'webgpu' ? 'fp16' : 'fp32') : m.precision;
    const suffix = precision === 'fp16' ? '.fp16.onnx' : '.onnx';
    try {
      const [p, c] = await Promise.all([load(`${m.modelBase}plate${suffix}`), load(`${m.modelBase}chars${suffix}`)]);
      const opts: ort.InferenceSession.SessionOptions = { executionProviders: [backend], graphOptimizationLevel: 'all' };
      plate = wrap(await ort.InferenceSession.create(p, opts));
      chars = wrap(await ort.InferenceSession.create(c, opts));
      post({ type: 'ready', backend, precision, loadMs: Math.round(performance.now() - t0) });
      return;
    } catch (e) {
      lastErr = e;
    }
  }
  throw lastErr;
}

async function runFrame(m: RunMsg) {
  if (!plate || !chars) throw new Error('models not loaded');
  const t0 = performance.now();
  const { frame } = m;
  const reads = await readPlates(plate, chars, { image: frame, width: frame.width, height: frame.height }, { plateConf: m.plateConf, charConf: m.charConf });
  const ms = performance.now() - t0;
  const out: ReadOut[] = await Promise.all(reads.map(async (r) => ({ ...r, crop: await createImageBitmap(frame, r.box[0], r.box[1], r.box[2] - r.box[0], r.box[3] - r.box[1]) })));
  const { width, height } = frame;
  frame.close();
  post({ type: 'result', id: m.id, reads: out, ms, width, height }, out.map((r) => r.crop));
}

self.onmessage = (e: MessageEvent<InitMsg | RunMsg>) => {
  const m = e.data;
  (m.type === 'init' ? init(m) : runFrame(m)).catch((err: unknown) =>
    post({ type: 'error', id: m.type === 'run' ? m.id : undefined, message: err instanceof Error ? err.message : String(err) }),
  );
};
