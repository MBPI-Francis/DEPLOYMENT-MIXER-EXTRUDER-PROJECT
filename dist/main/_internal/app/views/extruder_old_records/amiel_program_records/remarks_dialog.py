from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QTextEdit, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt


class RemarksDialog(QDialog):
    def __init__(self, remarks_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Full Remarks")
        self.setFixedSize(400, 300)
        self.setStyleSheet("background-color: white;")

        layout = QVBoxLayout(self)

        # Header
        lbl = QLabel("Remarks Content:")
        lbl.setStyleSheet("font-weight: bold; font-size: 14px; color: #333;")
        layout.addWidget(lbl)

        # Text Area (Read Only)
        self.text_area = QTextEdit()
        self.text_area.setPlainText(remarks_text if remarks_text else "No content.")
        self.text_area.setReadOnly(True)
        self.text_area.setStyleSheet("""
            QTextEdit {
                border: 1px solid #ced4da;
                border-radius: 4px;
                padding: 10px;
                font-size: 13px;
                color: #495057;
                background-color: #f8f9fa;
            }
        """)
        layout.addWidget(self.text_area)

        # Close Button
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.clicked.connect(self.accept)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #5a6268; }
        """)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)