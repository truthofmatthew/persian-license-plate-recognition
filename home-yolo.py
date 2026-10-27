# home-yolo.py

"""
Main script to run the License Plate Recognition (LPR) application: camera -> plate detector
-> character detector -> resident lookup -> entry log. GUI in PySide6; inference through
plpr.Engine (ONNX Runtime, no PyTorch). Settings come from config.ini (see config.example.ini).
"""

import functools
import sys
import time
import warnings
from pathlib import Path

import cv2
from PySide6 import QtWidgets
from PySide6.QtCore import QCoreApplication, QSize, Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QGraphicsScene, QTableWidgetItem
from qtpy.uic import loadUi

from ai.img_model import draw_fps
from configParams import Parameters, capture_source
from database.db_entries_utils import db_entries_time, dbGetAllEntries
from database.db_resident_utils import db_get_plate_owner_name, db_get_plate_status
from enteries_window import EnteriesWindow
from helper.gui_maker import (
    center_widget,
    configure_main_table_widget,
    create_image_label,
    create_styled_button,
    get_status_color,
    get_status_text,
    on_label_double_click,
)
from helper.text_decorators import convert_english_to_persian, convert_persian_to_english, join_elements, split_string_language_specific
from plpr import Engine, PlateTracker
from resident_view import residentView
from residents_edit import residentsAddNewWindow
from residents_main import residentsWindow

warnings.filterwarnings("ignore", category=UserWarning)
params = Parameters()
engine = Engine(params.onnx_dir)


def to_qimage(bgr):
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    # copy: the QImage must not point into a numpy buffer that gets freed
    return QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format_RGB888).copy()


def plate_halves(plate):
    """Display strings for the two boxes of the plate widget: '12 B 345' and the region code."""
    codes = list(plate.left) + [plate.letter] + list(plate.middle)
    return convert_english_to_persian(codes, display=True), convert_english_to_persian(plate.region, display=True)


class MainWindow(QtWidgets.QMainWindow):
    """
    The main window class of the LPR application.
    It sets up the user interface and connects signals and slots.
    """

    def __init__(self):
        """
       Initializes the main window and its components.
       """
        super().__init__()
        loadUi('./gui/mainFinal.ui', self)
        self.setFixedSize(self.size())

        self.camImage = None
        self.plateImage = None
        self.residentsWindow = None
        self.enterieswindow = None
        self.startButton.clicked.connect(self.start_webcam)
        self.stopButton.clicked.connect(self.stop_webcam)
        self.usersListButton.clicked.connect(self.show_residents_list)
        self.enteriesListButton.clicked.connect(self.show_entries_list)

        exitAct = QAction("Exit", self)
        exitAct.setShortcut("Ctrl+Q")

        self.startButton.setIcon(QPixmap("./icons/icons8-play-80.png"))
        self.startButton.setIconSize(QSize(40, 40))

        self.stopButton.setIcon(QPixmap("./icons/icons8-stop-80.png"))
        self.stopButton.setIconSize(QSize(40, 40))

        self.usersListButton.setIcon(QPixmap("./icons/icons8-people-64.png"))
        self.usersListButton.setIconSize(QSize(40, 40))

        self.enteriesListButton.setIcon(QPixmap("./icons/icons8-car-80.png"))
        self.enteriesListButton.setIconSize(QSize(40, 40))

        self.settingsButton.setIcon(QPixmap("./icons/icons8-tools-80.png"))
        self.settingsButton.setIconSize(QSize(40, 40))

        self.plateTextView.setStyleSheet(
            f"""border-image: url("{Path().absolute()}/Templates/template-base.png") 0 0 0 0 stretch stretch;""")

        self.Worker1 = Worker1()
        self.Worker1.plateDataUpdate.connect(self.on_plate_preview)
        self.Worker1.plateFinished.connect(self.on_plate_data_update)
        self.Worker1.mainViewUpdate.connect(self.on_main_view_update)

        self.Worker2 = Worker2()
        self.Worker2.mainTableUpdate.connect(self.refresh_table)
        self.Worker2.start()

        configure_main_table_widget(self)
        self.scene = QGraphicsScene()
        # one pixmap item, updated in place: adding a pixmap per frame grew memory without bound
        self.frameItem = self.scene.addPixmap(QPixmap())
        self.scene.setSceneRect(0, 0, 960, 540)
        self.gv.setScene(self.scene)
        self.gv.setRenderHints(QPainter.Antialiasing)

    def refresh_table(self, plateNum=''):

        # Get all entries from the database with a limit of 10 and where the plate number is like the given plate number
        plateNum = dbGetAllEntries(limit=10, whereLike=plateNum)
        # Set the number of rows in the table widget to the length of the plate number list
        self.tableWidget.setRowCount(len(plateNum))
        # Iterate through the plate number list
        for index, entry in enumerate(plateNum):
            # Get the plate number in English
            plateNum2 = join_elements(
                convert_persian_to_english(split_string_language_specific(entry.getPlateNumber(display=True))))
            # Get the plate status from the database
            statusNum = db_get_plate_status(plateNum2)
            # Set the status of the entry in the table widget
            self.tableWidget.setItem(index, 0, entry.getStatus(statusNum=statusNum))
            # Set the plate number of the entry in the table widget
            self.tableWidget.setItem(index, 1, QTableWidgetItem(entry.getPlateNumber(display=True)))
            # Set the time of the entry in the table widget
            self.tableWidget.setItem(index, 2, QTableWidgetItem(entry.getTime()))
            # Set the date of the entry in the table widget
            self.tableWidget.setItem(index, 3, QTableWidgetItem(entry.getDate()))

            # Load the plate picture
            Image = QImage()
            Image.load(entry.getPlatePic())
            # Create a QcroppedPlate from the Image
            QcroppedPlate = QPixmap.fromImage(Image)

            # Create an image label from the QcroppedPlate
            item = create_image_label(QcroppedPlate)
            # Set a mouse press event to on_label_double_click
            item.mousePressEvent = functools.partial(on_label_double_click, source_object=item)
            # Set the cell widget of the table widget to the image label
            self.tableWidget.setCellWidget(index, 4, item)
            # Set the row height of the table widget to 44
            self.tableWidget.setRowHeight(index, 44)

            # Create an info button
            infoBtnItem = create_styled_button('info')
            # Set a mouse press event to on_info_button_clicked
            infoBtnItem.mousePressEvent = functools.partial(self.on_info_button_clicked, source_object=infoBtnItem)
            # Set the cell widget of the table widget to the info button
            self.tableWidget.setCellWidget(index, 5, infoBtnItem)

            # Create an add button
            addBtnItem = create_styled_button('add')
            # Set a mouse press event to on_add_button_clicked
            addBtnItem.mousePressEvent = functools.partial(self.on_add_button_clicked, source_object=addBtnItem)
            # Set the cell widget of the table widget to the add button
            self.tableWidget.setCellWidget(index, 6, addBtnItem)
            # Disable the add button
            addBtnItem.setEnabled(False)

            # If the status is 2, enable the add button and disable the info button
            if statusNum == 2:
                addBtnItem.setEnabled(True)
                infoBtnItem.setEnabled(False)

    def on_info_button_clicked(self, event, source_object=None):
        r = self.tableWidget.currentRow()
        field1 = self.tableWidget.item(r, 1)
        residentView(residnetPlate=field1.text()).exec()

    def on_add_button_clicked(self, event, source_object=None):
        r = self.tableWidget.currentRow()
        field1 = self.tableWidget.item(r, 1)
        residentAddWindow = residentsAddNewWindow(self, isNew=True,
                                                  residnetPlate=field1.text())
        residentAddWindow.exec()
        self.refresh_table()

    def closeEvent(self, event):
        """### IT OVERRIDES closeEvent from PySide6"""
        self.Worker1.stop()
        self.Worker1.wait(2000)
        if self.residentsWindow is not None and self.enterieswindow is not None:
            self.residentsWindow.close()
            self.enterieswindow.close()  # TODO if not openned any window will crash
        event.accept()

    def show_residents_list(self):
        residentsMain = residentsWindow()
        center_widget(residentsMain)
        residentsMain.exec()
        self.Worker2.start()

    def show_entries_list(self):
        enterieswindow = EnteriesWindow()
        center_widget(enterieswindow)
        enterieswindow.exec()

    def on_main_view_update(self, mainViewImage):
        self.frameItem.setPixmap(QPixmap.fromImage(mainViewImage))
        self.gv.fitInView(self.scene.sceneRect())

    def show_plate(self, cropped_plate: QImage, plate) -> tuple[str, str]:
        self.plate_view.setScaledContents(True)
        self.plate_view.setPixmap(QPixmap.fromImage(cropped_plate))
        plt_text_num, plt_text_ir = plate_halves(plate)
        self.plate_text_num.setText(plt_text_num)
        self.plate_text_ir.setText(plt_text_ir)
        return plt_text_num, plt_text_ir

    def on_plate_preview(self, cropped_plate: QImage, plate, char_conf: int, plate_conf: int) -> None:
        """Every processed frame: just show what the camera reads right now."""
        self.show_plate(cropped_plate, plate)

    def on_plate_data_update(self, cropped_plate: QImage, plate, char_conf_avg: int, plate_conf_avg: int) -> None:
        """Once per vehicle (finished track): look up the resident, log the entry, notify the service."""
        plt_text_num, plt_text_ir = self.show_plate(cropped_plate, plate)
        status = db_get_plate_status(plate.key)
        self.update_plate_owner(db_get_plate_owner_name(plate.key))
        self.update_plate_permission(status)

        external_service_data = {
            'plate_number': plt_text_num + '-' + plt_text_ir,
            'image': cropped_plate
        }
        db_entries_time(plate.key, char_conf_avg, plate_conf_avg, cropped_plate, status,
                        external_service_data=external_service_data)
        self.Worker2.start()

    def update_plate_owner(self, name):
        if name:
            self.plate_owner_name_view.setText(name)
        else:
            self.plate_owner_name_view.setText('')

    def update_plate_permission(self, status):
        r, g, b = get_status_color(status)
        statusText = get_status_text(status)

        self.plate_permission_view.setText(statusText)
        self.plate_permission_view.setStyleSheet(f"background-color: rgb({r}, {g}, {b});")

    def start_webcam(self):
        if not self.Worker1.isRunning():
            self.Worker1.start()
        else:
            self.Worker1.unPause()

    def stop_webcam(self):
        self.Worker1.stop()


class Worker1(QThread):
    """
    Worker thread that grabs frames, reads plates on every Nth frame and tracks them,
    so a passing car produces one plateFinished signal instead of one per frame.
    """
    mainViewUpdate = Signal(QImage)
    plateDataUpdate = Signal(QImage, object, int, int)  # live preview: crop, PlateNumber, char %, plate %
    plateFinished = Signal(QImage, object, int, int)  # once per vehicle, same arguments
    TotalFramePass = 0

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        self.prepare_capture()
        while self.ThreadActive:
            success, frame = self.Capture.read()
            if not success:
                if params.source == 'video':
                    break  # end of file
                time.sleep(0.05)
                continue
            self.process_frame(frame)
            self.manageFrameRate()
        self.Capture.release()
        self.finish(self.tracker.flush())  # car still in view when the video ended or Stop was pressed

    def prepare_capture(self):
        self.prev_frame_time = 0
        self.ThreadActive = True
        self.reads = []
        self.bestCrops = {}  # track id -> (crop QImage, PlateRead) with the highest char confidence
        self.tracker = PlateTracker(min_hits=params.min_hits)
        self.Capture = cv2.VideoCapture(capture_source(params))
        self.adjust_video_position()

    def adjust_video_position(self):
        if params.source == 'video':
            total = int(self.Capture.get(cv2.CAP_PROP_FRAME_COUNT))
            self.TotalFramePass = 0 if self.TotalFramePass >= total else self.TotalFramePass
            self.Capture.set(cv2.CAP_PROP_POS_FRAMES, self.TotalFramePass)

    def process_frame(self, frame):
        self.TotalFramePass += 1
        frame = cv2.resize(frame, (960, 540))
        if self.TotalFramePass % params.process_every_n == 0:
            self.reads = engine.read(frame, params.plate_conf, params.char_conf)
            self.track(frame, self.reads)
        for r in self.reads:  # skipped frames show the last boxes
            x1, y1, x2, y2 = r.box
            cv2.rectangle(frame, (x1 - 3, y1 - 3), (x2 + 3, y2 + 3), color=(0, 0, 255), thickness=3)
        self.emitFrame(frame)

    def track(self, frame, reads):
        crops = {}
        for r in reads:
            if r.plate is None:  # not a complete 8-symbol plate
                continue
            x1, y1, x2, y2 = r.box
            crop = to_qimage(cv2.resize(frame[y1:y2, x1:x2], (600, 132)))
            crops[r.box] = (crop, r)
            self.plateDataUpdate.emit(crop, r.plate, round(r.char_conf * 100), round(r.plate_conf * 100))

        done = self.tracker.update(reads)
        for t in self.tracker.tracks:
            if t.missed == 0 and t.box in crops:
                best = self.bestCrops.get(t.id)
                if best is None or crops[t.box][1].char_conf >= best[1].char_conf:
                    self.bestCrops[t.id] = crops[t.box]
        self.finish(done)

    def finish(self, done):
        for t in done:
            if t.id in self.bestCrops:
                crop, r = self.bestCrops[t.id]
                self.plateFinished.emit(crop, t.best, round(r.char_conf * 100), round(t.plate_conf * 100))
        live = {t.id for t in self.tracker.tracks}
        self.bestCrops = {k: v for k, v in self.bestCrops.items() if k in live}

    def manageFrameRate(self):
        new_frame_time = time.time()
        fps = 1 / max(new_frame_time - self.prev_frame_time, 1e-6)
        self.prev_frame_time = new_frame_time
        self.currentFPS = fps  # Save the current FPS for later drawing on the frame

    def emitFrame(self, frame):
        if hasattr(self, 'currentFPS'):  # Check if currentFPS has been calculated
            draw_fps(frame, self.currentFPS)
        self.mainViewUpdate.emit(to_qimage(frame))

    def unPause(self):
        self.ThreadActive = True

    def stop(self):
        self.ThreadActive = False


class Worker2(QThread):
    mainTableUpdate = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):
        self.mainTableUpdate.emit()
        time.sleep(.5)

    def unPause(self):
        self.ThreadActive = True

    def stop(self):
        self.ThreadActive = False


if __name__ == "__main__":
    QCoreApplication.setAttribute(Qt.AA_ShareOpenGLContexts)  # must be set before QApplication exists (issue #20)
    app = QtWidgets.QApplication(sys.argv)

    app.setStyle('Windows')

    window = MainWindow()
    window.setWindowIcon(QIcon("./icons/65th_xs.png"))
    window.setIconSize(QSize(16, 16))
    center_widget(window)
    window.show()
    sys.exit(app.exec())
