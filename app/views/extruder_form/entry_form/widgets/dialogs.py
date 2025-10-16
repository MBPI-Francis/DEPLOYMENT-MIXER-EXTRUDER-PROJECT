# app/views/extruder_form/entry_form/widgets/dialogs.py

from decimal import Decimal
from typing import Dict, List, Callable

from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QDialogButtonBox, QListWidget, QLineEdit,
    QWidget, QSplitter, QListWidgetItem, QPushButton, QMessageBox, QGroupBox, QFormLayout, QHBoxLayout, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView
)

from ..ops import ExtruderOpsController


class LotNumberDialog(QDialog):
    """
    A simplified dialog for selecting lot numbers.
    It displays lot details and the associated materials directly from TblProd02.
    It supports an initial "unfiltered" state and a subsequent "filtered" state
    for adding more lots with the same product code and customer.
    """
    PAGE_SIZE = 100

    def __init__(self, controller: ExtruderOpsController,
                 success_callback: Callable,
                 parent=None,
                 initial_product_code: str = None,
                 initial_customer: str = None):
        super().__init__(parent)
        self.setWindowTitle("Select Lot Number")
        self.setMinimumSize(800, 600)

        # --- Core Components & State ---
        self.controller = controller
        self.success_callback = success_callback
        self.current_page = 1
        self.is_loading_more = False
        self.can_load_more = True

        # Permanent filters passed in from the main form, defining the dialog's mode.
        self.initial_product_code_lock = initial_product_code
        self.initial_customer_lock = initial_customer

        # --- UI Setup ---
        self._setup_ui()
        self._connect_signals()
        self._load_lots()
        self._initial_ui_state()

    # --------------------------------------------------------------------------
    # UI Creation & Initialization
    # --------------------------------------------------------------------------

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
        search_input.setPlaceholderText("Search Lot Number...")
        lot_list_widget = QListWidget()
        lot_list_widget.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
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
        details_layout.addRow("Production ID:", self.prod_id_label)
        details_layout.addRow("Product Code:", self.prod_code_label)
        details_layout.addRow("Customer:", self.customer_label)
        details_layout.addRow("Formula No:", self.formula_id_label)
        layout.addWidget(details_group)

        layout.addWidget(QLabel("Materials Used"))
        self.material_table = QTableWidget()
        self.material_table.setColumnCount(2)
        self.material_table.setHorizontalHeaderLabels(["Material Code", "Qty (kg)"])
        self.material_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.material_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.material_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.material_table.verticalHeader().setVisible(False)
        layout.addWidget(self.material_table)

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

        # The 'accepted' signal is automatically fired by the button with the AcceptRole
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.reset_btn.clicked.connect(self._reset_selections)

    # --------------------------------------------------------------------------
    # Core Logic and Event Handlers
    # --------------------------------------------------------------------------

    def accept(self):
        """
        Overrides the default OK/Apply button behavior. This is the single
        point of action for applying a selection.
        """
        selected_items = self.lot_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a lot number to apply.")
            return

        # The source of truth is always the currently selected item's data
        current_lot_data = selected_items[0].data(Qt.ItemDataRole.UserRole)

        is_initial_apply = self.initial_product_code_lock is None

        # Pass the data back to the main form
        self.success_callback([current_lot_data])

        # We don't need the success message here, as the main form will handle the refresh.
        # If it's the first apply, the dialog will be closed and reopened by the main form.
        # If it's a subsequent apply, we just close this instance.
        super().accept()  # This closes the dialog with a success code.

    @pyqtSlot()
    def _on_lot_selection_changed(self):
        """Updates the details and material preview when a lot is single-clicked."""
        selected_items = self.lot_list_widget.selectedItems()
        self.material_table.setRowCount(0)
        self.total_material_qty_label.setText("0.00 kg")

        if not selected_items:
            self._update_details_display(None)
            return

        item_data = selected_items[0].data(Qt.ItemDataRole.UserRole)
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
        """Resets the dialog state. Respects the permanent filter if it exists."""
        self.lot_list_widget.clearSelection()

        if self.initial_product_code_lock is None:
            self.search_input.clear()
            self._update_filter_status_display()

        self.current_page = 1
        self.can_load_more = True
        self._load_lots()

    # --------------------------------------------------------------------------
    # Data Loading and Helpers
    # --------------------------------------------------------------------------

    def _load_lots(self):
        """Queries the controller for lots using the current filters and populates the list."""
        self.is_loading_more = True
        try:
            lots = self.controller.get_lot_numbers_paginated(
                page=self.current_page,
                page_size=self.PAGE_SIZE,
                search_term=self.search_input.text(),
                product_code=self.initial_product_code_lock,
                customer=self.initial_customer_lock
            )
            if self.current_page == 1: self.lot_list_widget.clear()
            if not lots or len(lots) < self.PAGE_SIZE: self.can_load_more = False
            for lot_data in lots:
                item = QListWidgetItem(lot_data['lot_num'])
                item.setData(Qt.ItemDataRole.UserRole, lot_data)
                self.lot_list_widget.addItem(item)
        finally:
            self.is_loading_more = False

    def _update_details_display(self, data: Dict | None):
        """Updates the 'Lot Details' group box."""
        if data:
            self.prod_id_label.setText(str(data.get("prod_id", "-")))
            self.prod_code_label.setText(data.get("product_code", "-")))
            self.customer_label.setText(data.get("customer", "-")))
            self.formula_id_label.setText(str(data.get("formula_id", "-")))
            else:
            self.prod_id_label.setText("-")
            self.prod_code_label.setText("-")
            self.customer_label.setText("-")
            self.formula_id_label.setText("-")

    def _update_filter_status_display(self):
        """Updates the visibility and text of the filter status label."""
        if self.initial_product_code_lock and self.initial_customer_lock:
            self.filter_status_label.setText(
                f"Filtering by Code: '{self.initial_product_code_lock}' and Customer: '{self.initial_customer_lock}'."
            )
            self.filter_status_label.show()
        else:
            self.filter_status_label.hide()

    @pyqtSlot()
    def _trigger_search(self):
        """Resets pagination and reloads lots based on the current search term."""
        self.current_page = 1
        self.can_load_more = True
        self._load_lots()

    @pyqtSlot(int)
    def _on_scroll(self, value: int):
        """Loads the next page of lots when the user scrolls to the bottom."""
        scrollbar = self.lot_list_widget.verticalScrollBar()
        if not self.can_load_more or self.is_loading_more or value < scrollbar.maximum() * 0.9: return
        self.current_page += 1
        self._load_lots()

        