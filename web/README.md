# PLPR web app

Reads Iranian license plates in the browser. Both models run on the device through
[onnxruntime-web](https://onnxruntime.ai/docs/tutorials/web/), the resident list and the entry
log live in IndexedDB, and nothing is uploaded. It installs as a PWA and works offline after the
first visit.

Screens: **Live** (camera, video file, photo or stream URL), **Log** (Jalali time, plate, status,
crop; search, CSV export, clear), **Residents** (add, edit, delete, allowed toggle, CSV
import/export) and **Settings** (thresholds, every-Nth frame, backend, precision, language, theme).
Persian (RTL) is the default; the header button switches to English.

## Run it

```bash
cd web
npm install
npm run models     # copies ../model/onnx/*.onnx and labels.json into public/models/
npm run dev        # http://localhost:5173
```

The models come from `scripts/export_onnx.py` in the repo root. `npm run models` fails with a
clear message if `model/onnx/` is empty.

| Command | What it does |
| --- | --- |
| `npm run build` | Type-checks (strict) and builds the static site into `dist/` |
| `npm run preview` | Serves `dist/` on port 4173 |
| `npm test` | Vitest unit tests: plate grammar, tracker voting, YOLO decode/NMS, CSV |
| `npm run e2e` | Playwright: builds, previews, reads both fixture plates (fp32 and fp16), checks offline reload and clicks through every screen |
| `npm run bench` | Model load time and per-frame latency, fp32 vs fp16 on WASM |
| `npm run screenshots` | Regenerates `docs/screenshots/web-*.png` with fake residents |

Playwright needs Chromium once: `npx playwright install chromium`.

## How it is built

```
web/
  src/lib/         framework-free pipeline, publishable as its own package (index.ts)
    labels.ts      character classes, mirrors plpr/labels.py
    plate.ts       plate grammar and DB keys, mirrors plpr/plate.py
    pipeline.ts    letterbox, YOLOv5 decode, NMS, readPlates, mirrors plpr/engine.py
    tracker.ts     IoU tracker with confidence-weighted votes, mirrors plpr/tracking.py
  src/worker.ts    loads the models and runs inference off the main thread
  src/engine.ts    page-side handle on the worker
  src/db.ts        IndexedDB: residents, log, settings
  src/ui/          React screens
  e2e/             Playwright specs
  scripts/         copy-models, copy-ort, icons
```

`src/lib` takes an `Infer` function per model instead of importing onnxruntime, so it runs with any
runtime that returns the raw `[1, 25200, 5+nc]` YOLOv5 output. Keep it in step with `plpr/`: the
e2e test reads `tests/fixtures/plate_34D31966.jpg` and `plate_87Y16111.jpg` on a 300 px grey border,
the same check as `tests/test_core.py`, and fails if the port drifts.

The tracker matches `plpr/tracking.py` and adds one method, `flush()`, which logs the pending car
when a photo is read, a video ends or the camera stops.

Live processing skips frames on purpose: a frame goes to the worker only when the previous one is
done and it is the Nth frame (Settings). Slow phones read fewer frames instead of falling behind.

## Backends and precision

`Automatic` tries WebGPU first (fp16 models) and falls back to WASM (fp32 models). Both can be
forced in Settings. The onnxruntime WASM files are copied from `node_modules` into `public/ort/`
at build time and served from the same origin, not a CDN.

WASM uses several threads only when the page is cross-origin isolated. `vite dev` and `vite preview`
send the COOP/COEP headers; on a static host that cannot set headers it runs single-threaded and
slower.

Measured in headless Chromium 156 on an Apple Silicon Mac, WASM with 4 threads, one plate per
frame (plate model + character model), served from localhost, 4 runs of 5 frames each on a machine
that was busy with other work:

| Models | Load (download + session) | Per frame, median per run |
| --- | --- | --- |
| fp32 | 2.3 to 3.2 s | 363 to 445 ms |
| fp16 | 1.5 to 2.9 s | 357 to 425 ms (one outlier run: 853 ms) |

On WASM, fp16 is about as fast as fp32 and loads faster because the files are half the size. WASM
still defaults to fp32 as the conservative choice; both precisions read the test plates correctly,
so pick fp16 in Settings on slow connections. Headless Chromium has no WebGPU adapter, so WebGPU
was not measured; test it in a desktop browser with Settings > Backend > WebGPU.

## Browser support

- WebGPU: Chrome and Edge 113+, Safari 26+, Firefox 141+ on Windows.
- Everything else falls back to WASM, which works in all current browsers.
- Camera access needs HTTPS (or localhost). Phones use the rear camera when there is one.

## Deploy as a static site

`npm run build` produces a plain static site in `dist/` with relative paths, so it works from a
sub-path such as GitHub Pages. Upload `dist/` anywhere that serves files. For WASM threads, add
these headers if your host allows it:

```
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Embedder-Policy: require-corp
```

## Hosting the models elsewhere

The models are about 56 MB (fp32) and 28 MB (fp16), so you may not want them in the site itself.
Point the app at another base URL at build time:

```bash
VITE_MODEL_BASE=https://huggingface.co/<user>/<repo>/resolve/main/ npm run build
```

The base must serve `plate.onnx`, `chars.onnx`, `plate.fp16.onnx`, `chars.fp16.onnx` with CORS
headers (GitHub Release assets and Hugging Face both do). Then you can delete `dist/models/`.
Models are cached in the `plpr-models` Cache Storage bucket on first load (a CacheFirst service
worker rule covers later visits), so a second visit works offline.

## Camera streams and RTSP

Browsers cannot open `rtsp://` URLs. Use the edge agent's go2rtc instead: the **Stream URL** source
plays any address a `<video>` element can play, such as go2rtc's HLS
(`http://<edge>:1984/api/stream.m3u8?src=<camera>`) or MP4 (`/api/stream.mp4?src=<camera>`)
endpoints. HLS plays natively in Safari and on Android; if your browser cannot play it, use the MP4
endpoint. The stream must send CORS headers (`api: origin: "*"` in go2rtc), otherwise the
browser blocks reading the frames.
