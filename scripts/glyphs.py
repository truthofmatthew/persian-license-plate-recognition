"""Plate glyphs redrawn from real photos, for the Blender renderer (scripts/blender_synth.py --glyphs).

Fonts only look roughly like the plate typeface. This builds each symbol from real plate crops instead:
  1. grids   for every class, a few grid images of 24 real crops each (default 3 grids)
  2. redraw  sends each class's grids to Gemini (Nano Banana) and asks for one clean black-on-white glyph
  3. trace   turns each clean glyph into polygons (outline + holes) that Blender extrudes into 3D

Usage:
  python scripts/glyphs.py grids  --src /path/to/iranis --out data/glyphs   # <src>/<class>/*.jpg, IRANIS layout
  GEMINI_API_KEY=... python scripts/glyphs.py redraw --out data/glyphs [--model ...] [--only 4 Sad]
  python scripts/glyphs.py trace  --out data/glyphs                          # also writes data/glyphs/sheet.png

Look at data/glyphs/raw/*.png before tracing; delete a bad one and run redraw again to get a new one
(redraw skips classes that already have a raw image). Classes with no real crops keep using the font.
"""
import argparse
import base64
import json
import os
import sys
import urllib.request
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plpr.labels import CHAR_CLASSES, CODE_TO_PERSIAN

GRID_COLS, GRID_ROWS, CELL = 6, 4, (128, 160)  # 24 crops per grid, cell w x h
API = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_MODEL = "gemini-nano-banana-2.1"


def grids(src: Path, out: Path, per_class: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    (out / "grids").mkdir(parents=True, exist_ok=True)
    codes = {code for code, _ in CHAR_CLASSES}
    for d in sorted(p for p in src.iterdir() if p.is_dir()):
        if d.name not in codes:
            print(f"skip folder {d.name}: not a class in plpr/labels.py")
            continue
        files = sorted(f for f in d.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".bmp"})
        pick = rng.choice(len(files), min(len(files), per_class * GRID_COLS * GRID_ROWS), replace=False)
        for k in range(per_class):
            chunk = pick[k * GRID_COLS * GRID_ROWS:(k + 1) * GRID_COLS * GRID_ROWS]
            if len(chunk) == 0:
                break
            cells = [_cell(cv2.imread(str(files[i]), cv2.IMREAD_GRAYSCALE)) for i in chunk]
            cells += [np.full((CELL[1], CELL[0]), 255, np.uint8)] * (GRID_COLS * GRID_ROWS - len(cells))
            rows = [np.hstack(cells[r * GRID_COLS:(r + 1) * GRID_COLS]) for r in range(GRID_ROWS)]
            cv2.imwrite(str(out / "grids" / f"{d.name}_{k}.png"), np.vstack(rows))
        print(f"{d.name}: {len(files)} crops -> {min(per_class, -(-len(pick) // (GRID_COLS * GRID_ROWS)))} grids")


def _cell(img: np.ndarray) -> np.ndarray:
    """Fit one crop into a cell with a 4 px white gap, contrast stretched so all cells look alike."""
    w, h = CELL[0] - 8, CELL[1] - 8
    s = min(w / img.shape[1], h / img.shape[0])
    img = cv2.resize(img, (max(1, round(img.shape[1] * s)), max(1, round(img.shape[0] * s))), interpolation=cv2.INTER_CUBIC)
    img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX)
    cell = np.full((CELL[1], CELL[0]), 255, np.uint8)
    y, x = (CELL[1] - img.shape[0]) // 2, (CELL[0] - img.shape[1]) // 2
    cell[y:y + img.shape[0], x:x + img.shape[1]] = img
    return cell


def _prompt(code: str, n_grids: int) -> str:
    kind = "digit" if code.isdigit() else "letter"
    char = "۰۱۲۳۴۵۶۷۸۹"[int(code)] if code.isdigit() else CODE_TO_PERSIAN[code]
    return (
        f"The {n_grids} images are grids of real photos, 24 per grid, all showing the same Persian {kind} '{char}' "
        "cut from Iranian car license plates (blurry, dirty, tilted, different cameras). "
        "Draw this one character exactly once, as it is pressed into Iranian license plates: the same typeface, "
        "stroke weight, proportions and details as in the photos, not a generic font. "
        "Solid pure black on a pure white background, upright, centred, about 70% of the image height, "
        "crisp clean edges, no shading, texture, noise, border, plate, shadow or any other text."
    )


def _images(obj):
    """Every base64 image block anywhere in an API response."""
    if isinstance(obj, dict):
        if obj.get("type") == "image" and obj.get("data"):
            yield obj["data"]
        for v in obj.values():
            yield from _images(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _images(v)


def redraw(out: Path, model: str, only: list[str] | None) -> None:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("set GEMINI_API_KEY (Google AI Studio key) to redraw glyphs")
    (out / "raw").mkdir(parents=True, exist_ok=True)
    by_code: dict[str, list[Path]] = {}
    for g in sorted((out / "grids").glob("*.png")):
        by_code.setdefault(g.stem.rsplit("_", 1)[0], []).append(g)
    for code, files in by_code.items():
        target = out / "raw" / f"{code}.png"
        if (only and code not in only) or (target.exists() and not only):
            continue
        body = {
            "model": model,
            "input": [{"type": "image", "mime_type": "image/png", "data": base64.b64encode(f.read_bytes()).decode()} for f in files]
                     + [{"type": "text", "text": _prompt(code, len(files))}],
            "response_format": {"type": "image", "mime_type": "image/png", "aspect_ratio": "1:1", "image_size": "2K"},
        }
        req = urllib.request.Request(API, json.dumps(body).encode(), {"Content-Type": "application/json", "x-goog-api-key": key})
        with urllib.request.urlopen(req, timeout=300) as r:
            imgs = list(_images(json.load(r)))
        if not imgs:
            print(f"{code}: no image in the response")
            continue
        target.write_bytes(base64.b64decode(imgs[-1]))
        print(f"{code}: {target}")


def trace_glyph(img: np.ndarray) -> list[list[list[float]]]:
    """Black-on-white glyph image -> polygons (outlines and holes), y up, ink box height 1, x from 0.

    Blender fills 2D curves even-odd, so holes need no special marking.
    """
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, ink = cv2.threshold(cv2.GaussianBlur(gray, (5, 5), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(ink)
    keep = [i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] > 0.002 * ink.size]  # drop specks; keep dots of letters
    ink = np.isin(lab, keep).astype(np.uint8) * 255
    ys, xs = np.nonzero(ink)
    if len(xs) == 0:
        raise ValueError("no ink found")
    x0, y1, h = xs.min(), ys.max(), ys.max() - ys.min() + 1
    contours, _ = cv2.findContours(ink, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    polys = []
    for c in contours:
        c = cv2.approxPolyDP(c, 0.002 * h, True).reshape(-1, 2)
        if len(c) >= 3:
            polys.append([[round((x - x0) / h, 5), round((y1 - y) / h, 5)] for x, y in c])
    return polys


def trace(out: Path) -> None:
    (out / "shapes").mkdir(parents=True, exist_ok=True)
    tiles = []
    for f in sorted((out / "raw").glob("*.png")):
        polys = trace_glyph(cv2.imread(str(f)))
        (out / "shapes" / f"{f.stem}.json").write_text(json.dumps(polys))
        tile = np.full((220, 200), 255, np.uint8)  # draw the traced shape back for checking
        pts = [(np.array(p) * [150, -150] + [25, 185]).astype(np.int32) for p in polys]
        cv2.fillPoly(tile, pts, 0)  # fillPoly is even-odd too, like Blender
        cv2.putText(tile, f.stem, (5, 215), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 128, 1)
        tiles.append(tile)
        print(f"{f.stem}: {len(polys)} polygons, {sum(map(len, polys))} points")
    if tiles:
        tiles += [np.full_like(tiles[0], 255)] * (-len(tiles) % 8)
        cv2.imwrite(str(out / "sheet.png"), np.vstack([np.hstack(tiles[i:i + 8]) for i in range(0, len(tiles), 8)]))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["grids", "redraw", "trace"])
    ap.add_argument("--out", default="data/glyphs")
    ap.add_argument("--src", help="grids: folder with one sub-folder of crops per class (IRANIS layout)")
    ap.add_argument("--grids", type=int, default=3, help="grids: grids per class, 24 crops each")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--model", default=DEFAULT_MODEL, help="redraw: Gemini image model id, e.g. the Nano Banana Pro id")
    ap.add_argument("--only", nargs="*", help="redraw: just these class codes (overwrites their raw image)")
    a = ap.parse_args()
    out = ROOT / a.out
    if a.step == "grids":
        if not a.src:
            sys.exit("grids needs --src")
        grids(Path(a.src), out, a.grids, a.seed)
    elif a.step == "redraw":
        redraw(out, a.model, a.only)
    else:
        trace(out)


if __name__ == "__main__":
    main()
