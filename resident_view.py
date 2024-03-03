import sys

from PySide6.QtWidgets import *
from qtpy.uic import loadUi

from database.db_resident_utils import dbGetResidentDatasByPlate
from helper.gui_maker import get_status_text
from helper.text_decorators import *

params = Parameters()


class residentView(QDialog):

    def __init__(self, parent=None, residnetPlate='s'):
        super(residentView, self).__init__()

        loadUi('./gui/residentView.ui', self)
        self.setFixedSize(self.size())
        editingResident = dbGetResidentDatasByPlate(
            join_elements(convert_persian_to_english(split_string_language_specific(residnetPlate))))

        self.labelFname.setText(editingResident.getFirstName())
        self.labelLname.setText(editingResident.getLastName())
        self.labelBuilding.setText(editingResident.getBuilding(appendBuilding=True))
        self.labelBlock.setText(editingResident.getBlock())
        self.labelNum.setText(editingResident.getNum())
        self.labelCarModel.setText(editingResident.getCarModel())
        self.labelStatus.setText(get_status_text(editingResident.getStatus(item=False)))

        self.labelPlateNum.setText(editingResident.getPlateNumber(display=True))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = residentView()
    window.setWindowTitle('ثبت ساکن جدید')
    window.show()

    sys.exit(app.exec_())
