# A CUSTOM LINE EDITS
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtGui import QMouseEvent
from typing import override

class LotNumberLineEdit(QLineEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        # Removed the NoSpaceValidator since input mask handles formatting
        self.setMaxLength(11)
    
    @override
    def keyPressEvent(self, event):
        if event.text().isalpha():
            upper_char = event.text().upper()
            self.insert(upper_char)
        else:
            super().keyPressEvent(event)

    @override
    def mousePressEvent(self, event: QMouseEvent):
        super().mousePressEvent(event)

        if not self.text():
            self.setCursorPosition(0)
        else:
            self.setCursorPosition(len(self.text()))
    
    @override
    def clear(self):
        """Override clear to properly handle input mask"""
        self.setInputMask("")  # Remove mask temporarily
        super().clear()
        # Restore default mask
        self.setInputMask("0000AA; ")
        self.setPlaceholderText("e.g.1234AB or 1234AB-5678CD")
        
        self.setCursorPosition(0)