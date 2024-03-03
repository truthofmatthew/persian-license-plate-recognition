# LPR Application with Deep Learning and GUI

## Introduction

This project explores License Plate Recognition (LPR) using deep learning models, integrated within a graphical user interface (GUI) for enhanced user interaction. The application aims to accurately identify and read vehicle license plates from images or video streams, leveraging advanced deep learning techniques for detection and optical character recognition (OCR). This integration facilitates a user-friendly platform for various applications, including traffic monitoring, security systems, and parking management.

Prerequisites: Python, PyTorch, PySide6, OpenCV, Pillow.

Core Content:
- **Setting Up the Environment**: Requirements include PySide6, PyTorch, Pillow, and OpenCV.
- **Deep Learning Models for LPR**: Utilizing YOLOv5 models for plate and character recognition.
- **Creating a GUI with PySide6**: Building a user interface for real-time LPR monitoring.
- **Integrating PyTorch Models**: How to load and infer with custom-trained models.
- **Real-Time Video Processing**: Implementing webcam feed processing for plate detection.
- **Database Integration for Plate Recognition**: Storing and managing recognized plates.
- **User Interaction**: Adding functionalities for resident management and entry logging.

## Setting Up the Environment

To run this LPR application, you need to install the following dependencies:

- `PySide6`: For creating the graphical user interface.
- `PyTorch`: The deep learning framework used for training and inference.
- `Pillow`: For image processing tasks.
- `OpenCV`: For image and video manipulation.

You can install these dependencies via pip:

```python
pip install PySide6 torch torchvision torchaudio Pillow opencv-python
```
## Deep Learning Models for LPR

This application utilizes the YOLOv5 models for both license plate detection and character recognition, offering high accuracy and efficiency. The models are trained on a diverse dataset to accurately identify license plates and their characters under various conditions.

### License Plate Detection
- **Model**: Custom YOLOv5 model trained specifically for detecting license plates in images or video frames.
- **Usage**: The model takes an input image or video frame and outputs bounding box coordinates for detected license plates.

### Character Recognition
- **Model**: Another YOLOv5 model trained for recognizing characters on the detected license plates.
- **Usage**: After detecting a license plate, this model identifies and reads the characters on the plate.

Both models are integrated into the application's workflow, allowing for seamless detection and recognition of license plates in real-time.

## Creating a GUI with PySide6

The application features a graphical user interface (GUI) built using PySide6, facilitating real-time license plate recognition (LPR) monitoring. The GUI is designed for ease of use, allowing users to interact with the LPR system effectively.

### Key Components of the GUI

- **Main Window**: Displays the video feed where license plates are detected. Detected plates are highlighted with bounding boxes.
- **Plate Details**: Shows the detected license plate's image, the recognized characters, and additional information such as the plate's status (e.g., registered, not registered) and the vehicle owner's name, if available.
- **Control Panel**: Includes buttons to start and stop the video feed, access resident management, view entry logs, and adjust settings.

### Implementation Highlights

1. **Layout and Design**:
   - Utilize PySide6's layout managers to design a responsive and organized interface.
   - Integrate icons and visual feedback for a user-friendly experience.

2. **Event Handling**:
   - Implement signal-slot mechanisms to handle user interactions (e.g., button clicks) and update the GUI in response to real-time LPR results.

3. **Real-Time Updates**:
   - Use threading to process video frames without blocking the GUI, ensuring a smooth and responsive application.

```python
from PySide6.QtWidgets import QApplication, QMainWindow
# Import additional necessary modules and classes

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        # Initialize UI components and layout
        
    # Define methods to update UI components based on LPR results

if __name__ == "__main__":
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
```

## Integrating PyTorch Models

The LPR application integrates custom-trained PyTorch models for license plate detection and character recognition. These models are essential for the application's deep learning capabilities.

### Steps for Model Integration

1. **Model Loading**: Custom-trained YOLOv5 models are loaded into the application using PyTorch.
2. **Inference**: The application processes video frames in real-time, using the models to detect license plates and recognize characters.

### Key Implementation Details

- **Use of `torch.load`**: Load the trained model weights.
- **Preprocessing**: Frames from the video feed are preprocessed to match the input requirements of the models.
- **Detection and Recognition**: The models perform license plate detection and character recognition on the preprocessed frames.

```python
import torch
from models import CustomModel # Assuming a custom model class
from torchvision import transforms

# Load models
model_path = 'path/to/your_model.pth'
model = CustomModel()
model.load_state_dict(torch.load(model_path))
model.eval()

# Define preprocessing
preprocess = transforms.Compose([
    transforms.Resize((640, 640)),
    transforms.ToTensor(),
])

def infer(image):
    # Preprocess the image
    input_tensor = preprocess(image)
    input_batch = input_tensor.unsqueeze(0)  # Create a mini-batch as expected by the model
    
    with torch.no_grad():
        output = model(input_batch)
        # Process output for plate detection and character recognition
    
    return output

# Example usage
# image = PIL.Image.open("path/to/your_image.jpg")
# output = infer(image)
```
## Real-Time Video Processing

Implementing real-time video processing enables the LPR application to detect license plates from a webcam feed.

### Steps for Video Processing

1. **Capture Video Feed**: Utilize OpenCV to capture video from the webcam.
2. **Frame Processing**: Each frame is processed in real-time to detect license plates.
3. **Display Results**: The application displays the processed frames, highlighting detected license plates.

### Key Implementation Details

- **OpenCV for Video Capture**: Use `cv2.VideoCapture` to capture video.
- **Frame-by-Frame Processing**: Apply the PyTorch model to each frame for license plate detection.
- **Real-Time Display**: Processed frames are displayed with bounding boxes around detected plates.

```python
import cv2
import torch
from models import CustomModel # Assuming a custom model class

# Load the trained model (as described in previous sections)
model = CustomModel().eval()

# Initialize webcam
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Convert frame to PIL Image or apply necessary transformations
    # processed_frame = preprocess(frame)
    
    # Model inference
    # output = infer(processed_frame)
    
    # Display results
    # For simplicity, this just shows the original frame
    cv2.imshow('LPR Detection', frame)
    
    # Break loop with 'q' key
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

## Database Integration for Plate Recognition

Integrating a database allows the LPR application to store and manage recognized license plates, facilitating efficient tracking and management.

### Steps for Database Integration

1. **Database Setup**: Initialize a database schema to store license plate data.
2. **Data Insertion**: After recognizing a license plate, insert the data into the database.
3. **Data Retrieval**: Query the database for historical plate recognition data or for specific plate information.

### Key Implementation Details

- **Database Choice**: SQLite, MySQL, or PostgreSQL can be used depending on the application requirements.
- **SQLAlchemy for ORM**: Utilize SQLAlchemy for database operations to abstract SQL commands, making the code more maintainable and portable.

```python
from sqlalchemy import create_engine, Column, String, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

Base = declarative_base()

class LicensePlate(Base):
    __tablename__ = 'license_plates'
    id = Column(Integer, primary_key=True)
    plate_number = Column(String, unique=True)
    detection_time = Column(DateTime, default=datetime.datetime.utcnow)

# Database setup
engine = create_engine('sqlite:///lpr.db')
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

def insert_plate(plate_number):
    session = Session()
    new_plate = LicensePlate(plate_number=plate_number)
    session.add(new_plate)
    session.commit()
    session.close()

def query_plate(plate_number):
    session = Session()
    plate = session.query(LicensePlate).filter(LicensePlate.plate_number == plate_number).first()
    session.close()
    return plate

# Example usage
# insert_plate('ABC123')
# plate_info = query_plate('ABC123')
# if plate_info:
#     print(f"Plate {plate_info.plate_number} detected at {plate_info.detection_time}")
```


## User Interaction: Resident Management and Entry Logging

Enhancing the LPR application with user interaction features such as resident management and entry logging improves usability and functionality.

### Steps for Implementing User Interaction

1. **Resident Management**: Allows users to add, edit, or delete resident information, including linking license plates to specific residents.
2. **Entry Logging**: Automatically logs each license plate detection event with details such as time of detection and associated resident.

### Key Implementation Details

- **GUI Components**: Use PySide6 to create forms and dialogs for entering and editing resident information.
- **Database Operations**: Implement functions to handle database interactions for adding, updating, and removing resident data.
- **Real-Time Logging**: Incorporate functionality to log entry events in real-time as license plates are recognized.

```python
# Assuming SQLAlchemy models and session setup as previously outlined

class Resident(Base):
    __tablename__ = 'residents'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    license_plate = Column(String, unique=True)
    status = Column(String)  # e.g., Allowed, Not Allowed, Non-Registered

def add_resident(name, license_plate, status):
    session = Session()
    resident = Resident(name=name, license_plate=license_plate, status=status)
    session.add(resident)
    session.commit()
    session.close()

def log_entry(plate_number, detection_time):
    session = Session()
    resident = session.query(Resident).filter(Resident.license_plate == plate_number).first()
    if resident:
        entry = LicensePlate(plate_number=plate_number, detection_time=detection_time)
        session.add(entry)
        session.commit()
    session.close()

# GUI functionality for adding a resident
# This would be connected to a form in the PySide6 application
def on_add_resident_clicked():
    name = input("Enter resident's name: ")
    license_plate = input("Enter license plate: ")
    status = input("Enter status (Allowed, Not Allowed, Non-Registered): ")
    add_resident(name, license_plate, status)
# Example usage
# on_add_resident_clicked()
# log_entry('ABC123', datetime.datetime.now())
```


