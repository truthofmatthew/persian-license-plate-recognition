import hashlib
import hmac
import json
import sqlite3
from datetime import timedelta
from pathlib import Path

import cv2
import httpx
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from plpr.engine import DEFAULT_MODEL_DIR
from server import webhooks
from server.app import create_app, purge_old
from server.import_v1 import import_v1
from server.models import Entry, Resident, utcnow
from server.settings import Settings

FIX = Path(__file__).parent / "fixtures"
ADMIN = {"Authorization": "Bearer admin-test-token"}
needs_models = pytest.mark.skipif(not (DEFAULT_MODEL_DIR / "plate.onnx").exists(), reason="run scripts/export_onnx.py first")


@pytest.fixture
def app(tmp_path):
    return create_app(Settings(database_url=f"sqlite:///{tmp_path}/plpr.db", data_dir=tmp_path, admin_token="admin-test-token",
                               retention_days=0))


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def gate(client):
    site = client.post("/v1/sites", json={"name": "Tower A"}, headers=ADMIN).json()
    return client.post("/v1/gates", json={"site_id": site["id"], "name": "main"}, headers=ADMIN).json()


def make_key(client, role, gate_id=None):
    r = client.post("/v1/keys", json={"name": role, "role": role, "gate_id": gate_id}, headers=ADMIN)
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['token']}"}


def scene_jpeg(name="34D31966") -> bytes:
    img = cv2.imread(str(FIX / f"plate_{name}.jpg"))
    scene = cv2.copyMakeBorder(img, 300, 300, 300, 300, cv2.BORDER_CONSTANT, value=(90, 90, 90))
    return cv2.imencode(".jpg", scene)[1].tobytes()


def test_auth_and_roles(client, gate):
    assert client.get("/healthz").json()["status"] == "ok"
    assert client.get("/v1/sites").status_code == 401
    assert client.get("/v1/sites", headers={"Authorization": "Bearer nope"}).status_code == 401
    viewer = make_key(client, "viewer")
    assert client.get("/v1/sites", headers=viewer).status_code == 200
    assert client.post("/v1/sites", json={"name": "x"}, headers=viewer).status_code == 403
    assert client.post(f"/v1/gates/{gate['id']}/events", data={"plate_key": "34D31966"}, headers=viewer).status_code == 403
    gate_key = make_key(client, "gate", gate["id"])
    assert client.get("/v1/entries", headers=gate_key).status_code == 403
    other = client.post("/v1/gates", json={"site_id": gate["site_id"], "name": "back"}, headers=ADMIN).json()
    assert client.post(f"/v1/gates/{other['id']}/events", data={"plate_key": "34D31966"}, headers=gate_key).status_code == 403


def test_upload_limits(client):
    files = {"image": ("x.gif", b"GIF89a", "image/gif")}
    assert client.post("/v1/read", files=files, headers=ADMIN).status_code == 415
    files = {"image": ("x.jpg", b"not really a jpeg", "image/jpeg")}
    assert client.post("/v1/read", files=files, headers=ADMIN).status_code == 400


@needs_models
def test_read_endpoint(client):
    r = client.post("/v1/read", files={"image": ("scene.jpg", scene_jpeg(), "image/jpeg")}, headers=ADMIN)
    assert r.status_code == 200
    assert [p["key"] for p in r.json()] == ["34D31966"]
    assert "ایران" in r.json()[0]["persian"]


def test_gate_event_status_and_webhook(client, gate, monkeypatch):
    sent = []
    monkeypatch.setattr(webhooks, "deliver", lambda *a, **k: sent.append(a))
    wh = client.post("/v1/webhooks", json={"url": "https://example.test/hook", "events": "entry.allowed"}, headers=ADMIN).json()
    assert wh["secret"] and "secret" not in client.get("/v1/webhooks", headers=ADMIN).json()[0]
    client.post("/v1/residents", json={"site_id": gate["site_id"], "plate_key": "34D31966", "name": "Ali"}, headers=ADMIN)
    gk = make_key(client, "gate", gate["id"])
    url = f"/v1/gates/{gate['id']}/events"

    crop = cv2.imencode(".jpg", cv2.imread(str(FIX / "plate_34D31966.jpg")))[1].tobytes()
    e = client.post(url, data={"plate_key": "34D31966", "plate_conf": 0.9, "char_conf": 0.95, "event_id": "a1"},
                    files={"crop": ("c.jpg", crop, "image/jpeg")}, headers=gk).json()
    assert e["status"] == "allowed" and e["resident_id"]
    assert client.get(f"/v1/entries/{e['id']}/crop", headers=ADMIN).content[:2] == b"\xff\xd8"
    # retry with the same event id is a no-op
    assert client.post(url, data={"plate_key": "34D31966", "event_id": "a1"}, headers=gk).json()["id"] == e["id"]

    u = client.post(url, data={"plate_key": "87Y16111", "agreement": 0.5, "timestamp": "2026-01-02T03:04:05+03:30"}, headers=gk).json()
    assert u["status"] == "unknown" and u["created_at"].startswith("2026-01-01T23:34:05")
    assert client.post(url, data={"plate_key": "garbage"}, headers=gk).status_code == 422

    assert [s[2] for s in sent] == ["entry.allowed"]  # unknown entry didn't match the webhook's event filter
    assert sent[0][3]["plate_key"] == "34D31966"

    page = client.get("/v1/entries", params={"status": "unknown"}, headers=ADMIN).json()
    assert page["total"] == 1 and page["items"][0]["plate_key"] == "87Y16111"
    assert client.get("/v1/entries", params={"plate": "34D", "since": "2026-06-01T00:00:00Z"}, headers=ADMIN).json()["total"] == 1
    assert [x["id"] for x in client.get("/v1/review", headers=ADMIN).json()] == [u["id"]]
    fixed = client.patch(f"/v1/entries/{u['id']}", json={"plate_key": "34D31966"}, headers=ADMIN).json()
    assert fixed["status"] == "allowed" and fixed["reviewed"]
    assert client.get("/v1/review", headers=ADMIN).json() == []


def test_webhook_signature_and_retries():
    calls = []

    def handler(request: httpx.Request):
        calls.append(request)
        return httpx.Response(500 if len(calls) < 3 else 200)

    ok = webhooks.deliver("https://example.test/hook", "s3cret", "entry.allowed", {"plate_key": "34D31966"},
                          backoff=0, transport=httpx.MockTransport(handler))
    assert ok and len(calls) == 3
    req = calls[-1]
    expected = "sha256=" + hmac.new(b"s3cret", req.content, hashlib.sha256).hexdigest()
    assert req.headers["X-PLPR-Signature"] == expected
    assert json.loads(req.content) == {"event": "entry.allowed", "data": {"plate_key": "34D31966"}}

    calls.clear()
    assert not webhooks.deliver("https://example.test/hook", "s", "e", {}, retries=3, backoff=0,
                                transport=httpx.MockTransport(lambda r: calls.append(r) or httpx.Response(503)))
    assert len(calls) == 4  # first try + 3 retries


def test_residents_csv_roundtrip(client, gate):
    site = gate["site_id"]
    csv_in = "plate_key,name,unit,car_model,allowed\n34D31966,علی رضایی,A-12,Pride,1\n87Y16111,Sara,B-3,,0\nbad,x,,,1\n"
    r = client.post("/v1/residents/import", params={"site_id": site}, files={"file": ("r.csv", csv_in.encode(), "text/csv")}, headers=ADMIN)
    assert r.json()["created"] == 2 and len(r.json()["errors"]) == 1
    out = client.get("/v1/residents/export.csv", params={"site_id": site}, headers=ADMIN).content
    # importing the export again updates the same rows, nothing new
    r2 = client.post("/v1/residents/import", params={"site_id": site}, files={"file": ("r.csv", out, "text/csv")}, headers=ADMIN)
    assert r2.json() == {"created": 0, "updated": 2, "errors": []}
    rows = client.get("/v1/residents", params={"site_id": site}, headers=ADMIN).json()
    assert {(x["plate_key"], x["name"], x["allowed"]) for x in rows} == {("34D31966", "علی رضایی", True), ("87Y16111", "Sara", False)}
    dup = client.post("/v1/residents", json={"site_id": site, "plate_key": "34D31966"}, headers=ADMIN)
    assert dup.status_code == 409


def test_import_v1(tmp_path, app, client):
    res, ent = tmp_path / "residents.db", tmp_path / "entries.db"
    with sqlite3.connect(res) as c:
        c.execute("CREATE TABLE residents (fName TEXT, lName TEXT, building INTEGER, block INTEGER, num INTEGER, carModel TEXT,"
                  " plateNum VARCHAR(12) NOT NULL, status INTEGER, UNIQUE(plateNum))")
        c.executemany("INSERT INTO residents VALUES (?,?,?,?,?,?,?,?)",
                      [("Ali", "Rezaei", 1, 2, 3, "Pride", "34D31966", 1), ("Bad", "Plate", 1, 1, 1, "", "xx", 1)])
    with sqlite3.connect(ent) as c:
        c.execute("CREATE TABLE entries (platePercent INTEGER, charPercent INTEGER, eDate VARCHAR(25), eTime VARCHAR(25),"
                  " plateNum VARCHAR(20) NOT NULL, status INTEGER)")
        c.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?)",
                      [(93, 76, "2024-03-04", "02:50:03", "34D31966", 1), (80, 70, "2024-03-04", "02:51:00", "87Y16111", 2)])
    with Session(app.state.db) as s:
        rep = import_v1(s, res, ent)
        assert (rep["residents"], rep["entries"], len(rep["skipped"])) == (1, 2, 1)
        assert import_v1(s, res, ent, rep["site_id"], rep["gate_id"])["entries"] == 0  # idempotent
        r = s.exec(select(Resident)).one()
        assert (r.name, r.unit, r.allowed) == ("Ali Rezaei", "1-2-3", True)
        e = s.exec(select(Entry).where(Entry.plate_key == "34D31966")).one()
        assert e.status == "allowed" and e.plate_conf == 0.93 and e.resident_id == r.id
        assert e.created_at.strftime("%Y-%m-%d %H:%M") == "2024-03-03 23:20"  # 02:50 Tehran = 23:20 UTC


def test_retention(app, client, gate, tmp_path):
    gk = make_key(client, "gate", gate["id"])
    crop = cv2.imencode(".jpg", cv2.imread(str(FIX / "plate_34D31966.jpg")))[1].tobytes()
    old_ts = (utcnow() - timedelta(days=100)).isoformat()
    old = client.post(f"/v1/gates/{gate['id']}/events", data={"plate_key": "34D31966", "timestamp": old_ts},
                      files={"crop": ("c.jpg", crop, "image/jpeg")}, headers=gk).json()
    new = client.post(f"/v1/gates/{gate['id']}/events", data={"plate_key": "87Y16111"}, headers=gk).json()
    crop_file = tmp_path / old["crop_path"]
    assert crop_file.exists()
    with Session(app.state.db) as s:
        assert purge_old(s, 90, tmp_path) == 1
        assert [e.id for e in s.exec(select(Entry))] == [new["id"]]
    assert not crop_file.exists()
