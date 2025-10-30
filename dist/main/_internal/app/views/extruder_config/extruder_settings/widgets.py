# app/views/extruder_settings/records/widgets.py

from typing import Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QLineEdit, QDialog,
    QLabel, QCheckBox, QGroupBox, QAbstractItemView
)
from PyQt6.QtCore import pyqtSignal, Qt
from sqlalchemy.orm import sessionmaker

from . import ops
from ....validators.ExtruderSettingsValidator import RestoreValidator


# --- NEW: Added ConfirmationDialog ---
class ConfirmationDialog(QDialog):
    """The 'Type YES' confirmation dialog you specifically requested."""

    def __init__(self, parent=None, message: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Confirm Action")
        self.setMinimumWidth(450)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.instructions_label = QLabel("To proceed, please type <b>YES</b> in the box below.")
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Type YES to confirm")
        self.confirm_input.setObjectName("ConfirmInput")

        self.proceed_button = QPushButton("Proceed")
        self.proceed_button.setEnabled(False)
        self.proceed_button.setObjectName("PrimaryButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.proceed_button)

        layout.addWidget(self.message_label)
        layout.addWidget(self.instructions_label)
        layout.addWidget(self.confirm_input)
        layout.addLayout(button_layout)

        self.confirm_input.textChanged.connect(lambda text: self.proceed_button.setEnabled(text == "YES"))
        self.proceed_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)


# The RestoreDialog remains unchanged...
class RestoreDialog(QDialog):
    operation_successful = pyqtSignal()

    def __init__(self, session_factory: Callable, get_deleted_func: Callable,
                 restore_func: Callable, item_name_plural: str, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.get_deleted = get_deleted_func
        self.restore = restore_func
        self.item_name_plural = item_name_plural
        self.setWindowTitle(f"Restore Deleted {self.item_name_plural}")
        self.setMinimumSize(500, 350)
        self.setModal(True)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["", "ID", f"{item_name_plural.rstrip('s')} Name"])
        self.table.setColumnHidden(1, True)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.select_all_checkbox = QCheckBox("Select All")
        restore_button = QPushButton("Restore Selected")
        restore_button.setObjectName("SuccessButton")
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("SecondaryButton")
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.select_all_checkbox)
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(restore_button)
        layout.addWidget(self.table)
        layout.addLayout(button_layout)
        restore_button.clicked.connect(self._on_restore)
        cancel_button.clicked.connect(self.reject)
        self.select_all_checkbox.stateChanged.connect(
            lambda state: self._toggle_all(state == Qt.CheckState.Checked.value))

    def open(self):
        self._populate_table()
        self.exec()

    def _populate_table(self):
        self.table.setRowCount(0)
        session = self.Session()
        try:
            for row, item in enumerate(self.get_deleted(session)):
                self.table.insertRow(row)
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk.setCheckState(Qt.CheckState.Unchecked)
                self.table.setItem(row, 0, chk)
                self.table.setItem(row, 1, QTableWidgetItem(str(item.id)))
                self.table.setItem(row, 2, QTableWidgetItem(item.name))
        finally:
            session.close()

    def _toggle_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(state)

    def _on_restore(self):
        ids = [int(self.table.item(r, 1).text()) for r in range(self.table.rowCount()) if
               self.table.item(r, 0).checkState() == Qt.CheckState.Checked]
        if not ids:
            QMessageBox.warning(self, "No Selection",
                                f"Please select at least one {self.item_name_plural.lower()} to restore.")
            return
        session = self.Session()
        try:
            self.restore(session, RestoreValidator(item_ids=ids))
            QMessageBox.information(self, "Success", f"Selected {self.item_name_plural.lower()} have been restored.")
            self.operation_successful.emit()
            self.accept()
        finally:
            session.close()


# --- NEW: Resin-specific Panel ---
class ResinManagementPanel(QGroupBox):
    """A specific panel for managing Resins with an abbreviation column."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        self.search_bar = QLineEdit(placeholderText=f"Search {title.lower()}...")
        self.search_bar.setObjectName("SearchBar")
        self.add_button = QPushButton(f"Add New {title.rstrip('s')}")
        self.restore_button = QPushButton("Restore")
        self.add_button.setObjectName("PrimaryButton")
        self.restore_button.setObjectName("SecondaryButton")
        top_layout.addWidget(self.search_bar)
        top_layout.addStretch()
        top_layout.addWidget(self.restore_button)
        top_layout.addWidget(self.add_button)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["ID", "Abbr.", "Name", "Created By", "Created At"])
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(0, True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        layout.addLayout(top_layout)
        layout.addWidget(self.table)


# --- NEW: Zone-specific Panel ---
class ZoneManagementPanel(QGroupBox):
    """A specific panel for managing Zones (no abbreviation column)."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        self.search_bar = QLineEdit(placeholderText=f"Search {title.lower()}...")
        self.search_bar.setObjectName("SearchBar")
        self.add_button = QPushButton(f"Add New {title.rstrip('s')}")
        self.restore_button = QPushButton("Restore")
        self.add_button.setObjectName("PrimaryButton")
        self.restore_button.setObjectName("SecondaryButton")
        top_layout.addWidget(self.search_bar)
        top_layout.addStretch()
        top_layout.addWidget(self.restore_button)
        top_layout.addWidget(self.add_button)

        self.table = QTableWidget()
        self.table.setColumnCount(4)  # Only 4 columns
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Created By", "Created At"])
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Name is column 1
        self.table.setColumnHidden(0, True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        layout.addLayout(top_layout)
        layout.addWidget(self.table)