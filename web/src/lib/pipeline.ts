// Two-stage pipeline: plate detector -> character detector. Mirrors plpr/engine.py.
// Runtime-agnostic: pass in an `Infer` per model (onnxruntime-web, or anything else).
import { CHAR_CLASSES } from './labels';
import { parseCodes, plateKey, type PlateNumber } from './plate';

export type Box = [number, number, number, number]; // x1, y1, x2, y2 in source pixels
/** Runs a YOLOv5 model on a [1,3,size,size] RGB tensor in 0..1 and returns the raw [1,N,5+nc] output. */
export type Infer = (input: Float32Array, size: number) => Promise<{ data: Float32Array; dims: readonly number[] }>;
/** Anything drawImage accepts, with its pixel size. */
export interface Source { image: CanvasImageSource; width: number; height: number }

export interface Det { box: Box; score: number; cls: number }
export interface PlateRead {
  box: Box;
  plateConf: number;
  codes: string[];
  charConfs: number[];
  plate: PlateNumber | null;
}

export const readText = (r: PlateRead): string => (r.plate ? plateKey(r.plate) : r.codes.join(''));
export const readCharConf = (r: PlateRead): number => (r.charConfs.length ? r.charConfs.reduce((a, b) => a + b, 0) / r.charConfs.length : 0);

let canvas: OffscreenCanvas | null = null;

/** Resize keeping aspect ratio, pad with 114 grey (YOLOv5 convention), return CHW float32 RGB / 255. */
export function letterbox(src: Source, sx: number, sy: number, sw: number, sh: number, size: number) {
  const r = Math.min(size / sh, size / sw);
  const nh = Math.round(sh * r), nw = Math.round(sw * r);
  const top = Math.floor((size - nh) / 2), left = Math.floor((size - nw) / 2);
  if (!canvas || canvas.width !== size) canvas = new OffscreenCanvas(size, size);
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!;
  ctx.fillStyle = 'rgb(114,114,114)';
  ctx.fillRect(0, 0, size, size);
  ctx.drawImage(src.image, sx, sy, sw, sh, left, top, nw, nh);
  const px = ctx.getImageData(0, 0, size, size).data;
  const n = size * size;
  const out = new Float32Array(3 * n);
  for (let i = 0; i < n; i++) {
    out[i] = px[i * 4] / 255;
    out[n + i] = px[i * 4 + 1] / 255;
    out[2 * n + i] = px[i * 4 + 2] / 255;
  }
  return { tensor: out, r, dx: left, dy: top };
}

const boxIou = (a: Box, b: Box) => {
  const ix = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0]));
  const iy = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const inter = ix * iy;
  const union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter;
  return union > 0 ? inter / union : 0;
};

/** YOLOv5 raw output (N rows of 5+nc) -> detections after class-agnostic NMS, like cv2.dnn.NMSBoxes. */
export function decode(data: Float32Array, rows: number, stride: number, conf: number, iouThr: number): Det[] {
  const cands: Det[] = [];
  for (let i = 0, o = 0; i < rows; i++, o += stride) {
    const obj = data[o + 4];
    if (obj <= conf) continue; // class scores are <= 1, so obj*cls cannot pass either
    let cls = 0, best = -Infinity;
    for (let c = 5; c < stride; c++) if (data[o + c] > best) { best = data[o + c]; cls = c - 5; }
    const score = best * obj;
    if (score <= conf) continue;
    const cx = data[o], cy = data[o + 1], w = data[o + 2], h = data[o + 3];
    cands.push({ box: [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], score, cls });
  }
  cands.sort((a, b) => b.score - a.score);
  const keep: Det[] = [];
  for (const d of cands) if (keep.every((k) => boxIou(k.box, d.box) <= iouThr)) keep.push(d);
  return keep;
}

async function run(infer: Infer, src: Source, sx: number, sy: number, sw: number, sh: number, conf: number, iouThr: number, size: number): Promise<Det[]> {
  const { tensor, r, dx, dy } = letterbox(src, sx, sy, sw, sh, size);
  const out = await infer(tensor, size);
  const stride = out.dims[out.dims.length - 1];
  const clip = (v: number, hi: number) => Math.min(Math.max(v, 0), hi);
  return decode(out.data, out.data.length / stride, stride, conf, iouThr).map((d) => ({
    ...d,
    box: [clip((d.box[0] - dx) / r, sw), clip((d.box[1] - dy) / r, sh), clip((d.box[2] - dx) / r, sw), clip((d.box[3] - dy) / r, sh)],
  }));
}

export interface ReadOptions { plateConf?: number; charConf?: number; size?: number }

/** Character codes left to right for one plate region of the source. */
export async function readChars(chars: Infer, src: Source, sx: number, sy: number, sw: number, sh: number, conf = 0.5, size = 640) {
  let det = await run(chars, src, sx, sy, sw, sh, conf, 0.3, size);
  if (det.length > 8) det = [...det].sort((a, b) => b.score - a.score).slice(0, 8); // keep the 8 most confident
  det.sort((a, b) => a.box[0] - b.box[0]);
  return { codes: det.map((d) => CHAR_CLASSES[d.cls][0]), confs: det.map((d) => d.score) };
}

/** Every plate in the source, each with its characters read. */
export async function readPlates(plate: Infer, chars: Infer, src: Source, opts: ReadOptions = {}): Promise<PlateRead[]> {
  const { plateConf = 0.5, charConf = 0.5, size = 640 } = opts;
  const reads: PlateRead[] = [];
  for (const d of await run(plate, src, 0, 0, src.width, src.height, plateConf, 0.45, size)) {
    const [x1, y1, x2, y2] = d.box.map(Math.trunc) as Box;
    if (x2 - x1 < 8 || y2 - y1 < 4) continue;
    const { codes, confs } = await readChars(chars, src, x1, y1, x2 - x1, y2 - y1, charConf, size);
    reads.push({ box: [x1, y1, x2, y2], plateConf: d.score, codes, charConfs: confs, plate: parseCodes(codes) });
  }
  return reads;
}
