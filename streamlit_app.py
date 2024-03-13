import streamlit as st
import pandas as pd
from PIL import Image
import torch
import cv2
import numpy as np
import tempfile
from configParams import Parameters

params = Parameters()
# Load models
modelPlate = torch.hub.load('yolov5', 'custom', params.modelPlate_path, source='local', force_reload=True)
modelCharX = torch.hub.load('yolov5', 'custom', params.modelCharX_path, source='local', force_reload=True)


def detect_plate_chars(image):
    results_plate = modelPlate(image)
    plates = []
    for *xyxy, conf, _ in results_plate.xyxy[0]:
        x1, y1, x2, y2 = map(int, xyxy)
        crop_img = image[y1:y2, x1:x2]
        results_char = modelCharX(crop_img)
        chars = []
        confidences = []
        for *_, conf_char, class_char in results_char.xyxy[0]:
            char = results_char.names[int(class_char)]
            chars.append(char)
            confidences.append(conf_char.item())
        plate_text = ''.join(chars)
        char_conf_avg = np.mean(confidences) if confidences else 0
        plates.append((plate_text, conf.item(), char_conf_avg))
    return plates


def process_image(image):
    # Convert PIL image to cv2 format
    image = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    plates = detect_plate_chars(image)
    return plates


def display_results(plates):
    if plates:
        df = pd.DataFrame(plates, columns=["License Plate", "Plate Confidence", "Average Char Confidence"])
        st.table(df)
    else:
        st.write("No license plates detected.")


def main():
    st.title("License Plate Detection")
    uploaded_file = st.file_uploader("Choose an image or video...", type=["jpg", "jpeg", "png", "mp4"])

    if uploaded_file is not None:
        if uploaded_file.type == "video/mp4":
            tfile = tempfile.NamedTemporaryFile(delete=False)
            tfile.write(uploaded_file.read())
            cap = cv2.VideoCapture(tfile.name)
            stframe = st.empty()
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(frame)
                plates = process_image(pil_img)
                stframe.image(pil_img, use_column_width=True)
                display_results(plates)
        else:
            image = Image.open(uploaded_file)
            plates = process_image(image)
            st.image(image, caption="Uploaded Image", use_column_width=True)
            display_results(plates)


if __name__ == "__main__":
    main()
