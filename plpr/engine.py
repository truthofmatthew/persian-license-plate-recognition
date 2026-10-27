"""ONNX Runtime inference for the two-stage pipeline: plate detector -> character detector.

No PyTorch needed. The same ONNX files run in the browser (web/) through onnxruntime-web,
and web/src/pipeline.ts mirrors this file, so keep the two in step.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort

from .labels import CHAR_CLASSES
from .plate import PlateNumber, parse_codes

DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[1] / "model" / "onnx"


@dataclass
class PlateRead:
    box: tuple[int, int, int, int]  # x1, y1, x2, y2 in source pixels
    plate_conf: float
    codes: list[str] = field(default_factory=list)
    char_confs: list[float] = field(default_factory=list)
    plate: PlateNumber | None = None

    @property
    def char_conf(self) -> float:
        return float(np.mean(self.char_confs)) if self.char_confs else 0.0

    @property
    def text(self) -> str:
        return self.plate.key if self.plate else "".join(self.codes)


def letterbox(img: np.ndarray, size: int) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize keeping aspect ratio, pad with 114 grey (YOLOv5 convention)."""
    h, w = img.shape[:2]
    r = min(size / h, size / w)
    nh, nw = round(h * r), round(w * r)
    top, left = (size - nh) // 2, (size - nw) // 2
    out = np.full((size, size, 3), 114, np.uint8)
    out[top:top + nh, left:left + nw] = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    return out, r, (left, top)


def decode(pred: np.ndarray, conf: float, iou: float) -> np.ndarray:
    """YOLOv5 raw output (N, 5+nc) -> (K, 6) [x1, y1, x2, y2, score, cls] after class-agnostic NMS."""
    scores_all = pred[:, 5:] * pred[:, 4:5]
    cls = scores_all.argmax(1)
    scores = scores_all[np.arange(len(cls)), cls]
    keep = scores > conf
    if not keep.any():
        return np.zeros((0, 6), np.float32)
    p, scores, cls = pred[keep], scores[keep], cls[keep]
    xywh = p[:, :4].copy()
    xywh[:, :2] -= xywh[:, 2:] / 2  # cx,cy -> x,y (top-left) for NMSBoxes
    idx = cv2.dnn.NMSBoxes(xywh.tolist(), scores.tolist(), conf, iou)
    idx = np.array(idx).reshape(-1)
    b = xywh[idx]
    return np.column_stack([b[:, 0], b[:, 1], b[:, 0] + b[:, 2], b[:, 1] + b[:, 3], scores[idx], cls[idx]]).astype(np.float32)


class Engine:
    def __init__(self, model_dir: str | Path = DEFAULT_MODEL_DIR, fp16: bool = False, providers: list[str] | None = None,
                 variant: str = ""):
        """variant: "" (fp32), "fp16" or "int8"; picks model/onnx/{plate,chars}.<variant>.onnx."""
        model_dir = Path(model_dir)
        variant = variant or ("fp16" if fp16 else "")
        suffix = f".{variant}.onnx" if variant else ".onnx"
        providers = providers or [p for p in ("CUDAExecutionProvider", "CoreMLExecutionProvider", "CPUExecutionProvider") if p in ort.get_available_providers()]
        opts = ort.SessionOptions()
        opts.log_severity_level = 3
        self.plate_sess = ort.InferenceSession(str(model_dir / f"plate{suffix}"), opts, providers=providers)
        self.char_sess = ort.InferenceSession(str(model_dir / f"chars{suffix}"), opts, providers=providers)
        self.size = self.plate_sess.get_inputs()[0].shape[2]

    def _run(self, sess: ort.InferenceSession, img_bgr: np.ndarray, conf: float, iou: float) -> np.ndarray:
        lb, r, (dx, dy) = letterbox(img_bgr, self.size)
        x = np.ascontiguousarray(lb[:, :, ::-1].transpose(2, 0, 1)[None], dtype=np.float32) / 255.0  # BGR->RGB, CHW
        det = decode(sess.run(None, {"images": x})[0][0], conf, iou)
        det[:, [0, 2]] = (det[:, [0, 2]] - dx) / r
        det[:, [1, 3]] = (det[:, [1, 3]] - dy) / r
        h, w = img_bgr.shape[:2]
        det[:, [0, 2]] = det[:, [0, 2]].clip(0, w)
        det[:, [1, 3]] = det[:, [1, 3]].clip(0, h)
        return det

    def detect_plates(self, img_bgr: np.ndarray, conf: float = 0.5) -> np.ndarray:
        return self._run(self.plate_sess, img_bgr, conf, 0.45)

    def read_chars(self, crop_bgr: np.ndarray, conf: float = 0.5) -> tuple[list[str], list[float]]:
        det = self._run(self.char_sess, crop_bgr, conf, 0.3)
        if len(det) > 8:  # keep the 8 most confident, then restore left-to-right order
            det = det[np.argsort(-det[:, 4])[:8]]
        det = det[np.argsort(det[:, 0])]
        return [CHAR_CLASSES[int(c)][0] for c in det[:, 5]], [float(s) for s in det[:, 4]]

    def read_crop(self, crop_bgr: np.ndarray, conf: float = 0.5) -> PlateRead:
        h, w = crop_bgr.shape[:2]
        codes, confs = self.read_chars(crop_bgr, conf)
        return PlateRead((0, 0, w, h), 1.0, codes, confs, parse_codes(codes))

    def read(self, img_bgr: np.ndarray, plate_conf: float = 0.5, char_conf: float = 0.5) -> list[PlateRead]:
        reads = []
        for x1, y1, x2, y2, s, _ in self.detect_plates(img_bgr, plate_conf):
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            if x2 - x1 < 8 or y2 - y1 < 4:
                continue
            codes, confs = self.read_chars(img_bgr[y1:y2, x1:x2], char_conf)
            reads.append(PlateRead((x1, y1, x2, y2), float(s), codes, confs, parse_codes(codes)))
        return reads
