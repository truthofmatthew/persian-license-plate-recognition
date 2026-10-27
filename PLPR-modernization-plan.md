# PLPR 2.0: modernization plan

Repo: `truthofmatthew/persian-license-plate-recognition` (450 stars, 126 forks, GPL-3.0)
Local clone: `/Volumes/Datas/Developments/Personal/persian-license-plate-recognition`
Last code change: PR #17, 2024. Audit date: 2026-10-24.

---

## 1. Where it stands today (audit)

### What it is
A PySide6 desktop app for gated residential parking. Pipeline per frame:

```
camera/RTSP → resize 960×540 → PIL autocontrast
 → YOLOv5 plate detector (plateYolo.pt, 14 MB)
 → crop → YOLOv5 character detector (CharsYolo.pt, 14 MB, sort boxes by x)
 → text → SQLite lookup (residents.db) → allowed / not allowed / unknown
 → log to entries.db + optional POST to an external service
```

Also in the repo: a Streamlit demo, a legacy Keras pipeline (`home-keras.py` + `.h5` models), a YOLOv8 trainer folder for the IRANIS dataset, plate templates (`Templates/*.png`, `.psd`), and `business/` docs that describe API licensing, subscriptions and hardware bundles.

### What works
- The two-stage idea (detect plate, then detect characters) is sound and still competitive for Persian plates.
- Real users: 450 stars, Persian-speaking issue reporters, two outside contributors.
- Domain pieces already exist: Jalali dates, Persian digit/letter mapping, plate input widget, resident and entry management.

### Problems found

| # | Area | Finding | Impact |
|---|------|---------|--------|
| 1 | Bug | `Worker1.prepare_capture` always opens `params.rtps`; the `source = webcam/video` setting in `config.ini` is ignored | Users can't switch sources without editing code |
| 2 | Bug | Plates are only read when detector confidence ≥ 90% (`home-yolo.py`) | Likely cause of issue #22 ("video plays, no plate detected") |
| 3 | Bug | No tracking: every frame with a plate triggers a DB insert, a lookup, a POST and a table refresh | Duplicate entries, load spikes, flicker |
| 4 | Memory (#18, #23) | `torch.hub.load(..., force_reload=True)`, pandas DataFrame per frame, PIL round-trip per frame, TF + Keras + Torch all in one requirements file, no frame skipping | Several GB of RAM, slow start-up |
| 5 | Security | SQL built with f-strings (`db_entries_utils.py:31`, `db_resident_utils.py:105,118,…`), including `ORDER BY {orderBy}` | SQL injection from search boxes or a crafted plate string |
| 6 | Security | Default RTSP credentials (`admin:123456`) committed in `config.ini` | Copy-paste deployments keep weak creds |
| 7 | Coverage (#19, #21) | Only standard white plates. No taxi, police, government, motorcycle, free-zone, diplomatic (English chars) | Biggest product gap users ask for |
| 8 | Stack | YOLOv5 vendored (147 files) and loaded through `torch.hub`; pinned to torch 2.2 / numpy 1.26 / ultralytics 8.1 | Does not install cleanly on Python 3.12+/3.13 or new CUDA; no ONNX path |
| 9 | Platform | Desktop-only (PySide6). Streamlit demo is a toy (no tracking, reloads per frame) | No browser, no mobile, no multi-site |
| 10 | Repo hygiene | ~200 MB of research PDFs (third-party copyright), `__pycache__`, `.idea`, `.DS_Store`, SQLite DBs, demo GIF all in git; two conflicting requirements files; `brighten_image` returns nothing | 475 MB clone, legal exposure from the PDFs |
| 11 | Licensing | YOLOv5 and Ultralytics are **AGPL-3.0**. The repo is GPL-3.0 and `business/` plans paid API and subscriptions | A hosted closed service on Ultralytics code needs either full source release (AGPL network clause) or an Ultralytics Enterprise license |
| 12 | Quality | No tests, no benchmark set, no accuracy numbers anywhere | Can't tell if a change helps or hurts |

---

## 2. Product vision

**"Persian ANPR that runs anywhere: in a browser tab, on a phone, on a $100 edge box, or as an API, with the same models."**

Three ways to use it, one model family and one plate parser:

1. **Web app (new, main surface).** Open a URL, allow the camera, plates are read in the browser. Nothing is uploaded unless the user wants cloud sync. Works offline as a PWA.
2. **Gate / edge agent.** Headless service on a mini-PC, Jetson or Raspberry Pi 5 + Hailo, reading RTSP cameras, opening the barrier, syncing to the dashboard.
3. **API / SDK.** `POST /v1/read` with an image, or a JS/Python package for developers who build their own apps.

### Target users

| Persona | Need | Surface |
|---------|------|---------|
| Building / complex manager (today's user) | Know who came in, let residents in automatically | Web dashboard + edge agent |
| Parking operator | Entry/exit times, billing, multiple gates | Edge agent + dashboard + API |
| Developer / integrator | Drop-in Persian plate reading | npm / PyPI package, REST API |
| Researcher / student (many current stars) | Train and compare models | Trainer, datasets, benchmark |

---

## 3. Goals and success metrics

| Metric | Today | Target for 2.0 |
|--------|-------|----------------|
| Full-plate exact-match accuracy, standard plates (held-out set) | not measured | ≥ 97% |
| Accuracy on special plates (taxi, police, govt, motorcycle, free-zone) | ~0% (not supported) | ≥ 90% |
| Browser speed, mid-range laptop (WebGPU) | n/a | ≥ 15 FPS end-to-end |
| Browser speed, mid-range Android phone | n/a | ≥ 8 FPS |
| Model download for web (both models, quantized) | 28 MB `.pt` | ≤ 8 MB |
| RAM, desktop/edge agent | multiple GB (issues #18, #23) | < 600 MB |
| Duplicate entries per vehicle pass | many | 1 |
| Clean install on Python 3.12/3.13 | fails | `uv sync` works first time |

---

## 4. Technology choices (state of the art, Oct 2026)

### 4.1 Detection model: replace YOLOv5

| Option | Licence | Why consider |
|--------|---------|--------------|
| **Ultralytics YOLO26 (n/s)** | AGPL-3.0 or paid | Newest Ultralytics line; NMS-free end-to-end head, built for edge and export; trainer already uses Ultralytics so migration is one command |
| Ultralytics YOLO11 (n/s) | AGPL-3.0 or paid | Mature, export path well-tested on ONNX/TF.js/CoreML |
| **RF-DETR (nano/small)** | Apache-2.0 | Real-time DETR, NMS-free, strong small-object accuracy, no AGPL constraint |
| D-FINE / DEIM | Apache-2.0 | Similar real-time DETR family, good if RF-DETR export misbehaves |

**Recommendation:** decide the business model first (section 7). If PLPR stays fully open source, use **YOLO26n** (cheapest path, same tooling). If a closed paid API or SDK is planned, use **RF-DETR** (Apache-2.0) so no Ultralytics licence is needed.

Pick the winner by a benchmark run on our own held-out set, not by leaderboard.

### 4.2 Character reading: two-stage stays, OCR head modernized

- **Keep the character detector** as the baseline. Persian plates have a fixed layout (2 digits, letter, 3 digits, 2-digit province code), and per-character boxes handle it well.
- **Add a sequence recognizer** on the cropped plate and compare: a small CTC/attention model such as PARSeq or a plate-specific model in the style of `fast-plate-ocr`. Upside: one pass instead of N boxes, handles two-row motorcycle plates naturally, smaller model.
- **Plate-type classifier head** (white, taxi yellow, police, government red, motorcycle, free-zone, diplomatic) so the parser knows the layout. Solves #19 and #21.
- **Layout-aware parser with validation**: regex on the Persian plate grammar, legal letter set, Unicode normalization (Arabic `ي/ك` → Persian `ی/ک`), Persian↔Latin digits. Rejects impossible reads instead of logging garbage.
- **Multi-frame voting**: track each vehicle (ByteTrack/BoT-SORT), read the plate on several frames, vote per character. This gives the largest accuracy gain for the least work.
- Optional, server-only: a small vision-language model as a second opinion for low-confidence reads during review. Not on the hot path.

### 4.3 Data

- IRANIS character dataset (already used by the trainer) and existing labelled plates.
- **Synthetic plates from `Templates/`.** The repo already has templates for Sepah, service, Tashrifat and others; render random valid plates, warp, blur, add glare/night/rain noise. Cheapest way to cover special plates.
- A **frozen benchmark set** (~2,000 real images across plate types, day/night, angles) that never goes into training. Every model change reports against it in CI.
- Active learning loop: low-confidence reads from consenting sites go to a review queue → labelled → next training round.

### 4.4 Running in the browser

```
getUserMedia / <video> / file upload
   → Web Worker (OffscreenCanvas, requestVideoFrameCallback)
      → ONNX Runtime Web
           WebGPU EP (Chrome, Edge, Safari 26+, Firefox 141+ on Windows)
           WASM SIMD + threads fallback (older browsers)
      → detector → crop → OCR → parser → tracker/vote
   → UI (React or Svelte), RTL, Jalali dates
   → IndexedDB for local log; optional sync to backend
```

- Export: PyTorch → ONNX (opset 17+), FP16 for WebGPU, INT8 for WASM. Cache models with the Cache API / service worker so the second visit loads instantly.
- Input sizes: detector at 640 (or 480 on phones), OCR at a fixed small crop (e.g. 64×256).
- **RTSP cameras cannot play directly in a browser.** Ship a tiny gateway (go2rtc or MediaMTX) that re-streams RTSP as WebRTC. The edge agent bundles it.
- Privacy: in-browser mode never uploads frames. Market this.

### 4.5 Backend and edge agent

- **Python service on FastAPI** with ONNX Runtime (CPU / CUDA / CoreML) and optional TensorRT on Jetson; OpenVINO on Intel mini-PCs; Hailo on Raspberry Pi 5. Same ONNX files as the web.
- **Postgres** (SQLite for single-gate installs) with parameterized queries through SQLAlchemy 2 / SQLModel, Alembic migrations.
- Auth (sites, users, roles), audit log, image retention policy (auto-delete crops after N days).
- Events out: webhooks (replaces the current hard-coded POST), MQTT for barrier controllers, relay/GPIO output for gate opening.
- Packaging: `uv` + `pyproject.toml`, Python 3.12+, one Docker image per target (x86 CPU, CUDA, Jetson, ARM).

### 4.6 What happens to the PySide6 desktop app

Retire it. The web app installed as a PWA covers the desktop case, and the edge agent covers always-on gates. If a native window is still required, wrap the web UI with Tauri. One UI codebase instead of two.

---

## 5. Roadmap

### Phase 0: stabilize the current release (1–2 weeks)
Ship as v1.1 so existing users benefit right away.
- Fix source selection bug (#1), lower and make configurable the 90% threshold (#2), add simple tracking + cooldown so one car = one entry (#3).
- Remove `force_reload=True`, pandas-per-frame, TF/Keras from default deps; add frame skipping. Measure RAM before/after (#18, #23).
- Parameterize every SQL query; whitelist `ORDER BY` columns (#5).
- Move secrets to `.env`, ship a `config.example.ini` without credentials (#6).
- Clean the repo: delete the research PDFs (replace with a links list), `__pycache__`, `.idea`, DB files; move models and demo GIF to GitHub Releases or Hugging Face. Rewrite history with `git filter-repo` only after asking forks/contributors.
- One `pyproject.toml`, Python 3.12, CI that installs and runs a smoke test.

### Phase 1: model and data modernization (4–6 weeks)
- Build the frozen benchmark set and an `eval` script (exact match, CER, per plate type, latency).
- Synthetic plate generator from `Templates/`.
- Retrain detector on YOLO26n and RF-DETR-nano, compare on the benchmark.
- Add plate-type classifier; train sequence OCR, compare with character detector.
- Layout-aware parser + multi-frame voting.
- Export ONNX FP16/INT8; publish models on Hugging Face with model cards.
- Exit criteria: section 3 accuracy targets met in Python.

### Phase 2: web app MVP (4–6 weeks)
- Static site (Vite + React or Svelte, TypeScript), ONNX Runtime Web with WebGPU/WASM, worker pipeline.
- Modes: live camera, upload image, upload video.
- Local resident list and entry log in IndexedDB, CSV import/export, Persian RTL UI, Jalali dates.
- PWA install + offline.
- Public demo on GitHub Pages / Vercel; this is the new README hero.
- Exit criteria: FPS and model size targets met on 3 reference devices.

### Phase 3: platform (6–8 weeks)
- FastAPI backend: sites, gates, users/roles, entries, residents, webhooks, retention.
- Edge agent Docker images + RTSP → WebRTC gateway; barrier relay output.
- Dashboard: live view per gate, search by plate, reports, review queue for low-confidence reads.
- npm package (`@plpr/web`) and PyPI package (`plpr`) exposing `readPlate(image)`.

### Phase 4: growth and monetization (ongoing)
- Hosted API with free tier; paid tiers per `business/` docs.
- Hardware bundle (mini-PC or Pi 5 + Hailo + camera, preinstalled agent).
- Integrations: n8n/Zapier webhooks, Home Assistant, parking billing.
- Community: contributor guide, labelled-data contributions, benchmark leaderboard.

---

## 6. Risks

| Risk | Mitigation |
|------|-----------|
| AGPL obligations from Ultralytics/YOLOv5 clash with paid closed offerings | Decide model licence path before Phase 1 ends (section 7) |
| Personal data: plates + timestamps + owner names | Local-first by default, retention limits, encryption at rest, consent text in UI |
| Rewriting git history breaks 126 forks | Do the cleanup on a new default branch / new major version, keep old history in a tag |
| Low-end phones too slow | 480-px detector, INT8 WASM path, process every Nth frame, show "best effort" mode |
| Special-plate data scarcity | Synthetic generator + targeted real data collection |
| Datas volume is 99% full (2.9 GB free) | Free space or use cloud GPU (Colab/Kaggle/Runpod) for training before Phase 1 |

---

## 7. Decisions needed from the owner

1. **Open source only, or open core + paid API?** This decides YOLO26 (AGPL) vs RF-DETR (Apache-2.0).
2. **Keep the PySide6 desktop app** in 2.0, or retire it in favour of PWA + edge agent?
3. **Repo strategy:** clean up in place (history rewrite, affects forks) or start `plpr` v2 as a new repo/monorepo and archive v1?
4. **Training compute:** local Mac (MPS), or a rented GPU?
5. **Which special plate types first?** Suggested order by demand in issues: motorcycle, taxi, government/police, free-zone/diplomatic.
