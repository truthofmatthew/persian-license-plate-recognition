"""Synthetic training data from Blender: cars with embossed 3D plates, rendered from random cameras.

Usage:
  python scripts/blender_synth.py --n 500 --out data/blender             # render, then build datasets
  python scripts/blender_synth.py --out data/blender --post-only         # rebuild datasets with fresh noise
  python scripts/blender_synth.py --n 20 --out data/blender --preview 20 # also draw the boxes for a look

Steps:
 1. <out>/jobs.json: random valid plates (same templates, letters and slots as plpr/synth.py).
 2. Blender headless runs scripts/blender/render_plates.py -> <out>/renders/*.jpg and labels.jsonl.
    The boxes come from projecting the 3D plate and glyph geometry, so nothing is labelled by hand.
 3. Two YOLO datasets built from the renders, with plpr.synth.photometric noise on top:
    <out>/plates  whole frames, 1 class (the plate)          -> plate detector
    <out>/chars   plate crops, 43 classes (CHAR_CLASSES)     -> character model
Re-running with a larger --n keeps the earlier renders and only renders the new ones.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plpr import synth
from plpr.labels import CHAR_CLASSES
from scripts.make_dataset import write_data_yaml

BLENDER_SCRIPT = ROOT / "scripts" / "blender" / "render_plates.py"


def find_blender(given: str | None) -> str:
    for c in (given, os.environ.get("BLENDER"), "/Applications/Blender.app/Contents/MacOS/Blender", shutil.which("blender")):
        if c and Path(c).exists():
            return c
    sys.exit("Blender not found: install it or pass --blender /path/to/blender")


def make_jobs(n: int, seed: int, special: float, font: Path, shapes: Path | None = None) -> list[dict]:
    """One job per image. With shapes (scripts/glyphs.py output), a symbol uses its traced glyph when there is one, else the font."""
    rng = np.random.default_rng(seed)

    def glyph(code: str):
        f = shapes / f"{code}.json" if shapes else None
        if not (f and f.exists()):
            return synth.glyph_text(code)
        # shortcut: traced images carry no size, so the height relative to a digit comes from the font; measure real plates to refine.
        rel = min(1.1, synth._glyph(code)[0].shape[0] / synth._digit_height())
        return {"shape": str(f), "digit": code.isdigit(), "height": round(rel, 3)}
    jobs = []
    for i in range(n):
        template = synth._pick_template(rng, None, special)
        codes = synth.random_codes(rng, template)
        jobs.append({
            "id": i, "seed": seed * 1_000_003 + i, "key": "".join(codes), "plate_type": synth._plate_type(template, codes),
            "template": str(synth.TEMPLATE_DIR / f"template-{template}.png"), "font": str(font),
            "ink": [0.015] * 3 if template in synth.DARK_INK else [0.85] * 3,
            "glyphs": [glyph(c) for c in codes], "slots": synth.SLOTS, "classes": [synth.CLASS_INDEX[c] for c in codes],
        })
    return jobs


def render(blender: str, jobs: Path, renders: Path, res: list[int], samples: int, device: str, engine: str) -> None:
    cmd = [blender, "-b", "--factory-startup", "-P", str(BLENDER_SCRIPT), "--", "--jobs", str(jobs), "--out", str(renders),
           "--res", *map(str, res), "--samples", str(samples), "--device", device, "--engine", engine]
    subprocess.run(cmd, check=True)


def crop(img: np.ndarray, row: dict, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """Loose axis-aligned crop around the plate, like the plate detector hands the character model."""
    x1, y1, x2, y2 = row["plate"]
    w, h = x2 - x1, y2 - y1
    m = rng.uniform(0.0, 0.08, 4) * [w, h, w, h]
    cx1, cy1 = int(max(0, x1 - m[0])), int(max(0, y1 - m[1]))
    cx2, cy2 = int(min(img.shape[1], x2 + m[2])), int(min(img.shape[0], y2 + m[3]))
    boxes = np.array(row["chars"], np.float32) - [cx1, cy1, cx1, cy1]
    boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, cx2 - cx1)
    boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, cy2 - cy1)
    return img[cy1:cy2, cx1:cx2].copy(), boxes


def post(out: Path, seed: int, min_plate_w: int) -> None:
    rows = [json.loads(line) for line in (out / "renders" / "labels.jsonl").open(encoding="utf-8")]
    rng = np.random.default_rng(seed)
    counts = {"plates": 0, "chars": 0}
    for row in rows:
        img = cv2.imread(str(out / "renders" / row["image"]))
        split = "val" if row["id"] % 10 == 0 else "train"
        stem = Path(row["image"]).stem
        samples = [("plates", synth.photometric(img, rng), np.array([row["plate"]], np.float32), [0])]
        if row["plate"][2] - row["plate"][0] >= min_plate_w:  # tiny plates are useless for reading characters
            c, boxes = crop(img, row, rng)
            samples.append(("chars", synth.photometric(c, rng), boxes, row["classes"]))
        for kind, im, boxes, classes in samples:
            for sub in ("images", "labels"):
                (out / kind / sub / split).mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(out / kind / "images" / split / f"{stem}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 92])
            (out / kind / "labels" / split / f"{stem}.txt").write_text(synth.yolo_lines(boxes, classes, im.shape[1], im.shape[0]))
            counts[kind] += 1
    write_data_yaml(out / "plates", ["IR_License_Plate"])
    write_data_yaml(out / "chars", [code for code, _ in CHAR_CLASSES])
    print(f"{len(rows)} renders -> {counts['plates']} plate frames in {out / 'plates'}, {counts['chars']} crops in {out / 'chars'}")


def preview(out: Path, n: int) -> None:
    """Draw the plate outline and character boxes on the first n renders, for checking by eye."""
    (out / "preview").mkdir(exist_ok=True)
    names = [code for code, _ in CHAR_CLASSES]
    for line in list((out / "renders" / "labels.jsonl").open(encoding="utf-8"))[:n]:
        row = json.loads(line)
        img = cv2.imread(str(out / "renders" / row["image"]))
        cv2.polylines(img, [np.array(row["corners"], np.int32)], True, (0, 255, 255), 2)
        for (x1, y1, x2, y2), c in zip(row["chars"], row["classes"]):
            cv2.rectangle(img, (int(x1), int(y1)), (int(x2), int(y2)), (0, 0, 255), 1)
            cv2.putText(img, names[c], (int(x1), int(y1) - 3), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)
        cv2.imwrite(str(out / "preview" / row["image"]), img)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=100, help="number of images to render")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--special", type=float, default=0.3, help="share of non-private plate templates")
    ap.add_argument("--glyphs", help="folder of traced glyphs (scripts/glyphs.py trace -> <out>/shapes); symbols without one use --font")
    ap.add_argument("--font", default=str(synth.FONT), help="TTF for symbols with no traced glyph (default Vazirmatn Bold)")
    ap.add_argument("--res", type=int, nargs=2, default=[1280, 960])
    ap.add_argument("--samples", type=int, default=32, help="render samples per image")
    ap.add_argument("--device", choices=["GPU", "CPU"], default="GPU")
    ap.add_argument("--engine", choices=["cycles", "eevee"], default="cycles", help="eevee is about 3x faster, with flatter lighting")
    ap.add_argument("--blender", help="path to the Blender binary (or set $BLENDER)")
    ap.add_argument("--min-plate-w", type=int, default=60, help="smallest plate width in px that still makes a chars crop")
    ap.add_argument("--post-only", action="store_true", help="skip rendering; rebuild the datasets from existing renders")
    ap.add_argument("--preview", type=int, default=0, help="draw boxes on the first N renders into <out>/preview")
    args = ap.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    if not args.post_only:
        jobs = out / "jobs.json"
        shapes = (ROOT / args.glyphs).resolve() if args.glyphs else None
        if shapes:
            missing = [c for c, _ in CHAR_CLASSES if c != "PwD" and not (shapes / f"{c}.json").exists()]
            print(f"traced glyphs from {shapes}; font fallback for: {' '.join(missing) or 'none'}")
        jobs.write_text(json.dumps(make_jobs(args.n, args.seed, args.special, Path(args.font).resolve(), shapes), ensure_ascii=False), encoding="utf-8")
        render(find_blender(args.blender), jobs, out / "renders", args.res, args.samples, args.device, args.engine)
    post(out, args.seed, args.min_plate_w)
    if args.preview:
        preview(out, args.preview)


if __name__ == "__main__":
    main()
