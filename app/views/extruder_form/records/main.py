# app/views/extruder_form/records/main.py
import decimal

from PyQt6.QtWidgets import QWidget, QTableWidgetItem, QMessageBox, QApplication
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDate
from PyQt6.QtGui import QColor, QBrush
from sqlalchemy.orm import Session
from typing import Type

from .ui_setup import Ui_ExtruderRecordsList
from .ops import ExtruderRecordsOperations


# Uncomment when ready to integrate
# from app.views.extruder_form.entry.main import ExtruderEntryFormView

class ExtruderRecordsView(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, session_factory: Type[Session], parent=None):
        super().__init__(parent)

        self.ui = Ui_ExtruderRecordsList()
        self.ui.setupUi(self)

        self.ops = ExtruderRecordsOperations(session_factory)

        self.is_loading = False
        self.is_deleted_color = QColor("#e0e0e0")

        self._setup_connections()
        self.load_initial_data()

    def _setup_connections(self):
        # ... (connections remain the same, but remove the lazy_load_data connection) ...
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.refresh_data)
        self.ui.search_input.textChanged.connect(lambda: self.search_timer.start(500))
        self.ui.date_filter_input.dateChanged.connect(self.refresh_data)
        self.ui.show_deleted_checkbox.stateChanged.connect(self.refresh_data)
        self.ui.table_widget.itemSelectionChanged.connect(self._update_button_states)
        self.ui.table_widget.doubleClicked.connect(self._edit_view_record)
        self.ui.delete_button.clicked.connect(self._delete_record)
        self.ui.restore_button.clicked.connect(self._restore_record)
        self.ui.edit_view_button.clicked.connect(self._edit_view_record)
        self.ui.clear_date_button.clicked.connect(self._clear_date_filter)
        

    def _clear_date_filter(self):
        """Clears the date in the QDateEdit, which will trigger a refresh."""
        self.ui.date_filter_input.setDate(QDate()) # Sets to a null/invalid date



    def refresh_data(self):
        """Public slot to refresh data from scratch."""
        self._load_records()


    def _trigger_filter_refresh(self):
        """Public slot to refresh data, can be connected from outside signals."""
        self.current_page = 1
        self.ui.table_widget.setRowCount(0)
        self._load_records()

    def load_initial_data(self):
        """Loads the first page of data when the widget is first shown."""
        self._load_records()

    def _load_records(self):
        if self.is_loading:
            return

        self.is_loading = True
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.ui.table_widget.setRowCount(0)

        try:
            # FIX: Date filter logic is now smarter
            filter_date = self.ui.date_filter_input.date()
            date_to_pass = filter_date.toPyDate() if filter_date.isValid() else None

            records = self.ops.get_records_with_details(
                search_term=self.ui.search_input.text(),
                filter_date=date_to_pass,  # Pass either a date or None
                show_deleted=self.ui.show_deleted_checkbox.isChecked()
            )
            for record_data in records:
                self._add_record_to_table(record_data)
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not load records:\n\n{e}")
        finally:
            self.is_loading = False
            QApplication.restoreOverrideCursor()
            self._update_button_states()

    def _add_record_to_table(self, data: dict):
        row_pos = self.ui.table_widget.rowCount()
        self.ui.table_widget.insertRow(row_pos)

        form_data = data['form_data']

        # Helper for formatting
        def fmt_datetime(dt):
            return dt.strftime("%Y-%m-%d %H:%M") if dt else "N/A"

        def fmt_decimal(d, places=2):
            return f"{d:.{places}f}" if isinstance(d, (decimal.Decimal, float)) and d > 0 else "0.00"

        # Prepare cell data
        cell_data = {
            0: str(form_data.id),
            1: fmt_datetime(form_data.created_at),
            2: data.get('machine_name', 'N/A'),
            3: form_data.product_code,
            4: form_data.lot_number,
            5: fmt_datetime(data.get('datetime_start')),
            6: fmt_datetime(data.get('datetime_end')),
            7: fmt_decimal(data.get('output_per_hour')),
            8: "N/A",  # Assuming 'target_output_hour' is not yet in the model
            9: fmt_decimal(data.get('total_output_qty')),
            10: data.get('purging_to_code') or "N/A",
            11: str(data.get('total_purging_time')) if data.get('total_purging_time') else "00:00:00",
            12: data.get('operators') or "N/A"
        }

        for col, text in cell_data.items():
            item = QTableWidgetItem(text)
            if form_data.is_deleted:
                item.setBackground(QBrush(self.is_deleted_color))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.ui.table_widget.setItem(row_pos, col, item)

    def _lazy_load_data(self, value):
        """Triggers loading the next page of data when the user scrolls to the bottom."""
        scrollbar = self.ui.table_widget.verticalScrollBar()
        # Trigger when scrollbar is near the bottom and there are more records to load
        if value >= scrollbar.maximum() * 0.9 and not self.is_loading:
            if self.ui.table_widget.rowCount() < self.total_records:
                self.current_page += 1
                self._load_records()

    def _get_selected_record_info(self):
        """Helper to get the ID and deletion status of the currently selected row."""
        selected_rows = self.ui.table_widget.selectionModel().selectedRows()
        if not selected_rows:
            return None, False

        row = selected_rows[0].row()
        record_id = int(self.ui.table_widget.item(row, 0).text())
        is_deleted = self.ui.table_widget.item(row, 0).background().color() == self.is_deleted_color

        return record_id, is_deleted

    def _update_button_states(self):
        """Enables or disables action buttons based on the selected record's status."""
        record_id, is_deleted = self._get_selected_record_info()

        has_selection = record_id is not None

        self.ui.edit_view_button.setEnabled(has_selection and not is_deleted)
        self.ui.delete_button.setEnabled(has_selection and not is_deleted)
        self.ui.restore_button.setEnabled(has_selection and is_deleted)

    def _delete_record(self):
        """Handles the soft-deletion of a selected record after user confirmation."""
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None or is_deleted:
            return

        reply = QMessageBox.question(self, 'Confirm Deletion',
                                     f"Are you sure you want to delete record ID: {record_id}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            if self.ops.soft_delete_record(record_id):
                QMessageBox.information(self, "Success", "Record deleted successfully.")
                self._trigger_filter_refresh()
                self.data_changed.emit()
            else:
                QMessageBox.critical(self, "Error", "Failed to delete the record.")

    def _restore_record(self):
        """Handles restoring a soft-deleted record."""
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None or not is_deleted:
            return

        if self.ops.restore_record(record_id):
            QMessageBox.information(self, "Success", "Record restored successfully.")
            self._trigger_filter_refresh()
            self.data_changed.emit()
        else:
            QMessageBox.critical(self, "Error", "Failed to restore the record.")

    def _edit_view_record(self):
        """Opens the ExtruderEntryForm for viewing or editing the selected record."""
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None or is_deleted:
            return

        full_data = self.ops.get_full_record_by_id(record_id)
        if full_data:
            # --- INTEGRATION POINT ---
            # This is where you instantiate and show your existing ExtruderEntryFormView.
            # You would create a method like `populate_form_for_editing(data_object)`
            # on that view and connect its `data_saved` signal back to `self._trigger_filter_refresh`.
            #
            # Example:
            # self.entry_form = ExtruderEntryFormView(self.ops.Session)
            # self.entry_form = ExtruderEntryFormView(self.ops.Session)
            # self.entry_form.data_saved.connect(self._trigger_filter_refresh)
            # self.entry_form.populate_for_editing(full_data)
            # self.entry_form.show()

            QMessageBox.information(self, "Edit / View",
                                    f"Ready to open form for Record ID: {record_id}.\nData has been fully loaded.")
        else:
            QMessageBox.warning(self, "Not Found", "Could not retrieve the full details for the selected record.")