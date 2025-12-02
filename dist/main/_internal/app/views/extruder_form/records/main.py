import decimal
import os
import traceback
from datetime import datetime, timedelta

import openpyxl
from PyQt6.QtWidgets import QWidget, QTableWidgetItem, QMessageBox, QApplication, QMenu, QDialog, QProgressDialog, \
    QFileDialog
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDate, QPoint, QThread
from PyQt6.QtGui import QColor, QBrush, QAction
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.copier import WorksheetCopy
from sqlalchemy.orm import Session
from typing import Type, List

from .bulk_export_dialog import BulkExportDialog
from .edit_dialog import ExtruderEditDialog
from .exporter import ExcelReportExporter
from .ui_setup import Ui_ExtruderRecordsList
from .ops import ExtruderRecordsOperations
from .view_dialog import ExtruderRecordViewDialog
from .filter_dialog import FilterDialog
from ..entry_form.widgets.error_dialog import ErrorDialog


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


class BulkExportWorker(QThread):
    progress = pyqtSignal(int, str)
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, record_ids: List[int], option: int, output_path: str, ops: ExtruderRecordsOperations,
                 parent=None):
        super().__init__(parent)
        self.record_ids = record_ids
        self.option = option
        self.output_path = output_path
        self.ops = ops
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            exporter = ExcelReportExporter(self.ops)
            total_records = len(self.record_ids)

            if self.option == BulkExportDialog.SEPARATE_FILES:
                self._export_to_separate_files(exporter, total_records)
            elif self.option == BulkExportDialog.SEPARATE_SHEETS:
                self._export_to_separate_sheets(exporter, total_records)
            elif self.option == BulkExportDialog.SINGLE_SHEET:
                self._export_to_single_sheet(exporter, total_records)

            if self._is_running:
                self.finished.emit("Bulk export completed successfully!")
        except Exception:
            self.error.emit(f"An unexpected error occurred during bulk export:\n\n{traceback.format_exc()}")

    def _export_to_separate_files(self, exporter, total):
        os.makedirs(self.output_path, exist_ok=True)
        for i, record_id in enumerate(self.record_ids):
            if not self._is_running: return
            record = self.ops.get_full_record_by_id(record_id)
            if not record: continue

            self.progress.emit(int((i / total) * 100), f"Exporting {record.ref_no} ({i + 1}/{total})...")
            filename = f"Report_{record.ref_no}_{record.lot_number}.xlsx".replace('/', '_')  # Sanitize filename
            file_path = os.path.join(self.output_path, filename)
            exporter.generate_single_report(record, file_path)
        self.progress.emit(100, "Finalizing...")

    # # --- THIS IS THE CORRECTED METHOD ---
    # def _export_to_separate_sheets(self, exporter, total):
    #     # 1. Load the template workbook. This will become our output file.
    #     output_wb = openpyxl.load_workbook(ExcelReportExporter.TEMPLATE_PATH)
    #
    #     # 2. Get the first sheet, which is our template.
    #     template_sheet = output_wb.active
    #
    #     is_first_record = True
    #     for i, record_id in enumerate(self.record_ids):
    #         if not self._is_running: return
    #         record = self.ops.get_full_record_by_id(record_id)
    #         if not record: continue
    #
    #         self.progress.emit(int((i / total) * 100), f"Processing {record.ref_no} ({i + 1}/{total})...")
    #
    #         current_sheet = None
    #         if is_first_record:
    #             # For the first record, use the sheet that's already in the workbook.
    #             current_sheet = template_sheet
    #             is_first_record = False
    #         else:
    #             # For all other records, create a copy of the original template sheet.
    #             current_sheet = output_wb.copy_worksheet(template_sheet)
    #
    #         # Set the title for the current sheet
    #         sheet_title = f"Ref {record.ref_no}".replace('/', '_').replace('\\', '_')[:31]
    #         current_sheet.title = sheet_title
    #
    #         # Populate the data onto this sheet
    #
    #         exporter.populate_sheet(current_sheet, record, overwrite_formulas=False)
    #
    #     self.progress.emit(100, "Saving file...")
    #     output_wb.save(self.output_path)
    #
    # # --- END CORRECTION ---

    # --- THIS IS THE CORRECTED METHOD ---
    def _export_to_separate_sheets(self, exporter, total):
        # 1. Load the pristine template once to use as a read-only source.
        template_wb = openpyxl.load_workbook(ExcelReportExporter.TEMPLATE_PATH)
        template_sheet = template_wb.active

        # 2. Create the final output workbook from scratch.
        output_wb = openpyxl.Workbook()
        output_wb.remove(output_wb.active) # remove default sheet

        for i, record_id in enumerate(self.record_ids):
            if not self._is_running: return
            record = self.ops.get_full_record_by_id(record_id)
            if not record: continue

            self.progress.emit(int((i / total) * 100), f"Processing {record.ref_no} ({i + 1}/{total})...")

            # 3. Create a new, blank sheet in the output workbook for this record.
            sheet_title = f"Ref {record.ref_no}".replace('/', '_').replace('\\', '_')[:31]
            new_sheet = output_wb.create_sheet(title=sheet_title)

            # 4. Manually build a perfect copy of the template's structure onto the new sheet.
            # This ensures no data is ever carried over from a previous record.
            for col_letter in [get_column_letter(c) for c in range(1, template_sheet.max_column + 1)]:
                new_sheet.column_dimensions[col_letter].width = template_sheet.column_dimensions[col_letter].width
            for row_idx, dim in template_sheet.row_dimensions.items():
                if dim.height is not None:
                    new_sheet.row_dimensions[row_idx].height = dim.height

            for row in template_sheet.iter_rows():
                for cell in row:
                    new_cell = new_sheet.cell(row=cell.row, column=cell.column)
                    new_cell.value = cell.value # Copy static labels
                    if cell.has_style:
                        new_cell.font = cell.font.copy()
                        new_cell.border = cell.border.copy()
                        new_cell.fill = cell.fill.copy()
                        new_cell.number_format = cell.number_format
                        new_cell.protection = cell.protection.copy()
                        new_cell.alignment = cell.alignment.copy()

            for mc_range in template_sheet.merged_cells.ranges:
                new_sheet.merge_cells(str(mc_range))

            # 5. Now that we have a guaranteed clean sheet, populate it.
            # We keep the template's formulas, so `overwrite_formulas` is False.
            exporter.populate_sheet(new_sheet, record, overwrite_formulas=False)

        self.progress.emit(100, "Saving file...")
        output_wb.save(self.output_path)
    # --- END CORRECTION ---

    def _export_to_single_sheet(self, exporter, total):
        output_wb = openpyxl.Workbook()
        output_sheet = output_wb.active
        output_sheet.title = "Bulk Report"

        template_wb = openpyxl.load_workbook(ExcelReportExporter.TEMPLATE_PATH)
        template_sheet = template_wb.active
        for col_letter in [get_column_letter(i) for i in range(1, template_sheet.max_column + 1)]:
            output_sheet.column_dimensions[col_letter].width = template_sheet.column_dimensions[col_letter].width

        template_row_heights = {i: dim.height for i, dim in template_sheet.row_dimensions.items()}
        default_row_height = template_sheet.sheet_format.defaultRowHeight

        for i, record_id in enumerate(self.record_ids):
            if not self._is_running: return
            record = self.ops.get_full_record_by_id(record_id)
            if not record: continue

            self.progress.emit(int((i / total) * 100), f"Processing {record.ref_no} ({i + 1}/{total})...")

            temp_wb = openpyxl.load_workbook(ExcelReportExporter.TEMPLATE_PATH)
            temp_sheet = temp_wb.active

            # --- THIS IS THE FIX ---
            # For this option, we MUST overwrite formulas with static values.
            exporter.populate_sheet(temp_sheet, record, row_offset=0, overwrite_formulas=True)
            # --- END FIX ---

            row_offset = i * ExcelReportExporter.REPORT_TOTAL_ROWS
            for row_idx in range(1, ExcelReportExporter.REPORT_TOTAL_ROWS + 2):
                height = template_row_heights.get(row_idx, default_row_height)
                if height is not None:
                    output_sheet.row_dimensions[row_idx + row_offset].height = height

            for row in temp_sheet.iter_rows():
                for cell in row:
                    new_cell = output_sheet.cell(row=cell.row + row_offset, column=cell.column)
                    new_cell.value = cell.value
                    if cell.has_style:
                        new_cell.font = cell.font.copy()
                        new_cell.border = cell.border.copy()
                        new_cell.fill = cell.fill.copy()
                        new_cell.number_format = cell.number_format
                        new_cell.protection = cell.protection.copy()
                        new_cell.alignment = cell.alignment.copy()

            for mc_range in temp_sheet.merged_cells.ranges:
                output_sheet.merge_cells(start_row=mc_range.min_row + row_offset, start_column=mc_range.min_col,
                                         end_row=mc_range.max_row + row_offset, end_column=mc_range.max_col)

        self.progress.emit(100, "Saving file...")
        output_wb.save(self.output_path)


# --- CORRECTED WORKER THREAD FOR EXPORTING ---
class ExportWorker(QThread):
    """ Runs the slow Excel export process in a background thread. """
    success = pyqtSignal(str)
    error = pyqtSignal(str)

    # --- FIX 1: The constructor now accepts the operations controller ---
    def __init__(self, record_object, ops_controller, output_path, parent=None):
        super().__init__(parent)
        self.record = record_object
        self.controller = ops_controller  # Store the controller
        self.output_path = output_path

    def run(self):
        try:
            # --- FIX 2: The controller is now a valid attribute of the worker ---
            exporter = ExcelReportExporter(self.record, self.controller)
            exporter.generate_report(self.output_path)
            self.success.emit(self.output_path)
        except Exception as e:
            # Send the full traceback for detailed error reporting
            self.error.emit(f"An error occurred during export:\n\n{traceback.format_exc()}")


class ExtruderRecordsView(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, session_factory: Type[Session], parent=None):
        super().__init__(parent)
        self.ui = Ui_ExtruderRecordsList()
        self.ui.setupUi(self)
        self.ops = ExtruderRecordsOperations(session_factory)

        # --- This will hold a reference to the worker to prevent it from being deleted ---
        self.export_worker = None
        self.bulk_export_worker = None

        self.filter_dialog = FilterDialog(session_factory, self)
        self.advanced_filters = {}
        self.is_loading = False
        self.is_deleted_color = QColor("#e0e0e0")


        self._setup_connections()
        self.load_initial_data()
        self._update_ui_for_view_mode()

        self.ui.table_widget.sortByColumn(1, Qt.SortOrder.DescendingOrder)

        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f: self.setStyleSheet(f.read())

    def _setup_connections(self):
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.refresh_data)
        self.ui.search_input.textChanged.connect(lambda: self.search_timer.start(500))
        self.ui.date_from_input.dateChanged.connect(self.refresh_data)
        self.ui.date_to_input.dateChanged.connect(self.refresh_data)

        self.ui.advanced_filter_button.clicked.connect(self._open_filter_dialog)
        self.ui.clear_filters_button.clicked.connect(self._clear_all_filters)
        self.ui.restore_selected_button.clicked.connect(self._restore_selected_records)
        self.ui.show_only_deleted_checkbox.stateChanged.connect(self.refresh_data)

        self.ui.table_widget.doubleClicked.connect(self._view_record)
        self.ui.table_widget.customContextMenuRequested.connect(self._show_context_menu)

    # --- THIS IS THE CORRECTED SINGLE-EXPORT METHOD ---
    def _export_record_to_excel(self):
        # Check if the bulk export worker is running
        if self.bulk_export_worker:
            QMessageBox.warning(self, "Export in Progress", "A bulk export is already running. Please wait.")
            return

        record_id, _ = self._get_selected_record_info()
        if record_id is None: return

        try:
            record = self.ops.get_full_record_by_id(record_id)
            if not record:
                QMessageBox.warning(self, "Not Found", "Could not retrieve the full record details for export.")
                return
        except Exception:
            ErrorDialog("Database Error", "Failed to fetch record data.", details=traceback.format_exc(),
                        parent=self).exec()
            return

        default_filename = f"Extruder_Report_{record.ref_no}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel Report", default_filename, "Excel Files (*.xlsx)")

        if not file_path:
            return

        # Use a wait cursor for this fast, single-file operation
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # Instantiate the refactored exporter
            exporter = ExcelReportExporter(self.ops)
            # Call the specific method for creating a single file
            exporter.generate_single_report(record, file_path)

            reply = QMessageBox.information(self, "Export Successful",
                                            f"Report successfully saved.\n\nDo you want to open the file?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                os.startfile(file_path)
        except Exception:
            ErrorDialog("Export Error", "Failed to save the Excel file.", details=traceback.format_exc(),
                        parent=self).exec()
        finally:
            QApplication.restoreOverrideCursor()  # Always restore the cursor

    def _on_export_success(self, filepath: str):
        reply = QMessageBox.information(self, "Export Successful",
                                      f"Report successfully saved.\n\nDo you want to open the file?",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            os.startfile(filepath)

    def _on_export_error(self, error_message: str):
        error_dialog = ErrorDialog("Export Error", "An unexpected error occurred during the export process.",
                                   details=error_message, parent=self)
        error_dialog.exec()

    # --- FIX 5: Robust cleanup handler to prevent the RuntimeError ---
    def _on_export_finished(self):
        """
        Cleans up the worker after it has finished running (on success, error, or cancel).
        This prevents the RuntimeError on subsequent clicks.
        """
        if self.export_worker:
            self.export_worker.deleteLater()
            # Setting the reference to None is the most important step.
            self.export_worker = None



    # (The rest of your file remains unchanged)
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
        self._update_ui_for_view_mode()

    def load_initial_data(self):
        self._load_records()

    def _update_ui_for_view_mode(self):
        is_deleted_view = self.ui.show_only_deleted_checkbox.isChecked()
        self.ui.restore_selected_button.setVisible(is_deleted_view)

    def _restore_selected_records(self):
        selected_rows = set(item.row() for item in self.ui.table_widget.selectedItems())
        if not selected_rows:
            QMessageBox.information(self, "No Selection", "Please select one or more records to restore.")
            return

        ids_to_restore = [int(self.ui.table_widget.item(row, 0).text()) for row in selected_rows]
        count = len(ids_to_restore)
        reply = QMessageBox.question(self, 'Confirm Restore',
                                     f"Are you sure you want to restore {count} selected record(s)?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            success = self.ops.restore_multiple_records(ids_to_restore)
            if success:
                QMessageBox.information(self, "Success", f"{count} record(s) have been restored.")
                self.refresh_data()
                self.data_changed.emit()
            else:
                QMessageBox.critical(self, "Error", "Failed to restore the selected records.")

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

            if search_term := self.ui.search_input.text():
                 all_filters['ref_no_search'] = search_term

            records = self.ops.get_records_with_details(filters=all_filters)
            for record_object in records:
                self._add_record_to_table(record_object)
        except Exception as e:
            QMessageBox.critical(self, "Database Error", f"Could not load records:\n\n{e}")
        finally:
            self.is_loading = False
            self.ui.table_widget.setSortingEnabled(True)
            QApplication.restoreOverrideCursor()

    def _add_record_to_table(self, record):
        row_pos = self.ui.table_widget.rowCount()
        self.ui.table_widget.insertRow(row_pos)
        total_output = sum(out.qty_output for out in record.extruder_outputs if out.qty_output)
        total_production_seconds = sum(
            (out.datetime_end - out.datetime_start).total_seconds() for out in record.extruder_outputs
            if out.datetime_start and out.datetime_end and out.datetime_end > out.datetime_start
        )
        total_production_hours = total_production_seconds / 3600.0
        output_per_hour = (total_output / decimal.Decimal(
            total_production_hours)) if total_production_hours > 0 else decimal.Decimal(0)
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
        start_times = [out.datetime_start for out in record.extruder_outputs if out.datetime_start]
        end_times = [out.datetime_end for out in record.extruder_outputs if out.datetime_end]
        min_start_time = min(start_times) if start_times else None
        max_end_time = max(end_times) if end_times else None
        # cell_data = {
        #     0: (str(record.id), record.id),
        #     1: (record.created_at.strftime("%Y-%m-%d %H:%M") if record.created_at else "N/A",
        #         record.created_at.timestamp() if record.created_at else 0),
        #     2: (getattr(record.machine, 'name', 'N/A'), None),
        #     3: (record.product_code, None),
        #     4: (record.lot_number, None),
        #     5: (min_start_time.strftime("%Y-%m-%d %H:%M") if min_start_time else "N/A",
        #         min_start_time.timestamp() if min_start_time else 0),
        #     6: (max_end_time.strftime("%Y-%m-%d %H:%M") if max_end_time else "N/A",
        #         max_end_time.timestamp() if max_end_time else 0),
        #     7: (f"{output_per_hour:.2f}", float(output_per_hour)),
        #     8: (f"{record.target_output_per_hour or 0:.2f}", float(record.target_output_per_hour or 0)),
        #     9: (f"{total_output or 0:.2f}", float(total_output or 0)),
        #     10: (", ".join([p.product_code for p in record.purging_headers if p.product_code]) or "N/A", None),
        #     11: (purging_time_str, total_purging_seconds),
        #     12: (", ".join([f"{p.employee.first_name} {p.employee.last_name}" for p in record.extruder_personnels if
        #                     p.employee]) or "N/A", None),
        # }

        cell_data = {
            0: (str(record.id), record.id),
            1: (record.created_at.strftime("%Y-%m-%d %H:%M") if record.created_at else "N/A", record.created_at.timestamp() if record.created_at else 0),
            2: (str(record.ref_no or ''), record.ref_no), # New Ref No column
            3: (getattr(record.machine, 'name', 'N/A'), None),
            4: (record.product_code, None),
            5: (record.lot_number, None),
            6: (min_start_time.strftime("%Y-%m-%d %H:%M") if min_start_time else "N/A", min_start_time.timestamp() if min_start_time else 0),
            7: (max_end_time.strftime("%Y-%m-%d %H:%M") if max_end_time else "N/A", max_end_time.timestamp() if max_end_time else 0),
            8: (f"{output_per_hour:.2f}", float(output_per_hour)),
            9: (f"{record.target_output_per_hour or 0:.2f}", float(record.target_output_per_hour or 0)),
            10: (f"{total_output or 0:.2f}", float(total_output or 0)),
            11: (", ".join([p.product_code for p in record.purging_headers if p.product_code]) or "N/A", None),
            12: (purging_time_str, total_purging_seconds),
            13: (", ".join([f"{p.employee.first_name} {p.employee.last_name}" for p in record.extruder_personnels if p.employee]) or "N/A", None),
        }
        # --- END FIX ---


        is_deleted_view = self.ui.show_only_deleted_checkbox.isChecked()
        for col, (text, numeric_val) in cell_data.items():
            if numeric_val is not None:
                item = NumericTableWidgetItem(text)
                item.setData(Qt.ItemDataRole.UserRole, numeric_val)
            else:
                item = QTableWidgetItem(text)
            if is_deleted_view:
                item.setBackground(QBrush(self.is_deleted_color))
            self.ui.table_widget.setItem(row_pos, col, item)

    def _get_selected_record_info(self):
        selected_rows = self.ui.table_widget.selectionModel().selectedRows()
        if not selected_rows: return None, False
        row = selected_rows[0].row()
        record_id = int(self.ui.table_widget.item(row, 0).text())
        is_deleted = self.ui.show_only_deleted_checkbox.isChecked()
        return record_id, is_deleted

    def _show_context_menu(self, position: QPoint):
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None: return

        context_menu = QMenu(self)
        if is_deleted:
            # Menu for deleted records
            view_action = QAction("View Record", self)
            restore_action = QAction("Restore Record", self)
            view_action.triggered.connect(self._view_record)
            restore_action.triggered.connect(self._restore_record)
            context_menu.addAction(view_action)
            context_menu.addAction(restore_action)
        else:
            # Menu for active records
            view_action = QAction("View Record", self)
            edit_action = QAction("Edit Record", self)
            delete_action = QAction("Delete Record", self)
            export_action = QAction("Export to Excel", self)

            view_action.triggered.connect(self._view_record)
            edit_action.triggered.connect(self._edit_record)
            delete_action.triggered.connect(self._delete_record)
            export_action.triggered.connect(self._export_record_to_excel)

            context_menu.addAction(view_action)
            context_menu.addAction(edit_action)
            context_menu.addSeparator()
            context_menu.addAction(export_action)

            # --- NEW: Add Bulk Export option ---
            record_count = self.ui.table_widget.rowCount()
            if record_count > 1:
                bulk_export_action = QAction(f"Bulk Export ({record_count} Records)...", self)
                bulk_export_action.triggered.connect(self._start_bulk_export)
                context_menu.addAction(bulk_export_action)

            context_menu.addSeparator()
            context_menu.addAction(delete_action)

        context_menu.exec(self.ui.table_widget.mapToGlobal(position))

    def _start_bulk_export(self):
        if self.bulk_export_worker:
            QMessageBox.warning(self, "Export in Progress", "A bulk export is already running.")
            return

        record_count = self.ui.table_widget.rowCount()
        dialog = BulkExportDialog(record_count, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            option = dialog.get_selected_option()

            # Get list of all record IDs currently displayed in the table
            record_ids = [int(self.ui.table_widget.item(row, 0).text()) for row in range(record_count)]

            output_path = ""
            if option == BulkExportDialog.SEPARATE_FILES:
                output_path = QFileDialog.getExistingDirectory(self, "Select Folder to Save Reports")
            else:
                default_filename = f"Bulk_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
                output_path, _ = QFileDialog.getSaveFileName(self, "Save Bulk Report", default_filename,
                                                             "Excel Files (*.xlsx)")

            if not output_path:
                return

            self.progress = QProgressDialog("Starting bulk export...", "Cancel", 0, 100, self)
            self.progress.setWindowTitle("Bulk Exporting")
            self.progress.setWindowModality(Qt.WindowModality.WindowModal)

            self.bulk_export_worker = BulkExportWorker(record_ids, option, output_path, self.ops)
            self.bulk_export_worker.progress.connect(self._update_bulk_progress)
            self.bulk_export_worker.finished.connect(self._on_bulk_export_finished)
            self.bulk_export_worker.error.connect(self._on_bulk_export_error)

            self.progress.canceled.connect(self.bulk_export_worker.stop)
            self.progress.show()

            self.bulk_export_worker.start()

    def _update_bulk_progress(self, value, text):
        self.progress.setValue(value)
        self.progress.setLabelText(text)

    def _on_bulk_export_finished(self, message):
        self.progress.setValue(100)
        QMessageBox.information(self, "Success", message)
        self.bulk_export_worker = None

    def _on_bulk_export_error(self, error_message):
        self.progress.close()
        ErrorDialog("Bulk Export Error", "An error occurred during the bulk export.", details=error_message,
                    parent=self).exec()
        self.bulk_export_worker = None



    def _delete_record(self):
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None or is_deleted: return
        reply = QMessageBox.question(self, 'Confirm Deletion', f"Delete record ID: {record_id}?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            if self.ops.soft_delete_record(record_id):
                self.refresh_data()
                self.data_changed.emit()
            else:
                QMessageBox.critical(self, "Error", "Failed to delete the record.")

    def _restore_record(self):
        record_id, is_deleted = self._get_selected_record_info()
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
        if record_id is None: return
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
                self.data_changed.emit()  # Ensure this signal is emitted
        else:
            QMessageBox.warning(self, "Not Found", "Could not retrieve full record details for editing.")