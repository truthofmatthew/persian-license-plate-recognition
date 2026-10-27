from pathlib import Path

import cv2
import pytest

from plpr import PlateNumber, PlateTracker, parse_codes
from plpr.engine import DEFAULT_MODEL_DIR, PlateRead

FIX = Path(__file__).parent / "fixtures"


def test_parse_and_key_roundtrip():
    p = parse_codes(list("34D31966"[:2]) + ["D"] + list("31966"))
    assert p and p.key == "34D31966" and p.valid
    assert PlateNumber.from_key("۳۴D۳۱۹-۶۶") == p
    assert parse_codes(["Sin", "4", "D", "3", "1", "9", "6", "6"]) is None
    assert parse_codes(list("3412")) is None
    assert "ایران" in p.persian and p.plate_type == "private"


def test_tracker_votes_and_emits_once():
    good = list("12") + ["B"] + list("34567")
    noisy = list("12") + ["B"] + list("34561")
    t = PlateTracker(min_hits=3)
    out = []
    for codes, conf in [(good, 0.9), (noisy, 0.4), (good, 0.8), (good, 0.9)]:
        out += t.update([PlateRead((10, 10, 110, 40), 0.8, codes, [conf] * 8, parse_codes(codes))])
    assert [tr.best.key for tr in out] == ["12B34567"]


def test_tracker_flush_finishes_pending_track_once():
    codes = list("12") + ["B"] + list("34567")
    t = PlateTracker(min_hits=3)
    assert t.update([PlateRead((10, 10, 110, 40), 0.8, codes, [0.9] * 8, parse_codes(codes))]) == []
    assert [tr.best.key for tr in t.flush()] == ["12B34567"]
    assert t.flush() == [] and t.tracks == []


@pytest.mark.skipif(not (DEFAULT_MODEL_DIR / "plate.onnx").exists(), reason="run scripts/export_onnx.py first")
@pytest.mark.parametrize("name", ["34D31966", "87Y16111"])
def test_engine_reads_real_plates(name):
    from plpr import Engine

    img = cv2.imread(str(FIX / f"plate_{name}.jpg"))
    eng = Engine()
    assert eng.read_crop(img).text == name
    scene = cv2.copyMakeBorder(img, 300, 300, 300, 300, cv2.BORDER_CONSTANT, value=(90, 90, 90))
    assert [r.text for r in eng.read(scene)] == [name]
