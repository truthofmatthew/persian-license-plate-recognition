"""Write YOLO-format synthetic datasets for the character model and the plate detector.

Usage:
  python scripts/make_dataset.py --kind chars --n 2000 --out data/synth_chars
  python scripts/make_dataset.py --kind plates --n 1000 --out data/synth_plates
  python scripts/make_dataset.py --kind bench --n 500 --scenes 200 --out data/bench   # frozen eval set

chars/plates: <out>/images/{train,val}/*.jpg, <out>/labels/{train,val}/*.txt, <out>/data.yaml.
bench: <out>/crops/plate_<KEY>_<i>.jpg, <out>/scenes/plate_<KEY>_<i>.jpg and <out>/labels.csv (path,key,type[,x1,y1,x2,y2] plate box for scenes),
the input format of scripts/eval.py.
"""
import argparse
import csv
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plpr import synth
from plpr.labels import CHAR_CLASSES


def write_yolo(out: Path, kind: str, n: int, val: float, seed: int) -> None:
    rng = np.random.default_rng(seed)
    names = [code for code, _ in CHAR_CLASSES] if kind == "chars" else ["IR_License_Plate"]
    n_val = int(n * val)
    for i in range(n):
        split = "val" if i < n_val else "train"
        s = synth.make_crop(rng) if kind == "chars" else synth.make_scene(rng)
        (out / "images" / split).mkdir(parents=True, exist_ok=True)
        (out / "labels" / split).mkdir(parents=True, exist_ok=True)
        stem = f"{i:06d}"
        cv2.imwrite(str(out / "images" / split / f"{stem}.jpg"), s.image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        h, w = s.image.shape[:2]
        (out / "labels" / split / f"{stem}.txt").write_text(synth.yolo_lines(s.boxes, s.classes, w, h))
    lines = [f"path: {out.resolve()}", "train: images/train", "val: images/val", f"nc: {len(names)}", "names:"]
    lines += [f"  {i}: {name!r}" for i, name in enumerate(names)]
    (out / "data.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{kind}: {n - n_val} train + {n_val} val -> {out}")


def write_bench(out: Path, n: int, scenes: int, seed: int) -> None:
    rng = np.random.default_rng(seed)
    rows = []
    for sub, count, make in (("crops", n, synth.make_crop), ("scenes", scenes, synth.make_scene)):
        (out / sub).mkdir(parents=True, exist_ok=True)
        for i in range(count):
            s = make(rng)
            path = f"{sub}/plate_{s.key}_{i:04d}.jpg"
            cv2.imwrite(str(out / path), s.image, [cv2.IMWRITE_JPEG_QUALITY, 92])
            box = [f"{v:.1f}" for v in s.boxes[0]] if sub == "scenes" else ["", "", "", ""]
            rows.append((path, s.key, s.plate_type, *box))
    with open(out / "labels.csv", "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([("path", "key", "type", "x1", "y1", "x2", "y2"), *rows])
    print(f"bench: {n} crops + {scenes} scenes -> {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", choices=["chars", "plates", "bench"], required=True)
    ap.add_argument("--n", type=int, default=2000)
    ap.add_argument("--scenes", type=int, default=200, help="bench only")
    ap.add_argument("--val", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    out = ROOT / args.out
    if args.kind == "bench":
        write_bench(out, args.n, args.scenes, args.seed)
    else:
        write_yolo(out, args.kind, args.n, args.val, args.seed)


if __name__ == "__main__":
    main()
