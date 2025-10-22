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
            machines = self.controller.get_machines()
            self.ui.machine_combo.addItem("", None)  # Add a blank default item
            for m in machines:
                self.ui.machine_combo.addItem(m.name, m.id)

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not load initial data: {e}")

    def _open_lot_number_dialog(self):
        """
        Opens the lot number dialog, passing the current product code and
        customer context if they exist.
        """
        try:
            initial_product_code = None
            initial_customer = None
            current_lot_text = self.ui.lot_number_input.text()

            # If there's already text, find the details for the first lot
            if current_lot_text:
                first_lot = current_lot_text.split(';')[0].strip()
                if first_lot:
                    # Use the new, more detailed controller method
                    lot_details = self.controller.get_details_for_lot(first_lot)
                    if lot_details:
                        initial_product_code = lot_details.get("product_code")
                        initial_customer = lot_details.get("customer")

            # Pass both initial locks to the dialog's constructor
            dialog = LotNumberDialog(
                self.controller,
                self._handle_dialog_selections_applied,
                self,
                initial_product_code=initial_product_code,
                initial_customer=initial_customer
            )
            dialog.exec()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open lot number selector: {e}")
            import traceback
            traceback.print_exc()



    # --- THIS IS THE ONLY METHOD THAT IS CHANGED ---
    def _handle_dialog_selections_applied(self, selection_data: dict):
        """
        This method is passed to the dialog and is called when 'Apply' is clicked.
        """
        selected_lots = selection_data.get("lots", [])
        selected_formulas = selection_data.get("formulas", [])

        if not selected_lots:
            return

        current_lots = set(self.ui.lot_number_input.text().split('; ')) if self.ui.lot_number_input.text() else set()
        current_formulas = set(
            self.ui.formula_id_input.text().split('; ')) if self.ui.formula_id_input.text() else set()

        current_lots.update(selected_lots)
        current_formulas.update(selected_formulas)

        final_lots = sorted([lot for lot in current_lots if lot])
        final_formulas = sorted([f for f in current_formulas if f])

        self.ui.lot_number_input.setText("; ".join(final_lots))
        self.ui.formula_id_input.setText("; ".join(final_formulas))

        self._prepopulate_form_from_lots(final_lots)

        # --- FIX: Call the new, correct calculation method ---
        try:
            # Use the complete list of final_lots for the calculation
            total_input = self.controller.get_total_batch_weight_for_lots(final_lots)
            self.ui.total_input_display.setText(f"{total_input:.2f}")
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Could not calculate total input: {e}")
        # --- END FIX ---


    # def _handle_dialog_selections_applied(self, selection_data: dict):
    #     """
    #     This method is passed to the dialog and is called when 'Apply' is clicked.
    #     """
    #     selected_lots = selection_data.get("lots", [])
    #     selected_formulas = selection_data.get("formulas", [])
    #
    #     if not selected_lots:
    #         return
    #
    #     current_lots = set(self.ui.lot_number_input.text().split('; ')) if self.ui.lot_number_input.text() else set()
    #     current_formulas = set(
    #         self.ui.formula_id_input.text().split('; ')) if self.ui.formula_id_input.text() else set()
    #
    #     current_lots.update(selected_lots)
    #     current_formulas.update(selected_formulas)
    #
    #     # Filter out any empty strings that might result from splitting
    #     final_lots = sorted([lot for lot in current_lots if lot])
    #     final_formulas = sorted([f for f in current_formulas if f])
    #
    #     self.ui.lot_number_input.setText("; ".join(final_lots))
    #     self.ui.formula_id_input.setText("; ".join(final_formulas))
    #
    #     # --- NEW LOGIC ---
    #     # 1. Prepopulate fields like Product Code, Order No, etc.
    #     self._prepopulate_form_from_lots(final_lots)
    #
    #     # 2. Call the new, accurate calculation method for Total Input
    #     try:
    #         total_input = self.controller.calculate_total_input(final_lots, final_formulas)
    #         self.ui.total_input_display.setText(f"{total_input:.2f}")
    #     except Exception as e:
    #         QMessageBox.critical(self, "Calculation Error", f"Could not calculate total input: {e}")
    #     # --- END NEW LOGIC ---

    # --- METHOD MODIFIED to remove the old total_input logic ---
    def _prepopulate_form_from_lots(self, lot_numbers: list):
        """Calls the controller to get data and fills the main form fields."""
        try:
            data = self.controller.get_data_for_lot_numbers(lot_numbers)
            self.ui.production_id_input.setText(data.get("production_id", ""))
            self.ui.product_code_input.setText(data.get("product_code", ""))
            self.ui.order_no_input.setText(data.get("order_no", ""))

            # The total_input line has been removed from here.

            customer_name = data.get("customer_name", "")
            self.ui.customer_input.setText(customer_name)
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
        self.ui.customer_input.clear()
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
                "customer": self.ui.customer_input.text(),
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