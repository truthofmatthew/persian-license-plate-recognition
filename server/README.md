# PLPR server and edge agent

Two programs share this package:

- **API server** (`server/app.py`, FastAPI): reads plates from uploaded images, stores gate entries, decides allowed/denied/unknown from the resident list, fires signed webhooks, purges old data.
- **Edge agent** (`server/agent.py`): runs next to a camera, reads frames with OpenCV, runs `plpr.Engine` + `PlateTracker` and posts one event per vehicle to the server. It keeps events on disk while the server is down.

Both use the ONNX models in `model/onnx/` (create them with `python scripts/export_onnx.py`, or use the Docker image, which exports them at build time).

## Setup

```bash
uv pip install -e ".[server]"
python scripts/export_onnx.py            # once; needs the "train" extra
export PLPR_ADMIN_TOKEN=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Interactive docs: `http://localhost:8000/docs`.

## Environment variables

| Variable | Default | Meaning |
|---|---|---|
| `PLPR_DATABASE_URL` | `sqlite:///./data/plpr.db` | Any SQLAlchemy URL. Postgres: `postgresql+psycopg://user:pass@host/plpr` (needs `psycopg[binary]`) |
| `PLPR_DATA_DIR` | `./data` | Plate crops are stored in `<data_dir>/crops` |
| `PLPR_MODEL_DIR` | `model/onnx` in the repo | ONNX model folder |
| `PLPR_RETENTION_DAYS` | `90` | Entries and crops older than this are deleted hourly. `0` keeps everything |
| `PLPR_ADMIN_TOKEN` | unset | Bootstrap admin key, created at startup if it doesn't exist yet |
| `PLPR_MAX_UPLOAD_MB` | `8` | Upload size cap for images and CSV files |
| `PLPR_PLATE_CONF`, `PLPR_CHAR_CONF` | `0.5` | Detector thresholds for `/v1/read` |
| `PLPR_REVIEW_AGREEMENT`, `PLPR_REVIEW_CONF` | `0.8`, `0.6` | Entries below either value show up in the review queue |
| `PLPR_CORS_ORIGINS` | `[]` | JSON list of origins allowed to call the API from a browser |

A `.env` file in the working directory is read too.

## Auth model

Every endpoint except `/healthz` needs `Authorization: Bearer <token>`. Tokens are random 256-bit strings; the database keeps only their SHA-256 hash, so a token is shown once, when it is created.

| Role | Can do |
|---|---|
| `admin` | everything: sites, gates, residents, keys, webhooks, reviewing entries |
| `gate` | `POST /v1/gates/{id}/events` and `POST /v1/read`. A gate key created with a `gate_id` can only post to that gate |
| `viewer` | read-only: list/get everything except keys and webhooks, export CSV, `POST /v1/read` |

`/v1/read` requires a key (viewer or gate) instead of being public, so no anonymous client can burn CPU on inference; there is no separate rate limiter.

Create the other keys with the bootstrap admin token:

```bash
curl -X POST localhost:8000/v1/keys -H "Authorization: Bearer $PLPR_ADMIN_TOKEN" \
  -H 'content-type: application/json' -d '{"name": "gate 1 camera", "role": "gate", "gate_id": 1}'
```

## Endpoints

| Method and path | Role | Notes |
|---|---|---|
| `GET /healthz` | none | DB check, whether models are loaded |
| `POST /v1/read` | viewer, gate | multipart `image` (JPEG/PNG/WebP). Returns plates; stores nothing |
| `POST /v1/gates/{id}/events` | gate | multipart: `plate_key`, `plate_conf`, `char_conf`, `agreement`, `event_id`, `timestamp`, optional `crop` image. Returns the stored entry with its `status`. A repeated `event_id` returns the existing entry |
| `GET/POST /v1/sites`, `GET/PUT/DELETE /v1/sites/{id}` | read: viewer, write: admin | |
| `GET/POST /v1/gates`, `GET/PUT/DELETE /v1/gates/{id}` | same | `?site_id=` filter |
| `GET/POST /v1/residents`, `GET/PUT/DELETE /v1/residents/{id}` | same | `?site_id=&plate=`; the plate is normalised (Persian digits, spaces and dashes are accepted) and unique per site |
| `GET /v1/residents/export.csv?site_id=` | viewer | columns `plate_key,name,unit,car_model,allowed` (UTF-8 with BOM, opens in Excel) |
| `POST /v1/residents/import?site_id=` | admin | multipart `file`, same columns; upserts by plate and reports bad rows |
| `GET /v1/entries` | viewer | filters `plate`, `status`, `gate_id`, `since`, `until`; `offset`/`limit`; returns `{total, items}`, newest first |
| `GET /v1/entries/{id}`, `GET /v1/entries/{id}/crop` | viewer | crop is a JPEG |
| `GET /v1/review` | viewer | unreviewed entries with low agreement or char confidence |
| `PATCH /v1/entries/{id}` | admin | `{"reviewed": true, "plate_key": "34D31966"}`; a corrected plate recomputes the status |
| `GET/POST /v1/webhooks`, `DELETE /v1/webhooks/{id}` | admin | the secret is returned only by POST |
| `GET/POST /v1/keys`, `DELETE /v1/keys/{id}` | admin | the token is returned only by POST |

Status rule: plate found in the gate's site resident list with `allowed=true` gives `allowed`, with `allowed=false` gives `denied`, not found gives `unknown`. All timestamps are UTC.

Uploads are checked at the boundary: content-type allow-list, `PLPR_MAX_UPLOAD_MB` cap, and the image must decode. Crops are re-encoded before they are written to disk.

## Webhooks

Each new entry fires `entry.allowed`, `entry.denied` or `entry.unknown` to every active webhook whose `events` list (comma separated, `*` for all) matches. Delivery runs in the background: one POST, then up to 3 retries with backoff (1 s, 2 s, 4 s).

```
POST <your url>
Content-Type: application/json
X-PLPR-Event: entry.allowed
X-PLPR-Signature: sha256=<hex HMAC-SHA256 of the raw body, keyed with the webhook secret>

{"event": "entry.allowed", "data": {"id": 12, "plate_key": "34D31966", "status": "allowed", "gate_id": 1, "site_id": 1, ...}}
```

Verify it on the receiving side against the raw bytes, before parsing:

```python
import hashlib, hmac

def verify(secret: str, body: bytes, header: str) -> bool:
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header)
```

Webhook URLs are set by admins and called from the server's network, so only add URLs you trust.

## Edge agent

```bash
export PLPR_AGENT_TOKEN=<gate key>
python -m server.agent --source rtsp://user:pass@192.168.1.64:554/stream1 --gate-id 1 --server http://plpr:8000
python -m server.agent --source 0 --gate-id 1 --standalone       # webcam, no server
python -m server.agent --source clip.mp4 --gate-id 1 --standalone  # a video file; exits at the end
```

- `--every N` runs recognition on every Nth frame (default 3). The tracker votes per character across frames and reports each vehicle once, with the crop from its sharpest read.
- **Offline buffering:** if the server can't be reached (network error, 5xx, 401/403), events go to `--spool` (default `./data/spool`, one JSON file each) and are sent oldest first once it answers again. Each event carries its own `event_id` and `timestamp`, so a retry never creates a duplicate and late events keep the time the car was seen. Events the server rejects as invalid (400/413/415/422) are logged and dropped.
- **Barrier relay:** `--relay-url URL` (or `PLPR_RELAY_URL`) is called when the server answers `allowed`. With `--relay-method POST` (default) it sends `{"plate_key": ..., "gate_id": ...}`; with `GET` it just requests the URL, which fits relays such as a Shelly (`http://<ip>/relay/0?turn=on`). Spooled events never trigger the relay: the car has left by then.
- **Reconnects:** RTSP and webcam sources are reopened every 3 s after a failure.
- **Shutdown:** SIGTERM or Ctrl-C stops after the current frame and makes one last attempt to flush the spool.
- `--standalone` writes entries into `--database-url` (default `sqlite:///./data/plpr.db`) using the same schema as the server, with status from that database's resident table. Point the server at the same file later to browse them.

## Importing v1 data

```bash
python -m server.import_v1 --residents database/residents.db --entries database/entries.db
```

Creates a site and gate (or use `--site-id`/`--gate-id`), upserts residents by plate (`fName lName` becomes the name, `building-block-num` the unit, status `0` means not allowed), and imports entries with v1 status codes `0/1/2` mapped to `denied/allowed/unknown`. v1 stored local times; `--tz` (default `Asia/Tehran`) converts them to UTC. Running it twice adds nothing new. Imported entries are marked reviewed.

## Docker

```bash
cp docker/.env.example docker/.env      # fill in PLPR_ADMIN_TOKEN and the camera URL
docker compose -f docker/docker-compose.yml up -d --build
curl localhost:8000/healthz
```

- `docker/Dockerfile` is multi-stage: the first stage installs CPU PyTorch and runs `scripts/export_onnx.py` on `model/*.pt`; the runtime stage is `python:3.12-slim` with onnxruntime only, running as a non-root user, data in the `/data` volume.
- `go2rtc` serves the camera to the web app over WebRTC (port 1984 for the API and signalling, 8555 for media) and restreams it over RTSP on 8554, so the agent and the browsers share one camera connection. Set `GATE1_RTSP_URL` in `docker/.env`. For WebRTC from other machines on Linux, `network_mode: host` on the go2rtc service is the simplest fix if the media port mapping isn't enough.
- The agent is in the `agent` profile because it needs a gate key: start the API, create a key, put it in `PLPR_AGENT_TOKEN`, then `docker compose -f docker/docker-compose.yml --profile agent up -d`.
- `--profile postgres` adds Postgres 16. Set `POSTGRES_PASSWORD` and `PLPR_DATABASE_URL=postgresql+psycopg://plpr:<password>@postgres:5432/plpr` (the image already includes psycopg). Tables are created on startup; there are no migrations yet.

## Running on edge hardware

The engine picks ONNX Runtime execution providers in this order: CUDA, CoreML, CPU (whichever the installed onnxruntime build offers). Which providers exist depends on the onnxruntime package you install, not on PLPR:

| Hardware | Package | Provider |
|---|---|---|
| x86 / ARM CPU, Raspberry Pi 4/5 (64-bit OS) | `onnxruntime` | `CPUExecutionProvider` |
| NVIDIA GPU | `onnxruntime-gpu` | `CUDAExecutionProvider`, `TensorrtExecutionProvider` |
| Jetson (JetPack) | NVIDIA's Jetson onnxruntime-gpu wheels | `CUDAExecutionProvider`, `TensorrtExecutionProvider` |
| Intel CPU/iGPU/NPU | `onnxruntime-openvino` | `OpenVINOExecutionProvider` |
| Apple Silicon | `onnxruntime` (macOS wheels) | `CoreMLExecutionProvider` |

To use TensorRT or OpenVINO, pass the provider list yourself: `Engine(providers=["TensorrtExecutionProvider", "CUDAExecutionProvider", "CPUExecutionProvider"])`; the agent and server use the default order above. On a Pi, start with `--every 5`. Keep the FP32 models on CPU: FP16 only pays off on GPUs.
