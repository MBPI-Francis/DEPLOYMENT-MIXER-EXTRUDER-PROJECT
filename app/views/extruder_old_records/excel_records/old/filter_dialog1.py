from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QDialogButtonBox
)
from PyQt6.QtCore import Qt


class FilterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter")
        self.setFixedWidth(400)
        self.setObjectName("FilterDialog")  # Linked to style.css

        layout = QVBoxLayout(self)

        # --- Form Inputs ---
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(15)

        self.input_code = QLineEdit()
        self.input_code.setPlaceholderText("e.g. 100-200")

        self.input_customer = QLineEdit()
        self.input_customer.setPlaceholderText("Customer Name")

        self.input_machine = QLineEdit()
        self.input_machine.setPlaceholderText("Machine No")

        self.input_lot = QLineEdit()
        self.input_lot.setPlaceholderText("Lot Number")

        self.input_remarks = QLineEdit()
        self.input_remarks.setPlaceholderText("Remarks content")

        # Add rows to form
        self.form_layout.addRow("Product Code:", self.input_code)
        self.form_layout.addRow("Customer:", self.input_customer)
        self.form_layout.addRow("Machine No:", self.input_machine)
        self.form_layout.addRow("Lot Number:", self.input_lot)
        self.form_layout.addRow("Remarks:", self.input_remarks)

        layout.addLayout(self.form_layout)

        # --- Buttons ---
        btn_layout = QHBoxLayout()

        self.btn_clear = QPushButton("Clear Filters")
        self.btn_clear.setObjectName("EditDialogCancelButton")  # Gray styling
        self.btn_clear.clicked.connect(self.clear_inputs)

        self.btn_apply = QPushButton("Apply Filter")
        self.btn_apply.setObjectName("PrimaryDialogButton")  # Blue styling
        self.btn_apply.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)

        layout.addLayout(btn_layout)

    def get_filters(self):
        """Returns a dictionary of active filters."""
        filters = {}
        if self.input_code.text().strip():
            filters['code'] = self.input_code.text().strip()
        if self.input_customer.text().strip():
            filters['customer'] = self.input_customer.text().strip()
        if self.input_machine.text().strip():
            filters['machine'] = self.input_machine.text().strip()
        if self.input_lot.text().strip():
            filters['lot'] = self.input_lot.text().strip()
        if self.input_remarks.text().strip():
            filters['remarks'] = self.input_remarks.text().strip()
        return filters

    def clear_inputs(self):
        self.input_code.clear()
        self.input_customer.clear()
        self.input_machine.clear()
        self.input_lot.clear()
        self.input_remarks.clear()