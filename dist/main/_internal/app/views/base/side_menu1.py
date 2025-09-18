# app/views/base/side_menu.py

from PyQt6.QtGui import QFont
# --- MODIFIED: Add QLabel to imports ---
from PyQt6.QtWidgets import (QWidget,
                             QLabel,
                             QVBoxLayout,
                             QPushButton)
from PyQt6.QtCore import Qt, QSize
import qtawesome as qta


class SideMenu:
    def __init__(self):
        self.root = None

    def side_menu_widget(self, dashboard):
        self.root = dashboard
        side_menu = QWidget()
        side_menu.setObjectName("SideMenu")
        side_menu.setMinimumWidth(0)
        side_menu.setMaximumWidth(200)

        layout = QVBoxLayout(side_menu)
        layout.setContentsMargins(10, 10, 10, 20)
        layout.setSpacing(15)

        # # --- NEW: BRAND LOGO TEXT ---
        # logo_label = QLabel("mbpi")
        # logo_label.setObjectName("SideMenuLogo")
        # # Set the font. Qt will use a fallback if "Myriad Pro" is not available.
        # logo_label.setFont(QFont("Myriad", 30, QFont.Weight.Bold))
        # # Center the text horizontally
        # logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # layout.addWidget(logo_label)
        # # --- END NEW ---

        # === Helper to create buttons ---
        def create_menu_button(text, icon_name, target_index):
            button = QPushButton(f"  {text}")
            button.setIcon(qta.icon(icon_name, color="#ecf0f1"))
            button.setIconSize(QSize(20, 20))
            button.setToolTip(text)
            button.setLayoutDirection(Qt.LayoutDirection.LeftToRight)
            button.clicked.connect(lambda: self.root.stacked_widget.setCurrentIndex(target_index))
            return button

        # === Mixer Section ===
        mixer_label = QLabel("MIXER MODULES")
        mixer_label.setObjectName("SectionHeader")
        layout.addWidget(mixer_label)
        layout.addWidget(create_menu_button("Mixer Machine", "fa5s.cogs", 0))
        layout.addWidget(create_menu_button("Mixer Form", "fa5s.file-signature", 1))
        layout.addWidget(create_menu_button("Mixer Report", "fa5s.chart-bar", 2))

        # === Extruder Section ===
        extruder_label = QLabel("EXTRUDER MODULES")
        extruder_label.setObjectName("SectionHeader")
        layout.addWidget(extruder_label)
        layout.addWidget(create_menu_button("Extruder Form", "fa5s.file-alt", 3))
        layout.addWidget(create_menu_button("Extruder Report", "fa5s.chart-pie", 4))

        layout.addStretch()

        # --- Logout Button ---
        btn_logout = QPushButton("  Logout")
        btn_logout.setIcon(qta.icon("fa5s.sign-out-alt", color="#ecf0f1"))
        btn_logout.setIconSize(QSize(20, 20))
        btn_logout.setToolTip("Logout")
        btn_logout.clicked.connect(self.root.close_dashboard_main_window)
        layout.addWidget(btn_logout)

        return side_menu