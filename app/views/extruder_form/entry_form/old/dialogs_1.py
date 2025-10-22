# app/views/extruder_form/entry_form/widgets/dialogs.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QListWidget, QLineEdit,
    QWidget, QSplitter, QListWidgetItem, QPushButton, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from typing import Dict, List, Callable, Any

# Keep a reference to the OpsController class for type hinting
from ..ops import ExtruderOpsController


# class LotNumberDialog(QDialog):
#     PAGE_SIZE = 100
#
#     def __init__(self, controller: ExtruderOpsController, success_callback: Callable, parent=None,
#                  initial_product_code: str = None):
#         super().__init__(parent)
#         self.setWindowTitle("Select Lot Number(s) and Formula(s)")
#         self.setMinimumSize(950, 700)
#
#         # --- State Variables ---
#         self.controller = controller
#         self.success_callback = success_callback
#         self.current_page = 1
#         self.is_loading_more = False
#         self.can_load_more = True
#         # --- MODIFIED: Set the locked_product_code from the argument ---
#         self.locked_product_code = initial_product_code
#
#         # --- UI Setup ---
#         layout = QVBoxLayout(self)
#         splitter = QSplitter(Qt.Orientation.Horizontal)
#         layout.addWidget(splitter)
#
#         # Left Panel
#         left_panel, self.search_input, self.lot_list_widget = self._create_left_panel()
#         splitter.addWidget(left_panel)
#         # Center Panel
#         center_panel, self.formula_list_widget, self.add_formula_btn = self._create_center_panel()
#         splitter.addWidget(center_panel)
#         # Right Panel
#         right_panel, self.selected_formulas_widget, self.remove_formula_btn, self.material_list_widget = self._create_right_panel()
#         splitter.addWidget(right_panel)
#         splitter.setSizes([250, 250, 450])
#
#         # --- Dialog Buttons ---
#         self.button_box = QDialogButtonBox()
#         self.apply_btn = self.button_box.addButton("Apply Selections", QDialogButtonBox.ButtonRole.AcceptRole)
#         self.reset_btn = self.button_box.addButton("Reset", QDialogButtonBox.ButtonRole.DestructiveRole)
#         self.close_btn = self.button_box.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
#         layout.addWidget(self.button_box)
#
#         # --- Search Debouncing Timer ---
#         self.search_timer = QTimer(self);
#         self.search_timer.setSingleShot(True);
#         self.search_timer.setInterval(300)
#
#         # --- Connections ---
#         self._connect_signals()
#
#         # --- Initial Load ---
#         self._load_lots()
#
#         # --- NEW: Apply initial UI lock if code was provided on creation ---
#         if self.locked_product_code:
#             self.search_input.setPlaceholderText(f"Locked to Product Code: {self.locked_product_code}")
#             self.search_input.setEnabled(False)
#         # --- END NEW ---
#
#     def _create_left_panel(self):
#         panel = QWidget()
#         layout = QVBoxLayout(panel)
#         layout.addWidget(QLabel("1. Select Lot Numbers"))
#         search_input = QLineEdit();
#         search_input.setPlaceholderText("Search Lot Number...")
#         lot_list_widget = QListWidget();
#         lot_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
#         layout.addWidget(search_input)
#         layout.addWidget(lot_list_widget)
#         return panel, search_input, lot_list_widget
#
#     def _create_center_panel(self):
#         panel = QWidget()
#         layout = QVBoxLayout(panel)
#         layout.addWidget(QLabel("2. Available Formulas"))
#         formula_list_widget = QListWidget()
#         add_formula_btn = QPushButton("Add Formula →");
#         add_formula_btn.setEnabled(False)
#         layout.addWidget(formula_list_widget)
#         layout.addWidget(add_formula_btn)
#         return panel, formula_list_widget, add_formula_btn
#
#     def _create_right_panel(self):
#         panel = QWidget()
#         layout = QVBoxLayout(panel)
#         layout.addWidget(QLabel("3. Selected Formulas"))
#         selected_formulas_widget = QListWidget()
#         remove_formula_btn = QPushButton("Remove Selected Formula")
#         layout.addWidget(selected_formulas_widget, 1)
#         layout.addWidget(remove_formula_btn)
#         layout.addWidget(QLabel("Materials for Selected Formula"))
#         material_list_widget = QListWidget()
#         layout.addWidget(material_list_widget, 2)
#         return panel, selected_formulas_widget, remove_formula_btn, material_list_widget
#
#     def _connect_signals(self):
#         self.search_timer.timeout.connect(self._trigger_search)
#         self.search_input.textChanged.connect(self.search_timer.start)
#         self.lot_list_widget.verticalScrollBar().valueChanged.connect(self._on_scroll)
#         self.lot_list_widget.itemSelectionChanged.connect(self._on_lot_selection_changed)
#         self.formula_list_widget.itemSelectionChanged.connect(self._on_formula_selection_changed)
#         self.add_formula_btn.clicked.connect(self._add_formula_to_selection)
#         self.remove_formula_btn.clicked.connect(self._remove_formula_from_selection)
#         # Connect custom buttons
#         self.apply_btn.clicked.connect(self._apply_selections)
#         self.reset_btn.clicked.connect(self._reset_selections)
#         self.close_btn.clicked.connect(self.reject)
#
#     def _load_lots(self):
#         self.is_loading_more = True
#         try:
#             lots = self.controller.get_lot_numbers_paginated(
#                 page=self.current_page, page_size=self.PAGE_SIZE,
#                 search_term=self.search_input.text(),
#                 product_code=self.locked_product_code  # Pass the locked code
#             )
#             if self.current_page == 1: self.lot_list_widget.clear()
#             if not lots or len(lots) < self.PAGE_SIZE: self.can_load_more = False
#
#             for lot_data in lots:
#                 item = QListWidgetItem(lot_data['lot_num'])
#                 item.setData(Qt.ItemDataRole.UserRole, lot_data)
#                 self.lot_list_widget.addItem(item)
#         finally:
#             self.is_loading_more = False
#
#     @pyqtSlot()
#     def _apply_selections(self):
#         selected_lots = [item.text() for item in self.lot_list_widget.selectedItems()]
#         selected_formulas = [self.selected_formulas_widget.item(i).text() for i in
#                              range(self.selected_formulas_widget.count())]
#
#         if not selected_lots or not selected_formulas:
#             QMessageBox.warning(self, "Incomplete Selection", "Please select at least one lot number and one formula.")
#             return
#
#         # --- Feature 2: Lock Product Code and Filter ---
#         if self.locked_product_code is None:
#             first_item_data = self.lot_list_widget.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
#             self.locked_product_code = first_item_data['product_code']
#
#             # Now, trigger a full reload of the list with the filter applied
#             self.current_page = 1
#             self.can_load_more = True
#             self._load_lots()
#             self.search_input.setPlaceholderText(f"Searching for Product Code: {self.locked_product_code}")
#             self.search_input.setEnabled(False)  # Disable search once locked
#
#         # --- Feature 1: Callback and Success Message ---
#         selection_data = {"lots": selected_lots, "formulas": selected_formulas}
#         self.success_callback(selection_data)  # Update the main form
#         QMessageBox.information(self, "Success", "Selections have been applied to the main form.")
#
#     @pyqtSlot()
#     def _reset_selections(self):
#         # Clear state
#         self.locked_product_code = None
#         self.current_page = 1
#         self.can_load_more = True
#
#         # Clear UI
#         self.formula_list_widget.clear()
#         self.material_list_widget.clear()
#         self.selected_formulas_widget.clear()
#         self.search_input.clear()
#         self.search_input.setPlaceholderText("Search Lot Number...")
#         self.search_input.setEnabled(True)
#
#         # Reload initial data
#         self._load_lots()
#
#     @pyqtSlot()
#     def _trigger_search(self):
#         self.current_page = 1
#         self.can_load_more = True
#         self._load_lots()
#
#     @pyqtSlot(int)
#     def _on_scroll(self, value: int):
#         scrollbar = self.lotl_ist_widget.verticalScrollBar()
#         if not self.can_load_more or self.is_loading_more or value < scrollbar.maximum() * 0.9: return
#         self.current_page += 1
#         self._load_lots()
#
#     @pyqtSlot()
#     def _on_lot_selection_changed(self):
#         selected_lots = [item.text() for item in self.lot_list_widget.selectedItems()]
#         self.formula_list_widget.clear();
#         self.material_list_widget.clear();
#         self.add_formula_btn.setEnabled(False)
#         if not selected_lots: return
#
#         try:
#             details = self.controller.get_details_for_lots(selected_lots)
#             self.formula_list_widget.addItems(sorted(details.keys()))
#             self.formula_details_cache = details
#         except Exception as e:
#             print(f"Error fetching details: {e}")
#
#     # ... (selection helper methods are unchanged) ...
#     @pyqtSlot()
#     def _on_formula_selection_changed(self):
#         self.material_list_widget.clear()
#         selected_items = self.formula_list_widget.selectedItems()
#         self.add_formula_btn.setEnabled(len(selected_items) > 0)
#         if not selected_items: return
#         formula_id = selected_items[0].text()
#         materials = self.formula_details_cache.get(formula_id, [])
#         for mat in materials: self.material_list_widget.addItem(f"{mat['mat_code']}: {mat['qty']}")
#
#     @pyqtSlot()
#     def _add_formula_to_selection(self):
#         selected = self.formula_list_widget.selectedItems()
#         if not selected: return
#         formula_to_add = selected[0].text()
#         existing = [self.selected_formulas_widget.item(i).text() for i in range(self.selected_formulas_widget.count())]
#         if formula_to_add not in existing: self.selected_formulas_widget.addItem(formula_to_add)
#
#     @pyqtSlot()
#     def _remove_formula_from_selection(self):
#         for item in self.selected_formulas_widget.selectedItems():
#             self.selected_formulas_widget.takeItem(self.selected_formulas_widget.row(item))


# ... (GenericSubFormDialog is unchanged) ...

class LotNumberDialog(QDialog):
    PAGE_SIZE = 100

    def __init__(self, controller: ExtruderOpsController, success_callback: Callable, parent=None, initial_product_code: str = None):
        super().__init__(parent)
        self.setWindowTitle("Select Lot Number(s) and Formula(s)")
        self.setMinimumSize(950, 700)

        # --- State Variables ---
        self.controller = controller
        self.success_callback = success_callback
        self.current_page = 1
        self.is_loading_more = False
        self.can_load_more = True
        self.locked_product_code = initial_product_code
        self._is_programmatically_selecting = False

        # --- UI Setup ---
        layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal); layout.addWidget(splitter)
        left_panel, self.search_input, self.lot_list_widget = self._create_left_panel(); splitter.addWidget(left_panel)
        center_panel, self.formula_list_widget, self.add_formula_btn = self._create_center_panel(); splitter.addWidget(center_panel)
        right_panel, self.selected_formulas_widget, self.remove_formula_btn, self.material_list_widget = self._create_right_panel(); splitter.addWidget(right_panel)
        splitter.setSizes([250, 250, 450])

        self.button_box = QDialogButtonBox()
        self.apply_btn = self.button_box.addButton("Apply Selections", QDialogButtonBox.ButtonRole.AcceptRole)
        self.reset_btn = self.button_box.addButton("Reset", QDialogButtonBox.ButtonRole.DestructiveRole)
        self.close_btn = self.button_box.addButton("Close", QDialogButtonBox.ButtonRole.RejectRole)
        layout.addWidget(self.button_box)

        self.search_timer = QTimer(self); self.search_timer.setSingleShot(True); self.search_timer.setInterval(300)
        self._connect_signals()
        self._load_lots()

        if self.locked_product_code:
            self.search_input.setPlaceholderText(f"Locked to Product Code: {self.locked_product_code}")
            self.search_input.setEnabled(False)
            self.lot_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        else:
            # --- NEW: Start in single selection mode for the initial choice ---
            self.lot_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)

    # ... (_create panel methods are unchanged) ...
    def _create_left_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("1. Select Lot Number"))
        search_input = QLineEdit(); search_input.setPlaceholderText("Search Lot Number...")
        lot_list_widget = QListWidget()
        # Selection mode is now set in __init__
        layout.addWidget(search_input)
        layout.addWidget(lot_list_widget)
        return panel, search_input, lot_list_widget

    def _create_center_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("2. Available Formulas"))
        formula_list_widget = QListWidget()
        add_formula_btn = QPushButton("Add Formula →"); add_formula_btn.setEnabled(False)
        layout.addWidget(formula_list_widget)
        layout.addWidget(add_formula_btn)
        return panel, formula_list_widget, add_formula_btn

    def _create_right_panel(self):
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.addWidget(QLabel("3. Selected Formulas"))
        selected_formulas_widget = QListWidget()
        remove_formula_btn = QPushButton("Remove Selected Formula")
        layout.addWidget(selected_formulas_widget, 1)
        layout.addWidget(remove_formula_btn)
        layout.addWidget(QLabel("Materials for Selected Formula"))
        material_list_widget = QListWidget()
        layout.addWidget(material_list_widget, 2)
        return panel, selected_formulas_widget, remove_formula_btn, material_list_widget

    def _connect_signals(self):
        self.search_timer.timeout.connect(self._trigger_search)
        self.search_input.textChanged.connect(self.search_timer.start)
        self.lot_list_widget.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.lot_list_widget.itemSelectionChanged.connect(self._on_lot_selection_changed)
        self.formula_list_widget.itemSelectionChanged.connect(self._on_formula_selection_changed)
        self.add_formula_btn.clicked.connect(self._add_formula_to_selection)
        self.remove_formula_btn.clicked.connect(self._remove_formula_from_selection)
        self.apply_btn.clicked.connect(self._apply_selections)
        self.reset_btn.clicked.connect(self._reset_selections)
        self.close_btn.clicked.connect(self.reject)

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

    # --- METHOD MODIFIED to enforce single selection on initial apply ---
    @pyqtSlot()
    def _apply_selections(self):
        selected_lots = [item.text() for item in self.lot_list_widget.selectedItems()]
        selected_formulas = [self.selected_formulas_widget.item(i).text() for i in range(self.selected_formulas_widget.count())]

        if not selected_lots or not selected_formulas:
            QMessageBox.warning(self, "Incomplete Selection", "Please select at least one lot number and one formula.")
            return

        # --- LOGIC CHANGED ---
        # If we are making the initial selection
        if self.locked_product_code is None:
            if len(selected_lots) > 1:
                QMessageBox.critical(self, "Invalid Selection", "Please select only ONE lot number for the initial selection.")
                return

            # Lock to the product code of the single selected item
            first_item_data = self.lot_list_widget.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
            self.locked_product_code = first_item_data['product_code']

            # Now that we're locked, switch to multi-selection mode for adding more lots
            self.lot_list_widget.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
            self.search_input.setPlaceholderText(f"Adding lots for code: {self.locked_product_code}")
            self.search_input.setEnabled(False)

        # --- END LOGIC CHANGE ---

        selection_data = {"lots": selected_lots, "formulas": selected_formulas}
        self.success_callback(selection_data)
        QMessageBox.information(self, "Success", f"Applied {len(selected_lots)} lot(s) to the main form.")

    # --- METHOD MODIFIED to reset selection mode ---
    @pyqtSlot()
    def _reset_selections(self):
        self.locked_product_code = None
        self.current_page = 1
        self.can_load_more = True
        self.formula_list_widget.clear()
        self.material_list_widget.clear()
        self.selected_formulas_widget.clear()
        self.search_input.clear()
        self.search_input.setPlaceholderText("Search Lot Number...")
        self.search_input.setEnabled(True)
        # --- NEW: Reset selection mode to single ---
        self.lot_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self._load_lots()

    @pyqtSlot()
    def _trigger_search(self):
        self.current_page = 1
        self.can_load_more = True
        # A new search should not affect the selection mode
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
    def _on_lot_selection_changed(self):
        """Fetches formulas for the current selection. No filtering logic needed here anymore."""
        self.formula_list_widget.clear()
        self.material_list_widget.clear()
        self.add_formula_btn.setEnabled(False)

        selected_items = self.lot_list_widget.selectedItems()
        if not selected_items:
            return

        selected_lots = [item.text() for item in selected_items]
        try:
            details = self.controller.get_details_for_lots(selected_lots)
            self.formula_list_widget.addItems(sorted(details.keys()))
            self.formula_details_cache = details
        except Exception as e:
            print(f"Error fetching formula details: {e}")

    # ... (the rest of the methods are unchanged) ...
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
    def _add_formula_to_selection(self):
        selected = self.formula_list_widget.selectedItems()
        if not selected: return
        formula_to_add = selected[0].text()
        existing = [self.selected_formulas_widget.item(i).text() for i in range(self.selected_formulas_widget.count())]
        if formula_to_add not in existing: self.selected_formulas_widget.addItem(formula_to_add)

    @pyqtSlot()
    def _remove_formula_from_selection(self):
        for item in self.selected_formulas_widget.selectedItems():
            self.selected_formulas_widget.takeItem(self.selected_formulas_widget.row(item))

            
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