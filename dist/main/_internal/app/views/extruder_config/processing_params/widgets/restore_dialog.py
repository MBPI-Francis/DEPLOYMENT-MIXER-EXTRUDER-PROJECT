# app/views/extruder_config/processing_params/restore_dialog.py
import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QMessageBox, QListWidgetItem, QLabel
)
from sqlalchemy.orm import Session
from .. import ops


class RestoreDialog(QDialog):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)

        style_path = os.path.join(os.path.dirname(__file__), '..', 'styles.css')
        with open(style_path, 'r') as f:
            self.setStyleSheet(f.read())


        self.session = session
        self.selected_machine_id = None  # Property to store the result

        self.setWindowTitle("Restore Parameter Sets")
        self.setMinimumWidth(400)
        self.setModal(True)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel("Select a machine to restore its parameter set:"))

        self.deleted_list = QListWidget()
        main_layout.addWidget(self.deleted_list)

        button_layout = QHBoxLayout()
        self.restore_button = QPushButton("Restore")
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        self.restore_button.setObjectName("PrimaryButton")
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.restore_button)

        main_layout.addLayout(button_layout)

        self.restore_button.clicked.connect(self._on_accept)
        self.cancel_button.clicked.connect(self.reject)

        self.populate_list()

    def populate_list(self):
        """Fetches and displays the list of soft-deleted machines."""
        deleted_machines = ops.get_soft_deleted_machines(self.session)
        if not deleted_machines:
            self.deleted_list.addItem("No deleted records found.")
            self.deleted_list.setEnabled(False)
            self.restore_button.setEnabled(False)
        else:
            for machine in deleted_machines:
                item = QListWidgetItem(machine.name)
                item.setData(Qt.ItemDataRole.UserRole, machine.id)
                self.deleted_list.addItem(item)

    def _on_accept(self):
        """
        When the user clicks 'Restore', this method validates the selection,
        stores the selected ID, and closes the dialog with an 'Accepted' signal.
        """
        selected_item = self.deleted_list.currentItem()
        if not selected_item or selected_item.data(Qt.ItemDataRole.UserRole) is None:
            QMessageBox.warning(self, "No Selection", "Please select a machine to restore.")
            return

        # Store the selected ID to be retrieved by the handler
        self.selected_machine_id = selected_item.data(Qt.ItemDataRole.UserRole)

        # This signals to the handler that the user confirmed the action
        self.accept()