# # app/views/extruder_config/processing_params/widgets/create_dialog.py
#
# from PyQt6.QtCore import Qt
# from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox
# from sqlalchemy.orm import Session
# from typing import Dict, Any
#
# from .resin_params_table import ResinParamsTable
# from .temp_table import TempTable
# from .. import ops
#
#
# class CreateProcessingParamsDialog(QDialog):
#     def __init__(self, session: Session, parent=None):
#         super().__init__(parent)
#         self.setWindowTitle("Create New Processing Parameter Set")
#         self.setWindowFlags(
#             self.windowFlags() | Qt.WindowType.Dialog | Qt.WindowType.WindowMinimizeButtonHint |
#             Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint
#         )
#         self.resize(1000, 800)
#         self.setModal(True)
#
#         all_resins = [(r.id, r.abbreviation) for r in ops.get_all_resins_for_dropdown(session)]
#         all_zones = [(z.id, z.name) for z in ops.get_all_zones_for_dropdown(session)]
#         all_machines = ops.get_all_machine_names(session)
#
#         main_layout = QVBoxLayout(self)
#
#         self.machine_name_combo = QComboBox()
#         self.machine_name_combo.setEditable(True)
#         self.machine_name_combo.addItems(all_machines)
#         self.machine_name_combo.lineEdit().setPlaceholderText("Select or Create a Machine Name...")
#         self.machine_name_combo.setObjectName("machineNameInput")
#
#         self.resin_params_table = ResinParamsTable(session=session, resins=all_resins)
#         self.temp_table = TempTable(all_zones)
#
#         # --- NEW: Explicitly add the first column and row for a new record ---
#         self.resin_params_table.add_column()
#         self.temp_table.add_row()
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
#         main_layout.addWidget(self.resin_params_table, stretch=1)
#         main_layout.addWidget(self.temp_table, stretch=2)
#         main_layout.addLayout(button_layout)
#
#         self.resin_params_table.column_count_changed.connect(self.temp_table.on_column_count_changed)
#
#         self.cancel_button.clicked.connect(self.reject)
#         self.save_button.clicked.connect(self.accept)
#
#     def get_data(self) -> Dict[str, Any]:
#         machine_name = self.machine_name_combo.currentText().strip()
#         if not machine_name:
#             raise ValueError("Machine Name cannot be empty.")
#         return {
#             "machine_name": machine_name,
#             "resin_params": self.resin_params_table.get_data(),
#             "temperatures": self.temp_table.get_data()
#         }
import os

# app/views/extruder_config/processing_params/widgets/create_dialog.py

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QLabel
from sqlalchemy.orm import Session
from typing import Dict, Any

from .resin_params_table import ResinParamsTable
from .temp_table import TempTable
from .. import ops


class CreateProcessingParamsDialog(QDialog):
    def __init__(self, session: Session, parent=None):
        super().__init__(parent)

        style_path = os.path.join(os.path.dirname(__file__), '..', 'styles.css')
        with open(style_path, 'r') as f:
            self.setStyleSheet(f.read())

        self.setWindowTitle("Create New Machine Settings")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.Dialog | Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(1000, 800)
        self.setModal(True)

        all_resins = [(r.id, r.abbreviation) for r in ops.get_all_resins_for_dropdown(session)]
        all_zones = [(z.id, z.name) for z in ops.get_all_zones_for_dropdown(session)]
        all_machines = ops.get_all_machine_names(session)

        main_layout = QVBoxLayout(self)

        self.machine_name_combo = QComboBox()
        self.machine_name_combo.setEditable(True)
        self.machine_name_combo.addItems(all_machines)
        self.machine_name_combo.lineEdit().setPlaceholderText("Select or Create a Machine Name...")
        self.machine_name_combo.setObjectName("MachineComboBox")
        self.machine_name_combo.setFixedWidth(300)

        # --- THIS IS THE NEW WIDGET ---
        # 1. Create the descriptive QLabel with HTML for bolding.
        description_text = (
            "Create a new standard setting for this machine. Add one or more "
            "<b>Resin Settings</b> (with their RPM and Feed Rate) and the corresponding "
            "<b>Zone Temperatures</b> below."
        )
        description_label = QLabel(description_text)

        # 2. Set its objectName to apply the new style from the CSS file.
        description_label.setObjectName("DescriptionLabel")
        description_label.setWordWrap(True)  # Ensure the text wraps if the dialog is narrow


        self.resin_params_table = ResinParamsTable(session=session, resins=all_resins, machine_combobox=self.machine_name_combo)
        self.temp_table = TempTable(all_zones)

        # Add a default row to the temperature table
        self.temp_table.add_row()

        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save Machine Settings")
        self.cancel_button = QPushButton("Cancel")
        self.save_button.setObjectName("PrimaryButton")
        self.cancel_button.setObjectName("SecondaryButton")
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        # main_layout.addWidget(self.machine_name_combo)

        main_layout.addWidget(self.resin_params_table, stretch=1)
        main_layout.addWidget(self.temp_table, stretch=2)
        main_layout.addWidget(description_label) # Add the new label here
        main_layout.addLayout(button_layout)

        # First, connect the signal for any *future* changes (like clicking the "Add Column" button)
        self.resin_params_table.column_count_changed.connect(self.temp_table.on_column_count_changed)

        # --- THE CRITICAL FIX ---
        # Now, manually get the initial column count from Table 1 and force Table 2 to sync to it.
        # This ensures they are identical when the dialog first appears.
        initial_dynamic_cols = self.resin_params_table.table.columnCount() - 1
        self.temp_table.on_column_count_changed(initial_dynamic_cols)

        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.accept)

    def get_data(self) -> Dict[str, Any]:
        machine_name = self.machine_name_combo.currentText().strip()
        if not machine_name:
            raise ValueError("Machine Name cannot be empty.")
        return {
            "machine_name": machine_name,
            "resin_params": self.resin_params_table.get_data(),
            "temperatures": self.temp_table.get_data()
        }