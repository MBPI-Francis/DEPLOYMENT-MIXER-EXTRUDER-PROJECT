from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QVBoxLayout, QFrame, QPushButton
from PyQt6.QtCore import Qt, QSize
import qtawesome as qta

class SideMenu:
    """
    A factory class that creates and manages the side menu widget.
    This follows the original design but separates signal connection for stability.
    """
    def __init__(self):
        # We will store references to the buttons here so we can connect them later.
        self.btn_extruder_config = None
        self.btn_mixer_old_record = None
        self.btn_mixer_machine = None
        self.btn_mixer_form = None
        self.btn_mixer_report = None
        self.btn_extruder_form = None
        self.btn_extruder_report = None
        self.dashboard = None

    def side_menu_widget(self, dashboard) -> QWidget:
        """Creates the entire side menu widget and its contents."""
        self.dashboard = dashboard
        side_menu = QWidget()
        # This objectName is crucial for your base.css to apply the background color.
        side_menu.setObjectName("SideMenu") 

        layout = QVBoxLayout(side_menu)
        layout.setContentsMargins(10, 10, 10, 20)
        layout.setSpacing(5)

        # --- Create all buttons and store them as instance variables ---
        mixer_label = QLabel("MIXER MODULES")
        mixer_label.setObjectName("SectionHeader")
        layout.addWidget(mixer_label)
        
        # We store the created buttons on `self` to access them later.
        self.btn_mixer_machine = self._create_menu_button("Mixer Machines", "fa5s.cogs")
        layout.addWidget(self.btn_mixer_machine)
        
        self.btn_mixer_form = self._create_menu_button("Mixer Form", "fa5s.file-signature")
        layout.addWidget(self.btn_mixer_form)

        self.btn_mixer_old_record = self._create_menu_button("Mixer Old Records", "fa5s.file-signature")
        layout.addWidget(self.btn_mixer_old_record)

        # self.btn_mixer_report = self._create_menu_button("Mixer Report", "fa5s.chart-bar")
        # layout.addWidget(self.btn_mixer_report)
        #
        # extruder_label = QLabel("EXTRUDER MODULES")
        # extruder_label.setObjectName("SectionHeader")
        # layout.addWidget(extruder_label)
        #

        self.btn_extruder_config = self._create_menu_button("Extruder Configs", "fa5s.file-alt")
        layout.addWidget(self.btn_extruder_config )


        self.btn_extruder_form = self._create_menu_button("Extruder Form", "fa5s.file-alt")
        layout.addWidget(self.btn_extruder_form)

        self.btn_extruder_report = self._create_menu_button("Extruder Report", "fa5s.chart-pie")
        layout.addWidget(self.btn_extruder_report)

        layout.addStretch()

        btn_logout = self._create_menu_button("Logout", "fa5s.sign-out-alt")
        btn_logout.clicked.connect(self.dashboard.close_dashboard_main_window)
        layout.addWidget(btn_logout)

        return side_menu

    def _create_menu_button(self, text: str, icon_name: str) -> QPushButton:
        """A helper factory to create consistent menu buttons."""
        button = QPushButton(f"  {text}")
        button.setIcon(qta.icon(icon_name, color="#ecf0f1"))
        button.setIconSize(QSize(18, 18))
        button.setToolTip(text)
        return button

    def connect_buttons(self):
        """
        Connects the navigation buttons' signals. This method is called from `base.py`
        AFTER the main stacked_widget is guaranteed to exist, preventing the startup crash.
        """
        if not self.dashboard:
            return

        self.btn_mixer_machine.clicked.connect(lambda: self.dashboard.stacked_widget.setCurrentIndex(0))
        self.btn_mixer_form.clicked.connect(lambda: self.dashboard.stacked_widget.setCurrentIndex(1))
        self.btn_mixer_old_record.clicked.connect(lambda: self.dashboard.stacked_widget.setCurrentIndex(2))

        # self.btn_mixer_report.clicked.connect(lambda: self.dashboard.stacked_widget.setCurrentIndex(3))
        self.btn_extruder_config.clicked.connect(lambda: self.dashboard.stacked_widget.setCurrentIndex(3))
        self.btn_extruder_form.clicked.connect(lambda: self.dashboard.stacked_widget.setCurrentIndex(4))
        self.btn_extruder_report.clicked.connect(lambda: self.dashboard.stacked_widget.setCurrentIndex(5))