# app/views/extruder_form/records/main.py

import decimal
from datetime import datetime, timedelta

from PyQt6.QtWidgets import QWidget, QTableWidgetItem, QMessageBox, QApplication, QMenu, QDialog
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDate, QPoint
from PyQt6.QtGui import QColor, QBrush, QAction
from sqlalchemy.orm import Session
from typing import Type

from .edit_dialog import ExtruderEditDialog
from .ui_setup import Ui_ExtruderRecordsList
from .ops import ExtruderRecordsOperations
from .view_dialog import ExtruderRecordViewDialog

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
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.refresh_data)
        self.ui.search_input.textChanged.connect(lambda: self.search_timer.start(500))
        self.ui.date_from_input.dateChanged.connect(self.refresh_data)
        self.ui.date_to_input.dateChanged.connect(self.refresh_data)
        self.ui.show_deleted_checkbox.stateChanged.connect(self.refresh_data)
        self.ui.table_widget.doubleClicked.connect(self._view_record)
        self.ui.table_widget.customContextMenuRequested.connect(self._show_context_menu)

    def _show_context_menu(self, position: QPoint):
        index = self.ui.table_widget.indexAt(position)
        if not index.isValid(): return
        self.ui.table_widget.selectRow(index.row())
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None: return

        context_menu = QMenu(self)
        view_action = QAction("View Record", self)
        # --- NEW: Add Edit action ---
        edit_action = QAction("Edit Record", self)
        delete_action = QAction("Delete Record", self)
        restore_action = QAction("Restore Record", self)
        view_action.triggered.connect(self._view_record)
        edit_action.triggered.connect(self._edit_record)
        delete_action.triggered.connect(self._delete_record)
        restore_action.triggered.connect(self._restore_record)

        if not is_deleted:
            context_menu.addAction(view_action)
            context_menu.addAction(edit_action) # <-- Add to menu
            context_menu.addSeparator()
            context_menu.addAction(delete_action)
        else:
            context_menu.addAction(restore_action)
        context_menu.exec(self.ui.table_widget.mapToGlobal(position))

    def refresh_data(self):
        self._load_records()

    def load_initial_data(self):
        self._load_records()

    # def _load_records(self):
    #     if self.is_loading: return
    #     self.is_loading = True
    #     QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
    #     self.ui.table_widget.setRowCount(0)
    #     try:
    #         date_from = self.ui.date_from_input.date()
    #         date_to = self.ui.date_to_input.date()
    #         date_from_pass = date_from.toPyDate() if date_from.isValid() else None
    #         date_to_pass = date_to.toPyDate() if date_to.isValid() else None
    #         records = self.ops.get_records_with_details(
    #             search_term=self.ui.search_input.text(),
    #             date_from=date_from_pass, date_to=date_to_pass,
    #             show_deleted=self.ui.show_deleted_checkbox.isChecked()
    #         )
    #         for record_data in records:
    #             self._add_record_to_table(record_data)
    #     except Exception as e:
    #         QMessageBox.critical(self, "Database Error", f"Could not load records:\n\n{e}")
    #     finally:
    #         self.is_loading = False
    #         QApplication.restoreOverrideCursor()

    def _load_records(self):
        if self.is_loading: return
        self.is_loading = True
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.ui.table_widget.setRowCount(0)
        try:
            date_from = self.ui.date_from_input.date()
            date_to = self.ui.date_to_input.date()
            date_from_pass = date_from.toPyDate() if date_from.isValid() else None
            date_to_pass = date_to.toPyDate() if date_to.isValid() else None

            # This now returns a list of ORM objects
            records = self.ops.get_records_with_details(
                search_term=self.ui.search_input.text(),
                date_from=date_from_pass,
                date_to=date_to_pass,
                show_deleted=self.ui.show_deleted_checkbox.isChecked()
            )

            # The add_record_to_table method will now handle the calculations
            for record_object in records:
                self._add_record_to_table(record_object)
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not load records:\n\n{e}")
        finally:
            self.is_loading = False
            QApplication.restoreOverrideCursor()


    # def _add_record_to_table(self, data: dict):
    #     row_pos = self.ui.table_widget.rowCount()
    #     self.ui.table_widget.insertRow(row_pos)
    #     form_data = data['form_data']
    #     def fmt_dt(dt): return dt.strftime("%Y-%m-%d %H:%M") if dt else "N/A"
    #     def fmt_dec(d): return f"{d or 0:.2f}"
    #     cell_data = {
    #         0: str(form_data.id), 1: fmt_dt(form_data.created_at),
    #         2: data.get('machine_name', 'N/A'), 3: form_data.product_code,
    #         4: form_data.lot_number, 5: fmt_dt(data.get('datetime_start')),
    #         6: fmt_dt(data.get('datetime_end')), 7: fmt_dec(data.get('output_per_hour')),
    #         # 8: fmt_dec(getattr(form_data, 'target_output_hour', None)),
    #         8: fmt_dec(getattr(form_data, 'target_output_per_hour', None)),
    #         9: fmt_dec(data.get('total_output_qty')), 10: data.get('purging_to_code') or "N/A",
    #         11: str(data.get('total_purging_time')) if data.get('total_purging_time') else "0:00:00",
    #         12: data.get('operators') or "N/A"
    #     }
    #     for col, text in cell_data.items():
    #         item = QTableWidgetItem(text)
    #         if form_data.is_deleted:
    #             item.setBackground(QBrush(self.is_deleted_color))
    #             item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
    #         self.ui.table_widget.setItem(row_pos, col, item)

    def _add_record_to_table(self, record):
        """
        --- THIS METHOD IS NOW CORRECTED ---
        Accepts a fully-loaded SQLAlchemy object and performs calculations
        before populating the table row.
        """
        row_pos = self.ui.table_widget.rowCount()
        self.ui.table_widget.insertRow(row_pos)

        # --- Python-side Calculations ---
        total_output = sum(out.qty_output for out in record.extruder_outputs if out.qty_output)

        purging_codes = ", ".join([p.product_code for p in record.purging_headers if p.product_code])

        total_purging_seconds = 0
        for p in record.purging_headers:
            if p.time_start and p.time_end:
                dummy_date = datetime.now().date()
                start_dt = datetime.combine(dummy_date, p.time_start)
                end_dt = datetime.combine(dummy_date, p.time_end)
                if end_dt < start_dt: end_dt += timedelta(days=1)
                total_purging_seconds += (end_dt - start_dt).total_seconds()

        purging_hours, rem = divmod(total_purging_seconds, 3600)
        purging_minutes, _ = divmod(rem, 60)
        purging_time_str = f"{int(purging_hours):02d}:{int(purging_minutes):02d}"

        operators = ", ".join([
            f"{p.employee.first_name} {p.employee.last_name}"
            for p in record.extruder_personnels if p.employee
        ])

        # Helper functions
        def fmt_dt(dt):
            return dt.strftime("%Y-%m-%d %H:%M") if dt else "N/A"

        def fmt_dec(val):
            return f"{val or 0:.2f}"

        # Get start and end times from the outputs
        start_times = [out.datetime_start for out in record.extruder_outputs if out.datetime_start]
        end_times = [out.datetime_end for out in record.extruder_outputs if out.datetime_end]

        cell_data = {
            0: str(record.id),
            1: fmt_dt(record.created_at),
            2: getattr(record.machine, 'name', 'N/A'),
            3: record.product_code,
            4: record.lot_number,
            5: fmt_dt(min(start_times) if start_times else None),
            6: fmt_dt(max(end_times) if end_times else None),
            7: "0.00",  # Output/hr is complex, can be added back later if needed
            8: fmt_dec(getattr(record, 'target_output_per_hour', None)),
            9: fmt_dec(total_output),
            10: purging_codes or "N/A",
            11: purging_time_str,
            12: operators or "N/A"
        }

        for col, text in cell_data.items():
            item = QTableWidgetItem(text)
            if record.is_deleted:
                item.setBackground(QBrush(QColor("#e0e0e0")))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            self.ui.table_widget.setItem(row_pos, col, item)

    def _get_selected_record_info(self):
        selected_rows = self.ui.table_widget.selectionModel().selectedRows()
        if not selected_rows: return None, False
        row = selected_rows[0].row()
        record_id = int(self.ui.table_widget.item(row, 0).text())
        is_deleted = self.ui.table_widget.item(row, 0).background().color() == self.is_deleted_color
        return record_id, is_deleted

    def _delete_record(self):
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None or is_deleted: return
        reply = QMessageBox.question(self, 'Confirm Deletion', f"Delete record ID: {record_id}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.ops.soft_delete_record(record_id):
                self.refresh_data(); self.data_changed.emit()
            else:
                QMessageBox.critical(self, "Error", "Failed to delete the record.")

    def _restore_record(self):
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None or not is_deleted: return
        if self.ops.restore_record(record_id):
            self.refresh_data(); self.data_changed.emit()
        else:
            QMessageBox.critical(self, "Error", "Failed to restore the record.")

    def _view_record(self):
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None or is_deleted: return
        full_data = self.ops.get_full_record_by_id(record_id)
        if full_data:
            view_dialog = ExtruderRecordViewDialog(self)
            view_dialog.populate_data(full_data)
            view_dialog.exec()
        else:
            QMessageBox.warning(self, "Not Found", "Could not retrieve full record details.")

    def _edit_record(self):  # New method for editing
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None or is_deleted: return

        full_data = self.ops.get_full_record_by_id(record_id)
        if full_data:
            # Create and execute the edit dialog

            edit_dialog = ExtruderEditDialog(self.ops.Session, full_data, self)

            # When the dialog is accepted (saved), refresh the main table.
            if edit_dialog.exec() == QDialog.DialogCode.Accepted:
                self.refresh_data()
        else:
            QMessageBox.warning(self, "Not Found", "Could not retrieve full record details for editing.")