# app/views/extruder_form/entry_form/main.py
import os
import traceback
from datetime import datetime, timedelta

from PyQt6.QtCore import QDate, QTime, Qt, QEvent, QObject, pyqtSignal
from PyQt6.QtGui import QShortcut, QKeySequence
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
    data_saved = pyqtSignal()

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
        self.edit_record_id = None

        # --- FIX: Restore the shortcut setup ---
        self._setup_shortcuts()

        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f: self.setStyleSheet(f.read())

    # --- NEW: Method to create shortcuts ---
    def _setup_shortcuts(self):
        """Creates and connects keyboard shortcuts for the form."""
        add_shortcut = QShortcut(QKeySequence("Shift+Return"), self)
        add_shortcut.activated.connect(self._on_add_row_shortcut)

        add_shortcut_enter = QShortcut(QKeySequence("Shift+Enter"), self)
        add_shortcut_enter.activated.connect(self._on_add_row_shortcut)

        delete_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        delete_shortcut.activated.connect(self._on_delete_shortcut)

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

        # --- NEW: Connect the custom signals from our new tables ---
        self.ui.output_log_table.tabbed_out_of_last_cell.connect(
            lambda: self.ui.no_purging_checkbox.setFocus()
        )
        self.ui.purging_details_table.tabbed_out_of_last_cell.connect(
            lambda: self.ui.remarks_input.setFocus()
        )

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


    def _initial_load(self):
        try:
            # --- Install event filter for keyboard shortcuts ---
            self.ui.output_log_table.viewport().installEventFilter(self)
            self.ui.purging_details_table.viewport().installEventFilter(self)

            encoders = self.controller.get_all_encoders()
            self.ui.prepared_by_combo.clear()
            self.ui.prepared_by_combo.addItem("")
            for encoder in encoders:
                self.ui.prepared_by_combo.addItem(encoder.nickname, encoder.id)

            self.employee_list = self.controller.get_all_employees()
            self.position_list = self.controller.get_all_positions()

            self.ui.shift_combo.clear()
            shifts = self.controller.get_all_shifts()
            self.ui.shift_combo.addItem("- Select -", None)
            for s in shifts:
                self.ui.shift_combo.addItem(s.name, s.id)

            # ... (rest of initial load is correct)
            machines = self.controller.get_all_machines()
            self.ui.mc_no_combo.addItem("- Select -", None)
            for m in machines: self.ui.mc_no_combo.addItem(m.name, m.id)
            screen_sizes = self.controller.get_all_screen_sizes()
            self.ui.screen_size_combo.addItem("- Select -", None)
            for s in screen_sizes: self.ui.screen_size_combo.addItem(s.size, s.id)
            screw_configs = self.controller.get_all_screw_configs()
            self.ui.screw_config_combo.addItem("- Select -", None)
            for sc in screw_configs: self.ui.screw_config_combo.addItem(sc.name, sc.id)
            self.resin_list = self.controller.get_all_resins()
            self.ui.purging_resin_combo.addItem("- Select -", None)
            for r in self.resin_list:
                self.ui.purging_resin_combo.addItem(r.abbreviation, r.id)
            initial_codes = self.controller.get_distinct_product_codes_paginated(page=1, page_size=1000, limit=1000)
            self.ui.purging_product_code_combo.populate_initial(initial_codes)
            zones = self.controller.get_all_zones()
            self.zone_mapping = {zone.name: zone.id for zone in zones}
            self.ui.no_purging_checkbox.setChecked(False)
            self._on_no_purging_toggled(False)
            self._add_personnel_row()
            self._add_output_log_row()
        except Exception as e:
            error_dialog = ErrorDialog("Database Error", "Could not load initial data.", details=traceback.format_exc(),
                                       parent=self)
            error_dialog.exec()

    # def _on_add_row_shortcut(self):
    #     """Handler for the Shift+Enter shortcut to add a new row."""
    #     # Check if the focus is in the output log's group box
    #     if self.ui.output_log_table.hasFocus() or \
    #             (self.focusWidget() and self.ui.output_log_table.isAncestorOf(self.focusWidget())):
    #         self._add_output_log_row()
    #
    #     # Check if focus is in the resin consumption group box
    #     elif self.ui.resin_group.hasFocus() or \
    #             (self.focusWidget() and self.ui.resin_group.isAncestorOf(self.focusWidget())):
    #         self._add_resin_row()
    #
    #
    #     elif self.ui.remarks_personnel_group.hasFocus() or \
    #          (self.focusWidget() and self.ui.remarks_personnel_group.isAncestorOf(self.focusWidget())):
    #         self._add_personnel_row()
    #
    # def _on_delete_shortcut(self):
    #     """Handler for the Ctrl+D shortcut to delete a row."""
    #     # Check output log
    #     if self.ui.output_log_table.hasFocus() or \
    #             (self.focusWidget() and self.ui.output_log_table.isAncestorOf(self.focusWidget())):
    #         if self.ui.output_log_table.rowCount() > 0 and self.ui.output_log_table.currentRow() >= 0:
    #             reply = QMessageBox.question(self, "Confirm Delete",
    #                                          "Are you sure you want to remove the selected log entry?",
    #                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    #                                          QMessageBox.StandardButton.No)
    #             if reply == QMessageBox.StandardButton.Yes:
    #                 self._remove_selected_output_log()
    #
    #     # Check resin consumption
    #     elif self.ui.resin_group.hasFocus() or \
    #             (self.focusWidget() and self.ui.resin_group.isAncestorOf(self.focusWidget())):
    #         if self.ui.purging_details_table.rowCount() > 0 and self.ui.purging_details_table.currentRow() >= 0:
    #             reply = QMessageBox.question(self, "Confirm Delete",
    #                                          "Are you sure you want to remove the selected resin entry?",
    #                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    #                                          QMessageBox.StandardButton.No)
    #             if reply == QMessageBox.StandardButton.Yes:
    #                 self._remove_selected_resin()
    #
    #     # --- NEW: Check personnel ---
    #     elif self.ui.remarks_personnel_group.hasFocus() or \
    #             (self.focusWidget() and self.ui.remarks_personnel_group.isAncestorOf(self.focusWidget())):
    #         # Since the dynamic rows aren't selectable, we can just remove the last one.
    #         if self.ui.personnel_container_layout.count() > 0:
    #             reply = QMessageBox.question(self, "Confirm Delete",
    #                                          "Are you sure you want to remove the last personnel entry?",
    #                                          QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    #                                          QMessageBox.StandardButton.No)
    #             if reply == QMessageBox.StandardButton.Yes:
    #                 self._remove_personnel_row()

    def _on_add_row_shortcut(self):
        """Handler for the Shift+Enter shortcut to add a new row."""
        # Check output log table
        if self.ui.output_log_table.hasFocus() or \
                (self.focusWidget() and self.ui.output_log_table.isAncestorOf(self.focusWidget())):
            self._add_output_log_row()

        # Check resin consumption table
        elif self.ui.resin_group.hasFocus() or \
                (self.focusWidget() and self.ui.resin_group.isAncestorOf(self.focusWidget())):
            self._add_resin_row()

        # --- FIX: Use the correct group box name 'remarks_personnel_group' ---
        elif self.ui.remarks_personnel_group.hasFocus() or \
                (self.focusWidget() and self.ui.remarks_personnel_group.isAncestorOf(self.focusWidget())):
            self._add_personnel_row()

    def _on_delete_shortcut(self):
        """Handler for the Ctrl+D shortcut to delete a row."""
        # Check output log table
        if self.ui.output_log_table.hasFocus() or \
                (self.focusWidget() and self.ui.output_log_table.isAncestorOf(self.focusWidget())):
            if self.ui.output_log_table.rowCount() > 0 and self.ui.output_log_table.currentRow() >= 0:
                reply = QMessageBox.question(self, "Confirm Delete",
                                             "Are you sure you want to remove the selected log entry?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                             QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self._remove_selected_output_log()

        # Check resin consumption table
        elif self.ui.resin_group.hasFocus() or \
                (self.focusWidget() and self.ui.resin_group.isAncestorOf(self.focusWidget())):
            if self.ui.purging_details_table.rowCount() > 0 and self.ui.purging_details_table.currentRow() >= 0:
                reply = QMessageBox.question(self, "Confirm Delete",
                                             "Are you sure you want to remove the selected resin entry?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                             QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self._remove_selected_resin()

        # --- FIX: Use the correct group box name 'remarks_personnel_group' ---
        elif self.ui.remarks_personnel_group.hasFocus() or \
                (self.focusWidget() and self.ui.remarks_personnel_group.isAncestorOf(self.focusWidget())):
            if self.ui.personnel_container_layout.count() > 0:
                reply = QMessageBox.question(self, "Confirm Delete",
                                             "Are you sure you want to remove the last personnel entry?",
                                             QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                             QMessageBox.StandardButton.No)
                if reply == QMessageBox.StandardButton.Yes:
                    self._remove_personnel_row()




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
        row_widget = QWidget()
        # --- THIS IS THE FIX (Part 1) ---
        # When creating a brand new row, stamp it with a None ID.
        row_widget.setProperty("db_id", None)
        # --- END FIX ---

        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        name_combo = QComboBox()
        name_combo.setObjectName("ComboBox")
        name_combo.setEditable(True)
        name_combo.addItem("- Select Name -", None)
        for emp in self.employee_list:
            name_combo.addItem(f"{emp.first_name} {emp.last_name}", emp.id)

        pos_combo = QComboBox()
        pos_combo.setObjectName("ComboBox")
        pos_combo.setEditable(True)
        pos_combo.addItem("- Select Position -", None)
        for pos in self.position_list:
            pos_combo.addItem(pos.name, pos.id)

        pos_combo.model().item(0).setEnabled(False)
        name_combo.model().item(0).setEnabled(False)

        row_layout.addWidget(name_combo)
        row_layout.addWidget(pos_combo)
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


    def _on_no_purging_toggled(self, checked: bool):
        """
        Enables or disables ONLY the purging process-specific fields.
        Resin, Pelletizer, Siever, and the Resin Consumption table remain enabled.
        """
        # 'checked' means "No Purging" is active, so the fields should be DISABLED.
        is_process_enabled = not checked

        # 1. Toggle only the specific, process-related fields.
        self.ui.resin_group.setEnabled(is_process_enabled)
        self.ui.purging_product_code_combo.setEnabled(is_process_enabled)
        self.ui.purging_start_time.setEnabled(is_process_enabled)
        self.ui.purging_end_time.setEnabled(is_process_enabled)

        # The 'resin_group' (Resin Consumption table) is NO LONGER disabled here.

        if is_process_enabled:
            # This runs when the user UNCHECKS "No Purging".
            # Reload the product codes for the now-enabled combo box.
            try:
                initial_codes = self.controller.get_distinct_product_codes_paginated(page=1, page_size=1000, limit=1000)
                self.ui.purging_product_code_combo.populate_initial(initial_codes)
            except Exception as e:
                error_dialog = ErrorDialog("Load Error", "Could not reload product codes.",
                                           details=traceback.format_exc(), parent=self)
                error_dialog.exec()
        else:
            # This runs when the user CHECKS "No Purging".
            # Clear only the fields that were just disabled.
            self.ui.purging_product_code_combo.clear()
            self.ui.purging_start_time.setTime(QTime(0, 0))
            self.ui.purging_end_time.setTime(QTime(0, 0))

            # Also clear the Resin Consumption table since its group was disabled.
            self.ui.purging_details_table.setRowCount(0)



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


        qty_item = QTableWidgetItem("0.00")
        notes_item = QTableWidgetItem("")

        table.setCellWidget(row_position, 0, resin_combo)
        table.setItem(row_position, 1, qty_item)
        table.setItem(row_position, 2, notes_item)


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


        self.ui.output_log_table.setCurrentCell(row_position, 0)
        self.ui.output_log_table.editItem(self.ui.output_log_table.item(row_position, 0))

    # def eventFilter(self, obj: QObject, event: QEvent) -> bool:
    #     # This event filter is now only for the Tab key functionality
    #     if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab and isinstance(obj, QTimeEdit):
    #         for row in range(self.ui.output_log_table.rowCount()):
    #             if self.ui.output_log_table.cellWidget(row, 2) is obj:
    #                 target_item = self.ui.output_log_table.item(row, 4)
    #                 if target_item:
    #                     self.ui.output_log_table.setCurrentItem(target_item)
    #                     self.ui.output_log_table.editItem(target_item)
    #                 return True
    #     return super().eventFilter(obj, event)


    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        """
        This event filter is now ONLY for handling the Tab key press on the
        'Time End' widget to skip the non-editable 'Time Used' column.
        """
        if event.type() == QEvent.Type.KeyPress and event.key() == Qt.Key.Key_Tab:
            if isinstance(obj, QTimeEdit):
                for row in range(self.ui.output_log_table.rowCount()):
                    # Check if the event is coming from a 'Time End' widget
                    if self.ui.output_log_table.cellWidget(row, 2) is obj:
                        # If so, find the 'Output (kg)' item in the next editable column
                        target_item = self.ui.output_log_table.item(row, 4)
                        if target_item:
                            self.ui.output_log_table.setCurrentItem(target_item)
                            self.ui.output_log_table.editItem(target_item)
                        return True  # Event handled

        # For all other events, let the default handler process them
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
        """Removes the currently selected row from the output log."""
        # This method is slightly modified to be more robust
        table = self.ui.output_log_table
        current_row = table.currentRow()
        if current_row >= 0:
            table.removeRow(current_row)



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
        self.edit_record_id = None  # <-- ADD THIS: Reset edit state on clear

        QMessageBox.information(self, "Cleared", "Form has been cleared.")


    def _gather_data_from_ui(self) -> dict | None:
        """
        --- THIS METHOD IS NOW CORRECTED ---
        Gathers all data from the UI using a 100% reliable method to get data
        from editable combo boxes.
        """
        try:
            prod_id_str = "; ".join(sorted([item for item in self.aggregated_prod_ids if item]))
            formula_no_str = "; ".join(sorted([item for item in self.aggregated_formula_ids if item]))
            order_no_str = "; ".join(sorted([item for item in self.aggregated_order_nos if item]))

            output_log_list = []
            for r in range(self.ui.output_log_table.rowCount()):
                date_widget = self.ui.output_log_table.cellWidget(r, 0);
                start_time_widget = self.ui.output_log_table.cellWidget(r, 1)
                end_time_widget = self.ui.output_log_table.cellWidget(r, 2);
                output_item = self.ui.output_log_table.item(r, 4)
                if not all([date_widget, start_time_widget, end_time_widget,
                            output_item]) or date_widget.date().isNull(): continue
                start_date = date_widget.date().toPyDate();
                start_time = start_time_widget.time().toPyTime();
                end_time = end_time_widget.time().toPyTime()
                datetime_start = datetime.combine(start_date, start_time);
                end_date = start_date
                if end_time <= start_time: end_date += timedelta(days=1)
                datetime_end = datetime.combine(end_date, end_time)
                output_log_list.append(
                    {"datetime_start": datetime_start, "datetime_end": datetime_end, "output": output_item.text()})

            data = {
                "main": {
                    "lot_number": self.ui.lot_number_input.text(), "production_id": prod_id_str,
                    "formula_no": formula_no_str,
                    "order_no": order_no_str, "product_code": self.ui.product_code_input.text(),
                    "customer": self.ui.customer_input.text(),
                    "qty_order": self.ui.qty_order_input.text(), "qty_produced": self.ui.qty_produced_input.text(),
                    "target_output_per_hour": self.ui.target_output_hr_input.text(),
                    "prepared_by_name": self.ui.prepared_by_combo.currentText(),
                    "machine_id": self.ui.mc_no_combo.currentData(), "shift_id": self.ui.shift_combo.currentData()
                },
                "machine_details": {
                    "screw_config_id": self.ui.screw_config_combo.currentData(),
                    "feed_rate": self.ui.feed_rate_input.text(),
                    "rpm": self.ui.rpm_input.text(), "screen_size_id": self.ui.screen_size_combo.currentData(),
                    "is_vacuum_on": self.ui.is_vacuum_on_checkbox.isChecked()
                },
                "output_log": output_log_list,
                "zone_temps": {name: widget.text() for name, widget in self.ui.zone_inputs.items()},
                "remarks": self.ui.remarks_input.toPlainText()
            }

            # --- THIS IS THE DEFINITIVE FIX ---
            personnel_list = []
            layout = self.ui.personnel_container_layout
            for i in range(layout.count()):
                if row_widget := layout.itemAt(i).widget():
                    db_id = row_widget.property("db_id")

                    row_layout = row_widget.layout()
                    if row_layout and row_layout.count() == 2:
                        name_combo: QComboBox = row_layout.itemAt(0).widget()
                        pos_combo: QComboBox = row_layout.itemAt(1).widget()

                        if isinstance(name_combo, QComboBox) and isinstance(pos_combo, QComboBox):
                            # Find the index corresponding to the current text
                            name_index = name_combo.findText(name_combo.currentText())
                            pos_index = pos_combo.findText(pos_combo.currentText())

                            # Get the data (ID) from that specific index
                            employee_id = name_combo.itemData(name_index)
                            position_id = pos_combo.itemData(pos_index)

                            if employee_id is not None and position_id is not None:
                                personnel_list.append({
                                    "id": db_id,
                                    "employee_id": employee_id,
                                    "position_id": position_id
                                })
            data["personnel"] = personnel_list
            # --- END FIX ---

            if not self.ui.no_purging_checkbox.isChecked():
                data["purging_header"] = {
                    "product_code_name": self.ui.purging_product_code_combo.currentText(),
                    "start_time": self.ui.purging_start_time.time().toPyTime(),
                    "end_time": self.ui.purging_end_time.time().toPyTime(),
                    "resin_id": self.ui.purging_resin_combo.currentData(),
                    "palletizer": self.ui.purging_palletizer_input.text(),
                    "siever": self.ui.purging_siever_input.text()
                }
                data["purging_details"] = [
                    {
                        "resin_id": self.ui.purging_details_table.cellWidget(r, 0).currentData(),
                        "qty": self.ui.purging_details_table.item(r, 1).text(),
                        "notes": self.ui.purging_details_table.item(r, 2).text().strip(),

                    } for r in range(self.ui.purging_details_table.rowCount())
                ]
            return data
        except Exception:
            error_dialog = ErrorDialog("Error Reading Form Data", "Could not read values from the form.",
                                       details=traceback.format_exc(), parent=self)
            error_dialog.exec();
            return None


    def _validate_required_fields(self) -> bool:
        """
        Checks all required fields. Resin, Pelletizer, Siever, and the Resin
        Consumption table are now always validated.
        """
        validation_map = {
            "Order Information": [
                (self.ui.lot_number_input, "Lot Number"),
            ],
            "Machine & Configuration": [
                (self.ui.mc_no_combo, "MC No."),
                (self.ui.shift_combo, "Shift"),
                (self.ui.screen_size_combo, "Screen Size"),
                (self.ui.screw_config_combo, "Screw Config."),
            ],
            "Personnel": [
                (self.ui.prepared_by_combo, "Prepared By"),
            ],
            # --- FIX: Purging Details now has its core fields always required ---
            "Purging Details": [
                (self.ui.purging_resin_combo, "Resin used (carrier)"),
                (self.ui.purging_palletizer_input, "Pelletizer used"),
                (self.ui.purging_siever_input, "Siever used"),
            ]
        }

        # Conditionally add the purging process fields to the validation map
        if not self.ui.no_purging_checkbox.isChecked():
            validation_map["Purging Details"].append(
                (self.ui.purging_product_code_combo, "Product Code")
            )

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

        if custom_rules_errors:
            missing_issues.append(
                f"<b>Other Issues:</b><ul>{''.join(f'<li>{err}</li>' for err in custom_rules_errors)}</ul>")

        # Final Check
        if missing_issues:
            final_issue_list_html = "<br>".join(missing_issues)
            error_dialog = ErrorDialog("Validation Error",
                                       f"Please correct the following issues before saving:<br>{final_issue_list_html}",
                                       parent=self)
            error_dialog.exec()
            return False

        return True

    def _save_form_data(self):
        # --- FIX: Only call the one comprehensive validation method ---

        if not self._validate_required_fields():
            return


        form_data = self._gather_data_from_ui()


        try:

            # --- THIS IS THE NEW LOGIC ---
            if self.edit_record_id is not None:
                # If we are in edit mode, call the update method

                self.controller.update_full_form(self.edit_record_id, form_data, self.zone_mapping)
                message = "The extruder form data has been updated successfully."
            else:
                # Otherwise, call the original save method for a new record
                self.controller.save_full_form(form_data, self.zone_mapping)
                message = "The extruder form data has been saved successfully."

            # Emit the signal to close the dialog and then show success
            self.data_saved.emit()
            success_dialog = SuccessDialog("Success", message, parent=self)
            success_dialog.exec()

            # Clearing the form is only necessary for a new entry, not an edit that closes
            if self.edit_record_id is None:
                self._clear_form()
            # --- END NEW LOGIC ---

        except Exception as e:
            error_dialog = ErrorDialog("Save Error", "Could not save the form data.", details=traceback.format_exc(), parent=self)
            error_dialog.exec()

    def populate_form_for_editing(self, record):
        """Fills the entire form with data from an existing record object."""
        self.edit_record_id = record.id

        # --- THIS IS THE DEFINITIVE FIX ---
        # 1. Clear any previous state before loading new data.
        self.aggregated_prod_ids.clear()
        self.aggregated_formula_ids.clear()
        self.aggregated_order_nos.clear()

        # 2. Re-initialize the internal sets from the record's stored strings.
        if record.production_id:
            self.aggregated_prod_ids = set(record.production_id.split('; '))
        if record.formula_no:
            self.aggregated_formula_ids = set(record.formula_no.split('; '))
        if record.order_no:
            self.aggregated_order_nos = set(record.order_no.split('; '))
        # --- END FIX ---


        self.ui.lot_number_input.setText(record.lot_number)
        self.ui.product_code_input.setText(record.product_code)
        self.ui.customer_input.setText(record.customer)
        self.ui.qty_order_input.setText(f"{record.qty_order or '0.00'}")
        self.ui.qty_produced_input.setText(f"{record.qty_produced or '0.00'}")
        self.ui.target_output_hr_input.setText(f"{getattr(record, 'target_output_per_hour', '0.00') or '0.00'}")
        self.ui.remarks_input.setPlainText(record.remarks)
        self.ui.shift_combo.setCurrentText(getattr(record.shift, 'name', ''))
        self.ui.mc_no_combo.setCurrentText(getattr(record.machine, 'name', ''))
        if record.machine_details:
            self.ui.feed_rate_input.setText(record.machine_details.feed_rate)
            self.ui.rpm_input.setText(record.machine_details.rpm)
            self.ui.screen_size_combo.setCurrentText(getattr(record.machine_details.screen_size, 'size', ''))
            self.ui.screw_config_combo.setCurrentText(getattr(record.machine_details.screw_config, 'name', ''))
            self.ui.is_vacuum_on_checkbox.setChecked(record.machine_details.is_vacuum_on)
        for temp in record.machine_temps:
            if temp.zone and temp.zone.name in self.ui.zone_inputs:
                self.ui.zone_inputs[temp.zone.name].setText(str(temp.temp_value))

        self.ui.output_log_table.setRowCount(0)
        for i, output in enumerate(
                sorted(record.extruder_outputs, key=lambda x: (x.datetime_start is None, x.datetime_start))):
            try:
                self._add_output_log_row()
                row = self.ui.output_log_table.rowCount() - 1
                date_widget = self.ui.output_log_table.cellWidget(row, 0)
                start_widget = self.ui.output_log_table.cellWidget(row, 1)
                end_widget = self.ui.output_log_table.cellWidget(row, 2)
                qty_item = self.ui.output_log_table.item(row, 4)
                if not all([date_widget, start_widget, end_widget, qty_item]):
                    raise RuntimeError(f"Could not find widgets for output log row {row}.")

                date_widget.blockSignals(True);
                start_widget.blockSignals(True);
                end_widget.blockSignals(True)
                try:
                    # --- THIS IS THE DEFINITIVE FIX ---
                    if output.datetime_start:
                        # Correct constructor for QDate
                        date_widget.setDate(QDate(output.datetime_start.date()))
                        # Correct constructor for QTime
                        start_widget.setTime(QTime(output.datetime_start.time()))
                    if output.datetime_end:
                        # Correct constructor for QTime
                        end_widget.setTime(QTime(output.datetime_end.time()))
                    qty_item.setText(f"{output.qty_output or '0.00'}")
                    # --- END FIX ---
                finally:
                    date_widget.blockSignals(False)
                    start_widget.blockSignals(False)
                    end_widget.blockSignals(False)

                self._calculate_output_log_time_used(row)

            except Exception as e:
                error_dialog = ErrorDialog(
                    title="Error Populating Form",
                    message=f"A critical error occurred while displaying data for output log entry #{i + 1}.",
                    details=traceback.format_exc(), parent=self
                )
                error_dialog.exec()
                return

            # --- THIS IS THE FIX (Part 3) ---
            # Populate Personnel
        while self.ui.personnel_container_layout.count() > 0: self._remove_personnel_row()
        self.ui.prepared_by_combo.setCurrentText(record.prepared_by)

        if record.extruder_personnels:
            for p in record.extruder_personnels:
                self._add_personnel_row()
                row_widget = self.ui.personnel_container_layout.itemAt(
                    self.ui.personnel_container_layout.count() - 1).widget()

                # Stamp the widget with its database ID
                row_widget.setProperty("db_id", p.id)

                name_combo = row_widget.findChildren(QComboBox)[0]
                pos_combo = row_widget.findChildren(QComboBox)[1]
                name_combo.setCurrentText(f"{p.employee.first_name} {p.employee.last_name}" if p.employee else "")
                pos_combo.setCurrentText(p.position.name if p.position else "")
        else:
            self._add_personnel_row()  # Add one blank row if none exist
        # --- END FIX ---

        if not record.purging_headers:
            self.ui.no_purging_checkbox.setChecked(True)



        else:
            self.ui.no_purging_checkbox.setChecked(False)
            header = record.purging_headers[0]
            self.ui.purging_product_code_combo.setCurrentText(header.product_code)
            self.ui.purging_start_time.setTime(header.time_start)
            self.ui.purging_end_time.setTime(header.time_end)
            self.ui.purging_resin_combo.setCurrentText(getattr(header.resin_used, 'abbreviation', ''))
            self.ui.purging_palletizer_input.setText(str(header.palletizer_used))
            self.ui.purging_siever_input.setText(str(header.siever_used))
            self.ui.purging_details_table.setRowCount(0)
            for detail in header.purging_details:
                self._add_resin_row()
                row = self.ui.purging_details_table.rowCount() - 1
                self.ui.purging_details_table.cellWidget(row, 0).setCurrentText(
                    getattr(detail.resin, 'abbreviation', ''))
                self.ui.purging_details_table.item(row, 1).setText(f"{detail.qty or '0.00'}")
                self.ui.purging_details_table.item(row, 2).setText(detail.notes)


        self._update_production_summary()
