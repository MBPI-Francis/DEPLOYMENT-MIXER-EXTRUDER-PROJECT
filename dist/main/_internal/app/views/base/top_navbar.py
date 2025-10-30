# app/views/base/top_navbar.py

from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QPushButton, QLabel
)
from PyQt6.QtCore import QSize
from PyQt6.QtGui import QFont
import qtawesome as qta


class TopNavBar(QWidget):
    """
    The top navigation bar for the application.
    Contains the hamburger menu, page title, and user profile section.
    """

    def __init__(self, dashboard, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dashboard = dashboard  # Reference to the main Base window

        self.setObjectName("TopBar")
        self.setFixedHeight(50)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(15)  # Add some spacing between elements

        # --- Hamburger Menu Button ---
        self.hamburger_button = QPushButton(icon=qta.icon("fa5s.times", color="#2c3e50"))
        self.hamburger_button.setIconSize(QSize(20, 20))
        self.hamburger_button.setObjectName("TopBarButton")
        self.hamburger_button.clicked.connect(self.dashboard.toggle_side_menu)
        layout.addWidget(self.hamburger_button)

        # --- Page Title Label (Moved Here) ---
        self.page_title_label = QLabel("Page Title")
        self.page_title_label.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.page_title_label.setObjectName("PageTitle")
        layout.addWidget(self.page_title_label)

        # This spacer pushes all subsequent widgets to the right
        layout.addStretch()

        # --- Sync DB Button ---
        self.sync_db_button = QPushButton(icon=qta.icon("fa5s.sync-alt", color="#2c3e50"), text=" Sync Legacy DB")
        self.sync_db_button.setObjectName("TopBarButton")
        self.sync_db_button.clicked.connect(self.dashboard.start_db_sync)
        layout.addWidget(self.sync_db_button)

        # --- Notification Button ---
        notification_button = QPushButton()
        notification_button.setIcon(qta.icon("fa5s.bell", color="#2c3e50"))
        notification_button.setObjectName("TopBarButton")
        layout.addWidget(notification_button)

        # --- User Profile Widget ---
        profile_widget = self._create_profile_widget()
        layout.addWidget(profile_widget)

    def _create_profile_widget(self) -> QWidget:
        """Creates the user profile display widget for the top right."""
        widget = QWidget()
        widget.setObjectName("TopBarProfileWidget")
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        user_label = QLabel(f"<strong>{self.dashboard.username.title()}</strong>")
        user_label.setObjectName("TopBarUserLabel")
        layout.addWidget(user_label)

        user_icon = QLabel()
        user_icon.setPixmap(qta.icon("fa5s.user-circle", color="#2c3e50").pixmap(30, 30))
        layout.addWidget(user_icon)

        return widget

    def set_page_title(self, title: str):
        """Public method to allow the main window to update the title."""
        self.page_title_label.setText(title)