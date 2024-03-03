from ultralytics import YOLO
from ultralytics import settings

# View all settings

settings.update({'datasets_dir': ''})
settings.update({'weights_dir': ''})
settings.update({'runs_dir': ''})

# print(settings)
model = YOLO('yolov8n.yaml')
results = model.train(data='datasets/split/dataset.yaml', epochs=256, imgsz=640, device='mps')
