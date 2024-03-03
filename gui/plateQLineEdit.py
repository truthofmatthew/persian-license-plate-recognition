from PySide6.QtCore import QRegularExpression
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import QLineEdit

space_codepoints = '\u0020\u2000-\u200F\u2028-\u202F'
persian_alpha_codepoints = '\u0621-\u0628\u062A-\u063A\u0641-\u0642\u0644-\u0648\u064E-\u0651\u0655\u067E\u0686\u0698\u06A9\u06AF\u06BE\u06CC'

punctuation_marks_codepoints = '\u060C\u061B\u061F\u0640\u066A\u066B\u066C'
additional_arabic_characters_codepoints = '\u0629\u0643\u0649-\u064B\u064D\u06D5'
persian_num_codepoints = '\u06F0-\u06F9'


class plateQLineEdit(QLineEdit):

    def __init__(self, arg__1, parent=None, *args, **kwargs):
        super().__init__(arg__1, parent, *args, **kwargs)

    def persianRegValidator(self, regExType):
        if regExType == 'fNameTextBox':
            return QRegularExpression('^[' + persian_alpha_codepoints + space_codepoints + ']*$')

        if regExType == 'lNameTextBox':
            return QRegularExpression('^[' + persian_alpha_codepoints + space_codepoints + ']*$')

        if regExType == 'plateTextNum_2':
            return QRegularExpression('^[' + persian_alpha_codepoints + space_codepoints + ']*$')

        if regExType == 'buildingTextBox':
            return QRegularExpression('^[' + persian_num_codepoints + '0-9' + ']*$')

        if regExType == 'numTextBox':
            return QRegularExpression('^[' + persian_num_codepoints + '0-9' + ']*$')

        if regExType == 'blockTextBox':
            return QRegularExpression('^[' + persian_num_codepoints + '0-9' + ']*$')

        if regExType == 'plateTextNum_1':
            return QRegularExpression('^[' + persian_num_codepoints + '0-9' + ']*$')

        if regExType == 'plateTextNum_3':
            return QRegularExpression('^[' + persian_num_codepoints + '0-9' + ']*$')

        if regExType == 'plateTextNum_4':
            return QRegularExpression('^[' + persian_num_codepoints + '0-9' + ']*$')

        if regExType == 'carModelTextBox':
            return QRegularExpression(
                '^[' + persian_alpha_codepoints + space_codepoints + persian_num_codepoints + '0-9' + ']*$')

    def keyPressEvent(self, event):
        regExField = self.persianRegValidator(self.objectName())
        validator = QRegularExpressionValidator(regExField)
        state = validator.validate(event.text(), 0)
        if state[0] == QRegularExpressionValidator.Acceptable or state[1] in ('\x08', '\r'):
            super().keyPressEvent(event)

    def focusInEvent(self, event):
        self.setStyleSheet(
            "background-color: rgb(153, 193, 241); border-color: rgb(0, 0, 0); border-width: 1px; border-style: solid;")
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self.setStyleSheet(
            "background-color: white; border-color: rgb(0, 0, 0); border-width: 1px; border-style: solid;")
        super().focusOutEvent(event)

    def is_not_blank(self, fieldString):
        return bool(fieldString and not fieldString.isspace())

    def getText(self):
        selfText = self.text()
        if self.is_not_blank(selfText):
            return selfText
        else:
            self.setFocus()
