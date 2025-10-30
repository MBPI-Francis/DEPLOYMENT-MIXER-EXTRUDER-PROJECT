# # app/views/extruder_form/entry_form/widgets/error_dialog.py
#
# from PyQt6.QtWidgets import (
#     QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
#     QSizePolicy, QDialogButtonBox, QTextEdit, QWidget, QGroupBox
# )
# from PyQt6.QtGui import QPixmap
# from PyQt6.QtCore import Qt
# from typing import List
#
# class ErrorDialog(QDialog):
#     """
#     An improved, user-friendly dialog for displaying errors with better
#     visual hierarchy and an optional list of specific issues.
#     """
#     # --- THIS IS THE FIX ---
#     # The method must be named __init__ with double underscores
#     def __init__(self, title: str, message: str, issues: List[str] = None, details: str = "", parent=None):
#         # The super() call must also use __init__
#         super().__init__(parent)
#
#         self.setWindowTitle("Error")
#         self.setMinimumWidth(450)
#         self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
#
#         # Main Layout
#         main_layout = QVBoxLayout(self)
#         main_layout.setSpacing(15)
#
#         # Top section with icon and text
#         top_layout = QHBoxLayout()
#         main_layout.addLayout(top_layout)
#
#         # Icon
#         icon_label = QLabel()
#         pixmap = self.style().standardIcon(
#             self.style().StandardPixmap.SP_MessageBoxCritical
#         ).pixmap(48, 48)
#         icon_label.setPixmap(pixmap)
#         icon_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
#         top_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
#
#         # Text content
#         text_layout = QVBoxLayout()
#         title_label = QLabel(f"<b>{title}</b>")
#         title_label.setStyleSheet("font-size: 14pt;")
#         message_label = QLabel(message)
#         message_label.setWordWrap(True)
#
#         text_layout.addWidget(title_label)
#         text_layout.addWidget(message_label)
#         top_layout.addLayout(text_layout)
#
#         # Optional list of specific issues (e.g., missing fields)
#         if issues:
#             issues_group = QGroupBox("Specific Issues:")
#             issues_layout = QVBoxLayout(issues_group)
#             list_text = "<ul>" + "".join(f"<li>{issue}</li>" for issue in issues) + "</ul>"
#             issues_label = QLabel(list_text)
#             issues_label.setWordWrap(True)
#             issues_layout.addWidget(issues_label)
#             main_layout.addWidget(issues_group)
#
#         # Optional, expandable details section
#         if details:
#             self.details_button = QPushButton("Show Technical Details")
#             self.details_button.setCheckable(True)
#             self.details_button.setChecked(False)
#             self.details_text = QTextEdit()
#             self.details_text.setText(details)
#             self.details_text.setReadOnly(True)
#             self.details_text.setFontFamily("monospace")
#             self.details_text.setVisible(False)
#             self.details_button.toggled.connect(self.details_text.setVisible)
#             main_layout.addWidget(self.details_button)
#             main_layout.addWidget(self.details_text)
#
#         # Bottom button
#         button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
#         button_box.accepted.connect(self.accept)
#         main_layout.addWidget(button_box)


# app/views/extruder_form/entry_form/widgets/error_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSizePolicy, QDialogButtonBox, QTextEdit, QWidget, QGroupBox, QScrollArea
)
from PyQt6.QtGui import QPixmap
from PyQt6.QtCore import Qt
from typing import List


class ErrorDialog(QDialog):
    """
    An improved, resizable, and scrollable dialog for displaying errors.
    """

    def __init__(self, title: str, message: str, issues: List[str] = None, details: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Error")
        self.setMinimumWidth(450)
        # --- FIX: Make the dialog resizable by the user ---
        self.setSizeGripEnabled(True)
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint & ~Qt.WindowType.WindowContextHelpButtonHint)

        # Main Layout for the entire dialog
        main_layout = QVBoxLayout(self)

        # --- NEW: Scroll Area Setup ---
        # 1. Create the Scroll Area
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)  # This is crucial!
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 2. Create a container widget to hold all the scrollable content
        scroll_content_widget = QWidget()

        # 3. Create the layout for the container widget
        content_layout = QVBoxLayout(scroll_content_widget)
        content_layout.setSpacing(15)

        # --- All existing content now goes into the 'content_layout' ---

        # Top section with icon and text
        top_layout = QHBoxLayout()
        icon_label = QLabel()
        pixmap = self.style().standardIcon(self.style().StandardPixmap.SP_MessageBoxCritical).pixmap(48, 48)
        icon_label.setPixmap(pixmap)
        icon_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        top_layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)

        text_layout = QVBoxLayout()
        title_label = QLabel(f"<b>{title}</b>")
        title_label.setStyleSheet("font-size: 14pt;")
        message_label = QLabel(message)
        message_label.setWordWrap(True)
        text_layout.addWidget(title_label)
        text_layout.addWidget(message_label)
        top_layout.addLayout(text_layout)

        content_layout.addLayout(top_layout)

        # Optional list of specific issues
        if issues:
            issues_group = QGroupBox("Specific Issues:")
            issues_layout = QVBoxLayout(issues_group)
            list_text = "<ul>" + "".join(f"<li>{issue}</li>" for issue in issues) + "</ul>"
            issues_label = QLabel(list_text)
            issues_label.setWordWrap(True)
            issues_layout.addWidget(issues_label)
            content_layout.addWidget(issues_group)

        # Optional, expandable details section
        if details:
            self.details_button = QPushButton("Show Technical Details")
            self.details_button.setCheckable(True)
            self.details_button.setChecked(False)
            self.details_text = QTextEdit()
            self.details_text.setText(details)
            self.details_text.setReadOnly(True)
            self.details_text.setFontFamily("monospace")
            self.details_text.setVisible(False)
            self.details_button.toggled.connect(self.details_text.setVisible)
            content_layout.addWidget(self.details_button)
            content_layout.addWidget(self.details_text)

        # Add a spacer at the end of the content to push everything up
        content_layout.addStretch()

        # 4. Set the container widget as the scroll area's content
        scroll_area.setWidget(scroll_content_widget)

        # --- Add the scroll area to the main dialog layout ---
        main_layout.addWidget(scroll_area)

        # Bottom button (outside the scroll area)
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        button_box.accepted.connect(self.accept)
        main_layout.addWidget(button_box)

        # Set a reasonable default size
        self.resize(500, 400)