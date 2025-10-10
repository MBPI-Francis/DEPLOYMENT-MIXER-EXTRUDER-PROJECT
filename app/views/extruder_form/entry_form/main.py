# app/views/extruder_form/entry_form/main.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QWidget, QMessageBox
from typing import Type
from sqlalchemy.orm import Session, sessionmaker
from decimal import Decimal

# Import the new classes
from .ui_setup import UiExtruderForm
from .ops import ExtruderOpsController
from .widgets.dialogs import LotNumberDialog, GenericSubFormDialog


class ExtruderEntryFormView(QWidget):
    # ... (__init__, _connect_signals, _initial_load are mostly the same) ...
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)

        self.Session = session_factory
        self.controller = ExtruderOpsController(self.Session)

        self.ui = UiExtruderForm()
        self.ui.setup_ui(self)

        self._connect_signals()
        self._initial_load()

    def _connect_signals(self):
        self.ui.lot_number_select_btn.clicked.connect(self._open_lot_number_dialog)
        self.ui.formula_id_select_btn.clicked.connect(self._open_formula_id_dialog)
        self.ui.zone_temps_btn.clicked.connect(lambda: self._open_generic_dialog("Zone Temperatures"))
        self.ui.personnel_btn.clicked.connect(lambda: self._open_generic_dialog("Extruder Personnel"))
        self.ui.purging_btn.clicked.connect(lambda: self._open_generic_dialog("Purging Details"))
        self.ui.machine_config_btn.clicked.connect(lambda: self._open_generic_dialog("Machine Configuration"))
        self.ui.extruder_output_btn.clicked.connect(lambda: self._open_generic_dialog("Extruder Output"))
        self.ui.used_materials_btn.clicked.connect(lambda: self._open_generic_dialog("Used Materials"))
        self.ui.save_button.clicked.connect(self._save_form_data)
        self.ui.clear_button.clicked.connect(self._clear_form)

    def _initial_load(self):
        """Load initial data for combo boxes."""
        try:
            customers = self.controller.get_customers()
            self.ui.customer_combo.addItem("", None)  # Add a blank default item
            for c in customers:
                self.ui.customer_combo.addItem(c.name, c.id)

            machines = self.controller.get_machines()
            self.ui.machine_combo.addItem("", None)  # Add a blank default item
            for m in machines:
                self.ui.machine_combo.addItem(m.name, m.id)

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not load initial data: {e}")

    def _open_lot_number_dialog(self):
        """
        Opens the lot number dialog, passing the current product code context if one exists.
        """
        try:
            initial_product_code = None
            current_lot_text = self.ui.lot_number_input.text()

            # --- NEW LOGIC ---
            # If there's already text in the lot number field, find its product code
            if current_lot_text:
                # Get the very first lot number from the semi-colon separated string
                first_lot = current_lot_text.split(';')[0].strip()
                if first_lot:
                    # Use our new controller method to get the code
                    initial_product_code = self.controller.get_product_code_for_lot(first_lot)
            # --- END NEW LOGIC ---

            # Pass the initial code (which could be None) to the dialog's constructor
            dialog = LotNumberDialog(
                self.controller,
                self._handle_dialog_selections_applied,
                self,
                initial_product_code=initial_product_code
            )
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open lot number selector: {e}")
            import traceback
            traceback.print_exc()

    def _handle_dialog_selections_applied(self, selection_data: dict):
        """
        This method is passed to the dialog and is called when 'Apply' is clicked.
        """
        selected_lots = selection_data.get("lots", [])
        selected_formulas = selection_data.get("formulas", [])

        if not selected_lots:
            return

        # Append to existing values instead of overwriting, using a set for uniqueness
        current_lots = set(self.ui.lot_number_input.text().split('; ')) if self.ui.lot_number_input.text() else set()
        current_formulas = set(
            self.ui.formula_id_input.text().split('; ')) if self.ui.formula_id_input.text() else set()

        current_lots.update(selected_lots)
        current_formulas.update(selected_formulas)

        # Update the main form's UI
        self.ui.lot_number_input.setText("; ".join(sorted(list(current_lots))))
        self.ui.formula_id_input.setText("; ".join(sorted(list(current_formulas))))

        # Trigger data prepopulation with the complete list of lots
        self._prepopulate_form_from_lots(list(current_lots))

    # ... (the rest of the file, including _prepopulate_form_from_lots, _clear_form, _save_form_data etc. remains unchanged) ...
    def _prepopulate_form_from_lots(self, lot_numbers: list):
        """Calls the controller to get data and fills the main form fields."""
        try:
            data = self.controller.get_data_for_lot_numbers(lot_numbers)
            self.ui.production_id_input.setText(data.get("production_id", ""))
            self.ui.product_code_input.setText(data.get("product_code", ""))
            self.ui.order_no_input.setText(data.get("order_no", ""))

            total_input = data.get("total_input", Decimal("0.00"))
            self.ui.total_input_display.setText(f"{total_input:.2f}")

            customer_name = data.get("customer_name")
            if customer_name:
                index = self.ui.customer_combo.findText(customer_name, Qt.MatchFlag.MatchFixedString)
                if index >= 0:
                    self.ui.customer_combo.setCurrentIndex(index)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to prepopulate form data: {e}")

    def _open_formula_id_dialog(self):
        """Re-opens the lot number dialog to allow changing the formula selection."""
        QMessageBox.information(self, "Select Formula",
                                "To change the selected formulas, please click the 'Select...' button next to the Lot Numbers.")
        self._open_lot_number_dialog()

    def _open_generic_dialog(self, title):
        dialog = GenericSubFormDialog(title, self)
        dialog.exec()

    def _clear_form(self):
        """Clears all input fields on the form."""
        # Clear line edits
        self.ui.lot_number_input.clear()
        self.ui.formula_id_input.clear()
        self.ui.production_id_input.clear()
        self.ui.product_code_input.clear()
        self.ui.order_no_input.clear()
        self.ui.ordered_qty_input.setText("0.00")
        self.ui.total_input_display.setText("0.00")
        self.ui.remarks_textedit.clear()

        # Reset combo boxes
        self.ui.customer_combo.setCurrentIndex(0)
        self.ui.machine_combo.setCurrentIndex(0)

        # Reset labels
        self.ui.total_output_display.setText("0.00")
        self.ui.output_percent_display.setText("0.00%")
        self.ui.loss_display.setText("0.00")
        self.ui.loss_percent_display.setText("0.00%")
        self.ui.output_per_hour_display.setText("0.00")

        # In a real app, you would also clear the data models for sub-forms
        print("Form cleared.")

    def _save_form_data(self):
        """Gathers all data from the UI and passes it to the controller to save."""
        if not self.ui.lot_number_input.text():
            QMessageBox.warning(self, "Missing Data", "Please select a lot number before saving.")
            return

        form_data = {
            "main": {
                "lot_number": self.ui.lot_number_input.text(),
                "formula_no": self.ui.formula_id_input.text(),
                "production_id": self.ui.production_id_input.text(),
                "product_code": self.ui.product_code_input.text(),
                "order_no": self.ui.order_no_input.text(),
                "customer_id": self.ui.customer_combo.currentData(),
                "machine_id": self.ui.machine_combo.currentData(),
                "machine_datetime_start": self.ui.start_datetime_edit.dateTime().toPyDateTime(),
                "machine_datetime_end": self.ui.end_datetime_edit.dateTime().toPyDateTime(),
                "qty_order": self.ui.ordered_qty_input.text(),
                "total_input": self.ui.total_input_display.text(),
                "remarks": self.ui.remarks_textedit.toPlainText(),
            },
            "personnel": [],
            "machine_temps": [],
            # ... other sub-form data will be gathered here ...
        }

        try:
            self.controller.save_full_form(form_data)
            QMessageBox.information(self, "Success", "Form data has been saved (simulated).")
            self._clear_form()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save the form: {e}")