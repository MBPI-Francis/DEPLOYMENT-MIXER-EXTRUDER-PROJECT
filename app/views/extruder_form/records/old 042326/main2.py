# app/views/extruder_form/records/main.py

import decimal
import os
import traceback
from datetime import datetime, timedelta
from typing import Type, List

import openpyxl
import pandas as pd  # Added for Data Handling
from openpyxl.utils import get_column_letter

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QDate, QPoint, QThread
from PyQt6.QtGui import QAction, QColor, QBrush
from PyQt6.QtWidgets import (QWidget, QTableWidgetItem, QMessageBox, QApplication, QMenu, QDialog, QProgressDialog,
                             QFileDialog, QGroupBox, QGridLayout, QLabel,
                             QVBoxLayout, QPushButton, QHBoxLayout)
from sqlalchemy.orm import Session

from .bulk_export_dialog import BulkExportDialog
from .edit_dialog import ExtruderEditDialog
# Update import to include the new class
from .exporter import ExcelReportExporter, ExtruderListExporter
from .filter_dialog import FilterDialog
from .ops import ExtruderRecordsOperations
from .ui_setup import Ui_ExtruderRecordsList
from .view_dialog import ExtruderRecordViewDialog
from ..entry_form.widgets.error_dialog import ErrorDialog


# ... (Keep NumericTableWidgetItem and BulkExportWorker classes unchanged) ...
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
        template_wb = openpyxl.load_workbook(ExcelReportExporter.TEMPLATE_PATH)
        template_sheet = template_wb.active

        output_wb = openpyxl.Workbook()
        output_wb.remove(output_wb.active)

        for i, record in enumerate(self.records):
            if not self._is_running: return
            self.progress.emit(int((i / total) * 100), f"Processing {record.ref_no} ({i + 1}/{total})...")

            sheet_title = f"Ref {record.ref_no}".replace('/', '_').replace('\\', '_')[:31]
            new_sheet = output_wb.create_sheet(title=sheet_title)

            for col_letter in [get_column_letter(c) for c in range(1, template_sheet.max_column + 1)]:
                new_sheet.column_dimensions[col_letter].width = template_sheet.column_dimensions[col_letter].width
            for row_idx, dim in template_sheet.row_dimensions.items():
                if dim.height is not None:
                    new_sheet.row_dimensions[row_idx].height = dim.height

            for row in template_sheet.iter_rows():
                for cell in row:
                    new_cell = new_sheet.cell(row=cell.row, column=cell.column)
                    new_cell.value = cell.value
                    if cell.has_style:
                        new_cell.font = cell.font.copy()
                        new_cell.border = cell.border.copy()
                        new_cell.fill = cell.fill.copy()
                        new_cell.number_format = cell.number_format
                        new_cell.protection = cell.protection.copy()
                        new_cell.alignment = cell.alignment.copy()

            for mc_range in template_sheet.merged_cells.ranges:
                new_sheet.merge_cells(str(mc_range))

            exporter.populate_sheet(new_sheet, record, overwrite_formulas=False)

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
                        new_cell.font = cell.font.copy()
                        new_cell.border = cell.border.copy()
                        new_cell.fill = cell.fill.copy()
                        new_cell.number_format = cell.number_format
                        new_cell.protection = cell.protection.copy()
                        new_cell.alignment = cell.alignment.copy()

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


class ExtruderRecordsView(QWidget):
    data_changed = pyqtSignal()

    def __init__(self, session_factory: Type[Session], parent=None):
        super().__init__(parent)
        self.ui = Ui_ExtruderRecordsList()
        self.ui.setupUi(self)
        self.ops = ExtruderRecordsOperations(session_factory)

        self.bulk_export_worker = None
        self.filter_dialog = FilterDialog(session_factory, self)
        self.advanced_filters = {}
        self.is_loading = False
        self.is_deleted_color = QColor("#e0e0e0")

        # --- Data State ---
        self.full_data = pd.DataFrame()
        self.current_summary_stats = {}

        self._setup_connections()

        # --- UI Injection: Add Export Button to Search Bar ---
        self._inject_export_button()

        # --- UI Addition: Add Summary Box ---
        self.summary_box = self._create_summary_box()
        # Add to the main layout created by setupUi (usually it has a main layout)
        # If the generated UI doesn't expose the main layout easily, we assume it's the widget's layout
        if self.layout():
            self.layout().addWidget(self.summary_box)
        else:
            # Fallback if setupUi didn't set a layout on 'self' (which is rare for .ui files)
            layout = QVBoxLayout(self)
            layout.addWidget(self.ui.frame)
            layout.addWidget(self.summary_box)

        self.load_initial_data()
        self._update_ui_for_view_mode()

        self.ui.table_widget.sortByColumn(1, Qt.SortOrder.DescendingOrder)

        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f: self.setStyleSheet(f.read())

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

    # def _create_summary_box(self) -> QGroupBox:
    #     summary_box = QGroupBox("Loaded Data Summary")
    #     summary_box.setObjectName("SummaryBox")
    #
    #     layout = QGridLayout(summary_box)
    #     layout.setSpacing(10)
    #
    #     self.total_output_label = QLabel("0.00")
    #     self.total_waste_qty_label = QLabel("0.00")
    #     self.total_proc_duration_label = QLabel("0:00")
    #     self.total_waste_duration_label = QLabel("0:00")
    #     self.proc_excel_decimal_label = QLabel("0.00")
    #     self.waste_excel_decimal_label = QLabel("0.00")
    #
    #     all_value_labels = [
    #         self.total_output_label, self.total_waste_qty_label,
    #         self.total_proc_duration_label, self.total_waste_duration_label,
    #         self.proc_excel_decimal_label, self.waste_excel_decimal_label
    #     ]
    #
    #     for label in all_value_labels:
    #         label.setObjectName("SummaryValueLabel")
    #         label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    #
    #     layout.addWidget(QLabel("<b>Total Output Qty:</b>"), 0, 0)
    #     layout.addWidget(self.total_output_label, 0, 1)
    #     layout.addWidget(QLabel("<b>Total Processing Duration (HH:MM):</b>"), 0, 2)
    #     layout.addWidget(self.total_proc_duration_label, 0, 3)
    #     layout.addWidget(QLabel("<b>Processing Duration (Excel Decimal):</b>"), 0, 4)
    #     layout.addWidget(self.proc_excel_decimal_label, 0, 5)
    #
    #     layout.addWidget(QLabel("<b>Total Waste Qty:</b>"), 1, 0)
    #     layout.addWidget(self.total_waste_qty_label, 1, 1)
    #     layout.addWidget(QLabel("<b>Total Waste Duration (HH:MM):</b>"), 1, 2)
    #     layout.addWidget(self.total_waste_duration_label, 1, 3)
    #     layout.addWidget(QLabel("<b>Waste Duration (Excel Decimal):</b>"), 1, 4)
    #     layout.addWidget(self.waste_excel_decimal_label, 1, 5)
    #
    #     layout.setColumnStretch(2, 1)
    #     layout.setColumnStretch(4, 1)
    #     layout.setColumnStretch(6, 2)
    #
    #     return summary_box

    # def _create_summary_box(self) -> QGroupBox:
    #     """
    #     Creates the Summary Box UI matching the Mixer module's look.
    #     """
    #     summary_box = QGroupBox()
    #     summary_box.setObjectName("SummaryBox")
    #
    #     # Use Grid Layout
    #     layout = QGridLayout(summary_box)
    #     layout.setSpacing(10)  # Comfortable spacing
    #
    #
    #     # Initialize Value Labels
    #     self.total_output_label = QLabel("0.00")
    #     self.total_waste_qty_label = QLabel("0.00")
    #     self.total_proc_duration_label = QLabel("0:00")
    #     self.total_waste_duration_label = QLabel("0:00")
    #     self.proc_excel_decimal_label = QLabel("0.00")
    #     self.waste_excel_decimal_label = QLabel("0.00")
    #
    #     all_value_labels = [
    #         self.total_output_label, self.total_waste_qty_label,
    #         self.total_proc_duration_label, self.total_waste_duration_label,
    #         self.proc_excel_decimal_label, self.waste_excel_decimal_label
    #     ]
    #
    #     # Apply Object Name for CSS Styling and Alignment
    #     for label in all_value_labels:
    #         label.setObjectName("SummaryValueLabel")
    #         label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    #
    #     # --- Row 0: Production Data ---
    #     layout.addWidget(QLabel("Total Output Qty:"), 0, 0)
    #     layout.addWidget(self.total_output_label, 0, 1)
    #
    #     layout.addWidget(QLabel("Processing Duration (HH:MM):"), 0, 2)
    #     layout.addWidget(self.total_proc_duration_label, 0, 3)
    #
    #     layout.addWidget(QLabel("Processing (Excel Dec):"), 0, 4)
    #     layout.addWidget(self.proc_excel_decimal_label, 0, 5)
    #
    #     # --- Row 1: Waste Data ---
    #     layout.addWidget(QLabel("Total Purging Qty:"), 1, 0)
    #     layout.addWidget(self.total_waste_qty_label, 1, 1)
    #
    #     layout.addWidget(QLabel("Purging Duration (HH:MM):"), 1, 2)
    #     layout.addWidget(self.total_waste_duration_label, 1, 3)
    #
    #     layout.addWidget(QLabel("Purging (Excel Dec):"), 1, 4)
    #     layout.addWidget(self.waste_excel_decimal_label, 1, 5)
    #
    #     # Stretch factors to keep columns proportional
    #     # Columns 0, 2, 4 are labels (auto size)
    #     # Columns 1, 3, 5 are values (stretch to fill)
    #     layout.setColumnStretch(1, 3)
    #     layout.setColumnStretch(3, 3)
    #     layout.setColumnStretch(5, 5)
    #
    #     return summary_box

    def _create_summary_box(self) -> QGroupBox:
        """
        Creates the Summary Box UI matching the Mixer module's look.
        """
        summary_box = QGroupBox()
        summary_box.setObjectName("SummaryBox")

        layout = QGridLayout(summary_box)
        layout.setSpacing(10)


        # Initialize Value Labels
        self.total_output_label = QLabel("0.00")
        self.total_waste_qty_label = QLabel("0.00")
        self.total_proc_duration_label = QLabel("0:00")
        self.total_waste_duration_label = QLabel("0:00")
        self.proc_excel_decimal_label = QLabel("0.00")
        self.waste_excel_decimal_label = QLabel("0.00")

        all_value_labels = [
            self.total_output_label, self.total_waste_qty_label,
            self.total_proc_duration_label, self.total_waste_duration_label,
            self.proc_excel_decimal_label, self.waste_excel_decimal_label
        ]

        for label in all_value_labels:
            label.setObjectName("SummaryValueLabel")
            # CHANGED: AlignLeft ensures the value sits immediately next to the label
            label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        # --- Row 0: Production Data ---
        layout.addWidget(QLabel("<b>Total Output Qty:</b>"), 0, 0)
        layout.addWidget(self.total_output_label, 0, 1)

        layout.addWidget(QLabel("<b>Total Processing Duration:</b>"), 0, 2)
        layout.addWidget(self.total_proc_duration_label, 0, 3)

        layout.addWidget(QLabel("<b>Processing Duration (Decimal):</b>"), 0, 4)
        layout.addWidget(self.proc_excel_decimal_label, 0, 5)

        # --- Row 1: Waste Data (Updated to 'Purging') ---
        layout.addWidget(QLabel("<b>Total Cleaning Qty:</b>"), 1, 0)
        layout.addWidget(self.total_waste_qty_label, 1, 1)

        layout.addWidget(QLabel("<b>Total Cleaning Duration:</b>"), 1, 2)
        layout.addWidget(self.total_waste_duration_label, 1, 3)

        layout.addWidget(QLabel("<b>Cleaning Duration (Decimal):</b>"), 1, 4)
        layout.addWidget(self.waste_excel_decimal_label, 1, 5)

        # Stretch factors ensure the 3 groups are evenly spaced horizontally
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(3, 1)
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
        proc_decimal = (proc_h % 24) + (proc_m / 60)
        waste_decimal = (waste_h % 24) + (waste_m / 60)

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
        # 1. Check if table is empty
        if self.ui.table_widget.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "There is no data available to export.")
            return

        default_filename = f"Extruder_Summary_List_{datetime.now().strftime('%Y%m%d')}.xlsx"
        desktop_path = os.path.join(os.path.expanduser("~"), "Desktop")
        default_full_path = os.path.join(desktop_path, default_filename)

        file_path, _ = QFileDialog.getSaveFileName(self, "Save List Export", default_full_path, "Excel Files (*.xlsx)")
        if not file_path:
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # 2. Fetch Export Data using the specialized OPS method
            current_filters = self.advanced_filters.copy()
            current_filters['search_term'] = self.ui.search_input.text()
            current_filters['date_from'] = self.ui.date_from_input.date().toPyDate()
            current_filters['date_to'] = self.ui.date_to_input.date().toPyDate()
            current_filters['show_only_deleted'] = self.ui.show_only_deleted_checkbox.isChecked()
            if self.ui.search_input.text():
                current_filters['ref_no_search'] = self.ui.search_input.text()

            # get_export_data returns a list of dictionaries with keys like 'Total Output', 'Cleaning Duration', etc.
            export_data = self.ops.get_export_data(current_filters)

            # 3. Calculate Stats for the Footer based on the EXPORT data
            # This ensures the footer matches the rows in the excel file exactly.

            total_output = sum(item['Total Output'] for item in export_data)
            # Note: ops.py doesn't return 'Waste QTY' in get_export_data currently,
            # we might need to rely on self.current_summary_stats OR update ops.py.
            # However, looking at previous turns, self.full_data stores the UI view data.
            #
            # OPTION A: Recalculate from export_data (Most accurate if export_data has all fields)
            # The OPS get_export_data returns 'Cleaning Duration' but not explicit Waste QTY column.
            #
            # OPTION B: Use self.current_summary_stats (Matches the UI Summary Box).
            # This is safer because the UI Summary Box logic is robust.

            summary_stats = self.current_summary_stats

            # 4. Export
            exporter = ExtruderListExporter()
            exporter.export_list(export_data, summary_stats, file_path)

            QMessageBox.information(self, "Success", "List exported successfully!")
            os.startfile(file_path)

        except Exception as e:
            ErrorDialog("Export Error", "Failed to export list.", details=traceback.format_exc(), parent=self).exec()
        finally:
            QApplication.restoreOverrideCursor()

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
        """
        Loads records, populates self.full_data for calculations,
        and updates the table and summary box.
        """
        if self.is_loading: return
        self.is_loading = True
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.ui.table_widget.setSortingEnabled(False)
        self.ui.table_widget.setRowCount(0)

        self.full_data = pd.DataFrame()  # Reset
        df_rows = []

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

                # --- GATHER DATA FOR SUMMARY BOX & EXPORT ---
                # 1. Output
                r_output = sum(out.qty_output for out in record_object.extruder_outputs if out.qty_output)

                # 2. Waste (Cleaning)
                r_waste = 0
                for ph in record_object.purging_headers:
                    for pd_item in ph.purging_details:
                        if pd_item.qty:
                            r_waste += float(pd_item.qty)

                # 3. Processing Duration
                r_proc_sec = sum(
                    (out.datetime_end - out.datetime_start).total_seconds()
                    for out in record_object.extruder_outputs
                    if out.datetime_start and out.datetime_end and out.datetime_end > out.datetime_start
                )
                ph, prem = divmod(r_proc_sec, 3600)
                pm, _ = divmod(prem, 60)
                r_proc_str = f"{int(ph)}:{int(pm):02}"

                # 4. Waste Duration
                r_waste_sec = 0
                for p in record_object.purging_headers:
                    if p.time_start and p.time_end:
                        dummy_date = datetime.now().date()
                        start_dt = datetime.combine(dummy_date, p.time_start)
                        end_dt = datetime.combine(dummy_date, p.time_end)
                        if end_dt < start_dt: end_dt += timedelta(days=1)
                        r_waste_sec += (end_dt - start_dt).total_seconds()

                wh, wrem = divmod(r_waste_sec, 3600)
                wm, _ = divmod(wrem, 60)
                r_waste_str = f"{int(wh)}:{int(wm):02}"

                # Add to list
                df_rows.append({
                    'Date Encoded': record_object.created_at.strftime(
                        "%Y-%m-%d %H:%M") if record_object.created_at else "",
                    'Ref No': record_object.ref_no,
                    'Machine': getattr(record_object.machine, 'name', 'N/A'),
                    'Product Code': record_object.product_code,
                    'Lot Number': record_object.lot_number,
                    'Output QTY': float(r_output or 0),
                    'Waste QTY': float(r_waste),
                    'Processing Duration': r_proc_str,
                    'Waste Duration': r_waste_str
                })

        except Exception:
            error_dialog = ErrorDialog("Database Error", "Could not load records.", details=traceback.format_exc(),
                                       parent=self)
            error_dialog.exec()
        finally:
            if df_rows:
                self.full_data = pd.DataFrame(df_rows)
            else:
                # Empty DF with correct columns to safely call summary update
                self.full_data = pd.DataFrame(
                    columns=['Date Encoded', 'Ref No', 'Machine', 'Product Code', 'Lot Number', 'Output QTY',
                             'Waste QTY', 'Processing Duration', 'Waste Duration'])

            self._update_summary_box()
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