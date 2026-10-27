import threading
from pathlib import Path

import cv2
import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient

from plpr.engine import DEFAULT_MODEL_DIR
from server.agent import Agent, Event, HttpSink, LocalSink, Spool, run
from server.app import create_app
from server.settings import Settings

FIX = Path(__file__).parent / "fixtures"
ADMIN = {"Authorization": "Bearer admin-test-token"}
pytestmark = pytest.mark.skipif(not (DEFAULT_MODEL_DIR / "plate.onnx").exists(), reason="run scripts/export_onnx.py first")


@pytest.fixture(scope="module")
def engine():
    from plpr import Engine

    return Engine()


@pytest.fixture
def server(tmp_path):
    app = create_app(Settings(database_url=f"sqlite:///{tmp_path}/plpr.db", data_dir=tmp_path / "srv", admin_token="admin-test-token"))
    with TestClient(app) as c:
        site = c.post("/v1/sites", json={"name": "s"}, headers=ADMIN).json()
        gate = c.post("/v1/gates", json={"site_id": site["id"], "name": "g"}, headers=ADMIN).json()
        c.post("/v1/residents", json={"site_id": site["id"], "plate_key": "34D31966"}, headers=ADMIN)
        token = c.post("/v1/keys", json={"name": "cam", "role": "gate", "gate_id": gate["id"]}, headers=ADMIN).json()["token"]
        yield c, gate["id"], token


def make_video(path: Path) -> Path:
    """One car: the plate drifts across a grey 960x540 frame for 40 frames, then 30 empty frames."""
    plate = cv2.imread(str(FIX / "plate_34D31966.jpg"))
    h, w = plate.shape[:2]
    out = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (960, 540))
    for i in range(70):
        frame = np.full((540, 960, 3), 90, np.uint8)
        if i < 40:
            x, y = 100 + 3 * i, 200
            frame[y:y + h, x:x + w] = plate
        out.write(frame)
    out.release()
    return path


def test_agent_one_event_per_vehicle(engine, server, tmp_path):
    client, gate_id, token = server
    relay_calls = []
    agent = Agent(engine, HttpSink("", token, gate_id, client=client), Spool(tmp_path / "spool"), every=2)
    agent.open_barrier = relay_calls.append  # relay is plain HTTP; just record the call here
    run(str(make_video(tmp_path / "car.avi")), agent, threading.Event())

    entries = client.get("/v1/entries", headers=ADMIN).json()
    assert [e["plate_key"] for e in entries["items"]] == ["34D31966"]
    e = entries["items"][0]
    assert e["status"] == "allowed" and e["crop_path"] and e["agreement"] > 0.9
    assert [ev.plate_key for ev in relay_calls] == ["34D31966"]
    assert len(agent.spool) == 0


def test_agent_buffers_offline_then_flushes(server, tmp_path):
    client, gate_id, token = server

    def down(request):
        raise httpx.ConnectError("server down")

    sink = HttpSink("http://plpr.invalid", token, gate_id, client=httpx.Client(transport=httpx.MockTransport(down), base_url="http://x"))
    agent = Agent(None, sink, Spool(tmp_path / "spool"))
    ev1 = Event("e1", "34D31966", 0.9, 0.9, 1.0, "2026-10-27T08:00:00Z")
    ev2 = Event("e2", "87Y16111", 0.9, 0.9, 1.0, "2026-10-27T08:01:00Z", b"")
    assert agent.deliver(ev1) is None and agent.deliver(ev2) is None
    assert len(agent.spool) == 2

    sink.client = client  # server is back
    assert agent.flush() and len(agent.spool) == 0
    items = client.get("/v1/entries", headers=ADMIN).json()["items"]
    assert [(e["event_id"], e["created_at"][:19]) for e in items] == [("e2", "2026-10-27T08:01:00"), ("e1", "2026-10-27T08:00:00")]
    assert agent.flush()  # nothing left, nothing re-sent
    assert client.get("/v1/entries", headers=ADMIN).json()["total"] == 2


def test_standalone_sink(tmp_path):
    sink = LocalSink(f"sqlite:///{tmp_path}/local.db", tmp_path, gate_id=3)
    out = sink.post(Event("e1", "34D31966", 0.9, 0.8, 1.0, "2026-10-27T08:00:00Z", b"\xff\xd8jpeg"))
    assert out["status"] == "unknown" and out["gate_id"] == 3 and (tmp_path / out["crop_path"]).exists()
