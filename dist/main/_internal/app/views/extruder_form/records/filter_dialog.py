# app/views/extruder_form/records/filter_dialog.py

from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QWidget, QGridLayout, QGroupBox, QFormLayout,
                             QLineEdit, QComboBox, QCheckBox, QDoubleSpinBox)
from sqlalchemy.orm import Session
from typing import Type

# --- NEW: Import the SmartComboBox ---
from app.widgets.smart_combo_box import SmartComboBox
from .ops import ExtruderRecordsOperations


class Ui_FilterDialog(object):
    def setupUi(self, Dialog: QDialog):
        Dialog.setWindowTitle("Advanced Record Filters")
        Dialog.setMinimumWidth(450)

        self.layout = QGridLayout(Dialog)

        # Basic Filters Group
        basic_group = QGroupBox("Basic Filters")
        basic_layout = QFormLayout(basic_group)
        self.machine_combo = QComboBox()

        # --- MODIFIED: Use SmartComboBox for Product Code and Lot Number ---
        self.product_code_combo = SmartComboBox()
        self.lot_number_combo = SmartComboBox()

        self.operator_combo = QComboBox()
        basic_layout.addRow("Machine No.:", self.machine_combo)
        basic_layout.addRow("Product Code:", self.product_code_combo)
        basic_layout.addRow("Lot Number:", self.lot_number_combo)
        basic_layout.addRow("Operator:", self.operator_combo)

        # ... (Rest of the UI setup is unchanged)
        advanced_group = QGroupBox("Advanced Numeric Filters")
        advanced_layout = QFormLayout(advanced_group)
        self.total_output_min = QDoubleSpinBox(maximum=99999.99)
        self.total_output_max = QDoubleSpinBox(maximum=99999.99)
        self.output_hr_min = QDoubleSpinBox(maximum=99999.99)
        self.output_hr_max = QDoubleSpinBox(maximum=99999.99)
        advanced_layout.addRow("Total Output (Min):", self.total_output_min)
        advanced_layout.addRow("Total Output (Max):", self.total_output_max)
        advanced_layout.addRow("Output/hr (Min):", self.output_hr_min)
        advanced_layout.addRow("Output/hr (Max):", self.output_hr_max)
        options_group = QGroupBox("Other Options")
        options_layout = QFormLayout(options_group)
        self.show_deleted_checkbox = QCheckBox("Include deleted records in search")
        options_layout.addRow(self.show_deleted_checkbox)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(basic_group, 0, 0, 1, 2)
        self.layout.addWidget(advanced_group, 1, 0, 1, 2)
        self.layout.addWidget(options_group, 2, 0, 1, 2)
        self.layout.addWidget(self.button_box, 3, 1)


class FilterDialog(QDialog):
    def __init__(self, session_factory: Type[Session], parent=None):
        super().__init__(parent)
        self.ui = Ui_FilterDialog()
        self.ui.setupUi(self)
        self.ops = ExtruderRecordsOperations(session_factory)

        self._setup_connections()

    def _setup_connections(self):
        self.ui.button_box.accepted.connect(self.accept)
        self.ui.button_box.rejected.connect(self.reject)

        # --- NEW: Connect the custom signals from the SmartComboBoxes ---
        self.ui.product_code_combo.full_search_requested.connect(self._on_product_code_search)
        self.ui.lot_number_combo.full_search_requested.connect(self._on_lot_number_search)

    # --- NEW: Handler for product code live search ---
    def _on_product_code_search(self, text: str):
        """
        Receives search text from the SmartComboBox, calls the ops controller,
        and updates the combo with the database results.
        """
        results = self.ops.search_product_codes(search_term=text)
        self.ui.product_code_combo.update_with_search_results(results)

    # --- NEW: Handler for lot number live search ---
    def _on_lot_number_search(self, text: str):
        """
        Receives search text from the SmartComboBox, calls the ops controller,
        and updates the combo with the database results.
        """
        results = self.ops.search_lot_numbers(search_term=text)
        self.ui.lot_number_combo.update_with_search_results(results)

    def populate_dropdowns(self):
        """
        Queries the database and fills all combo boxes.
        This is called right before showing the dialog.
        """
        # --- Populate standard combo boxes (unchanged) ---
        current_machine = self.ui.machine_combo.currentData()
        self.ui.machine_combo.clear()
        self.ui.machine_combo.addItem("All Machines", userData=None)
        machines = self.ops.get_distinct_machines()
        for machine_id, name in machines:
            self.ui.machine_combo.addItem(name, userData=machine_id)
        if current_machine:
            index = self.ui.machine_combo.findData(current_machine)
            if index != -1: self.ui.machine_combo.setCurrentIndex(index)

        current_operator = self.ui.operator_combo.currentData()
        self.ui.operator_combo.clear()
        self.ui.operator_combo.addItem("All Operators", userData=None)
        operators = self.ops.get_distinct_operators()
        for op_id, name in operators:
            self.ui.operator_combo.addItem(name, userData=op_id)
        if current_operator:
            index = self.ui.operator_combo.findData(current_operator)
            if index != -1: self.ui.operator_combo.setCurrentIndex(index)

        # --- MODIFIED: Perform initial population for SmartComboBoxes ---
        initial_codes = self.ops.get_initial_product_codes()
        self.ui.product_code_combo.populate_initial(initial_codes)

        initial_lots = self.ops.get_initial_lot_numbers()
        self.ui.lot_number_combo.populate_initial(initial_lots)

    def get_filters(self) -> dict:
        """Returns a dictionary of the selected filter criteria."""
        filters = {}
        # Standard combo filters
        if self.ui.machine_combo.currentIndex() > 0:
            filters['machine_id'] = self.ui.machine_combo.currentData()
        if self.ui.operator_combo.currentIndex() > 0:
            filters['operator_id'] = self.ui.operator_combo.currentData()

        # --- MODIFIED: Retrieve values from SmartComboBoxes using currentText() ---
        if product_code := self.ui.product_code_combo.currentText().strip():
            filters['product_code'] = product_code
        if lot_number := self.ui.lot_number_combo.currentText().strip():
            # Use a different key to distinguish from the global search
            filters['lot_number_exact'] = lot_number

        # Advanced numeric filters (unchanged)
        if self.ui.total_output_min.value() > 0:
            filters['total_output_min'] = self.ui.total_output_min.value()
        if self.ui.total_output_max.value() > 0:
            filters['total_output_max'] = self.ui.total_output_max.value()
        if self.ui.output_hr_min.value() > 0:
            filters['output_hr_min'] = self.ui.output_hr_min.value()
        if self.ui.output_hr_max.value() > 0:
            filters['output_hr_max'] = self.ui.output_hr_max.value()

        filters['show_deleted'] = self.ui.show_deleted_checkbox.isChecked()
        return filters