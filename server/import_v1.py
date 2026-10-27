"""Import a v1 desktop database (residents.db / entries.db) into the v2 server schema.

    python -m server.import_v1 --residents database/residents.db --entries database/entries.db

Safe to run twice: residents are upserted by plate, entries get a stable event id.
v1 stored local wall-clock times; --tz says which zone they were in (default Asia/Tehran).
v1 status codes: 0 = denied, 1 = allowed, 2 = unknown (not a resident).
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import MetaData, Table, create_engine
from sqlalchemy import select as sa_select
from sqlmodel import Session, SQLModel, select

from plpr import PlateNumber

from .models import Entry, Gate, Resident, Site, Status, to_utc

V1_STATUS = {0: Status.denied, 1: Status.allowed, 2: Status.unknown}


def v1_rows(path: Path, table: str) -> list[dict]:
    engine = create_engine(f"sqlite:///{path}")
    t = Table(table, MetaData(), autoload_with=engine)
    with engine.connect() as c:
        return [dict(r._mapping) for r in c.execute(sa_select(t))]


def import_v1(session: Session, residents_db: Path | None, entries_db: Path | None,
              site_id: int | None = None, gate_id: int | None = None, tz: str = "Asia/Tehran") -> dict:
    if site_id is None:
        site = Site(name="v1 import")
        session.add(site)
        session.flush()
        site_id = site.id
    if gate_id is None:
        gate = Gate(site_id=site_id, name="v1 gate")
        session.add(gate)
        session.flush()
        gate_id = gate.id
    report = {"site_id": site_id, "gate_id": gate_id, "residents": 0, "entries": 0, "skipped": []}

    for row in v1_rows(residents_db, "residents") if residents_db else []:
        plate = PlateNumber.from_key(str(row["plateNum"] or ""))
        if not plate:
            report["skipped"].append(f"resident {row['plateNum']!r}")
            continue
        fields = {
            "name": f"{row['fName'] or ''} {row['lName'] or ''}".strip(),
            "unit": "-".join(str(row[k]) for k in ("building", "block", "num") if row[k] is not None),
            "car_model": row["carModel"] or "",
            "allowed": row["status"] != 0,
        }
        r = session.exec(select(Resident).where(Resident.site_id == site_id, Resident.plate_key == plate.key)).first()
        if r:
            r.sqlmodel_update(fields)
        else:
            r = Resident(site_id=site_id, plate_key=plate.key, **fields)
        session.add(r)
        report["residents"] += 1
    session.flush()

    zone = ZoneInfo(tz)
    for row in v1_rows(entries_db, "entries") if entries_db else []:
        plate = PlateNumber.from_key(str(row["plateNum"] or ""))
        try:
            when = datetime.strptime(f"{row['eDate']} {row['eTime']}", "%Y-%m-%d %H:%M:%S").replace(tzinfo=zone)
        except (TypeError, ValueError):
            when = None
        if not plate or not when:
            report["skipped"].append(f"entry {row['plateNum']!r} {row['eDate']} {row['eTime']}")
            continue
        event_id = f"v1-{plate.key}-{row['eDate']}T{row['eTime']}"
        if session.exec(select(Entry).where(Entry.event_id == event_id)).first():
            continue
        resident = session.exec(select(Resident).where(Resident.site_id == site_id, Resident.plate_key == plate.key)).first()
        session.add(Entry(
            event_id=event_id, gate_id=gate_id, plate_key=plate.key, persian=plate.persian, plate_type=plate.plate_type,
            plate_conf=(row["platePercent"] or 0) / 100, char_conf=(row["charPercent"] or 0) / 100,
            status=V1_STATUS.get(row["status"], Status.unknown), resident_id=resident and resident.id,
            created_at=to_utc(when), reviewed=True,
        ))
        report["entries"] += 1
    session.commit()
    return report


def main(argv: list[str] | None = None) -> None:
    from .settings import Settings

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--residents", type=Path, help="v1 residents.db")
    ap.add_argument("--entries", type=Path, help="v1 entries.db")
    ap.add_argument("--database-url", default=Settings().database_url, help="target (default: PLPR_DATABASE_URL)")
    ap.add_argument("--site-id", type=int, help="existing site; a new one is created when omitted")
    ap.add_argument("--gate-id", type=int, help="existing gate for the entries; a new one is created when omitted")
    ap.add_argument("--tz", default="Asia/Tehran", help="time zone of v1 eDate/eTime")
    args = ap.parse_args(argv)
    if not (args.residents or args.entries):
        ap.error("give --residents and/or --entries")
    if args.database_url.startswith("sqlite:///"):
        Path(args.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(args.database_url)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        report = import_v1(session, args.residents, args.entries, args.site_id, args.gate_id, args.tz)
    skipped = report.pop("skipped")
    print(report, f"skipped={len(skipped)}", *skipped[:20], sep="\n")


if __name__ == "__main__":
    main()
