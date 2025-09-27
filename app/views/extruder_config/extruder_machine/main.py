# app/views/extruder_machines/records/main.py

import os
from typing import Type, Callable
from pydantic import ValidationError

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QMessageBox, QHeaderView, QLineEdit, QAbstractItemView, QDialog, QFormLayout,
    QLabel, QCheckBox, QMenu
)
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QAction
import qtawesome as qta
from sqlalchemy.orm import sessionmaker

from . import ops
from ....validators.ExtruderMachineValidator import ExtruderMachineValidator, RestoreValidator


def load_stylesheet(widget):
    """Loads the stylesheet for this module."""
    current_dir = os.path.dirname(os.path.realpath(__file__))
    css_path = os.path.join(current_dir, "styles.css")
    try:
        with open(css_path, "r") as f:
            widget.setStyleSheet(f.read())
    except FileNotFoundError:
        print(f"Warning: Stylesheet not found at {css_path}")


# --- Dialog Classes ---

class CreateMachineDialog(QDialog):
    operation_successful = pyqtSignal()

    def __init__(self, session_factory: Callable[..., sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.setWindowTitle("Add New Extruder Machine")
        self.setMinimumWidth(400)
        self.setModal(True)

        self.name_input = QLineEdit()
        self.save_button = QPushButton("Save Machine")
        self.save_button.setObjectName("PrimaryButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.save_button.setEnabled(False)

        layout = QFormLayout(self)
        layout.addRow("Machine Name:", self.name_input)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        layout.addRow(button_layout)

        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._on_save)
        self.name_input.textChanged.connect(self._validate_input)

    def _validate_input(self):
        try:
            ExtruderMachineValidator(name=self.name_input.text())
            self.save_button.setEnabled(True)
        except ValidationError:
            self.save_button.setEnabled(False)

    def _on_save(self):
        session = self.Session()
        try:
            validated_data = ExtruderMachineValidator(name=self.name_input.text())
            if ops.check_machine_name_exists(session, name=validated_data.name):
                QMessageBox.warning(self, "Duplicate Entry", f"A machine named '{validated_data.name}' already exists.")
                return

            ops.create_machine(session, validated_data)
            QMessageBox.information(self, "Success", f"Machine '{validated_data.name}' created successfully.")
            self.operation_successful.emit()
            self.accept()
        except ValidationError as e:
            QMessageBox.warning(self, "Validation Error", f"Please check your input:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "An Error Occurred", f"Could not save the machine: {e}")
        finally:
            session.close()

    def open(self):
        self.name_input.clear()
        self._validate_input()
        self.exec()


class UpdateMachineDialog(QDialog):
    operation_successful = pyqtSignal()

    def __init__(self, session_factory: Callable[..., sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.machine_id = None
        self.original_name = ""
        self.setWindowTitle("Edit Extruder Machine")
        self.setMinimumWidth(400)
        self.setModal(True)

        self.name_input = QLineEdit()
        self.save_button = QPushButton("Save Changes")
        self.save_button.setObjectName("PrimaryButton")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")

        layout = QFormLayout(self)
        layout.addRow("Machine Name:", self.name_input)
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)
        layout.addRow(button_layout)

        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self._on_save)
        self.name_input.textChanged.connect(self._validate_input)

    def _validate_input(self):
        is_valid = False
        try:
            ExtruderMachineValidator(name=self.name_input.text())
            if self.name_input.text().strip() != self.original_name:
                is_valid = True
        except ValidationError:
            is_valid = False
        self.save_button.setEnabled(is_valid)

    def _on_save(self):
        if not self.machine_id: return
        session = self.Session()
        try:
            validated_data = ExtruderMachineValidator(name=self.name_input.text())
            if ops.check_machine_name_exists(session, name=validated_data.name, exclude_id=self.machine_id):
                QMessageBox.warning(self, "Duplicate Entry",
                                    f"Another machine named '{validated_data.name}' already exists.")
                return

            ops.update_machine(session, self.machine_id, validated_data)
            QMessageBox.information(self, "Success", "Machine has been updated.")
            self.operation_successful.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "An Error Occurred", f"Could not update machine: {e}")
        finally:
            session.close()

    def open(self, machine_id: int, current_name: str):
        self.machine_id = machine_id
        self.original_name = current_name
        self.name_input.setText(current_name)
        self._validate_input()
        self.exec()


class ConfirmationDialog(QDialog):
    """The 'Type YES' confirmation dialog you specifically requested."""

    def __init__(self, parent=None, message: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Confirm Action")
        self.setMinimumWidth(400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.instructions_label = QLabel("To proceed, please type <b>YES</b> in the box below.")
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Type YES to confirm")

        self.proceed_button = QPushButton("Proceed")
        self.proceed_button.setObjectName("PrimaryButton")
        self.proceed_button.setEnabled(False)
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


class RestoreMachineDialog(QDialog):
    operation_successful = pyqtSignal()

    def __init__(self, session_factory: Callable[..., sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.setWindowTitle("Restore Deleted Machines")
        self.setMinimumSize(600, 400)
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["", "ID", "Machine Name"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setColumnHidden(1, True)  # Hide ID

        self.select_all_checkbox = QCheckBox("Select All")
        restore_button = QPushButton("Restore Selected")
        restore_button.setObjectName("PrimaryButton")
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("SecondaryButton")

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.select_all_checkbox)
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(restore_button)
        layout.addWidget(self.table)
        layout.addLayout(button_layout)

        self.select_all_checkbox.stateChanged.connect(
            lambda state: self._toggle_all(state == Qt.CheckState.Checked.value))
        cancel_button.clicked.connect(self.reject)
        restore_button.clicked.connect(self._on_restore)

    def _populate_table(self):
        self.table.setRowCount(0)
        session = self.Session()
        try:
            for row, machine in enumerate(ops.get_deleted_machines(session)):
                self.table.insertRow(row)
                chk_box = QTableWidgetItem()
                chk_box.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk_box.setCheckState(Qt.CheckState.Unchecked)
                self.table.setItem(row, 0, chk_box)
                self.table.setItem(row, 1, QTableWidgetItem(str(machine.id)))
                self.table.setItem(row, 2, QTableWidgetItem(machine.name))
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
            QMessageBox.warning(self, "No Selection", "Please select at least one machine to restore.")
            return

        session = self.Session()
        try:
            validated_data = RestoreValidator(machine_ids=ids)
            num = ops.restore_machines(session, validated_data)
            QMessageBox.information(self, "Success", f"{num} machine(s) restored.")
            self.operation_successful.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred: {e}")
        finally:
            session.close()

    def open(self):
        self._populate_table()
        self.exec()


# --- Main View Class ---

class ExtruderMachineView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.setObjectName("ExtruderMachineModule")
        self._setup_ui()
        self._connect_signals()

        # Initialize dialogs
        self.create_dialog = CreateMachineDialog(self.Session, self)
        self.update_dialog = UpdateMachineDialog(self.Session, self)
        self.restore_dialog = RestoreMachineDialog(self.Session, self)

        load_stylesheet(self)
        self._populate_table()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()
        filter_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter by name...")
        self.search_input.setClearButtonEnabled(True)

        filter_layout.addWidget(QLabel("Filter:"))
        filter_layout.addWidget(self.search_input)

        self.add_button = QPushButton("Add New Machine")
        self.restore_button = QPushButton("Restore Deleted")
        self.add_button.setObjectName("PrimaryButton")
        self.restore_button.setObjectName("SecondaryButton")

        top_layout.addLayout(filter_layout)
        top_layout.addStretch()
        top_layout.addWidget(self.restore_button)
        top_layout.addWidget(self.add_button)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Machine Name", "Created By", "Created At"])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(0, True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        layout.addLayout(top_layout)
        layout.addWidget(self.table)

    def _connect_signals(self):
        self.add_button.clicked.connect(self._handle_add)
        self.restore_button.clicked.connect(self._handle_restore)
        self.search_input.textChanged.connect(self._apply_filters)

        self.table.customContextMenuRequested.connect(self.show_table_context_menu)

    def _populate_table(self):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        session = self.Session()
        try:
            machines = ops.get_all_machines_with_creator(session)
            for row, result in enumerate(machines):
                machine, creator_name = result
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(str(machine.id)))
                self.table.setItem(row, 1, QTableWidgetItem(machine.name))
                self.table.setItem(row, 2, QTableWidgetItem(creator_name or "N/A"))
                self.table.setItem(row, 3, QTableWidgetItem(machine.created_at.strftime("%Y-%m-%d %H:%M")))
        finally:
            session.close()
        self.table.setSortingEnabled(True)

    def show_table_context_menu(self, position):
        item = self.table.itemAt(position)
        if not item: return

        context_menu = QMenu(self)
        edit_action = QAction(qta.icon("fa5s.edit", color="#007bff"), "Edit Machine", self)
        delete_action = QAction(qta.icon("fa5s.trash-alt", color="#dc3545"), "Delete Machine", self)
        context_menu.addAction(edit_action)
        context_menu.addAction(delete_action)

        row = item.row()
        machine_id = int(self.table.item(row, 0).text())
        machine_name = self.table.item(row, 1).text()

        action = context_menu.exec(self.table.mapToGlobal(position))
        if action == edit_action:
            self._handle_edit(machine_id, machine_name)
        elif action == delete_action:
            self._handle_delete(machine_id, machine_name)


    def _apply_filters(self):
        """Show/hide table rows based on filter criteria."""
        name_filter = self.search_input.text().lower()

        for row in range(self.table.rowCount()):
            name_match = name_filter in self.table.item(row, 1).text().lower()

            self.table.setRowHidden(row, not (name_match))
            

    def _handle_add(self):
        self.create_dialog.operation_successful.connect(self._populate_table)
        self.create_dialog.open()
        self.create_dialog.operation_successful.disconnect(self._populate_table)

    def _handle_edit(self, machine_id: int, machine_name: str):
        self.update_dialog.operation_successful.connect(self._populate_table)
        self.update_dialog.open(machine_id, machine_name)
        self.update_dialog.operation_successful.disconnect(self._populate_table)

    def _handle_delete(self, machine_id: int, machine_name: str):
        msg = f"Are you sure you want to delete the machine '{machine_name}'?"
        dialog = ConfirmationDialog(self, message=msg)
        if dialog.exec():
            session = self.Session()
            try:
                ops.soft_delete_machine(session, machine_id)
                QMessageBox.information(self, "Success", "Machine has been deleted.")
                self._populate_table()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete machine: {e}")
            finally:
                session.close()

    def _handle_restore(self):
        self.restore_dialog.operation_successful.connect(self._populate_table)
        self.restore_dialog.open()
        self.restore_dialog.operation_successful.disconnect(self._populate_table)