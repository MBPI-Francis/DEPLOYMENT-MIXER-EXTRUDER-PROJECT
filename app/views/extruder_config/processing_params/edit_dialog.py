# app/views/extruder_config/processing_params/edit_dialog.py

import traceback
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QMessageBox, QTableWidgetItem
from sqlalchemy.orm import Session
from typing import Dict, Any

from .widgets.resin_params_table import ResinParamsTable
from .widgets.temp_table import TempTable
from . import ops


class EditProcessingParamsDialog(QDialog):
    def __init__(self, session: Session, machine_id: int, parent=None):
        super().__init__(parent)
        self.session = session
        self.machine_id = machine_id

        self.setWindowTitle("Edit Processing Parameter Set")
        self.setWindowFlags(
            self.windowFlags() | Qt.WindowType.Dialog | Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(1000, 800)
        self.setModal(True)

        # --- Initial Data Fetch ---
        self.all_resins = [(r.id, r.abbreviation) for r in ops.get_all_resins_for_dropdown(session)]
        self.all_zones = [(z.id, z.name) for z in ops.get_all_zones_for_dropdown(session)]

        # --- UI Setup ---
        main_layout = QVBoxLayout(self)
        self.machine_name_combo = QComboBox()
        self.machine_name_combo.setEditable(True)
        self.machine_name_combo.setObjectName("machineNameInput")

        all_machines = ops.get_all_machine_names(session)
        self.machine_name_combo.addItems(all_machines)

        self.resin_params_table = ResinParamsTable(session=self.session, resins=self.all_resins)
        self.temp_table = TempTable(self.all_zones)

        button_layout = QHBoxLayout()
        self.save_button = QPushButton("Update Parameter Set")
        self.cancel_button = QPushButton("Cancel")
        self.save_button.setObjectName("PrimaryButton")
        button_layout.addStretch()
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.save_button)

        main_layout.addWidget(self.machine_name_combo)
        main_layout.addWidget(self.resin_params_table, stretch=1)
        main_layout.addWidget(self.temp_table, stretch=2)
        main_layout.addLayout(button_layout)

        # --- Connections ---
        self.resin_params_table.column_count_changed.connect(self.temp_table.on_column_count_changed)
        self.cancel_button.clicked.connect(self.reject)
        self.save_button.clicked.connect(self.accept)

        # Use QTimer to ensure this runs after the event loop has started
        QTimer.singleShot(0, self.populate_form)

    def populate_form(self):
        """
        Safely fetches and populates the form, with extensive error handling.
        """
        # --- NEW: Wrap the entire logic in a try-except block to prevent crashes ---
        try:
            details = ops.get_processing_set_details(self.session, self.machine_id)
            if not details:
                QMessageBox.critical(self, "Error", "Could not load data for the selected machine.")
                self.reject()  # Close the dialog if no data
                return

            self.machine_name_combo.setCurrentText(details.get('machine_name', ''))

            # Block signals to prevent re-entrancy issues
            self.resin_params_table.table.blockSignals(True)
            self.temp_table.table.blockSignals(True)

            # Clear existing content from the tables using new dedicated methods
            self.resin_params_table.clear_dynamic_columns()
            self.temp_table.clear_rows()

            resin_data_list = details.get('resin_params_data', [])

            # --- Populate Resin Parameters Table (Columns) ---
            for col_idx, resin_data in enumerate(resin_data_list):
                self.resin_params_table.add_column()

                table_col = col_idx + 1  # Dynamic columns start at index 1

                resin_id = resin_data.get('resin_id')
                motor_rpm = str(resin_data.get('motor_rpm', ''))
                feed_rate = str(resin_data.get('feed_rate', ''))

                delegate = self.resin_params_table.column_delegates.get(table_col)
                if delegate and resin_id:
                    params = ops.get_params_for_resin(self.session, resin_id)
                    delegate.set_items(rpms=params['rpms'], feed_rates=params['feed_rates'])

                resin_abbr = next((abbr for rid, abbr in self.all_resins if rid == resin_id), "")

                resin_item = QTableWidgetItem(resin_abbr)
                resin_item.setData(Qt.ItemDataRole.UserRole, resin_id)
                self.resin_params_table.table.setItem(0, table_col, resin_item)
                self.resin_params_table.table.setItem(1, table_col, QTableWidgetItem(motor_rpm))
                self.resin_params_table.table.setItem(2, table_col, QTableWidgetItem(feed_rate))
                self.resin_params_table.table.horizontalHeaderItem(table_col).setText(resin_abbr)

            # --- Populate Temperature Table (Rows and Data) ---
            all_zone_ids_in_data = sorted(list({zid for r in resin_data_list for zid in r.get('temps', {})}))
            zone_id_to_row_map = {}
            for row_idx, zone_id in enumerate(all_zone_ids_in_data):
                self.temp_table.add_row()
                zone_name = next((name for zid, name in self.all_zones if zid == zone_id), "")
                zone_item = QTableWidgetItem(zone_name)
                zone_item.setData(Qt.ItemDataRole.UserRole, zone_id)
                self.temp_table.table.setItem(row_idx, 0, zone_item)
                zone_id_to_row_map[zone_id] = row_idx

            for col_idx, resin_data in enumerate(resin_data_list):
                table_col = col_idx + 1
                for zone_id, temp_value in resin_data.get('temps', {}).items():
                    if zone_id in zone_id_to_row_map:
                        row_idx = zone_id_to_row_map[zone_id]
                        self.temp_table.table.setItem(row_idx, table_col, QTableWidgetItem(str(temp_value)))

        except Exception as e:
            # --- CRITICAL DEBUGGING STEP ---
            error_message = f"An unexpected error occurred while loading the edit dialog:\n\n{str(e)}"
            tb_str = traceback.format_exc()  # Get the full error traceback
            print(tb_str)  # Also print to console for more detail
            QMessageBox.critical(self, "Loading Error", error_message)
            self.reject()  # Close the dialog after showing the error

        finally:
            # Always unblock signals, no matter what happens
            self.resin_params_table.table.blockSignals(False)
            self.temp_table.table.blockSignals(False)

    def get_data(self) -> Dict[str, Any]:
        machine_name = self.machine_name_combo.currentText().strip()
        if not machine_name:
            raise ValueError("Machine Name cannot be empty.")
        return {
            "machine_name": machine_name,
            "resin_params": self.resin_params_table.get_data(),
            "temperatures": self.temp_table.get_data()
        }