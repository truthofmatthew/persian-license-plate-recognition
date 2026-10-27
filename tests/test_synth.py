import numpy as np
import pytest

from plpr import PlateNumber, synth
from plpr.labels import CHAR_CLASSES


@pytest.mark.parametrize("template", list(synth.TEMPLATE_TYPE))
def test_crop_has_8_boxes_inside_and_valid_key(template):
    for seed in range(5):
        s = synth.make_crop(np.random.default_rng(seed), template)
        h, w = s.image.shape[:2]
        assert s.boxes.shape == (8, 4) and len(s.classes) == 8
        assert (s.boxes[:, [0, 2]] >= 0).all() and (s.boxes[:, [0, 2]] <= w).all()
        assert (s.boxes[:, [1, 3]] >= 0).all() and (s.boxes[:, [1, 3]] <= h).all()
        assert (s.boxes[:, 2] > s.boxes[:, 0]).all() and (s.boxes[:, 3] > s.boxes[:, 1]).all()
        p = PlateNumber.from_key(s.key)
        assert p and p.valid and p.key == s.key
        assert "".join(CHAR_CLASSES[c][0] for c in s.classes) == s.key


def test_boxes_left_to_right():
    s = synth.make_crop(np.random.default_rng(0), "base", augment=False)
    assert (np.diff(s.boxes[:, 0]) > 0).all()


def test_deterministic_with_seed():
    a = synth.make_crop(np.random.default_rng(42))
    b = synth.make_crop(np.random.default_rng(42))
    assert a.key == b.key and np.array_equal(a.image, b.image) and np.array_equal(a.boxes, b.boxes)
    sa, sb = synth.make_scene(np.random.default_rng(7)), synth.make_scene(np.random.default_rng(7))
    assert sa.key == sb.key and np.array_equal(sa.image, sb.image)


def test_scene_plate_box_inside():
    s = synth.make_scene(np.random.default_rng(3), size=320)
    x1, y1, x2, y2 = s.boxes[0]
    assert s.image.shape == (320, 320, 3) and 0 <= x1 < x2 <= 320 and 0 <= y1 < y2 <= 320 and s.classes == [0]


def test_yolo_lines_normalised():
    s = synth.make_crop(np.random.default_rng(1))
    rows = [list(map(float, r.split())) for r in synth.yolo_lines(s.boxes, s.classes, *s.image.shape[1::-1]).splitlines()]
    assert len(rows) == 8 and all(0 <= v <= 1 for r in rows for v in r[1:])
