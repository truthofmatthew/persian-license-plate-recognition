import functools
import sys

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QTableWidgetItem, QApplication, QDialog
from qtpy.uic import loadUi

from configParams import Parameters
from database.db_entries_utils import dbGetAllEntries
from database.db_resident_utils import db_get_plate_status
from helper.gui_maker import create_image_label, on_label_double_click, create_styled_button, center_widget, \
    configure_edit_table_widget
from helper.text_decorators import convert_persian_to_english, split_string_language_specific, join_elements
from resident_view import residentView
from residents_edit import residentsAddNewWindow

params = Parameters()


class EnteriesWindow(QDialog):

    def __init__(self, isSearching=False, residnetPlate=''):
        super(EnteriesWindow, self).__init__()

        loadUi('./gui/edit_enteries.ui', self)
        self.setFixedSize(self.size())
        configure_edit_table_widget(self)
        if isSearching:
            self.residnetPlateEng = join_elements(
                convert_persian_to_english(split_string_language_specific(residnetPlate)))

            self.refresh_table(self.residnetPlateEng)
        else:
            self.refresh_table()

    def refresh_table(self, plateNum=''):

        plateNum = dbGetAllEntries(limit=100, whereLike=plateNum)
        self.tableWidget.setRowCount(len(plateNum))
        for index, entry in enumerate(plateNum):
            plateNum2 = join_elements(
                convert_persian_to_english(split_string_language_specific(entry.getPlateNumber(display=True))))
            statusNum = db_get_plate_status(plateNum2)

            self.tableWidget.setItem(index, 0, QTableWidgetItem(entry.getStatus(statusNum=statusNum)))
            self.tableWidget.setItem(index, 1, QTableWidgetItem(entry.getPlateNumber(display=True)))
            self.tableWidget.setItem(index, 2, QTableWidgetItem(entry.getTime()))
            self.tableWidget.setItem(index, 3, QTableWidgetItem(entry.getDate()))
            Image = QImage()
            Image.load(entry.getPlatePic())
            QcroppedPlate = QPixmap.fromImage(Image)

            item = create_image_label(QcroppedPlate)
            item.mousePressEvent = functools.partial(on_label_double_click, source_object=item)
            self.tableWidget.setCellWidget(index, 4, item)
            self.tableWidget.setRowHeight(index, 44)
            self.tableWidget.setItem(index, 5, QTableWidgetItem(entry.getCharPercent()))
            self.tableWidget.setItem(index, 6, QTableWidgetItem(entry.getPlatePercent()))

            infoBtnItem = create_styled_button('info')
            infoBtnItem.mousePressEvent = functools.partial(self.btnInfoClicked, source_object=infoBtnItem)
            self.tableWidget.setCellWidget(index, 7, infoBtnItem)
            if statusNum == 2:
                addBtnItem = create_styled_button('add')
                addBtnItem.mousePressEvent = functools.partial(self.btnAddClicked, source_object=addBtnItem)
                self.tableWidget.setCellWidget(index, 8, addBtnItem)
                infoBtnItem.setEnabled(False)

    def btnInfoClicked(self, event, source_object=None):
        r = self.tableWidget.currentRow()
        field1 = self.tableWidget.item(r, 1)
        residentView(residnetPlate=field1.text()).exec_()

    def btnAddClicked(self, event, source_object=None):
        r = self.tableWidget.currentRow()
        field1 = self.tableWidget.item(r, 1)
        self.residentAddEditWindow(isNew=True, residnetPlate=field1.text())

    def residentAddEditWindow(self, isEditing=False, isNew=False, isInfo=False, residnetPlate=None):

        residentWindow = None
        if residentWindow is None:
            residentWindow = residentsAddNewWindow(self, isEditing, isNew, isInfo, residnetPlate)
            residentWindow.exec_()
        else:
            residentWindow.close()  # Close window.
            residentWindow = None
        self.refresh_table()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = EnteriesWindow()
    window.setWindowTitle('لیست ترددهای شهرک')
    center_widget(window)
    window.show()
    sys.exit(app.exec_())
