# # app/views/extruder_config/processing_params/widgets/resin_params_table.py
#
# from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QHeaderView, QPushButton, QTableWidgetItem
# from PyQt6.QtCore import pyqtSignal, Qt
# from sqlalchemy.orm import Session
# from typing import List, Dict
#
# from .delegates import ComboBoxDelegate, CascadingComboBoxDelegate
# from .. import ops
#
#
# class ResinParamsTable(QWidget):
#     column_count_changed = pyqtSignal(int)
#
#     def __init__(self, session: Session, resins: List, parent=None):
#         super().__init__(parent)
#         self.session = session
#         self.resins = resins
#         self.column_delegates = {}
#         self._is_handling_change = False
#
#         main_layout = QVBoxLayout(self)
#         main_layout.setContentsMargins(0, 0, 0, 0)
#
#         toolbar_layout = QHBoxLayout()
#         self.add_col_button = QPushButton("＋ Add Resin Column")
#         self.remove_col_button = QPushButton("－ Remove Last Column")
#         toolbar_layout.addStretch()
#         toolbar_layout.addWidget(self.remove_col_button)
#         toolbar_layout.addWidget(self.add_col_button)
#
#         self.table = QTableWidget(rowCount=3)
#         main_layout.addLayout(toolbar_layout)
#         main_layout.addWidget(self.table)
#
#         self.table.insertColumn(0)
#         self.table.setItem(0, 0, self.create_read_only_item("Resin Used"))
#         self.table.setItem(1, 0, self.create_read_only_item("Main Motor RPM"))
#         self.table.setItem(2, 0, self.create_read_only_item("Feed Rate"))
#         self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
#         self.table.verticalHeader().setVisible(False)
#
#         resin_delegate = ComboBoxDelegate(resins, parent=self.table, editable=False)
#         self.table.setItemDelegateForRow(0, resin_delegate)
#
#         self.add_col_button.clicked.connect(self.add_column)
#         self.remove_col_button.clicked.connect(self.remove_column)
#         self.table.itemChanged.connect(self.on_item_changed)
#
#     def set_read_only(self, read_only: bool):
#         """Toggles the read-only state of the widget."""
#         self.add_col_button.setVisible(not read_only)
#         self.remove_col_button.setVisible(not read_only)
#         self.table.setEditTriggers(
#             QTableWidget.EditTrigger.NoEditTriggers if read_only else QTableWidget.EditTrigger.AllEditTriggers)
#
#     def clear_dynamic_columns(self):
#         """Removes all columns except for the static first one."""
#         while self.table.columnCount() > 1:
#             self.table.removeColumn(self.table.columnCount() - 1)
#         self.column_delegates.clear()
#         self.column_count_changed.emit(0)
#
#     def create_read_only_item(self, text):
#         item = QTableWidgetItem(text)
#         item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
#         return item
#
#     def add_column(self):
#         col = self.table.columnCount()
#         self.table.insertColumn(col)
#         self.table.setHorizontalHeaderItem(col, QTableWidgetItem(f"Resin {col}"))
#         cascading_delegate = CascadingComboBoxDelegate(parent=self.table)
#         self.table.setItemDelegateForColumn(col, cascading_delegate)
#         self.column_delegates[col] = cascading_delegate
#         self.column_count_changed.emit(self.table.columnCount() - 1)
#
#     def remove_column(self):
#         if self.table.columnCount() > 1:
#             col_to_remove = self.table.columnCount() - 1
#             if col_to_remove in self.column_delegates: del self.column_delegates[col_to_remove]
#             self.table.removeColumn(col_to_remove)
#             self.column_count_changed.emit(self.table.columnCount() - 1)
#
#     def on_item_changed(self, item: QTableWidgetItem):
#         if self._is_handling_change: return
#         self._is_handling_change = True
#         try:
#             if item.row() == 0 and item.column() > 0:
#                 column, resin_id = item.column(), item.data(Qt.ItemDataRole.UserRole)
#                 self.table.horizontalHeaderItem(column).setText(item.text())
#                 delegate = self.column_delegates.get(column)
#                 if resin_id and delegate:
#                     params = ops.get_params_for_resin(self.session, resin_id)
#                     delegate.set_items(rpms=params['rpms'], feed_rates=params['feed_rates'])
#                 elif delegate:
#                     delegate.set_items(rpms=[], feed_rates=[])
#                 self.table.setItem(1, column, QTableWidgetItem(""))
#                 self.table.setItem(2, column, QTableWidgetItem(""))
#         finally:
#             self._is_handling_change = False
#
#     def get_data(self) -> Dict:
#         if self.table.columnCount() <= 1: raise ValueError("Please add and fill at least one resin column.")
#         data = {}
#         for col in range(1, self.table.columnCount()):
#             resin_item, rpm_item, feed_item = self.table.item(0, col), self.table.item(1, col), self.table.item(2, col)
#             resin_id = resin_item.data(Qt.ItemDataRole.UserRole) if resin_item else None
#             if not resin_id: raise ValueError(f"Please select a Resin for column {col}.")
#             if not rpm_item or not rpm_item.text().strip(): raise ValueError(
#                 f"Please enter/select a Main Motor RPM for column {col}.")
#             if not feed_item or not feed_item.text().strip(): raise ValueError(
#                 f"Please enter/select a Feed Rate for column {col}.")
#             data[col] = {'resin_id': resin_id, 'motor_rpm': rpm_item.text().strip(),
#                          'feed_rate': feed_item.text().strip()}
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
        self._is_handling_change = False

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        toolbar_layout = QHBoxLayout()
        self.add_col_button = QPushButton("＋ Add Resin Column")
        self.remove_col_button = QPushButton("－ Remove Last Column")
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self.remove_col_button)
        toolbar_layout.addWidget(self.add_col_button)

        self.table = QTableWidget(rowCount=3)
        main_layout.addLayout(toolbar_layout)
        main_layout.addWidget(self.table)

        self.table.insertColumn(0)
        self.table.setItem(0, 0, self.create_read_only_item("Resin Used"))
        self.table.setItem(1, 0, self.create_read_only_item("Main Motor RPM"))
        self.table.setItem(2, 0, self.create_read_only_item("Feed Rate"))
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)

        resin_delegate = ComboBoxDelegate(resins, parent=self.table, editable=False)
        self.table.setItemDelegateForRow(0, resin_delegate)

        # --- RESTORED: Add two default columns for a new record ---
        self.add_column()
        self.add_column()

        self.add_col_button.clicked.connect(self.add_column)
        self.remove_col_button.clicked.connect(self.remove_column)
        self.table.itemChanged.connect(self.on_item_changed)

    def set_read_only(self, read_only: bool):
        self.add_col_button.setVisible(not read_only)
        self.remove_col_button.setVisible(not read_only)
        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers if read_only else QTableWidget.EditTrigger.AllEditTriggers)

    def clear_dynamic_columns(self):
        while self.table.columnCount() > 1:
            self.table.removeColumn(self.table.columnCount() - 1)
        self.column_delegates.clear()
        self.column_count_changed.emit(0)

    def create_read_only_item(self, text):
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        return item

    def add_column(self):
        col = self.table.columnCount()
        self.table.insertColumn(col)
        self.table.setHorizontalHeaderItem(col, QTableWidgetItem(f"Resin {col}"))
        cascading_delegate = CascadingComboBoxDelegate(parent=self.table)
        self.table.setItemDelegateForColumn(col, cascading_delegate)
        self.column_delegates[col] = cascading_delegate
        self.column_count_changed.emit(self.table.columnCount() - 1)

    def remove_column(self):
        if self.table.columnCount() > 1:
            col_to_remove = self.table.columnCount() - 1
            if col_to_remove in self.column_delegates: del self.column_delegates[col_to_remove]
            self.table.removeColumn(col_to_remove)
            self.column_count_changed.emit(self.table.columnCount() - 1)

    def on_item_changed(self, item: QTableWidgetItem):
        if self._is_handling_change: return
        self._is_handling_change = True
        try:
            if item.row() == 0 and item.column() > 0:
                column, resin_id = item.column(), item.data(Qt.ItemDataRole.UserRole)
                self.table.horizontalHeaderItem(column).setText(item.text())
                delegate = self.column_delegates.get(column)
                if resin_id and delegate:
                    params = ops.get_params_for_resin(self.session, resin_id)
                    delegate.set_items(rpms=params['rpms'], feed_rates=params['feed_rates'])
                elif delegate:
                    delegate.set_items(rpms=[], feed_rates=[])
                self.table.setItem(1, column, QTableWidgetItem(""))
                self.table.setItem(2, column, QTableWidgetItem(""))
        finally:
            self._is_handling_change = False

    def get_data(self) -> Dict:
        if self.table.columnCount() <= 1: raise ValueError("Please add and fill at least one resin column.")
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