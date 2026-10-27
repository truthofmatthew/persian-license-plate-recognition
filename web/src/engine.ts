// Page-side handle on the inference worker.
import type { Backend, InitMsg, OutMsg, Precision, ReadOut } from './worker';
import type { Settings } from './db';

export type EngineState =
  | { status: 'loading' }
  | { status: 'ready'; backend: Backend; precision: Precision; loadMs: number }
  | { status: 'error'; message: string };
export interface FrameResult { reads: ReadOut[]; ms: number; width: number; height: number }

const abs = (path: string) => new URL(path, location.href).href; // the worker resolves relative URLs against its own script
const MODEL_BASE = abs(import.meta.env.VITE_MODEL_BASE || `${import.meta.env.BASE_URL}models/`);
const ORT_BASE = abs(`${import.meta.env.BASE_URL}ort/`);

export class Engine {
  private worker: Worker;
  private next = 1;
  private pending = new Map<number, { resolve: (r: FrameResult) => void; reject: (e: Error) => void }>();

  constructor(settings: Pick<Settings, 'backend' | 'precision'>, onState: (s: EngineState) => void) {
    this.worker = new Worker(new URL('./worker.ts', import.meta.url), { type: 'module' });
    this.worker.onmessage = (e: MessageEvent<OutMsg>) => {
      const m = e.data;
      if (m.type === 'ready') onState({ status: 'ready', backend: m.backend, precision: m.precision, loadMs: m.loadMs });
      else if (m.type === 'result') this.settle(m.id)?.resolve(m);
      else if (m.id !== undefined) this.settle(m.id)?.reject(new Error(m.message));
      else onState({ status: 'error', message: m.message });
    };
    onState({ status: 'loading' });
    const init: InitMsg = { type: 'init', backend: settings.backend, precision: settings.precision, modelBase: MODEL_BASE, ortBase: ORT_BASE };
    this.worker.postMessage(init);
  }

  private settle(id: number) {
    const p = this.pending.get(id);
    this.pending.delete(id);
    return p;
  }

  /** Takes ownership of `frame` (it is transferred to the worker). */
  run(frame: ImageBitmap, plateConf: number, charConf: number): Promise<FrameResult> {
    const id = this.next++;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.worker.postMessage({ type: 'run', id, frame, plateConf, charConf }, [frame]);
    });
  }

  dispose() {
    this.worker.terminate();
    this.pending.forEach((p) => p.reject(new Error('engine stopped')));
  }
}
