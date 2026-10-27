# Training a newer model

PLPR ships YOLOv5s models. `scripts/train.py` trains a newer Ultralytics model (YOLO26n by default,
YOLO11n also works) on synthetic plates, optionally mixed with real labelled data, and exports ONNX files
that `plpr.engine` loads without code changes.

Ultralytics is AGPL-3.0. It is only used for training and export (`pip install -e ".[train]"`);
inference uses ONNX Runtime alone.

## 1. Make data

```bash
python scripts/make_dataset.py --kind chars  --n 20000 --out data/synth_chars    # plate crops, 43 char classes
python scripts/make_dataset.py --kind plates --n 10000 --out data/synth_plates   # 640x640 scenes, 1 plate class
```

`plpr/synth.py` renders random valid plates on `Templates/*.png` with `vazir.ttf` (Vazirmatn Bold),
then applies perspective, blur, noise, brightness/contrast, glare, night darkening and JPEG artifacts.
70% of plates are private (white), 30% use the special templates (taxi/public, government, police,
military, diplomatic, free zone). Class order is `plpr/labels.py` `CHAR_CLASSES`, which the engine assumes.
Disk use is about 18 KB per crop and 70 KB per scene.

Synthetic data alone will not match the real plate font, dirt or lighting. Mix in real labelled plates:

```bash
python scripts/train.py --data data/synth_chars/data.yaml --name chars --extra-train /data/real_chars/images/train
```

Extra folders must be YOLO format (`images/` next to `labels/`) with the same class ids as `CHAR_CLASSES`.
The IRANIS dataset (see `trainer/README.md`) is single-character images, not plates with 8 boxes, so it does
not plug in here directly; it would need its class names remapped to `CHAR_CLASSES` and is better suited to
a separate character classifier.

## 2. Train and export

```bash
python scripts/train.py --data data/synth_chars/data.yaml  --name chars --model yolo26n.pt --epochs 100
python scripts/train.py --data data/synth_plates/data.yaml --name plate --model yolo26n.pt --epochs 100
```

- Device is picked automatically: CUDA, then Apple `mps`, then CPU (`--device` overrides).
- Pretrained weights download to `data/weights/`; runs go to `data/runs/<name>/`.
- Horizontal flips are off (a mirrored Persian glyph is a different glyph); mosaic is off for chars.
- Output: `data/models/<name>.onnx` and `<name>.fp16.onnx`, exported at `--export-imgsz 640`. Both models
  must use the same input size, because `Engine` letterboxes to the plate model's size for both.

To use the new files, copy them into `model/onnx/` (or pass `Engine(model_dir=...)`), then run
`pytest tests/test_core.py` and `scripts/eval.py` (see `docs/benchmark.md`) and compare against the YOLOv5 numbers.
Replace one model at a time; a new chars model works with the old plate model and the other way round.

### Output contract

Ultralytics YOLOv8/11/26 Detect heads export `(1, 4+nc, N)`: `cx, cy, w, h` in input pixels followed by
sigmoid class scores, no objectness. YOLOv5 exports `(1, N, 5+nc)` with objectness. `train.py` appends four
ONNX nodes (Transpose, two Slices, Concat with a constant column of ones) so the saved file is
`(1, N, 5+nc)` with objectness 1. `decode()` then computes `cls * 1`, so **plpr.engine and
web/src/pipeline.ts need no change**. The output is renamed `output`; the input stays `images`.

The export uses `nms=None` (the default), which gives the raw one-to-many head and keeps NMS in
`decode()`. YOLO26's NMS-free head (`nms=False`, output `(1, 300, 6)` as `x1, y1, x2, y2, score, class`)
would let `decode()` skip NMS, but that needs a second decode path in both `plpr/engine.py` and the web
pipeline; not done.

### Smoke run (done, 2026-10-27)

```bash
python scripts/make_dataset.py --kind chars --n 600 --out data/synth_chars
python scripts/train.py --data data/synth_chars/data.yaml --name chars --epochs 2 --imgsz 320
```

YOLO26n, 540 train / 60 val crops, 2 epochs at 320 px on Apple M4 (`mps`): about 1 minute per epoch with
other jobs running. mAP50 0.056 after 2 epochs (meaningless this early; it proves the loop runs).
Export gave `data/models/chars.onnx` (9.9 MB fp32) with output `(1, 8400, 48)`; `Engine` loaded it next to the
YOLOv5 plate model and decoded boxes without errors.

## Full training: time and compute

Rough estimates for YOLO26n at 640 px, 100 epochs; measure with a 1-epoch run first.

| set | Apple M4 (`mps`) | single T4 / L4 GPU | A100 / H100 |
|---|---|---|---|
| chars, 20k crops | days | 4-6 h | about 1 h |
| plates, 10k scenes | 1-2 days | 2-4 h | under 1 h |

- A laptop is fine for smoke runs and fine-tuning on a few thousand images; for full runs use a rented GPU
  (Colab, Kaggle, RunPod, Lambda, Vast.ai). Copy `data/synth_*` or regenerate there with the same seed.
- Train at the size you export (640). `Engine` letterboxes crops to the plate model's input size, so a chars
  model trained at 320 sees characters twice as large at inference. The 320 px smoke run only tests the pipeline.
- Start from `yolo26n.pt` (pretrained) rather than a `.yaml`; it converges much faster.

After training, quantize for the web build with `python scripts/quantize.py` and check the accuracy drop
with `scripts/eval.py --variants fp32 int8` (keep int8 only if it reads the fixtures and loses at most 2 points).
