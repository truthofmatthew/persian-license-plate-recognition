"""Database tables. Everything goes through SQLModel, so SQLite and Postgres both work."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, Session, SQLModel, UniqueConstraint, select


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def to_utc(dt: datetime) -> datetime:
    """Aware UTC (SQLModel requires tz-aware datetimes). Naive input is taken as UTC."""
    return dt.astimezone(timezone.utc) if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class Role(str, Enum):
    admin = "admin"
    gate = "gate"
    viewer = "viewer"


class Status(str, Enum):
    allowed = "allowed"
    denied = "denied"
    unknown = "unknown"


class SiteBase(SQLModel):
    name: str


class Site(SiteBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class GateBase(SQLModel):
    site_id: int = Field(foreign_key="site.id", index=True)
    name: str


class Gate(GateBase, table=True):
    id: int | None = Field(default=None, primary_key=True)


class ResidentBase(SQLModel):
    site_id: int = Field(foreign_key="site.id", index=True)
    plate_key: str = Field(index=True, description="v1 key format, e.g. 34D31966")
    name: str = ""
    unit: str = ""
    car_model: str = ""
    allowed: bool = True


class Resident(ResidentBase, table=True):
    __table_args__ = (UniqueConstraint("site_id", "plate_key"),)
    id: int | None = Field(default=None, primary_key=True)


class Entry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    event_id: str | None = Field(default=None, unique=True, description="client id, makes agent retries idempotent")
    gate_id: int = Field(foreign_key="gate.id", index=True)
    plate_key: str = Field(index=True)
    persian: str = ""
    plate_type: str = ""
    plate_conf: float = 0.0
    char_conf: float = 0.0
    agreement: float = 1.0
    status: Status = Field(index=True)
    resident_id: int | None = Field(default=None, foreign_key="resident.id")
    created_at: datetime = Field(default_factory=utcnow, index=True)
    crop_path: str | None = None
    reviewed: bool = False


class ApiKey(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    token_hash: str = Field(unique=True)
    role: Role
    gate_id: int | None = Field(default=None, foreign_key="gate.id", description="gate keys may be pinned to one gate")
    created_at: datetime = Field(default_factory=utcnow)


class WebhookBase(SQLModel):
    url: str
    events: str = Field(default="*", description="comma list: entry.allowed, entry.denied, entry.unknown, or *")
    active: bool = True


class Webhook(WebhookBase, table=True):
    id: int | None = Field(default=None, primary_key=True)
    secret: str


def resident_status(session: Session, site_id: int, key: str) -> tuple[Status, int | None]:
    """allowed/denied from the site's resident list; unknown when the plate isn't registered."""
    r = session.exec(select(Resident).where(Resident.site_id == site_id, Resident.plate_key == key)).first()
    if not r:
        return Status.unknown, None
    return (Status.allowed if r.allowed else Status.denied), r.id
