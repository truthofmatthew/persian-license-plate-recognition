"""Evaluate the ONNX models on labelled images and print a markdown report.

Ground truth comes from a labels CSV (path,key,type[,x1,y1,x2,y2], paths relative to the CSV) or,
without --labels, from file names ``plate_<KEY>[_anything].jpg`` under --images.
Wide images (w/h >= 2) are treated as plate crops (Engine.read_crop); the rest as scenes
(Engine.read, plus plate-detection recall at IoU >= 0.5 when the CSV has a box).

Usage:
  python scripts/eval.py --images tests/fixtures
  python scripts/eval.py --labels data/bench/labels.csv --variants fp32 fp16 int8 --out report.md
"""
import argparse
import csv
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plpr import Engine, PlateNumber
from plpr.engine import DEFAULT_MODEL_DIR
from plpr.tracking import iou

NAME_RE = re.compile(r"^plate_(.+?)(?:_\d+)?$")


def load_engine(model_dir: Path, variant: str, providers: list[str]) -> Engine:
    return Engine(model_dir, providers=providers, variant="" if variant == "fp32" else variant)


def key_codes(key: str) -> list[str]:
    p = PlateNumber.from_key(key)
    return list(p.left) + [p.letter] + list(p.middle) + list(p.region) if p else list(key)


def edit_distance(a: list[str], b: list[str]) -> int:
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        prev, d[0] = d[0], i
        for j, y in enumerate(b, 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (x != y))
    return d[-1]


def load_items(images: Path | None, labels: Path | None) -> list[dict]:
    items = []
    if labels:
        with open(labels, encoding="utf-8") as f:
            for row in csv.DictReader(f):
                box = tuple(float(row[k]) for k in ("x1", "y1", "x2", "y2")) if row.get("x1") else None
                items.append({"path": labels.parent / row["path"], "key": row["key"], "type": row.get("type") or "", "box": box})
    else:
        for p in sorted(images.rglob("*")):
            m = NAME_RE.match(p.stem)
            if m and p.suffix.lower() in (".jpg", ".jpeg", ".png"):
                items.append({"path": p, "key": m.group(1), "type": "", "box": None})
    for it in items:
        if not it["type"]:
            p = PlateNumber.from_key(it["key"])
            it["type"] = p.plate_type if p else "unknown"
    return items


def evaluate(eng: Engine, items: list[dict]) -> dict:
    per_type = defaultdict(lambda: [0, 0, 0, 0])  # n, exact, char errors, chars
    det_hit = det_n = 0
    times = []
    for it in items:
        img = cv2.imread(str(it["path"]))
        h, w = img.shape[:2]
        t0 = time.perf_counter()
        if w / h >= 2:
            r = eng.read_crop(img)
        else:
            reads = eng.read(img)
            r = max(reads, key=lambda x: x.plate_conf) if reads else None
            det_n += 1
            if it["box"]:
                det_hit += any(iou(x.box, it["box"]) >= 0.5 for x in reads)
            else:
                det_hit += bool(reads)
        times.append((time.perf_counter() - t0) * 1000)
        gt = key_codes(it["key"])
        pred = r.codes if r else []
        s = per_type[it["type"]]
        s[0] += 1
        s[1] += (r.text if r else "") == it["key"]
        s[2] += edit_distance(pred, gt)
        s[3] += len(gt)
    tot = np.sum(list(per_type.values()), axis=0)
    t = np.array(times[1:] or times)  # first call includes session warm-up
    return {"n": int(tot[0]), "exact": tot[1] / tot[0], "cer": tot[2] / tot[3], "per_type": dict(per_type),
            "det": det_hit / det_n if det_n else None, "det_n": det_n, "ms_mean": t.mean(), "ms_p95": np.percentile(t, 95)}


def report(results: dict[str, dict], model_dir: Path, variants: list[str]) -> str:
    out = ["| variant | size plate+chars (MB) | n | exact match | CER | plate recall (scenes) | latency mean / p95 (ms) |", "|---|---|---|---|---|---|---|"]
    for v, r in results.items():
        suffix = ".onnx" if v == "fp32" else f".{v}.onnx"
        mb = sum((model_dir / f"{m}{suffix}").stat().st_size for m in ("plate", "chars")) / 1e6
        det = f"{r['det']:.1%} ({r['det_n']})" if r["det"] is not None else "-"
        out.append(f"| {v} | {mb:.1f} | {r['n']} | {r['exact']:.1%} | {r['cer']:.1%} | {det} | {r['ms_mean']:.1f} / {r['ms_p95']:.1f} |")
    types = sorted({t for r in results.values() for t in r["per_type"]})
    out += ["", "| plate type | n | " + " | ".join(f"{v} exact / CER" for v in variants) + " |", "|---|---|" + "---|" * len(variants)]
    for t in types:
        n = next(r["per_type"][t][0] for r in results.values() if t in r["per_type"])
        cells = [f"{r['per_type'][t][1] / r['per_type'][t][0]:.0%} / {r['per_type'][t][2] / r['per_type'][t][3]:.0%}" for r in results.values()]
        out.append(f"| {t} | {n} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", type=Path, help="folder of plate_<KEY>*.jpg")
    ap.add_argument("--labels", type=Path, help="CSV path,key,type[,x1,y1,x2,y2]")
    ap.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    ap.add_argument("--variants", nargs="+", default=["fp32", "fp16"], help="fp32, fp16 or any <name> with plate.<name>.onnx")
    ap.add_argument("--provider", default="cpu", choices=["cpu", "auto"], help="cpu keeps numbers comparable across machines")
    ap.add_argument("--out", type=Path, help="also write the markdown here")
    args = ap.parse_args()
    if not (args.images or args.labels):
        ap.error("pass --images or --labels")
    items = load_items(args.images, args.labels)
    providers = ["CPUExecutionProvider"] if args.provider == "cpu" else None
    results = {v: evaluate(load_engine(args.model_dir, v, providers), items) for v in args.variants}
    md = report(results, args.model_dir, args.variants)
    print(md)
    if args.out:
        args.out.write_text(md, encoding="utf-8")


if __name__ == "__main__":
    main()
