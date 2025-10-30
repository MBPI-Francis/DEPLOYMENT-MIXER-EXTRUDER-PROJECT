# app/views/extruder_form/entry_form/widgets/numeric_line_edit.py

import locale
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QValidator, QDoubleValidator
from PyQt6.QtWidgets import QLineEdit


class QNumericLineEdit(QLineEdit):
    """
    A QLineEdit subclass that formats text with thousand separators
    and validates for numeric input (float/decimal).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        # Use system's locale for number formatting
        try:
            locale.setlocale(locale.LC_ALL, '')
        except locale.Error:
            # Fallback for systems where setting locale might fail
            pass

        # Validator to allow only numbers and a decimal point
        self.validator = QDoubleValidator()
        self.validator.setNotation(QDoubleValidator.Notation.StandardNotation)
        self.validator.setDecimals(2)
        self.setValidator(self.validator)

        self.textChanged.connect(self._format_text)
        self._is_formatting = False

    def _format_text(self, text: str):
        """Internal slot to apply thousand separators."""
        # Prevent recursive formatting loops
        if self._is_formatting:
            return

        self._is_formatting = True

        try:
            # Separate the integer part from the decimal part
            if '.' in text:
                integer_part, decimal_part = text.split('.', 1)
                decimal_part = '.' + decimal_part
            else:
                integer_part, decimal_part = text, ''

            # Remove existing commas to parse the number
            integer_part_no_commas = integer_part.replace(locale.getlocale()[1], '')

            if integer_part_no_commas:
                # Format the integer part with thousand separators
                num = int(integer_part_no_commas)
                formatted_integer = f"{num:,}"
            else:
                formatted_integer = '0' if '.' in text else ''

            # Recombine and set the text
            new_text = formatted_integer + decimal_part
            cursor_pos = self.cursorPosition()

            # Adjust cursor position to account for added/removed commas
            old_len = len(text)
            new_len = len(new_text)

            self.setText(new_text)
            self.setCursorPosition(cursor_pos + (new_len - old_len))

        except (ValueError, IndexError):
            # Handle cases where the text is not a valid number yet (e.g., "-")
            pass
        finally:
            self._is_formatting = False

    def get_value(self) -> float:
        """Returns the numeric value of the text, stripped of formatting."""
        text = self.text()
        if not text:
            return 0.0
        try:
            # Remove thousand separators for conversion
            return float(text.replace(',', ''))
        except ValueError:
            return 0.0