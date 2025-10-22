# app/views/extruder_form/entry_form/ui_setup.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QGroupBox,
    QDateTimeEdit, QTableWidget, QHeaderView, QAbstractItemView,
    QTimeEdit, QDateEdit, QSpacerItem, QSizePolicy, QFrame
)
from PyQt6.QtCore import QDateTime, QDate


class Ui_ExtruderEntryForm:
    def setup_ui(self, parent_widget: QWidget):
        main_layout = QVBoxLayout(parent_widget)
        grid_layout = QGridLayout()
        main_layout.addLayout(grid_layout)

        order_group = self._create_order_info_group()
        grid_layout.addWidget(order_group, 0, 0)
        machine_group = self._create_machine_config_group()
        grid_layout.addWidget(machine_group, 0, 1)
        zones_group = self._create_zones_group()
        grid_layout.addWidget(zones_group, 0, 2)
        purging_resin_layout = QHBoxLayout()
        self.purging_group = self._create_purging_group()
        self.resin_group = self._create_resin_consumption_group()
        purging_resin_layout.addWidget(self.purging_group)
        purging_resin_layout.addWidget(self.resin_group)
        grid_layout.addLayout(purging_resin_layout, 1, 0, 1, 2)
        summary_group = self._create_summary_group()
        grid_layout.addWidget(summary_group, 1, 2)
        output_log_group = self._create_output_log_group()
        grid_layout.addWidget(output_log_group, 2, 0, 1, 3)
        remarks_personnel_group = self._create_remarks_personnel_group()
        grid_layout.addWidget(remarks_personnel_group, 3, 0, 1, 3)
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self.clear_button = QPushButton("Clear Form")
        self.save_button = QPushButton("Save Form")
        action_layout.addWidget(self.clear_button)
        action_layout.addWidget(self.save_button)
        main_layout.addLayout(action_layout)

    def _create_remarks_personnel_group(self):
        """
        Creates a single group box for Remarks (top) and Personnel (bottom).
        The operator selection is now two simple combo boxes.
        """
        group = QGroupBox("Remarks & Personnel")
        main_v_layout = QVBoxLayout(group)

        # Remarks
        main_v_layout.addWidget(QLabel("Remarks:"))
        self.remarks_input = QTextEdit()
        self.remarks_input.setFixedHeight(80)
        main_v_layout.addWidget(self.remarks_input)

        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_v_layout.addWidget(separator)

        # --- THE FIX: Simplified Personnel Section with correct widgets ---
        personnel_form_layout = QFormLayout()

        self.prepared_by_combo = QComboBox()
        self.operator_combo = QComboBox()  # This widget is now created
        self.position_combo = QComboBox()  # This widget is now created

        personnel_form_layout.addRow("Prepared By:", self.prepared_by_combo)
        personnel_form_layout.addRow("Operator:", self.operator_combo)
        personnel_form_layout.addRow("Position:", self.position_combo)

        main_v_layout.addLayout(personnel_form_layout)
        # The table and buttons are removed from the UI definition.

        return group

    # Other methods remain unchanged
    def _create_order_info_group(self):
        group = QGroupBox("Order Information")
        form_layout = QFormLayout(group)
        lot_layout = QHBoxLayout()
        self.lot_number_input = QLineEdit()
        self.lot_number_input.setReadOnly(True)
        self.lot_number_select_btn = QPushButton("Select...")
        lot_layout.addWidget(self.lot_number_input)
        lot_layout.addWidget(self.lot_number_select_btn)
        form_layout.addRow("Input Lot Number(s):", lot_layout)
        self.product_code_input = QLineEdit()
        self.product_code_input.setReadOnly(True)
        self.customer_input = QLineEdit()
        self.customer_input.setReadOnly(True)
        self.qty_order_input = QLineEdit("0.00")
        self.qty_produced_input = QLineEdit("0.00")
        self.target_output_hr_input = QLineEdit("0.00")
        form_layout.addRow("Production Code:", self.product_code_input)
        form_layout.addRow("Customer:", self.customer_input)
        form_layout.addRow("QTY. Order (kg):", self.qty_order_input)
        form_layout.addRow("Qty. Produced (kg):", self.qty_produced_input)
        form_layout.addRow("Target Output per Hour (Kg/Hr):", self.target_output_hr_input)
        return group

    def _create_machine_config_group(self):
        group = QGroupBox("Machine and Configuration Settings")
        layout = QFormLayout(group)
        self.shift_combo = QComboBox()
        self.mc_no_combo = QComboBox()
        self.feed_rate_input = QLineEdit("0.00")
        self.rpm_input = QLineEdit("0.00")
        self.screen_size_combo = QComboBox()
        self.screw_config_combo = QComboBox()
        layout.addRow("Shift:", self.shift_combo)
        layout.addRow("MC No.:", self.mc_no_combo)
        layout.addRow("Feed Rate:", self.feed_rate_input)
        layout.addRow("RPM:", self.rpm_input)
        layout.addRow("Screen Size:", self.screen_size_combo)
        layout.addRow("Screw Config.:", self.screw_config_combo)
        return group

    def _create_zones_group(self):
        group = QGroupBox("Extruder Zone Temperatures")
        layout = QGridLayout(group)
        self.zone_inputs = {}
        zones = [("Z12 (Die head)", 0, 0), ("Z11 (Die head)", 0, 1), ("Z10 (Die head)", 0, 2), ("Z9", 1, 0),
                 ("Z8", 1, 1), ("Z7 (Die head)", 1, 2), ("Z6", 2, 0), ("Z5", 2, 1), ("Z4", 2, 2), ("Z3", 3, 0),
                 ("Z2", 3, 1), ("Z1", 3, 2)]
        for label, row, col in zones:
            self.zone_inputs[label.split(' ')[0]] = QLineEdit("0")
            layout.addWidget(QLabel(label), row * 2, col)
            layout.addWidget(self.zone_inputs[label.split(' ')[0]], row * 2 + 1, col)
        return group

    def _create_purging_group(self):
        group = QGroupBox("Purging Details")
        layout = QFormLayout(group)
        self.purging_product_code_combo = QComboBox()
        self.purging_start_time = QTimeEdit()
        self.purging_end_time = QTimeEdit()
        self.purging_resin_combo = QComboBox()
        self.purging_palletizer_input = QLineEdit("0.00")
        self.purging_siever_input = QLineEdit("0.00")
        layout.addRow("Product Code:", self.purging_product_code_combo)
        layout.addRow("Start Time:", self.purging_start_time)
        layout.addRow("End Time:", self.purging_end_time)
        layout.addRow("Resin:", self.purging_resin_combo)
        layout.addRow("Pelletizer:", self.purging_palletizer_input)
        layout.addRow("Siever:", self.purging_siever_input)
        return group

    def _create_resin_consumption_group(self):
        group = QGroupBox("Resin Consumption")
        layout = QVBoxLayout(group)
        self.resin_table = QTableWidget(0, 2)
        self.resin_table.setHorizontalHeaderLabels(["Resin", "Qty (Kg.)"])
        self.resin_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.resin_table)
        resin_button_layout = QHBoxLayout()
        resin_button_layout.addStretch()
        self.add_resin_btn = QPushButton("Add Resin")
        self.remove_resin_btn = QPushButton("Remove Selected")
        resin_button_layout.addWidget(self.add_resin_btn)
        resin_button_layout.addWidget(self.remove_resin_btn)
        layout.addLayout(resin_button_layout)
        return group

    def _create_summary_group(self):
        group = QGroupBox("Production Summary")
        layout = QFormLayout(group)
        self.total_output_label = QLabel("0.00 KG")
        self.output_percent_label = QLabel("0.00 %")
        self.loss_label = QLabel("0.00 KG")
        self.loss_percent_label = QLabel("0.00 %")
        self.output_per_hour_label = QLabel("0.00 KG/HR")
        self.resin_qty_label = QLabel("0.00 KG")
        layout.addRow("Total Output:", self.total_output_label)
        layout.addRow("Output %:", self.output_percent_label)
        layout.addRow("Loss:", self.loss_label)
        layout.addRow("Loss %:", self.loss_percent_label)
        layout.addRow("Output per hour:", self.output_per_hour_label)
        layout.addRow("Resin QTY:", self.resin_qty_label)
        spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        layout.addItem(spacer)
        return group

    def _create_output_log_group(self):
        group = QGroupBox("Extruder Output Log")
        layout = QVBoxLayout(group)
        self.output_log_table = QTableWidget(0, 5)
        self.output_log_table.setHorizontalHeaderLabels(["Date", "Time Start", "Time End", "Output (kg)", "Loss (kg)"])
        self.output_log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.output_log_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.output_log_table)
        log_button_layout = QHBoxLayout()
        log_button_layout.addStretch()
        self.add_output_log_btn = QPushButton("Add Log Entry")
        self.remove_output_log_btn = QPushButton("Remove Selected")
        log_button_layout.addWidget(self.add_output_log_btn)
        log_button_layout.addWidget(self.remove_output_log_btn)
        layout.addLayout(log_button_layout)
        return group