from pathlib import Path

import cv2
import numpy as np
import pytest

from plpr import synth
from plpr.plate_type import TYPES, classify_plate_type

FIX = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("template", list(synth.TEMPLATE_TYPE))
def test_template_colours(template):
    rng = np.random.default_rng(0)
    for _ in range(5):
        s = synth.make_crop(rng, template, augment=False)
        assert classify_plate_type(s.image, s.key[2:-5]) == s.plate_type


def test_letter_overrides():
    s = synth.make_crop(np.random.default_rng(0), "base", augment=False)
    assert classify_plate_type(s.image, "PwD") == "disabled"
    y = synth.make_crop(np.random.default_rng(0), "ommomi", augment=False)
    assert classify_plate_type(y.image, "Taxi") == "taxi" and classify_plate_type(y.image, "PuV") == "public"


def test_real_plates_are_private_and_tiny_is_unknown():
    for f in FIX.glob("plate_*.jpg"):
        assert classify_plate_type(cv2.imread(str(f))) == "private"
    assert classify_plate_type(np.zeros((2, 2, 3), np.uint8)) == "unknown"
    assert set(TYPES) >= set(synth.TEMPLATE_TYPE.values()) | {"taxi"}
