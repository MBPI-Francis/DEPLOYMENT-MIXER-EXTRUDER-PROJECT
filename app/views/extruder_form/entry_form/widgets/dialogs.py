# app/views/extruder_form/entry_form/widgets/dialogs.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QListWidget, QLineEdit,
    QWidget, QSplitter, QListWidgetItem, QPushButton, QMessageBox, QGroupBox, QFormLayout
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from typing import Dict, List, Callable, Any

from ..ops import ExtruderOpsController


class LotNumberDialog(QDialog):
    PAGE_SIZE = 100

    def __init__(self, controller: ExtruderOpsController, success_callback: Callable, parent=None,
                 initial_product_code: str = None):
        super().__init__(parent)
        self.setWindowTitle("Select Lot Number(s) and Formula(s)")
        self.setMinimumSize(950, 700)

        self.controller = controller
        self.success_callback = success_callback
        self.current_page = 1
        self.is_loading_more = False
        self.can_load_more = True
        self.locked_product_code = initial_product_code
        self.locked_lot_item = None

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

        if self.locked_product_code:
            self.search_input.setPlaceholderText(f"Adding lots for code: {self.locked_product_code}")
            self.search_input.setEnabled(False)
            self.lot_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        else:
            self.lot_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

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

    # --- NEW METHOD: Handles selection changes in the "Selected Formulas" list ---
    @pyqtSlot()
    def _on_selected_formula_changed(self):
        self.material_list_widget.clear()
        selected_items = self.selected_formulas_widget.selectedItems()

        # Also a good place to manage the enabled state of the remove button
        self.remove_formula_btn.setEnabled(len(selected_items) > 0)

        if not selected_items:
            return

        formula_id = selected_items[0].text()

        # We can safely use the cache because a formula can only get into this
        # list if its details were already fetched.
        materials = self.formula_details_cache.get(formula_id, [])
        for mat in materials:
            self.material_list_widget.addItem(f"{mat['mat_code']}: {mat['qty']}")

    # ... (All other methods remain unchanged) ...
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

    def _update_locked_details_display(self):
        if self.locked_lot_item:
            data = self.locked_lot_item.data(Qt.ItemDataRole.UserRole)
            self.locked_lot_num_label.setText(self.locked_lot_item.text())
            self.locked_prod_id_label.setText(str(data.get("prod_id", "-")))
            self.locked_prod_code_label.setText(data.get("product_code", "-"))
        else:
            self.locked_lot_num_label.setText("-")
            self.locked_prod_id_label.setText("-")
            self.locked_prod_code_label.setText("-")

    @pyqtSlot()
    def _on_lot_selection_changed(self):
        self._fetch_and_display_formulas()

    @pyqtSlot(QListWidgetItem)
    def _on_lot_double_clicked(self, item: QListWidgetItem):
        if self.locked_lot_item and self.locked_lot_item is not item:
            reply = QMessageBox.question(self, "Confirm Change",
                                         "This will clear your selected formulas and lock this new lot number. Proceed?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        self.locked_lot_item = item
        self.selected_formulas_widget.clear()
        self._update_locked_details_display()
        self.lot_list_widget.setCurrentItem(item)
        QMessageBox.information(self, "Lot Locked", f"Lot '{item.text()}' is now locked.")
        if self.formula_list_widget.count() == 1:
            item_to_move = self.formula_list_widget.takeItem(0)
            if item_to_move:
                self.selected_formulas_widget.addItem(item_to_move)

    @pyqtSlot()
    def _reset_selections(self):
        self.locked_product_code = None
        self.locked_lot_item = None
        self._update_locked_details_display()
        self.current_page = 1
        self.can_load_more = True
        self.formula_list_widget.clear()
        self.material_list_widget.clear()
        self.selected_formulas_widget.clear()
        self.search_input.clear()
        self.search_input.setPlaceholderText("Search Lot Number...")
        self.search_input.setEnabled(True)
        self.lot_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._load_lots()

    @pyqtSlot()
    def _add_formula_to_selection(self):
        if not self.locked_lot_item:
            QMessageBox.warning(self, "No Lot Locked", "Please double-click a lot to lock it before adding formulas.")
            return
        previewed_items = self.lot_list_widget.selectedItems()
        if not previewed_items or previewed_items[0] is not self.locked_lot_item:
            QMessageBox.warning(self, "Selection Mismatch",
                                f"You can only add formulas for the locked lot: {self.locked_lot_item.text()}.\n\n"
                                "Please single-click the locked lot number again before adding formulas.")
            return
        selected_items = self.formula_list_widget.selectedItems()
        if not selected_items:
            return
        item_to_move = self.formula_list_widget.takeItem(self.formula_list_widget.row(selected_items[0]))
        if item_to_move:
            self.selected_formulas_widget.addItem(item_to_move)

    @pyqtSlot()
    def _apply_selections(self):
        if not self.locked_lot_item:
            QMessageBox.warning(self, "No Lot Locked",
                                "Please double-click a lot to lock it, then add at least one formula to apply.")
            return
        selected_formulas = [self.selected_formulas_widget.item(i).text() for i in
                             range(self.selected_formulas_widget.count())]
        if not selected_formulas:
            QMessageBox.warning(self, "No Formula Selected",
                                "Please add at least one formula for the locked lot number.")
            return
        locked_lot_text = self.locked_lot_item.text()
        if self.locked_product_code is None:
            item_data = self.locked_lot_item.data(Qt.ItemDataRole.UserRole)
            self.locked_product_code = item_data['product_code']
            self.lot_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            self.search_input.setPlaceholderText(f"Adding lots for code: {self.locked_product_code}")
            self.search_input.setEnabled(False)
        selection_data = {"lots": [locked_lot_text], "formulas": selected_formulas}
        self.success_callback(selection_data)
        QMessageBox.information(self, "Success", f"Applied lot '{locked_lot_text}' to the main form.")

    def _fetch_and_display_formulas(self):
        self.formula_list_widget.clear()
        self.material_list_widget.clear()
        self.add_formula_btn.setEnabled(False)
        selected_items = self.lot_list_widget.selectedItems()
        if not selected_items: return
        selected_lots = [item.text() for item in selected_items]
        try:
            details = self.controller.get_details_for_lots(selected_lots)
            formula_ids = sorted(details.keys())
            self.formula_list_widget.addItems(formula_ids)
            self.formula_details_cache = details
        except Exception as e:
            print(f"Error fetching formula details: {e}")

    def _create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("1. Select Lot (Double-click to lock)"))
        search_input = QLineEdit();
        search_input.setPlaceholderText("Search Lot Number...")
        lot_list_widget = QListWidget()
        layout.addWidget(search_input)
        layout.addWidget(lot_list_widget)
        return panel, search_input, lot_list_widget

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
        material_list_widget = QListWidget()
        layout.addWidget(material_list_widget, 2)
        return panel, selected_formulas_widget, remove_formula_btn, material_list_widget

    def _load_lots(self):
        self.is_loading_more = True
        try:
            lots = self.controller.get_lot_numbers_paginated(
                page=self.current_page, page_size=self.PAGE_SIZE,
                search_term=self.search_input.text(),
                product_code=self.locked_product_code
            )
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

    @pyqtSlot()
    def _on_formula_selection_changed(self):
        self.material_list_widget.clear()
        selected_items = self.formula_list_widget.selectedItems()
        self.add_formula_btn.setEnabled(len(selected_items) > 0)
        if not selected_items: return
        formula_id = selected_items[0].text()
        materials = self.formula_details_cache.get(formula_id, [])
        for mat in materials: self.material_list_widget.addItem(f"{mat['mat_code']}: {mat['qty']}")

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