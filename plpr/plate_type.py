"""Plate type from the plate body colour (HSV), refined by the letter code when it is known.

Colours come from Templates/*.png: white private, yellow public/taxi, red government, dark green
police, khaki/blue military, light blue diplomatic/service, white with a split right box free zone.
"""
from __future__ import annotations

import cv2
import numpy as np

TYPES = ("private", "taxi", "public", "government", "police", "military", "diplomatic", "free_zone", "disabled", "unknown")


def _split_right_box(crop_bgr: np.ndarray) -> bool:
    """Free-zone/transit plates have a horizontal rule across the right box instead of "ایران"."""
    h, w = crop_bgr.shape[:2]
    box = cv2.cvtColor(crop_bgr[int(h * 0.15):int(h * 0.85), int(w * 0.79):int(w * 0.96)], cv2.COLOR_BGR2GRAY)
    if box.size == 0:
        return False
    dark = box < (0.6 * np.median(box))
    rows = dark.mean(1)
    mid = rows[int(len(rows) * 0.3):int(len(rows) * 0.7)]
    return bool(mid.size and mid.max() > 0.85)


def classify_plate_type(crop_bgr: np.ndarray, letter: str | None = None) -> str:
    """One of TYPES for a plate crop (BGR). ``letter`` is the Latin code from the reader, if any."""
    if letter == "PwD":
        return "disabled"
    h, w = crop_bgr.shape[:2]
    if h < 4 or w < 8:
        return "unknown"
    body = cv2.cvtColor(crop_bgr[int(h * 0.12):int(h * 0.88), int(w * 0.14):int(w * 0.76)], cv2.COLOR_BGR2HSV).reshape(-1, 3)
    # Characters cover under half the body, so the median pixel is background.
    hue, sat, val = (float(np.median(body[:, i])) for i in range(3))
    colored = body[body[:, 1] > 80]
    if len(colored) > len(body) / 2:  # hue median over saturated pixels only (hue is noise on grey)
        hue = float(np.median(colored[:, 0]))
    if sat < 60 and val > 90:  # white
        return "free_zone" if _split_right_box(crop_bgr) else "private"
    if 35 <= hue <= 95 and val < 110 and sat > 80:  # dark green
        return "police" if letter in (None, "P") else "military"
    if sat < 60:
        return "unknown"
    if hue < 8 or hue > 165:
        return "government"
    if 8 <= hue <= 22 and sat < 150:  # khaki (artesh)
        return "military"
    if 15 <= hue <= 35:
        return "taxi" if letter == "Taxi" else "public"
    if 95 <= hue < 104:
        return "diplomatic"
    if 104 <= hue <= 130:  # dark blue (defa, armed forces)
        return "military"
    return "unknown"
