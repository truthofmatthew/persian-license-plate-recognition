import sys
from pathlib import Path

import pandas as pd
import persian
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from persian import convert_fa_numbers
from qtpy.uic import loadUi

from configParams import getFieldNames
from database.classResidents import Resident
from database.db_resident_utils import insertResident, dbGetPlateExist, dbGetResidentDatasByPlate
from gui import plateQLineEdit
from helper.text_decorators import *

params = Parameters()


class residentsAddNewWindow(QDialog):

    def __init__(self, parent=None, isEditing=False, isNew=False, isInfo=False, residnetPlate='s'):

        super(residentsAddNewWindow, self).__init__()

        self.isEditing = isEditing
        self.isNew = isNew
        self.isInfo = isInfo
        self.residnetPlateEng = join_elements(convert_persian_to_english(split_string_language_specific(residnetPlate)))

        loadUi('./gui/residentNew.ui', self)
        self.setFixedSize(self.size())

        self.addResidentButton.clicked.connect(self.addUser)

        self.addResidentButton.setIcon(QPixmap("./icons/icons8-add-user-male-80.png"))
        self.addResidentButton.setIconSize(QSize(30, 30))

        self.plateTextView.setStyleSheet(
            f"""border-image: url("{Path().absolute()}/Templates/template-base.png") 0 0 0 0 stretch stretch;""")

        fieldsList = ['fName', 'lName', 'building', 'block', 'num', 'carModel', 'plateNum', 'status']

        fieldsList = getFieldNames(fieldsList)

        self.plateAlphabetComboBox.addItems(params.plateAlphabet.values())
        self.statusComboBox.addItems(list(params.fieldStatus.values())[:2])

        if self.isEditing:
            self.setWindowTitle('ویرایش ساکن')
            self.addResidentButton.setText('ثبت تغییرات')

            self.addResidentButton.setIcon(QPixmap("./icons/icons8-change-user-80.png"))
            self.addResidentButton.setIconSize(QSize(30, 30))
            self.editingResident = dbGetResidentDatasByPlate(self.residnetPlateEng)

            self.fNameTextBox.setText(self.editingResident.getFirstName())
            self.lNameTextBox.setText(self.editingResident.getLastName())
            self.buildingTextBox.setText(self.editingResident.getBuilding(appendBuilding=False))
            self.blockTextBox.setText(self.editingResident.getBlock())
            self.numTextBox.setText(self.editingResident.getNum())
            self.carModelTextBox.setText(self.editingResident.getCarModel())
            self.statusComboBox.setCurrentIndex(int(self.editingResident.getStatus(item=False)))

            self.plateTextNum_1.setText(self.editingResident.getPlateNumber(display=False)[:2])
            self.plateTextNum_3.setText(self.editingResident.getPlateNumber(display=False)[3:6])
            self.plateTextNum_4.setText(self.editingResident.getPlateNumber(display=False)[6:8])

            inv_map = {v: k for k, v in params.plateAlphabet.items()}
            plateAlpabet = inv_map[self.editingResident.getPlateNumber(display=False)[2]]
            self.plateAlphabetComboBox.setCurrentText(params.plateAlphabet[plateAlpabet])
            if isInfo:
                self.setWindowTitle('نمایش اطلاعات ساکن')
                self.addResidentButton.hide()
                self.setEnabled(False)

        if self.isNew:
            self.setWindowTitle('ثبت ساکن جدید')
            self.newResident = reshape_persian_text(residnetPlate)
            self.plateTextNum_1.setText(self.newResident[:2])
            self.plateTextNum_3.setText(self.newResident[3:6])
            self.plateTextNum_4.setText(self.newResident[6:8])
            self.plateAlphabetComboBox.setCurrentText(unicodedata.normalize('NFKC', self.newResident[2]))

    def addUser(self):

        fNameTextBox = self.fNameTextBox.getText()
        lNameTextBox = self.lNameTextBox.getText()
        buildingTextBox = self.buildingTextBox.getText()
        blockTextBox = self.blockTextBox.getText()
        numTextBox = self.numTextBox.getText()
        carModelTextBox = self.carModelTextBox.getText()

        inv_map = {v: k for k, v in params.plateAlphabet.items()}
        plateAlpabet = inv_map[self.plateAlphabetComboBox.currentText()]

        plateNumText = '{}{}{}{}'.format(self.plateTextNum_1.getText(), plateAlpabet, self.plateTextNum_3.getText(),
                                         self.plateTextNum_4.getText())
        plateNumTextBox = persian.convert_fa_numbers(plateNumText)

        statusTextBox = self.statusComboBox.currentText()
        statusIndex = self.statusComboBox.currentIndex()

        if fNameTextBox and lNameTextBox and buildingTextBox and blockTextBox and numTextBox and carModelTextBox and plateNumTextBox:

            resident = Resident(
                fNameTextBox,
                lNameTextBox,
                convert_fa_numbers(buildingTextBox),
                convert_fa_numbers(blockTextBox),
                convert_fa_numbers(numTextBox),
                carModelTextBox,
                plateNumTextBox,
                statusIndex,
            )

            if self.isEditing:
                insertResident(resident, True, self.residnetPlateEng)
                self.statusLabel.setText('ویرایش  ساکن انجام شد.')
                self.statusLabel.setStyleSheet("""background-color: rgb({}, {}, {});""".format(51, 209, 122))  # BLUE

                for item in self.findChildren(plateQLineEdit.plateQLineEdit):
                    item.setText('')

            elif not dbGetPlateExist(plateNumTextBox):
                insertResident(resident)
                self.statusLabel.setText('ساکن جدید ثبت شد.')
                self.statusLabel.setStyleSheet("""background-color: rgb({}, {}, {});""".format(51, 209, 122))  # GREEN
                for item in self.findChildren(plateQLineEdit.plateQLineEdit):
                    item.setText('')
            else:
                self.statusLabel.setText('پلاک تکراری است.')
                self.statusLabel.setStyleSheet("""
                background-color: rgb({}, {}, {});
                color: white;
                font-weight: bold;
                padding-right: 2px;
                padding-left: 2px;""".format(224, 27, 36))  # RED

            residentExport = {
                'fName': [fNameTextBox],
                'lName': [lNameTextBox],
                'building': [convert_fa_numbers(buildingTextBox)],
                'block': [convert_fa_numbers(blockTextBox)],
                'num': [convert_fa_numbers(numTextBox)],
                'carModel': [carModelTextBox],
                'plateNum': [plateNumTextBox],
                'status': [statusIndex],
            }

            df = pd.DataFrame(residentExport)
            df.to_csv(str(Path().absolute()) + '/base/residents.csv', header=False, index=False, mode='a',
                      encoding='utf-8')


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = residentsAddNewWindow()
    window.setWindowTitle('ثبت ساکن جدید')
    window.show()

    sys.exit(app.exec_())
