"""Export the YOLOv5 plate and character models to ONNX (FP32 + FP16) with class labels.

Usage: python scripts/export_onnx.py [--imgsz 640] [--out model/onnx]

The web app, the FastAPI server and the edge agent all load these files, so this is
the only place that touches PyTorch at deploy time.
"""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "yolov5"))
os.environ.setdefault("TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD", "1")  # yolov5 checkpoints are pickled models

import onnx
import torch
from onnxconverter_common import float16

MODELS = {"plate": "model/plateYolo.pt", "chars": "model/CharsYolo.pt"}


def export(name: str, weights: Path, out: Path, imgsz: int) -> list[str]:
    from models.experimental import attempt_load  # yolov5

    model = attempt_load(weights, device="cpu", inplace=True, fuse=True).eval()
    for m in model.modules():
        if hasattr(m, "export"):
            m.export = True  # yolov5 Detect returns a single tensor when exporting
    names = model.names if isinstance(model.names, list) else [model.names[i] for i in sorted(model.names)]

    fp32 = out / f"{name}.onnx"
    torch.onnx.export(
        model, torch.zeros(1, 3, imgsz, imgsz), fp32, opset_version=17, dynamo=False,
        input_names=["images"], output_names=["output"],
    )
    proto = onnx.load(fp32)
    onnx.checker.check_model(proto)
    for k, v in {"names": json.dumps(names, ensure_ascii=False), "imgsz": str(imgsz), "stride": "32"}.items():
        proto.metadata_props.add(key=k, value=v)
    onnx.save(proto, fp32)
    onnx.save(float16.convert_float_to_float16(proto, keep_io_types=True), out / f"{name}.fp16.onnx")
    print(f"{name}: {len(names)} classes -> {fp32} ({fp32.stat().st_size / 1e6:.1f} MB)")
    return names


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--out", default="model/onnx")
    args = ap.parse_args()
    out = ROOT / args.out
    out.mkdir(parents=True, exist_ok=True)
    labels = {name: export(name, ROOT / w, out, args.imgsz) for name, w in MODELS.items()}
    labels["imgsz"] = args.imgsz
    (out / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
