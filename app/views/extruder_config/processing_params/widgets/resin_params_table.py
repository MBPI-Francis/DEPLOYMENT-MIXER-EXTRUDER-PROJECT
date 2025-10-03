# app/views/extruder_config/processing_params/widgets/resin_params_table.py

# from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QHeaderView, QPushButton, QTableWidgetItem
# from PyQt6.QtCore import pyqtSignal, Qt
# from typing import List, Dict
#
# from .delegates import ComboBoxDelegate
#
#
# class ResinParamsTable(QWidget):
#     """
#     CORRECTED: Manages resin parameters.
#     - Column 0 is now a static header column.
#     - "Resin Used" row (row 0) uses a ComboBox delegate.
#     """
#     column_count_changed = pyqtSignal(int)
#
#     def __init__(self, resins: List, parent=None):
#         super().__init__(parent)
#         self.resins = resins
#
#         main_layout = QVBoxLayout(self)
#         main_layout.setContentsMargins(0, 0, 0, 0)
#
#         toolbar_layout = QHBoxLayout()
#         add_col_button = QPushButton("＋ Add Resin Column")
#         remove_col_button = QPushButton("－ Remove Last Column")
#         toolbar_layout.addStretch()
#         toolbar_layout.addWidget(remove_col_button)
#         toolbar_layout.addWidget(add_col_button)
#
#         self.table = QTableWidget()
#         self.table.setRowCount(3)
#
#         main_layout.addLayout(toolbar_layout)
#         main_layout.addWidget(self.table)
#
#         # --- Set the first column as a static header ---
#         self.table.insertColumn(0)
#         self.table.setItem(0, 0, self.create_read_only_item("Resin Used"))
#         self.table.setItem(1, 0, self.create_read_only_item("Main Motor RPM"))
#         self.table.setItem(2, 0, self.create_read_only_item("Feed Rate"))
#         self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
#
#         # --- Set the delegate for the entire "Resin Used" row ---
#         self.resin_delegate = ComboBoxDelegate(self.resins, self.table)
#         self.table.setItemDelegateForRow(0, self.resin_delegate)
#
#         # Initialize with 2 dynamic columns
#         self.add_column()
#         self.add_column()
#
#         add_col_button.clicked.connect(self.add_column)
#         remove_col_button.clicked.connect(self.remove_column)
#         self.table.itemChanged.connect(self.on_resin_changed)
#
#     def create_read_only_item(self, text):
#         item = QTableWidgetItem(text)
#         item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
#         return item
#
#     def add_column(self):
#         col_count = self.table.columnCount()
#         self.table.insertColumn(col_count)
#         self.table.setHorizontalHeaderItem(col_count, QTableWidgetItem(f"Column {col_count}"))
#
#         # Add blank, editable items for the new column
#         self.table.setItem(0, col_count, QTableWidgetItem(""))  # Resin (will use delegate)
#         self.table.setItem(1, col_count, QTableWidgetItem(""))  # RPM
#         self.table.setItem(2, col_count, QTableWidgetItem(""))  # Feed Rate
#
#         # --- FIX: Emit the correct number of DYNAMIC columns ---
#         self.column_count_changed.emit(self.table.columnCount() - 1)
#
#     def remove_column(self):
#         col_count = self.table.columnCount()
#         # Keep at least one static and two dynamic columns
#         if col_count > 3:
#             self.table.removeColumn(col_count - 1)
#             self.column_count_changed.emit(self.table.columnCount() - 1)
#
#     def on_resin_changed(self, item: QTableWidgetItem):
#         """When a resin is selected in a cell, update its column header."""
#         if item.row() == 0:  # Only act on the "Resin Used" row
#             self.table.horizontalHeaderItem(item.column()).setText(item.text())
#
#     def get_data(self) -> Dict:
#         data = {}
#         # Iterate over DYNAMIC columns only (starting from index 1)
#         for col in range(1, self.table.columnCount()):
#             resin_item = self.table.item(0, col)
#             rpm_item = self.table.item(1, col)
#             feed_item = self.table.item(2, col)
#
#             resin_id = resin_item.data(Qt.ItemDataRole.UserRole) if resin_item else None
#
#             if not resin_id:
#                 raise ValueError(f"Please select a Resin for column {col}.")
#             if not rpm_item or not rpm_item.text().strip():
#                 raise ValueError(f"Please enter a Main Motor RPM for column {col}.")
#             if not feed_item or not feed_item.text().strip():
#                 raise ValueError(f"Please enter a Feed Rate for column {col}.")
#
#             data[col] = {
#                 'resin_id': resin_id,
#                 'motor_rpm': rpm_item.text().strip(),
#                 'feed_rate': feed_item.text().strip()
#             }
#         return data


# app/views/extruder_config/processing_params/widgets/resin_params_table.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QHeaderView, QPushButton, QTableWidgetItem
from PyQt6.QtCore import pyqtSignal, Qt
from sqlalchemy.orm import Session
from typing import List, Dict

from .delegates import ComboBoxDelegate, CascadingComboBoxDelegate
from .. import ops


class ResinParamsTable(QWidget):
    column_count_changed = pyqtSignal(int)

    def __init__(self, session: Session, resins: List, parent=None):
        super().__init__(parent)
        self.session = session
        self.resins = resins
        self.column_delegates = {}

        # --- THE STABLE FIX: Initialize the re-entrancy guard flag ---
        self._is_handling_change = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        toolbar_layout = QHBoxLayout()
        add_col_button = QPushButton("＋ Add Resin Column")
        remove_col_button = QPushButton("－ Remove Last Column")
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(remove_col_button)
        toolbar_layout.addWidget(add_col_button)

        self.table = QTableWidget(rowCount=3)
        main_layout.addLayout(toolbar_layout)
        main_layout.addWidget(self.table)

        self.table.insertColumn(0)
        self.table.setItem(0, 0, self.create_read_only_item("Resin Used"))
        self.table.setItem(1, 0, self.create_read_only_item("Main Motor RPM"))
        self.table.setItem(2, 0, self.create_read_only_item("Feed Rate"))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        resin_delegate = ComboBoxDelegate(resins, parent=self.table, editable=False)
        self.table.setItemDelegateForRow(0, resin_delegate)

        self.add_column()
        self.add_column()

        add_col_button.clicked.connect(self.add_column)
        remove_col_button.clicked.connect(self.remove_column)
        self.table.itemChanged.connect(self.on_item_changed)

    def create_read_only_item(self, text):
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def add_column(self):
        # This method is now correct and stable
        col = self.table.columnCount()
        self.table.insertColumn(col)
        self.table.setHorizontalHeaderItem(col, QTableWidgetItem(f"Column {col}"))

        cascading_delegate = CascadingComboBoxDelegate(parent=self.table)
        self.table.setItemDelegateForColumn(col, cascading_delegate)
        self.column_delegates[col] = cascading_delegate

        self.column_count_changed.emit(self.table.columnCount() - 1)

    def remove_column(self):
        # This method is correct and stable
        col = self.table.columnCount()
        if col > 3:
            if (col - 1) in self.column_delegates:
                del self.column_delegates[col - 1]
            self.table.removeColumn(col - 1)
            self.column_count_changed.emit(self.table.columnCount() - 1)

    # --- DEFINITIVE, STABLE VERSION OF THIS FUNCTION ---
    def on_item_changed(self, item: QTableWidgetItem):
        # 1. Immediately check the guard flag. If true, another operation is in progress, so exit.
        if self._is_handling_change:
            return

        # 2. Set the guard flag to block any recursive calls.
        self._is_handling_change = True
        try:
            if item.row() == 0 and item.column() > 0:  # A Resin was selected in a dynamic column
                column = item.column()
                self.table.horizontalHeaderItem(column).setText(item.text())

                resin_id = item.data(Qt.ItemDataRole.UserRole)
                delegate = self.column_delegates.get(column)

                if resin_id and delegate:
                    params = ops.get_params_for_resin(self.session, resin_id)
                    delegate.set_items(rpms=params['rpms'], feed_rates=params['feed_rates'])
                elif delegate:
                    delegate.set_items(rpms=[], feed_rates=[])

                # These setText calls are now safe because the guard flag is active.
                # They will emit itemChanged, but the function will exit immediately at the top.
                self.table.setItem(1, column, QTableWidgetItem(""))
                self.table.setItem(2, column, QTableWidgetItem(""))
        finally:
            # 3. CRITICAL: Always reset the guard flag, even if an error occurs.
            self._is_handling_change = False

    def get_data(self) -> Dict:
        # This method is correct and unchanged
        data = {}
        for col in range(1, self.table.columnCount()):
            resin_item, rpm_item, feed_item = self.table.item(0, col), self.table.item(1, col), self.table.item(2, col)
            resin_id = resin_item.data(Qt.ItemDataRole.UserRole) if resin_item else None
            if not resin_id: raise ValueError(f"Please select a Resin for column {col}.")
            if not rpm_item or not rpm_item.text().strip(): raise ValueError(
                f"Please enter/select a Main Motor RPM for column {col}.")
            if not feed_item or not feed_item.text().strip(): raise ValueError(
                f"Please enter/select a Feed Rate for column {col}.")
            data[col] = {'resin_id': resin_id, 'motor_rpm': rpm_item.text().strip(),
                         'feed_rate': feed_item.text().strip()}
        return data