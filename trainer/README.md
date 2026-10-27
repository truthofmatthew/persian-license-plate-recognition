# IRANIS YOLOv8 trainer (legacy)

A small teaching project: prepare the [IRANIS dataset](https://github.com/alitourani/Iranis-dataset) and train
YOLOv8 on it. It was the folder `iranis yolov8 trainer/` before PLPR 2.0.

For the models that `plpr` actually loads (plate detector + 43-class character detector), use
`scripts/make_dataset.py` and `scripts/train.py` from the repo root instead; see
[docs/training.md](../docs/training.md).

IRANIS is a set of single-character images grouped in one folder per class. These scripts label every image
with one box covering the whole image, so the result behaves like a character classifier, not a detector that
finds the 8 symbols on a plate. Its class names also differ from `plpr/labels.py`.

## Steps

Run everything from this folder (`cd trainer`):

1. Install dependencies: `pip install -r requirements.txt` (or the repo's `pip install -e ".[train]"` plus `split-folders`).
2. Download IRANIS and extract it to `datasets/iranis/<class>/*.jpg`.
3. `python split_folders.py` writes `datasets/split/{train,val,test}/<class>/` (80/10/10).
4. `python annotate_for_yolo.py` writes a YOLO `.txt` next to each image, `datasets/split/dataset.yaml`
   and `datasets/split/annotations.json` (COCO).
5. `python train_yolo.py` trains `yolov8n.yaml` from scratch for 256 epochs on `mps`
   (change `device` to `cuda`, `cpu` or `0` on other machines).

Note: `annotate_for_yolo.py` resizes small images in place (minimum side 256 px), so keep a copy of the
original download.
