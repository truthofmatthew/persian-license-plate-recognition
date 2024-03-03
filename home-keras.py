import gc
import statistics
import sys
import time
import warnings

import torch
from PIL import ImageOps
from PySide6.QtCore import *
from PySide6.QtCore import Signal
from PySide6.QtWidgets import *
from keras.models import load_model
from qtpy.uic import loadUi

import ai.img_model as imgModel
from ai.img_model import *
from enteries_window import EnteriesWindow
from helper.gui_maker import *

warnings.filterwarnings("ignore", category=UserWarning)

params = Parameters()
videoSource = r"./anpr_video.mp4"  # input video path


def device():
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif torch.backends.mps.is_available():
        return torch.device("mps")
    else:
        return torch.device("cpu")


characterRecognitionModel = load_model('./hdf5/darkchar_recognition.h5')

char_id_dict = {v: k for k, v in params.char_dict.items()}


class IconDelegate(QStyledItemDelegate):
    def initStyleOption(self, option, index):
        super(IconDelegate, self).initStyleOption(option, index)
        option.decorationSize = option.rect.size()


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super(MainWindow, self).__init__()

        print(device())
        loadUi('./gui/main.ui', self)
        self.camImage = None
        self.plateImage = None
        self.userswindow = None
        self.enterieswindow = None
        self.startButton.clicked.connect(self.start_webcam)
        self.stopButton.clicked.connect(self.stop_webcam)
        self.usersListButton.clicked.connect(self.showUsersList)
        self.enteriesListButton.clicked.connect(self.showEnteriesList)
        self.Worker1 = Worker1()
        self.Worker1.ImageUpdate.connect(self.ImageUpdateSlot)
        self.Worker1.mainViewUpdate.connect(self.mainViewUpdateSlot)
        # getTableWidget(self)
        #
        # setTableWidgetData(self, dbRefreshTable())

        torch.cuda.empty_cache()
        gc.collect()

    def closeEvent(self, event):
        if self.userswindow is not None or self.enterieswindow is not None:
            self.userswindow.close()
            self.enterieswindow.close()
        event.accept()

    def showUsersList(self):
        pass
        # if self.userswindow is None:
        #     self.userswindow = UsersWindow()
        #     self.userswindow.show()
        # else:
        #     self.userswindow.close()  # Close window.
        #     self.userswindow = None

    def showEnteriesList(self):
        if self.enterieswindow is None:
            self.enterieswindow = EnteriesWindow()
            self.enterieswindow.show()
        else:
            self.enterieswindow.close()  # Close window.
            self.enterieswindow = None

    def mainViewUpdateSlot(self, mainViewImage):
        self.mainView.setScaledContents(True)
        self.mainView.setPixmap(QPixmap.fromImage(mainViewImage))

    def ImageUpdateSlot(self, croppedPlate, plateText, croppedChars, charConfAvg, plateConfAvg):

        if len(plateText) == 8:
            if charConfAvg >= 70:
                self.plateCroppedView.setScaledContents(True)
                self.plateCroppedView.setPixmap(QPixmap.fromImage(croppedChars))

                self.plateView.setScaledContents(True)

                self.plateView.setPixmap(QPixmap.fromImage(croppedPlate))

                # setTableWidgetData(self, dbRefreshTable())

                pltTextNum = convert_english_to_persian(plateText[:6])
                pltTextIR = convert_english_to_persian(plateText[6:])

                self.plateTextNum.setText(pltTextNum)
                self.plateTextIR.setText(pltTextIR)

                # status = dbPlatePermissionChecker((plate_text_cleaner(plateText)))
                # self.plateOwner(dbgetPlateOwnerName((plate_text_cleaner(plateText))))
                # self.platePermission(status)

                # dbEnteriesTime(plate_text_cleaner(plateText), charConfAvg, plateConfAvg, croppedPlate, status)

    def plateOwner(self, name):
        if name:
            self.plateOwnerNameView.setText(name)
        else:
            self.plateOwnerNameView.setText('')

    def platePermission(self, perm):
        if perm == 1:
            self.platePermissionView.setText('مجاز')
            self.platePermissionView.setStyleSheet("background-color: rgb(51, 209, 122);")
        elif perm == 0:
            self.platePermissionView.setText('غیر مجاز')
            self.platePermissionView.setStyleSheet("background-color: rgb(224, 27, 36);")
        elif perm == 2:
            self.platePermissionView.setText('ثبت نشده')
            self.platePermissionView.setStyleSheet("background-color: rgb(246, 211, 45);")
        else:
            self.platePermissionView.setText(' ')
            self.platePermissionView.setStyleSheet("background-color: rgba(0,0,0,0);")

    def start_webcam(self):
        if not self.Worker1.isRunning():
            self.Worker1.start()
        else:
            self.Worker1.unPause()

    def stop_webcam(self):
        self.Worker1.stop()


class Worker1(QThread):
    mainViewUpdate = Signal(QImage)
    ImageUpdate = Signal(QImage, list, QImage, int, int)
    TotalFramePass = 0

    def __init__(self, parent=None):
        super().__init__(parent)

    def run(self):

        prev_frame_time = 0

        self.charImageUpdate = []

        self.ThreadActive = True

        Capture = cv2.VideoCapture(videoSource)
        if videoSource != 0:
            total = int(Capture.get(cv2.CAP_PROP_FRAME_COUNT))
            if self.TotalFramePass <= total:
                Capture.set(1, self.TotalFramePass)
            else:
                self.TotalFramePass = 0
        while self.ThreadActive:
            self.TotalFramePass += 1

            success, frame = Capture.read()
            frame = frame[89: 308, 17: 383]
            resize = cv2.resize(frame, (960, 540))
            effect = ImageOps.autocontrast(imgModel.to_img_pil(resize), cutoff=1)
            resize = cv2.cvtColor(imgModel.to_img_opencv(effect), cv2.COLOR_BGR2RGB)

            if success:

                modelResult = model(resize)
                platesResult = np.array(modelResult.pandas().xyxy[0])
                for plate in platesResult:

                    plateConf = (int(plate[-3] * 100))
                    if plateConf >= 90:

                        cv2.rectangle(resize, (int(plate[0]) - 3, int(plate[1]) - 3),
                                      (int(plate[2]) + 3, int(plate[3]) + 3),
                                      color=(0, 0, 255), thickness=3)

                        croppedPlate = resize[int(plate[1]): int(plate[3]), int(plate[0]): int(plate[2])]
                        plateText, char_detected, out_img, croppedChars, charConfAvg = self.detect(croppedPlate, 0.5,
                                                                                                   char_id_dict)
                        if plateText:
                            croppedChars = QImage(croppedChars, croppedChars.shape[1],
                                                  croppedChars.shape[0],
                                                  QImage.Format_RGB888)
                        croppedPlate = cv2.resize(croppedPlate, (600, 132))
                        croppedPlateImage = QImage(croppedPlate.data, croppedPlate.shape[1], croppedPlate.shape[0],
                                                   QImage.Format_RGB888)
                        self.ImageUpdate.emit(croppedPlateImage, plateText, croppedChars, charConfAvg, plateConf)

                new_frame_time = time.time()
                fps = 1 / (new_frame_time - prev_frame_time)
                prev_frame_time = new_frame_time

                imgModel.draw_fps(resize, fps)
                mainFrame = QImage(resize.data, resize.shape[1], resize.shape[0],
                                   QImage.Format_RGB888)

                self.mainViewUpdate.emit(mainFrame)

    def listAverage(self, lst):
        return sum(lst) / len(lst)

    def detect(self, img_path, conf_th, char_id_dict):

        img_res = []
        conf_avg = []
        charConfAvg = []
        det = modelCharX(img_path)
        det = (det.pred[0]).tolist()
        plate_img = img_path
        sorted_det = sorted(det, key=lambda x: (x[0]))
        plate_char = []
        for plate in sorted_det:
            conf = plate[4]
            if conf > conf_th:
                plate_char.append(char_id_dict[str(int(plate[5]))])
                conf_avg.append(int(plate[4] * 100))

                croppedChar = plate_img[int(plate[1]): int(plate[3]), int(plate[0]): int(plate[2])]
                resize_char = cv2.resize(croppedChar, (75, 75))

                img_res.append(resize_char)

        croppedChars = imgModel.concat_images(img_res, 'horizontal')
        if conf_avg:
            charConfAvg = math.ceil(statistics.mean(conf_avg))

        return plate_char, sorted_det, plate_img, croppedChars, charConfAvg

    def unPause(self):
        self.ThreadActive = True

    def stop(self):
        self.ThreadActive = False

    def fix_dimension(self, img):
        new_img = np.zeros((75, 75, 3))
        for i in range(3):
            new_img[:, :, i] = img
        return new_img

    def detectCharacters(self):
        dic = {}
        output = []
        sa = []

        for i, c in enumerate(params.label_map):
            dic[i] = c

        for i, ch in enumerate(self.charImageUpdate):  # iterating over the characters
            if np.any(ch):
                resize_char = cv2.resize(ch, (75, 75), interpolation=cv2.INTER_AREA)
                img = self.fix_dimension(resize_char)
                sa.append(resize_char)
                img = img.reshape(1, 75, 75, 3)  # preparing image for the model
                y_ = characterRecognitionModel.predict(img,
                                                       use_multiprocessing=True,
                                                       batch_size=32,
                                                       verbose=0,
                                                       )[0]  # predicting the class

                classes_y = np.argmax(y_, axis=0)

                character = dic[classes_y]

                output.append(character)  # storing the result in a list
        vis = cv2.hconcat(sa)

        return output, vis


if __name__ == "__main__":
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)

    app = QtWidgets.QApplication(sys.argv)
    window = MainWindow()

    window.show()
    sys.exit(app.exec_())
