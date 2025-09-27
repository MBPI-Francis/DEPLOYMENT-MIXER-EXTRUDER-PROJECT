# app/views/extruder_settings/records/main.py

import os
from typing import Type
from PyQt6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout
from sqlalchemy.orm import sessionmaker

from . import ops
# Import the specific widgets and handlers
from .widgets import ResinManagementPanel, ZoneManagementPanel
from .handlers import ResinPanelHandlers, ZonePanelHandlers
from ....validators.ExtruderSettingsValidator import ResinValidator, ZoneValidator

def load_stylesheet(widget):
    current_dir = os.path.dirname(os.path.realpath(__file__))
    css_path = os.path.join(current_dir, "styles.css")
    try:
        with open(css_path, "r") as f:
            widget.setStyleSheet(f.read())
    except FileNotFoundError:
        print(f"Warning: Stylesheet not found at {css_path}")

# --- NEW: Use specific classes for each panel ---
class ResinPanel(ResinManagementPanel, ResinPanelHandlers):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(title="Resins", parent=parent)
        self.Session = session_factory
        resin_config = {
            'get_all_func': ops.get_all_resins_with_creator,
            'get_deleted_func': ops.get_deleted_resins,
            'create_func': ops.create_resin,
            'update_func': ops.update_resin,
            'restore_func': ops.restore_resins,
            'check_exists_func': ops.check_resin_name_exists,
            'validator': ResinValidator,
            'name_singular': "Resin",
            'name_plural': "Resins",
            'delete_many_func': ops.soft_delete_resins,
            'check_abbreviation_exists_func': ops.check_resin_abbreviation_exists,
        }
        self.setup_handlers(resin_config)

class ZonePanel(ZoneManagementPanel, ZonePanelHandlers):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(title="Zones", parent=parent)
        self.Session = session_factory
        zone_config = {
            'get_all_func': ops.get_all_zones_with_creator,
            'get_deleted_func': ops.get_deleted_zones,
            'create_func': ops.create_zone,
            'update_func': ops.update_zone,
            'restore_func': ops.restore_zones,
            'check_exists_func': ops.check_zone_name_exists,
            'validator': ZoneValidator,
            'name_singular': "Zone",
            'name_plural': "Zones",
            'delete_many_func': ops.soft_delete_zones,
            # NOTE: No abbreviation check function is passed in, as it's not needed.
        }
        self.setup_handlers(zone_config)

# --- The Main View remains the same ---
class ExtruderSettingsView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.setObjectName("ExtruderSettingsModule")
        main_layout = QVBoxLayout(self)
        top_panels_layout = QHBoxLayout()
        self.zone_panel = ZonePanel(session_factory, self)
        self.resin_panel = ResinPanel(session_factory, self)
        top_panels_layout.addWidget(self.zone_panel)
        top_panels_layout.addWidget(self.resin_panel)
        main_layout.addLayout(top_panels_layout)
        load_stylesheet(self)