😅 I made this project to help people learn how to train their models and use them for their own projects. It's specifically designed for training a license plate reading project, but it can be adapted for any object detection task. Personally, I believe all resources and tools related to it should be open source to encourage community development and learning.

## 📚 Additional Academic Resources

Explore the `pdf-research` directory for research papers and articles on LPR technologies, offering insights into the techniques and algorithms behind the system.

---

1. Download the Iranis dataset.
2. Decompress and use `split_folders.py`.
3. Use `annotate_for_yolo.py` after splitting.
4. Finally, use `train_yolo.py`.


# YOLOv8 Training Project

This project demonstrates how to prepare the Iranis dataset for object detection and train YOLOv8, providing a practical example of how to apply deep learning for visual recognition tasks.

## Requirements

- Python 3.x
- split-folders
- PIL (Pillow)
- ultralytics

## Setup

1. Install dependencies:
   ```bash
   pip install split-folders pillow ultralytics
   ```
   
2. Clone this repository:
   ```bash
   git clone https://github.com/mtkarimi/iranis-yolo-trainer.git
   cd iranis-yolo-trainer
   ```

3. Download the Iranis Dataset Files from [here](https://github.com/alitourani/Iranis-dataset) and extract the files into a `dataset` directory.

## Dataset Preparation

1. Split your dataset into training, validation, and test sets:
   ```python
   from split_dataset import split_dataset
   split_dataset('dataset/iranis', 'datasets/split')
   ```

2. Process the dataset for YOLO and COCO:
   ```python
   from process_dataset import process_dataset_for_yolo_and_coco, create_yaml_file, create_coco_json
   classes, coco_images, coco_annotations, coco_categories = process_dataset_for_yolo_and_coco('datasets/split')
   create_yaml_file(classes, 'datasets/split')
   create_coco_json(coco_images, coco_annotations, coco_categories, 'datasets/split')
   ```

## Training

Train the model with the prepared dataset:
```python
from train_model import train_yolov8
train_yolov8('datasets/split/dataset.yaml', epochs=256, imgsz=640, device='mps')
```

## Contributing

Feel free to contribute to this project by submitting pull requests or opening issues.
