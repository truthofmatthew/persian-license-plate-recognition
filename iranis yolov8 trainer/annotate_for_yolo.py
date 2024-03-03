import os
import json
from PIL import Image


def resize_image_in_place(image_path, min_size=256):
    with Image.open(image_path) as img:
        factor = max(min_size / img.width, min_size / img.height)
        # Only resize if either dimension is smaller than min_size
        if factor > 1:
            new_size = (int(img.width * factor), int(img.height * factor))
            resized_img = img.resize(new_size, Image.Resampling.LANCZOS)
            resized_img.save(image_path)  # Save resized image back to disk


def get_bounding_boxes_for_image(image):
    return [(0, 0, image.width, image.height)]


def convert_bbox_to_yolo_format(bbox, image_width, image_height):
    x1, y1, x2, y2 = bbox
    x_center = ((x1 + x2) / 2) / image_width
    y_center = ((y1 + y2) / 2) / image_height
    width = (x2 - x1) / image_width
    height = (y2 - y1) / image_height
    return x_center, y_center, width, height


def convert_bbox_to_coco_format(bbox):
    x1, y1, x2, y2 = bbox
    return [x1, y1, x2 - x1, y2 - y1]


def process_dataset_for_yolo_and_coco(dataset_path, min_image_size=256):
    split_folders = ['train', 'test', 'val']
    classes = []
    coco_images = []
    coco_annotations = []
    annotation_id = 1

    for split_folder in split_folders:
        split_path = os.path.join(dataset_path, split_folder)
        class_dirs = [d for d in os.listdir(split_path) if os.path.isdir(os.path.join(split_path, d))]
        classes.extend(class_dirs)

        for class_dir in class_dirs:
            class_path = os.path.join(split_path, class_dir)
            image_files = [f for f in os.listdir(class_path) if f.endswith(('.jpg', '.png'))]

            for image_file in image_files:
                image_path = os.path.join(class_path, image_file)
                resize_image_in_place(image_path, min_image_size)

                with Image.open(image_path) as image:
                    image_width, image_height = image.size
                    bboxes = get_bounding_boxes_for_image(image)
                    image_id = len(coco_images) + 1

                    # YOLO format annotations
                    annotation_lines = []
                    for bbox in bboxes:
                        x_center, y_center, width, height = convert_bbox_to_yolo_format(bbox, image_width, image_height)
                        class_id = classes.index(class_dir)
                        annotation_lines.append(f"{class_id} {x_center} {y_center} {width} {height}")

                    # Save YOLO annotations
                    annotation_file_path = os.path.join(class_path, image_file.rsplit('.', 1)[0] + '.txt')
                    with open(annotation_file_path, 'w') as file:
                        file.write('\n'.join(annotation_lines))

                    # COCO format annotations
                    coco_images.append(
                            {
                                    "id": image_id,
                                    "width": image_width,
                                    "height": image_height,
                                    "file_name": image_file
                                    }
                            )
                    for bbox in bboxes:
                        coco_bbox = convert_bbox_to_coco_format(bbox)
                        coco_annotations.append(
                                {
                                        "id": annotation_id,
                                        "image_id": image_id,
                                        "category_id": class_id + 1,
                                        "bbox": coco_bbox,
                                        "area": coco_bbox[2] * coco_bbox[3],
                                        "iscrowd": 0,
                                        "segmentation": []
                                        }
                                )
                        annotation_id += 1

    # Ensure classes are unique and sorted
    classes = sorted(set(classes))
    coco_categories = [{
                               "id": i + 1,
                               "name": class_name
                               } for i, class_name in enumerate(classes)]

    return classes, coco_images, coco_annotations, coco_categories


def create_yaml_file(classes, dataset_path):
    yaml_content = f"""
path: {dataset_path}
train: {os.path.join(dataset_path, 'train')}
val: {os.path.join(dataset_path, 'val')}
test: {os.path.join(dataset_path, 'test')}

nc: {len(classes)}
names: {classes}
"""
    yaml_file_path = os.path.join(dataset_path, 'dataset.yaml')
    with open(yaml_file_path, 'w') as yaml_file:
        yaml_file.write(yaml_content)

def create_coco_json(images, annotations, categories, dataset_path):
    coco_format = {
        "images": images,
        "annotations": annotations,
        "categories": categories
    }
    coco_file_path = os.path.join(dataset_path, 'annotations.json')
    with open(coco_file_path, 'w') as coco_file:
        json.dump(coco_format, coco_file)

dataset_path = 'datasets/split'
classes, coco_images, coco_annotations, coco_categories = process_dataset_for_yolo_and_coco(dataset_path)
create_yaml_file(classes, dataset_path)
create_coco_json(coco_images, coco_annotations, coco_categories, dataset_path)
print("YAML and COCO annotation files generated.")
