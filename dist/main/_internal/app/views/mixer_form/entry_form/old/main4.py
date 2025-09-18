import os
import re
from datetime import datetime
from typing import Type, Callable, List
from pydantic import ValidationError

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QMessageBox, QLineEdit, QGroupBox, QLabel, QDateEdit, QGridLayout,
    QSpinBox, QDoubleSpinBox, QTextEdit, QComboBox, QScrollArea, QFrame,
    QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import pyqtSignal, Qt, QDate, QEvent
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
import qtawesome as qta

# Import your database and validator modules
from ...database.mixer_draft_ops import (
    get_user_draft, sync_draft, clear_user_draft,
    finalize_draft_to_permanent, get_next_reference_no, delete_staged_detail
)
from ...database.mixer_machine_ops import get_active_machines
from ...validators.mixer_form_validators import (
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
    """A custom QLineEdit for user-friendly 24-hour time input."""
    def __init__(self, initial_time=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setInputMask('00:00')
        if initial_time and hasattr(initial_time, 'strftime'):
            self.setText(initial_time.strftime("%H:%M"))
        else:
            self.setText(datetime.now().strftime("%H:%M"))

class DetailRowWidget(QWidget):
    """A custom widget representing a single, editable row of detail data."""
    delete_requested = pyqtSignal(object)

    def __init__(self, machine_map: dict, detail=None):
        super().__init__()
        self.setObjectName("DetailRowWidget")
        self.detail_id = getattr(detail, 'id', None)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)

        self.delete_button = QPushButton(icon=qta.icon("fa5s.times", color="#d9534f"))
        self.delete_button.setToolTip("Delete this row")
        self.delete_button.setFixedWidth(30)
        self.delete_button.clicked.connect(lambda: self.delete_requested.emit(self))
        
        self.machine_combo = QComboBox()
        for machine_id, machine_name in machine_map.items():
            self.machine_combo.addItem(machine_name, userData=machine_id)
        
        self.product_code_edit = QLineEdit(getattr(detail, 'product_code', ''))
        self.lot_no_edit = QLineEdit(getattr(detail, 'lot_no', ''))
        self.lot_count_spin = QSpinBox(minimum=1, maximum=9999, value=getattr(detail, 'lot_count', 1))
        self.lot_no_edit.textChanged.connect(lambda text: self._calculate_lot_count(text, self.lot_count_spin))
        self.proc_start_time = TimeLineEdit(getattr(detail, 'process_time_start', None))
        self.proc_end_time = TimeLineEdit(getattr(detail, 'process_time_end', None))
        self.processed_by_edit = QLineEdit(getattr(detail, 'processed_by', ''))
        self.output_qty_spin = QDoubleSpinBox(minimum=0.01, decimals=2, value=getattr(detail, 'output_qty', 0.01))
        self.clean_start_time = TimeLineEdit(getattr(detail, 'cleaning_time_start', None))
        self.clean_end_time = TimeLineEdit(getattr(detail, 'cleaning_time_end', None))
        self.clean_rm_code_edit = QLineEdit(getattr(detail, 'cleaning_rm_code', ''))
        self.clean_qty_spin = QDoubleSpinBox(minimum=0.01, decimals=2, value=getattr(detail, 'cleaning_qty', 0.01))
        self.remarks_edit = QLineEdit(getattr(detail, 'remarks', ''))
        
        if detail:
            self.machine_combo.setCurrentIndex(self.machine_combo.findData(detail.mc_id))

        layout.addWidget(self.delete_button)
        layout.addWidget(self.machine_combo, 2)
        layout.addWidget(self.product_code_edit, 2)
        layout.addWidget(self.lot_no_edit, 2)
        layout.addWidget(self.lot_count_spin, 1)
        layout.addWidget(self.proc_start_time, 1)
        layout.addWidget(self.proc_end_time, 1)
        layout.addWidget(self.processed_by_edit, 2)
        layout.addWidget(self.output_qty_spin, 1)
        layout.addWidget(self.clean_start_time, 1)
        layout.addWidget(self.clean_end_time, 1)
        layout.addWidget(self.clean_rm_code_edit, 2)
        layout.addWidget(self.clean_qty_spin, 1)
        layout.addWidget(self.remarks_edit, 3)

    def get_data(self) -> MixerDetailCreateValidator:
        """Reads data from the widgets and returns a validated Pydantic model."""
        return MixerDetailCreateValidator(
            mc_id=self.machine_combo.currentData(),
            product_code=self.product_code_edit.text(),
            lot_no=self.lot_no_edit.text(),
            lot_count=self.lot_count_spin.value(),
            process_time_start=self.proc_start_time.text(),
            process_time_end=self.proc_end_time.text(),
            processed_by=self.processed_by_edit.text(),
            output_qty=self.output_qty_spin.value(),
            cleaning_time_start=self.clean_start_time.text(),
            cleaning_time_end=self.clean_end_time.text(),
            cleaning_rm_code=self.clean_rm_code_edit.text(),
            cleaning_qty=self.clean_qty_spin.value(),
            remarks=self.remarks_edit.text()
        )
    
    def _calculate_lot_count(self, text: str, target_spinbox: QSpinBox):
        """Auto-calculates lot count for this row's spinbox."""
        text = text.strip().upper()
        numbers = re.findall(r'(\d+)', text)
        count = 1
        if '-' in text and len(numbers) == 2:
            try:
                start, end = int(numbers[0]), int(numbers[1])
                if end >= start:
                    count = (end - start) + 1
            except (ValueError, IndexError):
                count = 1
        target_spinbox.setValue(count)

class MixerFormView(QWidget):
    """
    The main content widget for the Mixer Form. This widget is designed to be
    placed inside a QScrollArea by its parent (base.py).
    """
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.user_id = 1
        self.machine_map = {}
        self.detail_rows: List[DetailRowWidget] = []

        self.setObjectName("MixerFormModule")
        self._setup_ui()
        self._connect_signals()
        
        self.installEventFilter(self)
        load_stylesheet(self)
        self._load_draft_from_db()

    def eventFilter(self, source, event):
        """Captures keyboard events to handle shortcuts like Shift+Enter."""
        if event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return and (event.modifiers() & Qt.KeyboardModifier.ShiftModifier):
                current_focus = self.focusWidget()
                if isinstance(current_focus, QWidget):
                    parent = current_focus.parentWidget()
                    if isinstance(parent, DetailRowWidget) and parent.remarks_edit is current_focus:
                        self._handle_add_row()
                        return True
        return super().eventFilter(source, event)

    def _setup_ui(self):
        """Initializes and arranges all widgets for the user interface."""
        # The main_layout is the layout of this QWidget itself. NO SCROLL AREA.
        main_layout = QVBoxLayout(self)
        
        header_layout = QGridLayout()
        self.ref_no_input = QLineEdit()
        self.ref_no_input.setReadOnly(True)
        self.date_input = QDateEdit(calendarPopup=True, date=QDate.currentDate())
        self.time_start_input = TimeLineEdit()
        self.time_end_input = TimeLineEdit()
        header_layout.addWidget(QLabel("Reference No:"), 0, 0)
        header_layout.addWidget(self.ref_no_input, 0, 1)
        header_layout.addWidget(QLabel("Date:"), 0, 2)
        header_layout.addWidget(self.date_input, 0, 3)
        header_layout.addWidget(QLabel("Shift Time Start/End:"), 1, 0)
        header_layout.addWidget(self.time_start_input, 1, 1)
        header_layout.addWidget(self.time_end_input, 1, 2)
        header_layout.addItem(QSpacerItem(20, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum), 0, 4)

        staged_group = QGroupBox("Production Details (Press Shift+Enter in the last field to add a new row)")
        staged_layout = QVBoxLayout(staged_group)

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
        self.clear_form_button = QPushButton("Clear & Delete Draft")
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
        
        # --- THIS IS THE CRITICAL FIX ---
        # We give the staged_group a stretch factor of 1. This tells the main_layout
        # that this group should take up all available vertical space.
        main_layout.addWidget(staged_group, 1)
        main_layout.addLayout(final_actions_layout)

    def _create_detail_header(self) -> QWidget:
        """Creates a static header widget that looks like a table header."""
        header_widget = QWidget()
        header_widget.setObjectName("DetailHeaderWidget")
        layout = QHBoxLayout(header_widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(10)
        
        layout.addWidget(QLabel(""), 30)
        layout.addWidget(QLabel("Machine"), 2)
        layout.addWidget(QLabel("Product Code"), 2)
        layout.addWidget(QLabel("Lot No"), 2)
        layout.addWidget(QLabel("Lot Count"), 1)
        layout.addWidget(QLabel("Process Start"), 1)
        layout.addWidget(QLabel("Process End"), 1)
        layout.addWidget(QLabel("Processed By"), 2)
        layout.addWidget(QLabel("Output Qty"), 1)
        layout.addWidget(QLabel("Cleaning Start"), 1)
        layout.addWidget(QLabel("Cleaning End"), 1)
        layout.addWidget(QLabel("Cleaning RM"), 2)
        layout.addWidget(QLabel("Cleaning Qty"), 1)
        layout.addWidget(QLabel("Remarks"), 3)
            
        return header_widget

    def _connect_signals(self):
        """Connects all widget signals to their respective handler methods."""
        self.add_row_button.clicked.connect(self._handle_add_row)
        self.save_draft_button.clicked.connect(self._handle_save_draft)
        self.clear_form_button.clicked.connect(self._handle_clear_draft)
        self.save_all_button.clicked.connect(self._handle_finalize)

    def _populate_machine_combobox(self):
        """Fetches active machines and populates the internal machine_map."""
        session = self.Session()
        try:
            machines = get_active_machines(session)
            self.machine_map = {m.id: m.name for m in machines}
        except Exception as e:
            QMessageBox.critical(self, "Fatal Error", f"Could not load required machine data: {e}")
            self.machine_map = {}
        finally:
            session.close()

    def _load_draft_from_db(self):
        """Loads an existing user draft from the database on startup."""
        self._populate_machine_combobox()
        session = self.Session()
        try:
            draft = get_user_draft(session, self.user_id)
            self._clear_all_rows()
            
            if draft:
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

    def _fetch_and_set_next_ref_no(self):
        """Gets the next available reference number and populates the input field."""
        session = self.Session()
        try:
            next_ref = get_next_reference_no(session)
            self.ref_no_input.setText(str(next_ref).zfill(6))
        finally:
            session.close()

    def _add_row_widget(self, detail=None):
        """Creates a new DetailRowWidget and adds it to the layout."""
        row_widget = DetailRowWidget(self.machine_map, detail)
        row_widget.delete_requested.connect(self._handle_delete_row)
        self.details_layout.addWidget(row_widget)
        self.detail_rows.append(row_widget)
        row_widget.product_code_edit.setFocus()

    def _handle_add_row(self):
        """Adds a blank row to the form."""
        self._add_row_widget()

    def _handle_delete_row(self, row_widget: DetailRowWidget):
        """Handles deletion of a row from the UI and potentially the DB."""
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
        """Removes all detail row widgets from the UI."""
        for widget in self.detail_rows:
            widget.deleteLater()
        self.detail_rows.clear()
        
    def _gather_data_from_ui(self) -> tuple[MixerHeaderDataValidator, list[MixerDetailCreateValidator]]:
        """A helper method to read and validate all data from the UI."""
        header_data = MixerHeaderDataValidator(
            reference_no=int(self.ref_no_input.text()) if self.ref_no_input.text() else None,
            date=self.date_input.date().toPyDate(),
            time_start=self.time_start_input.text(),
            time_end=self.time_end_input.text()
        )
        details_to_save = [row.get_data() for row in self.detail_rows]
        return header_data, details_to_save

    def _handle_save_draft(self):
        """Reads all data from the row widgets, validates, and syncs with the database."""
        session = self.Session()
        try:
            header_data, details_data = self._gather_data_from_ui()
            sync_draft(session, self.user_id, header_data, details_data)
            QMessageBox.information(self, "Draft Saved", "Your progress has been saved successfully.")
            self._load_draft_from_db()
        except ValidationError as e:
            QMessageBox.warning(self, "Validation Error", f"Could not save draft. Please check all fields:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"An error occurred: {e}")
        finally:
            if session.is_active:
                session.close()
    
    def _handle_finalize(self):
        """Finalizes the draft to permanent records after a final save of the draft."""
        self._handle_save_draft()
        session = self.Session()
        try:
            final_header_data = MixerFinalSubmissionValidator(
                reference_no=int(self.ref_no_input.text()),
                date=self.date_input.date().toPyDate(),
                time_start=self.time_start_input.text(),
                time_end=self.time_end_input.text()
            )
            finalize_draft_to_permanent(session, self.user_id, final_header_data)
            QMessageBox.information(self, "Success", "Batch saved successfully.")
            self._clear_form_state(delete_draft=False)
            self._fetch_and_set_next_ref_no()
        except (ValueError, ValidationError) as e:
            QMessageBox.warning(self, "Validation Error", f"Cannot finalize batch:\n{e}")
        except IntegrityError as e:
            QMessageBox.critical(self, "Save Failed", str(e))
        except Exception as e:
            QMessageBox.critical(self, "An Error Occurred", f"Could not save batch: {e}")
        finally:
            session.close()
    
    def _handle_clear_draft(self):
        """Clears all fields and the draft from the database after confirmation."""
        confirm = QMessageBox.question(self, "Confirm Clear",
            "Are you sure you want to clear the entire form and delete the draft from the database?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            self._clear_form_state(delete_draft=True)

    def _clear_form_state(self, delete_draft: bool):
        """Helper to reset the entire form's UI and optionally the database draft."""
        if delete_draft:
            session = self.Session()
            try:
                clear_user_draft(session, self.user_id)
            finally:
                session.close()
        
        self._clear_all_rows()
        self._fetch_and_set_next_ref_no()
        self.date_input.setDate(QDate.currentDate())
        now = datetime.now().strftime("%H:%M")
        self.time_start_input.setText(now)
        self.time_end_input.setText(now)
        self._add_row_widget()