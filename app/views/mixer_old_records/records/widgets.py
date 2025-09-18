# app/views/mixer_old_records/records/widgets.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QDoubleSpinBox, QHBoxLayout, QLabel,
    QTimeEdit, QGridLayout, QWidget, QPushButton, QDateEdit, QComboBox,
    QMessageBox, QTableWidget, QTableWidgetItem, QCheckBox, QDialogButtonBox,
    QHeaderView, QTextEdit, QFrame, QCompleter
)
from PyQt6.QtCore import Qt, QTime, QDate, pyqtSignal
from typing import List
import pandas as pd

# app/views/mixer_old_records/records/widgets.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLineEdit, QDoubleSpinBox, QHBoxLayout, QLabel,
    QTimeEdit, QGridLayout, QWidget, QPushButton, QDateEdit, QComboBox,
    QMessageBox, QTableWidget, QTableWidgetItem, QCheckBox, QDialogButtonBox,
    QHeaderView
)
from PyQt6.QtCore import Qt, QTime, QDate
from typing import List
import pandas as pd

from app.database.legacy_ops import search_all_product_codes, search_all_lot_numbers, get_all_lot_numbers_for_product
from app.validators.lot_validator import LotNumberValidator
from app.widgets.smart_combo_box import SmartComboBox

class FilterDialog(QDialog):
    """
    A dedicated, user-friendly dialog for filtering report data.
    FINAL WORKING VERSION.
    """

    perform_search_requested = pyqtSignal(object, object, str)

    def __init__(self, machine_list: list, initial_data: dict, current_filters: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Filter Mixer Report")
        self.setObjectName("FilterDialog")
        self.setMinimumWidth(500)

        # --- Define default values for comparison ---
        self.MAX_QTY = 999999.0

        main_layout = QVBoxLayout(self)
        form_layout = QGridLayout()
        form_layout.setSpacing(15) # A bit more spacing for a cleaner look
        # --- Create all filter widgets ---
        self.date_from = QDateEdit(calendarPopup=True)
        self.date_to = QDateEdit(calendarPopup=True, date=current_filters.get("date_to", QDate.currentDate()))
        self.ref_no = QLineEdit(str(current_filters.get("ref_no", "")))

        # self.mc_name = QComboBox()

        # self.mc_name.addItems(machine_list)
        # if current_filters.get("mc_name"):
        #     self.mc_name.setCurrentText(current_filters["mc_name"])

        self.mc_name = SmartComboBox()

        self.mc_name.populate_initial(["All"] + machine_list)
        self.mc_name.setCurrentText(current_filters.get("mc_name", "All"))

        # self.product_code = QLineEdit(current_filters.get("product_code", ""))
        self.product_code = SmartComboBox()
        self.product_code.populate_initial(initial_data.get("product_codes", []))
        self.product_code.setCurrentText(current_filters.get("product_code", ""))

        self.lot_number = SmartComboBox()
        self.lot_number.populate_initial(["<blank>"] + initial_data.get("lot_numbers", []))
        self.lot_number.setCurrentText(current_filters.get("lot_number", ""))
        # self.lot_number = QLineEdit(current_filters.get("lot_number", ""))
        self.processed_by = QLineEdit(current_filters.get("processed_by", ""))
        # self.cleaning_rm = QLineEdit(current_filters.get("cleaning_rm", ""))


        self.output_from = QDoubleSpinBox(buttonSymbols=QDoubleSpinBox.ButtonSymbols.NoButtons, maximum=self.MAX_QTY, value=current_filters.get("output_qty_from", 0.0))
        self.output_to = QDoubleSpinBox(buttonSymbols=QDoubleSpinBox.ButtonSymbols.NoButtons, maximum=self.MAX_QTY, value=current_filters.get("output_qty_to", self.MAX_QTY))

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

        form_layout.addWidget(QLabel("<b>Output QTY Range:</b>"), 6, 0)
        form_layout.addWidget(self.output_from, 6, 1)
        form_layout.addWidget(QLabel("to"), 6, 2)
        form_layout.addWidget(self.output_to, 6, 3)

        main_layout.addLayout(form_layout)

        # --- MODIFICATION START: Explicit Buttons and Direct Connections ---
        # Instead of QDialogButtonBox, we create our own layout and buttons.
        # This gives us direct control and ensures the connections work.
        button_layout = QHBoxLayout()
        button_layout.addStretch(1) # Pushes buttons to the right

        self.cancel_button = QPushButton("Cancel")
        self.apply_button = QPushButton("Apply")
        self.apply_button.setObjectName("PrimaryDialogButton") # Apply styling

        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)

        # Connect the 'clicked' signal of each button directly to the
        # dialog's built-in 'accept' and 'reject' methods. This is foolproof.
        self.apply_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)

        main_layout.addLayout(button_layout)
        # --- MODIFICATION END ---


        self._connect_live_search()

    def _connect_live_search(self):
        """Connects signals to the DELEGATION handler."""
        self.product_code.full_search_requested.connect(
            lambda term: self.perform_search_requested.emit(self.product_code, search_all_product_codes, term)
        )
        self.lot_number.full_search_requested.connect(
            lambda term: self.perform_search_requested.emit(self.lot_number, search_all_lot_numbers, term)
        )


    def get_filters(self) -> dict:
        """
        Builds a clean dictionary of only the filters that the user has actively set.
        This logic is correct and remains unchanged from the last good version.
        """
        filters = {}

        # Date range is always active.
        filters["date_from"] = self.date_from.date().toPyDate()
        filters["date_to"] = self.date_to.date().toPyDate()

        # Handle text and combo box fields
        if self.ref_no.text().strip():
            filters["ref_no"] = self.ref_no.text().strip()


        if self.mc_name.currentIndex() != 0 and self.mc_name.currentText() != "All": # 0 is "All Machines"
            filters["mc_name"] = self.mc_name.currentText()

        if self.product_code.text().strip():
            filters["product_code"] = self.product_code.text().strip()
        if self.lot_number.text().strip():
            filters["lot_number"] = self.lot_number.text().strip()
        if self.processed_by.text().strip():
            filters["processed_by"] = self.processed_by.text().strip()

        # Handle numeric ranges correctly
        if self.output_from.value() > 0.0:
            filters["output_qty_from"] = self.output_from.value()
        if self.output_to.value() < self.MAX_QTY:
            filters["output_qty_to"] = self.output_to.value()

        return filters



class EditRecordDialog(QDialog):
    """
    REDESIGNED & STABLE: This dialog uses a standard QDialog window and
    a QGridLayout to perfectly match the user-provided GUI layout.
    """
    perform_search_requested = pyqtSignal(object, object, str)

    def __init__(self, record_data: pd.Series, machine_list: list, initial_data: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Record (ID: {record_data.get('detail_id')})")
        self.setObjectName("EditRecordDialog")
        self.setMinimumWidth(550)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        grid = QGridLayout()
        grid.setVerticalSpacing(15)
        grid.setHorizontalSpacing(15)

        # --- Create all input widgets ---

        # Date widget is correct
        record_date = QDate.fromString(str(record_data.get("Date", "")).split(" ")[0], "yyyy-MM-dd")
        self.date_edit = QDateEdit(calendarPopup=True, date=record_date)



        # --- (Existing widget creation is unchanged) ---
        self.mc_name = SmartComboBox()
        self.mc_name.set_mandatory(True)
        self.mc_name.populate_initial(machine_list)
        self.mc_name.setCurrentText(str(record_data.get("MC #", "")))

        self.product_code = SmartComboBox()
        self.product_code.set_mandatory(True)
        self.product_code.populate_initial(initial_data.get("product_codes", []))
        self.product_code.setCurrentText(str(record_data.get("Product Code", "")))

        self.lot_number = SmartComboBox()
        self.lot_number.set_mandatory(True)
        self.lot_number.populate_initial(initial_data.get("lot_numbers", []))
        self.lot_number.setCurrentText(str(record_data.get("Lot Number", "")))

        # --- MODIFICATION: 'operator' (Processed By) is now a QComboBox ---
        self.processed_by = QComboBox()
        self.processed_by.setEditable(True)  # This is key for auto-suggestion
        self.processed_by.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.processed_by.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.processed_by.completer().setFilterMode(Qt.MatchFlag.MatchContains)

        # Populate the combo box with the list of operators from initial_data
        self.processed_by.addItems(initial_data.get("operators", []))
        self.processed_by.setCurrentText(str(record_data.get("Processed By", "")))
        # --- END OF MODIFICATION ---


        self.process_start = QTimeEdit(
            time=QTime.fromString(str(record_data.get("Processing Start", "00:00")), "HH:mm"))
        self.process_start.setDisplayFormat("HH:mm")
        self.process_end = QTimeEdit(time=QTime.fromString(str(record_data.get("Processing End", "00:00")), "HH:mm"))
        self.process_end.setDisplayFormat("HH:mm")


        self.qty = None
        if record_data.get("Output QTY", 0.0) == '':
            self.qty = 0.00

        else:
            self.qty = record_data.get("Output QTY", 0.0)

        self.output_qty = QDoubleSpinBox(maximum=999999, decimals=2, value=float(self.qty))




        # --- MODIFICATION: Add new widgets to the layout ---
        # --- General Details Section ---
        grid.addWidget(self._create_labeled_widget("Date", self.date_edit), 0, 0)


        # Add a separator
        grid.addWidget(self._create_section_header("Mixer Details"), 1, 0, 1, 3)

        grid.addWidget(self._create_labeled_widget("Machine", self.mc_name), 2, 0)
        grid.addWidget(self._create_labeled_widget("Code", self.product_code), 2, 1)
        grid.addWidget(self._create_labeled_widget("Lot #", self.lot_number), 2, 2)

        # --- Processing Details Section ---
        grid.addWidget(self._create_section_header("Processing Details"), 3, 0, 1, 3)
        grid.addWidget(self._create_labeled_widget("Processed by", self.processed_by), 4, 0, 1, 3)
        grid.addWidget(self._create_labeled_widget("Time Start", self.process_start), 5, 0)
        grid.addWidget(self._create_labeled_widget("Time End", self.process_end), 5, 1)
        grid.addWidget(self._create_labeled_widget("Output QTY", self.output_qty), 5, 2)

        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(2, 1)
        main_layout.addLayout(grid)

        # --- Buttons and Connections (no changes needed here) ---
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("CANCEL")
        self.save_button = QPushButton("SAVE")
        self.cancel_button.setObjectName("EditDialogCancelButton")
        self.save_button.setObjectName("EditDialogSaveButton")
        button_layout.addWidget(self.cancel_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        main_layout.addLayout(button_layout)
        self.save_button.clicked.connect(self.on_save_clicked)
        self.cancel_button.clicked.connect(self.reject)
        self._connect_search_signals()



    def _create_labeled_widget(self, label_text: str, widget: QWidget) -> QWidget:
        """Helper function to create a container with a label above a widget."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        label = QLabel(label_text)
        label.setStyleSheet("color: #343a40;")  # A softer black for the label text
        layout.addWidget(label)
        layout.addWidget(widget)
        return container

    def _connect_search_signals(self):
        self.product_code.full_search_requested.connect(
            lambda term: self.on_search_delegation_requested(self.product_code, search_all_product_codes, term)
        )
        self.lot_number.full_search_requested.connect(
            lambda term: self.on_search_delegation_requested(self.lot_number, search_all_lot_numbers, term)
        )

    def on_search_delegation_requested(self, combo_box, search_function, term):
        self.perform_search_requested.emit(combo_box, search_function, term)

    def validate_data(self) -> bool:
        """
        Performs comprehensive validation on all fields. This version allows
        Lot Number and Processed By to be blank (null).
        """
        # --- Header Field Validation (This is correct) ---
        if not self.date_edit.date().isValid() or self.date_edit.date() > QDate.currentDate():
            QMessageBox.warning(self, "Validation Error", "A valid date (today or in the past) must be selected.")
            self.date_edit.setFocus()
            return False

        # --- Detail Field Validation ---
        # Machine and Product Code are still mandatory
        if not self.mc_name.is_valid():
            QMessageBox.warning(self, "Validation Error", "A valid Machine must be selected.")
            self.mc_name.setFocus()
            return False

        if not self.product_code.is_valid():
            QMessageBox.warning(self, "Validation Error", "Product Code is invalid or empty.")
            self.product_code.setFocus()
            return False

        # --- MODIFIED: ADVANCED LOT NUMBER VALIDATION (Now Optional) ---
        product_code = self.product_code.text()
        lot_no_to_validate = self.lot_number.text().strip()

        # Only perform validation IF the user has entered a lot number.
        if lot_no_to_validate:
            session = self.parent().Session()
            try:
                existing_lots_tuples = get_all_lot_numbers_for_product(session, product_code)
                db_lots_for_product = [item for item, in existing_lots_tuples]

                if not db_lots_for_product:
                    QMessageBox.warning(self, "Validation Error",
                                        f"Cannot validate Lot Number because no lot numbers exist for Product '{product_code}'.")
                    self.product_code.setFocus()
                    return False

                lot_validator = LotNumberValidator(db_lots_for_product)
                is_valid, error_message = lot_validator.validate_lot_entry(lot_no_to_validate, product_code)

                if not is_valid:
                    QMessageBox.warning(self, "Validation Error", error_message)
                    self.lot_number.setFocus()
                    return False
            finally:
                session.close()
        # --- END OF MODIFICATION ---

        # --- MODIFIED: Processed By is now OPTIONAL ---
        # The check 'if not self.processed_by.text().strip()' has been removed.
        # This field can now be blank.

        # --- (Rest of the validation logic is the same) ---
        # if self.output_qty.value() <= 0:
        #     QMessageBox.warning(self, "Validation Error", "Output Qty must be greater than 0.")
        #     self.output_qty.setFocus()
        #     return False

        if self.process_start.time() > QTime(0, 0) and self.process_end.time() == QTime(0, 0):
            QMessageBox.warning(self, "Validation Error", "Processing End Time cannot be 00:00 if a Start Time is set.")
            self.process_end.setFocus()
            return False

        # --- (Cleaning details validation is not needed for Old Records) ---

        return True  # All checks passed

    def on_save_clicked(self):
        if self.validate_data(): self.accept()

    def get_updated_data(self) -> dict:
        return {
            # --- NEW Header fields ---
            "date": self.date_edit.date().toPyDate(),

            # --- Existing Detail fields ---
            "MC #": self.mc_name.currentText(),
            "product_code": self.product_code.text().strip(),
            "lot_no": self.lot_number.text().strip(),
            "time_start": self.process_start.time().toPyTime(),
            "time_end": self.process_end.time().toPyTime(),
            "operator": self.processed_by.currentText().strip() or None,
            "quantity": self.output_qty.value(),
        }

    def _create_section_header(self, title: str) -> QWidget:
        """Helper to create a styled section header with a line underneath."""
        # The container for the whole section header
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 10, 0, 0)  # Add some space above and below
        layout.setSpacing(5)

        # The title label
        label = QLabel(title)
        label.setStyleSheet("font-size: 11pt; font-weight: bold; color: #000;")

        # The horizontal line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setObjectName("SeparatorLine")  # Use the style we defined in CSS

        # Add them to the layout
        layout.addWidget(label)
        layout.addWidget(line)

        return container


class SecureConfirmationDialog(QDialog):
    def __init__(self, title: str, message: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(QLabel(message))
        main_layout.addWidget(QLabel("<b>To confirm, type 'YES':</b>"))
        self.confirm_input = QLineEdit()
        main_layout.addWidget(self.confirm_input)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Confirm")
        self.ok_button.setEnabled(False)
        main_layout.addWidget(self.button_box)
        self.confirm_input.textChanged.connect(lambda text: self.ok_button.setEnabled(text == "YES"))
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)


class RestoreDialog(QDialog):
    def __init__(self, deleted_data: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restore Deleted Records")
        self.setMinimumSize(1000, 600)
        self.data = deleted_data;
        self.table = QTableWidget()
        self.setup_table(self.data)
        self.select_all_checkbox = QCheckBox("Select All")
        self.restore_button = QPushButton("Restore Selected")
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
        self.select_all_checkbox.stateChanged.connect(
            lambda state: [self.table.item(i, 0).setCheckState(Qt.CheckState(state)) for i in
                           range(self.table.rowCount())])
        self.table.itemChanged.connect(lambda: self.restore_button.setEnabled(len(self.get_selected_ids()) > 0))

    def setup_table(self, data: pd.DataFrame):
        display_columns = [col for col in data.columns if col != 'detail_id']
        self.table.setColumnCount(len(display_columns) + 1)
        self.table.setHorizontalHeaderLabels([""] + display_columns)
        self.table.setRowCount(len(data))
        for i, row in data.iterrows():
            cb_item = QTableWidgetItem()
            cb_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            cb_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(i, 0, cb_item)
            for j, col_name in enumerate(display_columns):
                cell_data = row.get(col_name)
                item = QTableWidgetItem(str(cell_data) if pd.notna(cell_data) else "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, j + 1, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def get_selected_ids(self) -> List[int]:
        return [int(self.data.iloc[i]['detail_id']) for i in range(self.table.rowCount()) if
                self.table.item(i, 0).checkState() == Qt.CheckState.Checked]