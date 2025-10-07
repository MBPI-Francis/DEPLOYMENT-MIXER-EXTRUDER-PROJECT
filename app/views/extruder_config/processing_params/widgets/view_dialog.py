# app/views/extruder_config/processing_params/view_dialog.py

import traceback
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QComboBox, QMessageBox, QTableWidgetItem
from sqlalchemy.orm import Session

from .resin_params_table import ResinParamsTable
from .temp_table import TempTable
from .. import ops


class ViewProcessingParamsDialog(QDialog):
    """
    A dedicated, read-only dialog for viewing an existing parameter set.
    """

    def __init__(self, session: Session, machine_id: int, parent=None):
        super().__init__(parent)
        self.session = session
        self.machine_id = machine_id

        self.setWindowTitle("View Processing Parameter Set")
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
        self.machine_name_combo.setObjectName("machineNameInput")

        self.resin_params_table = ResinParamsTable(session=self.session, resins=self.all_resins)
        self.temp_table = TempTable(self.all_zones)

        button_layout = QHBoxLayout()
        self.edit_button = QPushButton("Edit")
        self.close_button = QPushButton("Close")
        self.edit_button.setObjectName("PrimaryButton")
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        button_layout.addWidget(self.edit_button)

        main_layout.addWidget(self.machine_name_combo)
        main_layout.addWidget(self.resin_params_table, stretch=1)
        main_layout.addWidget(self.temp_table, stretch=2)
        main_layout.addLayout(button_layout)

        self.edit_button.clicked.connect(self.accept)
        self.close_button.clicked.connect(self.reject)

        QTimer.singleShot(0, self.populate_and_lock_form)

    def populate_and_lock_form(self):
        """
        Safely populates the form and then makes all widgets read-only.
        """
        try:
            details = ops.get_processing_set_details(self.session, self.machine_id)
            if not details:
                QMessageBox.critical(self, "Error", "Could not load data for the selected machine.")
                self.reject()
                return

            # --- THIS IS THE FIX for the blank machine name ---
            machine_name = details.get('machine_name', '')
            # 1. Add the machine name as an item to the list.
            self.machine_name_combo.addItem(machine_name)
            # 2. Now set it as the current text.
            self.machine_name_combo.setCurrentText(machine_name)

            self.resin_params_table.blockSignals(True)
            self.temp_table.table.blockSignals(True)

            self.resin_params_table.clear_dynamic_columns()
            self.temp_table.clear_rows()

            resin_data_list = details.get('resin_params_data', [])
            num_dynamic_columns = len(resin_data_list)
            self.temp_table.on_column_count_changed(num_dynamic_columns)

            for col_idx, resin_data in enumerate(resin_data_list):
                self.resin_params_table.add_column()
                table_col = col_idx + 1
                resin_id = resin_data.get('resin_id')
                motor_rpm = str(resin_data.get('motor_rpm', ''))
                feed_rate = str(resin_data.get('feed_rate', ''))
                resin_abbr = next((abbr for rid, abbr in self.all_resins if rid == resin_id), "")
                resin_item = QTableWidgetItem(resin_abbr)
                self.resin_params_table.table.setItem(0, table_col, resin_item)
                self.resin_params_table.table.setItem(1, table_col, QTableWidgetItem(motor_rpm))
                self.resin_params_table.table.setItem(2, table_col, QTableWidgetItem(feed_rate))
                self.resin_params_table.table.horizontalHeaderItem(table_col).setText(resin_abbr)

            all_zone_ids = sorted(list({zid for r in resin_data_list for zid in r.get('temps', {})}))
            zone_id_to_row_map = {}
            for row_idx, zone_id in enumerate(all_zone_ids):
                self.temp_table.add_row()
                zone_name = next((name for zid, name in self.all_zones if zid == zone_id), "")
                zone_item = QTableWidgetItem(zone_name)
                self.temp_table.table.setItem(row_idx, 0, zone_item)
                zone_id_to_row_map[zone_id] = row_idx

            for col_idx, resin_data in enumerate(resin_data_list):
                table_col = col_idx + 1
                for zone_id, temp_value in resin_data.get('temps', {}).items():
                    if zone_id in zone_id_to_row_map:
                        row_idx = zone_id_to_row_map[zone_id]
                        self.temp_table.table.setItem(row_idx, table_col, QTableWidgetItem(str(temp_value)))

            self.machine_name_combo.setEnabled(False)
            self.resin_params_table.set_read_only(True)
            self.temp_table.set_read_only(True)

        except Exception as e:
            error_message = f"An unexpected error occurred while loading the view dialog:\n\n{str(e)}"
            tb_str = traceback.format_exc()
            print(tb_str)
            QMessageBox.critical(self, "Loading Error", error_message)
            self.reject()

        finally:
            self.resin_params_table.table.blockSignals(False)
            self.temp_table.table.blockSignals(False)