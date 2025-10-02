# app/views/extruder_config/processing_params/widgets/temp_table.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QPushButton, QTableWidgetItem, QLabel
from PyQt6.QtCore import pyqtSlot, Qt
from typing import List, Dict

from .delegates import DynamicComboBoxDelegate, NumericDelegate


class TempTable(QWidget):
    """
    CORRECTED: Manages temperature settings.
    - Column 0 is for Zone selection.
    - Dynamic columns (1 and onward) are for temp values.
    """

    def __init__(self, zones: List, parent=None):
        super().__init__(parent)
        # ... (toolbar setup is unchanged) ...
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout = QHBoxLayout()

        title_label = QLabel("<b>Temperature</b>")
        add_row_button = QPushButton("＋ Add Zone Row")
        remove_row_button = QPushButton("－ Remove Last Row")
        toolbar_layout.addWidget(title_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(remove_row_button)
        toolbar_layout.addWidget(add_row_button)

        self.table = QTableWidget()

        # --- FIX: Set up columns correctly ---
        self.table.insertColumn(0)
        self.table.setHorizontalHeaderLabels(["Zone"])

        self.table.setItemDelegateForColumn(0, DynamicComboBoxDelegate(zones, self.table))


        self.numeric_delegate = NumericDelegate(self.table)

        main_layout.addLayout(toolbar_layout)
        main_layout.addWidget(self.table)

        add_row_button.clicked.connect(self.add_row)
        remove_row_button.clicked.connect(self.remove_row)

    @pyqtSlot(int)
    def on_column_count_changed(self, dynamic_col_count: int):
        """
        Slot to receive the number of DYNAMIC columns from Table 1.
        Total columns will be 1 (for Zone) + dynamic_col_count.
        """
        total_cols = 1 + dynamic_col_count
        self.table.setColumnCount(total_cols)
        # Apply numeric delegate to all temp columns (from index 1 onward)
        for col in range(1, total_cols):
            self.table.setItemDelegateForColumn(col, self.numeric_delegate)

    # ... (add_row, remove_row methods are unchanged) ...
    def add_row(self):
        self.table.insertRow(self.table.rowCount())

    def remove_row(self):
        if self.table.rowCount() > 0: self.table.removeRow(self.table.rowCount() - 1)

    def get_data(self) -> List[Dict]:
        data = []
        for row in range(self.table.rowCount()):
            zone_item = self.table.item(row, 0)
            if not zone_item or zone_item.data(Qt.ItemDataRole.UserRole) is None:
                raise ValueError(f"Please select a Zone for temperature row {row + 1}.")

            zone_id = zone_item.data(Qt.ItemDataRole.UserRole)

            # Iterate over DYNAMIC columns (1 and onward)
            for col in range(1, self.table.columnCount()):
                temp_item = self.table.item(row, col)
                if not temp_item or not temp_item.text().strip():
                    raise ValueError(f"Please enter a temperature for Zone '{zone_item.text()}' in column {col}.")

                try:
                    temp_value = float(temp_item.text())
                except ValueError:
                    raise ValueError(f"Invalid temperature '{temp_item.text()}'. Please use numbers only.")

                data.append({
                    'zone_id': zone_id,
                    'col_idx': col,  # This now correctly maps to the dynamic column index
                    'temp_value': temp_value
                })
        return data