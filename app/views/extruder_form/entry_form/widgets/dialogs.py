# app/views/extruder_form/entry_form/widgets/dialogs.py

from decimal import Decimal
from typing import Dict, Callable

from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QLineEdit,
    QWidget, QSplitter, QMessageBox, QGroupBox, QFormLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)
from .numeric_line_edit import QNumericLineEdit
from ..ops import ExtruderOpsController


class LotNumberDialog(QDialog):
    PAGE_SIZE = 100

    def __init__(self, controller: ExtruderOpsController,
                 success_callback: Callable,
                 parent=None,
                 initial_product_code: str = None,
                 initial_customer: str = None):
        super().__init__(parent)
        self.setWindowTitle("Select Lot Number")
        self.setMinimumSize(800, 600)

        self.controller = controller
        self.success_callback = success_callback
        self.current_page = 1
        self.is_loading_more = False
        self.can_load_more = True

        self.initial_product_code_lock = initial_product_code
        self.initial_customer_lock = initial_customer

        self._setup_ui()
        self._connect_signals()
        self._load_lots()
        self._initial_ui_state()

    # --- All other methods are correct ---
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        left_panel, self.search_input, self.lot_list_widget = self._create_left_panel()
        right_panel = self._create_right_panel()
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 500])
        self.button_box = QDialogButtonBox()
        self.apply_btn = self.button_box.addButton("Apply Selection", QDialogButtonBox.ButtonRole.AcceptRole)
        self.reset_btn = self.button_box.addButton("Reset", QDialogButtonBox.ButtonRole.DestructiveRole)
        self.close_btn = self.button_box.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(self.button_box)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(300)

    def _create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("1. Select Lot Number"))
        self.filter_status_label = QLabel()
        self.filter_status_label.setStyleSheet("font-style: italic; color: #555;")
        self.filter_status_label.setWordWrap(True)
        layout.addWidget(self.filter_status_label)
        search_input = QLineEdit()
        search_input.setPlaceholderText("Search by Production ID or Lot Number...")

        lot_list_widget = QTableWidget()
        lot_list_widget.setColumnCount(2)
        lot_list_widget.setHorizontalHeaderLabels(["Prod ID", "Lot Number"])
        lot_list_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        lot_list_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        lot_list_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        lot_list_widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        lot_list_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        lot_list_widget.verticalHeader().setVisible(False)

        layout.addWidget(search_input)
        layout.addWidget(lot_list_widget)
        return panel, search_input, lot_list_widget

    def _create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        details_group = QGroupBox("Lot Details")
        details_layout = QFormLayout(details_group)
        self.prod_id_label = QLabel("-")
        self.prod_code_label = QLabel("-")
        self.customer_label = QLabel("-")
        self.formula_id_label = QLabel("-")

        # --- FIX: Add the new labels for the new details ---
        self.order_no_label = QLabel("-")
        self.qty_order_label = QLabel("-")
        self.qty_produced_label = QLabel("-")


        details_layout.addRow("Production ID:", self.prod_id_label)
        details_layout.addRow("Product Code:", self.prod_code_label)
        details_layout.addRow("Customer:", self.customer_label)
        details_layout.addRow("Formula No:", self.formula_id_label)

        # --- FIX: Add the new rows to the layout ---
        details_layout.addRow("Order Number:", self.order_no_label)
        details_layout.addRow("Qty Order (kg):", self.qty_order_label)
        details_layout.addRow("Qty Produced (kg):", self.qty_produced_label)

        layout.addWidget(details_group)

        prod_cut_group = QGroupBox("Production Cut (Optional)")
        prod_cut_layout = QFormLayout(prod_cut_group)
        self.prod_cut_checkbox = QCheckBox("Apply Production Cut")

        self.prod_cut_lot_input = QLineEdit()
        self.prod_cut_lot_input.setPlaceholderText("Enter Lot number")
        self.prod_cut_lot_input.setEnabled(False)

        self.prod_cut_qty_input = QNumericLineEdit()
        self.prod_cut_qty_input.setPlaceholderText("Enter Qty in kg")
        self.prod_cut_qty_input.setEnabled(False)

        prod_cut_layout.addRow(self.prod_cut_checkbox)
        prod_cut_layout.addRow("Lot Number:", self.prod_cut_lot_input)
        prod_cut_layout.addRow("Production Cut Qty:", self.prod_cut_qty_input)
        layout.addWidget(prod_cut_group)

        layout.addWidget(QLabel("Materials Used"))
        self.material_table = QTableWidget()
        self.material_table.setColumnCount(2)
        self.material_table.setHorizontalHeaderLabels(["Material Code", "Qty (kg)"])
        self.material_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.material_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.material_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.material_table.verticalHeader().setVisible(False)
        layout.addWidget(self.material_table)

        summary_layout = QHBoxLayout()
        summary_layout.addStretch()
        summary_layout.addWidget(QLabel("<b>Total Material Qty:</b>"))
        self.total_material_qty_label = QLabel("0.00 kg")
        self.total_material_qty_label.setStyleSheet("font-weight: bold;")
        summary_layout.addWidget(self.total_material_qty_label)
        layout.addLayout(summary_layout)
        return panel

    def _initial_ui_state(self):
        if self.initial_product_code_lock and self.initial_customer_lock:
            self._update_filter_status_display()
            self.search_input.setPlaceholderText("Search within filtered list...")
            self.apply_btn.setText("Apply Additional Lot")
        else:
            self.filter_status_label.hide()

    def _connect_signals(self):
        self.search_timer.timeout.connect(self._trigger_search)
        self.search_input.textChanged.connect(self.search_timer.start)
        self.lot_list_widget.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.lot_list_widget.itemSelectionChanged.connect(self._on_lot_selection_changed)
        self.lot_list_widget.itemDoubleClicked.connect(lambda: self.accept())
        self.prod_cut_checkbox.toggled.connect(self.prod_cut_qty_input.setEnabled)
        self.prod_cut_checkbox.toggled.connect(self.prod_cut_lot_input.setEnabled)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)  # Close button calls reject()
        self.reset_btn.clicked.connect(self._reset_selections)

    def accept(self):
        """
        Handles the apply/accept action. It validates, sends data, and then
        decides whether to close or reset based on its state.
        """
        selected_items = self.lot_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a lot number to apply.")
            return

        # if self.prod_cut_checkbox.isChecked():
        #     prod_cut_qty_value = self.prod_cut_qty_input.get_value()
        #     prod_cut_lot_value = self.prod_cut_lot_input.get_value()
        #
        #     if prod_cut_qty_value <= 0:
        #         QMessageBox.warning(self, "Validation Error", "Production Cut requires a quantity greater than zero.")
        #         return

        if self.prod_cut_checkbox.isChecked():
            # Note: If prod_cut_lot_input is a standard QLineEdit, it uses .text().
            # If you made a custom class with .get_value(), you can swap this back.
            prod_cut_lot_value = self.prod_cut_lot_input.text().strip()
            prod_cut_qty_value = self.prod_cut_qty_input.get_value()

            # 1. Validate the Lot Number
            if not prod_cut_lot_value:  # This gracefully catches None, "", and "   "
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    "Production Cut requires a Lot Number."
                )
                self.prod_cut_lot_input.setFocus()  # Puts the cursor in the empty box
                return

            # 2. Validate the Quantity
            if prod_cut_qty_value is None or prod_cut_qty_value <= 0:
                QMessageBox.warning(
                    self,
                    "Validation Error",
                    "Production Cut requires a quantity greater than zero."
                )
                self.prod_cut_qty_input.setFocus()  # Puts the cursor in the invalid box
                return






            # Removed this 11/12/2025. Due to Production staff can't enter a production cut
            # try:
            #     total_material_qty = float(self.total_material_qty_label.text().replace(" kg", ""))
            #     if prod_cut_value > total_material_qty:
            #         QMessageBox.warning(self, "Validation Error",
            #                             f"Production Cut Qty ({prod_cut_value:.2f} kg) cannot exceed the "
            #                             f"Total Material Qty ({total_material_qty:.2f} kg).")
            #         return
            # except (ValueError, TypeError):
            #     QMessageBox.critical(self, "Error", "Could not verify total material quantity.")
            #     return

        current_lot_data = selected_items[0].data(Qt.ItemDataRole.UserRole)
        prod_cut_qty = self.prod_cut_qty_input.get_value() if self.prod_cut_checkbox.isChecked() else None
        prod_cut_lot = self.prod_cut_lot_input.text().strip() if self.prod_cut_checkbox.isChecked() else None
        print(prod_cut_lot)

        self.success_callback({
            "lot_data": current_lot_data,
            "prod_cut_qty": prod_cut_qty,
            "prod_cut_lot": prod_cut_lot,

        })

        # --- FIX FOR BUG 2: Conditional closing logic ---
        is_initial_apply = self.initial_product_code_lock is None

        if is_initial_apply:
            # On the first apply, close the dialog. The main window will handle reopening it if needed.
            super().accept()
        else:
            # On subsequent applies, stay open and reset for the next entry.
            self.lot_list_widget.clearSelection()
            self._update_details_display(None)
            QMessageBox.information(self, "Success", f"Applied lot '{current_lot_data['lot_num']}' to the main form.")

    @pyqtSlot()
    def _on_lot_selection_changed(self):
        selected_rows = self.lot_list_widget.selectionModel().selectedRows()
        self.material_table.setRowCount(0)
        self.total_material_qty_label.setText("0.00 kg")

        if not selected_rows:
            self._update_details_display(None)
            return

        item = self.lot_list_widget.item(selected_rows[0].row(), 0)
        item_data = item.data(Qt.ItemDataRole.UserRole)
        self._update_details_display(item_data)

        prod_id = item_data.get("prod_id")
        if not prod_id: return

        try:
            materials = self.controller.get_materials_for_prod_ids([prod_id])
            total_qty = Decimal("0.00")
            self.material_table.setRowCount(len(materials))
            for i, mat in enumerate(materials):
                qty = mat.get('qty') or Decimal("0.00")
                code_item = QTableWidgetItem(mat.get("mat_code", "N/A"))
                qty_item = QTableWidgetItem(f"{qty:.2f}")
                qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.material_table.setItem(i, 0, code_item)
                self.material_table.setItem(i, 1, qty_item)
                total_qty += qty
            self.total_material_qty_label.setText(f"{total_qty:.2f} kg")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not fetch materials: {e}")

    @pyqtSlot()
    def _reset_selections(self):
        self.lot_list_widget.clearSelection()
        if self.initial_product_code_lock is None:
            self.search_input.clear()
        self._load_lots()

    def _load_lots(self):
        self.is_loading_more = True
        try:
            lots = self.controller.get_lot_numbers_paginated(
                page=self.current_page,
                page_size=self.PAGE_SIZE,
                search_term=self.search_input.text(),
                product_code=self.initial_product_code_lock,
                customer=self.initial_customer_lock
            )
            if self.current_page == 1: self.lot_list_widget.setRowCount(0)
            if not lots or len(lots) < self.PAGE_SIZE: self.can_load_more = False

            for lot_data in lots:
                row_pos = self.lot_list_widget.rowCount()
                self.lot_list_widget.insertRow(row_pos)
                prod_id_item = QTableWidgetItem(str(lot_data.get("prod_id", "")))
                prod_id_item.setData(Qt.ItemDataRole.UserRole, lot_data)
                self.lot_list_widget.setItem(row_pos, 0, prod_id_item)
                self.lot_list_widget.setItem(row_pos, 1, QTableWidgetItem(lot_data.get("lot_num", "")))
        finally:
            self.is_loading_more = False

    def _update_details_display(self, data: Dict | None):
        """
        Updates the entire details panel when a new lot is selected.
        This now includes fetching the order quantity.
        """
        if data:
            self.prod_id_label.setText(str(data.get("prod_id", "-")))
            self.prod_code_label.setText(data.get("product_code", "-"))
            self.customer_label.setText(data.get("customer", "-"))
            self.formula_id_label.setText(str(data.get("formula_id", "-")))

            # --- FIX: Set the new labels ---
            order_no = data.get("order_no", "")
            self.order_no_label.setText(str(order_no))

            qty_produced = data.get("qty_produced")
            self.qty_produced_label.setText(f"{qty_produced:.2f}" if qty_produced is not None else "-")

            # Perform the lookup for Qty Order
            if order_no:
                order_qty = self.controller.get_order_qty_by_order_number(order_no)
                self.qty_order_label.setText(f"{order_qty:.2f}" if order_qty is not None else "Not Found")
            else:
                self.qty_order_label.setText("-")
        else:
            # Clear all labels when no lot is selected
            self.prod_id_label.setText("-")
            self.prod_code_label.setText("-")
            self.customer_label.setText("-")
            self.formula_id_label.setText("-")
            # --- FIX: Clear the new labels as well ---
            self.order_no_label.setText("-")
            self.qty_order_label.setText("-")
            self.qty_produced_label.setText("-")

        # Reset prod cut feature
        self.prod_cut_checkbox.setChecked(False)
        self.prod_cut_qty_input.clear()
        self.prod_cut_lot_input.clear()


    def _update_filter_status_display(self):
        if self.initial_product_code_lock and self.initial_customer_lock:
            self.filter_status_label.setText(
                f"Filtering by Code: '{self.initial_product_code_lock}'."
            )
            self.filter_status_label.show()
        else:
            self.filter_status_label.hide()

    @pyqtSlot()
    def _trigger_search(self):
        self.current_page = 1

        self.can_load_more = True
        self._load_lots()

    @pyqtSlot(int)
    def _on_scroll(self, value: int):
        scrollbar = self.lot_list_widget.verticalScrollBar()
        if not self.can_load_more or self.is_loading_more or value < scrollbar.maximum() * 0.9: return
        self.current_page += 1
        self._load_lots()


class GenericSubFormDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"This is the placeholder dialog for '{title}'."))
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(button_box)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)