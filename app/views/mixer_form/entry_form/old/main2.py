import os
import re
from datetime import datetime
from typing import Type, Callable
from pydantic import ValidationError
import qtawesome as qta
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView, QLineEdit,
    QAbstractItemView, QGroupBox, QLabel, QDateEdit, QGridLayout,
    QSpinBox, QDoubleSpinBox, QTextEdit, QComboBox, QMenu
)
from PyQt6.QtCore import pyqtSignal, Qt, QDate, QEvent
from PyQt6.QtGui import QAction
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

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


class MixerFormView(QWidget):
    """
    The main view for the Mixer Form, featuring an Excel-like interface for
    staging production details before final submission.
    """

    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.user_id = 1
        self.machine_map = {}

        self.setObjectName("MixerFormModule")
        self._setup_ui()
        self._connect_signals()

        self.staged_table.installEventFilter(self)
        load_stylesheet(self)
        self._load_draft_from_db()

    def eventFilter(self, source, event):
        """Captures keyboard events on the table to handle shortcuts."""
        if (event.type() == QEvent.Type.KeyPress and
                source is self.staged_table and
                event.key() == Qt.Key.Key_Return and
                (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
            self._handle_add_row()
            return True
        return super().eventFilter(source, event)

    def _setup_ui(self):
        """Initializes and arranges all widgets for the user interface."""
        main_layout = QVBoxLayout(self)

        header_group = QGroupBox("Header Information")
        header_layout = QGridLayout(header_group)
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

        staged_group = QGroupBox("Production Details (Press Shift+Enter to add a new row)")
        staged_layout = QVBoxLayout(staged_group)

        table_toolbar_layout = QHBoxLayout()
        self.add_row_button = QPushButton("Add New Row")
        self.save_draft_button = QPushButton("Save Draft")
        self.save_draft_button.setObjectName("PrimaryButton")
        table_toolbar_layout.addWidget(self.add_row_button)
        table_toolbar_layout.addStretch()
        table_toolbar_layout.addWidget(self.save_draft_button)

        self.staged_table = QTableWidget()
        # --- NEW: Added a 'Delete' column ---
        self.staged_table.setColumnCount(15)
        self.staged_table.setHorizontalHeaderLabels([
            "Detail ID", "Machine", "Product Code", "Lot No", "Lot Count",
            "Process Start", "Process End", "Processed By", "Output Qty",
            "Cleaning Start", "Cleaning End", "Cleaning RM Code", "Cleaning Qty", "Remarks", ""
        ])
        self.staged_table.setColumnHidden(0, True)
        self.staged_table.horizontalHeader().setSectionResizeMode(14, QHeaderView.ResizeMode.ResizeToContents)

        staged_layout.addLayout(table_toolbar_layout)
        staged_layout.addWidget(self.staged_table)

        final_actions_layout = QHBoxLayout()
        self.clear_form_button = QPushButton("Clear & Delete Draft")
        self.save_all_button = QPushButton("Finalize and Save Batch")
        self.clear_form_button.setObjectName("DangerButton")
        self.save_all_button.setObjectName("SuccessButton")
        final_actions_layout.addWidget(self.clear_form_button)
        final_actions_layout.addStretch()
        final_actions_layout.addWidget(self.save_all_button)

        main_layout.addWidget(header_group)
        main_layout.addWidget(staged_group)
        main_layout.addLayout(final_actions_layout)

    def _connect_signals(self):
        """Connects all widget signals to their respective handler methods."""
        self.add_row_button.clicked.connect(self._handle_add_row)
        self.save_draft_button.clicked.connect(self._handle_save_draft)
        self.clear_form_button.clicked.connect(self._handle_clear_draft)
        self.save_all_button.clicked.connect(self._handle_finalize)
        self.staged_table.customContextMenuRequested.connect(self.show_staged_table_context_menu)

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
            # Block signals to prevent unintended triggers while populating
            self.staged_table.blockSignals(True)
            self.staged_table.setRowCount(0)

            if draft:
                self.ref_no_input.setText(
                    str(draft.reference_no).zfill(6)) if draft.reference_no else self._fetch_and_set_next_ref_no()
                if draft.date: self.date_input.setDate(QDate(draft.date))
                if draft.time_start: self.time_start_input.setText(draft.time_start.strftime("%H:%M"))
                if draft.time_end: self.time_end_input.setText(draft.time_end.strftime("%H:%M"))
                for detail in sorted(draft.details, key=lambda d: d.created_at):
                    self._add_row_to_table(detail)
            else:
                self._fetch_and_set_next_ref_no()
        finally:
            self.staged_table.blockSignals(False)
            session.close()

    def _fetch_and_set_next_ref_no(self):
        """Gets the next available reference number and populates the input field."""
        session = self.Session()
        try:
            next_ref = get_next_reference_no(session)
            self.ref_no_input.setText(str(next_ref).zfill(6))
        finally:
            session.close()

    def _add_row_to_table(self, detail=None):
        """Adds a new row to the table and populates it with editable widgets and data."""
        row_pos = self.staged_table.rowCount()
        self.staged_table.insertRow(row_pos)

        machine_combo = QComboBox()
        for machine_id, machine_name in self.machine_map.items():
            machine_combo.addItem(machine_name, userData=machine_id)

        lot_no_edit = QLineEdit(getattr(detail, 'lot_no', ''))
        lot_count_spin = QSpinBox(minimum=1, maximum=9999, value=getattr(detail, 'lot_count', 1))
        lot_no_edit.textChanged.connect(lambda text, spin=lot_count_spin: self._calculate_lot_count(text, spin))

        widgets = {
            0: QTableWidgetItem(str(getattr(detail, 'id', ''))),
            1: machine_combo,
            2: QLineEdit(getattr(detail, 'product_code', '')),
            3: lot_no_edit,
            4: lot_count_spin,
            5: TimeLineEdit(getattr(detail, 'process_time_start', None)),
            6: TimeLineEdit(getattr(detail, 'process_time_end', None)),
            7: QLineEdit(getattr(detail, 'processed_by', '')),
            8: QDoubleSpinBox(minimum=0.01, decimals=2, value=getattr(detail, 'output_qty', 0.01)),
            9: TimeLineEdit(getattr(detail, 'cleaning_time_start', None)),
            10: TimeLineEdit(getattr(detail, 'cleaning_time_end', None)),
            11: QLineEdit(getattr(detail, 'cleaning_rm_code', '')),
            12: QDoubleSpinBox(minimum=0.01, decimals=2, value=getattr(detail, 'cleaning_qty', 0.01)),
            13: QLineEdit(getattr(detail, 'remarks', ''))
        }

        if detail:
            machine_combo.setCurrentIndex(machine_combo.findData(detail.mc_id))

        for col, widget in widgets.items():
            if isinstance(widget, QWidget):
                self.staged_table.setCellWidget(row_pos, col, widget)
            else:
                self.staged_table.setItem(row_pos, col, widget)

        self.staged_table.setCurrentCell(row_pos, 2)

        delete_button = QPushButton()
        delete_button.setIcon(qta.icon("fa5s.times", color="red"))
        delete_button.setToolTip("Delete this row")
        # Store the row number this button belongs to
        delete_button.setProperty("row", row_pos)
        delete_button.clicked.connect(self._handle_delete_row_button_click)

        # Add the button to the last column
        self.staged_table.setCellWidget(row_pos, 14, delete_button)

    def _handle_add_row(self):
        """Handles the 'Add New Row' button click or Shift+Enter shortcut."""
        self._add_row_to_table()

    def _gather_data_from_ui(self) -> tuple[MixerHeaderDataValidator, list[MixerDetailCreateValidator]]:
        """A helper method to read and validate all data from the UI."""
        header_data = MixerHeaderDataValidator(
            reference_no=int(self.ref_no_input.text()) if self.ref_no_input.text() else None,
            date=self.date_input.date().toPyDate(),
            time_start=self.time_start_input.text(),
            time_end=self.time_end_input.text()
        )

        details_to_save = []
        for row in range(self.staged_table.rowCount()):
            detail_data = MixerDetailCreateValidator(
                mc_id=self.staged_table.cellWidget(row, 1).currentData(),
                product_code=self.staged_table.cellWidget(row, 2).text(),
                lot_no=self.staged_table.cellWidget(row, 3).text(),
                lot_count=self.staged_table.cellWidget(row, 4).value(),
                process_time_start=self.staged_table.cellWidget(row, 5).text(),
                process_time_end=self.staged_table.cellWidget(row, 6).text(),
                processed_by=self.staged_table.cellWidget(row, 7).text(),
                output_qty=self.staged_table.cellWidget(row, 8).value(),
                cleaning_time_start=self.staged_table.cellWidget(row, 9).text(),
                cleaning_time_end=self.staged_table.cellWidget(row, 10).text(),
                cleaning_rm_code=self.staged_table.cellWidget(row, 11).text(),
                cleaning_qty=self.staged_table.cellWidget(row, 12).value(),
                remarks=self.staged_table.cellWidget(row, 13).text()
            )
            details_to_save.append(detail_data)

        return header_data, details_to_save

    def _handle_save_draft(self):
        """Reads all data from the table, validates, and syncs with the database."""
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
        """Finalizes the draft to permanent records."""
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
            self._clear_form_state(delete_draft=False)  # Draft is already deleted by finalize function
            self._fetch_and_set_next_ref_no()
        except (ValueError, ValidationError) as e:
            QMessageBox.warning(self, "Validation Error", f"Cannot finalize batch:\n{e}")
        except IntegrityError as e:
            QMessageBox.critical(self, "Save Failed", str(e))
        except Exception as e:
            QMessageBox.critical(self, "An Error Occurred", f"Could not save batch: {e}")
        finally:
            session.close()

    def show_staged_table_context_menu(self, position):
        """Shows a context menu to delete a staged item."""
        item = self.staged_table.itemAt(position)
        if not item: return

        context_menu = QMenu(self)
        delete_action = QAction("Delete this row", self)
        context_menu.addAction(delete_action)

        row = item.row()
        detail_id_item = self.staged_table.item(row, 0)

        if detail_id_item and detail_id_item.text():
            detail_id = int(detail_id_item.text())
            delete_action.triggered.connect(lambda: self._handle_delete_staged_item(detail_id))
        else:
            delete_action.setText("Remove new row")
            delete_action.triggered.connect(lambda: self.staged_table.removeRow(row))

        context_menu.exec(self.staged_table.mapToGlobal(position))

    def _handle_delete_staged_item(self, detail_id: int):
        """Deletes a single item from the draft and refreshes the UI."""
        confirm = QMessageBox.question(self, "Confirm Delete",
                                       "Are you sure you want to permanently delete this record from the draft?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if confirm == QMessageBox.StandardButton.Yes:
            session = self.Session()
            try:
                delete_staged_detail(session, detail_id)
                self._load_draft_from_db()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete item: {e}")
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

        self.staged_table.setRowCount(0)
        self._fetch_and_set_next_ref_no()
        self.date_input.setDate(QDate.currentDate())
        now = datetime.now().strftime("%H:%M")
        self.time_start_input.setText(now)
        self.time_end_input.setText(now)

    def _calculate_lot_count(self, text: str, target_spinbox: QSpinBox):
        """Auto-calculates lot count for a specific row's spinbox."""
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

    def _handle_delete_row_button_click(self):
        """Handles the click of any 'X' button in the table rows."""
        # Get the button that sent the signal
        sender_button = self.sender()
        if not sender_button:
            return

        # Retrieve the row number we stored in the button's property
        row_to_delete = sender_button.property("row")
        if row_to_delete is None:
            return

        detail_id_item = self.staged_table.item(row_to_delete, 0)

        if detail_id_item and detail_id_item.text():
            # This is an existing record that needs to be deleted from the database
            detail_id = int(detail_id_item.text())
            self._handle_delete_staged_item(detail_id)
        else:
            # This is a new, unsaved row. Just remove it from the visual table.
            self.staged_table.removeRow(row_to_delete)
            # After removing, we must update the "row" property of all subsequent buttons
            self._update_button_row_indices()

    def _update_button_row_indices(self):
        """After a row is removed, this function updates the stored row number in the remaining buttons."""
        for row in range(self.staged_table.rowCount()):
            button = self.staged_table.cellWidget(row, 14)
            if button:
                button.setProperty("row", row)

    def _handle_delete_staged_item(self, detail_id: int):
        """Deletes a single item from the database draft and refreshes the UI."""
        confirm = QMessageBox.question(self, "Confirm Delete",
                                       "This record is saved in your draft. Are you sure you want to permanently delete it?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

        if confirm == QMessageBox.StandardButton.Yes:
            session = self.Session()
            try:
                delete_staged_detail(session, detail_id)
                self._load_draft_from_db()  # Reload the entire draft to ensure consistency
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete item: {e}")
            finally:
                session.close()