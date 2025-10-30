# app/views/extruder_form/entry_form/widgets/success_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSizePolicy, QDialogButtonBox
)
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtCore import Qt


class SuccessDialog(QDialog):
    """
    A custom, user-friendly dialog to show a success message.
    """

    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Success")
        self.setMinimumWidth(350)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Main Layout
        main_layout = QVBoxLayout(self)

        # Top section with icon and text
        top_layout = QHBoxLayout()
        main_layout.addLayout(top_layout)

        # Icon (using a built-in Qt icon for simplicity)
        icon_label = QLabel()
        # You can replace this with your own icon file if you have one:
        # pixmap = QPixmap("path/to/your/success_icon.png")
        pixmap = self.style().standardIcon(
            self.style().StandardPixmap.SP_DialogApplyButton
        ).pixmap(48, 48)  # A nice checkmark/apply icon
        icon_label.setPixmap(pixmap)
        icon_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        top_layout.addWidget(icon_label)

        # Text content
        text_layout = QVBoxLayout()
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("font-size: 14pt;")
        message_label = QLabel(message)
        message_label.setWordWrap(True)

        text_layout.addWidget(title_label)
        text_layout.addWidget(message_label)
        top_layout.addLayout(text_layout)

        # Separator Line
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_layout.addWidget(separator)

        # Bottom button
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)