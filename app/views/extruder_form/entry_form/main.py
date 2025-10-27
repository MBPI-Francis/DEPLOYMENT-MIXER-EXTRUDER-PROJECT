# app/views/extruder_form/entry_form/main.py
import traceback
from datetime import datetime, timedelta

from PyQt6.QtCore import QDate, QTime, Qt, QEvent, QObject
from PyQt6.QtWidgets import QWidget, QMessageBox, QComboBox, QTableWidgetItem, QLineEdit, QDateEdit, QTimeEdit, \
    QHBoxLayout
from typing import Type
from sqlalchemy.orm import sessionmaker
from decimal import Decimal, InvalidOperation
from .widgets.success_dialog import SuccessDialog
from .widgets.error_dialog import ErrorDialog

from .ui_setup import Ui_ExtruderEntryForm
from .ops import ExtruderOpsController
from .widgets.dialogs import LotNumberDialog
from .widgets.smart_date_edit import SmartDateEdit


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
        self.ui.no_purging_checkbox.toggled.connect(self._on_no_purging_toggled)
        self.ui.purging_start_time.timeChanged.connect(self._calculate_purging_time_used)
        self.ui.purging_end_time.timeChanged.connect(self._calculate_purging_time_used)

        self.ui.add_personnel_btn.clicked.connect(self._add_personnel_row)
        self.ui.remove_personnel_btn.clicked.connect(self._remove_personnel_row)

        self.ui.lot_number_select_btn.clicked.connect(self._open_lot_number_dialog)
        self.ui.add_resin_btn.clicked.connect(self._add_resin_row)
        self.ui.remove_resin_btn.clicked.connect(self._remove_selected_resin)
        self.ui.add_output_log_btn.clicked.connect(self._add_output_log_row)
        self.ui.remove_output_log_btn.clicked.connect(self._remove_selected_output_log)
        self.ui.purging_details_table.cellChanged.connect(self._update_production_summary)
        self.ui.output_log_table.cellChanged.connect(self._update_production_summary)
        self.ui.qty_order_input.textChanged.connect(self._update_production_summary)
        self.ui.save_button.clicked.connect(self._save_form_data)
        self.ui.clear_button.clicked.connect(self._clear_form)

        self.ui.purging_product_code_combo.full_search_requested.connect(self._on_product_code_search_requested)

    def _calculate_purging_time_used(self):
        """Calculates and displays the duration between purging start and end times."""
        start_time = self.ui.purging_start_time.time()
        end_time = self.ui.purging_end_time.time()

        # secsTo handles the difference, but we must account for overnight shifts
        total_seconds = start_time.secsTo(end_time)
        if total_seconds < 0:
            # If negative, it means the end time is on the next day
            total_seconds += 86400  # Seconds in a 24-hour day

        # Convert total seconds into hours and minutes
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60

        # Format as HH:MM and update the label
        duration_text = f"{hours:02d}:{minutes:02d}"
        self.ui.purging_time_used_label.setText(duration_text)

    # def _initial_load(self):
    #     try:
    #         self.employee_list = self.controller.get_all_employees()
    #         self.position_list = self.controller.get_all_positions()
    #         self.ui.prepared_by_combo.addItem("- Select -", None)
    #         self.ui.operator_combo.addItem("- Select -", None)
    #         for emp in self.employee_list:
    #             full_name = f"{emp.first_name} {emp.last_name}"
    #             self.ui.prepared_by_combo.addItem(full_name, emp.id)
    #             self.ui.operator_combo.addItem(full_name, emp.id)
    #         self.ui.position_combo.addItem("- Select -", None)
    #
    #
    #
    #         for pos in self.position_list:
    #             self.ui.position_combo.addItem(pos.name, pos.id)
    #         self.ui.shift_combo.addItems(["- Select -", "1st Shift", "2nd Shift", "3rd Shift"])
    #         machines = self.controller.get_all_machines()
    #         self.ui.mc_no_combo.addItem("- Select -", None)
    #         for m in machines: self.ui.mc_no_combo.addItem(m.name, m.id)
    #         screen_sizes = self.controller.get_all_screen_sizes()
    #         self.ui.screen_size_combo.addItem("- Select -", None)
    #         for s in screen_sizes: self.ui.screen_size_combo.addItem(s.size, s.id)
    #
    #
    #
    #         # --- FIX: Populate Shift from the database ---
    #         self.ui.shift_combo.clear() # Clear any existing items
    #         shifts = self.controller.get_all_shifts()
    #         self.ui.shift_combo.addItem("- Select -", None)
    #         for s in shifts:
    #             self.ui.shift_combo.addItem(s.name, s.id)
    #
    #         # --- FIX: Populate Screw Config from the database ---
    #         self.ui.screw_config_combo.clear() # Clear any existing items
    #         screw_configs = self.controller.get_all_screw_configs()
    #         self.ui.screw_config_combo.addItem("- Select -", None)
    #         for sc in screw_configs:
    #             self.ui.screw_config_combo.addItem(sc.name, sc.id)
    #
    #         # --- Purging & Resin Data ---
    #         self.resin_list = self.controller.get_all_resins()
    #         self.ui.purging_resin_combo.addItem("- Select -", None)
    #         for r in self.resin_list:
    #             self.ui.purging_resin_combo.addItem(r.abbreviation, r.id)
    #
    #         self.ui.purging_product_code_combo.set_data_fetcher(
    #             self.controller.get_distinct_product_codes_paginated
    #         )
    #         self.ui.purging_product_code_combo.load_initial_data()
    #
    #
    #         zones = self.controller.get_all_zones()
    #         self.zone_mapping = {zone.name: zone.id for zone in zones}
    #
    #         self.ui.no_purging_checkbox.setChecked(False)
    #         self._on_no_purging_toggled(False)
    #     except Exception as e:
    #         QMessageBox.critical(self, "Database Error", f"Could not load initial data: {e}")

    # --- NEW DYNAMIC PERSONNEL METHODS ---

    def _initial_load(self):
        """
        Loads all necessary data from the database to populate the form's combo boxes.
        """
        try:
            # --- FIX: Load data for dynamic personnel and filtered "Prepared By" ---
            # 1. Fetch the list of encoders for the "Prepared By" combo box.
            encoders = self.controller.get_all_encoders()
            self.ui.prepared_by_combo.clear()
            self.ui.prepared_by_combo.addItem("")  # Start with a blank, editable entry
            for encoder in encoders:
                self.ui.prepared_by_combo.addItem(encoder.nickname, encoder.id)

            # 2. Fetch the full lists needed for the dynamic personnel rows.
            self.employee_list = self.controller.get_all_employees()
            self.position_list = self.controller.get_all_positions()
            # The old logic for operator_combo and position_combo is now removed.

            # --- Machine and Config Data ---
            self.ui.shift_combo.clear()
            shifts = self.controller.get_all_shifts()
            self.ui.shift_combo.addItem("- Select -", None)
            for s in shifts:
                self.ui.shift_combo.addItem(s.name, s.id)

            machines = self.controller.get_all_machines()
            self.ui.mc_no_combo.addItem("- Select -", None)
            for m in machines: self.ui.mc_no_combo.addItem(m.name, m.id)

            screen_sizes = self.controller.get_all_screen_sizes()
            self.ui.screen_size_combo.addItem("- Select -", None)
            for s in screen_sizes: self.ui.screen_size_combo.addItem(s.size, s.id)

            self.ui.screw_config_combo.clear()
            screw_configs = self.controller.get_all_screw_configs()
            self.ui.screw_config_combo.addItem("- Select -", None)
            for sc in screw_configs:
                self.ui.screw_config_combo.addItem(sc.name, sc.id)

            # --- Purging & Resin Data ---
            self.resin_list = self.controller.get_all_resins()
            self.ui.purging_resin_combo.addItem("- Select -", None)
            for r in self.resin_list:
                self.ui.purging_resin_combo.addItem(r.abbreviation, r.id)

            # --- THIS IS THE FIX ---
            # 1. Fetch the initial list of product codes.
            initial_codes = self.controller.get_distinct_product_codes_paginated(page=1, page_size=1000, limit=1000)

            # 2. Use the correct method 'populate_initial' to load the data.
            self.ui.purging_product_code_combo.populate_initial(initial_codes)

            zones = self.controller.get_all_zones()
            self.zone_mapping = {zone.name: zone.id for zone in zones}

            self.ui.no_purging_checkbox.setChecked(False)
            self._on_no_purging_toggled(False)

        #     ADD INITIAL ROW FOR PERSONNEL
            self._add_personnel_row()
        except Exception as e:
            # --- FIX: Use the new ErrorDialog ---
            error_dialog = ErrorDialog(
                title="Database Error",
                message="Could not load the initial data required for the form.",
                details=traceback.format_exc(),
                parent=self
            )
            error_dialog.exec()

    def _on_product_code_search_requested(self, search_term: str):
        try:
            # Fetch search results from the database
            results = self.controller.get_distinct_product_codes_paginated(
                page=1,
                page_size=50, # Limit server-side results
                search_term=search_term
            )
            # Push the results back into the combo box
            self.ui.purging_product_code_combo.update_with_search_results(results)
        except Exception as e:
            print(f"Error during product code search: {e}")



    def _add_personnel_row(self):
        """Dynamically creates and adds a new row for personnel entry."""
        # Create a container widget and a horizontal layout for the row
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        # Create Name ComboBox
        name_combo = QComboBox()
        name_combo.setEditable(True)
        name_combo.addItem("- Select Name -", None)
        for emp in self.employee_list:
            name_combo.addItem(f"{emp.first_name} {emp.last_name}", emp.id)

        # Create Position ComboBox
        pos_combo = QComboBox()
        pos_combo.setEditable(True)
        pos_combo.addItem("- Select Position -", None)
        for pos in self.position_list:
            pos_combo.addItem(pos.name, pos.id)

        pos_combo.model().item(0).setEnabled(False)
        name_combo.model().item(0).setEnabled(False)

        row_layout.addWidget(name_combo)
        row_layout.addWidget(pos_combo)

        # Add the new row widget to our container layout
        self.ui.personnel_container_layout.addWidget(row_widget)

    def _remove_personnel_row(self):
        """Removes the last added personnel row."""
        layout = self.ui.personnel_container_layout
        count = layout.count()
        if count > 0:
            # Get the widget at the last index
            widget_to_remove = layout.itemAt(count - 1).widget()
            if widget_to_remove:
                # Remove it from the layout and schedule it for deletion
                widget_to_remove.setParent(None)
                widget_to_remove.deleteLater()



    # --- NEW METHOD with INVERTED LOGIC ---
    def _on_no_purging_toggled(self, checked: bool):
        """
        Enables or disables the Purging and Resin Consumption group boxes,
        and correctly clears or reloads data.
        """
        is_enabled = not checked
        self.ui.purging_group.setEnabled(is_enabled)
        self.ui.resin_group.setEnabled(is_enabled)

        if is_enabled:
            # --- THIS IS THE FIX ---
            # When the section is RE-ENABLED, we need to re-populate the
            # initial list of items in the SmartComboBox.
            try:
                initial_codes = self.controller.get_distinct_product_codes_paginated(page=1, page_size=1000, limit=1000)
                self.ui.purging_product_code_combo.populate_initial(initial_codes)
            except Exception as e:
                error_dialog = ErrorDialog("Load Error", "Could not reload product codes.",
                                           details=traceback.format_exc(), parent=self)
                error_dialog.exec()
        else:
            # When the section is DISABLED, clear everything
            self.ui.purging_product_code_combo.clear()
            self.ui.purging_resin_combo.setCurrentIndex(0)
            self.ui.purging_palletizer_input.setText("0")
            self.ui.purging_siever_input.setText("0")
            self.ui.purging_start_time.setTime(QTime(0, 0))
            self.ui.purging_end_time.setTime(QTime(0, 0))
            self.ui.purging_details_table.setRowCount(0)
            self.ui.purging_time_used_label.setText("00:00")


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
            # --- FIX: Use the new ErrorDialog ---
            error_dialog = ErrorDialog(
                title="Dialog Error",
                message="An unexpected error occurred while trying to open the lot number selector.",
                details=traceback.format_exc(),
                parent=self
            )
            error_dialog.exec()

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
            # --- FIX: Use the new ErrorDialog ---
            error_dialog = ErrorDialog(
                title="Calculation Error",
                message="Could not set the quantity values after selecting a lot.",
                details=traceback.format_exc(),
                parent=self
            )
            error_dialog.exec()

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
        """Adds a new row to the Resin Consumption (Purging Details) table."""
        # --- FIX: Use the correct widget name ---
        table = self.ui.purging_details_table
        row_position = table.rowCount()
        table.insertRow(row_position)

        resin_combo = QComboBox()
        resin_combo.addItem("- Select -", None)
        for resin in self.resin_list:
            resin_combo.addItem(resin.abbreviation, resin.id)

        notes_item = QTableWidgetItem("")
        qty_item = QTableWidgetItem("0.00")

        table.setCellWidget(row_position, 0, resin_combo)
        table.setItem(row_position, 1, notes_item)
        table.setItem(row_position, 2, qty_item)

    def _remove_selected_resin(self):
        """Removes the selected row from the Resin Consumption table."""
        # --- FIX: Use the correct widget name ---
        table = self.ui.purging_details_table
        current_row = table.currentRow()
        if current_row >= 0:
            table.removeRow(current_row)

    def _add_output_log_row(self):
        row_position = self.ui.output_log_table.rowCount()
        self.ui.output_log_table.insertRow(row_position)

        date_edit = SmartDateEdit()
        time_start_edit = QTimeEdit(QTime(0, 0))
        time_start_edit.setDisplayFormat("HH:mm")
        time_end_edit = QTimeEdit(QTime(0, 0))
        time_end_edit.setDisplayFormat("HH:mm")
        time_end_edit.installEventFilter(self)

        time_used_item = QTableWidgetItem("00:00")
        time_used_item.setFlags(time_used_item.flags() & ~Qt.ItemFlag.ItemIsEditable)

        self.ui.output_log_table.setCellWidget(row_position, 0, date_edit)
        self.ui.output_log_table.setCellWidget(row_position, 1, time_start_edit)
        self.ui.output_log_table.setCellWidget(row_position, 2, time_end_edit)
        self.ui.output_log_table.setItem(row_position, 3, time_used_item)
        self.ui.output_log_table.setItem(row_position, 4, QTableWidgetItem("0.00"))

        # --- FIX: Connect all three widgets to the new calculation logic ---
        date_edit.dateChanged.connect(lambda date, r=row_position: self._calculate_output_log_time_used(r))
        time_start_edit.timeChanged.connect(lambda time, r=row_position: self._calculate_output_log_time_used(r))
        time_end_edit.timeChanged.connect(lambda time, r=row_position: self._calculate_output_log_time_used(r))

        # Manually trigger a calculation to set initial "00:00" state
        self._calculate_output_log_time_used(row_position)


    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        Catches Tab key presses on the 'Time End' widgets to manually
        move focus to the 'Output (kg)' cell.
        """
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            # Check if the object sending the event is a QTimeEdit in our table
            if isinstance(obj, QTimeEdit):
                # Find which row this widget belongs to
                for row in range(self.ui.output_log_table.rowCount()):
                    if self.ui.output_log_table.cellWidget(row, 2) is obj:
                        # We found our widget in the "Time End" column (2)
                        # Now, get the item in the "Output (kg)" column (4)
                        target_item = self.ui.output_log_table.item(row, 4)
                        if target_item:
                            # Set the current item to start editing
                            self.ui.output_log_table.setCurrentItem(target_item)
                            self.ui.output_log_table.editItem(target_item)
                        return True  # Event was handled, stop further processing

        # For all other events, pass them to the default handler
        return super().eventFilter(obj, event)

    def _calculate_output_log_time_used(self, row: int):
        """
        Calculates the duration for a row in the output log, correctly
        handling overnight shifts for the end date.
        """
        try:
            date_widget = self.ui.output_log_table.cellWidget(row, 0)
            start_widget = self.ui.output_log_table.cellWidget(row, 1)
            end_widget = self.ui.output_log_table.cellWidget(row, 2)
            time_used_item = self.ui.output_log_table.item(row, 3)

            if not all([date_widget, start_widget, end_widget, time_used_item]):
                return

            start_qdate = date_widget.date()
            start_qtime = start_widget.time()
            end_qtime = end_widget.time()

            if start_qdate.isNull():
                time_used_item.setText("00:00")
                return  # Can't calculate without a start date

            # --- THIS IS THE NEW LOGIC ---
            # Convert to Python types
            start_date = start_qdate.toPyDate()
            start_time = start_qtime.toPyTime()
            end_time = end_qtime.toPyTime()

            # 1. Construct the start datetime
            datetime_start = datetime.combine(start_date, start_time)

            # 2. Determine the end date based on the overnight rule
            end_date = start_date
            if end_time <= start_time:
                end_date += timedelta(days=1)

            # 3. Construct the end datetime
            datetime_end = datetime.combine(end_date, end_time)

            # 4. Calculate the duration
            duration = datetime_end - datetime_start
            total_seconds = duration.total_seconds()

            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)

            time_used_item.setText(f"{hours:02d}:{minutes:02d}")

        except Exception as e:
            print(f"Error calculating time used for row {row}: {e}")


    def _remove_selected_output_log(self):
        current_row = self.ui.output_log_table.currentRow()
        if current_row >= 0:
            self.ui.output_log_table.removeRow(current_row)



    # def _update_production_summary(self):
    #     try:
    #         total_output = Decimal("0.00")
    #         # --- NEW: Initialize total minutes for summing ---
    #         total_minutes_used = 0
    #
    #         # 1. Loop through the output log to sum output AND time
    #         for row in range(self.ui.output_log_table.rowCount()):
    #             output_item = self.ui.output_log_table.item(row, 4)
    #             if output_item:
    #                 total_output += Decimal(output_item.text() or '0')
    #
    #             # --- NEW: Parse and sum the "Time Used" column ---
    #             time_used_item = self.ui.output_log_table.item(row, 3)
    #             if time_used_item:
    #                 time_parts = time_used_item.text().split(':')
    #                 if len(time_parts) == 2:
    #                     hours = int(time_parts[0])
    #                     minutes = int(time_parts[1])
    #                     total_minutes_used += (hours * 60) + minutes
    #
    #         self.ui.total_output_label.setText(f"{total_output:.2f} KG")
    #
    #         # --- NEW: Format the total minutes and update the label ---
    #         total_hours = total_minutes_used // 60
    #         remaining_minutes = total_minutes_used % 60
    #         self.ui.total_time_used_label.setText(f"{total_hours:02d}:{remaining_minutes:02d}")
    #
    #         # 2. Continue with other calculations
    #         qty_produced_input = Decimal(self.ui.qty_produced_input.text() or '0')
    #         total_diff = total_output - qty_produced_input
    #
    #         if total_diff < 0:
    #             self.ui.loss_label.setText(f"{abs(total_diff):.2f} KG")
    #             self.ui.gain_label.setText("0.00 KG")
    #         else:
    #             self.ui.loss_label.setText("0.00 KG")
    #             self.ui.gain_label.setText(f"{total_diff:.2f} KG")
    #
    #         total_resin = Decimal("0.00")
    #         for row in range(self.ui.purging_details_table.rowCount()):
    #             qty_item = self.ui.purging_details_table.item(row, 2)
    #             if qty_item:
    #                 total_resin += Decimal(qty_item.text() or '0')
    #         self.ui.resin_qty_label.setText(f"{total_resin:.2f} KG")
    #
    #         output_percent = (total_output / qty_produced_input * 100) if qty_produced_input > 0 else Decimal("0.00")
    #         self.ui.output_percent_label.setText(f"{output_percent:.2f} %")
    #
    #         percent_diff = Decimal("0.00")
    #         if qty_produced_input > 0:
    #             percent_diff = (total_diff / qty_produced_input * 100)
    #
    #         if percent_diff < 0:
    #             self.ui.loss_percent_label.setText(f"{abs(percent_diff):.2f} %")
    #             self.ui.gain_percent_label.setText("0.00 %")
    #         else:
    #             self.ui.loss_percent_label.setText("0.00 %")
    #             self.ui.gain_percent_label.setText(f"{percent_diff:.2f} %")
    #
    #     except (InvalidOperation, TypeError, ValueError):
    #         # Added ValueError to safely handle potential int conversion errors
    #         pass

    def _update_production_summary(self):
        try:
            total_output = Decimal("0.00")
            total_minutes_used = 0

            # 1. Sum total output and total minutes from the log table
            for row in range(self.ui.output_log_table.rowCount()):
                output_item = self.ui.output_log_table.item(row, 4)
                if output_item:
                    total_output += Decimal(output_item.text() or '0')

                time_used_item = self.ui.output_log_table.item(row, 3)
                if time_used_item:
                    time_parts = time_used_item.text().split(':')
                    if len(time_parts) == 2:
                        hours = int(time_parts[0])
                        minutes = int(time_parts[1])
                        total_minutes_used += (hours * 60) + minutes

            # Update the display for Total Output and Total Time
            self.ui.total_output_label.setText(f"{total_output:.2f} KG")
            total_hours = total_minutes_used // 60
            remaining_minutes = total_minutes_used % 60
            self.ui.total_time_used_label.setText(f"{total_hours:02d}:{remaining_minutes:02d}")

            # --- THIS IS THE FIX ---
            # 2. Calculate Output per Hour
            output_per_hour = Decimal("0.00")
            if total_minutes_used > 0:
                # Convert total minutes to decimal hours
                total_hours_decimal = Decimal(total_minutes_used) / Decimal(60)
                # Calculate the rate
                output_per_hour = total_output / total_hours_decimal

            # 3. Update the label with the decimal value
            self.ui.output_per_hour_label.setText(f"{output_per_hour:.2f} KG/HR")
            # --- END FIX ---

            # 4. Continue with other calculations (Loss, Gain, Percentages)
            qty_produced_input = Decimal(self.ui.qty_produced_input.text() or '0')
            total_diff = total_output - qty_produced_input

            if total_diff < 0:
                self.ui.loss_label.setText(f"{abs(total_diff):.2f} KG")
                self.ui.gain_label.setText("0.00 KG")
            else:
                self.ui.loss_label.setText("0.00 KG")
                self.ui.gain_label.setText(f"{total_diff:.2f} KG")

            total_resin = Decimal("0.00")
            for row in range(self.ui.purging_details_table.rowCount()):
                qty_item = self.ui.purging_details_table.item(row, 2)
                if qty_item:
                    total_resin += Decimal(qty_item.text() or '0')
            self.ui.resin_qty_label.setText(f"{total_resin:.2f} KG")

            output_percent = (total_output / qty_produced_input * 100) if qty_produced_input > 0 else Decimal("0.00")
            self.ui.output_percent_label.setText(f"{output_percent:.2f} %")

            percent_diff = Decimal("0.00")
            if qty_produced_input > 0:
                percent_diff = (total_diff / qty_produced_input * 100)

            if percent_diff < 0:
                self.ui.loss_percent_label.setText(f"{abs(percent_diff):.2f} %")
                self.ui.gain_percent_label.setText("0.00 %")
            else:
                self.ui.loss_percent_label.setText("0.00 %")
                self.ui.gain_percent_label.setText(f"{percent_diff:.2f} %")

        except (InvalidOperation, TypeError, ValueError):
            pass


    def _clear_form(self):
        # Clear main form fields
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

        # Clear machine config fields
        self.ui.shift_combo.setCurrentIndex(0)
        self.ui.mc_no_combo.setCurrentIndex(0)
        self.ui.feed_rate_input.setText("0")
        self.ui.rpm_input.setText("0")
        self.ui.screen_size_combo.setCurrentIndex(0)
        self.ui.screw_config_combo.setCurrentIndex(0)
        self.ui.is_vacuum_on_checkbox.setChecked(False)

        # --- THIS IS THE FIX ---
        # 1. Do NOT touch the 'no_purging_checkbox'.

        # 2. Explicitly clear and reload the product code combo.
        initial_codes = self.controller.get_distinct_product_codes_paginated(page=1, page_size=1000, limit=1000)
        self.ui.purging_product_code_combo.populate_initial(initial_codes)

        # 3. Clear the other purging fields.
        self.ui.purging_resin_combo.setCurrentIndex(0)
        self.ui.purging_palletizer_input.setText("0")
        self.ui.purging_siever_input.setText("0")
        self.ui.purging_start_time.setTime(QTime(0, 0))
        self.ui.purging_end_time.setTime(QTime(0, 0))
        # --- END FIX ---

        # Clear tables and other fields
        self.ui.purging_details_table.setRowCount(0)
        self.ui.output_log_table.setRowCount(0)
        for widget in self.ui.zone_inputs.values():
            widget.setText("0")
        self.ui.remarks_input.clear()

        while self.ui.personnel_container_layout.count() > 0:
            self._remove_personnel_row()

        self.ui.prepared_by_combo.setCurrentIndex(0)
        self._add_personnel_row()


        # Update summary calculations
        self._update_production_summary()

        QMessageBox.information(self, "Cleared", "Form has been cleared.")


    # def _gather_data_from_ui(self) -> dict:
    #     prod_id_str = "; ".join(sorted([item for item in self.aggregated_prod_ids if item]))
    #     formula_no_str = "; ".join(sorted([item for item in self.aggregated_formula_ids if item]))
    #     order_no_str = "; ".join(sorted([item for item in self.aggregated_order_nos if item]))
    #     def get_table_cell_data(table, row, col):
    #         widget = table.cellWidget(row, col)
    #         if isinstance(widget, QComboBox): return widget.currentData(), widget.currentText()
    #         item = table.item(row, col)
    #         return (item.text() if item else None), None
    #     data = {
    #         "main": { "lot_number": self.ui.lot_number_input.text(), "production_id": prod_id_str, "formula_no": formula_no_str, "order_no": order_no_str, "product_code": self.ui.product_code_input.text(), "customer": self.ui.customer_input.text(), "qty_order": self.ui.qty_order_input.text(), "prepared_by_id": self.ui.prepared_by_combo.currentData(), "prepared_by_name": self.ui.prepared_by_combo.currentText(), "machine_id": self.ui.mc_no_combo.currentData(),
    #         # --- FIX: Add shift_id to the data being saved ---
    #         "shift_id": self.ui.shift_combo.currentData()
    #         },
    #         "machine_details": {
    #             "screw_config": self.ui.screw_config_combo.currentText(),
    #             "feed_rate": self.ui.feed_rate_input.text(),
    #             "rpm": self.ui.rpm_input.text(),
    #             "screen_size_id": self.ui.screen_size_combo.currentData(),
    #             # --- NEW: Get the boolean value from the checkbox ---
    #             "is_vacuum_on": self.ui.is_vacuum_on_checkbox.isChecked()
    #         },
    #         "purging": {
    #             # "product_code_id": self.ui.purging_product_code_combo.currentData(),
    #             "product_code_name": self.ui.purging_product_code_combo.currentText(),
    #             "start_time": self.ui.purging_start_time.time().toPyTime(),
    #             "end_time": self.ui.purging_end_time.time().toPyTime(),
    #             "resin_id": self.ui.purging_resin_combo.currentData(),
    #             "palletizer": self.ui.purging_palletizer_input.text(),
    #             "siever": self.ui.purging_siever_input.text(),
    #         },
    #         "resin_consumption": [ { "resin_id": get_table_cell_data(self.ui.resin_table, r, 0)[0], "resin_name": get_table_cell_data(self.ui.resin_table, r, 0)[1], "qty": get_table_cell_data(self.ui.resin_table, r, 1)[0] } for r in range(self.ui.resin_table.rowCount()) ],
    #         "output_log": [ { "date": self.ui.output_log_table.cellWidget(r, 0).date().toPyDate(), "time_start": self.ui.output_log_table.cellWidget(r, 1).time().toPyTime(), "time_end": self.ui.output_log_table.cellWidget(r, 2).time().toPyTime(), "output": get_table_cell_data(self.ui.output_log_table, r, 3)[0], "loss": get_table_cell_data(self.ui.output_log_table, r, 4)[0], } for r in range(self.ui.output_log_table.rowCount()) ],
    #         "zone_temps": {name: widget.text() for name, widget in self.ui.zone_inputs.items()},
    #         "personnel": [{"employee_id": self.ui.operator_combo.currentData(), "position_id": self.ui.position_combo.currentData()}],
    #         "summary": { "resin_qty_total": Decimal(self.ui.resin_qty_label.text().replace(" KG", "")) }
    #     }
    #
    #     personnel_list = []
    #     layout = self.ui.personnel_container_layout
    #     for i in range(layout.count()):
    #         row_widget = layout.itemAt(i).widget()
    #         if row_widget:
    #             # Find the QComboBoxes within the row widget
    #             name_combo = row_widget.findChild(QComboBox)
    #             pos_combo = row_widget.findChildren(QComboBox)[1] # Second combobox
    #
    #             # Only add if a valid employee is selected
    #             if name_combo.currentData() is not None:
    #                 personnel_list.append({
    #                     "employee_id": name_combo.currentData(),
    #                     "position_id": pos_combo.currentData()
    #                 })
    #     data["personnel"] = personnel_list
    #
    #
    #
    #     if not self.ui.no_purging_checkbox.isChecked():
    #         data["purging"] = {
    #             "product_code_name": self.ui.purging_product_code_combo.currentText(),
    #             "start_time": self.ui.purging_start_time.time().toPyTime(),
    #             "end_time": self.ui.purging_end_time.time().toPyTime(),
    #             "resin_id": self.ui.purging_resin_combo.currentData(),
    #             "palletizer": self.ui.purging_palletizer_input.text(),
    #             "siever": self.ui.purging_siever_input.text(),
    #         }
    #         data["resin_consumption"] = [
    #             {
    #                 "resin_id": get_table_cell_data(self.ui.resin_table, r, 0)[0],
    #                 "resin_name": get_table_cell_data(self.ui.resin_table, r, 0)[1],
    #                 "qty": get_table_cell_data(self.ui.resin_table, r, 1)[0]
    #             } for r in range(self.ui.resin_table.rowCount())
    #         ]
    #
    #     return data

    def _gather_data_from_ui(self) -> dict:
        """
        Gathers all data from the UI into a structured dictionary, ready for saving.
        """
        prod_id_str = "; ".join(sorted([item for item in self.aggregated_prod_ids if item]))
        formula_no_str = "; ".join(sorted([item for item in self.aggregated_formula_ids if item]))
        order_no_str = "; ".join(sorted([item for item in self.aggregated_order_nos if item]))

        # --- FIX: This logic is now moved into a dedicated block ---
        output_log_list = []
        for r in range(self.ui.output_log_table.rowCount()):
            date_widget = self.ui.output_log_table.cellWidget(r, 0)
            start_time_widget = self.ui.output_log_table.cellWidget(r, 1)
            end_time_widget = self.ui.output_log_table.cellWidget(r, 2)
            output_item = self.ui.output_log_table.item(r, 4)

            if not all([date_widget, start_time_widget, end_time_widget, output_item]) or date_widget.date().isNull():
                continue

            start_date = date_widget.date().toPyDate()
            start_time = start_time_widget.time().toPyTime()
            end_time = end_time_widget.time().toPyTime()

            datetime_start = datetime.combine(start_date, start_time)
            end_date = start_date
            if end_time <= start_time:
                end_date += timedelta(days=1)
            datetime_end = datetime.combine(end_date, end_time)

            output_log_list.append({
                "datetime_start": datetime_start,
                "datetime_end": datetime_end,
                "output": output_item.text(),
            })


        data = {
            "main": {
                "lot_number": self.ui.lot_number_input.text(),
                "production_id": prod_id_str,
                "formula_no": formula_no_str,
                "order_no": order_no_str,
                "product_code": self.ui.product_code_input.text(),
                "customer": self.ui.customer_input.text(),
                "qty_order": self.ui.qty_order_input.text(),
                "qty_produced": self.ui.qty_produced_input.text(),
                "target_output_per_hour": self.ui.target_output_hr_input.text(),
                "prepared_by_name": self.ui.prepared_by_combo.currentText(),
                "machine_id": self.ui.mc_no_combo.currentData(),
                "shift_id": self.ui.shift_combo.currentData()
            },
            "machine_details": {
                "screw_config_id": self.ui.screw_config_combo.currentData(),
                "feed_rate": self.ui.feed_rate_input.text(),
                "rpm": self.ui.rpm_input.text(),
                "screen_size_id": self.ui.screen_size_combo.currentData(),
                "is_vacuum_on": self.ui.is_vacuum_on_checkbox.isChecked()
            },
            "output_log": output_log_list,
            "zone_temps": {name: widget.text() for name, widget in self.ui.zone_inputs.items()},
            "remarks": self.ui.remarks_input.toPlainText()
        }

        # Conditionally add purging and personnel data
        personnel_list = []
        layout = self.ui.personnel_container_layout
        for i in range(layout.count()):
            row_widget = layout.itemAt(i).widget()
            if row_widget:
                name_combo = row_widget.findChild(QComboBox)
                pos_combo = row_widget.findChildren(QComboBox)[1]
                if name_combo.currentData() is not None:
                    personnel_list.append({
                        "employee_id": name_combo.currentData(),
                        "position_id": pos_combo.currentData()
                    })
        data["personnel"] = personnel_list

        if not self.ui.no_purging_checkbox.isChecked():
            data["purging_header"] = {
                "product_code_name": self.ui.purging_product_code_combo.text(),
                "start_time": self.ui.purging_start_time.time().toPyTime(),
                "end_time": self.ui.purging_end_time.time().toPyTime(),
                "resin_id": self.ui.purging_resin_combo.currentData(),
                "palletizer": self.ui.purging_palletizer_input.text(),
                "siever": self.ui.purging_siever_input.text(),
            }
            data["purging_details"] = [
                {
                    "resin_id": self.ui.purging_details_table.cellWidget(r, 0).currentData(),
                    "notes": self.ui.purging_details_table.item(r, 1).text().strip(),
                    "qty": self.ui.purging_details_table.item(r, 2).text()
                } for r in range(self.ui.purging_details_table.rowCount())
            ]

        return data

    def _validate_required_fields(self) -> bool:
        """
        Checks all required fields and business rules, grouping errors by section.
        Returns True if valid, False otherwise (and shows a message).
        """
        # --- FIX: Define fields in a structured dictionary by group ---
        validation_map = {
            "Production Details": [
                (self.ui.lot_number_input, "Lot Number"),
                (self.ui.product_code_input, "Product Code"),
                (self.ui.customer_input, "Customer"),
                (self.ui.qty_order_input, "QTY Order (kg)"),
                (self.ui.qty_produced_input, "QTY Produced (kg)"),
                (self.ui.target_output_hr_input, "Targer Output per Hour (Kg/Hr)"),

            ],
            "Machine & Configuration": [
                (self.ui.shift_combo, "Shift"),
                (self.ui.mc_no_combo, "MC No."),
                (self.ui.feed_rate_input, "Feed Rate"),
                (self.ui.rpm_input, "RPM"),
                (self.ui.screen_size_combo, "Screen Size"),
                (self.ui.screw_config_combo, "Screw Config."),
            ],
            "Personnel": [
                (self.ui.prepared_by_combo, "Prepared By"),

            ]
        }

        if not self.ui.no_purging_checkbox.isChecked():
            validation_map["Purging Details"] = [
                (self.ui.purging_product_code_combo, "Product Code"),
                (self.ui.purging_resin_combo, "Resin"),
                (self.ui.purging_palletizer_input, "Pelletizer"),
                (self.ui.purging_siever_input, "Siever"),
            ]

        missing_issues = []
        for group_name, fields in validation_map.items():
            group_errors = []
            for widget, field_name in fields:
                is_missing = False
                if isinstance(widget, QLineEdit):
                    if (widget.text().strip() in ('', '0', '0.00')):
                        is_missing = True
                elif isinstance(widget, QComboBox):
                    if widget.isEditable():
                        if not widget.currentText().strip():
                            is_missing = True
                    elif widget.currentIndex() <= 0:
                        is_missing = True

                if is_missing:
                    group_errors.append(field_name)

            if group_errors:
                missing_issues.append(
                    f"<b>{group_name}:</b><ul>{''.join(f'<li>{err}</li>' for err in group_errors)}</ul>")

        # --- Check dynamic/custom rules ---
        custom_rules_errors = []
        if self.ui.personnel_container_layout.count() == 0:
            custom_rules_errors.append("At least one Personnel must be added.")
        if self.ui.output_log_table.rowCount() == 0:
            custom_rules_errors.append("At least one Extruder Output Log entry is required.")
        all_zones_zero = all(int(z.text() or 0) == 0 for z in self.ui.zone_inputs.values())
        if all_zones_zero:
            custom_rules_errors.append("All Zone Temperatures cannot be zero.")

        # --- THIS IS THE FIX: The incorrect time validation block has been removed. ---
        # The logic to check if end_time <= start_time is no longer here.
        # The "Time Used" calculation already handles the overnight logic correctly.

        if custom_rules_errors:
            missing_issues.append(
                f"<b>Other Issues:</b><ul>{''.join(f'<li>{err}</li>' for err in custom_rules_errors)}</ul>")

        # --- Final Check ---
        if missing_issues:
            final_issue_list_html = "<br>".join(missing_issues)
            error_dialog = ErrorDialog(
                title="Validation Error",
                message=f"Please correct the following issues before saving:<br>{final_issue_list_html}",
                parent=self
            )
            error_dialog.exec()
            return False

        return True



    def _save_form_data(self):
        # --- FIX: Only call the one comprehensive validation method ---
        if not self._validate_required_fields():
            return

        form_data = self._gather_data_from_ui()
        try:
            self.controller.save_full_form(form_data, self.zone_mapping)
            success_dialog = SuccessDialog("Save Successful", "The extruder form data has been saved.", parent=self)
            success_dialog.exec()
            self._clear_form()
        except Exception as e:
            error_dialog = ErrorDialog("Save Error", "Could not save the form data.", details=traceback.format_exc(), parent=self)
            error_dialog.exec()