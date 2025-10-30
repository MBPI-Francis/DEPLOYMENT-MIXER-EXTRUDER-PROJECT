# app/views/extruder_form/entry_form/main.py

from PyQt6.QtCore import QDate, QTime, Qt
from PyQt6.QtWidgets import QWidget, QMessageBox, QComboBox, QTableWidgetItem, QLineEdit, QDateEdit, QTimeEdit
from typing import Type
from sqlalchemy.orm import sessionmaker
from decimal import Decimal, InvalidOperation

from .ui_setup import Ui_ExtruderEntryForm
from .ops import ExtruderOpsController
from .widgets.dialogs import LotNumberDialog


class ExtruderEntryFormView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.controller = ExtruderOpsController(self.Session)
        self.lot_number_dialog = None
        self.aggregated_prod_ids = set()
        self.aggregated_formula_ids = set()
        self.aggregated_order_nos = set()
        self.production_cut_active = False
        self.employee_list = []
        self.position_list = []
        self.resin_list = []
        self.zone_mapping = {}
        self.ui = Ui_ExtruderEntryForm()
        self.ui.setup_ui(self)
        self._connect_signals()
        self._initial_load()

    def _connect_signals(self):
        self.ui.lot_number_select_btn.clicked.connect(self._open_lot_number_dialog)
        self.ui.add_resin_btn.clicked.connect(self._add_resin_row)
        self.ui.remove_resin_btn.clicked.connect(self._remove_selected_resin)
        self.ui.add_output_log_btn.clicked.connect(self._add_output_log_row)
        self.ui.remove_output_log_btn.clicked.connect(self._remove_selected_output_log)
        self.ui.resin_table.cellChanged.connect(self._update_production_summary)
        self.ui.output_log_table.cellChanged.connect(self._update_production_summary)
        self.ui.qty_order_input.textChanged.connect(self._update_production_summary)
        self.ui.save_button.clicked.connect(self._save_form_data)
        self.ui.clear_button.clicked.connect(self._clear_form)

    def _initial_load(self):
        try:
            self.employee_list = self.controller.get_all_employees()
            self.position_list = self.controller.get_all_positions()
            self.ui.prepared_by_combo.addItem("- Select -", None)
            self.ui.operator_combo.addItem("- Select -", None)
            for emp in self.employee_list:
                full_name = f"{emp.first_name} {emp.last_name}"
                self.ui.prepared_by_combo.addItem(full_name, emp.id)
                self.ui.operator_combo.addItem(full_name, emp.id)
            self.ui.position_combo.addItem("- Select -", None)
            for pos in self.position_list:
                self.ui.position_combo.addItem(pos.name, pos.id)
            self.ui.shift_combo.addItems(["- Select -", "1st Shift", "2nd Shift", "3rd Shift"])
            machines = self.controller.get_all_machines()
            self.ui.mc_no_combo.addItem("- Select -", None)
            for m in machines: self.ui.mc_no_combo.addItem(m.name, m.id)
            screen_sizes = self.controller.get_all_screen_sizes()
            self.ui.screen_size_combo.addItem("- Select -", None)
            for s in screen_sizes: self.ui.screen_size_combo.addItem(s.size, s.id)
            self.ui.screw_config_combo.addItems(["- Select -", "Coil", "Configuration"])
            self.resin_list = self.controller.get_all_resins()
            self.ui.purging_resin_combo.addItem("- Select -", None)
            self.ui.purging_product_code_combo.addItem("- Select -", None)
            for r in self.resin_list:
                self.ui.purging_resin_combo.addItem(r.name, r.id)
                self.ui.purging_product_code_combo.addItem(r.name, r.id)
            zones = self.controller.get_all_zones()
            self.zone_mapping = {zone.name: zone.id for zone in zones}
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not load initial data: {e}")

    def _open_lot_number_dialog(self):
        try:
            if self.lot_number_dialog is None or not self.lot_number_dialog.isVisible():
                initial_product_code, initial_customer = None, None
                if self.ui.lot_number_input.text():
                    first_lot = self.ui.lot_number_input.text().split(';')[0].strip()
                    lot_details = self.controller.get_details_for_lot(first_lot)
                    if lot_details:
                        initial_product_code = lot_details.get("product_code")
                        initial_customer = lot_details.get("customer")
                self.lot_number_dialog = LotNumberDialog(self.controller, self._handle_lot_selection, self, initial_product_code=initial_product_code, initial_customer=initial_customer)
                self.lot_number_dialog.show()
            self.lot_number_dialog.activateWindow()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open lot number selector: {e}")

    def _handle_lot_selection(self, selection_data: dict):
        lot_data = selection_data.get("lot_data")
        prod_cut_qty = selection_data.get("prod_cut_qty")
        if not lot_data: return
        new_prod_id = str(lot_data.get("prod_id", ""))
        new_formula_id = str(lot_data.get("formula_id", ""))
        new_order_no = str(lot_data.get("order_no", ""))
        if new_prod_id: self.aggregated_prod_ids.add(new_prod_id)
        if new_formula_id: self.aggregated_formula_ids.add(new_formula_id)
        if new_order_no: self.aggregated_order_nos.add(new_order_no)
        current_lots_text = self.ui.lot_number_input.text()
        lot_set = set(current_lots_text.split('; ')) if current_lots_text else set()
        lot_set.add(lot_data.get("lot_num", ""))
        final_lots = sorted([item for item in lot_set if item])
        self.ui.lot_number_input.setText("; ".join(final_lots))
        try:
            if prod_cut_qty is not None:
                self.production_cut_active = True
                prod_cut_str = f"{Decimal(prod_cut_qty):.2f}"
                self.ui.qty_produced_input.setText(prod_cut_str)
                self.ui.qty_order_input.setText(prod_cut_str)
            elif not self.production_cut_active:
                total_produced = self.controller.get_total_produced_weight_for_lots(final_lots)
                self.ui.qty_produced_input.setText(f"{total_produced:.2f}")
        except Exception as e:
            QMessageBox.critical(self, "Calculation Error", f"Could not set quantity values: {e}")
        if len(final_lots) == 1:
            self._prepopulate_static_fields(final_lots[0])

    def _prepopulate_static_fields(self, lot_number: str):
        details = self.controller.get_details_for_lot(lot_number)
        if details:
            self.ui.product_code_input.setText(details.get("product_code", ""))
            self.ui.customer_input.setText(details.get("customer", ""))
            if not self.production_cut_active:
                order_no = details.get("order_no")
                if order_no:
                    order_qty = self.controller.get_order_qty_by_order_number(order_no)
                    if order_qty is not None:
                        self.ui.qty_order_input.setText(f"{order_qty:.2f}")
                    else:
                        self.ui.qty_order_input.setText("0.00")
            self._update_production_summary()

    def _add_resin_row(self):
        row_position = self.ui.resin_table.rowCount()
        self.ui.resin_table.insertRow(row_position)
        resin_combo = QComboBox()
        resin_combo.addItem("- Select -", None)
        for resin in self.resin_list:
            resin_combo.addItem(resin.name, resin.id)
        self.ui.resin_table.setCellWidget(row_position, 0, resin_combo)
        self.ui.resin_table.setItem(row_position, 1, QTableWidgetItem("0.00"))
    def _remove_selected_resin(self):
        current_row = self.ui.resin_table.currentRow()
        if current_row >= 0:
            self.ui.resin_table.removeRow(current_row)
    def _add_output_log_row(self):
        row_position = self.ui.output_log_table.rowCount()
        self.ui.output_log_table.insertRow(row_position)
        date_edit = QDateEdit(QDate.currentDate())
        date_edit.setCalendarPopup(True)
        time_start_edit = QTimeEdit(QTime.currentTime())
        time_end_edit = QTimeEdit(QTime.currentTime())
        self.ui.output_log_table.setCellWidget(row_position, 0, date_edit)
        self.ui.output_log_table.setCellWidget(row_position, 1, time_start_edit)
        self.ui.output_log_table.setCellWidget(row_position, 2, time_end_edit)
        self.ui.output_log_table.setItem(row_position, 3, QTableWidgetItem("0.00"))
        self.ui.output_log_table.setItem(row_position, 4, QTableWidgetItem("0.00"))
    def _remove_selected_output_log(self):
        current_row = self.ui.output_log_table.currentRow()
        if current_row >= 0:
            self.ui.output_log_table.removeRow(current_row)
    def _update_production_summary(self):
        try:
            total_output = Decimal("0.00")
            total_loss = Decimal("0.00")
            for row in range(self.ui.output_log_table.rowCount()):
                output_item = self.ui.output_log_table.item(row, 3)
                loss_item = self.ui.output_log_table.item(row, 4)
                if output_item: total_output += Decimal(output_item.text() or '0')
                if loss_item: total_loss += Decimal(loss_item.text() or '0')
            self.ui.total_output_label.setText(f"{total_output:.2f} KG")
            self.ui.loss_label.setText(f"{total_loss:.2f} KG")
            qty_ordered = Decimal(self.ui.qty_order_input.text() or '0')
            output_percent = (total_output / qty_ordered * 100) if qty_ordered > 0 else Decimal("0.00")
            self.ui.output_percent_label.setText(f"{output_percent:.2f} %")
            total_resin = Decimal("0.00")
            for row in range(self.ui.resin_table.rowCount()):
                qty_item = self.ui.resin_table.item(row, 1)
                if qty_item: total_resin += Decimal(qty_item.text() or '0')
            self.ui.resin_qty_label.setText(f"{total_resin:.2f} KG")
            loss_percent = (total_loss / total_resin * 100) if total_resin > 0 else Decimal("0.00")
            self.ui.loss_percent_label.setText(f"{loss_percent:.2f} %")
        except (InvalidOperation, TypeError): pass
    def _clear_form(self):
        self.aggregated_prod_ids.clear()
        self.aggregated_formula_ids.clear()
        self.aggregated_order_nos.clear()
        self.production_cut_active = False
        self.ui.lot_number_input.clear()
        self.ui.product_code_input.clear()
        self.ui.customer_input.clear()
        self.ui.qty_order_input.setText("0.00")
        self.ui.qty_produced_input.setText("0.00")
        self.ui.target_output_hr_input.setText("0.00")
        self.ui.prepared_by_combo.setCurrentIndex(0)
        self.ui.operator_combo.setCurrentIndex(0)
        self.ui.position_combo.setCurrentIndex(0)
        self.ui.shift_combo.setCurrentIndex(0)
        self.ui.mc_no_combo.setCurrentIndex(0)
        self.ui.feed_rate_input.setText("0.00")
        self.ui.rpm_input.setText("0.00")
        self.ui.screen_size_combo.setCurrentIndex(0)
        self.ui.screw_config_combo.setCurrentIndex(0)
        self.ui.purging_product_code_combo.setCurrentIndex(0)
        self.ui.purging_resin_combo.setCurrentIndex(0)
        self.ui.purging_palletizer_input.setText("0.00")
        self.ui.purging_siever_input.setText("0.00")
        self.ui.resin_table.setRowCount(0)
        self.ui.output_log_table.setRowCount(0)
        for widget in self.ui.zone_inputs.values(): widget.setText("0")
        self.ui.remarks_input.clear()
        self._update_production_summary()
        QMessageBox.information(self, "Cleared", "Form has been cleared.")
    def _gather_data_from_ui(self) -> dict:
        prod_id_str = "; ".join(sorted([item for item in self.aggregated_prod_ids if item]))
        formula_no_str = "; ".join(sorted([item for item in self.aggregated_formula_ids if item]))
        order_no_str = "; ".join(sorted([item for item in self.aggregated_order_nos if item]))
        def get_table_cell_data(table, row, col):
            widget = table.cellWidget(row, col)
            if isinstance(widget, QComboBox): return widget.currentData(), widget.currentText()
            item = table.item(row, col)
            return (item.text() if item else None), None
        data = {
            "main": { "lot_number": self.ui.lot_number_input.text(), "production_id": prod_id_str, "formula_no": formula_no_str, "order_no": order_no_str, "product_code": self.ui.product_code_input.text(), "customer": self.ui.customer_input.text(), "qty_order": self.ui.qty_order_input.text(), "prepared_by_id": self.ui.prepared_by_combo.currentData(), "prepared_by_name": self.ui.prepared_by_combo.currentText(), "machine_id": self.ui.mc_no_combo.currentData(), },
            "machine_config": { "shift": self.ui.shift_combo.currentText(), "feed_rate": self.ui.feed_rate_input.text(), "rpm": self.ui.rpm_input.text(), "screen_size_id": self.ui.screen_size_combo.currentData(), "screw_config": self.ui.screw_config_combo.currentText(), },
            "purging": { "product_code_id": self.ui.purging_product_code_combo.currentData(), "product_code_name": self.ui.purging_product_code_combo.currentText(), "start_time": self.ui.purging_start_time.time().toPyTime(), "end_time": self.ui.purging_end_time.time().toPyTime(), "resin_id": self.ui.purging_resin_combo.currentData(), "palletizer": self.ui.purging_palletizer_input.text(), "siever": self.ui.purging_siever_input.text(), },
            "resin_consumption": [ { "resin_id": get_table_cell_data(self.ui.resin_table, r, 0)[0], "resin_name": get_table_cell_data(self.ui.resin_table, r, 0)[1], "qty": get_table_cell_data(self.ui.resin_table, r, 1)[0] } for r in range(self.ui.resin_table.rowCount()) ],
            "output_log": [ { "date": self.ui.output_log_table.cellWidget(r, 0).date().toPyDate(), "time_start": self.ui.output_log_table.cellWidget(r, 1).time().toPyTime(), "time_end": self.ui.output_log_table.cellWidget(r, 2).time().toPyTime(), "output": get_table_cell_data(self.ui.output_log_table, r, 3)[0], "loss": get_table_cell_data(self.ui.output_log_table, r, 4)[0], } for r in range(self.ui.output_log_table.rowCount()) ],
            "zone_temps": {name: widget.text() for name, widget in self.ui.zone_inputs.items()},
            "personnel": [{"employee_id": self.ui.operator_combo.currentData(), "position_id": self.ui.position_combo.currentData()}],
            "summary": { "resin_qty_total": Decimal(self.ui.resin_qty_label.text().replace(" KG", "")) }
        }
        return data
    def _save_form_data(self):
        if not self.ui.lot_number_input.text():
            QMessageBox.warning(self, "Missing Data", "Please select a lot number before saving.")
            return
        form_data = self._gather_data_from_ui()
        try:
            self.controller.save_full_form(form_data, self.zone_mapping)
            QMessageBox.information(self, "Success", "Form data has been saved (simulated).")
            self._clear_form()
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Could not save the form: {e}\n\nCheck console for details.")
            import traceback
            traceback.print_exc()