"""INT8-quantize model/onnx/{plate,chars}.onnx for the web build.

Usage:
  python scripts/quantize.py --mode static --calib 64        # QDQ, synthetic calibration (default)
  python scripts/quantize.py --mode dynamic

Writes model/onnx/{plate,chars}.int8.onnx. Check accuracy before shipping with
  python scripts/eval.py --labels data/bench/labels.csv --variants fp32 int8
"""
import argparse
import sys
import tempfile
from pathlib import Path

import numpy as np
from onnxruntime.quantization import CalibrationDataReader, QuantFormat, QuantType, quant_pre_process, quantize_dynamic, quantize_static

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from plpr import synth
from plpr.engine import DEFAULT_MODEL_DIR, letterbox


class SynthReader(CalibrationDataReader):
    """Feeds letterboxed synthetic images, preprocessed exactly like Engine._run."""

    def __init__(self, kind: str, n: int, size: int, seed: int = 99):
        rng = np.random.default_rng(seed)
        imgs = [(synth.make_crop(rng) if kind == "chars" else synth.make_scene(rng)).image for _ in range(n)]
        self.batches = iter(
            {"images": np.ascontiguousarray(letterbox(im, size)[0][:, :, ::-1].transpose(2, 0, 1)[None], dtype=np.float32) / 255.0}
            for im in imgs
        )

    def get_next(self):
        return next(self.batches, None)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["static", "dynamic"], default="static")
    ap.add_argument("--calib", type=int, default=64, help="calibration images per model (static)")
    ap.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    ap.add_argument("--imgsz", type=int, default=640)
    args = ap.parse_args()
    for name in ("plate", "chars"):
        src, dst = args.model_dir / f"{name}.onnx", args.model_dir / f"{name}.int8.onnx"
        with tempfile.TemporaryDirectory() as tmp:
            pre = Path(tmp) / "pre.onnx"
            quant_pre_process(str(src), str(pre))  # shape inference + graph cleanup
            if args.mode == "dynamic":
                quantize_dynamic(pre, dst, weight_type=QuantType.QUInt8)
            else:
                quantize_static(
                    pre, dst, SynthReader(name, args.calib, args.imgsz), quant_format=QuantFormat.QDQ,
                    per_channel=True, activation_type=QuantType.QUInt8, weight_type=QuantType.QInt8,
                    op_types_to_quantize=["Conv"],  # keep the detect head math (sigmoid/grid/anchors) in float
                )
        print(f"{name}: {src.stat().st_size / 1e6:.1f} MB -> {dst} ({dst.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
