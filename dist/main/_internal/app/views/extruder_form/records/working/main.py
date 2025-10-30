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
from .filter_dialog import FilterDialog


class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            self_data = float(self.data(Qt.ItemDataRole.UserRole))
        except (ValueError, TypeError):
            self_data = 0.0

        try:
            other_data = float(other.data(Qt.ItemDataRole.UserRole))
        except (ValueError, TypeError):
            other_data = 0.0

        return self_data < other_data


class ExtruderRecordsView(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, session_factory: Type[Session], parent=None):
        super().__init__(parent)
        self.ui = Ui_ExtruderRecordsList()
        self.ui.setupUi(self)
        self.ops = ExtruderRecordsOperations(session_factory)

        self.filter_dialog = FilterDialog(session_factory, self)
        self.advanced_filters = {}

        self.is_loading = False
        self.is_deleted_color = QColor("#e0e0e0")

        self._setup_connections()
        self.load_initial_data()

        # --- FIX: Corrected the attribute name from DescendingSort to DescendingOrder ---
        self.ui.table_widget.sortByColumn(1, Qt.SortOrder.DescendingOrder)

    def _setup_connections(self):
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.refresh_data)
        self.ui.search_input.textChanged.connect(lambda: self.search_timer.start(500))
        self.ui.date_from_input.dateChanged.connect(self.refresh_data)
        self.ui.date_to_input.dateChanged.connect(self.refresh_data)

        self.ui.advanced_filter_button.clicked.connect(self._open_filter_dialog)
        self.ui.clear_filters_button.clicked.connect(self._clear_all_filters)

        self.ui.show_only_deleted_checkbox.stateChanged.connect(self.refresh_data)

        self.ui.table_widget.doubleClicked.connect(self._view_record)
        self.ui.table_widget.customContextMenuRequested.connect(self._show_context_menu)

    def _open_filter_dialog(self):
        self.filter_dialog.populate_dropdowns()
        if self.filter_dialog.exec() == QDialog.DialogCode.Accepted:
            self.advanced_filters = self.filter_dialog.get_filters()
            self.refresh_data()

    def _clear_all_filters(self):
        self.ui.search_input.clear()
        self.ui.date_from_input.setDate(QDate.currentDate().addMonths(-1))
        self.ui.date_to_input.setDate(QDate.currentDate())
        self.advanced_filters.clear()
        self.refresh_data()

    def refresh_data(self):
        self._load_records()

    def load_initial_data(self):
        self._load_records()

    def _load_records(self):
        if self.is_loading: return
        self.is_loading = True
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)

        self.ui.table_widget.setSortingEnabled(False)
        self.ui.table_widget.setRowCount(0)

        try:
            all_filters = self.advanced_filters.copy()
            all_filters['search_term'] = self.ui.search_input.text()
            all_filters['date_from'] = self.ui.date_from_input.date().toPyDate()
            all_filters['date_to'] = self.ui.date_to_input.date().toPyDate()


            all_filters['show_only_deleted'] = self.ui.show_only_deleted_checkbox.isChecked()

            records = self.ops.get_records_with_details(filters=all_filters)
            for record_object in records:
                self._add_record_to_table(record_object)

        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not load records:\n\n{e}")
        finally:
            self.is_loading = False
            self.ui.table_widget.setSortingEnabled(True)
            QApplication.restoreOverrideCursor()

    # def _add_record_to_table(self, record):
    #     row_pos = self.ui.table_widget.rowCount()
    #     self.ui.table_widget.insertRow(row_pos)
    #
    #     total_output = sum(out.qty_output for out in record.extruder_outputs if out.qty_output)
    #     start_times = [out.datetime_start for out in record.extruder_outputs if out.datetime_start]
    #     end_times = [out.datetime_end for out in record.extruder_outputs if out.datetime_end]
    #     min_start_time = min(start_times) if start_times else None
    #     max_end_time = max(end_times) if end_times else None
    #
    #     cell_data = {
    #         0: (str(record.id), record.id),
    #         1: (record.created_at.strftime("%Y-%m-%d %H:%M") if record.created_at else "N/A",
    #             record.created_at.timestamp() if record.created_at else 0),
    #         2: (getattr(record.machine, 'name', 'N/A'), None),
    #         3: (record.product_code, None),
    #         4: (record.lot_number, None),
    #         5: (min_start_time.strftime("%Y-%m-%d %H:%M") if min_start_time else "N/A",
    #             min_start_time.timestamp() if min_start_time else 0),
    #         6: (max_end_time.strftime("%Y-%m-%d %H:%M") if max_end_time else "N/A",
    #             max_end_time.timestamp() if max_end_time else 0),
    #         7: ("0.00", 0.0),  # Output/hr needs more complex calculation
    #         8: (f"{record.target_output_per_hour or 0:.2f}", float(record.target_output_per_hour or 0)),
    #         9: (f"{total_output or 0:.2f}", float(total_output or 0)),
    #         10: (", ".join([p.product_code for p in record.purging_headers if p.product_code]) or "N/A", None),
    #         11: ("00:00", 0),  # Total purging time needs calculation
    #         12: (", ".join([f"{p.employee.first_name} {p.employee.last_name}" for p in record.extruder_personnels if
    #                         p.employee]) or "N/A", None),
    #     }
    #
    #     for col, (text, numeric_val) in cell_data.items():
    #         if numeric_val is not None:
    #             item = NumericTableWidgetItem(text)
    #             item.setData(Qt.ItemDataRole.UserRole, numeric_val)
    #         else:
    #             item = QTableWidgetItem(text)
    #
    #         if record.is_deleted:
    #             item.setBackground(QBrush(QColor("#e0e0e0")))
    #             item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)
    #
    #         self.ui.table_widget.setItem(row_pos, col, item)

    # --- Other methods are unchanged ---

    def _add_record_to_table(self, record):
        row_pos = self.ui.table_widget.rowCount()
        self.ui.table_widget.insertRow(row_pos)

        # --- FIX: Calculation Logic Added ---

        # Calculate Total Output and Production Time
        total_output = sum(out.qty_output for out in record.extruder_outputs if out.qty_output)
        total_production_seconds = sum(
            (out.datetime_end - out.datetime_start).total_seconds() for out in record.extruder_outputs
            if out.datetime_start and out.datetime_end and out.datetime_end > out.datetime_start
        )
        total_production_hours = total_production_seconds / 3600.0
        output_per_hour = (total_output / decimal.Decimal(
            total_production_hours)) if total_production_hours > 0 else decimal.Decimal(0)

        # Calculate Total Purging Time
        total_purging_seconds = 0
        for p in record.purging_headers:
            if p.time_start and p.time_end:
                dummy_date = datetime.now().date()
                start_dt = datetime.combine(dummy_date, p.time_start)
                end_dt = datetime.combine(dummy_date, p.time_end)
                if end_dt < start_dt:
                    end_dt += timedelta(days=1)
                total_purging_seconds += (end_dt - start_dt).total_seconds()

        purging_hours, rem = divmod(total_purging_seconds, 3600)
        purging_minutes, _ = divmod(rem, 60)
        purging_time_str = f"{int(purging_hours):02}:{int(purging_minutes):02}"

        # --- Other Preparations (unchanged) ---
        start_times = [out.datetime_start for out in record.extruder_outputs if out.datetime_start]
        end_times = [out.datetime_end for out in record.extruder_outputs if out.datetime_end]
        min_start_time = min(start_times) if start_times else None
        max_end_time = max(end_times) if end_times else None

        # --- MODIFIED: Use calculated values ---
        cell_data = {
            0: (str(record.id), record.id),
            1: (record.created_at.strftime("%Y-%m-%d %H:%M") if record.created_at else "N/A",
                record.created_at.timestamp() if record.created_at else 0),
            2: (getattr(record.machine, 'name', 'N/A'), None),
            3: (record.product_code, None),
            4: (record.lot_number, None),
            5: (min_start_time.strftime("%Y-%m-%d %H:%M") if min_start_time else "N/A",
                min_start_time.timestamp() if min_start_time else 0),
            6: (max_end_time.strftime("%Y-%m-%d %H:%M") if max_end_time else "N/A",
                max_end_time.timestamp() if max_end_time else 0),
            7: (f"{output_per_hour:.2f}", float(output_per_hour)),
            8: (f"{record.target_output_per_hour or 0:.2f}", float(record.target_output_per_hour or 0)),
            9: (f"{total_output or 0:.2f}", float(total_output or 0)),
            10: (", ".join([p.product_code for p in record.purging_headers if p.product_code]) or "N/A", None),
            11: (purging_time_str, total_purging_seconds),
            12: (", ".join([f"{p.employee.first_name} {p.employee.last_name}" for p in record.extruder_personnels if
                            p.employee]) or "N/A", None),
        }

        is_deleted_view = self.ui.show_only_deleted_checkbox.isChecked()


        for col, (text, numeric_val) in cell_data.items():
            if numeric_val is not None:
                item = NumericTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, numeric_val)
            else:
                item = QTableWidgetItem(text)

            # if record.is_deleted:
            #     item.setBackground(QBrush(QColor("#e0e0e0")))
            #     item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

            if is_deleted_view:
                item.setBackground(QBrush(self.is_deleted_color))
                # Prevent interaction since these are archived records
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsSelectable)

            self.ui.table_widget.setItem(row_pos, col, item)


    # def _get_selected_record_info(self):
    #     selected_rows = self.ui.table_widget.selectionModel().selectedRows()
    #     if not selected_rows: return None, False
    #     row = selected_rows[0].row()
    #     record_id = int(self.ui.table_widget.item(row, 0).text())
    #     is_deleted = self.ui.table_widget.item(row, 0).background().color() == self.is_deleted_color
    #     return record_id, is_deleted


    def _get_selected_record_info(self):
        # --- MODIFIED: Simplified to rely on the checkbox state ---
        selected_rows = self.ui.table_widget.selectionModel().selectedRows()
        if not selected_rows: return None, False
        row = selected_rows[0].row()
        record_id = int(self.ui.table_widget.item(row, 0).text())
        is_deleted = self.ui.show_only_deleted_checkbox.isChecked()
        return record_id, is_deleted

    # def _show_context_menu(self, position: QPoint):
    #     index = self.ui.table_widget.indexAt(position)
    #     if not index.isValid(): return
    #     self.ui.table_widget.selectRow(index.row())
    #     record_id, is_deleted = self._get_selected_record_info()
    #     if record_id is None: return
    #     context_menu = QMenu(self)
    #     view_action = QAction("View Record", self)
    #     edit_action = QAction("Edit Record", self)
    #     delete_action = QAction("Delete Record", self)
    #     restore_action = QAction("Restore Record", self)
    #     view_action.triggered.connect(self._view_record)
    #     edit_action.triggered.connect(self._edit_record)
    #     delete_action.triggered.connect(self._delete_record)
    #     restore_action.triggered.connect(self._restore_record)
    #     if not is_deleted:
    #         context_menu.addAction(view_action)
    #         context_menu.addAction(edit_action)
    #         context_menu.addSeparator()
    #         context_menu.addAction(delete_action)
    #     else:
    #         context_menu.addAction(restore_action)
    #     context_menu.exec(self.ui.table_widget.mapToGlobal(position))

    def _show_context_menu(self, position: QPoint):
        # --- MODIFIED: Dynamically build the context menu ---
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None: return

        context_menu = QMenu(self)

        if is_deleted:
            # If we are viewing deleted records, only show the Restore action
            restore_action = QAction("Restore Record", self)
            restore_action.triggered.connect(self._restore_record)
            context_menu.addAction(restore_action)
        else:
            # If we are viewing active records, show the standard actions
            view_action = QAction("View Record", self)
            edit_action = QAction("Edit Record", self)
            delete_action = QAction("Delete Record", self)

            view_action.triggered.connect(self._view_record)
            edit_action.triggered.connect(self._edit_record)
            delete_action.triggered.connect(self._delete_record)

            context_menu.addAction(view_action)
            context_menu.addAction(edit_action)
            context_menu.addSeparator()
            context_menu.addAction(delete_action)

        context_menu.exec(self.ui.table_widget.mapToGlobal(position))

    def _delete_record(self):
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None or is_deleted: return
        reply = QMessageBox.question(self, 'Confirm Deletion', f"Delete record ID: {record_id}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.ops.soft_delete_record(record_id):
                self.refresh_data();
                self.data_changed.emit()
            else:
                QMessageBox.critical(self, "Error", "Failed to delete the record.")

    # def _restore_record(self):
    #     record_id, is_deleted = self._get_selected_record_info()
    #     if record_id is None or not is_deleted: return
    #     if self.ops.restore_record(record_id):
    #         self.refresh_data();
    #         self.data_changed.emit()
    #     else:
    #         QMessageBox.critical(self, "Error", "Failed to restore the record.")

    def _restore_record(self):
        record_id, is_deleted = self._get_selected_record_info()
        # A check to ensure we only restore from the deleted view
        if record_id is None or not is_deleted: return

        reply = QMessageBox.question(self, 'Confirm Restore',
                                     f"Are you sure you want to restore record ID: {record_id}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)

        if reply == QMessageBox.StandardButton.Yes:
            if self.ops.restore_record(record_id):
                QMessageBox.information(self, "Success", f"Record {record_id} has been restored.")
                self.refresh_data()
                self.data_changed.emit()
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

    def _edit_record(self):
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None or is_deleted: return
        full_data = self.ops.get_full_record_by_id(record_id)
        if full_data:
            edit_dialog = ExtruderEditDialog(self.ops.Session, full_data, self)
            if edit_dialog.exec() == QDialog.DialogCode.Accepted:
                self.refresh_data()
        else:
            QMessageBox.warning(self, "Not Found", "Could not retrieve full record details for editing.")