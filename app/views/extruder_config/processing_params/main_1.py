# app/views/extruder_config/processing_params/main.py

import os
from typing import Type

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem, QHeaderView
from sqlalchemy.orm import sessionmaker

from .handlers import ProcessingParamsHandlers


class ExtruderProcessingParamsView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.setObjectName("ProcessingParamsModule")

        main_layout = QVBoxLayout(self)

        # --- Top Bar ---
        top_bar_layout = QHBoxLayout()
        top_bar_layout.addStretch()
        self.create_button = QPushButton("＋ Create New Parameter Set")
        self.create_button.setObjectName("PrimaryButton")
        top_bar_layout.addWidget(self.create_button)

        # --- Main Table ---
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Machine Name", "Created By"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)  # Recommended

        # --- NEW: Enable context menu ---
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        main_layout.addLayout(top_bar_layout)
        main_layout.addWidget(self.table)

        # --- Setup Handler ---
        self.handler = ProcessingParamsHandlers(parent_view=self)
        self.handler.Session = session_factory
        self.handler.setup_handlers(config={})

    # --- UPDATED: To accept and store data (like an ID) ---
    def create_item(self, text, data=None):
        """Helper to create a non-editable table item with optional associated data."""
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        if data is not None:
            item.setData(Qt.ItemDataRole.UserRole, data)
        return item