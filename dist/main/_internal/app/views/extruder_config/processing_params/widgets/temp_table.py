# app/views/extruder_config/processing_params/widgets/temp_table.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QPushButton, QTableWidgetItem, QLabel
from PyQt6.QtCore import pyqtSlot, Qt
from typing import List, Dict

from .delegates import NumericDelegate, ComboBoxDelegate


class TempTable(QWidget):
    def __init__(self, zones: List, parent=None):
        super().__init__(parent)
        self.zones = zones
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        toolbar_layout = QHBoxLayout()
        title_label = QLabel("<b>Temperature Settings</b>")
        self.add_row_button = QPushButton("＋ Add Zone Row")
        self.add_row_button.setObjectName("PrimaryButton")
        self.remove_row_button = QPushButton("－ Remove Last Row")
        self.remove_row_button.setObjectName("DangerButton")
        toolbar_layout.addWidget(title_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.remove_row_button)
        toolbar_layout.addWidget(self.add_row_button)

        self.table = QTableWidget()
        self.table.verticalHeader().setVisible(False)

        self.table.insertColumn(0)
        self.table.setHorizontalHeaderLabels(["Zone"])
        zone_delegate = ComboBoxDelegate(zones, parent=self.table, editable=False)
        self.table.setItemDelegateForColumn(0, zone_delegate)

        self.numeric_delegate = NumericDelegate(self.table)
        main_layout.addLayout(toolbar_layout)
        main_layout.addWidget(self.table)

        self.add_row_button.clicked.connect(self.add_row)
        self.remove_row_button.clicked.connect(self.remove_row)

    def set_read_only(self, read_only: bool):
        """Toggles the read-only state of the widget."""
        self.add_row_button.setVisible(not read_only)
        self.remove_row_button.setVisible(not read_only)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers if read_only else QTableWidget.EditTrigger.AllEditTriggers)

    def clear_rows(self):
        """Removes all rows from the table."""
        self.table.setRowCount(0)

    @pyqtSlot(int)
    def on_column_count_changed(self, dynamic_col_count: int):
        total_cols = 1 + dynamic_col_count
        current_cols = self.table.columnCount()
        self.table.setColumnCount(total_cols)
        # Only set new delegates if columns were added
        if total_cols > current_cols:
            for col in range(current_cols, total_cols):
                self.table.setItemDelegateForColumn(col, self.numeric_delegate)

    def add_row(self):
        self.table.insertRow(self.table.rowCount())

    def remove_row(self):
        if self.table.rowCount() > 0: self.table.removeRow(self.table.rowCount() - 1)

    def get_data(self) -> List[Dict]:
        if self.table.rowCount() == 0 and self.table.columnCount() > 1: raise ValueError(
            "Please add at least one temperature zone.")
        data = []
        for row in range(self.table.rowCount()):
            zone_item = self.table.item(row, 0)
            if not zone_item or zone_item.data(Qt.ItemDataRole.UserRole) is None: raise ValueError(
                f"Please select a Zone for row {row + 1}.")
            zone_id = zone_item.data(Qt.ItemDataRole.UserRole)
            for col in range(1, self.table.columnCount()):
                temp_item = self.table.item(row, col)
                if not temp_item or not temp_item.text().strip(): raise ValueError(
                    f"Please enter a temperature for Zone '{zone_item.text()}' in column {col}.")
                try:
                    temp_value = float(temp_item.text())
                except (ValueError, TypeError):
                    raise ValueError(f"Invalid temperature '{temp_item.text()}'. Please use numbers only.")
                data.append({'zone_id': zone_id, 'col_idx': col, 'temp_value': temp_value})
        return data