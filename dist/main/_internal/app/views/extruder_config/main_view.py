# app/views/mixer_form/main_view.py

import os
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget
from sqlalchemy.orm import sessionmaker
from typing import Type
from . import ExtruderMachineView, ExtruderSettingsView, ExtruderProcessingParamsView
from .resin_params.main import ResinParamsView


# Import the two child widgets we will place in the tabs



def load_stylesheet(widget):
    """Loads the stylesheet for this module."""
    current_dir = os.path.dirname(os.path.realpath(__file__))
    css_path = os.path.join(current_dir, "styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            widget.setStyleSheet(f.read())


class ExtruderConfigView(QWidget):
    """
    The main container widget for the Mixer section. It uses a QTabWidget
    to manage the Entry Form and the Records view.
    """
    STYLESHEET = """
        QTabWidget::pane {
            background: white;
            border-radius: 8px;
        }
        QTabBar::tab {
            background: transparent;
            min-width: 120px;
            padding: 8px;
            font-weight: bold;
            color: #555;
            font-size: 16px;
        }
        QTabBar::tab:selected {
            color: #2c3e50;
            border-bottom: 2px solid #2c3e50; 
        }
        QTabBar::tab:!selected:hover {
            color: #2c3e50;
            border-bottom: 2px solid #2c3e50; 
        }
    """

    def __init__(self, session_factory: Type[sessionmaker], parent=None):

        super().__init__(parent)
        self.Session = session_factory

        self.setStyleSheet(self.STYLESHEET)

        # --- Main Layout ---
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- Tab Widget Setup ---
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # --- Instantiate Child Widgets ---


        # Create an instance for the tabs
        self.extruder_machine_tab = ExtruderMachineView(session_factory=self.Session)
        self.extruder_resin_tab = ExtruderSettingsView(session_factory=self.Session)
        self.resin_params_tab = ResinParamsView(session_factory=self.Session)
        self.processing_params_tab = ExtruderProcessingParamsView(session_factory=self.Session)





        # --- Add Widgets as Tabs ---
        # As requested, you can easily comment out this line to hide the records tab
        self.tab_widget.addTab(self.extruder_machine_tab, "Extruder Machines")
        self.tab_widget.addTab(self.extruder_resin_tab, "Zones/Resins List")
        self.tab_widget.addTab(self.resin_params_tab, "Resin Settings")
        self.tab_widget.addTab(self.processing_params_tab, "Machine Settings")





        # Load the local stylesheet if it exists
        load_stylesheet(self)