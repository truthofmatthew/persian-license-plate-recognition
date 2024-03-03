from PySide6.QtGui import QColor
from PySide6.QtWidgets import QTableWidgetItem

from helper.gui_maker import get_status_text, get_status_color
from helper.text_decorators import convert_english_to_persian, split_string_language_specific


class Resident:

    def __init__(self, fName, lName, building, block, num, carModel, plateNum, status
                 ):
        self.fName = fName
        self.lName = lName
        self.building = building
        self.block = block
        self.num = num
        self.carModel = carModel
        self.plateNum = plateNum
        self.status = status

    def getFirstName(self):
        return self.fName

    def getLastName(self):
        return self.lName

    def getFullName(self):
        return '{} {}'.format(self.fName, self.lName)

    def getBuilding(self, appendBuilding=True):
        if appendBuilding:
            return '{}{}'.format(self.building, ' طبقه ')
        else:
            return str(self.building)

    def getBlock(self):
        return str(self.block)

    def getNum(self):
        return str(self.num)

    def getCarModel(self):
        return self.carModel

    def getPlateNumber(self, display=False):
        return convert_english_to_persian(split_string_language_specific(self.plateNum), display)

    def getStatus(self, item=True):
        if item:
            statusData = self.status
            r, g, b = get_status_color(statusData)
            statusText = get_status_text(statusData)
            statusItem = QTableWidgetItem(statusText)
            statusItem.setBackground(QColor(r, g, b))
            return statusItem
        return str(self.status)
