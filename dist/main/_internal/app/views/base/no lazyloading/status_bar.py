import sys
import socket
from getmac import get_mac_address
from datetime import datetime

from PyQt6.QtCore import QSize, QTimer
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QStatusBar,
    QLabel,
    QFrame,
    QWidget,
    QVBoxLayout
)
from qtawesome import icon as qta_icon


# =============================================================================
# YOUR MODIFIED BottomStatusBar CLASS
# (Paste the class from Step 2 here)
# =============================================================================
class BottomStatusBar:
    def __init__(self):
        self.status_timer = None
        self.program_credits = None
        self.powered_by_software = None
        self.time_label = None
        self.db_status_text_label = None
        self.db_status_icon_label = None
        self.status_bar = None
        self.root = None

        # --- NEW WIDGETS INITIALIZED ---
        self.pc_name_icon = None
        self.pc_name_label = None
        self.ip_address_icon = None
        self.ip_address_label = None
        self.mac_address_icon = None
        self.mac_address_label = None
        # --- END NEW WIDGETS ---

    @staticmethod
    def create_separator():
        separator = QLabel(" | ")
        separator.setStyleSheet("""
            color: grey;
            padding: 0 5px;
        """)

        return separator


    def setup_status_bar(self, dashboard):
        self.root = dashboard

        self.root.status_bar = QStatusBar()
        self.root.setStatusBar(self.root.status_bar)

        # --- EXISTING WIDGETS ---
        self.root.db_status_icon_label = QLabel()
        self.root.db_status_icon_label.setFixedSize(QSize(20, 20))
        self.root.db_status_icon_label.setObjectName("Base-db-status-icon-label")

        self.root.db_status_text_label = QLabel()
        self.root.db_status_text_label.setObjectName("Base-db-status-text-label")

        self.root.time_label = QLabel()
        self.root.time_label.setObjectName("Base-status-time-label")

        self.root.program_credits = QLabel("Developed by: IT Department Team")

        # --- NEW: Get System Information ---
        pc_name = socket.gethostname()
        try:
            # This is a reliable way to get the primary IP address
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip_address = s.getsockname()[0]
        except Exception:
            ip_address = "N/A"  # In case of no network connection

        mac_address = get_mac_address()

        # --- NEW: Create Labels for System Info ---
        # PC Name
        self.root.pc_name_icon = QLabel()
        self.root.pc_name_icon.setPixmap(qta_icon("fa5s.desktop", color="gray").pixmap(QSize(16, 16)))
        self.root.pc_name_label = QLabel(f" {pc_name}")

        # IP Address
        self.root.ip_address_icon = QLabel()
        self.root.ip_address_icon.setPixmap(qta_icon("fa5s.network-wired", color="gray").pixmap(QSize(16, 16)))
        self.root.ip_address_label = QLabel(f"IP: {ip_address}")

        # MAC Address
        self.root.mac_address_icon = QLabel()
        self.root.mac_address_icon.setPixmap(qta_icon("fa5s.barcode", color="gray").pixmap(QSize(16, 16)))
        self.root.mac_address_label = QLabel(f"MAC: {mac_address}")
        # --- END NEW ---

        # icon for db_status_icon_label
        self.root.db_status_icon_label.setPixmap(
            qta_icon("fa5s.check-circle", color="green").pixmap(QSize(16, 16))
        )
        self.root.db_status_text_label.setText("DB Connected ")

        # --- UPDATED: Add all widgets to the status bar ---
        # DB Status
        self.root.status_bar.addPermanentWidget(self.root.db_status_icon_label)
        self.root.status_bar.addPermanentWidget(self.root.db_status_text_label)
        self.root.status_bar.addPermanentWidget(self.create_separator())

        # Time
        self.root.status_bar.addPermanentWidget(self.root.time_label)
        self.root.status_bar.addPermanentWidget(self.create_separator())

        # PC NAME
        self.root.status_bar.addPermanentWidget(self.root.pc_name_icon)
        self.root.status_bar.addPermanentWidget(self.root.pc_name_label)
        self.root.status_bar.addPermanentWidget(self.create_separator())

        self.root.status_bar.addPermanentWidget(self.root.ip_address_icon)
        self.root.status_bar.addPermanentWidget(self.root.ip_address_label)
        self.root.status_bar.addPermanentWidget(self.create_separator())

        self.root.status_bar.addPermanentWidget(self.root.mac_address_icon)
        self.root.status_bar.addPermanentWidget(self.root.mac_address_label)
        self.root.status_bar.addPermanentWidget(self.create_separator())

        self.root.status_bar.addPermanentWidget(self.root.program_credits)


        # --- END UPDATED ---

        self.root.status_timer = QTimer(self.root)
        self.root.status_timer.timeout.connect(
            lambda: self.root.time_label.setText(f" {datetime.now().strftime('%b %d, %Y  %I:%M:%S %p')} "
                                                 ))
        self.root.status_timer.setObjectName("Base-status-qtimer")

        self.root.status_timer.start(1000)
