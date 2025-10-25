# app/views/extruder_form/entry_form/ui_setup.py
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QGroupBox,
    QDateTimeEdit, QTableWidget, QHeaderView, QAbstractItemView,
    QTimeEdit, QDateEdit, QSpacerItem, QSizePolicy, QFrame, QCheckBox
)
from PyQt6.QtCore import QDateTime, QDate, QTime

from app.views.extruder_form.entry_form.widgets.lazy_loading_combo import LazyLoadingComboBox
from app.widgets.smart_combo_box import SmartComboBox


class Ui_ExtruderEntryForm:

    def setup_ui(self, parent_widget: QWidget):
        main_layout = QVBoxLayout(parent_widget)
        grid_layout = QGridLayout()
        main_layout.addLayout(grid_layout)

        # --- Row 1 (Unchanged) ---
        order_group = self._create_order_info_group()
        grid_layout.addWidget(order_group, 0, 0)
        machine_group = self._create_machine_config_group()
        grid_layout.addWidget(machine_group, 0, 1)
        zones_group = self._create_zones_group()
        grid_layout.addWidget(zones_group, 0, 2)

        # --- Row 2 & 3 ---
        output_log_group = self._create_output_log_group()
        grid_layout.addWidget(output_log_group, 1, 0, 2, 1)

        # --- FIX: Create the container group with the "No Purging" checkbox ---
        main_purging_resin_group = QGroupBox("Purging and Resin Details")
        main_purging_resin_layout = QVBoxLayout(main_purging_resin_group)

        # The checkbox is now at the top with the new label
        self.no_purging_checkbox = QCheckBox("No Purging")
        main_purging_resin_layout.addWidget(self.no_purging_checkbox)

        purging_resin_h_layout = QHBoxLayout()
        self.purging_group = self._create_purging_group()
        self.resin_group = self._create_resin_consumption_group()
        purging_resin_h_layout.addWidget(self.purging_group)
        purging_resin_h_layout.addWidget(self.resin_group)
        main_purging_resin_layout.addLayout(purging_resin_h_layout)

        grid_layout.addWidget(main_purging_resin_group, 1, 1, 1, 2)

        # Row 3 (Unchanged)
        remarks_personnel_group = self._create_remarks_personnel_group()
        grid_layout.addWidget(remarks_personnel_group, 2, 1)
        summary_group = self._create_summary_group()
        grid_layout.addWidget(summary_group, 2, 2)

        # Action Buttons
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        self.clear_button = QPushButton("Clear Form")
        self.save_button = QPushButton("Save Form")
        action_layout.addWidget(self.clear_button)
        action_layout.addWidget(self.save_button)
        main_layout.addLayout(action_layout)

    # def _create_remarks_personnel_group(self):
    #     """
    #     Creates a group for Remarks and a dynamic list of Personnel.
    #     """
    #     group = QGroupBox("Remarks & Personnel")
    #     main_v_layout = QVBoxLayout(group)
    #
    #     # Remarks (Top Section)
    #     main_v_layout.addWidget(QLabel("Remarks:"))
    #     self.remarks_input = QTextEdit()
    #     self.remarks_input.setFixedHeight(80)
    #     main_v_layout.addWidget(self.remarks_input)
    #
    #     # Separator
    #     separator = QFrame()
    #     separator.setFrameShape(QFrame.Shape.HLine)
    #     separator.setFrameShadow(QFrame.Shadow.Sunken)
    #     main_v_layout.addWidget(separator)
    #
    #     # --- FIX: New Dynamic Personnel Layout ---
    #
    #     # Static "Prepared By" field
    #     prepared_by_layout = QFormLayout()
    #     self.prepared_by_combo = QComboBox()
    #     self.prepared_by_combo.setEditable(True)  # Make it editable
    #     prepared_by_layout.addRow("Prepared By:", self.prepared_by_combo)
    #     main_v_layout.addLayout(prepared_by_layout)
    #
    #     # Container for dynamic personnel rows
    #     main_v_layout.addWidget(QLabel("Personnel:"))
    #     personnel_container_widget = QWidget()
    #     self.personnel_container_layout = QVBoxLayout(personnel_container_widget)
    #     self.personnel_container_layout.setContentsMargins(0, 0, 0, 0)  # Remove padding
    #     main_v_layout.addWidget(personnel_container_widget)
    #
    #     # Add/Remove buttons for the dynamic list
    #     personnel_buttons_layout = QHBoxLayout()
    #     personnel_buttons_layout.addStretch()
    #     self.add_personnel_btn = QPushButton("Add Personnel")
    #     self.remove_personnel_btn = QPushButton("Remove Last")
    #     personnel_buttons_layout.addWidget(self.add_personnel_btn)
    #     personnel_buttons_layout.addWidget(self.remove_personnel_btn)
    #     main_v_layout.addLayout(personnel_buttons_layout)
    #
    #     return group

    def _create_remarks_personnel_group(self):
        """
        Creates a group for Remarks and a dynamic list of Personnel with
        an indented/aligned layout.
        """
        group = QGroupBox("Remarks and Personnel")
        main_v_layout = QVBoxLayout(group)

        # Remarks (Top Section) - Unchanged
        main_v_layout.addWidget(QLabel("Remarks:"))
        self.remarks_input = QTextEdit()
        self.remarks_input.setFixedHeight(80)
        main_v_layout.addWidget(self.remarks_input)

        # Separator - Unchanged
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        main_v_layout.addWidget(separator)

        # --- THIS IS THE NEW, IMPROVED LAYOUT ---
        # 1. Use a QFormLayout for the entire personnel section for proper alignment.
        personnel_form_layout = QFormLayout()
        personnel_form_layout.setContentsMargins(0, 5, 0, 0)  # Add a little top margin

        # 2. "Prepared By" is the first row.
        self.prepared_by_combo = QComboBox()
        self.prepared_by_combo.setEditable(True)
        personnel_form_layout.addRow("Prepared By:", self.prepared_by_combo)

        # 3. Create the container that will hold all the dynamic rows.
        personnel_container_widget = QWidget()
        self.personnel_container_layout = QVBoxLayout(personnel_container_widget)
        self.personnel_container_layout.setContentsMargins(0, 0, 0, 0)
        self.personnel_container_layout.setSpacing(5)  # Spacing between dynamic rows

        # 4. Add the container to the QFormLayout. The "Personnel:" label will be on the left,
        #    and the entire container for the rows will be on the right, perfectly aligned.
        personnel_form_layout.addRow("Personnel:", personnel_container_widget)

        # Add this beautifully aligned section to the main group box layout
        main_v_layout.addLayout(personnel_form_layout)

        # 5. Add/Remove buttons remain at the bottom
        personnel_buttons_layout = QHBoxLayout()
        personnel_buttons_layout.addStretch()
        self.add_personnel_btn = QPushButton("Add Personnel")
        self.remove_personnel_btn = QPushButton("Remove Last")
        personnel_buttons_layout.addWidget(self.add_personnel_btn)
        personnel_buttons_layout.addWidget(self.remove_personnel_btn)
        main_v_layout.addLayout(personnel_buttons_layout)

        return group



    def _create_order_info_group(self):
        group = QGroupBox("Production Details")
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
        """
        Creates the machine config group with the checkbox aligned to the left
        and its label on the right.
        """
        group = QGroupBox("Machine and Configuration Settings")
        layout = QFormLayout(group)
        self.shift_combo = QComboBox()
        self.mc_no_combo = QComboBox()
        self.feed_rate_input = QLineEdit("0")
        self.rpm_input = QLineEdit("0")
        self.screen_size_combo = QComboBox()
        self.screw_config_combo = QComboBox()

        # --- THIS IS THE FIX ---
        # 1. Create a horizontal layout for the vacuum controls
        vacuum_layout = QHBoxLayout()
        self.is_vacuum_on_checkbox = QCheckBox()  # Create checkbox with no text
        vacuum_label = QLabel("Vacuum ON")  # Create a separate label

        # 2. Add the checkbox, then the label, to the horizontal layout
        vacuum_layout.addWidget(self.is_vacuum_on_checkbox)
        vacuum_layout.addWidget(vacuum_label)
        vacuum_layout.addStretch()  # Push the checkbox and label to the left

        # 3. Add the rows to the form layout
        layout.addRow("Shift:", self.shift_combo)
        layout.addRow("MC No.:", self.mc_no_combo)
        layout.addRow("Feed Rate:", self.feed_rate_input)
        layout.addRow("RPM:", self.rpm_input)
        layout.addRow("Screen Size:", self.screen_size_combo)

        # 4. Add the horizontal layout. The label part of addRow is empty.
        layout.addRow("", vacuum_layout)

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

        self.purging_product_code_combo = SmartComboBox()
        self.purging_product_code_combo.setPlaceholderText("Type to search Product Codes...")

        self.purging_start_time = QTimeEdit()
        self.purging_end_time = QTimeEdit()

        self.purging_start_time.setDisplayFormat("HH:mm")
        self.purging_start_time.setTime(QTime(0, 0))

        self.purging_end_time.setDisplayFormat("HH:mm")
        self.purging_end_time.setTime(QTime(0, 0))

        self.purging_time_used_label = QLabel("00:00")

        self.purging_resin_combo = QComboBox()
        self.purging_palletizer_input = QLineEdit("0")
        self.purging_siever_input = QLineEdit("0")

        # --- THIS IS THE FIX ---
        # 1. Create a validator with the 'group' (a QGroupBox) as its proper Qt parent.
        #    It no longer needs to be stored as a 'self' attribute.
        int_validator = QIntValidator(0, 20, group)

        # 2. Apply this safely parented validator to the input fields.
        self.purging_palletizer_input.setValidator(int_validator)
        self.purging_siever_input.setValidator(int_validator)
        # --- END FIX ---

        layout.addRow("Product Code:", self.purging_product_code_combo)
        layout.addRow("Start Time:", self.purging_start_time)
        layout.addRow("End Time:", self.purging_end_time)
        layout.addRow("Time Used (HH:mm):", self.purging_time_used_label)
        layout.addRow("Resin:", self.purging_resin_combo)
        layout.addRow("Pelletizer:", self.purging_palletizer_input)
        layout.addRow("Siever:", self.purging_siever_input)
        return group

    def _create_resin_consumption_group(self):
        group = QGroupBox("Resin Consumption")
        layout = QVBoxLayout(group)

        self.purging_details_table = QTableWidget(0, 3)
        self.purging_details_table.setHorizontalHeaderLabels(["Resin", "Notes/Additives", "Qty (Kg.)"])

        self.purging_details_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.purging_details_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.purging_details_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self.purging_details_table)

        resin_button_layout = QHBoxLayout()
        resin_button_layout.addStretch()

        # --- THIS IS THE FIX: Rename the buttons to match main.py ---
        self.add_resin_btn = QPushButton("Add Resin")
        self.remove_resin_btn = QPushButton("Remove Selected")

        resin_button_layout.addWidget(self.add_resin_btn)
        resin_button_layout.addWidget(self.remove_resin_btn)
        layout.addLayout(resin_button_layout)

        return group

    # def _create_summary_group(self):
    #     group = QGroupBox("Production Summary")
    #     layout = QFormLayout(group)
    #     self.total_output_label = QLabel("0.00 KG")
    #     self.output_percent_label = QLabel("0.00 %")
    #     self.loss_label = QLabel("0.00 KG")
    #     self.loss_percent_label = QLabel("0.00 %")
    #     self.gain_label = QLabel("0.00 KG")
    #     self.gain_percent_label = QLabel("0.00 %")
    #     self.output_per_hour_label = QLabel("0.00 KG/HR")
    #     self.resin_qty_label = QLabel("0.00 KG")
    #     layout.addRow("Total Output:", self.total_output_label)
    #     layout.addRow("Output %:", self.output_percent_label)
    #     layout.addRow("Loss:", self.loss_label)
    #     layout.addRow("Loss %:", self.loss_percent_label)
    #
    #     layout.addRow("Gain:", self.gain_label)
    #     layout.addRow("Gain %:", self.gain_percent_label)
    #
    #     layout.addRow("Output per hour:", self.output_per_hour_label)
    #     layout.addRow("Resin QTY:", self.resin_qty_label)
    #     spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
    #     layout.addItem(spacer)
    #     return group

    def _create_summary_group(self):
        group = QGroupBox("Production Summary")
        layout = QFormLayout(group)
        self.total_output_label = QLabel("0.00 KG")
        self.output_percent_label = QLabel("0.00 %")
        self.loss_label = QLabel("0.00 KG")
        self.gain_label = QLabel("0.00 KG")
        self.loss_percent_label = QLabel("0.00 %")
        self.gain_percent_label = QLabel("0.00 %")

        # --- NEW: Create the label for the total time ---
        self.total_time_used_label = QLabel("00:00")

        self.output_per_hour_label = QLabel("0.00 KG/HR")
        self.resin_qty_label = QLabel("0.00 KG")

        layout.addRow("Total Output:", self.total_output_label)

        # --- NEW: Add the new label to the layout ---
        layout.addRow("Total Time Used (HH:mm):", self.total_time_used_label)

        layout.addRow("Output %:", self.output_percent_label)
        layout.addRow("Loss:", self.loss_label)
        layout.addRow("Gain:", self.gain_label)
        layout.addRow("Loss %:", self.loss_percent_label)
        layout.addRow("Gain %:", self.gain_percent_label)
        layout.addRow("Output per hour:", self.output_per_hour_label)
        layout.addRow("Resin QTY:", self.resin_qty_label)
        spacer = QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        layout.addItem(spacer)
        return group


    def _create_output_log_group(self):
        group = QGroupBox("Extruder Output Log")
        layout = QVBoxLayout(group)

        # --- FIX: Column count is now 5 (Date, Start, End, Used, Output) ---
        self.output_log_table = QTableWidget(0, 5)

        # --- FIX: Updated header labels ---
        self.output_log_table.setHorizontalHeaderLabels([
            "Date", "Time Start", "Time End", "Time Used", "Output (kg)"
        ])

        self.output_log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.output_log_table.horizontalHeader().setSectionResizeMode(0,
                                                                      QHeaderView.ResizeMode.ResizeToContents)  # Date
        self.output_log_table.horizontalHeader().setSectionResizeMode(3,
                                                                      QHeaderView.ResizeMode.ResizeToContents)  # Time Used

        layout.addWidget(self.output_log_table)
        log_button_layout = QHBoxLayout()
        log_button_layout.addStretch()
        self.add_output_log_btn = QPushButton("Add Log Entry")
        self.remove_output_log_btn = QPushButton("Remove Selected")
        log_button_layout.addWidget(self.add_output_log_btn)
        log_button_layout.addWidget(self.remove_output_log_btn)
        layout.addLayout(log_button_layout)
        return group