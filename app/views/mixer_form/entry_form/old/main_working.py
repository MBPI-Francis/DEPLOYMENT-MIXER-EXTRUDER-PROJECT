# app/views/mixer_form/main.py

import os
import re
from datetime import datetime, time, date, timedelta
from typing import Type, Callable, List
from pydantic import ValidationError

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QMessageBox, QLineEdit, QGroupBox, QLabel, QDateEdit, QGridLayout,
    QSpinBox, QDoubleSpinBox, QTextEdit, QScrollArea, QFrame, QApplication,
    QSpacerItem, QSizePolicy, QDialog, QCompleter, QComboBox
)
from PyQt6.QtCore import pyqtSignal, Qt, QDate, QEvent, QThread, pyqtSlot, QStringListModel
from PyQt6.QtGui import QAction, QKeyEvent
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import qtawesome as qta

from app.validators.lot_validator import LotNumberValidator
# --- Corrected Imports ---
from app.widgets import ModifiedComboBox
from app.widgets.lot_combo_box import LotComboBox
from app.widgets.smart_combo_box import SmartComboBox # Import our new widget
from app.database.legacy_ops import (
    get_initial_lot_numbers, get_initial_product_codes,
    search_all_lot_numbers, search_all_product_codes, search_all_raw_materials, get_initial_raw_materials,
    get_all_lot_numbers_for_product, get_all_processed_by_names
)
# --- End Corrected Imports ---

from app.database.mixer_draft_ops import (
    get_user_draft, sync_draft, clear_user_draft,
    finalize_draft_to_permanent, get_next_reference_no, delete_staged_detail
)
from app.database.mixer_machine_ops import get_active_machines
from app.validators.mixer_form_validators import (
    MixerDetailCreateValidator, MixerHeaderDataValidator, MixerFinalSubmissionValidator
)

def load_stylesheet(widget):
    """Loads the stylesheet for this module."""
    current_dir = os.path.dirname(os.path.realpath(__file__))
    css_path = os.path.join(current_dir, "mixer_form_styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r") as f:
            widget.setStyleSheet(f.read())

class TimeLineEdit(QLineEdit):
    def __init__(self, initial_time=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setInputMask('00:00')
        if initial_time and hasattr(initial_time, 'strftime'):
            self.setText(initial_time.strftime("%H:%M"))
        else:
            self.setText("00:00")

class FormattedDoubleSpinBox(QDoubleSpinBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setGroupSeparatorShown(True)
        self.setMaximum(999999.99)

    def textFromValue(self, value: float) -> str:
        return f"{value:,.2f}"
    

# --- NEW WORKER for LIVE SEARCHING ---
class LiveSearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, session_factory: Callable, search_function: Callable, search_term: str, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.search_function = search_function
        self.search_term = search_term

    def run(self):
        session = self.Session()
        try:
            results = self.search_function(session, self.search_term)
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(f"Live search failed: {e}")
        finally:
            session.close()

class RemarksDialog(QDialog):
    def __init__(self, current_remarks: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Remarks")
        self.setMinimumWidth(450)
        self.setModal(True)
        if parent:
            self.setStyleSheet(parent.styleSheet())
        
        layout = QVBoxLayout(self)
        self.remarks_text_edit = QTextEdit()
        self.remarks_text_edit.setPlaceholderText("Enter any additional remarks here...")
        self.remarks_text_edit.setPlainText(current_remarks)
        
        button_layout = QHBoxLayout()
        save_button = QPushButton("Save Remarks")
        save_button.setObjectName("SuccessButton")
        cancel_button = QPushButton("Cancel")
        cancel_button.setObjectName("DangerButton")
    
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)
        
        layout.addWidget(self.remarks_text_edit)
        layout.addLayout(button_layout)
        
        save_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

    def get_remarks(self) -> str:
        return self.remarks_text_edit.toPlainText()


class DetailRowWidget(QWidget):
    """A custom widget representing a single, editable row of detail data."""
    delete_requested = pyqtSignal(object)

    def __init__(self, machine_map: dict, processed_by_names: List[str]):
        """
        Constructor now only builds the UI elements without populating them
        with draft data.
        """
        super().__init__()
        self.setObjectName("DetailRowWidget")
        self.detail_id = None
        self._remarks_text = ''

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        self.delete_button = QPushButton(icon=qta.icon("fa5s.times", color="#d9534f"))
        self.delete_button.setToolTip("Delete this row (Ctrl+D)")
        self.delete_button.setFixedWidth(20)
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self))

        self.machine_combo = ModifiedComboBox()
        for machine_id, machine_name in machine_map.items():
            self.machine_combo.addItem(machine_name, userData=machine_id)

        self.product_code_edit = SmartComboBox()
        self.product_code_edit.set_mandatory(True)

        self.lot_no_edit = LotComboBox()
        self.lot_no_edit.set_mandatory(True)

        self.lot_count_spin = QDoubleSpinBox(minimum=0, maximum=999999, decimals=0)
        self.lot_no_edit.lineEdit().textChanged.connect(
            lambda text: self._calculate_lot_count(text, self.lot_count_spin)
        )

        self.proc_start_time = TimeLineEdit()
        self.proc_end_time = TimeLineEdit()

        # --- WIDGET CHANGE: QLineEdit becomes a QComboBox ---
        self.processed_by_edit = QComboBox()
        self.processed_by_edit.setEditable(True)  # Allow new entries
        self.processed_by_edit.addItems(processed_by_names)
        self.processed_by_edit.setCompleter(QCompleter(processed_by_names))
        self.processed_by_edit.setCurrentIndex(-1) # Start with a blank selection
        # --- END OF WIDGET CHANGE ---


        self.output_qty_spin = FormattedDoubleSpinBox(minimum=0.00, decimals=2)
        self.clean_start_time = TimeLineEdit()
        self.clean_end_time = TimeLineEdit()
        self.clean_rm_code_edit = SmartComboBox()
        self.clean_rm_code_edit.setMinimumWidth(125)
        self.clean_qty_spin = FormattedDoubleSpinBox(minimum=0.00, decimals=2)
        self.remarks_button = QPushButton("Add Remarks")
        self.remarks_button.setObjectName("RemarksButton")
        self.remarks_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remarks_button.clicked.connect(self.open_remarks_dialog)
        self.update_remarks_button_text()

        self.proc_time_label = QLabel("0h 0m")
        self.proc_time_label.setObjectName("TimeCounterLabel")
        self.proc_start_time.textChanged.connect(self._calculate_time_diffs)
        self.proc_end_time.textChanged.connect(self._calculate_time_diffs)

        self.clean_time_label = QLabel("0h 0m")
        self.clean_time_label.setObjectName("TimeCounterLabel")
        self.clean_start_time.textChanged.connect(self._calculate_time_diffs)
        self.clean_end_time.textChanged.connect(self._calculate_time_diffs)

        proc_time_widget = QWidget()
        proc_time_layout = QHBoxLayout(proc_time_widget);
        proc_time_layout.setContentsMargins(0, 0, 0, 0)
        proc_time_layout.addWidget(self.proc_start_time);
        proc_time_layout.addWidget(self.proc_end_time)
        clean_time_widget = QWidget()
        clean_time_layout = QHBoxLayout(clean_time_widget);
        clean_time_layout.setContentsMargins(0, 0, 0, 0)
        clean_time_layout.addWidget(self.clean_start_time);
        clean_time_layout.addWidget(self.clean_end_time)
        layout.addWidget(self.delete_button, 1);
        layout.addWidget(self.machine_combo, 4)
        layout.addWidget(self.product_code_edit, 4);
        layout.addWidget(self.lot_no_edit, 4)
        layout.addWidget(self.lot_count_spin, 2);
        layout.addWidget(proc_time_widget, 3)
        layout.addWidget(self.proc_time_label, 1);
        layout.addWidget(self.processed_by_edit, 3)
        layout.addWidget(self.output_qty_spin, 2);
        layout.addWidget(clean_time_widget, 3)
        layout.addWidget(self.clean_time_label, 1);
        layout.addWidget(self.clean_rm_code_edit, 3)
        layout.addWidget(self.clean_qty_spin, 2);
        layout.addWidget(self.remarks_button, 3)

    def populate_draft_data(self, detail):
        """Populates the row's widgets with data from a draft detail object."""
        if not detail:
            return

        self.detail_id = getattr(detail, 'id', None)
        self._remarks_text = getattr(detail, 'remarks', '')

        # --- Set values for all fields from the draft object ---
        self.machine_combo.setCurrentIndex(self.machine_combo.findData(detail.mc_id))
        self.product_code_edit.setCurrentText(getattr(detail, 'product_code', ''))
        self.lot_no_edit.setCurrentText(getattr(detail, 'lot_no', ''))
        self.lot_count_spin.setValue(getattr(detail, 'lot_count', 0))
        self.processed_by_edit.setCurrentText(getattr(detail, 'processed_by', ''))
        self.output_qty_spin.setValue(getattr(detail, 'output_qty', 0.00))
        self.clean_rm_code_edit.setCurrentText(getattr(detail, 'cleaning_rm_code', ''))
        self.clean_qty_spin.setValue(getattr(detail, 'cleaning_qty', 0.00))

        # Safely set time values
        if p_start := getattr(detail, 'process_time_start', None):
            self.proc_start_time.setText(p_start.strftime("%H:%M"))
        if p_end := getattr(detail, 'process_time_end', None):
            self.proc_end_time.setText(p_end.strftime("%H:%M"))
        if c_start := getattr(detail, 'cleaning_time_start', None):
            self.clean_start_time.setText(c_start.strftime("%H:%M"))
        if c_end := getattr(detail, 'cleaning_time_end', None):
            self.clean_end_time.setText(c_end.strftime("%H:%M"))

        self.update_remarks_button_text()

    def _calculate_time_diffs(self):
        self._update_single_time_diff(self.proc_start_time, self.proc_end_time, self.proc_time_label)
        self._update_single_time_diff(self.clean_start_time, self.clean_end_time, self.clean_time_label)
    
    def _update_single_time_diff(self, start_widget: TimeLineEdit, end_widget: TimeLineEdit, label: QLabel):
        try:
            start_time = datetime.strptime(start_widget.text(), "%H:%M").time()
            end_time = datetime.strptime(end_widget.text(), "%H:%M").time()
            start_dt = datetime.combine(date.today(), start_time)
            end_dt = datetime.combine(date.today(), end_time)
            if end_dt < start_dt:
                end_dt += timedelta(days=1)
            diff = end_dt - start_dt
            total_minutes = diff.total_seconds() / 60
            hours = int(total_minutes // 60)
            minutes = int(total_minutes % 60)
            label.setText(f"{hours}h {minutes}m")
        except ValueError:
            label.setText("Invalid")

    def update_remarks_button_text(self):
        if self._remarks_text and self._remarks_text.strip():
            self.remarks_button.setText("View Remarks")
            self.remarks_button.setToolTip(self._remarks_text)
        else:
            self.remarks_button.setText("Add Remarks")
            self.remarks_button.setToolTip("Click to add remarks")

    def open_remarks_dialog(self):
        dialog = RemarksDialog(self._remarks_text, self)
        if dialog.exec():
            self._remarks_text = dialog.get_remarks()
            self.update_remarks_button_text()

    def get_data(self) -> MixerDetailCreateValidator:
        return MixerDetailCreateValidator(
            mc_id=self.machine_combo.currentData(),
            product_code=self.product_code_edit.text(),
            lot_no=self.lot_no_edit.text(),
            lot_count=self.lot_count_spin.value(),
            process_time_start=self.proc_start_time.text(),
            process_time_end=self.proc_end_time.text(),
            processed_by=self.processed_by_edit.currentText(),
            output_qty=self.output_qty_spin.value(),
            cleaning_time_start=self.clean_start_time.text(),
            cleaning_time_end=self.clean_end_time.text(),
            cleaning_rm_code=self.clean_rm_code_edit.text(),
            cleaning_qty=self.clean_qty_spin.value(),
            remarks=self._remarks_text
        )

    def _calculate_lot_count(self, text: str, target_spinbox: QSpinBox):
        total_count = 0
        # Split by semicolon for multiple entries, and filter out any empty strings.
        lot_entries = [entry.strip() for entry in text.split(';') if entry.strip()]

        for entry in lot_entries:
            entry = entry.upper()
            numbers = re.findall(r'(\d+)', entry)

            # Case 1: Handle ranges like "1005AM-1007AM"
            if '-' in entry and len(numbers) == 2:
                try:
                    start, end = int(numbers[0]), int(numbers[1])
                    if end >= start:
                        total_count += (end - start) + 1
                    # If end < start, it's an invalid range, so we add 0.
                except (ValueError, IndexError):
                    # Malformed range (e.g., "100-XYZ"), add 0.
                    pass
            # Case 2: Handle single entries like "1005AM" that are not ranges.
            elif numbers:
                total_count += 1
            # Case 3: Malformed entries with no numbers are ignored (add 0).

        target_spinbox.setValue(total_count)


class MixerEntryFormView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.user_id = 1
        self.machine_map = {}
        self.detail_rows: List[DetailRowWidget] = []
        
        self.initial_lot_numbers = []
        self.initial_product_codes = []
        self.initial_raw_materials = []
        self.processed_by_names = []
        self.live_search_worker = None


        self.setObjectName("MixerFormModule")
        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()
        
        load_stylesheet(self)


    def keyPressEvent(self, event: QKeyEvent):
        if event.key() == Qt.Key.Key_Backspace and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            current_focus = self.focusWidget()
            if isinstance(current_focus, QWidget):
                parent_row = current_focus
                while parent_row is not None and not isinstance(parent_row, DetailRowWidget):
                    parent_row = parent_row.parentWidget()
                if isinstance(parent_row, DetailRowWidget):
                    self._handle_delete_row(parent_row)
                    event.accept()
                    return
        if event.key() == Qt.Key.Key_Return and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
            self._handle_add_row()
            event.accept()
            return
        super().keyPressEvent(event)

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        header_layout = QGridLayout()
        header_layout.setHorizontalSpacing(20)
        header_layout.setVerticalSpacing(0)
        self.ref_no_input = QLineEdit()
        self.ref_no_input.setReadOnly(True)
        self.date_input = QDateEdit(calendarPopup=True, date=QDate.currentDate())
        self.time_start_input = TimeLineEdit()
        self.time_end_input = TimeLineEdit()
        time_layout = QHBoxLayout()
        time_layout.setContentsMargins(0,0,0,0)
        time_layout.setSpacing(5)
        time_layout.addWidget(self.time_start_input)
        time_layout.addWidget(QLabel("to"))
        time_layout.addWidget(self.time_end_input)
        ref_label = QLabel("Reference No:")
        ref_label.setProperty("class", "HeaderLabel")
        date_label = QLabel("Date:")
        date_label.setProperty("class", "HeaderLabel")
        time_label = QLabel("Shift Time:")
        time_label.setProperty("class", "HeaderLabel")
        header_layout.addWidget(ref_label, 0, 0)
        header_layout.addWidget(self.ref_no_input, 1, 0)
        header_layout.addWidget(date_label, 0, 1)
        header_layout.addWidget(self.date_input, 1, 1)
        header_layout.addWidget(time_label, 0, 2)
        header_layout.addLayout(time_layout, 1, 2)
        header_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum), 1, 3)
        self.staged_group = QGroupBox("Production Details (Shift+Enter to add new row, Ctrl+D to delete focused row)")
        staged_layout = QVBoxLayout(self.staged_group)
        table_toolbar_layout = QHBoxLayout()
        self.add_row_button = QPushButton("Add New Detail Row")
        self.save_draft_button = QPushButton("Save Draft")
        self.save_draft_button.setObjectName("PrimaryButton")
        table_toolbar_layout.addWidget(self.add_row_button)
        table_toolbar_layout.addStretch()
        table_toolbar_layout.addWidget(self.save_draft_button)
        details_container = QWidget()
        details_container.setObjectName("DetailsContainer")
        self.details_layout = QVBoxLayout(details_container)
        self.details_layout.setContentsMargins(0,0,0,0)
        self.details_layout.setSpacing(0)
        self.details_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        staged_layout.addLayout(table_toolbar_layout)
        staged_layout.addWidget(self._create_detail_header())
        staged_layout.addWidget(details_container)
        final_actions_layout = QHBoxLayout()
        self.clear_form_button = QPushButton("Clear Draft")
        self.save_all_button = QPushButton("Finalize and Save Batch")
        self.clear_form_button.setObjectName("DangerButton")
        self.save_all_button.setObjectName("SuccessButton")
        final_actions_layout.addWidget(self.clear_form_button)
        final_actions_layout.addStretch()
        final_actions_layout.addWidget(self.save_all_button)
        main_layout.addLayout(header_layout)
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        separator.setObjectName("SeparatorLine")
        main_layout.addWidget(separator)
        main_layout.addWidget(self.staged_group, 1)
        main_layout.addLayout(final_actions_layout)

    def _create_detail_header(self) -> QWidget:
        header_widget = QWidget()
        header_widget.setObjectName("DetailHeaderWidget")
        header_widget.setFixedHeight(40)
        layout = QHBoxLayout(header_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        proc_time_label = QLabel("Process Time")
        proc_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        clean_time_label = QLabel("Cleaning Time")
        clean_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(QLabel(""), 1)
        layout.addWidget(QLabel("Machine"), 4)
        layout.addWidget(QLabel("Product Code"), 4)
        layout.addWidget(QLabel("Lot No"), 4)
        layout.addWidget(QLabel("Lot Count"), 2)
        layout.addWidget(proc_time_label, 3)
        layout.addWidget(QLabel(""), 1)
        layout.addWidget(QLabel("Processed By"), 3)
        layout.addWidget(QLabel("Output Qty"), 2)
        layout.addWidget(clean_time_label, 3)
        layout.addWidget(QLabel(""), 1)
        layout.addWidget(QLabel("Cleaning RM"), 3)
        layout.addWidget(QLabel("Cleaning Qty"), 2)
        layout.addWidget(QLabel("Remarks"), 3)
        return header_widget

    def _connect_signals(self):
        self.add_row_button.clicked.connect(self._handle_add_row)
        self.save_draft_button.clicked.connect(self._handle_save_draft)
        self.clear_form_button.clicked.connect(self._handle_clear_draft)
        self.save_all_button.clicked.connect(self._handle_finalize)

    def _setup_shortcuts(self):
        """Creates and connects QAction shortcuts for the entire widget."""
        # Standard shortcuts
        add_row_action = QAction("Add Row", self)
        add_row_action.setShortcut("Shift+Return")
        add_row_action.triggered.connect(self._handle_add_row)
        
        delete_row_action = QAction("Delete Row", self)
        delete_row_action.setShortcut("Ctrl+D")
        delete_row_action.triggered.connect(self._handle_delete_shortcut)
        
        # New shortcuts for saving
        save_draft_action = QAction("Save Draft", self)
        save_draft_action.setShortcut("Ctrl+S")
        save_draft_action.triggered.connect(self._handle_save_draft)
        
        finalize_action = QAction("Finalize Batch", self)
        finalize_action.setShortcut("Ctrl+Shift+S")
        finalize_action.triggered.connect(self._handle_finalize)
        
        # Add all actions to the widget to make them active
        self.addActions([
            add_row_action, 
            delete_row_action, 
            save_draft_action, 
            finalize_action
        ])
        
        # Also set tooltips for the buttons for better UX
        self.save_draft_button.setToolTip("Save current progress as a draft (Ctrl+S)")
        self.save_all_button.setToolTip("Finalize and save batch to permanent records (Ctrl+Shift+S)")

    def _handle_delete_shortcut(self):
        current_focus = self.focusWidget()
        if not isinstance(current_focus, QWidget):
            return
        parent_row = current_focus
        while parent_row is not None and not isinstance(parent_row, DetailRowWidget):
            parent_row = parent_row.parentWidget()
        if isinstance(parent_row, DetailRowWidget):
            self._handle_delete_row(parent_row)

    def _populate_machine_combobox(self, session: sessionmaker):
        """Fetches active machines. Now takes a session."""
        machines = get_active_machines(session)
        self.machine_map = {m.id: m.name for m in machines}

    def _fetch_and_set_next_ref_no(self): # Modified to accept session

        session = self.Session()
        try:
            next_ref = get_next_reference_no(session)
            self.ref_no_input.setText(str(next_ref).zfill(6))
        except Exception as e:
            print(f"Error fetching next reference number: {e}")
            self.ref_no_input.setText("ERROR")

    def _handle_add_row(self):
        # When adding a new row, it will also be populated with the master lists
        self._add_row_widget()

    def _handle_delete_row(self, row_widget: DetailRowWidget):
        if row_widget.detail_id:
            confirm = QMessageBox.question(self, "Confirm Delete",
                "This record is saved in your draft. Are you sure you want to permanently delete it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if confirm == QMessageBox.StandardButton.Yes:
                session = self.Session()
                try:
                    delete_staged_detail(session, row_widget.detail_id)
                    self.detail_rows.remove(row_widget)
                    row_widget.deleteLater()
                except Exception as e:
                    QMessageBox.critical(self, "Error", f"Could not delete item: {e}")
                finally:
                    session.close()
        else:
            self.detail_rows.remove(row_widget)
            row_widget.deleteLater()
    
    def _clear_all_rows(self):
        for widget in self.detail_rows:
            widget.deleteLater()
        self.detail_rows.clear()
        
    def _gather_data_from_ui(self) -> tuple[MixerHeaderDataValidator, list[MixerDetailCreateValidator]]:
        header_data = MixerHeaderDataValidator(
            reference_no=int(self.ref_no_input.text()) if self.ref_no_input.text() else None,
            date=self.date_input.date().toPyDate(),
            time_start=self.time_start_input.text(),
            time_end=self.time_end_input.text()
        )
        details_to_save = [row.get_data() for row in self.detail_rows]
        return header_data, details_to_save


    def _load_initial_data(self):
        """Loads only the first 1000 items for a fast startup."""
        print("Loading initial form data...")
        self.setEnabled(False)
        self.staged_group.setTitle("Loading options...")
        QApplication.processEvents()
        
        session = self.Session()
        try:
            # Load machines
            machines = get_active_machines(session)
            self.machine_map = {m.id: m.name for m in machines}
            
            # Load ONLY the initial, limited lists
            print("Fetching initial lot numbers...")
            self.initial_lot_numbers = get_initial_lot_numbers(session, limit=100)
            print("Fetching initial product codes...")
            self.initial_product_codes = get_initial_product_codes(session, limit=100)

            print("Fetching initial raw materials...")
            self.initial_raw_materials = get_initial_raw_materials(session, limit=100)

            print("Fetching processor names...")
            self.processed_by_names = get_all_processed_by_names(session)  # <--- ADD THIS LINE

            
            self._load_draft_and_populate_rows(session)
            
        except Exception as e:
            QMessageBox.critical(self, "Fatal Error", f"Could not load form data: {e}")
        finally:
            session.close()
            self.setEnabled(True)
            self.staged_group.setTitle("Production Details (Shift+Enter to add new row, Ctrl+D to delete focused row)")
            print("Form ready.")

            

    def _load_draft_and_populate_rows(self, session: sessionmaker):
        """Loads the user's draft and populates all detail rows."""
        self._clear_all_rows()
        draft = get_user_draft(session, self.user_id)
        
        if draft and draft.details:
            self.ref_no_input.setText(str(draft.reference_no).zfill(6))
            if draft.date: self.date_input.setDate(QDate(draft.date))
            if draft.time_start: self.time_start_input.setText(draft.time_start.strftime("%H:%M"))
            if draft.time_end: self.time_end_input.setText(draft.time_end.strftime("%H:%M"))
            for detail in sorted(draft.details, key=lambda d: d.created_at):
                self._add_row_widget(detail)
        else:
            self._fetch_and_set_next_ref_no()
            self._add_row_widget()


    @pyqtSlot()
    def _on_legacy_data_loaded(self):
        """Callback for when the worker has finished POPULATING the models."""
        print("UI Thread: Worker has finished populating models.")
        # The models are already attributes of self, so we don't need to reassign them.
        # We can now safely load the draft which will create rows using these models.
        self._load_draft_from_db()
        
        self.setEnabled(True)
        self.staged_group.setTitle("Production Details (Shift+Enter to add new row, Ctrl+D to delete focused row)")
        print("UI Thread: Form is ready and responsive.")

    def _on_data_load_error(self, error_message):
        QMessageBox.critical(self, "Fatal Error", error_message)
        self.setEnabled(True)

    def _load_draft_from_db(self):
        session = self.Session()
        try:
            draft = get_user_draft(session, self.user_id)
            self._clear_all_rows()
            if draft and draft.details:
                self.ref_no_input.setText(str(draft.reference_no).zfill(6)) if draft.reference_no else self._fetch_and_set_next_ref_no()
                if draft.date: self.date_input.setDate(QDate(draft.date))
                if draft.time_start: self.time_start_input.setText(draft.time_start.strftime("%H:%M"))
                if draft.time_end: self.time_end_input.setText(draft.time_end.strftime("%H:%M"))
                for detail in sorted(draft.details, key=lambda d: d.created_at):
                    self._add_row_widget(detail)
            else:
                self._fetch_and_set_next_ref_no()
                self._add_row_widget()
        finally:
            session.close()

    def _add_row_widget(self, detail=None):
        # --- CORRECTED ORDER OF OPERATIONS ---

        # 1. Create the widget. It is empty of data.
        row_widget = DetailRowWidget(self.machine_map, self.processed_by_names)

        # 2. Populate the combo boxes with their lists of available items.
        row_widget.lot_no_edit.populate_initial(self.initial_lot_numbers)
        row_widget.product_code_edit.populate_initial(self.initial_product_codes)
        row_widget.clean_rm_code_edit.populate_initial(self.initial_raw_materials)

        # 3. NOW that the combo boxes have items, populate the widget with draft data if it exists.
        if detail:
            row_widget.populate_draft_data(detail)

        # 4. Connect all signals for live searching and deletion.
        row_widget.lot_no_edit.full_search_requested.connect(
            lambda term: self.on_full_search_requested(row_widget.lot_no_edit, search_all_lot_numbers, term)
        )
        row_widget.product_code_edit.full_search_requested.connect(
            lambda term: self.on_full_search_requested(row_widget.product_code_edit, search_all_product_codes, term)
        )
        row_widget.clean_rm_code_edit.full_search_requested.connect(
            lambda term: self.on_full_search_requested(row_widget.clean_rm_code_edit, search_all_raw_materials, term)
        )
        row_widget.delete_requested.connect(self._handle_delete_row)

        # 5. Add the fully prepared widget to the layout.
        self.details_layout.addWidget(row_widget)
        self.detail_rows.append(row_widget)
        row_widget.machine_combo.setFocus()

    def on_full_search_requested(self, combo_box: SmartComboBox, search_function: Callable, search_term: str):
        """
        This slot launches a background worker to perform a full database search.
        """
        # If a search is already running, simply ignore this new request.
        if self.live_search_worker and self.live_search_worker.isRunning():
            print(f"Search already in progress. Ignoring request for '{search_term}'.")
            return
            
        print(f"Starting full search for '{search_term}'...")
        self.live_search_worker = LiveSearchWorker(self.Session, search_function, search_term, self)
        
        # Connect the worker's result signal to the specific combo box that requested it
        self.live_search_worker.results_ready.connect(combo_box.update_with_search_results)
        self.live_search_worker.error.connect(lambda msg: print(f"Search Error: {msg}"))
        
        # --- THIS IS THE FIX ---
        # 1. Connect the worker's finished signal to our new cleanup slot.
        # 2. DO NOT connect it to deleteLater here.
        self.live_search_worker.finished.connect(self._on_search_finished)
        
        self.live_search_worker.start()


    @pyqtSlot()
    def _on_search_finished(self):
        """
        This slot is called when the live search worker is done.
        It safely cleans up the worker reference.
        """
        print("Live search worker has finished.")
        # The worker's thread has stopped. Now it's safe to get rid of the object.
        self.live_search_worker.deleteLater()
        self.live_search_worker = None # Set the attribute back to None.


    def _validate_form_data(self) -> bool:
        """
        Checks all detail rows to ensure mandatory fields are filled and valid.
        Returns True if all valid, False otherwise.
        """
        # --- NEW: Caching mechanism for lot numbers to avoid redundant DB calls ---
        lot_number_cache = {}
        session = self.Session()
        try:
            for i, row in enumerate(self.detail_rows):
                row_num = i + 1

                # --- Validation for Product Code (as before) ---
                if not row.product_code_edit.is_valid():
                    QMessageBox.warning(self, "Validation Error", f"Row {row_num}: Product Code is invalid or empty.")
                    row.product_code_edit.setFocus()
                    return False

                # --- NEW: ADVANCED LOT NUMBER VALIDATION LOGIC ---
                product_code = row.product_code_edit.text()
                lot_no_to_validate = row.lot_no_edit.text()

                if not lot_no_to_validate.strip():
                    QMessageBox.warning(self, "Validation Error", f"Row {row_num}: Lot Number cannot be empty.")
                    row.lot_no_edit.setFocus()
                    return False

                # Check cache first
                if product_code not in lot_number_cache:
                    # If not in cache, fetch from DB and store it
                    existing_lots = get_all_lot_numbers_for_product(session, product_code)
                    lot_number_cache[product_code] = [item for item, in existing_lots]

                # Retrieve from cache
                db_lots_for_product = lot_number_cache[product_code]

                if not db_lots_for_product:
                    QMessageBox.warning(self, "Validation Error",
                                        f"Row {row_num}: Cannot validate Lot Number because no lot numbers exist for Product '{product_code}'.")
                    row.product_code_edit.setFocus()
                    return False

                lot_validator = LotNumberValidator(db_lots_for_product)
                is_valid, error_message = lot_validator.validate_lot_entry(lot_no_to_validate, product_code)

                if not is_valid:
                    QMessageBox.warning(self, "Validation Error", f"Row {row_num}: {error_message}")
                    row.lot_no_edit.setFocus()
                    return False
                # --- END OF NEW LOT NUMBER VALIDATION ---

                if not row.clean_rm_code_edit.is_valid():
                    QMessageBox.warning(self, "Validation Error",
                                        f"Row {row_num}: Cleaning RM Code is invalid. Please select an item or leave it empty.")
                    row.clean_rm_code_edit.setFocus()
                    return False

                if row.machine_combo.currentIndex() == -1:
                    QMessageBox.warning(self, "Validation Error", f"Row {row_num}: Machine No must be selected.")
                    row.machine_combo.setFocus()
                    return False

                if not row.processed_by_edit.currentText().strip():
                    QMessageBox.warning(self, "Validation Error", f"Row {row_num}: Processed By cannot be empty.")
                    row.processed_by_edit.setFocus()
                    return False

                if row.output_qty_spin.value() <= 0:
                    QMessageBox.warning(self, "Validation Error", f"Row {row_num}: Output Qty must be greater than 0.")
                    row.output_qty_spin.setFocus()
                    return False

                rm_code = row.clean_rm_code_edit.text().strip()
                rm_qty = row.clean_qty_spin.value()
                if (rm_code and rm_qty <= 0):
                    QMessageBox.warning(self, "Validation Error",
                                        f"Row {row_num}: Cleaning Qty must be greater than 0 if a Cleaning RM is selected.")
                    row.clean_qty_spin.setFocus()
                    return False
                if (rm_qty > 0 and not rm_code):
                    QMessageBox.warning(self, "Validation Error",
                                        f"Row {row_num}: A Cleaning RM must be selected if Cleaning Qty is entered.")
                    row.clean_rm_code_edit.setFocus()
                    return False

                if row.proc_start_time.text() != "00:00" and row.proc_end_time.text() == "00:00":
                    QMessageBox.warning(self, "Validation Error",
                                        f"Row {row_num}: Process End Time cannot be 00:00 if a Start Time is set.")
                    row.proc_end_time.setFocus()
                    return False

                if row.clean_start_time.text() != "00:00" and row.clean_end_time.text() == "00:00":
                    QMessageBox.warning(self, "Validation Error",
                                        f"Row {row_num}: Cleaning End Time cannot be 00:00 if a Start Time is set.")
                    row.clean_end_time.setFocus()
                    return False

            return True  # All rows are valid

        finally:
            session.close()



    def _handle_save_draft(self): # Simplified
        """Reads all data, validates, and syncs with the database."""

        # --- NEW: Call the validator first ---
        if not self._validate_form_data():
            return # Stop the save if validation fails
        
        session = self.Session()

        try:
            header_data, details_data = self._gather_data_from_ui()
            if not details_data:
                QMessageBox.warning(self, "Empty Draft", "Cannot save an empty draft.")
                return
            sync_draft(session, self.user_id, header_data, details_data)
            QMessageBox.information(self, "Draft Saved", "Your progress has been saved.")
        except ValidationError as e:
            QMessageBox.warning(self, "Validation Error", f"Could not save draft:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred: {e}")
        finally:
            if session.is_active:
                session.close()

    # def _handle_finalize(self):
        
    #     self._handle_save_draft()
    #     session = self.Session()
    #     try:
    #         final_header_data = MixerFinalSubmissionValidator(
    #             reference_no=int(self.ref_no_input.text()),
    #             date=self.date_input.date().toPyDate(),
    #             time_start=self.time_start_input.text(),
    #             time_end=self.time_end_input.text()
    #         )
    #         finalize_draft_to_permanent(session, self.user_id, final_header_data)
    #         QMessageBox.information(self, "Success", "Batch saved successfully.")
    #         self._clear_form_state(delete_draft=False)
    #         self._fetch_and_set_next_ref_no()
    #     except (ValueError, ValidationError) as e:
    #         QMessageBox.warning(self, "Validation Error", f"Cannot finalize batch:\n{e}")
    #     except IntegrityError as e:
    #         QMessageBox.critical(self, "Save Failed", str(e))
    #     except Exception as e:
    #         QMessageBox.critical(self, "An Error Occurred", f"Could not save batch: {e}")
    #     finally:
    #         session.close()
    

    def _handle_finalize(self):
        """
        Finalizes the draft to permanent records. Now includes validation.
        """
        # --- NEW: Call the validator first ---
        if not self._validate_form_data():
            return # Stop the finalization if validation fails
        
        # The save draft call is implicitly part of the validation, so we can
        # proceed directly to the finalize logic.
        session = self.Session()
        try:
            # First, ensure the draft is up-to-date
            header_data, details_data = self._gather_data_from_ui()
            sync_draft(session, self.user_id, header_data, details_data)
            
            # Now, proceed with finalization
            final_header_data = MixerFinalSubmissionValidator(
                reference_no=int(self.ref_no_input.text()),
                date=self.date_input.date().toPyDate(),
                time_start=self.time_start_input.text(),
                time_end=self.time_end_input.text()
            )
            finalize_draft_to_permanent(session, self.user_id, final_header_data)
            QMessageBox.information(self, "Success", "Batch saved successfully.")
            self._clear_form_state(delete_draft=False) # Pass session to clear
        except (ValueError, ValidationError) as e:
            QMessageBox.warning(self, "Validation Error", f"Cannot finalize batch:\n{e}")
        except IntegrityError as e:
            QMessageBox.critical(self, "Save Failed", str(e))
        except Exception as e:
            QMessageBox.critical(self, "An Error Occurred", f"Could not save batch: {e}")
        finally:
            session.close()

    def _handle_clear_draft(self):
        confirm = QMessageBox.question(self, "Confirm Clear",
            "Are you sure you want to clear the entire form and delete the draft from the database?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self._clear_form_state(delete_draft=True)

    def _clear_form_state(self, delete_draft: bool):
        if delete_draft:
            session = self.Session()
            try:
                clear_user_draft(session, self.user_id)
            finally:
                session.close()
        
        self._clear_all_rows()
        self._fetch_and_set_next_ref_no()
        self.date_input.setDate(QDate.currentDate())
        self.time_start_input.setText("00:00")
        self.time_end_input.setText("00:00")
        self._add_row_widget()

    def showEvent(self, event):
        """Loads data only the first time the widget is shown."""
        super().showEvent(event)
        if not hasattr(self, '_initial_data_loaded'):
            self._initial_data_loaded = True
            self._load_initial_data()