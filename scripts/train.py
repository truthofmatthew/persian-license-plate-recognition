"""Train a newer YOLO (YOLO26n / YOLO11n, Ultralytics) for plates or characters and export it for plpr.engine.

Usage:
  python scripts/make_dataset.py --kind chars --n 20000 --out data/synth_chars
  python scripts/train.py --data data/synth_chars/data.yaml --name chars --model yolo26n.pt --epochs 100
  python scripts/train.py --data data/synth_chars/data.yaml --name chars --extra-train /path/to/real/images/train

Writes <out>/<name>.onnx and <name>.fp16.onnx (default out: data/models). Ultralytics Detect heads
export (1, 4+nc, N) without objectness; export_for_plpr() appends a Transpose + ones column so the
file has the YOLOv5 contract (1, N, 5+nc) that plpr.engine.decode and web/src/pipeline.ts read.
Ultralytics is AGPL-3.0; it is only needed here, never at inference time.
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper
from onnxconverter_common import float16

ROOT = Path(__file__).resolve().parents[1]


def pick_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "0"
    if torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def to_v5_contract(src: Path, dst: Path, names: list[str], imgsz: int) -> None:
    """(1, 4+nc, N) cx,cy,w,h,cls... -> (1, N, 5+nc) with objectness 1, output renamed 'output'."""
    m = onnx.load(src)
    g = m.graph
    old = g.output[0]
    dims = [d.dim_value for d in old.type.tensor_type.shape.dim]
    _, c, n = dims
    nc = c - 4
    assert nc == len(names), f"model has {nc} classes, data.yaml has {len(names)}"
    g.initializer.extend([
        numpy_helper.from_array(np.ones((1, n, 1), np.float32), "v5_ones"),
        numpy_helper.from_array(np.array([0], np.int64), "v5_s0"),
        numpy_helper.from_array(np.array([4], np.int64), "v5_s4"),
        numpy_helper.from_array(np.array([c], np.int64), "v5_sc"),
        numpy_helper.from_array(np.array([2], np.int64), "v5_ax"),
    ])
    g.node.extend([
        helper.make_node("Transpose", [old.name], ["v5_t"], perm=[0, 2, 1]),
        helper.make_node("Slice", ["v5_t", "v5_s0", "v5_s4", "v5_ax"], ["v5_box"]),
        helper.make_node("Slice", ["v5_t", "v5_s4", "v5_sc", "v5_ax"], ["v5_cls"]),
        helper.make_node("Concat", ["v5_box", "v5_ones", "v5_cls"], ["output"], axis=2),
    ])
    g.output.remove(old)
    g.output.append(helper.make_tensor_value_info("output", TensorProto.FLOAT, [1, n, 5 + nc]))
    del m.metadata_props[:]
    for k, v in {"names": json.dumps(names, ensure_ascii=False), "imgsz": str(imgsz), "stride": "32"}.items():
        m.metadata_props.add(key=k, value=v)
    onnx.checker.check_model(m)
    onnx.save(m, dst)
    onnx.save(float16.convert_float_to_float16(m, keep_io_types=True), dst.with_suffix("").with_suffix(".fp16.onnx"))


def merged_data(data: Path, extra: list[str], out_dir: Path) -> Path:
    """data.yaml with extra train image dirs appended (labels must use the same class order)."""
    import yaml

    cfg = yaml.safe_load(data.read_text(encoding="utf-8"))
    base = Path(cfg.get("path") or data.parent)
    cfg["path"] = str(base.resolve())
    cfg["train"] = [cfg["train"]] if isinstance(cfg["train"], str) else cfg["train"]
    cfg["train"] += [str(Path(p).resolve()) for p in extra]
    out = out_dir / f"{data.stem}.merged.yaml"
    out.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True, help="YOLO data.yaml (scripts/make_dataset.py)")
    ap.add_argument("--name", choices=["plate", "chars"], required=True)
    ap.add_argument("--model", default="yolo26n.pt", help="yolo26n.pt, yolo11n.pt, or a .yaml to train from scratch")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=640, help="train size")
    ap.add_argument("--export-imgsz", type=int, default=640, help="must match the other model: Engine uses one input size")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--device", default=None, help="default: cuda > mps > cpu")
    ap.add_argument("--extra-train", nargs="*", default=[], help="more YOLO image dirs, e.g. real labelled plates")
    ap.add_argument("--out", type=Path, default=ROOT / "data" / "models")
    ap.add_argument("--fraction", type=float, default=1.0, help="use part of the train set (smoke runs)")
    args = ap.parse_args()

    from ultralytics import YOLO

    runs = ROOT / "data" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    data = merged_data(args.data, args.extra_train, runs) if args.extra_train else args.data
    device = args.device or pick_device()
    weights = ROOT / "data" / "weights" / args.model  # keep downloaded checkpoints out of the repo root
    if args.model.endswith(".pt") and "/" not in args.model and not Path(args.model).exists():
        weights.parent.mkdir(parents=True, exist_ok=True)
        args.model = str(weights)
    model = YOLO(args.model)
    model.train(data=str(data), epochs=args.epochs, imgsz=args.imgsz, batch=args.batch, device=device,
                project=str(runs), name=args.name, exist_ok=True, fraction=args.fraction,
                fliplr=0.0,  # mirrored Persian glyphs are other glyphs; left/right order matters
                mosaic=0.0 if args.name == "chars" else 1.0)
    best = runs / args.name / "weights" / "best.pt"
    trained = YOLO(str(best))
    raw = Path(trained.export(format="onnx", imgsz=args.export_imgsz, opset=17, simplify=True, dynamic=False))
    names = [trained.names[i] for i in sorted(trained.names)]
    args.out.mkdir(parents=True, exist_ok=True)
    dst = args.out / f"{args.name}.onnx"
    to_v5_contract(raw, dst, names, args.export_imgsz)
    print(f"{args.name}: {best} -> {dst} ({dst.stat().st_size / 1e6:.1f} MB) on {device}")


if __name__ == "__main__":
    sys.exit(main())
