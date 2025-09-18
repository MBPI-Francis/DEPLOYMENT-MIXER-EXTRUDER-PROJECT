# _ProductionProgramPoject/app/views/mixer_machines/main.py

import os
from datetime import datetime
from typing import Type, Callable, Optional
from pydantic import ValidationError

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView, QLineEdit,
    QAbstractItemView, QDialog, QFormLayout, QLabel, QDateEdit,
    QCheckBox, QMenu
)
from PyQt6.QtCore import pyqtSignal, Qt, QDate
from PyQt6.QtGui import QIcon, QAction
import qtawesome as qta
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# Import the database operations and validators we created
from ...database.mixer_machine_ops import (
    get_all_machines_with_creator, create_machine, update_machine,
    soft_delete_machine, get_deleted_machines, restore_machines,
    check_machine_name_exists  # NEW: Import the duplicate checker
)
from ...validators.mixer_machine_validators import MixerMachineValidator, RestoreValidator

def load_stylesheet(widget):
    """Loads the stylesheet for the mixer machine module."""
    current_dir = os.path.dirname(os.path.realpath(__file__))
    css_path = os.path.join(current_dir, "styles/mixer_machine_styles.css")
    try:
        with open(css_path, "r") as f:
            # Apply the stylesheet directly to the widget passed in.
            widget.setStyleSheet(f.read())
    except FileNotFoundError:
        print(f"Warning: Stylesheet not found at {css_path}")
        # The module will still function, just without the custom styles.


# --- Reusable Dialog Classes ---

class PasswordConfirmationDialog(QDialog):
    """A simple dialog to securely ask for the user's password."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Confirm Action")
        self.setModal(True)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        form_layout = QFormLayout(self)
        form_layout.addRow(QLabel("Please enter your password to proceed:"), self.password_input)

        confirm_button = QPushButton("Confirm")
        cancel_button = QPushButton("Cancel")
        confirm_button.setObjectName("SuccessButton")

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(confirm_button)
        form_layout.addRow(button_layout)

        confirm_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

    def get_password(self) -> str:
        return self.password_input.text()





class CreateMachineDialog(QDialog):
    """Dialog for creating a new machine."""
    operation_successful = pyqtSignal()

    def __init__(self, session_factory: Callable[..., sessionmaker], user_id: int, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.user_id = user_id

        # ... (UI setup code remains unchanged) ...
        self.setWindowTitle("Add New Mixer Machine")
        self.setMinimumWidth(450)
        self.setModal(True)
        self.name_input = QLineEdit()
        self.save_button = QPushButton("Save Machine")
        self.cancel_button = QPushButton("Cancel")
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
        """Enable save button only if input is valid."""
        try:
            MixerMachineValidator(name=self.name_input.text())
            self.save_button.setEnabled(True)
        except ValidationError:
            self.save_button.setEnabled(False)

    def _on_save(self):
        """MODIFIED: Handle the save action with duplicate checking."""
        session = self.Session()
        try:
            # 1. Validate the input format first
            validated_data = MixerMachineValidator(name=self.name_input.text())

            # 2. NEW: Check for business logic errors (e.g., duplicates)
            if check_machine_name_exists(session, name=validated_data.name):
                QMessageBox.warning(self, "Duplicate Entry",
                                    f"A machine with the name '{validated_data.name}' already exists.")
                return  # Stop the save process

            # 3. If all checks pass, proceed with creation
            create_machine(session, validated_data, self.user_id)
            QMessageBox.information(self, "Success", f"Machine '{validated_data.name}' was created successfully.")
            self.operation_successful.emit()
            self.accept()
        except ValidationError as e:
            QMessageBox.warning(self, "Validation Error", f"Please check your input:\n{e}")
        except IntegrityError:  # Catches unique constraint violations at the DB level as a fallback
            QMessageBox.critical(self, "Database Error", "This machine name already exists.")
        except Exception as e:
            QMessageBox.critical(self, "An Error Occurred", f"Could not save the machine: {e}")
        finally:
            session.close()

    def open(self):
        """Public method to clear and show the dialog."""
        self.name_input.clear()
        self._validate_input()
        self.exec()


class UpdateMachineDialog(QDialog):
    """Dialog for updating an existing machine."""
    operation_successful = pyqtSignal()

    def __init__(self, session_factory: Callable[..., sessionmaker], user_id: int, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.user_id = user_id
        self.machine_id = None
        self.original_name = ""  # NEW: Store the original name

        # ... (UI setup code remains unchanged) ...
        self.setWindowTitle("Edit Mixer Machine")
        self.setMinimumWidth(450)
        self.setModal(True)
        self.name_input = QLineEdit()
        self.save_button = QPushButton("Save Changes")
        self.cancel_button = QPushButton("Cancel")
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
        """Enable save button only if the input is valid and has changed."""
        is_valid = False
        try:
            # Check if the text is a valid machine name format
            MixerMachineValidator(name=self.name_input.text())
            # Additionally, check if the name has actually changed from the original
            if self.name_input.text().strip() != self.original_name:
                is_valid = True
        except ValidationError:
            is_valid = False

        self.save_button.setEnabled(is_valid)

    def _on_save(self):
        """MODIFIED: Handle the update action with duplicate checking."""
        if not self.machine_id: return
        session = self.Session()
        try:
            # 1. Validate the input format
            validated_data = MixerMachineValidator(name=self.name_input.text())

            # 2. NEW: Check if the new name conflicts with any *other* machine
            if check_machine_name_exists(session, name=validated_data.name, exclude_id=self.machine_id):
                QMessageBox.warning(self, "Duplicate Entry",
                                    f"Another machine with the name '{validated_data.name}' already exists.")
                return  # Stop the save process

            # 3. If all checks pass, proceed with the update
            update_machine(session, self.machine_id, validated_data, self.user_id)
            QMessageBox.information(self, "Success", "Machine has been updated.")
            self.operation_successful.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "An Error Occurred", f"Could not update the machine: {e}")
        finally:
            session.close()

    def open(self, machine_id: int, current_name: str):
        """MODIFIED: Store the original name when opening."""
        self.machine_id = machine_id
        self.original_name = current_name
        self.name_input.setText(current_name)
        self._validate_input()  # Initial validation state
        self.exec()

class RestoreMachineDialog(QDialog):
    """Dialog for viewing and restoring deleted machines."""
    operation_successful = pyqtSignal()

    def __init__(self, session_factory: Callable[..., sessionmaker], user_id: int, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.user_id = user_id

        self.setWindowTitle("Restore Deleted Machines")
        self.setMinimumSize(600, 400)
        self.setModal(True)
        self.setObjectName("MachineDialog")

        # --- Widgets & Layout ---
        layout = QVBoxLayout(self)
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["", "ID", "Machine Name"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.select_all_checkbox = QCheckBox("Select All")

        restore_button = QPushButton("Restore Selected")
        cancel_button = QPushButton("Cancel")
        restore_button.setObjectName("SuccessButton")

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.select_all_checkbox)
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(restore_button)

        layout.addWidget(self.table)
        layout.addLayout(button_layout)

        # --- Connections ---
        self.select_all_checkbox.stateChanged.connect(self._toggle_all_checkboxes)
        cancel_button.clicked.connect(self.reject)
        restore_button.clicked.connect(self._on_restore)

    def _populate_table(self):
        """Fetch and display deleted machines."""
        self.table.setRowCount(0)
        session = self.Session()
        try:
            deleted_machines = get_deleted_machines(session)
            for row_num, machine in enumerate(deleted_machines):
                self.table.insertRow(row_num)

                # Checkbox
                chk_box_item = QTableWidgetItem()
                chk_box_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
                chk_box_item.setCheckState(Qt.CheckState.Unchecked)
                self.table.setItem(row_num, 0, chk_box_item)

                # ID and Name
                self.table.setItem(row_num, 1, QTableWidgetItem(str(machine.id)))
                self.table.setItem(row_num, 2, QTableWidgetItem(machine.name))
        finally:
            session.close()

    def _toggle_all_checkboxes(self, state):
        """Check or uncheck all items in the table."""
        check_state = Qt.CheckState.Checked if state == 2 else Qt.CheckState.Unchecked
        for row in range(self.table.rowCount()):
            self.table.item(row, 0).setCheckState(check_state)

    def _on_restore(self):
        """Handle the restore action."""
        ids_to_restore = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() == Qt.CheckState.Checked:
                ids_to_restore.append(int(self.table.item(row, 1).text()))

        if not ids_to_restore:
            QMessageBox.warning(self, "No Selection", "Please select at least one machine to restore.")
            return

        session = self.Session()
        try:
            validated_data = RestoreValidator(machine_ids=ids_to_restore)
            num_restored = restore_machines(session, validated_data, self.user_id)
            QMessageBox.information(self, "Success", f"{num_restored} machine(s) have been restored.")
            self.operation_successful.emit()
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred: {e}")
        finally:
            session.close()

    def open(self):
        self._populate_table()
        self.exec()


# --- The Main View Class with Context Menu ---

class MixerMachineMainView(QWidget):
    """The main view for the Mixer Machine submodule with a modern context menu."""

    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.user_id = 1
        self.user_password = "password"

        self.setObjectName("MixerMachineModule")
        self._setup_ui()
        self._connect_signals()

        self.create_dialog = CreateMachineDialog(self.Session, self.user_id, self)
        self.update_dialog = UpdateMachineDialog(self.Session, self.user_id, self)
        self.restore_dialog = RestoreMachineDialog(self.Session, self.user_id, self)

        load_stylesheet(self)
        self._populate_table()

    def _setup_ui(self):
        """Initialize and arrange all widgets on the main view."""
        layout = QVBoxLayout(self)

        # ... (Top layout with filters and buttons remains unchanged) ...
        top_layout = QHBoxLayout()
        filter_layout = QHBoxLayout()
        self.name_filter_input = QLineEdit()
        self.name_filter_input.setPlaceholderText("Filter by name...")

        filter_layout.addWidget(QLabel("Filter:"))
        filter_layout.addWidget(self.name_filter_input)
        self.add_button = QPushButton("Add New Machine")
        self.restore_button = QPushButton("Restore Deleted")
        self.add_button.setObjectName("PrimaryButton")
        self.restore_button.setObjectName("SecondaryButton")
        top_layout.addLayout(filter_layout)
        top_layout.addStretch()
        top_layout.addWidget(self.restore_button)
        top_layout.addWidget(self.add_button)

        # --- Table Section ---
        self.table = QTableWidget()
        self.table.setObjectName("MachineTable")

        # MODIFIED: Column count is now 4 because we removed the "Actions" column
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Machine Name", "Created By", "Created At"])

        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setColumnHidden(0, True)

        # NEW: Enable the context menu policy
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        layout.addLayout(top_layout)
        layout.addWidget(self.table)

    def _connect_signals(self):
        """Central place to connect all widget signals to slots."""
        self.add_button.clicked.connect(self._handle_add)
        self.restore_button.clicked.connect(self._handle_restore)
        self.name_filter_input.textChanged.connect(self._apply_filters)

        # NEW: Connect the signal for the custom context menu
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)

    def _populate_table(self):
        """Fetch machine data and display it in the main table."""
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        session = self.Session()
        try:
            machines = get_all_machines_with_creator(session)
            for row_num, machine in enumerate(machines):
                self.table.insertRow(row_num)
                self.table.setItem(row_num, 0, QTableWidgetItem(str(machine.id)))
                self.table.setItem(row_num, 1, QTableWidgetItem(machine.name))
                self.table.setItem(row_num, 2, QTableWidgetItem(machine.created_by_username or "N/A"))
                self.table.setItem(row_num, 3, QTableWidgetItem(machine.created_at.strftime("%Y-%m-%d %H:%M")))

                # REMOVED: The old code for adding buttons to the actions column is now gone.
        finally:
            session.close()
        self.table.setSortingEnabled(True)

    # NEW: This method handles the right-click event.
    def show_table_context_menu(self, position):
        """
        Creates and shows a context menu when a user right-clicks on the table.
        """
        # Get the specific item that was right-clicked
        item = self.table.itemAt(position)
        if not item:
            return  # Do nothing if the click is on an empty area

        # --- Create the Menu ---
        context_menu = QMenu(self)

        # --- Create Actions for the Menu ---
        edit_action = QAction(qta.icon("fa5s.edit", color="blue"), "Edit Machine", self)
        delete_action = QAction(qta.icon("fa5s.trash-alt", color="red"), "Delete Machine", self)

        # Add actions to the menu
        context_menu.addAction(edit_action)
        context_menu.addAction(delete_action)

        # --- Connect Actions to Handler Methods ---
        # We need to get the data for the clicked row to pass to our handlers.
        row = item.row()
        machine_id = int(self.table.item(row, 0).text())
        machine_name = self.table.item(row, 1).text()

        # Use lambda functions to pass the specific row's data to the handlers
        edit_action.triggered.connect(lambda: self._handle_edit(machine_id, machine_name))
        delete_action.triggered.connect(lambda: self._handle_delete(machine_id))

        # --- Show the Menu ---
        # The `mapToGlobal` function converts the click position to screen coordinates.
        context_menu.exec(self.table.mapToGlobal(position))

    def _apply_filters(self):
        """Show/hide table rows based on filter criteria."""
        name_filter = self.name_filter_input.text().lower()

        for row in range(self.table.rowCount()):
            name_match = name_filter in self.table.item(row, 1).text().lower()

            self.table.setRowHidden(row, not (name_match))

    def _handle_add(self):
        """Launch the create dialog and refresh table on success."""
        self.create_dialog.operation_successful.connect(self._populate_table)
        self.create_dialog.open()
        self.create_dialog.operation_successful.disconnect(self._populate_table)

    def _handle_edit(self, machine_id: int, machine_name: str):
        """Launch the update dialog and refresh table on success."""
        self.update_dialog.operation_successful.connect(self._populate_table)
        self.update_dialog.open(machine_id, machine_name)
        self.update_dialog.operation_successful.disconnect(self._populate_table)

    def _handle_delete(self, machine_id: int):
        """Handle the delete action with password confirmation."""
        confirm = QMessageBox.warning(self, "Confirm Deletion",
                                      "Are you sure you want to delete this machine? This action cannot be undone directly.",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)

        if confirm == QMessageBox.StandardButton.Yes:
            pwd_dialog = PasswordConfirmationDialog(self)
            if pwd_dialog.exec():
                if pwd_dialog.get_password() == self.user_password:
                    session = self.Session()
                    try:
                        soft_delete_machine(session, machine_id, self.user_id)
                        QMessageBox.information(self, "Success", "Machine has been deleted.")
                        self._populate_table()
                    except Exception as e:
                        QMessageBox.critical(self, "Error", f"Could not delete machine: {e}")
                    finally:
                        session.close()
                else:
                    QMessageBox.critical(self, "Failed", "Incorrect password.")

    def _handle_restore(self):
        """Launch the restore dialog and refresh table on success."""
        self.restore_dialog.operation_successful.connect(self._populate_table)
        self.restore_dialog.open()
        self.restore_dialog.operation_successful.disconnect(self._populate_table)