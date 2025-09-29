# app/views/extruder_config/resin_params/widgets.py

from typing import Callable, List
from PyQt6.QtWidgets import (
    QStyledItemDelegate, QComboBox, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTableWidget, QTableWidgetItem, QMessageBox, QHeaderView,
    QLineEdit, QDialog, QLabel, QGroupBox, QAbstractItemView, QCheckBox
)
from PyQt6.QtCore import pyqtSignal, Qt

from . import ops
# NOTE: This file has NO dependency on ops.py. It is a pure UI component.
# This makes it more reusable and stable.
from ....validators.ExtruderSettingsValidator import RestoreValidator


# In app/views/extruder_config/resin_params/widgets.py

# --- UPDATED: A simpler, more robust ComboBoxDelegate ---
class ComboBoxDelegate(QStyledItemDelegate):
    """
    A custom delegate for an editable QComboBox. Its only job is to transfer
    the editor's state to the model. All validation is left to the handler.
    """

    def __init__(self, items: List, parent=None):
        super().__init__(parent)
        self.items = items

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.setEditable(True)
        editor.lineEdit().setPlaceholderText("Select or type to search...")
        for item_id, display_name in self.items:
            editor.addItem(display_name, userData=item_id)
        editor.setCurrentIndex(-1)
        return editor

    def setEditorData(self, editor, index):
        current_id = index.model().data(index, Qt.ItemDataRole.UserRole)
        if current_id:
            editor_index = editor.findData(current_id)
            if editor_index >= 0:
                editor.setCurrentIndex(editor_index)
        else:
            # If there's no ID, just show the text that might be in the cell
            editor.setCurrentText(index.model().data(index, Qt.ItemDataRole.DisplayRole))

    def setModelData(self, editor, model, index):
        """
        --- KEY CHANGE ---
        This method now faithfully transfers the editor's text to the model,
        letting the handler perform all validation.
        """
        current_text = editor.currentText()
        editor_index = editor.findText(current_text, Qt.MatchFlag.MatchFixedString)

        selected_id = None
        if editor_index >= 0:
            selected_id = editor.itemData(editor_index)

        # ALWAYS write the current text to the display role.
        # This is what allows the handler to see "Sample 1".
        model.setData(index, current_text, Qt.ItemDataRole.DisplayRole)
        # Write the ID (or None if the text is invalid) to the user role.
        model.setData(index, selected_id, Qt.ItemDataRole.UserRole)


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


class RestoreDialog(QDialog):
    operation_successful = pyqtSignal()
    def __init__(self, session_factory: Callable, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.setWindowTitle("Restore Deleted Parameters")
        self.setMinimumSize(600, 400)
        self.setModal(True)
        # ... (The rest of this dialog's logic is the same as in the extruder_settings module)
        layout = QVBoxLayout(self)
        self.table = QTableWidget(0, 5, self) # ID, Resin, RPM, Feed Rate
        self.table.setHorizontalHeaderLabels(["", "ID", "Resin", "Motor RPM", "Feed Rate"])
        self.table.setColumnHidden(1, True)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.select_all_checkbox = QCheckBox("Select All")
        restore_button = QPushButton("Restore Selected")
        restore_button.setObjectName("SuccessButton")
        cancel_button = QPushButton("Cancel")
        button_layout = QHBoxLayout()
        button_layout.addWidget(self.select_all_checkbox)
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(restore_button)
        layout.addWidget(self.table)
        layout.addLayout(button_layout)
        restore_button.clicked.connect(self._on_restore)
        cancel_button.clicked.connect(self.reject)
        self.select_all_checkbox.stateChanged.connect(lambda state: self._toggle_all(state == Qt.CheckState.Checked.value))

    def open(self):
        self._populate_table()
        self.exec()
    def _populate_table(self):
        self.table.setRowCount(0)
        session = self.Session()
        try:
            for row, result in enumerate(ops.get_deleted_resin_params(session)):
                param, resin_name = result
                self.table.insertRow(row)
                chk = QTableWidgetItem()
                chk.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk.setCheckState(Qt.CheckState.Unchecked)
                self.table.setItem(row, 0, chk)
                self.table.setItem(row, 1, QTableWidgetItem(str(param.id)))
                self.table.setItem(row, 2, QTableWidgetItem(resin_name))
                self.table.setItem(row, 3, QTableWidgetItem(param.motor_rpm))
                self.table.setItem(row, 4, QTableWidgetItem(param.feed_rate))
        finally:
            session.close()

    def _toggle_all(self, checked):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()): self.table.item(row, 0).setCheckState(state)

    def _on_restore(self):
        ids = [int(self.table.item(r, 1).text()) for r in range(self.table.rowCount()) if self.table.item(r, 0).checkState() == Qt.CheckState.Checked]
        if not ids:
            QMessageBox.warning(self, "No Selection", "Please select at least one parameter to restore.")
            return
        session = self.Session()
        try:
            ops.restore_resin_params(session, RestoreValidator(item_ids=ids))
            QMessageBox.information(self, "Success", "Selected parameters have been restored.")
            self.operation_successful.emit()
            self.accept()
        finally:
            session.close()


class ResinParamsManagementPanel(QGroupBox):
    def __init__(self, title: str, column_config: List, parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)
        top_layout = QHBoxLayout()
        self.search_bar = QLineEdit(placeholderText="Search...")
        self.add_button = QPushButton("Add New Parameter")
        self.restore_button = QPushButton("Restore")
        self.add_button.setObjectName("PrimaryButton")
        self.restore_button.setObjectName("SecondaryButton")
        top_layout.addWidget(self.search_bar)
        top_layout.addStretch()
        top_layout.addWidget(self.restore_button)
        top_layout.addWidget(self.add_button)

        self.table = QTableWidget()
        self.table.setColumnCount(len(column_config))
        headers = [col['header'] for col in column_config]
        self.table.setHorizontalHeaderLabels(headers)
        for i, col in enumerate(column_config):
            if col.get('stretch'): self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            if col.get('hidden'): self.table.setColumnHidden(i, True)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        layout.addLayout(top_layout)
        layout.addWidget(self.table)