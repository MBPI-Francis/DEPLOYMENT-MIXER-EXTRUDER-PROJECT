# app/views/extruder_form/entry_form/widgets/smart_date_edit.py

from PyQt6.QtCore import QDate, Qt
from PyQt6.QtWidgets import QDateEdit, QToolTip
from PyQt6.QtGui import QKeyEvent, QFocusEvent
from datetime import datetime



class SmartDateEdit(QDateEdit):
    """
    A QDateEdit subclass with intelligent, as-you-type date formatting
    and completion for rapid keyboard entry.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCalendarPopup(True)
        self.setDisplayFormat("MM/dd/yyyy")

        # Internal buffer to store raw numeric input
        self._raw_text = ""

        # Set a null date, which makes the field blank
        self.setDate(QDate())

        # When the date is changed (e.g., by the calendar), sync our buffer
        self.dateChanged.connect(self._update_buffer_from_date)

    def wheelEvent(self, event):
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent):
        """Overrides key press to capture input and apply live formatting."""
        key = event.key()

        if Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
            if len(self._raw_text) < 8:
                self._raw_text += event.text()
                self._reformat_text()
            return  # Absorb the event

        elif key == Qt.Key.Key_Backspace:
            self._raw_text = self._raw_text[:-1]
            self._reformat_text()
            return  # Absorb the event

        elif key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
            self._parse_and_set_date()
            # Pass the event to the parent to handle tabbing, etc.
            super().keyPressEvent(event)
        else:
            # For all other keys (arrows, etc.), use default behavior
            super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent):
        """Parse the buffer when the widget loses focus."""
        self._parse_and_set_date()
        super().focusOutEvent(event)

    def clear(self):
        """Overrides clear to reset the internal buffer and the date."""
        self._raw_text = ""
        self.setDate(QDate())
        super().clear()

    def _reformat_text(self):
        """Formats the raw numeric text with slashes as the user types."""
        if not self._raw_text:
            self.lineEdit().clear()
            return

        parts = []
        if len(self._raw_text) > 0:
            parts.append(self._raw_text[:2])
        if len(self._raw_text) > 2:
            parts.append(self._raw_text[2:4])
        if len(self._raw_text) > 4:
            parts.append(self._raw_text[4:])

        formatted_text = "/".join(parts)
        self.lineEdit().setText(formatted_text)

    def _update_buffer_from_date(self, date: QDate):
        """When the date is set externally (e.g., calendar), update the buffer."""
        if date.isNull():
            self._raw_text = ""
        else:
            self._raw_text = date.toString("MMddyyyy")

    def _parse_and_set_date(self):
        """
        Parses the final raw text buffer and updates the QDate object.
        This contains the core formatting logic.
        """
        if not self._raw_text:
            self.setDate(QDate())
            return

        text = self._raw_text
        current_year = QDate.currentDate().year()
        parsed_date = None

        try:
            # Interpret flexible lengths
            if len(text) in [3, 7]:  # MDD or MDDYYYY
                text = '0' + text

            if len(text) == 4:  # MMDD -> MMDD/YYYY (current year)
                dt = datetime.strptime(text, "%m%d")
                parsed_date = QDate(current_year, dt.month, dt.day)
            elif len(text) == 6:  # MMDDYY -> MMDD/YYYY
                dt = datetime.strptime(text, "%m%d%y")
                parsed_date = QDate(dt.year, dt.month, dt.day)
            elif len(text) == 8:  # MMDDYYYY
                dt = datetime.strptime(text, "%m%d%Y")
                parsed_date = QDate(dt.year, dt.month, dt.day)

            if parsed_date and parsed_date.isValid():
                self.setDate(parsed_date)
            else:
                self._show_error_tooltip("Invalid date entered.")
                self.clear()

        except ValueError:
            self._show_error_tooltip("Invalid date format.")
            self.clear()

    def _show_error_tooltip(self, message: str):
        """Shows a brief validation error tooltip near the widget."""
        pos = self.mapToGlobal(self.rect().bottomLeft())
        QToolTip.showText(pos, message, self, self.rect(), 2000)