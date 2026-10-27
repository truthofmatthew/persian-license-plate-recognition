"""Synthetic Persian plates: render random valid plates on Templates/*.png with per-character boxes.

Boxes use the 43-class scheme of plpr.labels.CHAR_CLASSES, so samples train the character model
directly; scene samples paste a warped plate on a background and carry the plate box instead.
Needs Pillow (already a core dependency). Everything random goes through one numpy Generator,
so a seed gives the same images on the same library versions.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .labels import CHAR_CLASSES, CODE_TO_PERSIAN, FA_DIGITS, VALID_LETTERS

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "Templates"
FONT = ROOT / "vazir.ttf"
BG_DIR = ROOT / "yolov5" / "data" / "images"

CLASS_INDEX = {code: i for i, (code, _) in enumerate(CHAR_CLASSES)}

# template file stem -> plate type it shows (see plpr.plate_type)
TEMPLATE_TYPE = {
    "base": "private", "ommomi": "public", "dolati": "government", "tashrifat": "government",
    "police": "police", "sepah": "military", "artesh": "military", "defa": "military",
    "Niromosalah": "military", "diplomat": "diplomatic", "service": "diplomatic", "gozar": "free_zone",
}
DARK_INK = {"base", "ommomi", "artesh", "gozar"}  # black characters; the rest use white
# PwD plates show a wheelchair, not a letter, so the generator does not draw them.
LETTERS = sorted(VALID_LETTERS - {"PwD"})
# shortcut: letter pools per template are approximate (real series rules are not encoded), refine with real data.
TEMPLATE_LETTERS = {"ommomi": ["Taxi", "PuV", "Sin"], "police": ["P"], "dolati": ["A"], "sepah": [c for c in LETTERS if c != "P"]}
# Multi-glyph letters drawn with presentation forms in visual (left-to-right) order: Pillow here has no raqm shaping.
GLYPH = {"A": "ﻒﻟا", "H": "ﻫ"}

# Slot geometry on the 600x132 templates: (x, width) per symbol, shared baseline and height.
BODY_SLOTS = [(68, 55), (128, 55), (190, 76), (272, 55), (333, 55), (394, 55)]
REGION_SLOTS = [(474, 50), (530, 50)]
BODY_Y, BODY_H = 112, 82        # baseline y and height of a full-height digit
REGION_Y, REGION_H = 120, 66


@dataclass
class Sample:
    image: np.ndarray            # BGR uint8
    key: str                     # e.g. "34D31966"
    plate_type: str
    template: str
    boxes: np.ndarray            # (N, 4) x1, y1, x2, y2 in image pixels
    classes: list[int]           # char class per box (crops) or [0] (scenes)


@cache
def _template(name: str) -> np.ndarray:
    return cv2.imread(str(TEMPLATE_DIR / f"template-{name}.png"), cv2.IMREAD_UNCHANGED)


@cache
def _glyph(code: str) -> tuple[np.ndarray, int]:
    """Ink mask of one symbol at a fixed font size, and its top offset from the baseline."""
    text = GLYPH.get(code, CODE_TO_PERSIAN[code] if not code.isdigit() else FA_DIGITS[int(code)])
    font = ImageFont.truetype(str(FONT), 120)
    im = Image.new("L", (400, 300))
    ImageDraw.Draw(im).text((50, 200), text, font=font, fill=255, anchor="ls")
    m = np.asarray(im)
    ys, xs = np.nonzero(m > 40)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1], int(ys.min()) - 200


@cache
def _digit_height() -> int:
    return max(-_glyph(str(d))[1] for d in range(10))


def _backgrounds() -> list[Path]:
    return sorted(BG_DIR.glob("*.jpg"))


def random_codes(rng: np.random.Generator, template: str = "base") -> list[str]:
    letter = str(rng.choice(TEMPLATE_LETTERS.get(template, LETTERS)))
    d = [str(x) for x in rng.integers(0, 10, 7)]
    d[0] = str(rng.integers(1, 10))  # plates do not start with 0
    d[5] = str(rng.integers(1, 10))  # region codes run 10..99
    return d[:2] + [letter] + d[2:]


def render_plate(codes: list[str], template: str = "base", rng: np.random.Generator | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Clean 600x132 BGRA plate with the 8 symbols drawn; returns (image, boxes)."""
    rng = rng or np.random.default_rng()
    img = _template(template).copy()
    ink = np.array((20, 20, 20) if template in DARK_INK else (245, 245, 245), np.float32)
    boxes = []
    slots = [(s, BODY_Y, BODY_H) for s in BODY_SLOTS[:2]] + [(BODY_SLOTS[2], BODY_Y, BODY_H)] + \
            [(s, BODY_Y, BODY_H) for s in BODY_SLOTS[3:]] + [(s, REGION_Y, REGION_H) for s in REGION_SLOTS]
    jitter = rng.uniform(-3, 3, (8, 2))
    for code, ((x, w), base_y, h), (jx, jy) in zip(codes, slots, jitter):
        mask, top = _glyph(code)
        s = h / _digit_height()
        gh, gw = max(1, round(mask.shape[0] * s)), max(1, round(mask.shape[1] * s * 0.95))
        gw = min(gw, w)  # wide letters squeeze into their slot
        if not code.isdigit():
            gh = min(gh, round(h * 1.1))
        m = cv2.resize(mask, (gw, gh), interpolation=cv2.INTER_AREA).astype(np.float32)[..., None] / 255
        x0 = int(x + (w - gw) / 2 + jx)
        y0 = int(np.clip(base_y + top * s + jy, 2, 130 - gh))
        roi = img[y0:y0 + gh, x0:x0 + gw, :3].astype(np.float32)
        img[y0:y0 + gh, x0:x0 + gw, :3] = (roi * (1 - m) + ink * m).astype(np.uint8)
        boxes.append((x0, y0, x0 + gw, y0 + gh))
    return img, np.array(boxes, np.float32)


def _warp(img: np.ndarray, boxes: np.ndarray, H: np.ndarray, size: tuple[int, int], border=cv2.BORDER_REPLICATE) -> tuple[np.ndarray, np.ndarray]:
    out = cv2.warpPerspective(img, H, size, flags=cv2.INTER_LINEAR, borderMode=border)
    c = np.stack([boxes[:, [0, 1]], boxes[:, [2, 1]], boxes[:, [2, 3]], boxes[:, [0, 3]]], 1).reshape(-1, 1, 2)
    c = cv2.perspectiveTransform(c.astype(np.float32), H).reshape(-1, 4, 2)
    nb = np.concatenate([c.min(1), c.max(1)], 1)
    nb[:, [0, 2]] = nb[:, [0, 2]].clip(0, size[0])
    nb[:, [1, 3]] = nb[:, [1, 3]].clip(0, size[1])
    return out, nb


def photometric(img: np.ndarray, rng: np.random.Generator, strength: float = 1.0) -> np.ndarray:
    """Blur, noise, brightness/contrast, glare, night darkening and JPEG artifacts."""
    f = img.astype(np.float32)
    h, w = f.shape[:2]
    if rng.random() < 0.6 * strength:  # brightness / contrast
        f = (f - 128) * rng.uniform(0.6, 1.3) + 128 + rng.uniform(-50, 40)
    if rng.random() < 0.2 * strength:  # glare: soft bright blob
        cx, cy, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(0.1, 0.4) * w
        yy, xx = np.mgrid[:h, :w]
        f += (rng.uniform(80, 200) * np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r * r)))[..., None]
    if rng.random() < 0.15 * strength:  # night: darker, blue tint, more noise
        f = 255 * (np.clip(f, 0, 255) / 255) ** rng.uniform(1.6, 2.6) * np.array([1.1, 0.9, 0.8])
        f += rng.normal(0, 8, f.shape)
    if rng.random() < 0.5 * strength:  # blur: gaussian or horizontal motion
        if rng.random() < 0.5:
            f = cv2.GaussianBlur(f, (0, 0), rng.uniform(0.5, 1.8))
        else:
            k = int(rng.integers(3, 9))
            f = cv2.filter2D(f, -1, np.full((1, k), 1 / k, np.float32))
    if rng.random() < 0.5 * strength:
        f += rng.normal(0, rng.uniform(2, 12), f.shape)
    out = np.clip(f, 0, 255).astype(np.uint8)
    if rng.random() < 0.6 * strength:
        _, enc = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, int(rng.integers(20, 90))])
        out = cv2.imdecode(enc, cv2.IMREAD_COLOR)
    return out


def _pick_template(rng: np.random.Generator, template: str | None, special: float) -> str:
    if template:
        return template
    return str(rng.choice([t for t in TEMPLATE_TYPE if t != "base"])) if rng.random() < special else "base"


def _plate_type(template: str, codes: list[str]) -> str:
    return "taxi" if template == "ommomi" and codes[2] == "Taxi" else TEMPLATE_TYPE[template]


def make_crop(rng: np.random.Generator, template: str | None = None, augment: bool = True, special: float = 0.3) -> Sample:
    """A plate crop like the plate detector would hand to the character model."""
    template = _pick_template(rng, template, special)
    codes = random_codes(rng, template)
    plate, boxes = render_plate(codes, template, rng)
    a = plate[:, :, 3:].astype(np.float32) / 255  # rounded corners -> random surround colour
    img = (plate[:, :, :3] * a + rng.uniform(40, 200, 3) * (1 - a)).astype(np.uint8)
    if augment:
        w_out = int(rng.uniform(160, 600))
        h_out = int(w_out * 132 / 600 * rng.uniform(0.95, 1.15))
        src = np.float32([[0, 0], [600, 0], [600, 132], [0, 132]])
        j = rng.uniform(-0.05, 0.05, (4, 2)) * [w_out, h_out]  # loose crop + perspective
        dst = np.float32([[0, 0], [w_out, 0], [w_out, h_out], [0, h_out]]) + j
        img, boxes = _warp(img, boxes, cv2.getPerspectiveTransform(src, dst.astype(np.float32)), (w_out, h_out))
        img = photometric(img, rng)
    return Sample(img, "".join(codes), _plate_type(template, codes), template, boxes, [CLASS_INDEX[c] for c in codes])


def _background(rng: np.random.Generator, size: int) -> np.ndarray:
    bgs = _backgrounds()
    kind = rng.integers(0, 3 if bgs else 2)
    if kind == 0:  # smooth noise
        small = rng.integers(0, 256, (8, 8, 3)).astype(np.uint8)
        return cv2.resize(small, (size, size), interpolation=cv2.INTER_CUBIC)
    if kind == 1:  # linear gradient
        a, b = rng.uniform(0, 255, 3), rng.uniform(0, 255, 3)
        t = np.linspace(0, 1, size)[:, None, None]
        g = (a * (1 - t) + b * t).astype(np.uint8)
        return np.ascontiguousarray(np.broadcast_to(g, (size, size, 3)))
    im = cv2.imread(str(bgs[int(rng.integers(len(bgs)))]))
    s = size / min(im.shape[:2]) * rng.uniform(1, 2)
    im = cv2.resize(im, None, fx=s, fy=s)
    y, x = int(rng.integers(0, im.shape[0] - size + 1)), int(rng.integers(0, im.shape[1] - size + 1))
    return im[y:y + size, x:x + size].copy()


def make_scene(rng: np.random.Generator, size: int = 640, template: str | None = None, special: float = 0.3) -> Sample:
    """A square scene with one warped plate; boxes holds the plate box (class 0)."""
    template = _pick_template(rng, template, special)
    codes = random_codes(rng, template)
    plate, _ = render_plate(codes, template, rng)
    bg = _background(rng, size).astype(np.float32)
    pw = rng.uniform(0.12, 0.45) * size
    ph = pw * 132 / 600
    cx, cy = rng.uniform(pw / 2 + 5, size - pw / 2 - 5), rng.uniform(ph / 2 + 5, size - ph / 2 - 5)
    dst = np.float32([[cx - pw / 2, cy - ph / 2], [cx + pw / 2, cy - ph / 2], [cx + pw / 2, cy + ph / 2], [cx - pw / 2, cy + ph / 2]])
    dst += rng.uniform(-0.08, 0.08, (4, 2)) * [pw, ph * 2]
    H = cv2.getPerspectiveTransform(np.float32([[0, 0], [600, 0], [600, 132], [0, 132]]), dst.astype(np.float32))
    warped, pbox = _warp(plate, np.array([[0, 0, 600, 132]], np.float32), H, (size, size), cv2.BORDER_CONSTANT)
    a = warped[:, :, 3:].astype(np.float32) / 255
    img = photometric((warped[:, :, :3] * a + bg * (1 - a)).astype(np.uint8), rng)
    return Sample(img, "".join(codes), _plate_type(template, codes), template, pbox, [0])


def yolo_lines(boxes: np.ndarray, classes: list[int], w: int, h: int) -> str:
    """YOLO label text: one 'cls cx cy w h' line per box, normalised to [0, 1]."""
    rows = []
    for (x1, y1, x2, y2), c in zip(boxes, classes):
        rows.append(f"{c} {(x1 + x2) / 2 / w:.6f} {(y1 + y2) / 2 / h:.6f} {(x2 - x1) / w:.6f} {(y2 - y1) / h:.6f}")
    return "\n".join(rows) + "\n"
