# app/views/extruder_config/processing_params/widgets/confirmation_dialog.py

import os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QLineEdit
)


class ConfirmationDialog(QDialog):
    """A dialog that requires the user to type 'YES' to confirm an action."""

    def __init__(self, parent=None, message: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Confirm Action")
        self.setMinimumWidth(450)
        self.setModal(True)

        # --- Load the shared stylesheet ---
        style_path = os.path.join(os.path.dirname(__file__), '..', 'styles.css')
        if os.path.exists(style_path):
            with open(style_path, 'r') as f:
                self.setStyleSheet(f.read())
        # ------------------------------------

        layout = QVBoxLayout(self)
        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.instructions_label = QLabel("To proceed, please type <b>YES</b> in the box below.")
        self.confirm_input = QLineEdit()
        self.confirm_input.setPlaceholderText("Type YES to confirm")
        self.confirm_input.setObjectName("ConfirmInput")  # Matches the CSS ID selector

        self.proceed_button = QPushButton("Proceed")
        self.proceed_button.setEnabled(False)
        self.proceed_button.setObjectName("PrimaryButton")  # Matches the CSS ID selector
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setObjectName("SecondaryButton")
        # No specific object name needed for cancel, will use default QPushButton style

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.proceed_button)

        layout.addWidget(self.message_label)
        layout.addWidget(self.instructions_label)
        layout.addWidget(self.confirm_input)
        layout.addLayout(button_layout)

        # Enable the 'Proceed' button only when the input text is exactly "YES"
        self.confirm_input.textChanged.connect(lambda text: self.proceed_button.setEnabled(text == "YES"))

        # Connect the buttons to the dialog's standard accept/reject signals
        self.proceed_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)