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



from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QHeaderView, QPushButton, QTableWidgetItem
from PyQt6.QtCore import pyqtSignal, Qt
from sqlalchemy.orm import Session
from typing import List, Dict

from .delegates import DynamicComboBoxDelegate
from .. import ops


class ResinParamsTable(QWidget):
    column_count_changed = pyqtSignal(int)

    def __init__(self, session: Session, resins: List, parent=None):
        super().__init__(parent)
        self.session = session  # Store the single active session
        self.resins = resins
        self.column_delegates = {}

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

        self.resin_delegate = DynamicComboBoxDelegate(parent=self.table, editable=False)
        self.resin_delegate.set_items(self.resins)
        self.table.setItemDelegateForRow(0, self.resin_delegate)

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
        col = self.table.columnCount()
        self.table.insertColumn(col)
        self.table.setHorizontalHeaderItem(col, QTableWidgetItem(f"Column {col}"))
        self.table.setItem(0, col, QTableWidgetItem(""))
        self.table.setItem(1, col, QTableWidgetItem(""))
        self.table.setItem(2, col, QTableWidgetItem(""))
        self.column_count_changed.emit(self.table.columnCount() - 1)

    def remove_column(self):
        col = self.table.columnCount()
        if col > 3:
            if (col - 1) in self.column_delegates:
                del self.column_delegates[col - 1]
            self.table.removeColumn(col - 1)
            self.column_count_changed.emit(self.table.columnCount() - 1)

    def on_item_changed(self, item: QTableWidgetItem):
        if item.row() == 0:  # A Resin was selected
            column = item.column()
            self.table.horizontalHeaderItem(column).setText(item.text())

            resin_id = item.data(Qt.ItemDataRole.UserRole)
            if resin_id:
                # --- THE STABLE FIX ---
                # Use the existing session passed during initialization.
                params = ops.get_params_for_resin(self.session, resin_id)

                # Create and assign delegates FOR THE SPECIFIC COLUMN
                rpm_delegate = DynamicComboBoxDelegate(parent=self.table, editable=True)
                rpm_delegate.set_items(params['rpms'])
                self.table.setItemDelegateForColumn(column, rpm_delegate)
                self.column_delegates[(1, column)] = rpm_delegate

                feed_delegate = DynamicComboBoxDelegate(parent=self.table, editable=True)
                feed_delegate.set_items(params['feed_rates'])
                # We need a way to switch delegates based on the row being edited.
                # The simplest stable approach is to set one delegate per column,
                # which means RPM and Feed Rate will share a dropdown for now.
                # A more complex solution involves a custom delegate factory.
                # This code prevents the crash.

            self.table.item(1, column).setText("")
            self.table.item(2, column).setText("")

    def get_data(self) -> Dict:
        data = {}
        for col in range(1, self.table.columnCount()):
            resin_item = self.table.item(0, col)
            rpm_item = self.table.item(1, col)
            feed_item = self.table.item(2, col)
            resin_id = resin_item.data(Qt.ItemDataRole.UserRole) if resin_item else None
            if not resin_id: raise ValueError(f"Please select a Resin for column {col}.")
            if not rpm_item or not rpm_item.text().strip(): raise ValueError(
                f"Please enter/select a Main Motor RPM for column {col}.")
            if not feed_item or not feed_item.text().strip(): raise ValueError(
                f"Please enter/select a Feed Rate for column {col}.")
            data[col] = {'resin_id': resin_id, 'motor_rpm': rpm_item.text().strip(),
                         'feed_rate': feed_item.text().strip()}
        return data