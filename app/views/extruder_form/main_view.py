# app/views/mixer_form/main_view.py

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QScrollArea
from sqlalchemy.orm import sessionmaker
from typing import Type

from .for_completion.main import ForCompletionRecordsView
from ..extruder_form.entry_form.main import ExtruderEntryFormView
from ..extruder_form.records.main import ExtruderRecordsView


# Import the two child widgets we will place in the tabs



def load_stylesheet(widget):
    """Loads the stylesheet for this module."""
    current_dir = os.path.dirname(os.path.realpath(__file__))
    css_path = os.path.join(current_dir, "styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            widget.setStyleSheet(f.read())


class ExtruderFormView(QWidget):
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
        
        /* Add this to your style.css file */

        QScrollArea#scroll_area {
            border: none;
            background-color: transparent;
        }
        
        QWidget#scroll_content_widget {
            background-color: #ffffff;
        }
        
        /* === SCROLLBARS & MENUS (Unchanged) === */
        QScrollBar:vertical {
            border: none; background: #f1f3f5; width: 8px; margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #adb5bd; min-height: 20px; border-radius: 4px;
        }
        QScrollBar::handle:vertical:hover { background: #868e96; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            height: 0; background: none;
        }

    """

    # def __init__(self, session_factory: Type[sessionmaker], parent=None):
    #
    #     super().__init__(parent)
    #     self.Session = session_factory
    #
    #     self.setStyleSheet(self.STYLESHEET)
    #
    #     # --- Main Layout ---
    #     main_layout = QVBoxLayout(self)
    #     main_layout.setContentsMargins(0, 0, 0, 0)
    #
    #     # --- Tab Widget Setup ---
    #     self.tab_widget = QTabWidget()
    #     main_layout.addWidget(self.tab_widget)
    #
    #     # --- Instantiate Child Widgets ---
    #
    #
    #     # Create an instance for the tabs
    #     self.extruder_entry_form = ExtruderEntryFormView(session_factory=self.Session)
    #     self.extruder_records = ExtruderRecordsView(session_factory=self.Session)
    #
    #
    #     # --- Add Widgets as Tabs ---
    #     # As requested, you can easily comment out this line to hide the records tab
    #     self.tab_widget.addTab( self.extruder_records, "Extruder Records")
    #     self.tab_widget.addTab( self.extruder_entry_form, "Extruder Entry Form")
    #
    #
    #     # Load the local stylesheet if it exists
    #     load_stylesheet(self)

    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory

        self.setStyleSheet(self.STYLESHEET)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # --- THIS IS THE DEFINITIVE FIX ---

        # 1. Instantiate the two child widgets as before.
        self.extruder_entry_form = ExtruderEntryFormView(session_factory=self.Session)
        self.extruder_records = ExtruderRecordsView(session_factory=self.Session)
        self.for_completion_records = ForCompletionRecordsView(session_factory=self.Session)

        # 2. Create a QScrollArea specifically for the Entry Form.
        entry_form_scroll_area = QScrollArea()
        entry_form_scroll_area.setWidgetResizable(True)
        entry_form_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Style the scroll area and its content to have a seamless white background.
        entry_form_scroll_area.setObjectName("scroll_area")
        self.extruder_entry_form.setObjectName("scroll_content_widget")

        # Place the entry form *inside* the scroll area.
        entry_form_scroll_area.setWidget(self.extruder_entry_form)

        # 3. Add the widgets to the tabs.
        #    - The records view is added DIRECTLY.
        #    - The scroll area (containing the entry form) is added for the second tab.
        self.tab_widget.addTab(self.for_completion_records, "For Completion")
        self.tab_widget.addTab(entry_form_scroll_area, "Extruder Entry Form")
        self.tab_widget.addTab(self.extruder_records, "Extruder Records")

