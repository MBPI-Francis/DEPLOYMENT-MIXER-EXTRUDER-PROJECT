import os
import pandas as pd
# app/views/mixer_form/widgets/widgets.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QDialogButtonBox, QLineEdit,
    QMessageBox, QDoubleSpinBox, QHBoxLayout, QLabel,
    QComboBox, QDateEdit, QGridLayout, QPushButton, QTextEdit, QTableWidgetItem, QCheckBox, QTableWidget, QTimeEdit,
    QFormLayout, QWidget, QFrame, QHeaderView, QStyle, QStyleOptionButton
)
from PyQt6.QtCore import Qt, QDate, QTime, pyqtSlot, pyqtSignal, QRect
from typing import List, Callable

from sqlalchemy.orm import sessionmaker

from app.database.legacy_ops import search_all_raw_materials, search_all_lot_numbers, search_all_product_codes, \
    get_all_lot_numbers_for_product
from app.validators.lot_validator import LotNumberValidator
from app.widgets import ModifiedComboBox
from app.widgets.smart_combo_box import SmartComboBox


# (Keep the other classes like RemarksViewerDialog, RestoreDialog, etc., as they are)


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

        self.MAX_QTY = 999999.0

        # --- CRITICAL STEP: Load and Convert Dates ---
        # 1. Look for 'date_from' in current_filters. If not found, default to 1 month ago.
        # 2. Look for 'date_to' in current_filters. If not found, default to today.

        py_date_from = current_filters.get("date_from")
        py_date_to = current_filters.get("date_to")

        # Conversion: datetime.date -> QDate
        if py_date_from:
            q_date_from = QDate(py_date_from.year, py_date_from.month, py_date_from.day)
        else:
            q_date_from = QDate.currentDate().addMonths(-1)

        if py_date_to:
            q_date_to = QDate(py_date_to.year, py_date_to.month, py_date_to.day)
        else:
            q_date_to = QDate.currentDate()

        main_layout = QVBoxLayout(self)
        form_layout = QGridLayout()
        form_layout.setSpacing(15)

        # --- Create widgets and APPLY the converted dates ---
        self.date_from = QDateEdit(calendarPopup=True)
        self.date_from.setDate(q_date_from)  # This prevents the 2000-01-01 reset

        self.date_to = QDateEdit(calendarPopup=True)
        self.date_to.setDate(q_date_to)  # This keeps the "To" date saved

        self.ref_no = QLineEdit(str(current_filters.get("ref_no", "")))

        # self.mc_name = QComboBox()

        # self.mc_name.addItems(machine_list)
        # if current_filters.get("mc_name"):
        #     self.mc_name.setCurrentText(current_filters["mc_name"])

        self.mc_name = SmartComboBox()
        self.mc_name.populate_initial(["All"] + machine_list)
        self.mc_name.setCurrentText(current_filters.get("mc_name", ""))

        # self.product_code = QLineEdit(current_filters.get("product_code", ""))
        self.product_code = SmartComboBox()
        self.product_code.populate_initial(initial_data.get("product_codes", []))
        self.product_code.setCurrentText(current_filters.get("product_code", ""))

        self.lot_number = SmartComboBox()
        self.lot_number.populate_initial(initial_data.get("lot_numbers", []))
        self.lot_number.setCurrentText(current_filters.get("lot_number", ""))

        # self.lot_number = QLineEdit(current_filters.get("lot_number", ""))
        self.processed_by = QLineEdit(current_filters.get("processed_by", ""))
        # self.cleaning_rm = QLineEdit(current_filters.get("cleaning_rm", ""))

        self.cleaning_rm = SmartComboBox()
        self.cleaning_rm.populate_initial(initial_data.get("raw_materials", []))
        self.cleaning_rm.setCurrentText(current_filters.get("cleaning_rm", ""))


        self.output_from = QDoubleSpinBox(buttonSymbols=QDoubleSpinBox.ButtonSymbols.NoButtons, maximum=self.MAX_QTY, value=current_filters.get("output_qty_from", 0.0))
        self.output_to = QDoubleSpinBox(buttonSymbols=QDoubleSpinBox.ButtonSymbols.NoButtons, maximum=self.MAX_QTY, value=current_filters.get("output_qty_to", self.MAX_QTY))
        self.cleaning_from = QDoubleSpinBox(buttonSymbols=QDoubleSpinBox.ButtonSymbols.NoButtons, maximum=self.MAX_QTY, value=current_filters.get("cleaning_qty_from", 0.0))
        self.cleaning_to = QDoubleSpinBox(buttonSymbols=QDoubleSpinBox.ButtonSymbols.NoButtons, maximum=self.MAX_QTY, value=current_filters.get("cleaning_qty_to", self.MAX_QTY))

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
        if self.ref_no.text().strip().isdigit():
            filters["ref_no"] = int(self.ref_no.text().strip())
        if self.mc_name.currentIndex() != 0: # 0 is "All Machines"
            filters["mc_name"] = self.mc_name.currentText()
        if self.product_code.text().strip():
            filters["product_code"] = self.product_code.text().strip()
        if self.lot_number.text().strip():
            filters["lot_number"] = self.lot_number.text().strip()
        if self.processed_by.text().strip():
            filters["processed_by"] = self.processed_by.text().strip()
        if self.cleaning_rm.text().strip():
            filters["cleaning_rm"] = self.cleaning_rm.text().strip()

        # Handle numeric ranges correctly
        if self.output_from.value() > 0.0:
            filters["output_qty_from"] = self.output_from.value()
        if self.output_to.value() < self.MAX_QTY:
            filters["output_qty_to"] = self.output_to.value()

        if self.cleaning_from.value() > 0.0:
            filters["cleaning_qty_from"] = self.cleaning_from.value()
        if self.cleaning_to.value() < self.MAX_QTY:
            filters["cleaning_qty_to"] = self.cleaning_to.value()

        return filters



class RemarksViewerDialog(QDialog):
    """A simple, read-only dialog to display long remarks text."""

    def __init__(self, remarks_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("View Remarks")
        self.setMinimumWidth(450)
        self.setModal(True)

        layout = QVBoxLayout(self)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(remarks_text)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        button_box.rejected.connect(self.reject)  # Close button acts as reject

        layout.addWidget(text_edit)
        layout.addWidget(button_box)


# --- NEW: Custom Header Class to handle the "Select All" Checkbox ---
class HeaderViewWithCheckbox(QHeaderView):
    select_all_state_changed = pyqtSignal(Qt.CheckState)

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.isOn = Qt.CheckState.Unchecked

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        super().paintSection(painter, rect, logicalIndex)
        painter.restore()

        if logicalIndex == 0:
            option = QStyleOptionButton()
            option.rect = QRect(3, 5, 20, 20)  # Center it a bit
            option.state = QStyle.StateFlag.State_Enabled
            if self.isOn == Qt.CheckState.Checked:
                option.state |= QStyle.StateFlag.State_On
            elif self.isOn == Qt.CheckState.PartiallyChecked:
                option.state |= QStyle.StateFlag.State_NoChange  # This draws the square for partial check
            else:
                option.state |= QStyle.StateFlag.State_Off

            self.style().drawControl(QStyle.ControlElement.CE_CheckBox, option, painter)

    def mousePressEvent(self, event):
        if self.logicalIndexAt(event.pos()) == 0:
            if self.isOn == Qt.CheckState.Checked:
                self.isOn = Qt.CheckState.Unchecked
            else:
                self.isOn = Qt.CheckState.Checked
            self.updateSection(0)
            self.select_all_state_changed.emit(self.isOn)
        else:
            super().mousePressEvent(event)

    def set_check_state(self, state: Qt.CheckState):
        """Allows external control of the checkbox state."""
        if self.isOn != state:
            self.isOn = state
            self.updateSection(0)


class RestoreDialog(QDialog):
    """
    CORRECTED & ADVANCED: Uses a custom QHeaderView to safely implement the
    'Select All' checkbox, fixing the previous crash.
    """

    def __init__(self, deleted_data: pd.DataFrame, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Restore Deleted Records")
        self.setMinimumSize(1100, 700)
        self.data = deleted_data

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search deleted records...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter_table)
        main_layout.addWidget(self.search_input)

        self.table = QTableWidget()
        # --- MODIFICATION: Set the custom header BEFORE setting up the table ---
        self.custom_header = HeaderViewWithCheckbox()
        self.table.setHorizontalHeader(self.custom_header)

        self.setup_table(self.data)
        main_layout.addWidget(self.table)

        footer_layout = QHBoxLayout()
        close_button = QPushButton("Close")
        self.restore_button = QPushButton("Restore Selected")
        self.restore_button.setObjectName("PrimaryDialogButton")
        self.restore_button.setEnabled(False)
        footer_layout.addWidget(close_button)
        footer_layout.addStretch()
        footer_layout.addWidget(self.restore_button)
        main_layout.addLayout(footer_layout)

        # --- Connections ---
        self.restore_button.clicked.connect(self.accept)
        close_button.clicked.connect(self.reject)
        # Connect the custom header's signal to our toggle logic
        self.custom_header.select_all_state_changed.connect(self.toggle_select_all)
        self.table.itemChanged.connect(self.update_ui_state)

    def setup_table(self, data: pd.DataFrame):
        display_columns = [col for col in data.columns if col != 'detail_id']
        self.table.setColumnCount(len(display_columns) + 1)
        # The first header is now managed by our custom class
        self.table.setHorizontalHeaderLabels([""] + display_columns)

        self.table.setRowCount(len(data))
        for i, row in data.iterrows():
            checkbox_item = QTableWidgetItem()
            checkbox_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            checkbox_item.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(i, 0, checkbox_item)
            for j, col_name in enumerate(display_columns):
                cell_text = str(row[col_name]) if pd.notna(row[col_name]) else ""
                item = QTableWidgetItem(cell_text)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, j + 1, item)

        header = self.table.horizontalHeader()  # Get the custom header
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        for i in range(1, self.table.columnCount()):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        try:
            product_code_index = display_columns.index("Product Code") + 1
            header.setSectionResizeMode(product_code_index, QHeaderView.ResizeMode.Stretch)
        except ValueError:
            header.setStretchLastSection(True)
        self.table.resizeColumnsToContents()

    def filter_table(self, search_text: str):
        search_text = search_text.lower()
        for i in range(self.table.rowCount()):
            match_found = False
            for j in range(1, self.table.columnCount()):
                item = self.table.item(i, j)
                if item and search_text in item.text().lower():
                    match_found = True
                    break
            self.table.setRowHidden(i, not match_found)
        self.update_ui_state()

    def toggle_select_all(self, check_state: Qt.CheckState):
        """Checks or unchecks all VISIBLE items in the table."""
        self.table.blockSignals(True)
        for i in range(self.table.rowCount()):
            if not self.table.isRowHidden(i):
                self.table.item(i, 0).setCheckState(check_state)
        self.table.blockSignals(False)
        self.update_ui_state()

    def update_ui_state(self):
        """Updates the state of the restore button and the custom header checkbox."""
        visible_rows = [i for i in range(self.table.rowCount()) if not self.table.isRowHidden(i)]
        if not visible_rows:
            self.restore_button.setEnabled(False)
            self.custom_header.set_check_state(Qt.CheckState.Unchecked)
            return

        checked_count = sum(1 for i in visible_rows if self.table.item(i, 0).checkState() == Qt.CheckState.Checked)

        self.restore_button.setEnabled(checked_count > 0)

        # Update header checkbox state
        if checked_count == len(visible_rows):
            self.custom_header.set_check_state(Qt.CheckState.Checked)
        elif checked_count > 0:
            self.custom_header.set_check_state(Qt.CheckState.PartiallyChecked)
        else:
            self.custom_header.set_check_state(Qt.CheckState.Unchecked)

    def get_selected_ids(self) -> List[int]:
        ids = []
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).checkState() == Qt.CheckState.Checked:
                detail_id = int(self.data.iloc[i]['detail_id'])
                ids.append(detail_id)
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

        # --- MODIFICATION: Correctly populate shift times from the data ---
        # Get the time objects from the pandas Series. pd.NaT is a "Not a Time" null value.
        shift_start_val = record_data.get("Shift Time Start")
        shift_end_val = record_data.get("Shift Time End")

        # Convert to QTime, handling nulls gracefully by defaulting to 00:00
        shift_start_qtime = QTime(shift_start_val.hour, shift_start_val.minute) if pd.notna(shift_start_val) else QTime(
            0, 0)
        shift_end_qtime = QTime(shift_end_val.hour, shift_end_val.minute) if pd.notna(shift_end_val) else QTime(0, 0)

        self.shift_start = QTimeEdit(time=shift_start_qtime)
        self.shift_start.setDisplayFormat("HH:mm")
        self.shift_end = QTimeEdit(time=shift_end_qtime)
        self.shift_end.setDisplayFormat("HH:mm")
        # --- END MODIFICATION ---

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



        self.processed_by = SmartComboBox()
        self.processed_by.set_mandatory(True)
        self.processed_by.populate_initial(initial_data.get("operators", []))
        self.processed_by.setCurrentText(str(record_data.get("Processed By", "")))


        self.process_start = QTimeEdit(
            time=QTime.fromString(str(record_data.get("Processing Start", "00:00")), "HH:mm"))
        self.process_start.setDisplayFormat("HH:mm")
        self.process_end = QTimeEdit(time=QTime.fromString(str(record_data.get("Processing End", "00:00")), "HH:mm"))
        self.process_end.setDisplayFormat("HH:mm")
        self.output_qty = QDoubleSpinBox(maximum=999999, decimals=2, value=float(record_data.get("Output QTY", 0.0)))
        self.cleaning_rm = SmartComboBox()
        self.cleaning_rm.populate_initial(initial_data.get("raw_materials", []))
        self.cleaning_rm.setCurrentText(str(record_data.get("Cleaning RM", "")))
        self.cleaning_qty = QDoubleSpinBox(maximum=999999, decimals=2,
                                           value=float(record_data.get("Cleaning QTY", 0.0)))
        self.cleaning_start = QTimeEdit(
            time=QTime.fromString(str(record_data.get("Cleaning Start", "00:00")), "HH:mm"))
        self.cleaning_start.setDisplayFormat("HH:mm")
        self.cleaning_end = QTimeEdit(time=QTime.fromString(str(record_data.get("Cleaning End", "00:00")), "HH:mm"))
        self.cleaning_end.setDisplayFormat("HH:mm")
        self.remarks = QTextEdit(str(record_data.get("Remarks", "")))

        # --- MODIFICATION: Add new widgets to the layout ---
        # --- General Details Section ---
        grid.addWidget(self._create_labeled_widget("Date", self.date_edit), 0, 0)
        grid.addWidget(self._create_labeled_widget("Shift Time Start", self.shift_start), 0, 1)
        grid.addWidget(self._create_labeled_widget("Shift Time End", self.shift_end), 0, 2)

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

        # --- Cleaning Details Section ---
        grid.addWidget(self._create_section_header("Cleaning Details"), 6, 0, 1, 3)
        grid.addWidget(self._create_labeled_widget("Cleaning RM", self.cleaning_rm), 7, 0, 1, 3)
        grid.addWidget(self._create_labeled_widget("Time Start", self.cleaning_start), 8, 0)
        grid.addWidget(self._create_labeled_widget("Time End", self.cleaning_end), 8, 1)
        grid.addWidget(self._create_labeled_widget("Cleaning QTY", self.cleaning_qty), 8, 2)

        grid.addWidget(self._create_labeled_widget("Remarks", self.remarks), 9, 0, 1, 3)

        grid.setColumnStretch(0, 1);
        grid.setColumnStretch(1, 1);
        grid.setColumnStretch(2, 1)
        main_layout.addLayout(grid)

        # --- Buttons and Connections (no changes needed here) ---
        button_layout = QHBoxLayout();
        self.cancel_button = QPushButton("CANCEL");
        self.save_button = QPushButton("SAVE");
        self.cancel_button.setObjectName("EditDialogCancelButton");
        self.save_button.setObjectName("EditDialogSaveButton");
        button_layout.addWidget(self.cancel_button);
        button_layout.addStretch();
        button_layout.addWidget(self.save_button);
        main_layout.addLayout(button_layout)
        self.save_button.clicked.connect(self.on_save_clicked);
        self.cancel_button.clicked.connect(self.reject);
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
        self.cleaning_rm.full_search_requested.connect(
            lambda term: self.on_search_delegation_requested(self.cleaning_rm, search_all_raw_materials, term)
        )

    def on_search_delegation_requested(self, combo_box, search_function, term):
        self.perform_search_requested.emit(combo_box, search_function, term)

    def validate_data(self) -> bool:
        """
        Performs comprehensive validation on all fields, including advanced
        lot number validation against the database.
        """
        # --- Header Field Validation (as before) ---
        if not self.date_edit.date().isValid() or self.date_edit.date() > QDate.currentDate():
            QMessageBox.warning(self, "Validation Error", "A valid date (today or in the past) must be selected.")
            self.date_edit.setFocus();
            return False
        if self.shift_start.time() > QTime(0, 0) and self.shift_end.time() == QTime(0, 0):
            QMessageBox.warning(self, "Validation Error", "Shift End Time cannot be 00:00 if a Start Time is set.")
            self.shift_end.setFocus();
            return False
        if self.shift_end.time() > QTime(0, 0) and self.shift_start.time() == QTime(0, 0):
            QMessageBox.warning(self, "Validation Error", "Shift Start Time must be set if an End Time is entered.")
            self.shift_start.setFocus();
            return False

        # --- Detail Field Validation ---
        if not self.mc_name.is_valid():
            QMessageBox.warning(self, "Validation Error", "A valid Machine must be selected.")
            self.mc_name.setFocus();
            return False

        if not self.product_code.is_valid():
            QMessageBox.warning(self, "Validation Error", "Product Code is invalid or empty.")
            self.product_code.setFocus();
            return False

        # --- NEW: ADVANCED LOT NUMBER VALIDATION ---
        session = self.parent().Session()  # Get a session from the parent widget
        try:
            product_code = self.product_code.text()
            lot_no_to_validate = self.lot_number.text()

            if not lot_no_to_validate.strip():
                QMessageBox.warning(self, "Validation Error", "Lot Number cannot be empty.")
                self.lot_number.setFocus()
                return False

            # Fetch the list of valid lot numbers for the selected product
            existing_lots_tuples = get_all_lot_numbers_for_product(session, product_code)
            db_lots_for_product = [item for item, in existing_lots_tuples]

            if not db_lots_for_product:
                QMessageBox.warning(self, "Validation Error",
                                    f"Cannot validate Lot Number because no lot numbers exist for Product '{product_code}'.")
                self.product_code.setFocus()
                return False

            # Use the new validator class
            lot_validator = LotNumberValidator(db_lots_for_product)
            is_valid, error_message = lot_validator.validate_lot_entry(lot_no_to_validate, product_code)

            if not is_valid:
                QMessageBox.warning(self, "Validation Error", error_message)
                self.lot_number.setFocus()
                return False

        finally:
            session.close()
        # --- END OF NEW LOT NUMBER VALIDATION ---

        # --- (Rest of the validation logic is the same) ---
        if not self.processed_by.text().strip():
            QMessageBox.warning(self, "Validation Error", "Processed By cannot be empty.")
            self.processed_by.setFocus();
            return False
        if self.output_qty.value() <= 0:
            QMessageBox.warning(self, "Validation Error", "Output Qty must be greater than 0.")
            self.output_qty.setFocus();
            return False
        if self.process_start.time() > QTime(0, 0) and self.process_end.time() == QTime(0, 0):
            QMessageBox.warning(self, "Validation Error", "Processing End Time cannot be 00:00 if a Start Time is set.")
            self.process_end.setFocus();
            return False

        rm_code = self.cleaning_rm.text().strip();
        rm_qty = self.cleaning_qty.value()
        if (rm_code and rm_qty <= 0):
            QMessageBox.warning(self, "Validation Error", "Cleaning Qty must be > 0 if a Cleaning RM is selected.")
            self.cleaning_qty.setFocus();
            return False
        if (rm_qty > 0 and not rm_code):
            QMessageBox.warning(self, "Validation Error", "A Cleaning RM must be selected if Cleaning Qty is entered.")
            self.cleaning_rm.setFocus();
            return False
        if self.cleaning_start.time() > QTime(0, 0) and self.cleaning_end.time() == QTime(0, 0):
            QMessageBox.warning(self, "Validation Error", "Cleaning End Time cannot be 00:00 if a Start Time is set.")
            self.cleaning_end.setFocus();
            return False

        return True  # All checks passed

    def on_save_clicked(self):
        if self.validate_data(): self.accept()

    def get_updated_data(self) -> dict:
        return {
            # --- NEW Header fields ---
            "date": self.date_edit.date().toPyDate(),
            "time_start": self.shift_start.time().toPyTime(),
            "time_end": self.shift_end.time().toPyTime(),

            # --- Existing Detail fields ---
            "MC #": self.mc_name.currentText(),
            "product_code": self.product_code.text().strip(),
            "lot_no": self.lot_number.text().strip(),
            "process_time_start": self.process_start.time().toPyTime(),
            "process_time_end": self.process_end.time().toPyTime(),
            "processed_by": self.processed_by.text().strip(),
            "output_qty": self.output_qty.value(),
            "cleaning_time_start": self.cleaning_start.time().toPyTime(),
            "cleaning_time_end": self.cleaning_end.time().toPyTime(),
            "cleaning_rm_code": self.cleaning_rm.text().strip(),
            "cleaning_qty": self.cleaning_qty.value(),
            "remarks": self.remarks.toPlainText().strip()
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


