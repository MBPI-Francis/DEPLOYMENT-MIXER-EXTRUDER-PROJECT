from PyQt6.QtWidgets import QDateEdit, QCalendarWidget
from PyQt6.QtCore import Qt
from typing import override

class ModifiedDateEdit(QDateEdit):
    def __init__(self, calendarPopup=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calendarPopup = calendarPopup
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setCalendarPopup(self.calendarPopup)
    
    @override
    def showEvent(self, e):
        calendar = self.findChild(QCalendarWidget)
        super().showEvent(e)
        
        if calendar:
            calendar.setCursor(Qt.CursorShape.PointingHandCursor)
    