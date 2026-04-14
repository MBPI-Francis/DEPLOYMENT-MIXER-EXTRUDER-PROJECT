import sys
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QLabel, QPushButton,
                             QFrame, QHBoxLayout, QGraphicsDropShadowEffect)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor


class MaintenancePage(QWidget):
    def __init__(self, end_date_str):
        super().__init__()

        # --- Window Setup ---
        self.setWindowTitle("System Maintenance")
        self.setFixedSize(500, 400)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Main Layout (Background matching your QMainWindow style)
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)

        # --- THE CENTRAL CARD ---
        # Using #ffffff and border-radius matching your theme logic
        self.card = QFrame()
        self.card.setObjectName("MainCard")
        self.card.setStyleSheet("""
            #MainCard {
                background-color: #ffffff;
                border: 1px solid #dfe6e9;
                border-radius: 8px;
            }
        """)

        # Subtle Shadow
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(20)
        shadow.setXOffset(0)
        shadow.setYOffset(4)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.card.setGraphicsEffect(shadow)

        self.card_layout = QVBoxLayout(self.card)
        self.card_layout.setContentsMargins(40, 40, 40, 40)
        self.card_layout.setSpacing(0)

        # --- 1. ICON / BRANDING ---
        self.logo_label = QLabel("SYSTEM STATUS")
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.logo_label.setStyleSheet("""
            color: #95a5a6; 
            font-family: 'Segoe UI'; 
            font-weight: bold; 
            font-size: 11px; 
            letter-spacing: 1.5px;
            margin-bottom: 10px;
        """)

        # --- 2. TITLE ---
        # Using #2c3e50 from your "SideMenu" / "PageTitle" styles
        title = QLabel("Under Maintenance")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            color: #2c3e50; 
            font-family: 'Segoe UI'; 
            font-size: 28px; 
            font-weight: bold;
        """)

        # --- 3. MESSAGE ---
        # Using #34495e from your "PageMessage" style
        message = QLabel(
            "We are currently updating our systems to serve you better. "
            "The application will be available shortly."
        )
        message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message.setWordWrap(True)
        message.setStyleSheet("""
            color: #34495e; 
            font-family: 'Segoe UI'; 
            font-size: 14px; 
            margin-top: 15px;
            line-height: 140%;
        """)

        # --- 4. TIME ESTIMATE BOX ---
        # Using #ecf0f1 for background and #2c3e50 for text
        time_box = QFrame()
        time_box.setStyleSheet("""
            background-color: #ecf0f1; 
            border-radius: 5px; 
            margin-top: 0px;
        """)
        time_layout = QVBoxLayout(time_box)

        time_header = QLabel("ESTIMATED COMPLETION")
        time_header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        time_header.setStyleSheet("color: #95a5a6; font-size: 10px; font-weight: bold;")

        self.time_val = QLabel(end_date_str)
        self.time_val.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_val.setStyleSheet("color: #2c3e50; font-size: 15px; font-weight: bold;")

        time_layout.addWidget(time_header)
        time_layout.addWidget(self.time_val)

        # --- 5. ACTION BUTTON ---
        # Styled to match your #SideMenu QPushButton hover/focus states
        self.btn_exit = QPushButton("Close Application")
        self.btn_exit.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_exit.setFixedHeight(70)
        self.btn_exit.setStyleSheet("""
            QPushButton {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: none;
                border-radius: 5px;
                font-family: "Segoe UI";
                font-size: 14px;
                font-weight: bold;
                margin-top: 30px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
            QPushButton:pressed {
                background-color: #1a252f;
            }
        """)
        self.btn_exit.clicked.connect(self.close_app)

        # --- Assemble ---
        self.card_layout.addWidget(self.logo_label)
        self.card_layout.addWidget(title)
        self.card_layout.addWidget(message)
        self.card_layout.addWidget(time_box)
        self.card_layout.addWidget(self.btn_exit)

        self.main_layout.addWidget(self.card)

    def close_app(self):
        from PyQt6.QtWidgets import QApplication
        QApplication.quit()

    # Drag functionality for frameless window
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton:
            self.move(self.pos() + event.globalPosition().toPoint() - self.drag_pos)
            self.drag_pos = event.globalPosition().toPoint()