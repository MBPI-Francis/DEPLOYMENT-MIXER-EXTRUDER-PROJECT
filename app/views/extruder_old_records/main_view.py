# app/views/mixer_form/main_view.py

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QTabWidget, QScrollArea
from sqlalchemy.orm import sessionmaker
from typing import Type
from ..extruder_old_records.excel_records.main import ExtruderExcelRecords
from ..extruder_old_records.amiel_program_records.main import ExtruderOldProgramRecords


# Import the two child widgets we will place in the tabs



def load_stylesheet(widget):
    """Loads the stylesheet for this module."""
    current_dir = os.path.dirname(os.path.realpath(__file__))
    css_path = os.path.join(current_dir, "styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            widget.setStyleSheet(f.read())


class ExtruderOldRecordsView(QWidget):
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
        self.extruder_amiel_rec = ExtruderOldProgramRecords(session_factory=self.Session)
        self.extruder_excel_rec = ExtruderExcelRecords(session_factory=self.Session)

        # 2. Create a QScrollArea specifically for the Entry Form.
        old_program_scroll_area = QScrollArea()
        old_program_scroll_area.setWidgetResizable(True)
        old_program_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Style the scroll area and its content to have a seamless white background.
        old_program_scroll_area.setObjectName("scroll_area")
        self.extruder_amiel_rec.setObjectName("scroll_content_widget")

        # Place the entry form *inside* the scroll area.
        old_program_scroll_area.setWidget(self.extruder_amiel_rec)

        excel_record_scroll_area = QScrollArea()
        excel_record_scroll_area.setWidgetResizable(True)
        excel_record_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # Style the scroll area and its content to have a seamless white background.
        excel_record_scroll_area.setObjectName("scroll_area")
        self.extruder_excel_rec.setObjectName("scroll_content_widget")

        # Place the entry form *inside* the scroll area.
        excel_record_scroll_area.setWidget(self.extruder_excel_rec)


        # 3. Add the widgets to the tabs.
        #    - The records view is added DIRECTLY.
        #    - The scroll area (containing the entry form) is added for the second tab.
        self.tab_widget.addTab(old_program_scroll_area, "Extruder Old Program Records")
        self.tab_widget.addTab(excel_record_scroll_area, "Extruder Old Excel Records")