"""Desktop app (home-yolo.py) helpers: SQLite layer and capture source selection."""
import sqlite3
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6", reason="desktop extra not installed: pip install -e .[desktop]")

from configParams import capture_source
from database import db_entries_utils as entries
from database import db_resident_utils as residents
from database.classEntries import Entries
from database.classResidents import Resident

EVIL = "12B345' OR '1'='1"


@pytest.fixture
def dbs(tmp_path, monkeypatch):
    monkeypatch.setattr(entries, "dbEntries", str(tmp_path / "entries.db"))
    monkeypatch.setattr(residents, "dbResidents", str(tmp_path / "residents.db"))
    return tmp_path


def tables(path):
    with sqlite3.connect(path) as con:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_tables_created_on_fresh_files(dbs):
    assert entries.dbGetAllEntries() == []
    assert residents.dbGetAllResidents() == []
    assert tables(dbs / "entries.db") == {"entries"}
    assert tables(dbs / "residents.db") == {"residents"}


def test_injection_strings_are_just_data(dbs):
    residents.insertResident(Resident("Resident", "A", 1, 2, 3, "Car", "34D31966", 1))
    entries.insertEntries(Entries(80, 90, "2026-01-01", "10:00:00", "34D31966", 1))

    assert residents.db_get_plate_status(EVIL) == 2  # unknown plate, not "every row"
    assert residents.db_get_plate_owner_name(EVIL) is None
    assert residents.dbGetPlateExist(EVIL) is False
    assert residents.dbGetResidentDatasByPlate(EVIL) is None
    assert residents.dbGetAllResidents(whereLike=EVIL) == []
    assert entries.dbGetAllEntries(whereLike=EVIL) == []
    assert entries.dbGetPlateLatestEntry(EVIL) is None

    residents.dbRemoveResident(EVIL)
    entries.dbRemoveEntries(EVIL)
    assert residents.db_get_plate_owner_name("34D31966") == "Resident A"
    assert [e.plateNum for e in entries.dbGetAllEntries(whereLike="34D")] == ["34D31966"]

    residents.insertResident(Resident("Resident", "B", 1, 2, 3, "Car", EVIL, 0))
    assert residents.db_get_plate_status(EVIL) == 0  # stored and read back verbatim


def test_order_by_whitelist(dbs):
    assert entries.dbGetAllEntries(orderBy="plateNum", orderType="asc") == []
    for bad in [("eDate; DROP TABLE entries", "DESC"), ("eDate", "DESC; --"), ("nope", "ASC")]:
        with pytest.raises(ValueError):
            entries.dbGetAllEntries(orderBy=bad[0], orderType=bad[1])
        with pytest.raises(ValueError):
            residents.dbGetAllResidents(orderBy=bad[0], orderType=bad[1])
    assert tables(dbs / "entries.db") == {"entries"}


@pytest.mark.parametrize("source, expected", [("webcam", 0), ("video", "clip.mp4"), ("rtsp", "rtsp://cam/1"), ("rtps", "rtsp://cam/1")])
def test_capture_source(source, expected):
    p = SimpleNamespace(source=source, webcam="0", video="clip.mp4", rtsp="rtsp://cam/1")
    assert capture_source(p) == expected


def test_capture_source_rejects_unknown():
    with pytest.raises(ValueError):
        capture_source(SimpleNamespace(source="usb", webcam="0", video="", rtsp=""))
