"""PLPR API server. Run: uvicorn server.app:app --host 0.0.0.0 --port 8000

Every endpoint except /healthz needs `Authorization: Bearer <token>`; see server/README.md.
"""
# No `from __future__ import annotations`: the CRUD helper below builds endpoints in a
# closure, and FastAPI must see real classes in those signatures, not strings.
import asyncio
import csv
import hashlib
import io
import logging
import secrets
import threading
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated

import cv2
import numpy as np
from fastapi import APIRouter, BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, create_engine, func, or_, select

from plpr import Engine, PlateNumber

from . import webhooks
from .models import (
    ApiKey,
    Entry,
    Gate,
    GateBase,
    Resident,
    ResidentBase,
    Role,
    Site,
    SiteBase,
    Status,
    Webhook,
    WebhookBase,
    resident_status,
    to_utc,
    utcnow,
)
from .settings import Settings

log = logging.getLogger("plpr.server")
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ---------------------------------------------------------------- plumbing

def hash_token(token: str) -> str:
    # API tokens are 256-bit random strings, so a fast hash is enough (no password stretching needed).
    return hashlib.sha256(token.encode()).hexdigest()


def get_session(request: Request):
    with Session(request.app.state.db) as session:
        yield session


def settings_of(request: Request) -> Settings:
    return request.app.state.settings


_bearer = HTTPBearer(auto_error=False)


def auth(*roles: Role):
    """Dependency: valid API key whose role is in `roles`. Admin keys pass every check."""
    def check(creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
              session: Annotated[Session, Depends(get_session)]) -> ApiKey:
        key = creds and session.exec(select(ApiKey).where(ApiKey.token_hash == hash_token(creds.credentials))).first()
        if not key:
            raise HTTPException(401, "missing or invalid API key", headers={"WWW-Authenticate": "Bearer"})
        if key.role != Role.admin and key.role not in roles:
            raise HTTPException(403, f"role {key.role.value} may not do this")
        return key
    return check


DB = Annotated[Session, Depends(get_session)]
Admin = Annotated[ApiKey, Depends(auth())]
Reader = Annotated[ApiKey, Depends(auth(Role.viewer))]
GateKey = Annotated[ApiKey, Depends(auth(Role.gate))]
ReadKey = Annotated[ApiKey, Depends(auth(Role.viewer, Role.gate))]


def get_or_404(session: Session, table, id_: int):
    obj = session.get(table, id_)
    if not obj:
        raise HTTPException(404, f"{table.__name__} {id_} not found")
    return obj


def commit(session: Session, obj):
    session.add(obj)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "conflicts with an existing record (duplicate or missing parent)") from None
    session.refresh(obj)
    return obj


def read_upload(upload: UploadFile, settings: Settings, types: set[str]) -> bytes:
    """Trust boundary for uploads: content type allow-list and a hard size cap."""
    if upload.content_type not in types:
        raise HTTPException(415, f"unsupported type {upload.content_type}; use one of {sorted(types)}")
    limit = int(settings.max_upload_mb * 1024 * 1024)
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"file larger than {settings.max_upload_mb} MB")
    return data


def decode_image(data: bytes) -> np.ndarray:
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(400, "not a decodable image")
    return img


def parse_plate(key: str) -> PlateNumber:
    plate = PlateNumber.from_key(key)
    if not plate:
        raise HTTPException(422, f"not a plate key: {key!r} (expected e.g. 34D31966)")
    return plate


def recognizer(request: Request) -> Engine:
    """Load the ONNX models on first use, so the API starts fast and tests that don't read images stay light."""
    state = request.app.state
    with state.engine_lock:
        if state.engine is None:
            s = state.settings
            state.engine = Engine(s.model_dir) if s.model_dir else Engine()
    return state.engine


def purge_old(session: Session, days: int, data_dir: Path) -> int:
    """Delete entries (and their crop files) older than `days`. Returns the number of entries removed."""
    cutoff = utcnow() - timedelta(days=days)
    old = session.exec(select(Entry).where(Entry.created_at < cutoff)).all()
    for e in old:
        if e.crop_path:
            (data_dir / e.crop_path).unlink(missing_ok=True)
        session.delete(e)
    session.commit()
    return len(old)


async def retention_loop(app: FastAPI) -> None:
    s: Settings = app.state.settings
    while True:
        try:
            with Session(app.state.db) as session:
                n = await asyncio.to_thread(purge_old, session, s.retention_days, s.data_dir)
            if n:
                log.info("retention: removed %d entries older than %d days", n, s.retention_days)
        except Exception:  # keep the loop alive; the next run retries
            log.exception("retention run failed")
        await asyncio.sleep(3600)


# ---------------------------------------------------------------- schemas

class PlateOut(BaseModel):
    box: tuple[int, int, int, int]
    plate_conf: float
    char_conf: float
    text: str
    key: str | None
    persian: str | None
    latin: str | None
    plate_type: str | None
    valid: bool


class EntryPage(BaseModel):
    total: int
    items: list[Entry]


class EntryReview(BaseModel):
    plate_key: str | None = None  # correct a misread; status is recomputed
    reviewed: bool = True


class KeyIn(BaseModel):
    name: str
    role: Role
    gate_id: int | None = None


class KeyOut(BaseModel):
    id: int
    name: str
    role: Role
    gate_id: int | None
    created_at: datetime
    token: str | None = None  # only returned once, at creation


class WebhookIn(WebhookBase):
    secret: str | None = None  # generated when omitted


class WebhookOut(WebhookBase):
    id: int


class WebhookCreated(WebhookOut):
    secret: str  # only returned here; store it on the receiving side


class ImportReport(BaseModel):
    created: int
    updated: int
    errors: list[str]


# ---------------------------------------------------------------- routes

v1 = APIRouter(prefix="/v1")


def add_crud(path: str, table: type[SQLModel], body: type[SQLModel], tag: str, clean=lambda s, d: d) -> None:
    """POST /path, GET/PUT/DELETE /path/{id}. Lists are written per resource because their filters differ."""
    @v1.post(path, response_model=table, status_code=201, tags=[tag], summary=f"Create {tag[:-1]}")
    def create(data: body, session: DB, _: Admin):
        return commit(session, table.model_validate(clean(session, data)))

    @v1.get(path + "/{id_}", response_model=table, tags=[tag], summary=f"Get {tag[:-1]}")
    def get_one(id_: int, session: DB, _: Reader):
        return get_or_404(session, table, id_)

    @v1.put(path + "/{id_}", response_model=table, tags=[tag], summary=f"Replace {tag[:-1]}")
    def replace(id_: int, data: body, session: DB, _: Admin):
        obj = get_or_404(session, table, id_)
        obj.sqlmodel_update(clean(session, data).model_dump())
        return commit(session, obj)

    @v1.delete(path + "/{id_}", status_code=204, tags=[tag], summary=f"Delete {tag[:-1]}")
    def delete(id_: int, session: DB, _: Admin):
        session.delete(get_or_404(session, table, id_))
        try:
            session.commit()
        except IntegrityError:
            raise HTTPException(409, "still referenced by other records") from None


def clean_resident(session: Session, data: ResidentBase) -> ResidentBase:
    get_or_404(session, Site, data.site_id)
    return data.model_copy(update={"plate_key": parse_plate(data.plate_key).key})


def clean_gate(session: Session, data: GateBase) -> GateBase:
    get_or_404(session, Site, data.site_id)
    return data


# sites, gates
@v1.get("/sites", response_model=list[Site], tags=["sites"], summary="List sites")
def list_sites(session: DB, _: Reader):
    return session.exec(select(Site)).all()


@v1.get("/gates", response_model=list[Gate], tags=["gates"], summary="List gates")
def list_gates(session: DB, _: Reader, site_id: int | None = None):
    q = select(Gate)
    if site_id is not None:
        q = q.where(Gate.site_id == site_id)
    return session.exec(q).all()


add_crud("/sites", Site, SiteBase, "sites")
add_crud("/gates", Gate, GateBase, "gates", clean_gate)


# residents: export/import are declared before add_crud so they match ahead of /residents/{id_}
@v1.get("/residents", response_model=list[Resident], tags=["residents"], summary="List residents")
def list_residents(session: DB, _: Reader, site_id: int | None = None, plate: str | None = None, offset: int = 0, limit: Annotated[int, Query(le=1000)] = 100):
    q = select(Resident)
    if site_id is not None:
        q = q.where(Resident.site_id == site_id)
    if plate:
        q = q.where(Resident.plate_key.contains(plate))
    return session.exec(q.order_by(Resident.id).offset(offset).limit(limit)).all()


CSV_FIELDS = ["plate_key", "name", "unit", "car_model", "allowed"]


@v1.get("/residents/export.csv", tags=["residents"], summary="Export residents of a site as CSV")
def export_residents(site_id: int, session: DB, _: Reader):
    out = io.StringIO()
    w = csv.DictWriter(out, CSV_FIELDS)
    w.writeheader()
    for r in session.exec(select(Resident).where(Resident.site_id == site_id).order_by(Resident.id)):
        w.writerow({f: getattr(r, f) for f in CSV_FIELDS} | {"allowed": int(r.allowed)})
    return Response("﻿" + out.getvalue(), media_type="text/csv; charset=utf-8",  # BOM so Excel shows Persian names
                    headers={"Content-Disposition": f'attachment; filename="residents-site{site_id}.csv"'})


@v1.post("/residents/import", response_model=ImportReport, tags=["residents"], summary="Import residents from CSV (upsert by plate)")
def import_residents(request: Request, site_id: int, file: Annotated[UploadFile, File()], session: DB, _: Admin):
    get_or_404(session, Site, site_id)
    data = read_upload(file, settings_of(request), {"text/csv", "application/vnd.ms-excel", "text/plain", "application/octet-stream"})
    try:
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8-sig"))))
    except (UnicodeDecodeError, csv.Error) as e:
        raise HTTPException(400, f"unreadable CSV: {e}") from None
    report = ImportReport(created=0, updated=0, errors=[])
    for line, row in enumerate(rows, start=2):
        plate = PlateNumber.from_key(row.get("plate_key") or "")
        if not plate:
            report.errors.append(f"line {line}: bad plate_key {row.get('plate_key')!r}")
            continue
        fields = {f: (row.get(f) or "").strip() for f in ("name", "unit", "car_model")}
        fields["allowed"] = (row.get("allowed") or "1").strip().lower() not in {"0", "false", "no", "denied"}
        r = session.exec(select(Resident).where(Resident.site_id == site_id, Resident.plate_key == plate.key)).first()
        if r:
            r.sqlmodel_update(fields)
            report.updated += 1
        else:
            r = Resident(site_id=site_id, plate_key=plate.key, **fields)
            report.created += 1
        session.add(r)
    session.commit()
    return report


add_crud("/residents", Resident, ResidentBase, "residents", clean_resident)


# webhooks: the secret is shown once, at creation
@v1.get("/webhooks", response_model=list[WebhookOut], tags=["webhooks"], summary="List webhooks")
def list_webhooks(session: DB, _: Admin):
    return session.exec(select(Webhook)).all()


@v1.post("/webhooks", response_model=WebhookCreated, status_code=201, tags=["webhooks"], summary="Create webhook")
def create_webhook(data: WebhookIn, session: DB, _: Admin):
    if not data.url.startswith(("http://", "https://")):
        raise HTTPException(422, "url must be http(s)")
    return commit(session, Webhook(**data.model_dump(exclude={"secret"}), secret=data.secret or secrets.token_urlsafe(32)))


@v1.delete("/webhooks/{id_}", status_code=204, tags=["webhooks"], summary="Delete webhook")
def delete_webhook(id_: int, session: DB, _: Admin):
    session.delete(get_or_404(session, Webhook, id_))
    session.commit()


# api keys
@v1.get("/keys", response_model=list[KeyOut], tags=["keys"], summary="List API keys")
def list_keys(session: DB, _: Admin):
    return [KeyOut(**k.model_dump()) for k in session.exec(select(ApiKey))]


@v1.post("/keys", response_model=KeyOut, status_code=201, tags=["keys"], summary="Create API key (token shown once)")
def create_key(data: KeyIn, session: DB, _: Admin):
    if data.gate_id is not None:
        get_or_404(session, Gate, data.gate_id)
    token = secrets.token_urlsafe(32)
    key = commit(session, ApiKey(**data.model_dump(), token_hash=hash_token(token)))
    return KeyOut(**key.model_dump(), token=token)


@v1.delete("/keys/{id_}", status_code=204, tags=["keys"], summary="Revoke API key")
def delete_key(id_: int, session: DB, me: Admin):
    if id_ == me.id:
        raise HTTPException(400, "can't revoke the key making this request")
    session.delete(get_or_404(session, ApiKey, id_))
    session.commit()


# recognition
@v1.post("/read", response_model=list[PlateOut], tags=["recognition"], summary="Read plates in an image (nothing is stored)")
def read_image(request: Request, image: Annotated[UploadFile, File()], _: ReadKey):
    s = settings_of(request)
    img = decode_image(read_upload(image, s, IMAGE_TYPES))
    out = []
    for r in recognizer(request).read(img, s.plate_conf, s.char_conf):
        p = r.plate
        out.append(PlateOut(box=r.box, plate_conf=r.plate_conf, char_conf=r.char_conf, text=r.text, key=p and p.key,
                            persian=p and p.persian, latin=p and p.latin, plate_type=p and p.plate_type, valid=bool(p and p.valid)))
    return out


@v1.post("/gates/{gate_id}/events", response_model=Entry, tags=["recognition"], summary="Edge agent reports a vehicle")
def gate_event(
    request: Request, gate_id: int, background: BackgroundTasks, session: DB, key: GateKey,
    plate_key: Annotated[str, Form()],
    plate_conf: Annotated[float, Form(ge=0, le=1)] = 0.0,
    char_conf: Annotated[float, Form(ge=0, le=1)] = 0.0,
    agreement: Annotated[float, Form(ge=0, le=1)] = 1.0,
    event_id: Annotated[str | None, Form(max_length=64)] = None,
    timestamp: Annotated[datetime | None, Form(description="when the agent saw it (buffered events); default now")] = None,
    crop: Annotated[UploadFile | None, File()] = None,
):
    gate = get_or_404(session, Gate, gate_id)
    if key.gate_id is not None and key.gate_id != gate_id:
        raise HTTPException(403, "this key belongs to another gate")
    if event_id and (seen := session.exec(select(Entry).where(Entry.event_id == event_id)).first()):
        return seen  # agent retry after a lost response
    plate = parse_plate(plate_key)
    s = settings_of(request)
    crop_path = None
    if crop is not None:
        img = decode_image(read_upload(crop, s, IMAGE_TYPES))
        crop_path = f"crops/{uuid.uuid4().hex}.jpg"
        cv2.imwrite(str(s.data_dir / crop_path), img)  # re-encode: never store the uploaded bytes as-is
    status, resident_id = resident_status(session, gate.site_id, plate.key)
    entry = commit(session, Entry(
        event_id=event_id, gate_id=gate_id, plate_key=plate.key, persian=plate.persian, plate_type=plate.plate_type,
        plate_conf=plate_conf, char_conf=char_conf, agreement=agreement, status=status, resident_id=resident_id,
        created_at=to_utc(timestamp) if timestamp else utcnow(), crop_path=crop_path,
    ))
    fire_webhooks(session, background, f"entry.{status.value}", entry.model_dump(mode="json") | {"site_id": gate.site_id})
    return entry


def fire_webhooks(session: Session, background: BackgroundTasks, event: str, data: dict) -> None:
    for wh in session.exec(select(Webhook).where(Webhook.active == True)):
        wanted = {e.strip() for e in wh.events.split(",")}
        if "*" in wanted or event in wanted:
            background.add_task(webhooks.deliver, wh.url, wh.secret, event, data)


# entries
def entry_filters(q, plate, status, gate_id, since, until):
    if plate:
        q = q.where(Entry.plate_key.contains(plate))
    if status:
        q = q.where(Entry.status == status)
    if gate_id is not None:
        q = q.where(Entry.gate_id == gate_id)
    if since:
        q = q.where(Entry.created_at >= to_utc(since))
    if until:
        q = q.where(Entry.created_at < to_utc(until))
    return q


@v1.get("/entries", response_model=EntryPage, tags=["entries"], summary="List entries, newest first")
def list_entries(session: DB, _: Reader, plate: str | None = None, status: Status | None = None, gate_id: int | None = None,
                 since: datetime | None = None, until: datetime | None = None,
                 offset: Annotated[int, Query(ge=0)] = 0, limit: Annotated[int, Query(ge=1, le=500)] = 50):
    total = session.exec(entry_filters(select(func.count()).select_from(Entry), plate, status, gate_id, since, until)).one()
    items = session.exec(entry_filters(select(Entry), plate, status, gate_id, since, until)
                         .order_by(Entry.created_at.desc()).offset(offset).limit(limit)).all()
    return EntryPage(total=total, items=items)


@v1.get("/review", response_model=list[Entry], tags=["entries"], summary="Unreviewed entries with low agreement or confidence")
def review_queue(session: DB, _: Reader, request: Request, limit: Annotated[int, Query(ge=1, le=500)] = 50):
    s = settings_of(request)
    q = select(Entry).where(Entry.reviewed == False, or_(Entry.agreement < s.review_agreement, Entry.char_conf < s.review_conf))
    return session.exec(q.order_by(Entry.created_at.desc()).limit(limit)).all()


@v1.get("/entries/{id_}", response_model=Entry, tags=["entries"], summary="Get entry")
def get_entry(id_: int, session: DB, _: Reader):
    return get_or_404(session, Entry, id_)


@v1.patch("/entries/{id_}", response_model=Entry, tags=["entries"], summary="Review an entry, optionally correcting the plate")
def review_entry(id_: int, data: EntryReview, session: DB, _: Admin):
    e = get_or_404(session, Entry, id_)
    if data.plate_key:
        plate = parse_plate(data.plate_key)
        site_id = get_or_404(session, Gate, e.gate_id).site_id
        e.plate_key, e.persian, e.plate_type = plate.key, plate.persian, plate.plate_type
        e.status, e.resident_id = resident_status(session, site_id, plate.key)
    e.reviewed = data.reviewed
    return commit(session, e)


@v1.get("/entries/{id_}/crop", tags=["entries"], summary="Plate crop image (JPEG)", response_class=FileResponse)
def entry_crop(request: Request, id_: int, session: DB, _: Reader):
    e = get_or_404(session, Entry, id_)
    path = settings_of(request).data_dir / e.crop_path if e.crop_path else None
    if not path or not path.exists():
        raise HTTPException(404, "no crop stored for this entry")
    return FileResponse(path, media_type="image/jpeg")


# ---------------------------------------------------------------- app

def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        (settings.data_dir / "crops").mkdir(parents=True, exist_ok=True)
        if settings.database_url.startswith("sqlite:///"):
            Path(settings.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        SQLModel.metadata.create_all(app.state.db)
        if settings.admin_token:
            with Session(app.state.db) as session:
                h = hash_token(settings.admin_token)
                if not session.exec(select(ApiKey).where(ApiKey.token_hash == h)).first():
                    session.add(ApiKey(name="bootstrap-admin", token_hash=h, role=Role.admin))
                    session.commit()
        task = asyncio.create_task(retention_loop(app)) if settings.retention_days > 0 else None
        yield
        if task:
            task.cancel()

    app = FastAPI(title="PLPR API", version="2.0.0", lifespan=lifespan,
                  description="Persian license plate recognition: read images, log gate entries, manage residents.")
    app.state.settings = settings
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    app.state.db = create_engine(settings.database_url, connect_args=connect_args)
    app.state.engine = None
    app.state.engine_lock = threading.Lock()
    if settings.cors_origins:
        app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    app.include_router(v1)

    @app.get("/healthz", tags=["health"])
    def healthz(request: Request):
        with Session(request.app.state.db) as session:
            session.exec(select(1)).one()
        return {"status": "ok", "models_loaded": request.app.state.engine is not None}

    return app


app = create_app()
