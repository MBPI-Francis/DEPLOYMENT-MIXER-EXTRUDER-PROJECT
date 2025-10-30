# app/views/extruder_form/entry_form/widgets/dialogs.py
from decimal import Decimal

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QListWidget, QLineEdit,
    QWidget, QSplitter, QListWidgetItem, QPushButton, QMessageBox, QGroupBox, QFormLayout, QHBoxLayout, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from typing import Dict, List, Callable, Any

from ..ops import ExtruderOpsController


class LotNumberDialog(QDialog):
    PAGE_SIZE = 100

    def __init__(self, controller: ExtruderOpsController,
                 success_callback: Callable,
                 parent=None,
                 initial_product_code: str = None,
                 initial_customer: str = None):
        super().__init__(parent)
        self.setWindowTitle("Select Lot Number(s) and Formula(s)")
        self.setMinimumSize(950, 700)

        self.controller = controller
        self.success_callback = success_callback
        self.current_page = 1
        self.is_loading_more = False
        self.can_load_more = True

        # self.locked_product_code = initial_product_code

        # --- FIX: Store the permanent lock state separately ---
        self.initial_product_code_lock = initial_product_code
        self.initial_customer_lock = initial_customer


        self.locked_product_code = initial_product_code
        self.locked_customer = initial_customer # Will be set on first apply


        # --- FIX: Store data, not the widget item ---
        self.locked_lot_data = None
        self.formula_details_cache = {}

        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal);
        layout.addWidget(splitter)
        left_panel, self.search_input, self.lot_list_widget = self._create_left_panel();
        splitter.addWidget(left_panel)
        center_panel, self.formula_list_widget, self.add_formula_btn = self._create_center_panel();
        splitter.addWidget(center_panel)
        right_panel, self.selected_formulas_widget, self.remove_formula_btn, self.material_list_widget = self._create_right_panel();
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 300, 400])

        self.button_box = QDialogButtonBox()
        self.apply_btn = self.button_box.addButton("Apply Selections", QDialogButtonBox.ButtonRole.AcceptRole)
        self.reset_btn = self.button_box.addButton("Reset", QDialogButtonBox.ButtonRole.DestructiveRole)
        self.close_btn = self.button_box.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(self.button_box)

        self.search_timer = QTimer(self);
        self.search_timer.setSingleShot(True);
        self.search_timer.setInterval(300)
        self._connect_signals()
        self._load_lots()

        self.lot_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        if self.locked_product_code and self.locked_customer:
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
        self.lot_list_widget.itemDoubleClicked.connect(self._on_lot_double_clicked)
        self.formula_list_widget.itemSelectionChanged.connect(self._on_formula_selection_changed)

        # --- NEW: Connect the signal for the "Selected Formulas" list ---
        self.selected_formulas_widget.itemSelectionChanged.connect(self._on_selected_formula_changed)

        self.add_formula_btn.clicked.connect(self._add_formula_to_selection)
        self.remove_formula_btn.clicked.connect(self._remove_formula_from_selection)
        self.apply_btn.clicked.connect(self._apply_selections)
        self.reset_btn.clicked.connect(self._reset_selections)
        self.close_btn.clicked.connect(self.reject)

    # --- METHOD MODIFIED to pass the correct context ---
    @pyqtSlot()
    def _on_selected_formula_changed(self):
        selected_items = self.selected_formulas_widget.selectedItems()
        self.remove_formula_btn.setEnabled(len(selected_items) > 0)

        if selected_items:
            self.formula_list_widget.clearSelection()
            batch_weight = self.locked_lot_data.get('batch_weight') if self.locked_lot_data else None
            self._update_material_preview(selected_items[0].text(), batch_weight)
        elif not self.formula_list_widget.selectedItems():
            self._update_material_preview(None, None)

    # --- METHOD MODIFIED with new signature ---
    def _update_material_preview(self, formula_id: str | None, batch_weight: Decimal | None):
        self.material_list_widget.setRowCount(0)
        self.material_list_widget.setHorizontalHeaderLabels(["Material Code", "Actual Qty (kg)"])
        total_actual_qty = Decimal("0.00")

        if formula_id and batch_weight is not None:
            materials = self.formula_details_cache.get(formula_id, [])
            total_ratio = sum(mat.get('qty', Decimal(0)) for mat in materials)

            if total_ratio > 0:
                self.material_list_widget.setRowCount(len(materials))
                for i, mat in enumerate(materials):
                    ratio = mat.get('qty', Decimal(0))
                    actual_qty = (ratio / total_ratio) * batch_weight

                    code_item = QTableWidgetItem(mat['mat_code'])
                    qty_item = QTableWidgetItem(f"{actual_qty:.2f}")
                    qty_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

                    self.material_list_widget.setItem(i, 0, code_item)
                    self.material_list_widget.setItem(i, 1, qty_item)

                    total_actual_qty += actual_qty

        else:
            self.material_list_widget.setHorizontalHeaderLabels(["Material Code", "Actual Qty (kg)"])

        self.total_material_qty_label.setText(f"{total_actual_qty:.2f} kg")



    def _create_center_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        details_group = QGroupBox("Locked Lot Details")
        details_layout = QFormLayout(details_group)
        self.locked_lot_num_label = QLabel("-")
        self.locked_prod_id_label = QLabel("-")
        self.locked_prod_code_label = QLabel("-")
        details_layout.addRow("Lot Number:", self.locked_lot_num_label)
        details_layout.addRow("Production ID:", self.locked_prod_id_label)
        details_layout.addRow("Product Code:", self.locked_prod_code_label)
        layout.addWidget(details_group)
        layout.addWidget(QLabel("2. Available Formulas"))
        formula_list_widget = QListWidget()
        add_formula_btn = QPushButton("Add Formula →");
        add_formula_btn.setEnabled(False)
        layout.addWidget(formula_list_widget)
        layout.addWidget(add_formula_btn)
        return panel, formula_list_widget, add_formula_btn

    # --- METHOD REWRITTEN to use data, not item ---
    def _update_locked_details_display(self):
        if self.locked_lot_data:
            self.locked_lot_num_label.setText(self.locked_lot_data.get("lot_num", "-"))
            self.locked_prod_id_label.setText(str(self.locked_lot_data.get("prod_id", "-")))
            self.locked_prod_code_label.setText(self.locked_lot_data.get("product_code", "-"))
        else:
            self.locked_lot_num_label.setText("-")
            self.locked_prod_id_label.setText("-")
            self.locked_prod_code_label.setText("-")

    @pyqtSlot()
    def _on_lot_selection_changed(self):
        self._fetch_and_display_formulas()

    # --- METHOD REWRITTEN to use data, not item ---
    @pyqtSlot(QListWidgetItem)
    def _on_lot_double_clicked(self, item: QListWidgetItem):
        if self.locked_lot_data and self.locked_lot_data['lot_num'] == item.text():
            QMessageBox.information(self, "Already Locked", f"Lot '{item.text()}' is already the locked lot.")
            return

        if self.formula_list_widget.count() == 0:
            QMessageBox.warning(self, "No Formulas Available",
                                f"Lot '{item.text()}' has no associated formulas and cannot be locked.")
            return

        if self.locked_lot_data:
            reply = QMessageBox.question(self, "Confirm Change",
                                         "This will clear your selected formulas and lock this new lot number. Proceed?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return

        self.locked_lot_data = item.data(Qt.ItemDataRole.UserRole)
        self.selected_formulas_widget.clear()
        self._update_locked_details_display()
        self.lot_list_widget.setCurrentItem(item)
        QMessageBox.information(self, "Lot Locked", f"Lot '{item.text()}' is now locked.")

        if self.formula_list_widget.count() == 1:
            item_to_move = self.formula_list_widget.takeItem(0)
            if item_to_move:
                self.selected_formulas_widget.addItem(item_to_move)
                self.selected_formulas_widget.setCurrentItem(item_to_move)

    @pyqtSlot()
    def _reset_selections(self):
        self.locked_lot_data = None
        self._update_locked_details_display()
        self.formula_list_widget.clear()
        self.selected_formulas_widget.clear()
        self._update_material_preview(None, None)

        if self.initial_product_code_lock is None and self.initial_customer_lock is None:
            self.locked_product_code = None
            self.locked_customer = None
            self.search_input.clear()
            self.apply_btn.setText("Apply Selections")

            # --- NEW: Hide the status label on a full reset ---
            self._update_filter_status_display()

        self.current_page = 1
        self.can_load_more = True
        self._load_lots()


    # --- METHOD REWRITTEN to use data, not item ---
    @pyqtSlot()
    def _add_formula_to_selection(self):
        previewed_items = self.lot_list_widget.selectedItems()
        if not previewed_items:
            QMessageBox.warning(self, "No Lot Selected", "Please select a lot number before adding formulas.")
            return

        previewed_item = previewed_items[0]
        previewed_data = previewed_item.data(Qt.ItemDataRole.UserRole)

        if self.locked_lot_data is None:
            if self.formula_list_widget.count() == 0:
                QMessageBox.warning(self, "No Formulas Available",
                                    "The selected lot has no formulas to add and cannot be locked.")
                return
            self.locked_lot_data = previewed_data
            self._update_locked_details_display()
            QMessageBox.information(self, "Lot Locked",
                                    f"Lot '{self.locked_lot_data['lot_num']}' is now locked because you added a formula.")
        elif self.locked_lot_data['lot_num'] != previewed_data['lot_num']:
            reply = QMessageBox.question(self, "Confirm Change",
                                         f"You are adding a formula for '{previewed_data['lot_num']}', but '{self.locked_lot_data['lot_num']}' is currently locked.\n\n"
                                         "Do you want to clear the previous selection and lock this new lot instead?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.selected_formulas_widget.clear()
                self.locked_lot_data = previewed_data
                self._update_locked_details_display()
            else:
                return

        selected_items = self.formula_list_widget.selectedItems()
        if not selected_items:
            return

        item_to_move = self.formula_list_widget.takeItem(self.formula_list_widget.row(selected_items[0]))
        if item_to_move:
            self.selected_formulas_widget.addItem(item_to_move)
            self.selected_formulas_widget.setCurrentItem(item_to_move)

            # --- THIS IS THE ONLY METHOD THAT IS CHANGED ---

    @pyqtSlot()
    def _apply_selections(self):
        if not self.locked_lot_data:
            QMessageBox.warning(self, "No Lot Locked",
                                "Please double-click a lot or add a formula to lock it before applying.")
            return

        # Final validation check (safety net for subsequent applies)
        if self.initial_product_code_lock and self.initial_customer_lock:
            current_lot_pc = self.locked_lot_data.get('product_code')
            current_customer = self.locked_lot_data.get('customer')
            if (current_lot_pc != self.initial_product_code_lock or
                    current_customer != self.initial_customer_lock):
                QMessageBox.critical(self, "Validation Error",
                                     f"The selected lot does not match the required Product Code and Customer.")
                return

        selected_formulas = [self.selected_formulas_widget.item(i).text() for i in
                             range(self.selected_formulas_widget.count())]
        if not selected_formulas:
            QMessageBox.warning(self, "No Formula Selected",
                                "Please add at least one formula for the locked lot number.")
            return

        locked_lot_text = self.locked_lot_data['lot_num']

        is_initial_apply = self.initial_product_code_lock is None

        # Step 1: Always send the data back to the main form
        selection_data = {"lots": [locked_lot_text], "formulas": selected_formulas}
        self.success_callback(selection_data)
        QMessageBox.information(self, "Success", f"Applied lot '{locked_lot_text}' to the main form.")

        # Step 2: If this was the first lot applied, update the dialog's permanent state and refresh its UI
        if is_initial_apply:
            # A. Set the permanent locks for the entire session
            self.initial_product_code_lock = self.locked_lot_data.get('product_code')
            self.initial_customer_lock = self.locked_lot_data.get('customer')

            # B. Update the current filter locks to match
            self.locked_product_code = self.initial_product_code_lock
            self.locked_customer = self.initial_customer_lock

            # C. Update the UI to reflect the new state
            self.apply_btn.setText("Apply Additional Lot")
            self._update_filter_status_display()  # This makes the label visible
            self.search_input.clear()
            self.search_input.setPlaceholderText("Search within filtered list...")

            # D. Force a reload of the lot list with the new, correct filters
            self.current_page = 1
            self.can_load_more = True
            self._load_lots()

        # Step 3: Always reset the temporary selections to prepare for the next addition
        self.selected_formulas_widget.clear()
        self.formula_list_widget.clear()
        self.locked_lot_data = None
        self._update_locked_details_display()
        self._update_material_preview(None, None)


    # --- METHOD MODIFIED to call preview with None ---
    def _fetch_and_display_formulas(self):
        self.formula_list_widget.clear()
        self._update_material_preview(None, None)
        self.add_formula_btn.setEnabled(False)
        selected_items = self.lot_list_widget.selectedItems()
        if not selected_items: return
        selected_lots = [item.text() for item in selected_items]
        try:
            details = self.controller.get_details_for_lots(selected_lots)
            all_formula_ids = sorted(details.keys())
            self.formula_details_cache.update(details)
            selected_ids = {self.selected_formulas_widget.item(i).text() for i in range(self.selected_formulas_widget.count())}
            available_ids = [fid for fid in all_formula_ids if fid not in selected_ids]
            self.formula_list_widget.addItems(available_ids)
            if len(available_ids) == 1:
                self.formula_list_widget.setCurrentRow(0)
        except Exception as e:
            print(f"Error fetching formula details: {e}")

    # --- METHOD MODIFIED to add the filter status label ---
    def _create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("1. Select Lot (Double-click to lock)"))

        # --- NEW: Create the filter status label ---
        self.filter_status_label = QLabel()
        self.filter_status_label.setStyleSheet("font-style: italic; color: #555;")
        self.filter_status_label.setWordWrap(True)
        layout.addWidget(self.filter_status_label)
        # --- END NEW ---

        search_input = QLineEdit();
        search_input.setPlaceholderText("Search within list...")
        lot_list_widget = QListWidget()
        layout.addWidget(search_input)
        layout.addWidget(lot_list_widget)
        return panel, search_input, lot_list_widget



    # --- NEW HELPER METHOD ---
    def _update_filter_status_display(self):
        """Updates the visibility and text of the filter status label."""
        if self.locked_product_code and self.locked_customer:
            self.filter_status_label.setText(
                f"Filtering by Code: '{self.locked_product_code}' and Customer: '{self.locked_customer}'."
            )
            self.filter_status_label.show()
        else:
            self.filter_status_label.hide()


    # --- THIS IS THE ONLY METHOD THAT IS CHANGED ---
    def _create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("3. Selected Formulas"))
        selected_formulas_widget = QListWidget()
        remove_formula_btn = QPushButton("Remove Selected Formula");
        remove_formula_btn.setEnabled(False)
        layout.addWidget(selected_formulas_widget, 1)
        layout.addWidget(remove_formula_btn)

        layout.addWidget(QLabel("Materials for Selected Formula"))

        # --- NEW: Use QTableWidget instead of QListWidget ---
        material_list_widget = QTableWidget()
        material_list_widget.setColumnCount(2)

        # --- FIX: Set proper column names (headers) ---
        material_list_widget.setHorizontalHeaderLabels(["Material Code", "Actual Qty (kg)"])

        # --- FIX: Set intelligent column resizing ---
        # Make the first column (Material Code) stretch to fill space
        material_list_widget.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        # Make the second column (Qty) resize to fit its content
        material_list_widget.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

        material_list_widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        material_list_widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        material_list_widget.verticalHeader().setVisible(False)
        layout.addWidget(material_list_widget, 2)
        # --- END FIX ---

        summary_layout = QHBoxLayout()
        summary_layout.addWidget(QLabel("<b>Total Qty:</b>"))
        summary_layout.addStretch()
        self.total_material_qty_label = QLabel("0.00 kg")
        self.total_material_qty_label.setStyleSheet("font-weight: bold;")
        summary_layout.addWidget(self.total_material_qty_label)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        layout.addLayout(summary_layout)

        return panel, selected_formulas_widget, remove_formula_btn, material_list_widget



    # --- METHOD MODIFIED to pass the correct customer filter ---
    def _load_lots(self):
        self.is_loading_more = True
        try:
            # --- FIX: Pass self.locked_customer to the controller ---
            lots = self.controller.get_lot_numbers_paginated(
                page=self.current_page, page_size=self.PAGE_SIZE,
                search_term=self.search_input.text(),
                product_code=self.locked_product_code,
                customer=self.locked_customer
            )
            # --- END FIX ---
            if self.current_page == 1: self.lot_list_widget.clear()
            if not lots or len(lots) < self.PAGE_SIZE: self.can_load_more = False
            for lot_data in lots:
                item = QListWidgetItem(lot_data['lot_num'])
                item.setData(Qt.ItemDataRole.UserRole, lot_data)
                self.lot_list_widget.addItem(item)
        finally:
            self.is_loading_more = False

    @pyqtSlot()
    def _trigger_search(self):
        self.current_page = 1
        self.can_load_more = True
        self.formula_list_widget.clear()
        self.material_list_widget.clear()
        self._load_lots()

    @pyqtSlot(int)
    def _on_scroll(self, value: int):
        scrollbar = self.lot_list_widget.verticalScrollBar()
        if not self.can_load_more or self.is_loading_more or value < scrollbar.maximum() * 0.9: return
        self.current_page += 1
        self._load_lots()

    # --- METHOD MODIFIED to pass the correct context ---
    @pyqtSlot()
    def _on_formula_selection_changed(self):
        selected_items = self.formula_list_widget.selectedItems()
        self.add_formula_btn.setEnabled(len(selected_items) > 0)

        if selected_items:
            self.selected_formulas_widget.clearSelection()
            previewed_lot_items = self.lot_list_widget.selectedItems()
            batch_weight = previewed_lot_items[0].data(Qt.ItemDataRole.UserRole).get('batch_weight') if previewed_lot_items else None
            self._update_material_preview(selected_items[0].text(), batch_weight)
        elif not self.selected_formulas_widget.selectedItems():
             self._update_material_preview(None, None)

    @pyqtSlot()
    def _remove_formula_from_selection(self):
        selected_items = self.selected_formulas_widget.selectedItems()
        if not selected_items: return
        item_to_move = self.selected_formulas_widget.takeItem(self.selected_formulas_widget.row(selected_items[0]))
        if item_to_move:
            self.formula_list_widget.addItem(item_to_move)
            self.formula_list_widget.sortItems()


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