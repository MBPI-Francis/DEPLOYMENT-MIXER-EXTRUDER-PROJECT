
# app/views/extruder_config/resin_params/main.py

import os
from typing import Type
from PyQt6.QtWidgets import QWidget, QVBoxLayout
from sqlalchemy.orm import sessionmaker

from . import ops
from .widgets import ResinParamsManagementPanel
from .handlers import ResinParamsPanelHandlers, COLUMN_CONFIG
from ....validators.ExtruderSettingsValidator import ResinParamsValidator


def load_stylesheet(widget):
    current_dir = os.path.dirname(os.path.realpath(__file__))
    css_path = os.path.join(current_dir, "styles.css")
    try:
        with open(css_path, "r") as f:
            widget.setStyleSheet(f.read())
    except FileNotFoundError:
        print(f"Warning: Stylesheet not found at {css_path}")


class ResinParamsView(QWidget, ResinParamsPanelHandlers):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.setObjectName("ResinParamsModule")
        self.Session = session_factory

        # Pass the column config directly to the widget
        self.panel = ResinParamsManagementPanel(
            title="Resin Parameters",
            column_config=COLUMN_CONFIG,  # <-- PASS CONFIG
            parent=self
        )

        self.table = self.panel.table
        self.add_button = self.panel.add_button
        self.restore_button = self.panel.restore_button  # <-- GET RESTORE BTN
        self.search_bar = self.panel.search_bar

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.panel)

        params_config = {
            'get_all_func': ops.get_all_resin_params_with_details,
            'create_func': ops.create_resin_param,
            'update_func': ops.update_resin_param,
            'delete_many_func': ops.soft_delete_resin_params,
            'check_exists_func': ops.check_resin_param_exists,
            'validator': ResinParamsValidator,
            'name_singular': "Resin",
            'name_plural': "Resins",
            'get_deleted_func': ops.get_deleted_resin_params,  # <-- ADDED
            'restore_func': ops.restore_resin_params,  # <-- ADDED
        }
        self.setup_handlers(params_config)
        load_stylesheet(self)