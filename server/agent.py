"""Edge agent: camera -> Engine + PlateTracker -> one event per vehicle -> PLPR server.

    python -m server.agent --source rtsp://user:pass@cam/stream --gate-id 1 --server http://api:8000 --token $TOKEN
    python -m server.agent --source 0 --gate-id 1 --standalone          # webcam, local SQLite, no server

Events that can't be delivered are spooled to disk (one JSON file each) and flushed, in
order, once the server answers again. With --relay-url the agent calls that URL whenever
the server says a plate is allowed, e.g. a Shelly/ESP relay that opens the barrier.
"""
from __future__ import annotations

import argparse
import base64
import json
import logging
import os
import signal
import threading
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

import cv2
import httpx
import numpy as np

from plpr import Engine, PlateTracker

log = logging.getLogger("plpr.agent")


class Offline(Exception):
    """Delivery failed in a way that may succeed later (network, 5xx, auth): spool and retry."""


@dataclass
class Event:
    event_id: str
    plate_key: str
    plate_conf: float
    char_conf: float
    agreement: float
    timestamp: str  # ISO 8601, UTC
    crop: bytes | None = None  # JPEG

    def to_json(self) -> str:
        d = asdict(self)
        d["crop"] = base64.b64encode(self.crop).decode() if self.crop else None
        return json.dumps(d)

    @classmethod
    def from_json(cls, s: str) -> Event:
        d = json.loads(s)
        d["crop"] = base64.b64decode(d["crop"]) if d["crop"] else None
        return cls(**d)


class HttpSink:
    """Posts events to POST /v1/gates/{gate_id}/events. `client` may be a FastAPI TestClient."""

    DROP = frozenset({400, 413, 415, 422})  # the server will never accept these, retrying is pointless

    def __init__(self, server: str, token: str, gate_id: int, client: httpx.Client | None = None):
        self.client = client or httpx.Client(base_url=server, timeout=10)
        self.path = f"/v1/gates/{gate_id}/events"
        self.headers = {"Authorization": f"Bearer {token}"}

    def post(self, ev: Event) -> dict | None:
        data = {k: str(v) for k, v in asdict(ev).items() if k != "crop"}
        files = {"crop": ("crop.jpg", ev.crop, "image/jpeg")} if ev.crop else None
        try:
            r = self.client.post(self.path, data=data, files=files, headers=self.headers)
        except httpx.HTTPError as e:
            raise Offline(str(e)) from e
        if r.status_code in self.DROP:
            log.error("server rejected %s (%s): %s", ev.plate_key, r.status_code, r.text[:200])
            return None
        if r.is_error:
            raise Offline(f"HTTP {r.status_code}")
        return r.json()


class LocalSink:
    """--standalone: write entries straight into a local database with the server's schema."""

    def __init__(self, database_url: str, data_dir: Path, gate_id: int):
        from sqlmodel import Session, SQLModel, create_engine

        from .models import Gate, Site

        self.data_dir, self.gate_id = Path(data_dir), gate_id
        (self.data_dir / "crops").mkdir(parents=True, exist_ok=True)
        if database_url.startswith("sqlite:///"):
            Path(database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        self.db = create_engine(database_url)
        SQLModel.metadata.create_all(self.db)
        with Session(self.db) as s:
            if not s.get(Gate, gate_id):
                site = Site(name="local")
                s.add(site)
                s.flush()
                s.add(Gate(id=gate_id, site_id=site.id, name=f"gate {gate_id}"))
                s.commit()

    def post(self, ev: Event) -> dict:
        from datetime import datetime

        from sqlmodel import Session

        from plpr import PlateNumber

        from .models import Entry, Gate, resident_status, to_utc

        plate = PlateNumber.from_key(ev.plate_key)
        crop_path = None
        if ev.crop:
            crop_path = f"crops/{ev.event_id}.jpg"
            (self.data_dir / crop_path).write_bytes(ev.crop)
        with Session(self.db) as s:
            status, resident_id = resident_status(s, s.get(Gate, self.gate_id).site_id, plate.key)
            e = Entry(event_id=ev.event_id, gate_id=self.gate_id, plate_key=plate.key, persian=plate.persian,
                      plate_type=plate.plate_type, plate_conf=ev.plate_conf, char_conf=ev.char_conf, agreement=ev.agreement,
                      status=status, resident_id=resident_id, created_at=to_utc(datetime.fromisoformat(ev.timestamp)),
                      crop_path=crop_path)
            s.add(e)
            s.commit()
            s.refresh(e)
            return e.model_dump(mode="json")


class Spool:
    """Disk queue: one JSON file per undelivered event, named so that sorting = arrival order."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)

    def put(self, ev: Event) -> None:
        f = self.path / f"{time.time_ns()}-{ev.event_id}.json"
        tmp = f.with_suffix(".tmp")
        tmp.write_text(ev.to_json())
        os.replace(tmp, f)  # atomic: a crash never leaves half an event behind

    def files(self) -> list[Path]:
        return sorted(self.path.glob("*.json"))

    def __len__(self) -> int:
        return len(self.files())


class Agent:
    def __init__(self, engine: Engine, sink, spool: Spool, every: int = 3, tracker: PlateTracker | None = None,
                 plate_conf: float = 0.5, char_conf: float = 0.5, relay_url: str | None = None, relay_method: str = "POST",
                 gate_id: int | None = None, flush_interval: float = 10.0):
        self.engine, self.sink, self.spool, self.every = engine, sink, spool, max(1, every)
        self.tracker = tracker or PlateTracker()
        self.plate_conf, self.char_conf = plate_conf, char_conf
        self.relay_url, self.relay_method, self.gate_id = relay_url, relay_method, gate_id
        self.flush_interval, self._last_flush = flush_interval, 0.0
        self.frame_no = 0
        self.best: dict[int, tuple[float, bytes]] = {}  # per live track: best char conf seen and that frame's crop

    def process(self, frame: np.ndarray) -> list[dict | None]:
        """Feed one frame. Returns the server's answer for every vehicle finished on this frame."""
        self.frame_no += 1
        if self.frame_no % self.every:
            return []
        reads = self.engine.read(frame, self.plate_conf, self.char_conf)
        done = self.tracker.update(reads)
        for t in self.tracker.tracks + done:
            r = next((r for r in reads if r.plate and r.box == t.box and t.missed == 0), None)
            if r and r.char_conf >= self.best.get(t.id, (-1.0, b""))[0]:
                self.best[t.id] = (r.char_conf, crop_jpeg(frame, t.box))
        results = self.finish(done)
        if len(self.spool) and time.monotonic() - self._last_flush > self.flush_interval:
            self.flush()
        return results

    def finish(self, done: list | None = None) -> list[dict | None]:
        """Deliver finished tracks; with no argument, finish everything still pending (end of input)."""
        if done is None:
            done = self.tracker.flush()
        results = []
        for t in done:
            conf, crop = self.best.get(t.id, (0.0, None))
            ev = Event(uuid.uuid4().hex, t.best.key, round(t.plate_conf, 4), round(conf, 4), round(t.agreement, 4),
                       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), crop)
            log.info("vehicle %s (agreement %.2f)", ev.plate_key, ev.agreement)
            results.append(self.deliver(ev))
        live = {t.id for t in self.tracker.tracks}
        self.best = {k: v for k, v in self.best.items() if k in live}
        return results

    def deliver(self, ev: Event) -> dict | None:
        if len(self.spool) and not self.flush():  # keep order: older events first
            self.spool.put(ev)
            return None
        try:
            res = self.sink.post(ev)
        except Offline as e:
            log.warning("server unreachable (%s), spooling %s", e, ev.plate_key)
            self.spool.put(ev)
            return None
        if res and res.get("status") == "allowed":
            self.open_barrier(ev)
        return res

    def flush(self) -> bool:
        """Send spooled events oldest first; stop at the first failure. True when the spool is empty."""
        self._last_flush = time.monotonic()
        for f in self.spool.files():
            try:
                self.sink.post(Event.from_json(f.read_text()))  # no relay for late events: the car is long gone
            except Offline:
                return False
            f.unlink()
        return True

    def open_barrier(self, ev: Event) -> None:
        if not self.relay_url:
            return
        try:
            httpx.request(self.relay_method, self.relay_url, timeout=5,
                          json={"plate_key": ev.plate_key, "gate_id": self.gate_id} if self.relay_method == "POST" else None)
        except httpx.HTTPError as e:
            log.error("relay call failed: %s", e)


def crop_jpeg(frame: np.ndarray, box: tuple, pad: float = 0.1) -> bytes:
    x1, y1, x2, y2 = box
    px, py = int((x2 - x1) * pad), int((y2 - y1) * pad)
    h, w = frame.shape[:2]
    crop = frame[max(0, y1 - py):min(h, y2 + py), max(0, x1 - px):min(w, x2 + px)]
    return cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()


def run(source: str, agent: Agent, stop: threading.Event, reconnect_delay: float = 3.0) -> None:
    """Read frames until stopped. Streams (RTSP/webcam) reconnect on failure; a video file ends the run."""
    is_file = Path(source).is_file()
    while not stop.is_set():
        cap = cv2.VideoCapture(int(source) if source.isdigit() else source)
        if not cap.isOpened():
            log.warning("can't open %s, retrying in %.0fs", source, reconnect_delay)
        while cap.isOpened() and not stop.is_set():
            ok, frame = cap.read()
            if not ok:
                break
            agent.process(frame)
        cap.release()
        if is_file:
            break
        if not stop.is_set():
            log.warning("stream %s dropped, reconnecting", source)
            stop.wait(reconnect_delay)
    agent.finish()  # car still in view when the file ended or the agent was stopped
    agent.flush()


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--source", required=True, help="rtsp://..., webcam index (0) or a video file")
    ap.add_argument("--gate-id", type=int, required=True)
    ap.add_argument("--server", default=os.environ.get("PLPR_SERVER", "http://localhost:8000"))
    ap.add_argument("--token", default=os.environ.get("PLPR_AGENT_TOKEN"), help="gate API key (prefer the PLPR_AGENT_TOKEN env var)")
    ap.add_argument("--standalone", action="store_true", help="no server: write entries to --database-url")
    ap.add_argument("--database-url", default="sqlite:///./data/plpr.db")
    ap.add_argument("--data-dir", default="./data")
    ap.add_argument("--spool", default="./data/spool", help="folder for events waiting for the server")
    ap.add_argument("--every", type=int, default=3, help="run recognition on every Nth frame")
    ap.add_argument("--plate-conf", type=float, default=0.5)
    ap.add_argument("--char-conf", type=float, default=0.5)
    ap.add_argument("--model-dir", default=os.environ.get("PLPR_MODEL_DIR"))
    ap.add_argument("--relay-url", default=os.environ.get("PLPR_RELAY_URL"), help="called when the server says 'allowed'")
    ap.add_argument("--relay-method", choices=["GET", "POST"], default="POST")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    if args.standalone:
        sink = LocalSink(args.database_url, Path(args.data_dir), args.gate_id)
    elif not args.token:
        ap.error("--token or PLPR_AGENT_TOKEN is required unless --standalone")
    else:
        sink = HttpSink(args.server, args.token, args.gate_id)
    engine = Engine(args.model_dir) if args.model_dir else Engine()
    agent = Agent(engine, sink, Spool(Path(args.spool)), args.every, plate_conf=args.plate_conf, char_conf=args.char_conf,
                  relay_url=args.relay_url, relay_method=args.relay_method, gate_id=args.gate_id)
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())
    log.info("agent started: gate %s, source %s, %s", args.gate_id, args.source, "standalone" if args.standalone else args.server)
    run(args.source, agent, stop)
    log.info("agent stopped, %d events still spooled", len(agent.spool))


if __name__ == "__main__":
    main()
