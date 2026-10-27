# Persian License Plate Recognition (PLPR)

Read Iranian license plates from a camera, a video or a photo, and decide whether the car may enter.
Version 2 runs the same models in four places: a browser tab, the original desktop app, an API server, and an edge agent next to the gate camera.

| Web app (desktop) | Web app (phone) |
|---|---|
| ![Web app reading plate 34D31966 and matching Resident A as allowed](docs/screenshots/web-live-desktop.png) | ![Web app on a 390 px wide phone screen](docs/screenshots/web-live-mobile.png) |

| Dark theme | Desktop app (PySide6) |
|---|---|
| ![Web app in dark theme, plate 87Y16111 marked not allowed](docs/screenshots/web-dark.png) | ![Desktop app with the plate boxed, owner and status, and the entries table](docs/screenshots/desktop.png) |

More: [entry log](docs/screenshots/web-log.png), [residents](docs/screenshots/web-residents.png), [API docs](docs/screenshots/api-docs.png).
All screenshots use made-up residents.

## What's in the box

| Part | Folder | What it does |
|---|---|---|
| Core library | `plpr/` | ONNX Runtime engine (no PyTorch), Persian plate grammar, tracker that votes across frames so one car gives one entry |
| Web app | `web/` | Runs the models in the browser with WebGPU or WebAssembly. Camera, video, photo or stream URL. Residents and log stay in the browser (IndexedDB). Installable, works offline. Persian (RTL) and English |
| Desktop app | `home-yolo.py` | The v1 PySide6 app, now on the new engine |
| API server | `server/` | FastAPI: read endpoint, residents, entries, review queue, signed webhooks, API keys with roles, data retention |
| Edge agent | `server/agent.py` | Reads an RTSP camera, webcam or video, posts one event per car, buffers while offline, can call a barrier relay |
| Docker | `docker/` | API + agent + go2rtc (RTSP to WebRTC/HLS for browsers) + optional Postgres |
| Training and evaluation | `scripts/`, `trainer/` | ONNX export, synthetic plate generator, benchmark, INT8 quantization, training on newer YOLO models |

## Quick start

All Python parts share one package. Python 3.10+ and [uv](https://docs.astral.sh/uv/) (or pip):

```bash
git clone https://github.com/truthofmatthew/persian-license-plate-recognition.git
cd persian-license-plate-recognition
uv venv && uv pip install -e ".[train]"
```

Export the ONNX models. This is the only step that needs PyTorch:

```bash
uv run python scripts/export_onnx.py
```

It writes `model/onnx/plate.onnx`, `chars.onnx`, their `.fp16.onnx` versions and `labels.json`.

### Web app

```bash
cd web
npm install
npm run models
npm run dev
```

Open the printed URL and allow the camera, or upload a photo. Nothing is uploaded anywhere. See [web/README.md](web/README.md) for deploying it as a static site and hosting the models elsewhere.

### Desktop app

```bash
uv pip install -e ".[desktop]"
cp config.example.ini config.ini
uv run python home-yolo.py
```

In `config.ini`, set `source` to `webcam`, `video` or `rtsp` and fill in the matching value. Put camera passwords only in your local `config.ini`, which git ignores. The `[DETECTION]` section sets the thresholds and how many frames to skip.

### API server and edge agent

```bash
uv pip install -e ".[server]"
PLPR_ADMIN_TOKEN=change-me uv run uvicorn server.app:app
uv run python -m server.agent --source rtsp://user:pass@camera/stream --gate-id 1 --server http://127.0.0.1:8000 --token <gate token>
```

Docker, environment variables, roles, webhook signatures and importing v1 databases are covered in [server/README.md](server/README.md).

### In your own code

```python
import cv2
from plpr import Engine, PlateTracker

engine = Engine()                      # or Engine(variant="fp16" | "int8")
for read in engine.read(cv2.imread("car.jpg")):
    print(read.text, read.plate and read.plate.persian, round(read.char_conf, 2))
```

## How it works

```
frame ─► plate detector (YOLOv5s, ONNX) ─► crop ─► character detector (43 classes)
      ─► sort left to right ─► grammar check: 2 digits, letter, 3 digits, 2-digit region
      ─► tracker: match boxes between frames, vote per character
      ─► one result per car, e.g. 34D31966 / ۳۴ د ۳۱۹ - ایران ۶۶
      ─► resident lookup ─► allowed / not allowed / unknown
```

`web/src/lib/` is a TypeScript port of `plpr/`. Both read the same test plates the same way, and the browser tests check this.

## Accuracy and speed today

These are the original v1 models, only converted. Details and how to reproduce them: [docs/benchmark.md](docs/benchmark.md).

| | Size (both models) | Real test plates | Synthetic set (700 images) |
|---|---|---|---|
| FP32 | 56.8 MB | 2/2 | 28.7% exact |
| FP16 | 28.5 MB | 2/2 | 28.6% exact |
| INT8 | 15.7 MB | 2/2 | 28.3% exact |

- The synthetic set is deliberately hard: blur, glare, night, tilted plates, and all special plate types. The old model has never seen most of these.
- Special plates (taxi, police, government, diplomatic, motorcycle) read poorly until the model is retrained. The tools for that are in place; see [docs/training.md](docs/training.md).
- Only two real labelled plates ship with the repo. A larger real test set is the most useful contribution right now.
- Desktop app on a 200-frame clip: peak memory went from 1067 MB to about 520 MB, and processing from 70.7 s to 6.9 s.
- Browser, WebAssembly, Apple Silicon: about 350–450 ms per frame. WebGPU should be much faster, but headless Chrome couldn't measure it.

## What changed in v2

- **Bug fixes:**
  - The `source` setting is respected.
  - The 90% confidence cutoff, which silently dropped most real plates (issue #22), is gone.
  - Each car is logged once instead of on every frame.
  - The old Qt startup warning is fixed (#20).
- **Memory and speed (#18, #23):** no more `torch.hub` at runtime, no pandas per frame, frames are skipped, and the preview no longer leaks a pixmap per frame.
- **Security:**
  - All SQL uses parameters, and sort columns are whitelisted.
  - Default camera credentials are no longer committed.
  - API tokens are stored only as hashes, and webhooks are signed with HMAC.
- **Repo cleanup:**
  - The research PDFs are removed and listed with links in [docs/research.md](docs/research.md).
  - Caches, IDE files, local databases and plate crops are no longer in git.
  - One `pyproject.toml` replaces two conflicting requirements files.
- **New:** the web app, API server, edge agent, Docker setup, synthetic data, benchmark, INT8 models, plate-type colour classifier (`plpr/plate_type.py`), training on YOLO11/YOLO26, and CI.

The full plan is in [PLPR-modernization-plan.md](PLPR-modernization-plan.md).

### Not done yet

- Retraining on real and synthetic data. Only a two-epoch smoke run was done, to prove the pipeline works.
- A sequence OCR model to compare against the character detector, and a comparison with an Apache-2.0 detector (RF-DETR).
- Running the Docker images (they weren't built here) and testing on a real camera, a phone or WebGPU.
- Hosted API and hardware bundle (business work, outside this repo).

## Tests

```bash
uv pip install -e ".[server,desktop,dev]"
QT_QPA_PLATFORM=offscreen uv run pytest -q
cd web && npm test && npm run e2e                     # unit + browser tests
```

## Licence notes

The code is GPL-3.0 (see [LICENSE](LICENSE)).

- **Ultralytics:** YOLOv5 (vendored in `yolov5/`) and the Ultralytics package used for training are AGPL-3.0.
- **Runtime parts:** the web app, server and agent only load ONNX files and don't import Ultralytics code.
- **Closed-source service:** if you plan one, check the licence of the trained weights and either train with an Apache-2.0 detector or buy an Ultralytics licence.

## Credits

- **Libraries:** YOLOv5 and Ultralytics, PyTorch, ONNX Runtime (Python and Web), OpenCV, PySide6, FastAPI, SQLModel, React, Vite, go2rtc, and the Vazir font.
- **Datasets:** [IR-LPR](https://github.com/mut-deep/IR-LPR), [Iranis-dataset](https://github.com/alitourani/Iranis-dataset) and [ILPR](https://github.com/amirmgh1375/iranian-license-plate-recognition).
- **Learning resources:** [Mahdi Rahmani](https://github.com/MahdiRahmani) and [Meftun AKARSU](https://github.com/mftnakrsu), whose repositories this project learned from.
- **Contributors:** everyone who opened issues and sent pull requests to v1.
