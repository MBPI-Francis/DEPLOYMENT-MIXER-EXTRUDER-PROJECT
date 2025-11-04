# app/views/extruder_form/entry_form/widgets/tab_aware_table.py

from PyQt6.QtWidgets import QTableWidget
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QKeyEvent


class TabAwareTableWidget(QTableWidget):
    """
    A QTableWidget subclass that emits a signal when the user presses Tab
    on the very last editable cell.
    """
    tabbed_out_of_last_cell = pyqtSignal()

    def keyPressEvent(self, event: QKeyEvent):
        """
        Overrides the key press event to detect tabbing out of the last cell.
        """
        # Check if the Tab key was pressed (without Shift)
        if event.key() == Qt.Key.Key_Tab and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:

            # Check if the current cell is the last one in the table
            is_last_row = self.currentRow() == self.rowCount() - 1
            is_last_col = self.currentColumn() == self.columnCount() - 1

            if is_last_row and is_last_col:
                # If it is, emit our custom signal and do NOT process the event further.
                # This prevents the default tab-wrapping behavior.
                self.tabbed_out_of_last_cell.emit()
                event.accept()  # Mark the event as handled
                return

        # For all other key presses, use the default QTableWidget behavior
        super().keyPressEvent(event)