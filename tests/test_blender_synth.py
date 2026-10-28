import json
import os

import cv2
import numpy as np
import pytest

from scripts import blender_synth, glyphs


def test_trace_keeps_holes_and_normalises_height():
    img = np.full((400, 400), 255, np.uint8)
    cv2.circle(img, (200, 200), 120, 0, -1)
    cv2.circle(img, (200, 200), 50, 255, -1)  # a ring: outline + hole
    polys = glyphs.trace_glyph(img)
    assert len(polys) == 2
    pts = np.concatenate([np.array(p) for p in polys])
    assert pts[:, 0].min() == 0 and pts[:, 1].min() == pytest.approx(0, abs=1e-3)
    assert pts[:, 1].max() == pytest.approx(1, abs=0.01) and pts[:, 0].max() == pytest.approx(1, abs=0.02)


def test_grids_tile_24_crops_per_image(tmp_path):
    rng = np.random.default_rng(0)
    (tmp_path / "src" / "4").mkdir(parents=True)
    (tmp_path / "src" / "not_a_class").mkdir()
    for i in range(30):
        cv2.imwrite(str(tmp_path / "src" / "4" / f"{i}.jpg"), rng.integers(0, 255, (40, 30), np.uint8))
    glyphs.grids(tmp_path / "src", tmp_path / "out", per_class=3, seed=0)
    out = sorted(p.name for p in (tmp_path / "out" / "grids").iterdir())
    assert out == ["4_0.png", "4_1.png"]  # 30 crops fill one grid and part of a second
    g = cv2.imread(str(tmp_path / "out" / "grids" / "4_0.png"))
    assert g.shape[:2] == (glyphs.GRID_ROWS * glyphs.CELL[1], glyphs.GRID_COLS * glyphs.CELL[0])


def test_jobs_use_traced_glyphs_where_present(tmp_path):
    (tmp_path / "4.json").write_text("[]")
    jobs = blender_synth.make_jobs(30, 0, 0.3, tmp_path / "font.ttf", tmp_path)
    for job in jobs:
        assert len(job["glyphs"]) == len(job["slots"]) == len(job["classes"]) == 8
        for g in job["glyphs"]:
            if isinstance(g, dict):
                assert g["shape"].endswith("4.json") and g["digit"] and 0.5 < g["height"] <= 1.1
    assert any(isinstance(g, dict) for j in jobs for g in j["glyphs"])
    assert any(isinstance(g, str) for j in jobs for g in j["glyphs"])


def test_crop_shifts_char_boxes_into_the_crop():
    img = np.zeros((480, 640, 3), np.uint8)
    row = {"plate": [100, 200, 300, 244], "chars": [[110 + 20 * i, 210, 125 + 20 * i, 240] for i in range(8)]}
    c, boxes = blender_synth.crop(img, row, np.random.default_rng(0))
    assert (boxes >= 0).all() and (boxes[:, [0, 2]] <= c.shape[1]).all() and (boxes[:, [1, 3]] <= c.shape[0]).all()
    assert boxes[:, 2].max() - boxes[:, 0].min() == pytest.approx(155, abs=1e-3)


@pytest.mark.skipif(not os.environ.get("PLPR_TEST_BLENDER"), reason="set PLPR_TEST_BLENDER=1 to render with Blender (about 20 s)")
def test_blender_renders_one_labelled_image(tmp_path):
    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps(blender_synth.make_jobs(1, 0, 0.3, blender_synth.synth.FONT), ensure_ascii=False), encoding="utf-8")
    blender_synth.render(blender_synth.find_blender(None), jobs, tmp_path / "r", [320, 240], 4, "GPU", "cycles")
    row = json.loads((tmp_path / "r" / "labels.jsonl").read_text(encoding="utf-8"))
    x1, y1, x2, y2 = row["plate"]
    assert 0 <= x1 < x2 <= 320 and 0 <= y1 < y2 <= 240
    assert all(x1 - 2 <= a and c <= x2 + 2 for a, _, c, _ in row["chars"])  # glyphs sit on the plate
