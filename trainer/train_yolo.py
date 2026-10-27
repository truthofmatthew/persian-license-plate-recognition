"""Train YOLOv8n from scratch on the IRANIS split made by split_folders.py + annotate_for_yolo.py.

Run from this folder: python train_yolo.py. For the plate/character models used by plpr,
prefer ../scripts/train.py (see ../docs/training.md).
"""
from ultralytics import YOLO

model = YOLO('yolov8n.yaml')
results = model.train(data='datasets/split/dataset.yaml', epochs=256, imgsz=640, device='mps')
