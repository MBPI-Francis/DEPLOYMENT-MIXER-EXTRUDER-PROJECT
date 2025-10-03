# app/views/extruder_config/processing_params/widgets/dialogs.py

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QMessageBox, QTableWidgetItem
from sqlalchemy.orm import Session
from typing import Dict, Any

from .resin_params_table import ResinParamsTable
from .temp_table import TempTable
from .. import ops


class BaseProcessingDialog(QDialog):
    """
    A base class containing shared UI and logic for the Create and Edit dialogs.
    """

    def __init__(self, session: Session, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.Dialog | Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(1000, 800)
        self.setModal(True)

        self.all_resins = [(r.id, r.abbreviation) for r in ops.get_all_resins_for_dropdown(session)]
        self.all_zones = [(z.id, z.name) for z in ops.get_all_zones_for_dropdown(session)]

        main_layout = QVBoxLayout(self)
        self.machine_name_combo = QComboBox()
        self.machine_name_combo.setEditable(True)
        self.machine_name_combo.lineEdit().setPlaceholderText("Select or Create a Machine Name...")
        self.machine_name_combo.setObjectName("machineNameInput")

        self.resin_params_table = ResinParamsTable(session=self.session, resins=self.all_resins)
        self.temp_table = TempTable(self.all_zones)

        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Save")
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
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.accept)

    def get_data(self) -> Dict[str, Any]:
        """Validates and extracts data from all form widgets."""
        machine_name = self.machine_name_combo.currentText().strip()
        if not machine_name:
            raise ValueError("Machine Name cannot be empty.")
        return {
            "machine_name": machine_name,
            "resin_params": self.resin_params_table.get_data(),
            "temperatures": self.temp_table.get_data()
        }


class CreateProcessingParamsDialog(BaseProcessingDialog):
    """Dialog for creating a new parameter set."""

    def __init__(self, session: Session, parent=None):
        super().__init__(session, parent)
        self.setWindowTitle("Create New Processing Parameter Set")
        self.save_button.setText("Save Parameter Set")

        all_machines = ops.get_all_machine_names(session)
        self.machine_name_combo.addItems(all_machines)

        initial_cols = self.resin_params_table.table.columnCount() - 1
        self.temp_table.on_column_count_changed(initial_cols)


class EditProcessingParamsDialog(BaseProcessingDialog):
    """Dialog for editing an existing parameter set."""

    def __init__(self, session: Session, machine_id: int, parent=None):
        super().__init__(session, parent)
        self.setWindowTitle("Edit Processing Parameter Set")
        self.save_button.setText("Update Parameter Set")
        self.machine_id = machine_id

        self.populate_form()

    def populate_form(self):
        """Fetches existing data and fills the form widgets."""
        details = ops.get_processing_set_details(self.session, self.machine_id)
        if not details:
            QMessageBox.critical(self, "Error", "Could not load data for the selected machine.")
            QTimer.singleShot(0, self.reject)
            return

        self.machine_name_combo.setCurrentText(details['machine_name'])

        # Clear default columns before populating
        while self.resin_params_table.table.columnCount() > 1:
            self.resin_params_table.remove_column()

        resin_data_list = details['resin_params_data']

        # Populate Resin Params table (Columns)
        for col_idx, resin_data in enumerate(resin_data_list):
            if col_idx > 0: self.resin_params_table.add_column()

            table_col = col_idx + 1
            resin_item = QTableWidgetItem()
            self.resin_params_table.table.setItem(0, table_col, resin_item)

            resin_abbr = next((abbr for id, abbr in self.all_resins if id == resin_data['resin_id']), "")
            resin_item.setData(Qt.ItemDataRole.UserRole, resin_data['resin_id'])
            resin_item.setText(resin_abbr)  # Triggers on_item_changed to populate dropdowns

            # Set RPM and Feed Rate *after* setting the resin
            self.resin_params_table.table.setItem(1, table_col, QTableWidgetItem(str(resin_data['motor_rpm'])))
            self.resin_params_table.table.setItem(2, table_col, QTableWidgetItem(str(resin_data['feed_rate'])))

        # Populate Temp table (Rows)
        all_zone_ids = {zid for r in resin_data_list for zid in r['temps']}
        zone_id_to_row_map = {}
        for row_idx, zone_id in enumerate(sorted(list(all_zone_ids))):
            self.temp_table.add_row()
            zone_item = QTableWidgetItem()
            self.temp_table.table.setItem(row_idx, 0, zone_item)
            zone_name = next((name for id, name in self.all_zones if id == zone_id), "")
            zone_item.setData(Qt.ItemDataRole.UserRole, zone_id)
            zone_item.setText(zone_name)
            zone_id_to_row_map[zone_id] = row_idx

        # Fill in the temperature values
        for col_idx, resin_data in enumerate(resin_data_list):
            table_col = col_idx + 1
            for zone_id, temp_value in resin_data['temps'].items():
                if zone_id in zone_id_to_row_map:
                    row_idx = zone_id_to_row_map[zone_id]
                    self.temp_table.table.setItem(row_idx, table_col, QTableWidgetItem(str(temp_value)))