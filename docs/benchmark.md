# Benchmark

Current models: YOLOv5s plate detector + YOLOv5s 43-class character detector, exported to ONNX
(`model/onnx`). Measured on 2026-10-27, Apple M4, ONNX Runtime CPU provider, one image at a time.
Other jobs were running on the machine, so treat latency as rough; accuracy numbers are exact.

## Reproduce

```bash
python scripts/make_dataset.py --kind bench --n 500 --scenes 200 --seed 1234 --out data/bench   # frozen set
python scripts/quantize.py --mode static --calib 48                                            # int8 files
python scripts/eval.py --images tests/fixtures --variants fp32 fp16 int8
python scripts/eval.py --labels data/bench/labels.csv --variants fp32 fp16 int8
```

`data/bench` is generated, not committed; the same seed and library versions give the same images.
Crops are plate images (Engine.read_crop); scenes are 640x640 images with one plate (Engine.read).

## Real plates (tests/fixtures, 2 crops)

| variant | size plate+chars (MB) | exact match | CER |
|---|---|---|---|
| fp32 | 56.8 | 2/2 | 0% |
| fp16 | 28.5 | 2/2 | 0% |
| int8 | 15.7 | 2/2 | 0% |

Two images is a smoke test, not an accuracy figure. A real labelled set is the next thing this needs.

## Synthetic benchmark (500 crops + 200 scenes, seed 1234)

| variant | size plate+chars (MB) | n | exact match | CER | plate recall (scenes, IoU 0.5) | latency mean / p95 (ms) |
|---|---|---|---|---|---|---|
| fp32 | 56.8 | 700 | 28.7% | 24.0% | 70.5% | 184 / 420 |
| fp16 | 28.5 | 700 | 28.6% | 24.1% | 70.5% | 126 / 238 |
| int8 | 15.7 | 700 | 28.3% | 24.0% | 71.0% | 159 / 380 |

| plate type | n | fp32 exact / CER | fp16 exact / CER | int8 exact / CER |
|---|---|---|---|---|
| private | 480 | 37% / 15% | 37% / 15% | 36% / 15% |
| public | 12 | 50% / 15% | 50% / 16% | 50% / 15% |
| taxi | 7 | 0% / 18% | 0% / 18% | 0% / 18% |
| government | 39 | 5% / 41% | 5% / 41% | 3% / 41% |
| police | 20 | 0% / 44% | 0% / 44% | 0% / 46% |
| military | 79 | 13% / 47% | 13% / 47% | 11% / 47% |
| diplomatic | 52 | 4% / 56% | 4% / 56% | 4% / 57% |
| free_zone | 11 | 36% / 22% | 36% / 22% | 45% / 19% |

How to read this:

- The synthetic set is harder than it looks for the current model: 30% of plates use the special-plate
  templates (white text on red/green/blue), which the YOLOv5 character model never saw. On white private
  plates it does far better.
- On 300 clean (unaugmented) private crops, per-character recall is 99% or more for the digits 1-9 and the
  common letters, but low for `0` (33%: the Vazirmatn zero is rounder than the plate font) and near zero for
  `A` (الف), `P` (پ, read as ب), `Taxi` (ت, read as ن), `ک`, `ز`, `ش`, `ژ`. These are rare in real data,
  so the old model is weak on them; part of the gap is also the font, which is bolder and wider than the
  real plate font.
- The synthetic numbers are a regression check between model versions, not a real-world accuracy claim.

## INT8 (scripts/quantize.py)

Static QDQ quantization of the Conv layers only (per-channel int8 weights, uint8 activations), calibrated on
48 synthetic images per model; the detect head stays float.

| model | fp32 | fp16 | int8 |
|---|---|---|---|
| plate | 28.1 MB | 14.1 MB | 7.7 MB |
| chars | 28.7 MB | 14.4 MB | 7.9 MB |

Accuracy holds: both fixtures still read correctly, synthetic exact match drops 0.4 points (limit was 2),
CER is unchanged and scene recall is within noise. So `model/onnx/{plate,chars}.int8.onnx` are kept.
INT8 is not faster than fp32 on the M4 CPU here; the gain is download size for the web build. Not yet
checked in onnxruntime-web (it supports QDQ / QLinearConv, but run the web demo on both fixtures first).
Dynamic quantization (`--mode dynamic`) was not benchmarked.
