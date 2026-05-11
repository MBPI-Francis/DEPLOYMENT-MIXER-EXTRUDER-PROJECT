# app/views/extruder_form/records/main.py

import decimal
import math
import os
import traceback
from datetime import datetime, timedelta
from typing import Type, List

import openpyxl
import pandas as pd
from openpyxl.utils import get_column_letter

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDate, QPoint, QThread
from PyQt6.QtGui import QAction, QColor, QBrush, QShowEvent, QIntValidator
from PyQt6.QtWidgets import (QWidget, QTableWidgetItem, QMessageBox, QApplication, QMenu, QDialog, QProgressDialog,
                             QFileDialog, QGroupBox, QGridLayout, QLabel,
                             QVBoxLayout, QPushButton, QHBoxLayout)
from sqlalchemy.orm import Session

import qtawesome as qta
from app.widgets.smart_combo_box import SmartComboBox
from .bulk_export_dialog import BulkExportDialog
from .edit_dialog import ExtruderEditDialog
from .exporter import ExcelReportExporter, ExtruderListExporter
from .filter_dialog import FilterDialog
from .ops import ExtruderRecordsOperations
from .ui_setup import Ui_ExtruderRecordsList
from .view_dialog import ExtruderRecordViewDialog
from ..entry_form.widgets.error_dialog import ErrorDialog
from ...mixer_form.records.main import LoadingDialog


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

    def __init__(self, records: List, option: int, output_path: str, ops: ExtruderRecordsOperations, parent=None):
        super().__init__(parent)
        self.records = records
        self.option = option
        self.output_path = output_path
        self.ops = ops
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            exporter = ExcelReportExporter(self.ops)
            total_records = len(self.records)
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
        for i, record in enumerate(self.records):
            if not self._is_running: return
            self.progress.emit(int((i / total) * 100), f"Exporting {record.ref_no} ({i + 1}/{total})...")
            filename = f"Report_{record.ref_no}_{record.lot_number}.xlsx".replace('/', '_').replace('\\', '_')
            file_path = os.path.join(self.output_path, filename)
            exporter.generate_single_report(record, file_path)
        self.progress.emit(100, "Finalizing...")

    def _export_to_separate_sheets(self, exporter, total):
        """
        Modified Logic:
        1. Group records by Machine Name.
        2. Create one sheet per Machine.
        3. Stack records for that machine vertically in that sheet.
        """
        # 1. Group Records by Machine
        records_by_machine = {}
        for record in self.records:
            # Handle cases where machine might be None
            machine_name = getattr(record.machine, 'name', 'Unknown Machine')
            if machine_name not in records_by_machine:
                records_by_machine[machine_name] = []
            records_by_machine[machine_name].append(record)

        # 2. Prepare Output Workbook
        output_wb = openpyxl.Workbook()
        output_wb.remove(output_wb.active)  # Remove default sheet

        # Prepare Template Reference (for column widths)
        template_wb = openpyxl.load_workbook(ExcelReportExporter.TEMPLATE_PATH)
        template_sheet = template_wb.active

        processed_count = 0

        # Sort machine names so tabs are ordered
        for machine_name in sorted(records_by_machine.keys()):
            if not self._is_running: return

            # Create Sheet for this Machine
            # Excel sheet names max 31 chars, no invalid chars
            safe_sheet_title = str(machine_name).replace('/', '-').replace('\\', '-').replace(':', '')[:31]
            ws = output_wb.create_sheet(title= "Machine "+safe_sheet_title)

            # Copy Column Widths from Template (Applied once per sheet)
            for col_letter in [get_column_letter(c) for c in range(1, template_sheet.max_column + 1)]:
                ws.column_dimensions[col_letter].width = template_sheet.column_dimensions[col_letter].width

            current_write_row = 0
            machine_records = records_by_machine[machine_name]

            # 3. Stack Records for this Machine
            for record in machine_records:
                if not self._is_running: return
                processed_count += 1
                self.progress.emit(int((processed_count / total) * 100),
                                   f"Processing {machine_name}: {record.ref_no}...")

                # Use a fresh template instance for every record to avoid data contamination
                temp_wb = openpyxl.load_workbook(ExcelReportExporter.TEMPLATE_PATH)
                temp_sheet = temp_wb.active

                # Populate the temp sheet (Handles dynamic rows, formatting, etc.)
                # overwrite_formulas=True is essential for stacking to preserve calculated totals
                exporter.populate_sheet(temp_sheet, record, row_offset=0, overwrite_formulas=True)

                max_row_in_temp = temp_sheet.max_row

                # Copy Row Heights
                for r in range(1, max_row_in_temp + 1):
                    if r in temp_sheet.row_dimensions:
                        dim = temp_sheet.row_dimensions[r]
                        if dim.height is not None:
                            ws.row_dimensions[current_write_row + r].height = dim.height

                # Copy Cells (Values + Styles)
                for row in temp_sheet.iter_rows():
                    for cell in row:
                        new_cell = ws.cell(row=cell.row + current_write_row, column=cell.column)
                        new_cell.value = cell.value
                        if cell.has_style:
                            new_cell.font = cell.font.copy()
                            new_cell.border = cell.border.copy()
                            new_cell.fill = cell.fill.copy()
                            new_cell.number_format = cell.number_format
                            new_cell.protection = cell.protection.copy()
                            new_cell.alignment = cell.alignment.copy()

                # Copy Merged Cells (Shifted by current_write_row)
                for mc_range in temp_sheet.merged_cells.ranges:
                    ws.merge_cells(
                        start_row=mc_range.min_row + current_write_row,
                        start_column=mc_range.min_col,
                        end_row=mc_range.max_row + current_write_row,
                        end_column=mc_range.max_col
                    )

                # Move write pointer down
                current_write_row += max_row_in_temp

        self.progress.emit(100, "Saving file...")
        output_wb.save(self.output_path)

    def _export_to_single_sheet(self, exporter, total):
        output_wb = openpyxl.Workbook()
        output_sheet = output_wb.active
        output_sheet.title = "Bulk Report"
        template_wb = openpyxl.load_workbook(ExcelReportExporter.TEMPLATE_PATH)
        template_sheet = template_wb.active
        for col_letter in [get_column_letter(i) for i in range(1, template_sheet.max_column + 1)]:
            output_sheet.column_dimensions[col_letter].width = template_sheet.column_dimensions[col_letter].width
        current_write_row = 0
        for i, record in enumerate(self.records):
            if not self._is_running: return
            self.progress.emit(int((i / total) * 100), f"Processing {record.ref_no} ({i + 1}/{total})...")
            temp_wb = openpyxl.load_workbook(ExcelReportExporter.TEMPLATE_PATH)
            temp_sheet = temp_wb.active
            exporter.populate_sheet(temp_sheet, record, row_offset=0, overwrite_formulas=True)
            max_row_in_temp = temp_sheet.max_row
            for r in range(1, max_row_in_temp + 1):
                if r in temp_sheet.row_dimensions:
                    dim = temp_sheet.row_dimensions[r]
                    if dim.height is not None:
                        output_sheet.row_dimensions[current_write_row + r].height = dim.height
            for row in temp_sheet.iter_rows():
                for cell in row:
                    new_cell = output_sheet.cell(row=cell.row + current_write_row, column=cell.column)
                    new_cell.value = cell.value
                    if cell.has_style:
                        new_cell.font, new_cell.border, new_cell.fill, new_cell.number_format, new_cell.protection, new_cell.alignment = \
                            cell.font.copy(), cell.border.copy(), cell.fill.copy(), cell.number_format, cell.protection.copy(), cell.alignment.copy()
            for mc_range in temp_sheet.merged_cells.ranges:
                output_sheet.merge_cells(
                    start_row=mc_range.min_row + current_write_row,
                    start_column=mc_range.min_col,
                    end_row=mc_range.max_row + current_write_row,
                    end_column=mc_range.max_col
                )
            current_write_row += max_row_in_temp
        self.progress.emit(100, "Saving file...")
        output_wb.save(self.output_path)



# --- NEW: Background Worker for Performance ---
class DataLoaderWorker(QThread):
    finished = pyqtSignal(int, list, dict) # total_count, records, stats
    error = pyqtSignal(str)

    def __init__(self, ops, filters, offset, limit):
        super().__init__()
        self.ops, self.filters, self.offset, self.limit = ops, filters, offset, limit

    def run(self):
        try:
            total = self.ops.get_extruder_record_count(self.filters)
            records = self.ops.get_paginated_records(self.filters, self.offset, self.limit)
            stats = self.ops.get_extruder_summary_aggregates(self.filters)
            self.finished.emit(total, records, stats)
        except Exception:
            self.error.emit(traceback.format_exc())


class ExtruderRecordsView(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, session_factory: Type[Session], parent=None):
        super().__init__(parent)
        self.ui = Ui_ExtruderRecordsList()
        self.ui.setupUi(self)
        self.ops = ExtruderRecordsOperations(session_factory)

        # --- PAGINATION STATE ---
        self.records_per_page = 100
        self.current_page = 1
        self.total_records = 0
        self.data_loader_worker = None
        self.loading_dialog = None
        self.current_filters = {}
        self.advanced_filters = {}
        self.full_data = pd.DataFrame()
        self.has_been_shown = False

        self.bulk_export_worker = None
        self.filter_dialog = FilterDialog(session_factory, self)
        self.advanced_filters = {}
        self.is_loading = False
        self.is_deleted_color = QColor("#e0e0e0")
        self.current_summary_stats = {}
        self.is_initial_load = True

        self._inject_export_button()


        if self.layout() is None: self.setLayout(QVBoxLayout())
        self.layout().addLayout(self.ui.filter_layout)
        self.layout().addWidget(self.ui.table_widget)

        self._setup_ui_enhancements()


        # --- Data is NO LONGER loaded in the constructor ---
        # self.load_initial_data()

        self._update_ui_for_view_mode()
        self.ui.table_widget.sortByColumn(1, Qt.SortOrder.DescendingOrder)
        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f: self.setStyleSheet(f.read())

        self._setup_connections()

    # --- NEW: Override showEvent for lazy loading ---
    def showEvent(self, event: QShowEvent):
        """
        Overrides the show event to load data only the first time the widget is displayed.
        """
        super().showEvent(event)
        if not self.has_been_shown:
            self.refresh_data()
            self.has_been_shown = True

    def _setup_ui_enhancements(self):
        # 1. Search Scope
        self.search_scope_combo = SmartComboBox()
        self.search_scope_combo.addItems(["All Columns", "Product Code", "Lot Number", "Ref No"])
        self.search_scope_combo.setFixedWidth(120)
        self.ui.filter_layout.insertWidget(0, self.search_scope_combo)

        # 2. Search Button
        self.search_btn = QPushButton(icon=qta.icon("fa5s.search"), objectName="ActionButton")
        self.ui.filter_layout.insertWidget(2, self.search_btn)

        # 3. Pagination Widget (Matches Mixer Style)
        self.pagination_container = QWidget()
        self.pagination_container.setObjectName("paginationWidget")
        p_layout = QHBoxLayout(self.pagination_container)

        self.records_per_page_combo = SmartComboBox()
        self.records_per_page_combo.addItems(["50", "100", "250", "500", "1000"])
        self.records_per_page_combo.setCurrentText(str(self.records_per_page))
        self.records_per_page_combo.setEditable(True)
        self.records_per_page_combo.setValidator(QIntValidator(1, 9999))
        self.records_per_page_combo.setFixedWidth(80)

        p_layout.addWidget(QLabel("Records per page:"))
        p_layout.addWidget(self.records_per_page_combo)
        p_layout.addStretch()

        self.first_page_btn = QPushButton("<< First")
        self.prev_page_btn = QPushButton("< Prev")
        self.page_label = QLabel("Page 1 of 1")
        self.next_page_btn = QPushButton("Next >")
        self.last_page_btn = QPushButton("Last >>")

        for btn in [self.first_page_btn, self.prev_page_btn, self.page_label, self.next_page_btn, self.last_page_btn]:
            p_layout.addWidget(btn)

        # 4. Final Layout assembly
        self.summary_box = self._create_summary_box()
        self.layout().addWidget(self.summary_box)
        self.layout().addWidget(self.pagination_container)


    def _inject_export_button(self):
        """Creates the export button and adds it next to the Clear Filters button."""
        self.export_list_button = QPushButton("Export List")
        self.export_list_button.setCursor(Qt.CursorShape.PointingHandCursor)
        # Use built-in icon or custom style
        self.export_list_button.setStyleSheet("""
            QPushButton {
                font-size: 10pt;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 6px;
                border: 1px solid #ced4da;
                background-color: #ffffff;
                color: #495057;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
        """)
        self.export_list_button.setToolTip("Export the currently loaded list and summary to Excel")
        self.export_list_button.clicked.connect(self.export_list_to_excel)

        # Logic to place it right after "Clear All Filters"
        if hasattr(self.ui, 'filter_layout') and hasattr(self.ui, 'clear_filters_button'):
            layout = self.ui.filter_layout
            # Find the position of the Clear Filters button
            index = layout.indexOf(self.ui.clear_filters_button)

            if index != -1:
                # Insert immediately after (index + 1)
                layout.insertWidget(index + 1, self.export_list_button)
            else:
                # Fallback: Just add to the end if specific button not found
                layout.addWidget(self.export_list_button)

    def _create_summary_box(self):
        summary_box = QGroupBox()
        summary_box.setObjectName('SummaryBox')
        layout = QGridLayout(summary_box)
        self.total_output_label = QLabel("0.00")
        self.total_waste_qty_label = QLabel("0.00")
        self.total_proc_duration_label = QLabel("0:00")
        self.total_waste_duration_label = QLabel("0:00")
        self.proc_excel_decimal_label = QLabel("0.00")
        self.waste_excel_decimal_label = QLabel("0.00")
        labels = [self.total_output_label, self.total_waste_qty_label, self.total_proc_duration_label,
                  self.total_waste_duration_label, self.proc_excel_decimal_label, self.waste_excel_decimal_label]
        for label in labels:
            label.setObjectName("SummaryValueLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(QLabel("<b>Total Output Qty:</b>"), 0, 0)
        layout.addWidget(self.total_output_label, 0, 1)
        layout.addWidget(QLabel("<b>Total Processing Duration:</b>"), 0, 2)
        layout.addWidget(self.total_proc_duration_label, 0, 3)
        layout.addWidget(QLabel("<b>Processing Duration (Decimal):</b>"), 0, 4)
        layout.addWidget(self.proc_excel_decimal_label, 0, 5)
        layout.addWidget(QLabel("<b>Total Cleaning Qty:</b>"), 1, 0)
        layout.addWidget(self.total_waste_qty_label, 1, 1)
        layout.addWidget(QLabel("<b>Total Cleaning Duration:</b>"), 1, 2)
        layout.addWidget(self.total_waste_duration_label, 1, 3)
        layout.addWidget(QLabel("<b>Cleaning Duration (Decimal):</b>"), 1, 4)
        layout.addWidget(self.waste_excel_decimal_label, 1, 5)
        layout.setColumnStretch(1, 1);
        layout.setColumnStretch(3, 1);
        layout.setColumnStretch(5, 1)
        return summary_box

    def _calculate_stats(self, df):
        """Helper to calculate summary stats dictionary."""
        if df.empty:
            return {
                "total_output": "0.00", "total_waste": "0.00",
                "proc_duration_str": "0:00", "waste_duration_str": "0:00",
                "proc_decimal": "0.00", "waste_decimal": "0.00"
            }

        total_output = df['Output QTY'].sum()
        total_waste = df['Waste QTY'].sum()

        def sum_durations(col_name):
            total_delta = timedelta()
            for duration_str in df[col_name].dropna().astype(str):
                if ':' in duration_str:
                    try:
                        parts = list(map(int, duration_str.split(':')))
                        if len(parts) >= 2:
                            total_delta += timedelta(hours=parts[0], minutes=parts[1])
                    except:
                        continue
            return total_delta

        total_proc_delta = sum_durations('Processing Duration')
        total_waste_delta = sum_durations('Waste Duration')

        def format_duration(delta):
            total_sec = delta.total_seconds()
            hours = int(total_sec // 3600)
            minutes = int((total_sec % 3600) // 60)
            return hours, minutes, f"{hours}:{minutes:02}"

        proc_h, proc_m, proc_str = format_duration(total_proc_delta)
        waste_h, waste_m, waste_str = format_duration(total_waste_delta)

        # Excel Decimal Formula: (Hours % 24) + (Minutes / 60)
        proc_decimal = proc_h + (proc_m / 60)
        waste_decimal = waste_h + (waste_m / 60)


        return {
            "total_output": f"{total_output:,.2f}",
            "total_waste": f"{total_waste:,.2f}",
            "proc_duration_str": proc_str,
            "waste_duration_str": waste_str,
            "proc_decimal": f"{proc_decimal:.2f}",
            "waste_decimal": f"{waste_decimal:.2f}"
        }

    def _update_summary_box(self):
        stats = self._calculate_stats(self.full_data)
        self.current_summary_stats = stats

        self.total_output_label.setText(stats['total_output'])
        self.total_waste_qty_label.setText(stats['total_waste'])
        self.total_proc_duration_label.setText(stats['proc_duration_str'])
        self.total_waste_duration_label.setText(stats['waste_duration_str'])
        self.proc_excel_decimal_label.setText(stats['proc_decimal'])
        self.waste_excel_decimal_label.setText(stats['waste_decimal'])



    def export_list_to_excel(self):
        # 1. Table check
        if self.ui.table_widget.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "There is no data available to export.")
            return

        default_filename = f"Extruder_Filtered_List_{datetime.now().strftime('%Y%m%d')}.xlsx"
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        default_full_path = os.path.join(desktop_path, default_filename)

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Filtered List", default_full_path,
                                                   "Excel Files (*.xlsx)")
        if not file_path:
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # 2. CAPTURE CURRENT UI FILTERS (Exactly as seen on screen)
            filters = self.advanced_filters.copy()
            filters['search_term'] = self.ui.search_input.text().strip()
            filters['search_field'] = self.search_scope_combo.currentText()
            filters['date_from'] = self.ui.date_from_input.date().toPyDate()
            filters['date_to'] = self.ui.date_to_input.date().toPyDate()
            filters['show_only_deleted'] = self.ui.show_only_deleted_checkbox.isChecked()

            filters['is_completed'] = True

            # 3. FETCH DATA (Filtered Rows)
            export_data = self.ops.get_export_data(filters)

            # 4. FETCH FRESH SUMMARY (Filtered Totals)
            # We don't use 'self.current_summary_stats' because it might be outdated.
            # We call the DB directly for the stats matching these specific filters.
            raw_stats = self.ops.get_extruder_summary_aggregates(filters)

            # Format the DB stats for the Excel Exporter
            def format_for_excel(s_dict):
                def _h_m(total_sec):
                    h, rem = divmod(int(total_sec), 3600)
                    m, _ = divmod(rem, 60)
                    return h, m, f"{h}:{m:02}"

                ph, pm, p_str = _h_m(s_dict["proc_seconds"])
                wh, wm, w_str = _h_m(s_dict["purge_seconds"])

                return {
                    "total_output": f"{s_dict['total_output']:,.2f}",
                    "total_waste": f"{s_dict['total_waste']:,.2f}",
                    "proc_duration_str": p_str,
                    "waste_duration_str": w_str,
                    "proc_decimal": f"{(ph + pm / 60):.2f}",
                    "waste_decimal": f"{(wh + wm / 60):.2f}"
                }

            filtered_summary_stats = format_for_excel(raw_stats)

            # 5. GENERATE EXCEL
            exporter = ExtruderListExporter()
            exporter.export_list(export_data, filtered_summary_stats, file_path)

            QMessageBox.information(self, "Success", "Filtered list exported successfully!")
            os.startfile(file_path)

        except Exception:
            ErrorDialog("Export Error", "Failed to export filtered list.",
                        details=traceback.format_exc(), parent=self).exec()
        finally:
            QApplication.restoreOverrideCursor()

    def _setup_connections(self):
        # Search signals
        self.search_btn.clicked.connect(self.initiate_search)
        self.ui.search_input.returnPressed.connect(self.initiate_search)
        self.search_scope_combo.currentIndexChanged.connect(self.initiate_search)

        # Pagination signals
        self.first_page_btn.clicked.connect(lambda: self._change_page(1))
        self.prev_page_btn.clicked.connect(lambda: self._change_page(self.current_page - 1))
        self.next_page_btn.clicked.connect(lambda: self._change_page(self.current_page + 1))
        self.last_page_btn.clicked.connect(self._go_to_last_page)
        self.records_per_page_combo.activated.connect(self._change_page_size)
        self.records_per_page_combo.lineEdit().returnPressed.connect(self._change_page_size)

        # Action signals
        self.ui.advanced_filter_button.clicked.connect(self._open_filter_dialog)
        self.ui.clear_filters_button.clicked.connect(self._clear_all_filters)
        self.ui.show_only_deleted_checkbox.stateChanged.connect(self.initiate_search)
        self.ui.table_widget.doubleClicked.connect(self._view_record)
        self.ui.table_widget.customContextMenuRequested.connect(self._show_context_menu)

    def initiate_search(self):
        """Reset to Page 1 and fetch data."""
        self.current_page = 1
        self.is_initial_load = False  # Stop using startup dates
        self.refresh_data()

    def _change_page(self, page):
        self.current_page = page
        self.refresh_data()

    def _go_to_last_page(self):
        last = math.ceil(self.total_records / self.records_per_page)
        self._change_page(max(1, last))

    def _change_page_size(self):
        try:
            val = int(self.records_per_page_combo.currentText())
            if val > 0:
                self.records_per_page = val
                self.initiate_search()
        except: self.records_per_page_combo.setCurrentText(str(self.records_per_page))



    def _open_filter_dialog(self):
        self.is_initial_load = False  # Any filtering action means it's no longer initial load
        self.filter_dialog.populate_dropdowns()
        if self.filter_dialog.exec() == QDialog.DialogCode.Accepted:
            self.advanced_filters = self.filter_dialog.get_filters()
            self.refresh_data()

    def _clear_all_filters(self):
        """Resets everything to startup state."""
        self.ui.search_input.clear()
        self.ui.date_from_input.setDate(QDate(2000, 1, 1))
        self.ui.date_to_input.setDate(QDate.currentDate())
        self.advanced_filters.clear()
        self.is_initial_load = True # Re-enable startup date range logic
        self.initiate_search()

    def refresh_data(self):
        """
        Asynchronous data fetcher that strictly enforces Page 1 (1-100)
        and calculates total record count.
        """
        if self.data_loader_worker and self.data_loader_worker.isRunning():
            return

        self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.set_text("Fetching records...")
        self.loading_dialog.show()

        # Prepare Filters
        filters = self.advanced_filters.copy()
        filters['search_term'] = self.ui.search_input.text().strip()
        filters['search_field'] = self.search_scope_combo.currentText()

        # Handle Date Logic for Initial Load
        # If is_initial_load is True, we might want to see ALL history (2000-01-01 to Today)
        # If False, we use whatever the user picked in the DateEdit widgets
        if self.is_initial_load:
            filters['date_from'] = QDate(2000, 1, 1).toPyDate()
            filters['date_to'] = QDate.currentDate().toPyDate()
        else:
            filters['date_from'] = self.ui.date_from_input.date().toPyDate()
            filters['date_to'] = self.ui.date_to_input.date().toPyDate()

        filters['show_only_deleted'] = self.ui.show_only_deleted_checkbox.isChecked()

        filters['is_completed'] = True

        # Calculate Offset for Pagination (Page 1 = Offset 0)
        offset = (self.current_page - 1) * self.records_per_page

        self.data_loader_worker = DataLoaderWorker(
            self.ops, filters, offset, self.records_per_page
        )
        self.data_loader_worker.finished.connect(self._on_data_loaded)
        self.data_loader_worker.error.connect(self._on_load_error)
        self.data_loader_worker.finished.connect(self.loading_dialog.close)
        self.data_loader_worker.start()

    def _on_data_loaded(self, total, records, stats):
        """
        Populates UI with exactly 100 records and enables pagination navigation.
        """
        self.total_records = total
        self.ui.table_widget.setRowCount(0)
        self.ui.table_widget.setSortingEnabled(False)

        # Populate only the 100 records fetched for this page
        for r in records:
            self._add_record_to_table(r)

        self.ui.table_widget.setSortingEnabled(True)

        # Update Pagination Display
        total_pages = math.ceil(total / self.records_per_page) if total > 0 else 1
        self.page_label.setText(f"Page {self.current_page} of {total_pages} (Total: {total:,})")

        # Set button states
        self.first_page_btn.setEnabled(self.current_page > 1)
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < total_pages)
        self.last_page_btn.setEnabled(self.current_page < total_pages)

        self._apply_summary_stats(stats)

        # Once the first load is successful, any future refresh uses the UI dates
        self.is_initial_load = False

    def _apply_summary_stats(self, stats):
        def fmt(s):
            h, rem = divmod(int(s), 3600)
            m, _ = divmod(rem, 60)
            return f"{h}:{m:02}", f"{(h + m/60):.2f}"

        p_str, p_dec = fmt(stats["proc_seconds"])
        w_str, w_dec = fmt(stats["purge_seconds"])

        self.total_output_label.setText(f"{stats['total_output']:,.2f}")
        self.total_waste_qty_label.setText(f"{stats['total_waste']:,.2f}")
        self.total_proc_duration_label.setText(p_str)
        self.total_waste_duration_label.setText(w_str)
        self.proc_excel_decimal_label.setText(p_dec)
        self.waste_excel_decimal_label.setText(w_dec)

    def _get_row_dict_for_dataframe(self, record):
        """Helper to build data for Excel export cache."""
        # Summation logic moved here for page-level data consistency
        r_output = sum(out.qty_output for out in record.extruder_outputs if out.qty_output)
        # (Same logic used in your original _load_records loop)
        # ...
        return {
            'Output QTY': float(r_output or 0),
            'Waste QTY': 0.0,  # Implement detail sum here if needed for export
            'Processing Duration': "0:00",  # Implement duration string here
            'Waste Duration': "0:00"
        }

    def _on_load_error(self, err):
        if self.loading_dialog: self.loading_dialog.close()
        ErrorDialog("Server Data Error", "Failed to communicate with the database.", details=err, parent=self).exec()

    def load_initial_data(self):
        self.refresh_data()

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

    def _show_context_menu(self, position: QPoint):
        record_id, is_deleted = self._get_selected_record_info()
        if record_id is None: return
        context_menu = QMenu(self)
        if is_deleted:
            view_action = QAction("View Record", self)
            restore_action = QAction("Restore Record", self)
            view_action.triggered.connect(self._view_record)
            restore_action.triggered.connect(self._restore_record)
            context_menu.addAction(view_action)
            context_menu.addAction(restore_action)
        else:
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

            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                record_ids = [int(self.ui.table_widget.item(row, 0).text()) for row in range(record_count)]
                records_to_sort = [self.ops.get_full_record_by_id(rid) for rid in record_ids]

                def get_min_start_time(record):
                    start_times = [out.datetime_start for out in record.extruder_outputs if out.datetime_start]
                    return min(start_times) if start_times else datetime.max

                sorted_records = sorted(
                    records_to_sort,
                    key=lambda r: (getattr(r.machine, 'name', ''), get_min_start_time(r))
                )
            finally:
                QApplication.restoreOverrideCursor()

            desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")

            output_path = ""
            if option == BulkExportDialog.SEPARATE_FILES:
                output_path = QFileDialog.getExistingDirectory(self, "Select Folder to Save Reports", desktop_path)
            else:
                default_filename = f"Bulk_Report_{datetime.now().strftime('%Y%m%d')}.xlsx"
                default_full_path = os.path.join(desktop_path, default_filename)
                output_path, _ = QFileDialog.getSaveFileName(self, "Save Bulk Report", default_full_path,
                                                             "Excel Files (*.xlsx)")

            if not output_path:
                return

            self.progress = QProgressDialog("Starting bulk export...", "Cancel", 0, 100, self)
            self.progress.setWindowTitle("Bulk Exporting")
            self.progress.setWindowModality(Qt.WindowModality.WindowModal)

            self.bulk_export_worker = BulkExportWorker(sorted_records, option, output_path, self.ops)
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
        if hasattr(self, 'progress') and self.progress: self.progress.close()
        ErrorDialog("Bulk Export Error", "An error occurred during the bulk export.", details=error_message,
                    parent=self).exec()
        self.bulk_export_worker = None

    def _export_record_to_excel(self):
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

        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        default_filename = f"Extruder_Report_{record.ref_no}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        default_full_path = os.path.join(desktop_path, default_filename)

        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel Report", default_full_path, "Excel Files (*.xlsx)")
        if not file_path:
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            exporter = ExcelReportExporter(self.ops)
            exporter.generate_single_report(record, file_path)

            reply = QMessageBox.information(self, "Export Successful",
                                            f"Report successfully saved.\n\nDo you want to open the file?",
                                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                os.startfile(file_path)

        except PermissionError:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Permission Denied",
                                "Unable to save the file.\n\nPlease ensure it is not open in Excel or another program.")
        except Exception:
            QApplication.restoreOverrideCursor()
            ErrorDialog("Export Error", "Failed to save the Excel file.", details=traceback.format_exc(),
                        parent=self).exec()
        finally:
            QApplication.restoreOverrideCursor()

    def _load_records(self):
        if self.is_loading: return
        self.is_loading = True
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.ui.table_widget.setSortingEnabled(False)
        self.ui.table_widget.setRowCount(0)
        self.full_data = pd.DataFrame()
        df_rows = []
        try:
            all_filters = self.advanced_filters.copy()

            if not self.is_initial_load:
                all_filters['date_from'] = self.ui.date_from_input.date().toPyDate()
                all_filters['date_to'] = self.ui.date_to_input.date().toPyDate()

            all_filters['search_term'] = self.ui.search_input.text()
            all_filters['show_only_deleted'] = self.ui.show_only_deleted_checkbox.isChecked()

            all_filters['is_completed'] = True

            if search_term := self.ui.search_input.text():
                all_filters['ref_no_search'] = search_term

            records = self.ops.get_records_with_details(filters=all_filters)
            for record_object in records:
                self._add_record_to_table(record_object)
                r_output = sum(out.qty_output for out in record_object.extruder_outputs if out.qty_output)
                r_waste = sum(
                    float(pd_item.qty) for ph in record_object.purging_headers for pd_item in ph.purging_details if
                    pd_item.qty)
                r_proc_sec = sum(
                    (out.datetime_end - out.datetime_start).total_seconds() for out in record_object.extruder_outputs if
                    out.datetime_start and out.datetime_end and out.datetime_end > out.datetime_start)
                ph, prem = divmod(r_proc_sec, 3600);
                pm, _ = divmod(prem, 60)
                r_proc_str = f"{int(ph)}:{int(pm):02}"
                r_waste_sec = sum((datetime.combine(datetime.min.date(), p.time_end) - datetime.combine(
                    datetime.min.date(), p.time_start)).total_seconds() if p.time_end > p.time_start else (
                            datetime.combine(datetime.min.date(), p.time_end) + timedelta(days=1) - datetime.combine(
                        datetime.min.date(), p.time_start)).total_seconds() for p in record_object.purging_headers if
                                  p.time_start and p.time_end)
                wh, wrem = divmod(r_waste_sec, 3600);
                wm, _ = divmod(wrem, 60)
                r_waste_str = f"{int(wh)}:{int(wm):02}"
                df_rows.append({
                    'Output QTY': float(r_output or 0), 'Waste QTY': float(r_waste),
                    'Processing Duration': r_proc_str, 'Waste Duration': r_waste_str
                })
        except Exception:
            error_dialog = ErrorDialog("Database Error", "Could not load records.", details=traceback.format_exc(),
                                       parent=self)
            error_dialog.exec()
        finally:
            self.full_data = pd.DataFrame(df_rows) if df_rows else pd.DataFrame(
                columns=['Output QTY', 'Waste QTY', 'Processing Duration', 'Waste Duration'])
            self._update_summary_box()
            self.is_loading = False
            self.ui.table_widget.setSortingEnabled(True)
            QApplication.restoreOverrideCursor()
            self.is_initial_load = False

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

        cell_data = {
            0: (str(record.id), record.id),
            1: (record.created_at.strftime("%Y-%m-%d %H:%M") if record.created_at else "N/A",
                record.created_at.timestamp() if record.created_at else 0),
            2: (str(record.ref_no or ''), record.ref_no),
            3: (getattr(record.machine, 'name', 'N/A'), None),
            4: (record.product_code, None),
            5: (record.lot_number, None),
            6: (min_start_time.strftime("%Y-%m-%d %H:%M") if min_start_time else "N/A",
                min_start_time.timestamp() if min_start_time else 0),
            7: (max_end_time.strftime("%Y-%m-%d %H:%M") if max_end_time else "N/A",
                max_end_time.timestamp() if max_end_time else 0),
            8: (f"{output_per_hour:.2f}", float(output_per_hour)),
            9: (f"{record.target_output_per_hour or 0:.2f}", float(record.target_output_per_hour or 0)),
            10: (f"{total_output or 0:.2f}", float(total_output or 0)),
            11: (", ".join([p.product_code for p in record.purging_headers if p.product_code]) or "N/A", None),
            12: (purging_time_str, total_purging_seconds),
            13: (", ".join([f"{p.employee.first_name} {p.employee.last_name}" for p in record.extruder_personnels if
                            p.employee]) or "N/A", None),
        }

        is_deleted_view = self.ui.show_only_deleted_checkbox.isChecked()
        for col, (text, numeric_val) in cell_data.items():
            item = NumericTableWidgetItem(text) if numeric_val is not None else QTableWidgetItem(text)
            if numeric_val is not None:
                item.setData(Qt.ItemDataRole.UserRole, numeric_val)
            if is_deleted_view:
                item.setBackground(QBrush(QColor("#e0e0e0")))
            self.ui.table_widget.setItem(row_pos, col, item)

    def _get_selected_record_info(self):
        selected_rows = self.ui.table_widget.selectionModel().selectedRows()
        if not selected_rows: return None, False
        row = selected_rows[0].row()
        record_id = int(self.ui.table_widget.item(row, 0).text())
        is_deleted = self.ui.show_only_deleted_checkbox.isChecked()
        return record_id, is_deleted

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
                self.data_changed.emit()
        else:
            QMessageBox.warning(self, "Not Found", "Could not retrieve full record details for editing.")


