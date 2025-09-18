from datetime import datetime
from typing import Type, Callable
from pydantic import ValidationError

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QMessageBox, QHeaderView, QLineEdit,
    QAbstractItemView, QGroupBox, QLabel, QDateEdit,
    QTimeEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QComboBox, QFormLayout
)
from PyQt6.QtCore import pyqtSignal, Qt, QDate, QTime
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

# Import the corrected database operations and validators
from ...database.mixer_draft_ops import get_user_draft, save_draft, clear_user_draft, finalize_draft_to_permanent
from ...database.mixer_machine_ops import get_active_machines
from ...validators.mixer_form_validators import MixerDetailCreateValidator, MixerHeaderDataValidator, \
    MixerFinalSubmissionValidator


class MixerFormView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.user_id = 1

        self._setup_ui()
        self._connect_signals()
        self._load_draft_from_db()

    def _setup_ui(self):
        # ... UI setup remains identical to your version ...
        main_layout = QVBoxLayout(self)
        header_group = QGroupBox("Header Information")
        header_layout = QFormLayout(header_group)
        self.ref_no_input = QLineEdit()
        self.date_input = QDateEdit(calendarPopup=True, date=QDate.currentDate())
        self.time_start_input = QTimeEdit(time=QTime.currentTime())
        self.time_end_input = QTimeEdit(time=QTime.currentTime())
        header_layout.addRow("Reference No:", self.ref_no_input)
        header_layout.addRow("Date:", self.date_input)
        header_layout.addRow("Shift Time Start:", self.time_start_input)
        header_layout.addRow("Shift Time End:", self.time_end_input)

        detail_group = QGroupBox("Add Production Detail")
        detail_layout = QFormLayout(detail_group)
        self.machine_input = QComboBox()
        self.product_code_input = QLineEdit()
        self.lot_no_input = QLineEdit()
        self.lot_count_input = QSpinBox(minimum=1)
        self.proc_time_start_input = QTimeEdit()
        self.proc_time_end_input = QTimeEdit()
        self.processed_by_input = QLineEdit()
        self.output_qty_input = QDoubleSpinBox(minimum=0.01)
        self.clean_time_start_input = QTimeEdit()
        self.clean_time_end_input = QTimeEdit()
        self.clean_rm_code_input = QLineEdit()
        self.clean_qty_input = QDoubleSpinBox(minimum=0.01)
        self.remarks_input = QTextEdit()
        detail_layout.addRow("Machine:", self.machine_input)
        detail_layout.addRow("Product Code:", self.product_code_input)
        detail_layout.addRow("Lot No:", self.lot_no_input)
        detail_layout.addRow("Lot Count:", self.lot_count_input)
        detail_layout.addRow("Process Time Start:", self.proc_time_start_input)
        detail_layout.addRow("Process Time End:", self.proc_time_end_input)
        detail_layout.addRow("Processed By:", self.processed_by_input)
        detail_layout.addRow("Output Qty (kg):", self.output_qty_input)
        detail_layout.addRow("Cleaning Time Start:", self.clean_time_start_input)
        detail_layout.addRow("Cleaning Time End:", self.clean_time_end_input)
        detail_layout.addRow("Cleaning RM Code:", self.clean_rm_code_input)
        detail_layout.addRow("Cleaning Qty (kg):", self.clean_qty_input)
        detail_layout.addRow("Remarks:", self.remarks_input)
        self.add_detail_button = QPushButton("Add Record to Batch")
        detail_layout.addRow(self.add_detail_button)

        staged_group = QGroupBox("Current Batch Records")
        staged_layout = QVBoxLayout(staged_group)
        self.staged_table = QTableWidget()
        self.staged_table.setColumnCount(5)
        self.staged_table.setHorizontalHeaderLabels(["Machine", "Product Code", "Lot No", "Lot Count", "Output Qty"])
        self.staged_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        staged_layout.addWidget(self.staged_table)

        final_actions_layout = QHBoxLayout()
        self.clear_form_button = QPushButton("Clear Entire Form")
        self.save_all_button = QPushButton("Save Batch to Database")
        final_actions_layout.addWidget(self.clear_form_button)
        final_actions_layout.addStretch()
        final_actions_layout.addWidget(self.save_all_button)

        main_layout.addWidget(header_group)
        main_layout.addWidget(detail_group)
        main_layout.addWidget(staged_group)
        main_layout.addLayout(final_actions_layout)

    def _connect_signals(self):
        self.add_detail_button.clicked.connect(self._handle_add_detail)
        self.clear_form_button.clicked.connect(self._handle_clear_form)
        self.save_all_button.clicked.connect(self._handle_save_all)

    def _populate_machine_combobox(self):
        session = self.Session()
        try:
            machines = get_active_machines(session)
            # Store machine names in a dictionary for easy lookup {id: name}
            self.machine_map = {m.id: m.name for m in machines}
            self.machine_input.clear()
            self.machine_input.addItem("Select a Machine...", userData=None)
            for machine_id, machine_name in self.machine_map.items():
                self.machine_input.addItem(machine_name, userData=machine_id)
        finally:
            session.close()

    def _load_draft_from_db(self):
        """On startup, checks for and loads an existing user draft."""
        self._populate_machine_combobox()
        session = self.Session()
        try:
            draft = get_user_draft(session, self.user_id)
            self.staged_table.setRowCount(0)  # Always clear the visual table first
            if draft:
                # Populate header fields
                if draft.reference_no: self.ref_no_input.setText(str(draft.reference_no))
                if draft.date: self.date_input.setDate(QDate(draft.date))
                if draft.time_start: self.time_start_input.setTime(QTime(draft.time_start))
                if draft.time_end: self.time_end_input.setTime(QTime(draft.time_end))

                # Populate the staged items table from the draft
                for detail in draft.details:
                    self._add_row_to_staged_table(detail)
        finally:
            session.close()

    def _handle_add_detail(self):
        """Gathers data, validates it, and saves it to the draft in the database."""
        session = self.Session()
        try:
            # 1. Gather and Validate Header Data
            ref_no_text = self.ref_no_input.text()
            header_data = MixerHeaderDataValidator(
                reference_no=int(ref_no_text) if ref_no_text.strip().isdigit() else None,
                date=self.date_input.date().toPyDate(),
                time_start=self.time_start_input.time().toPyTime(),
                time_end=self.time_end_input.time().toPyTime()
            )

            # 2. Gather and Validate Detail Data
            machine_id = self.machine_input.currentData()
            if not machine_id:
                raise ValueError("A machine must be selected.")

            detail_data = MixerDetailCreateValidator(
                mc_id=machine_id,
                product_code=self.product_code_input.text(),
                lot_no=self.lot_no_input.text(),
                lot_count=self.lot_count_input.value(),
                process_time_start=self.proc_time_start_input.time().toPyTime(),
                process_time_end=self.proc_time_end_input.time().toPyTime(),
                processed_by=self.processed_by_input.text(),
                output_qty=self.output_qty_input.value(),
                cleaning_time_start=self.clean_time_start_input.time().toPyTime(),
                cleaning_time_end=self.clean_time_end_input.time().toPyTime(),
                cleaning_rm_code=self.clean_rm_code_input.text(),
                cleaning_qty=self.clean_qty_input.value(),
                remarks=self.remarks_input.toPlainText()
            )

            # 3. Save draft to DB and update UI
            save_draft(session, self.user_id, header_data, detail_data)
            self._add_row_to_staged_table(detail_data)  # Add the new validated data to the table
            self._clear_detail_entry_form()
            QMessageBox.information(self, "Record Added", "The record has been added to your draft.")

        except ValueError as e:
            QMessageBox.warning(self, "Input Error", str(e))
        except ValidationError as e:
            QMessageBox.warning(self, "Validation Error", f"Please check all fields:\n{e}")
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not save draft: {e}")
        finally:
            session.close()

    def _add_row_to_staged_table(self, detail):
        """Visually adds a row. Can handle ORM objects or Pydantic models."""
        row_pos = self.staged_table.rowCount()
        self.staged_table.insertRow(row_pos)
        machine_name = self.machine_map.get(detail.mc_id, "Unknown")
        self.staged_table.setItem(row_pos, 0, QTableWidgetItem(machine_name))
        self.staged_table.setItem(row_pos, 1, QTableWidgetItem(detail.product_code))
        self.staged_table.setItem(row_pos, 2, QTableWidgetItem(detail.lot_no))
        self.staged_table.setItem(row_pos, 3, QTableWidgetItem(str(detail.lot_count)))
        self.staged_table.setItem(row_pos, 4, QTableWidgetItem(str(detail.output_qty)))

    def _handle_save_all(self):
        """Validates the complete form and finalizes the draft to permanent tables."""
        session = self.Session()
        try:
            # Validate the final header data separately.
            final_header_data = MixerFinalSubmissionValidator(
                reference_no=int(self.ref_no_input.text()),
                date=self.date_input.date().toPyDate(),
                time_start=self.time_start_input.time().toPyTime(),
                time_end=self.time_end_input.time().toPyTime()
            )

            # Call the finalization function.
            finalize_draft_to_permanent(session, self.user_id, final_header_data)
            QMessageBox.information(self, "Success", "Batch has been saved successfully to the permanent records.")
            # Clear the form completely after a successful final save.
            self._clear_form_state()

        except (ValueError, TypeError):
            QMessageBox.warning(self, "Input Error",
                                "Reference Number must be a valid number and all header fields must be filled for final submission.")
        except ValidationError as e:
            QMessageBox.warning(self, "Validation Error", f"Cannot save batch. Please check header fields:\n{e}")
        except IntegrityError as e:
            QMessageBox.critical(self, "Save Failed", str(e))
        except Exception as e:
            QMessageBox.critical(self, "An Error Occurred", f"Could not save the batch: {e}")
        finally:
            session.close()

    def _handle_clear_form(self):
        """Clears all fields and the draft from the database after confirmation."""
        confirm = QMessageBox.question(self, "Confirm Clear",
                                       "Are you sure you want to clear the entire form? This will permanently delete your current draft.",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if confirm == QMessageBox.StandardButton.Yes:
            session = self.Session()
            try:
                clear_user_draft(session, self.user_id)
                self._clear_form_state()  # Update the UI
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not clear draft: {e}")
            finally:
                session.close()

    def _clear_form_state(self):
        """Helper to reset the entire form's UI to a blank state."""
        self.ref_no_input.clear()
        self.date_input.setDate(QDate.currentDate())
        self.time_start_input.setTime(QTime(0, 0, 0))
        self.time_end_input.setTime(QTime(0, 0, 0))
        self._clear_detail_entry_form()
        self.staged_table.setRowCount(0)

    def _clear_detail_entry_form(self):
        self.product_code_input.clear()
        self.lot_no_input.clear()
        self.lot_count_input.setValue(1)
        self.processed_by_input.clear()
        self.output_qty_input.setValue(0.01)
        self.clean_rm_code_input.clear()
        self.clean_qty_input.setValue(0.01)
        self.remarks_input.clear()
        self.machine_input.setCurrentIndex(0)
        self.product_code_input.setFocus()