# app/views/extruder_old_records/excel_records/filter_dialog.py
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QComboBox, QListView
)
from PyQt6.QtCore import Qt, QTimer
from sqlalchemy.orm import sessionmaker

from .ops import ExtruderExcelRecordsOps


class LazyComboBox(QComboBox):
    """
    A ComboBox that loads items from the DB as you scroll or type.
    """

    def __init__(self, session_factory: sessionmaker, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(10)

        # Internal State
        self.skip_next_text_change = False
        self.current_offset = 0
        self.limit = 20
        self.has_more = True
        self.filter_text = ""

        # View Setup for Scroll Detection
        self.view_list = QListView()
        self.setView(self.view_list)
        self.view_list.verticalScrollBar().valueChanged.connect(self.on_scroll)

        # Search Debounce
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.reload_data)

        self.lineEdit().textEdited.connect(self.on_text_edited)

        # Initial Load
        self.reload_data()

    def on_text_edited(self, text):
        self.filter_text = text
        self.search_timer.start(300)  # Debounce typing

    def on_scroll(self, value):
        if not self.has_more:
            return

        # Check if near bottom
        if value >= self.view_list.verticalScrollBar().maximum() - 2:
            self.load_next_batch()

    def reload_data(self):
        """Resets and loads first batch based on text."""
        self.clear()
        self.current_offset = 0
        self.has_more = True

        # Add the typed text as a temporary item if it's not empty,
        # so the user doesn't lose what they typed while we query
        if self.filter_text:
            self.addItem(self.filter_text)
            self.setCurrentText(self.filter_text)

        self.fetch_items()

    def load_next_batch(self):
        self.current_offset += self.limit
        self.fetch_items()

    def fetch_items(self):
        with self.Session() as session:
            codes = ExtruderExcelRecordsOps.get_distinct_codes(
                session, self.filter_text, self.limit, self.current_offset
            )

            if len(codes) < self.limit:
                self.has_more = False

            for code in codes:
                # Avoid duplicates if the user typed text is already in list
                if self.findText(code) == -1:
                    self.addItem(code)


class FilterDialog(QDialog):
    def __init__(self, session_factory: sessionmaker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter")
        self.setFixedWidth(450)
        self.setObjectName("FilterDialog")

        layout = QVBoxLayout(self)

        # --- Form ---
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(12)

        # 1. Product Code (Lazy ComboBox)
        self.input_code = LazyComboBox(session_factory)
        self.input_code.setPlaceholderText("Type to search code...")
        self.input_code.setFixedHeight(30)

        # 2. Standard Text Fields
        self.input_customer = QLineEdit()
        self.input_customer.setPlaceholderText("Customer Name")

        self.input_machine = QLineEdit()
        self.input_machine.setPlaceholderText("Machine No")

        self.input_lot = QLineEdit()
        self.input_lot.setPlaceholderText("Lot Number")

        self.input_remarks = QLineEdit()
        self.input_remarks.setPlaceholderText("Remarks content")

        # 3. New Columns
        self.input_screw = QLineEdit()
        self.input_screw.setPlaceholderText("e.g. A, B, Standard")

        self.input_resin = QLineEdit()
        self.input_resin.setPlaceholderText("Resin Type")

        self.input_rpm = QLineEdit()
        self.input_rpm.setPlaceholderText("RPM Value")

        self.input_date = QLineEdit()
        self.input_date.setPlaceholderText("Date string match")

        # Add Rows
        self.form_layout.addRow("Product Code:", self.input_code)
        self.form_layout.addRow("Customer:", self.input_customer)
        self.form_layout.addRow("Machine No:", self.input_machine)
        self.form_layout.addRow("Lot Number:", self.input_lot)
        self.form_layout.addRow("Screw Config:", self.input_screw)
        self.form_layout.addRow("Resin Used:", self.input_resin)
        self.form_layout.addRow("RPM:", self.input_rpm)
        self.form_layout.addRow("Date:", self.input_date)
        self.form_layout.addRow("Remarks:", self.input_remarks)

        layout.addLayout(self.form_layout)

        # --- Buttons ---
        btn_layout = QHBoxLayout()

        self.btn_clear = QPushButton("Clear Filters")
        self.btn_clear.setObjectName("EditDialogCancelButton")
        self.btn_clear.clicked.connect(self.clear_inputs)

        self.btn_apply = QPushButton("Apply Filter")
        self.btn_apply.setObjectName("PrimaryDialogButton")
        self.btn_apply.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)

        layout.addLayout(btn_layout)

    def get_filters(self):
        filters = {}
        # For Combobox, we take currentText(). Note: If user typed something not in list, we still take it.
        code_val = self.input_code.currentText().strip()
        if code_val: filters['code'] = code_val

        if self.input_customer.text().strip(): filters['customer'] = self.input_customer.text().strip()
        if self.input_machine.text().strip(): filters['machine'] = self.input_machine.text().strip()
        if self.input_lot.text().strip(): filters['lot'] = self.input_lot.text().strip()
        if self.input_remarks.text().strip(): filters['remarks'] = self.input_remarks.text().strip()

        # New Fields
        if self.input_screw.text().strip(): filters['screw_config'] = self.input_screw.text().strip()
        if self.input_resin.text().strip(): filters['resin_used'] = self.input_resin.text().strip()
        if self.input_rpm.text().strip(): filters['rpm'] = self.input_rpm.text().strip()
        if self.input_date.text().strip(): filters['date'] = self.input_date.text().strip()

        return filters

    def clear_inputs(self):
        self.input_code.clear()
        self.input_code.reload_data()  # Reset combo
        self.input_customer.clear()
        self.input_machine.clear()
        self.input_lot.clear()
        self.input_remarks.clear()
        self.input_screw.clear()
        self.input_resin.clear()
        self.input_rpm.clear()
        self.input_date.clear()