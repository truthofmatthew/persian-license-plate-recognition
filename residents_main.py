import functools
import sys

from PySide6 import QtWidgets, QtCore
from PySide6.QtCore import *
from PySide6.QtGui import *
from PySide6.QtWidgets import *
from qtpy.uic import loadUi

from configParams import getFieldNames
from database.db_resident_utils import dbGetAllResidents, dbRemoveResident
from enteries_window import EnteriesWindow
from helper.gui_maker import CenterAlignDelegate, create_styled_button, center_widget
from helper.text_decorators import *
from residents_edit import residentsAddNewWindow

params = Parameters()


class residentsWindow(QDialog):

    def __init__(self):
        super(residentsWindow, self).__init__()

        loadUi('./gui/residents.ui', self)
        self.setFixedSize(self.size())
        self.residentWindow = None
        self.addResidentButton.clicked.connect(self.residentAddEditWindow)
        self.addResidentButton.setIcon(QPixmap("./icons/icons8-add-user-male-80.png"))
        self.addResidentButton.setStyleSheet("text-align:right; padding-right: 25px; qproperty-iconSize: 25px;")

        fieldsList = ['fName',
                      'lName',
                      'building',
                      'block',
                      'num',
                      'carModel',
                      'plateNum',
                      'status',
                      'editBtn',
                      'deleteBtn',
                      'findEntriesBtn']
        fieldsList = getFieldNames(fieldsList)

        self.tableWidget.setColumnCount(len(fieldsList))
        self.tableWidget.setRowCount(-1)
        self.tableWidget.setHorizontalHeaderLabels(fieldsList)
        self.tableWidget.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

        self.tableWidget.setLayoutDirection(Qt.RightToLeft)
        self.tableWidget.setSortingEnabled(True)

        delegate = CenterAlignDelegate(self.tableWidget)
        self.tableWidget.setItemDelegate(delegate)
        self.tableWidget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tableWidget.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.refresh_table()

        self.searchTextBox.textChanged.connect(self.searchLastName)

    def mainViewUpdateSlot(self, mainViewImage):
        self.mainView.setScaledContents(True)
        self.mainView.setPixmap(QPixmap.fromImage(mainViewImage))

    def btnDeleteClicked(self, event, source_object=None):
        indexes = self.tableWidget.selectionModel().selectedRows(column=6)
        model = self.tableWidget.model()
        role = Qt.DisplayRole  # or Qt.DecorationRole
        for index in indexes:
            selectedCellPlate = model.data(index, role)

            messageBox = QMessageBox(self)
            messageBox.setWindowTitle("حذف پلاک ساکن از لیست")
            messageBox.setIconPixmap(
                QPixmap("./icons/icons8-high-risk-80.png").scaled(50, 50, QtCore.Qt.KeepAspectRatio))
            messageBox.setText("آیا از حذف " + selectedCellPlate + " اطمینان دارید؟ ")

            buttonoptionA = messageBox.addButton("بله حذف شود", QMessageBox.YesRole)
            buttonoptionB = messageBox.addButton("خیر", QMessageBox.NoRole)
            messageBox.setDefaultButton(buttonoptionA)
            messageBox.exec_()

            if messageBox.clickedButton() == buttonoptionA:
                print(selectedCellPlate + ' حذف شد. ')
                dbRemoveResident(
                    join_elements(convert_persian_to_english(split_string_language_specific(selectedCellPlate))))
                self.tableWidget.removeRow(index.row())
        self.tableWidget.setRowCount(self.tableWidget.rowCount())

    def searchLastName(self):
        searchText = self.searchTextBox.toPlainText()
        self.refresh_table(searchText)

    def refresh_table(self, lastName=''):
        residentsList = dbGetAllResidents(whereLike=f"{lastName}")
        self.tableWidget.setRowCount(len(residentsList))
        for index, resident in enumerate(residentsList):
            self.tableWidget.setItem(index, 0, QTableWidgetItem(resident.getFirstName()))
            self.tableWidget.setItem(index, 1, QTableWidgetItem(resident.getLastName()))
            self.tableWidget.setItem(index, 2, QTableWidgetItem(resident.getBuilding()))
            self.tableWidget.setItem(index, 3, QTableWidgetItem(resident.getBlock()))
            self.tableWidget.setItem(index, 4, QTableWidgetItem(resident.getNum()))
            self.tableWidget.setItem(index, 5, QTableWidgetItem(resident.getCarModel()))
            self.tableWidget.setItem(index, 6, QTableWidgetItem(resident.getPlateNumber(display=True)))
            self.tableWidget.setItem(index, 7, resident.getStatus())

            editBtnItem = create_styled_button('edit')
            editBtnItem.mousePressEvent = functools.partial(self.btnEditClicked, source_object=editBtnItem)
            self.tableWidget.setCellWidget(index, 8, editBtnItem)
            deleteBtnItem = create_styled_button('delete')
            deleteBtnItem.mousePressEvent = functools.partial(self.btnDeleteClicked, source_object=deleteBtnItem)
            self.tableWidget.setCellWidget(index, 9, deleteBtnItem)
            self.tableWidget.setRowHeight(index, 40)

            searchBtnItem = create_styled_button('search')
            searchBtnItem.mousePressEvent = functools.partial(self.btnSearchClicked, source_object=searchBtnItem)
            self.tableWidget.setCellWidget(index, 10, searchBtnItem)
            self.tableWidget.setRowHeight(index, 40)

    def btnSearchClicked(self, event, source_object=None):
        r = self.tableWidget.currentRow()
        field1 = self.tableWidget.item(r, 6)

        enteriesWindow = EnteriesWindow(isSearching=True, residnetPlate=field1.text())
        enteriesWindow.exec_()

    def btnEditClicked(self, event, source_object=None):
        r = self.tableWidget.currentRow()
        field1 = self.tableWidget.item(r, 6)
        self.residentAddEditWindow(isEditing=True, residnetPlate=field1.text())

    def residentAddEditWindow(self, isEditing=False, residnetPlate=None):

        residentWindow = None
        if residentWindow is None:
            residentWindow = residentsAddNewWindow(self, isEditing, isNew=False, isInfo=False,
                                                   residnetPlate=residnetPlate)

            residentWindow.exec_()
        else:
            residentWindow.close()  # Close window.
            residentWindow = None
        self.refresh_table()

    def on_selectionChanged(self, selected, deselected):

        for ix in selected.indexes():
            if ix.row().isSelected():
                print('Selected Cell Location Row: {0}, Column: {1}'.format(ix.row(), ix.column()))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = residentsWindow()
    window.setWindowTitle('لیست ساکنین شهرک')
    center_widget(window)
    window.show()
    sys.exit(app.exec_())
