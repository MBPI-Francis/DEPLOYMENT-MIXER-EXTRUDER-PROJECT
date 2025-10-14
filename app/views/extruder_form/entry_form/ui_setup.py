# app/views/extruder_form/entry_form/ui_setup.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTextEdit, QGroupBox,
    QDateTimeEdit
)
from PyQt6.QtCore import QDateTime


class UiExtruderForm:
    """
    Creates and arranges all the widgets for the Extruder Entry Form.
    """

    def setup_ui(self, parent_widget: QWidget):
        # --- Create Widgets ---

        # Lot Number and Formula ID
        self.lot_number_input = QLineEdit()
        self.lot_number_select_btn = QPushButton("Select...")
        self.formula_id_input = QLineEdit()

        # Main Form Fields
        self.production_id_input = QLineEdit()
        self.production_id_input.setReadOnly(True)
        self.product_code_input = QLineEdit()
        self.product_code_input.setReadOnly(True)
        self.order_no_input = QLineEdit()
        self.order_no_input.setReadOnly(True)

        # --- MODIFIED: Changed from QComboBox to QLineEdit ---
        self.customer_input = QLineEdit()
        self.customer_input.setReadOnly(True) # Make it uneditable

        self.machine_combo = QComboBox()
        self.start_datetime_edit = QDateTimeEdit()
        self.start_datetime_edit.setDateTime(QDateTime.currentDateTime())
        self.end_datetime_edit = QDateTimeEdit()
        self.end_datetime_edit.setDateTime(QDateTime.currentDateTime())
        self.ordered_qty_input = QLineEdit("0.00")
        self.total_input_display = QLineEdit("0.00")
        # self.total_input_display.setReadOnly(True)
        self.remarks_textedit = QTextEdit()

        # Sub-Form Buttons
        self.zone_temps_btn = QPushButton("Set Zone Temperatures")
        self.personnel_btn = QPushButton("Add Personnel")
        self.purging_btn = QPushButton("Add Purging Details")
        self.machine_config_btn = QPushButton("Add Machine Config")
        self.extruder_output_btn = QPushButton("Add Extruder Output")
        self.used_materials_btn = QPushButton("View Used Materials")

        # Summary Fields
        self.total_output_display = QLabel("0.00")
        self.output_percent_display = QLabel("0.00%")
        self.loss_display = QLabel("0.00")
        self.loss_percent_display = QLabel("0.00%")
        self.output_per_hour_display = QLabel("0.00")

        # Action Buttons
        self.save_button = QPushButton("Save Form")
        self.clear_button = QPushButton("Clear Form")

        # --- Layouts ---

        # Main layout for the entire widget
        main_layout = QVBoxLayout(parent_widget)

        # Top section: Lot Number and Formula selection
        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("Lot Number(s):"))
        selection_layout.addWidget(self.lot_number_input)
        selection_layout.addWidget(self.lot_number_select_btn)
        selection_layout.addSpacing(20)
        selection_layout.addWidget(QLabel("Formula ID(s):"))
        selection_layout.addWidget(self.formula_id_input)
        main_layout.addLayout(selection_layout)

        # Grid layout for the main form and summary
        grid_layout = QGridLayout()
        main_layout.addLayout(grid_layout)

        # General Info Group
        general_group = QGroupBox("General Information")
        form_layout = QFormLayout()
        general_group.setLayout(form_layout)
        form_layout.addRow("Production ID:", self.production_id_input)
        form_layout.addRow("Product Code:", self.product_code_input)
        form_layout.addRow("Order No:", self.order_no_input)
        form_layout.addRow("Customer:", self.customer_input)
        form_layout.addRow("Machine:", self.machine_combo)
        form_layout.addRow("Machine Start:", self.start_datetime_edit)
        form_layout.addRow("Machine End:", self.end_datetime_edit)
        form_layout.addRow("Ordered Qty (kg):", self.ordered_qty_input)
        form_layout.addRow("Total Input (kg):", self.total_input_display)
        form_layout.addRow("Remarks:", self.remarks_textedit)

        # Sub-Forms Group
        sub_forms_group = QGroupBox("Form Details")
        sub_forms_layout = QVBoxLayout()
        sub_forms_group.setLayout(sub_forms_layout)
        sub_forms_layout.addWidget(self.zone_temps_btn)
        sub_forms_layout.addWidget(self.personnel_btn)
        sub_forms_layout.addWidget(self.purging_btn)
        sub_forms_layout.addWidget(self.machine_config_btn)
        sub_forms_layout.addWidget(self.extruder_output_btn)
        sub_forms_layout.addWidget(self.used_materials_btn)

        # Summary Group
        summary_group = QGroupBox("Production Summary")
        summary_layout = QFormLayout()
        summary_group.setLayout(summary_layout)
        summary_layout.addRow("Total Output (kg):", self.total_output_display)
        summary_layout.addRow("Output %:", self.output_percent_display)
        summary_layout.addRow("Loss (kg):", self.loss_display)
        summary_layout.addRow("Loss %:", self.loss_percent_display)
        summary_layout.addRow("Output/Hour (kg):", self.output_per_hour_display)

        grid_layout.addWidget(general_group, 0, 0)  # Row 0, Col 0
        grid_layout.addWidget(sub_forms_group, 0, 1)  # Row 0, Col 1
        grid_layout.addWidget(summary_group, 1, 1)  # Row 1, Col 1
        grid_layout.setColumnStretch(0, 2)  # First column is twice as wide
        grid_layout.setColumnStretch(1, 1)

        # Bottom Action Buttons
        action_layout = QHBoxLayout()
        action_layout.addStretch()
        action_layout.addWidget(self.clear_button)
        action_layout.addWidget(self.save_button)
        main_layout.addLayout(action_layout)