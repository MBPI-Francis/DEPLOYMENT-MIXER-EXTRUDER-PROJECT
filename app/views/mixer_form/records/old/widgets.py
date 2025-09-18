# app/views/mixer_report/widgets.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QDialogButtonBox, QLineEdit,
    QMessageBox, QCheckBox, QGroupBox, QDoubleSpinBox, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QComboBox, QDateEdit,
    QGridLayout, QPushButton
)
from PyQt6.QtCore import pyqtSignal, Qt, QDate
from PyQt6.QtGui import QFont
import pandas as pd
from typing import List


class FilterDialog(QDialog):
    """A dedicated, user-friendly dialog for filtering report data."""

    def __init__(self, machine_list: list, current_filters: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Mixer Report")
        self.setObjectName("FilterDialog")
        self.setMinimumWidth(500)

        main_layout = QVBoxLayout(self)
        form_layout = QGridLayout()
        form_layout.setSpacing(10)

        # --- Create all filter widgets ---
        self.date_from = QDateEdit(calendarPopup=True,
                                   date=current_filters.get("date_from", QDate.currentDate().addMonths(-1)))
        self.date_to = QDateEdit(calendarPopup=True, date=current_filters.get("date_to", QDate.currentDate()))
        self.ref_no = QLineEdit(str(current_filters.get("ref_no", "")))

        self.mc_name = QComboBox()
        self.mc_name.addItem("All Machines")
        self.mc_name.addItems(machine_list)
        if current_filters.get("mc_name"):
            self.mc_name.setCurrentText(current_filters["mc_name"])

        self.product_code = QLineEdit(current_filters.get("product_code", ""))
        self.lot_number = QLineEdit(current_filters.get("lot_number", ""))
        self.processed_by = QLineEdit(current_filters.get("processed_by", ""))
        self.cleaning_rm = QLineEdit(current_filters.get("cleaning_rm", ""))

        self.output_from = QDoubleSpinBox(buttonSymbols=QDoubleSpinBox.ButtonSymbols.NoButtons, maximum=999999,
                                          value=current_filters.get("output_qty_from", 0))
        self.output_to = QDoubleSpinBox(buttonSymbols=QDoubleSpinBox.ButtonSymbols.NoButtons, maximum=999999,
                                        value=current_filters.get("output_qty_to", 999999))

        self.cleaning_from = QDoubleSpinBox(buttonSymbols=QDoubleSpinBox.ButtonSymbols.NoButtons, maximum=999999,
                                            value=current_filters.get("cleaning_qty_from", 0))
        self.cleaning_to = QDoubleSpinBox(buttonSymbols=QDoubleSpinBox.ButtonSymbols.NoButtons, maximum=999999,
                                          value=current_filters.get("cleaning_qty_to", 999999))

        # --- Layout the form ---
        form_layout.addWidget(QLabel("<b>Date Range:</b>"), 0, 0)
        form_layout.addWidget(self.date_from, 0, 1)
        form_layout.addWidget(QLabel("to"), 0, 2)
        form_layout.addWidget(self.date_to, 0, 3)

        form_layout.addWidget(QLabel("<b>Ref No:</b>"), 1, 0)
        form_layout.addWidget(self.ref_no, 1, 1, 1, 3)

        form_layout.addWidget(QLabel("<b>Machine:</b>"), 2, 0)
        form_layout.addWidget(self.mc_name, 2, 1, 1, 3)

        form_layout.addWidget(QLabel("<b>Product Code:</b>"), 3, 0)
        form_layout.addWidget(self.product_code, 3, 1, 1, 3)

        form_layout.addWidget(QLabel("<b>Lot Number:</b>"), 4, 0)
        form_layout.addWidget(self.lot_number, 4, 1, 1, 3)

        form_layout.addWidget(QLabel("<b>Processed By:</b>"), 5, 0)
        form_layout.addWidget(self.processed_by, 5, 1, 1, 3)

        form_layout.addWidget(QLabel("<b>Cleaning RM:</b>"), 6, 0)
        form_layout.addWidget(self.cleaning_rm, 6, 1, 1, 3)

        form_layout.addWidget(QLabel("<b>Output QTY Range:</b>"), 7, 0)
        form_layout.addWidget(self.output_from, 7, 1)
        form_layout.addWidget(QLabel("to"), 7, 2)
        form_layout.addWidget(self.output_to, 7, 3)

        form_layout.addWidget(QLabel("<b>Cleaning QTY Range:</b>"), 8, 0)
        form_layout.addWidget(self.cleaning_from, 8, 1)
        form_layout.addWidget(QLabel("to"), 8, 2)
        form_layout.addWidget(self.cleaning_to, 8, 3)

        # --- Buttons ---
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Apply | QDialogButtonBox.StandardButton.Cancel)
        button_box.button(QDialogButtonBox.StandardButton.Apply).setObjectName("PrimaryDialogButton")
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        main_layout.addLayout(form_layout)
        main_layout.addWidget(button_box)

    def get_filters(self) -> dict:
        """Returns the user's selected filter settings."""
        filters = {
            "date_from": self.date_from.date().toPyDate(),
            "date_to": self.date_to.date().toPyDate(),
            "ref_no": int(self.ref_no.text()) if self.ref_no.text().isdigit() else None,
            "mc_name": self.mc_name.currentText() if self.mc_name.currentIndex() > 0 else None,
            "product_code": self.product_code.text().strip(),
            "lot_number": self.lot_number.text().strip(),
            "processed_by": self.processed_by.text().strip(),
            "cleaning_rm": self.cleaning_rm.text().strip(),
            "output_qty_from": self.output_from.value(),
            "output_qty_to": self.output_to.value(),
            "cleaning_qty_from": self.cleaning_from.value(),
            "cleaning_qty_to": self.cleaning_to.value(),
        }
        # Return only non-empty/non-default filters
        return {k: v for k, v in filters.items() if v}



class RemarksViewerDialog(QDialog):
    """A simple, read-only dialog to display long remarks text."""

    def __init__(self, remarks_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("View Remarks")
        self.setMinimumSize(400, 300)

        layout = QVBoxLayout(self)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(remarks_text)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)  # Close button acts as reject

        layout.addWidget(text_edit)
        layout.addWidget(button_box)


class RestoreDialog(QDialog):
    """A dialog for viewing and restoring soft-deleted records."""

    def __init__(self, deleted_data: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restore Deleted Records")
        self.setMinimumSize(800, 600)

        self.table = QTableWidget()
        self.setup_table(deleted_data)

        self.select_all_checkbox = QCheckBox("Select All")

        self.restore_button = QPushButton("Restore Selected")
        self.restore_button.setObjectName("PrimaryDialogButton")
        self.restore_button.setEnabled(False)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)

        bottom_layout = QHBoxLayout()
        bottom_layout.addWidget(self.select_all_checkbox)
        bottom_layout.addStretch()
        bottom_layout.addWidget(button_box)
        bottom_layout.addWidget(self.restore_button)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.table)
        main_layout.addLayout(bottom_layout)

        self.restore_button.clicked.connect(self.accept)
        button_box.rejected.connect(self.reject)
        self.select_all_checkbox.stateChanged.connect(self.toggle_select_all)
        self.table.itemChanged.connect(self.update_button_state)

    def setup_table(self, data: pd.DataFrame):
        self.table.setColumnCount(len(data.columns))  # +1 for checkbox
        self.table.setHorizontalHeaderLabels(["", "ID", "Date", "Ref No", "MC #", "Product Code", "Lot Number"])

        self.table.setRowCount(len(data))
        for i, row in data.iterrows():
            # Checkbox in the first column
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(i, 0, checkbox_item)

            # Data columns
            self.table.setItem(i, 1, QTableWidgetItem(str(row["detail_id"])))
            self.table.setItem(i, 2, QTableWidgetItem(str(row["Date"])))
            self.table.setItem(i, 3, QTableWidgetItem(str(row["Ref No"])))
            self.table.setItem(i, 4, QTableWidgetItem(str(row["MC #"])))
            self.table.setItem(i, 5, QTableWidgetItem(str(row["Product Code"])))
            self.table.setItem(i, 6, QTableWidgetItem(str(row["Lot Number"])))

        self.table.resizeColumnsToContents()

    def toggle_select_all(self, state: int):
        check_state = Qt.CheckState(state)
        for i in range(self.table.rowCount()):
            self.table.item(i, 0).setCheckState(check_state)

    def update_button_state(self):
        self.restore_button.setEnabled(len(self.get_selected_ids()) > 0)

    def get_selected_ids(self) -> List[int]:
        """Returns a list of the database IDs for the checked rows."""
        ids = []
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).checkState() == Qt.CheckState.Checked:
                ids.append(int(self.table.item(i, 1).text()))
        return ids


class SecureConfirmationDialog(QDialog):
    """A confirmation dialog that requires the user to type 'YES' to proceed."""

    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel(message))
        main_layout.addWidget(QLabel("<b>To confirm, please type 'YES' in the box below:</b>"))

        self.confirm_input = QLineEdit()
        main_layout.addWidget(self.confirm_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Confirm")
        self.ok_button.setEnabled(False)  # Start disabled

        main_layout.addWidget(self.button_box)

        self.confirm_input.textChanged.connect(self.check_input)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def check_input(self, text: str):
        """Enable the OK button only if the input is exactly 'YES'."""
        self.ok_button.setEnabled(text == "YES")