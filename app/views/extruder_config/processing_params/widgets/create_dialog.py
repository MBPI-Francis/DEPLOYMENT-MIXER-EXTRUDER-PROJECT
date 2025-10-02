# app/views/extruder_config/processing_params/widgets/create_dialog.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QMessageBox
from sqlalchemy.orm import Session
from typing import Dict, Any

from .resin_params_table import ResinParamsTable
from .temp_table import TempTable
from .. import ops


# class CreateProcessingParamsDialog(QDialog):
#     def __init__(self, session: Session, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("Create New Processing Parameter Set")
#
#         # --- THE KEY CHANGES FOR RESIZABILITY ---
#         # 1. Set window flags to include Minimize and Maximize buttons.
#         #    The Dialog flag is necessary to make it a pop-up window.
#         self.setWindowFlags(
#             self.windowFlags() |
#             Qt.WindowType.Dialog |
#             Qt.WindowType.WindowMinimizeButtonHint |
#             Qt.WindowType.WindowMaximizeButtonHint |
#             Qt.WindowType.WindowCloseButtonHint
#         )
#
#         # 2. Set a reasonable default starting size.
#         self.resize(1000, 800)  # Use resize() instead of setMinimumSize()
#
#         self.setModal(True)
#
#         # --- The rest of the code is unchanged ---
#         all_resins = [(r.id, r.abbreviation) for r in ops.get_all_resins_for_dropdown(session)]
#         all_zones = [(z.id, z.name) for z in ops.get_all_zones_for_dropdown(session)]
#
#         main_layout = QVBoxLayout(self)
#
#         self.machine_name_combo = QComboBox()
#         self.machine_name_combo.setEditable(True)
#         self.machine_name_combo.addItems(ops.get_all_machine_names(session))
#         self.machine_name_combo.lineEdit().setPlaceholderText("Select or Create a Machine Name...")
#         self.machine_name_combo.setObjectName("machineNameInput")
#
#         self.resin_params_table = ResinParamsTable(all_resins)
#         self.temp_table = TempTable(all_zones)
#
#         button_layout = QHBoxLayout()
#         self.save_button = QPushButton("Save Parameter Set")
#         self.cancel_button = QPushButton("Cancel")
#         self.save_button.setObjectName("PrimaryButton")
#         button_layout.addStretch()
#         button_layout.addWidget(self.cancel_button)
#         button_layout.addWidget(self.save_button)
#
#         main_layout.addWidget(self.machine_name_combo)
#         # The 'stretch' factors are what make the tables resize correctly
#         main_layout.addWidget(self.resin_params_table, stretch=1)
#         main_layout.addWidget(self.temp_table, stretch=2)
#         main_layout.addLayout(button_layout)
#
#         self.resin_params_table.column_count_changed.connect(self.temp_table.on_column_count_changed)
#
#         initial_dynamic_cols = self.resin_params_table.table.columnCount() - 1
#         self.temp_table.on_column_count_changed(initial_dynamic_cols)
#
#         self.cancel_button.clicked.connect(self.reject)
#         self.save_button.clicked.connect(self.accept)



class CreateProcessingParamsDialog(QDialog):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Processing Parameter Set")
        self.setWindowFlags(
            self.windowFlags() |
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
                )
        self.resize(1000, 800)
        self.setModal(True)

        # Use the single, provided session for all initial data fetching.
        all_resins = [(r.id, r.abbreviation) for r in ops.get_all_resins_for_dropdown(session)]
        all_zones = [(z.id, z.name) for z in ops.get_all_zones_for_dropdown(session)]
        all_machines = ops.get_all_machine_names(session)

        main_layout = QVBoxLayout(self)

        self.machine_name_combo = QComboBox()
        self.machine_name_combo.setEditable(True)
        self.machine_name_combo.addItems(all_machines)
        self.machine_name_combo.lineEdit().setPlaceholderText("Select or Create a Machine Name...")
        self.machine_name_combo.setObjectName("machineNameInput")

        # --- THE STABLE FIX ---
        # Pass the single, active 'session' object to the child table.
        self.resin_params_table = ResinParamsTable(session=session, resins=all_resins)
        self.temp_table = TempTable(all_zones)

        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save Parameter Set")
        self.cancel_button = QPushButton("Cancel")
        self.save_button.setObjectName("PrimaryButton")
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        main_layout.addWidget(self.machine_name_combo)
        main_layout.addWidget(self.resin_params_table, stretch=1)
        main_layout.addWidget(self.temp_table, stretch=2)
        main_layout.addLayout(button_layout)

        self.resin_params_table.column_count_changed.connect(self.temp_table.on_column_count_changed)
        initial_dynamic_cols = self.resin_params_table.table.columnCount() - 1
        self.temp_table.on_column_count_changed(initial_dynamic_cols)


        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.accept)


    def get_data(self) -> Dict[str, Any]:
        machine_name = self.machine_name_combo.currentText().strip()
        if not machine_name:
            raise ValueError("Machine Name cannot be empty.")

        # ... (rest of get_data is unchanged) ...
        return {
            "machine_name": machine_name,
            "resin_params": self.resin_params_table.get_data(),
            "temperatures": self.temp_table.get_data()
        }