# app/views/mixer_records/main.py

import os
import time
from typing import Type, Callable
from datetime import timedelta  # <-- NEW IMPORT

from PyQt6.QtGui import QAction, QKeySequence
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu, QMessageBox,
    QFileDialog, QLineEdit, QLabel, QDialog, QProgressBar,
    QGroupBox, QGridLayout  # <-- NEW IMPORTS
)
from PyQt6.QtCore import Qt, pyqtSlot, QThread, pyqtSignal, QPropertyAnimation, QTimer, QEasingCurve

import pandas as pd
import qtawesome as qta

from app.widgets.smart_combo_box import SmartComboBox
from app.widgets.workers import LiveSearchWorker
from .exporter import ExcelExporter
from .ops import (
    delete_mixer_record, get_mixer_report_data, get_deleted_mixer_records, restore_mixer_records,
    update_mixer_record, get_editor_initial_data
)
from .widgets import (
    FilterDialog, RemarksViewerDialog, RestoreDialog, SecureConfirmationDialog,
    EditRecordDialog
)
from models import MixerDetail
from app.database.mixer_machine_ops import get_active_machines


# --- All worker and dialog classes remain unchanged ---
class DatabaseMonitorThread(QThread):
    database_changed = pyqtSignal()

    # ... (implementation is correct, no changes needed) ...
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self._is_running = True
        self.last_known_timestamp = None

    def run(self):
        session = self.Session()
        try:
            self.last_known_timestamp = self._get_latest_timestamp(session)
        except Exception as e:
            print(f"Initial timestamp check failed: {e}")
        finally:
            session.close()
        while self._is_running:
            time.sleep(10)
            if not self._is_running: break
            session = self.Session()
            try:
                latest_timestamp = self._get_latest_timestamp(session)
                if latest_timestamp and latest_timestamp != self.last_known_timestamp:
                    self.last_known_timestamp = latest_timestamp
                    self.database_changed.emit()
            except Exception as e:
                print(f"Database monitor check failed: {e}")
            finally:
                session.close()

    def _get_latest_timestamp(self, session: sessionmaker):
        latest_created = session.query(func.max(MixerDetail.created_at)).scalar()
        latest_modified = session.query(func.max(MixerDetail.modified_at)).scalar()
        if latest_modified and (not latest_created or latest_modified > latest_created):
            return latest_modified
        return latest_created

    def stop(self):
        self._is_running = False


class ExportWorker(QThread):
    success = pyqtSignal(str)
    error = pyqtSignal(str)

    # ... (implementation is correct, no changes needed) ...
    def __init__(self, dataframe: pd.DataFrame, filepath: str, parent=None):
        super().__init__(parent)
        self.df = dataframe
        self.filepath = filepath

    def run(self):
        try:
            exporter = ExcelExporter(self.df)
            exporter.export(self.filepath)
            self.success.emit(self.filepath)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.error.emit(f"An error occurred during export:\n\n{e}\n\n{error_details}")


class LoadingDialog(QDialog):
    # ... (implementation is correct, no changes needed) ...
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Processing...")
        self.setModal(True)
        self.setFixedSize(300, 100)
        layout = QVBoxLayout(self)
        self.label = QLabel("Please wait...", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)  # Indeterminate mode
        layout.addWidget(self.label)
        layout.addWidget(self.progress_bar)

    def set_text(self, text: str):
        self.label.setText(text)


class MixerRecordsView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.full_data = pd.DataFrame()
        self.machine_list = []
        self.current_filters = {}
        self.editor_initial_data = {}
        self.live_search_worker = None
        self.export_worker = None

        main_layout = QVBoxLayout(self)
        top_bar_layout = QHBoxLayout()
        # ... (top bar setup is correct) ...
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search all columns...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(300)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setIcon(qta.icon("fa5s.sync-alt"))
        self.refresh_button.setObjectName("ActionButton")
        self.refresh_button.setToolTip("Refresh the data from the database (Ctrl+R)")
        self.filter_button = QPushButton("Filter Records...")
        self.filter_button.setObjectName("ActionButton")
        self.clear_filters_button = QPushButton("Clear Filters")
        self.clear_filters_button.setObjectName("ActionButton")
        self.restore_button = QPushButton("Restore Records...")
        self.restore_button.setObjectName("ActionButton")
        self.export_button = QPushButton("Export...")
        self.export_button.setObjectName("ActionButton")
        top_bar_layout.addWidget(self.search_input)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.refresh_button)
        top_bar_layout.addWidget(self.filter_button)
        top_bar_layout.addWidget(self.clear_filters_button)
        top_bar_layout.addWidget(self.restore_button)
        top_bar_layout.addWidget(self.export_button)

        self.notification_label = QLabel(self)
        self.notification_label.setObjectName("NotificationLabel")
        self.notification_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notification_label.setFixedHeight(0)
        self.notification_label.setStyleSheet(
            "QLabel#NotificationLabel { background-color: #28a745; color: white; font-weight: bold; font-size: 10pt; padding: 8px; }")

        self.table = QTableWidget()
        self.setup_table()

        # --- NEW: Create and add the summary box ---
        self.summary_box = self._create_summary_box()

        main_layout.addLayout(top_bar_layout)
        main_layout.addWidget(self.table)
        main_layout.addWidget(self.summary_box)  # Add the summary box to the layout
        main_layout.addWidget(self.notification_label)
        # --- END NEW ---

        # ... (signal connections and the rest of __init__ are correct) ...
        self.search_input.textChanged.connect(self.filter_table_by_search)
        self.refresh_button.clicked.connect(self.refresh_data)
        self.filter_button.clicked.connect(self.open_filter_dialog)
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.restore_button.clicked.connect(self.open_restore_dialog)
        self.export_button.clicked.connect(self.export_to_excel)
        self.refresh_button.clicked.connect(lambda: self.refresh_data(is_manual_refresh=True))
        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f: self.setStyleSheet(f.read())
        self._load_prerequisites_and_data()
        self._setup_shortcuts()
        self._start_database_monitor()

    # --- NEW: Method to create the summary box UI ---
    # def _create_summary_box(self) -> QGroupBox:
    #     """Creates the GroupBox container and all the labels for the summary."""
    #     summary_box = QGroupBox()
    #     summary_box.setObjectName("SummaryBox")
    #
    #     layout = QGridLayout(summary_box)
    #     layout.setSpacing(10)
    #
    #     # Create labels and store the value labels as instance members
    #     self.total_output_label = QLabel("0.00")
    #     self.avg_output_label = QLabel("0.00")
    #     self.total_cleaning_qty_label = QLabel("0.00")
    #     self.avg_cleaning_qty_label = QLabel("0.00")
    #     self.total_proc_duration_label = QLabel("0:00")
    #     self.total_clean_duration_label = QLabel("0:00")
    #
    #     # Set object names for styling
    #     for label in [self.total_output_label, self.avg_output_label, self.total_cleaning_qty_label,
    #                   self.avg_cleaning_qty_label, self.total_proc_duration_label, self.total_clean_duration_label]:
    #         label.setObjectName("SummaryValueLabel")
    #
    #     # Add labels to the grid layout
    #     layout.addWidget(QLabel("<b>Total Output Qty:</b>"), 0, 0)
    #     layout.addWidget(self.total_output_label, 0, 1)
    #     layout.addWidget(QLabel("<b>Average Output Qty:</b>"), 1, 0)
    #     layout.addWidget(self.avg_output_label, 1, 1)
    #
    #     layout.addWidget(QLabel("<b>Total Cleaning Qty:</b>"), 0, 2)
    #     layout.addWidget(self.total_cleaning_qty_label, 0, 3)
    #     layout.addWidget(QLabel("<b>Average Cleaning Qty:</b>"), 1, 2)
    #     layout.addWidget(self.avg_cleaning_qty_label, 1, 3)
    #
    #     layout.addWidget(QLabel("<b>Total Processing Duration:</b>"), 0, 4)
    #     layout.addWidget(self.total_proc_duration_label, 0, 5)
    #     layout.addWidget(QLabel("<b>Total Cleaning Duration:</b>"), 1, 4)
    #     layout.addWidget(self.total_clean_duration_label, 1, 5)
    #
    #     # Add a stretch to push columns to the left
    #     layout.setColumnStretch(6, 1)
    #
    #     return summary_box

    # --- NEW: Method to perform all summary calculations and update the UI ---

    # def _create_summary_box(self) -> QGroupBox:
    #     """Creates the GroupBox container and all the labels for the summary."""
    #     summary_box = QGroupBox()
    #     summary_box.setObjectName("SummaryBox")
    #
    #     layout = QGridLayout(summary_box)
    #     layout.setSpacing(10)
    #
    #     # Create labels and store the value labels as instance members
    #     self.total_output_label = QLabel("0.00")
    #     self.avg_output_label = QLabel("0.00")
    #     self.total_cleaning_qty_label = QLabel("0.00")
    #     self.avg_cleaning_qty_label = QLabel("0.00")
    #     self.total_proc_duration_label = QLabel("0:00")
    #     self.total_clean_duration_label = QLabel("0:00")
    #
    #     # Set object names for styling and right-align the values for a cleaner look
    #     for label in [self.total_output_label, self.avg_output_label, self.total_cleaning_qty_label,
    #                   self.avg_cleaning_qty_label, self.total_proc_duration_label, self.total_clean_duration_label]:
    #         label.setObjectName("SummaryValueLabel")
    #         label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    #
    #     # --- MODIFIED LAYOUT LOGIC ---
    #     # Group 1: Output Qty (Columns 0 & 1)
    #     layout.addWidget(QLabel("<b>Total Output Qty:</b>"), 0, 0)
    #     layout.addWidget(self.total_output_label, 0, 1)
    #     layout.addWidget(QLabel("<b>Average Output Qty:</b>"), 1, 0)
    #     layout.addWidget(self.avg_output_label, 1, 1)
    #
    #     # Group 2: Cleaning Qty (Columns 3 & 4) - Note the jump from col 1 to 3
    #     layout.addWidget(QLabel("<b>Total Cleaning Qty:</b>"), 0, 3)
    #     layout.addWidget(self.total_cleaning_qty_label, 0, 4)
    #     layout.addWidget(QLabel("<b>Average Cleaning Qty:</b>"), 1, 3)
    #     layout.addWidget(self.avg_cleaning_qty_label, 1, 4)
    #
    #     # Group 3: Durations (Columns 6 & 7) - Note the jump from col 4 to 6
    #     layout.addWidget(QLabel("<b>Total Processing Duration:</b>"), 0, 6)
    #     layout.addWidget(self.total_proc_duration_label, 0, 7)
    #     layout.addWidget(QLabel("<b>Total Cleaning Duration:</b>"), 1, 6)
    #     layout.addWidget(self.total_clean_duration_label, 1, 7)
    #
    #     # This is the key: Add stretch factors to the empty "spacer" columns (2 and 5)
    #     # This forces the available space to be distributed between the groups.
    #     layout.setColumnStretch(2, 1)
    #     layout.setColumnStretch(5, 1)
    #
    #     # We can add a final stretch to ensure everything stays aligned left if there's still extra space
    #     layout.setColumnStretch(8, 2)
    #     # --- END MODIFICATION ---
    #
    #     return summary_box

    def _create_summary_box(self) -> QGroupBox:
        """Creates the GroupBox container and all the labels for the summary."""
        # --- MODIFICATION: Add the title directly here ---
        summary_box = QGroupBox()
        summary_box.setObjectName("SummaryBox")

        layout = QGridLayout(summary_box)
        layout.setSpacing(10)

        # Create labels and store them as instance members (order doesn't matter here)
        self.visible_records_label = QLabel("0")
        self.total_output_label = QLabel("0.00")
        self.avg_output_label = QLabel("0.00")
        self.total_cleaning_qty_label = QLabel("0.00")
        self.avg_cleaning_qty_label = QLabel("0.00")
        self.total_proc_duration_label = QLabel("0.00")
        self.total_clean_duration_label = QLabel("0.00")

        # Set object names for styling and right-align the values
        all_value_labels = [
            self.visible_records_label, self.total_output_label, self.avg_output_label,
            self.total_cleaning_qty_label, self.avg_cleaning_qty_label,
            self.total_proc_duration_label, self.total_clean_duration_label
        ]
        for label in all_value_labels:
            label.setObjectName("SummaryValueLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # --- MODIFIED LAYOUT LOGIC ---

        # Group 1: Output Qty (Columns 0, 1)
        layout.addWidget(QLabel("<b>Total Output Qty:</b>"), 0, 0)
        layout.addWidget(self.total_output_label, 0, 1)
        layout.addWidget(QLabel("<b>Average Output Qty:</b>"), 1, 0)
        layout.addWidget(self.avg_output_label, 1, 1)

        # Group 2: Cleaning Qty (Columns 3, 4)
        layout.addWidget(QLabel("<b>Total Cleaning Qty:</b>"), 0, 3)
        layout.addWidget(self.total_cleaning_qty_label, 0, 4)
        layout.addWidget(QLabel("<b>Average Cleaning Qty:</b>"), 1, 3)
        layout.addWidget(self.avg_cleaning_qty_label, 1, 4)

        # Group 3: Durations (Columns 6, 7)
        layout.addWidget(QLabel("<b>Total Processing (Decimal Hours):</b>"), 0, 6)
        layout.addWidget(self.total_proc_duration_label, 0, 7)
        layout.addWidget(QLabel("<b>Total Cleaning (Decimal Hours):</b>"), 1, 6)
        layout.addWidget(self.total_clean_duration_label, 1, 7)

        # Group 4: Record Count (Columns 9, 10) - Positioned at the end
        layout.addWidget(QLabel("<b>Visible Records:</b>"), 0, 9)
        layout.addWidget(self.visible_records_label, 0, 10)

        # Use stretch factors to create space between the groups
        layout.setColumnStretch(2, 1)  # Spacer 1
        layout.setColumnStretch(5, 1)  # Spacer 2
        layout.setColumnStretch(8, 1)  # Spacer 3, before the record count

        # --- END MODIFICATION ---

        return summary_box


    # def _update_summary_box(self):
    #     """Calculates summaries based on visible table data and updates labels."""
    #     visible_ids = [
    #         self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
    #         for row in range(self.table.rowCount())
    #         if not self.table.isRowHidden(row) and self.table.item(row, 0)
    #     ]
    #
    #     if not visible_ids:
    #         # Reset all labels to zero if no data is visible
    #         self.total_output_label.setText("0.00")
    #         self.avg_output_label.setText("0.00")
    #         self.total_cleaning_qty_label.setText("0.00")
    #         self.avg_cleaning_qty_label.setText("0.00")
    #         self.total_proc_duration_label.setText("0:00")
    #         self.total_clean_duration_label.setText("0:00")
    #         return
    #
    #     # Filter the main DataFrame to get only the visible rows
    #     visible_df = self.full_data[self.full_data['detail_id'].isin(visible_ids)]
    #
    #     # --- Perform Calculations ---
    #     total_output = visible_df['Output QTY'].sum()
    #     avg_output = visible_df['Output QTY'].mean()
    #     total_cleaning = visible_df['Cleaning QTY'].sum()
    #     avg_cleaning = visible_df['Cleaning QTY'].mean()
    #
    #     # Calculate total durations
    #     total_proc_delta = timedelta()
    #     for duration_str in visible_df['Processing Duration'].dropna():
    #         try:
    #             hours, minutes = map(int, duration_str.split(':'))
    #             total_proc_delta += timedelta(hours=hours, minutes=minutes)
    #         except (ValueError, TypeError):
    #             continue
    #
    #     total_clean_delta = timedelta()
    #     for duration_str in visible_df['Cleaning Duration'].dropna():
    #         try:
    #             hours, minutes = map(int, duration_str.split(':'))
    #             total_clean_delta += timedelta(hours=hours, minutes=minutes)
    #         except (ValueError, TypeError):
    #             continue
    #
    #     # Format durations into HH:MM
    #     proc_secs = total_proc_delta.total_seconds()
    #     proc_h = int(proc_secs // 3600)
    #     proc_m = int((proc_secs % 3600) // 60)
    #
    #     clean_secs = total_clean_delta.total_seconds()
    #     clean_h = int(clean_secs // 3600)
    #     clean_m = int((clean_secs % 3600) // 60)
    #
    #     # --- Update Labels ---
    #     self.total_output_label.setText(f"{total_output:,.2f}")
    #     self.avg_output_label.setText(f"{avg_output:,.2f}")
    #     self.total_cleaning_qty_label.setText(f"{total_cleaning:,.2f}")
    #     self.avg_cleaning_qty_label.setText(f"{avg_cleaning:,.2f}")
    #     self.total_proc_duration_label.setText(f"{proc_h}:{proc_m:02}")
    #     self.total_clean_duration_label.setText(f"{clean_h}:{clean_m:02}")

    def _update_summary_box(self):
        """Calculates summaries based on visible table data and updates labels."""
        visible_ids = [
            self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
            for row in range(self.table.rowCount())
            if not self.table.isRowHidden(row) and self.table.item(row, 0)
        ]

        visible_count = len(visible_ids)
        self.visible_records_label.setText(f"{visible_count}")  # <-- NEW: Update record count

        if not visible_ids:
            # Reset all labels to zero if no data is visible
            self.total_output_label.setText("0.00")
            self.avg_output_label.setText("0.00")
            self.total_cleaning_qty_label.setText("0.00")
            self.avg_cleaning_qty_label.setText("0.00")
            self.total_proc_duration_label.setText("0.00")
            self.total_clean_duration_label.setText("0.00")
            return

        visible_df = self.full_data[self.full_data['detail_id'].isin(visible_ids)]

        # --- Perform Standard Calculations ---
        total_output = visible_df['Output QTY'].sum()
        avg_output = visible_df['Output QTY'].mean()
        total_cleaning = visible_df['Cleaning QTY'].sum()
        avg_cleaning = visible_df['Cleaning QTY'].mean()

        # --- MODIFIED: Duration and Decimal Conversion ---
        total_proc_delta = timedelta()
        for duration_str in visible_df['Processing Duration'].dropna():
            try:
                if duration_str:  # Ensure not an empty string
                    hours, minutes = map(int, duration_str.split(':'))
                    total_proc_delta += timedelta(hours=hours, minutes=minutes)
            except (ValueError, TypeError):
                continue

        total_clean_delta = timedelta()
        for duration_str in visible_df['Cleaning Duration'].dropna():
            try:
                if duration_str:
                    hours, minutes = map(int, duration_str.split(':'))
                    total_clean_delta += timedelta(hours=hours, minutes=minutes)
            except (ValueError, TypeError):
                continue

        # Directly convert total seconds to decimal hours
        proc_decimal_hours = total_proc_delta.total_seconds() / 3600
        clean_decimal_hours = total_clean_delta.total_seconds() / 3600
        # --- END MODIFICATION ---

        # --- Update All Labels ---
        self.total_output_label.setText(f"{total_output:,.2f}")
        self.avg_output_label.setText(f"{avg_output:,.2f}")
        self.total_cleaning_qty_label.setText(f"{total_cleaning:,.2f}")
        self.avg_cleaning_qty_label.setText(f"{avg_cleaning:,.2f}")
        self.total_proc_duration_label.setText(f"{proc_decimal_hours:.2f}")
        self.total_clean_duration_label.setText(f"{clean_decimal_hours:.2f}")




    # --- MODIFIED: Trigger summary update after filtering ---
    def filter_table_by_search(self, search_text: str):
        search_text = search_text.lower()
        # ... (existing filtering logic is correct) ...
        for row_index in range(self.table.rowCount()):
            match_found = False
            for col_index in range(self.table.columnCount()):
                item = self.table.item(row_index, col_index)
                widget = self.table.cellWidget(row_index, col_index)
                if item and search_text in item.text().lower():
                    match_found = True
                    break
                elif isinstance(widget, QPushButton):
                    detail_id = self.table.item(row_index, 0).data(Qt.ItemDataRole.UserRole)
                    original_remarks = self.full_data.loc[self.full_data['detail_id'] == detail_id, 'Remarks'].iloc[0]
                    if original_remarks and search_text in original_remarks.lower():
                        match_found = True
                        break
            self.table.setRowHidden(row_index, not match_found)

        # After filtering, update the summary box
        self._update_summary_box()

    # --- MODIFIED: Trigger summary update after populating table ---
    def populate_table(self, data: pd.DataFrame):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        # ... (existing population logic is correct) ...
        if data is None or data.empty:
            self.table.setSortingEnabled(True)
            self._update_summary_box()  # Update to show zeros
            return
        self.table.setRowCount(len(data))
        visible_columns = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        numeric_cols = {"Ref No", "Output QTY", "Cleaning QTY"}
        for i, row in data.iterrows():
            for j, col_name in enumerate(visible_columns):
                cell_data = row.get(col_name, '')
                if col_name == "Remarks":
                    if cell_data:
                        btn = QPushButton("View")
                        btn.setObjectName("ViewRemarksButton")
                        btn.clicked.connect(lambda _, rt=cell_data: self.show_remarks(rt))
                        self.table.setCellWidget(i, j, btn)
                    else:
                        self.table.setItem(i, j, QTableWidgetItem(""))
                elif col_name in numeric_cols:
                    item = self._create_table_item(cell_data)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(i, j, item)
                else:
                    item = QTableWidgetItem(str(cell_data))
                    self.table.setItem(i, j, item)
            first_item = self.table.item(i, 0)
            if first_item:
                first_item.setData(Qt.ItemDataRole.UserRole, row["detail_id"])

        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

        # After populating, update the summary box
        self._update_summary_box()

    # ... (all other methods remain the same) ...
    def _handle_export_to_excel(self):
        if self.export_worker and self.export_worker.isRunning():
            QMessageBox.warning(self, "Export in Progress", "An export is already running. Please wait.")
            return
        visible_df = self._get_visible_data_as_dataframe()
        if visible_df.empty:
            QMessageBox.warning(self, "No Data", "There is no data to export.");
            return
        default_filename = f"Mixer_Report_{pd.Timestamp.now().strftime('%Y-%m-%d')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel Report", default_filename, "Excel Files (*.xlsx)")
        if not file_path: return
        self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.set_text("Exporting to Excel, please wait...")
        self.export_worker = ExportWorker(visible_df, file_path)
        self.export_worker.success.connect(self._on_export_success)
        self.export_worker.error.connect(self._on_export_error)
        self.export_worker.finished.connect(self.loading_dialog.close)
        self.export_worker.finished.connect(self.export_worker.deleteLater)
        self.export_worker.start()
        self.loading_dialog.exec()

    @pyqtSlot(str)
    def _on_export_success(self, filepath: str):
        QMessageBox.information(self, "Export Successful", f"Report successfully saved to:\n{filepath}")

    @pyqtSlot(str)
    def _on_export_error(self, error_message: str):
        QMessageBox.critical(self, "Export Error", error_message)

    @pyqtSlot()
    def refresh_data(self, is_manual_refresh: bool = True):
        print("Refreshing data...")
        session = self.Session()
        try:
            self.full_data = get_mixer_report_data(session, self.current_filters)
            self.populate_table(self.full_data)
            self.filter_table_by_search(self.search_input.text())
            if is_manual_refresh:
                self.show_notification("Data successfully refreshed!")
        except Exception as e:
            QMessageBox.critical(self, "Refresh Error", f"Could not refresh report data:\n{e}")
        finally:
            session.close()

    def show_notification(self, message: str, duration_ms: int = 2000):
        self.notification_label.setText(message)
        self.anim_in = QPropertyAnimation(self.notification_label, b"maximumHeight")
        self.anim_in.setDuration(200)
        self.anim_in.setStartValue(0)
        self.anim_in.setEndValue(35)
        self.anim_in.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim_in.start()
        QTimer.singleShot(duration_ms, self.hide_notification)

    def hide_notification(self):
        self.anim_out = QPropertyAnimation(self.notification_label, b"maximumHeight")
        self.anim_out.setDuration(200)
        self.anim_out.setStartValue(35)
        self.anim_out.setEndValue(0)
        self.anim_out.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim_out.start()

    def _start_database_monitor(self):
        self.db_monitor_thread = DatabaseMonitorThread(self.Session, self)
        self.db_monitor_thread.database_changed.connect(self.on_database_changed)
        self.db_monitor_thread.start()

    def on_database_changed(self):
        print("Database change detected. Auto-refreshing table...")
        self.refresh_data(is_manual_refresh=False)

    def closeEvent(self, event):
        self.db_monitor_thread.stop()
        self.db_monitor_thread.wait()
        super().closeEvent(event)

    def _setup_shortcuts(self):
        refresh_action = QAction("Refresh Data", self)
        refresh_action.setShortcut(QKeySequence("Ctrl+R"))
        refresh_action.triggered.connect(lambda: self.refresh_data(is_manual_refresh=True))
        self.addAction(refresh_action)

    def _load_prerequisites_and_data(self):
        session = self.Session()
        try:
            active_machines = get_active_machines(session)
            self.machine_list = [m.name for m in active_machines] if active_machines is not None else []
            self.editor_initial_data = get_editor_initial_data(session)
            self.full_data = get_mixer_report_data(session, self.current_filters)
            self.populate_table(self.full_data)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            QMessageBox.critical(self, "Load Error", f"Could not load initial data:\n\n{e}\n\n{error_details}")
        finally:
            session.close()

    def load_data(self):
        self.refresh_data()

    def edit_selected_record(self):
        detail_id = self.get_id_from_selected_row()
        if not detail_id: return
        try:
            record_data = self.full_data.loc[self.full_data['detail_id'] == detail_id].iloc[0]
        except IndexError:
            QMessageBox.critical(self, "Error", "Could not find the selected record's data.");
            return
        edit_dialog = EditRecordDialog(record_data=record_data, machine_list=self.machine_list,
                                       initial_data=self.editor_initial_data, parent=self)
        edit_dialog.perform_search_requested.connect(self.on_dialog_search_requested)
        if not edit_dialog.exec(): return
        updated_data = edit_dialog.get_updated_data()
        confirm_dialog = SecureConfirmationDialog("Confirm Edit",
                                                  f"Are you sure you want to save the changes for record ID {detail_id}?",
                                                  self)
        confirm_dialog.setObjectName("SecureConfirmationDialog");
        confirm_dialog.ok_button.setObjectName("PrimaryDialogButton")
        if not confirm_dialog.exec(): return
        session = self.Session()
        try:
            update_mixer_record(session, detail_id, updated_data)
            QMessageBox.information(self, "Success", f"Record ID {detail_id} has been updated successfully.")
        except Exception as e:
            session.rollback();
            QMessageBox.critical(self, "Database Error", f"Could not update the record:\n{e}")
        finally:
            session.close()
            self.load_data()

    @pyqtSlot(object, object, str)
    def on_dialog_search_requested(self, combo_box: SmartComboBox, search_function: Callable, search_term: str):
        if self.live_search_worker and self.live_search_worker.isRunning(): return
        self.live_search_worker = LiveSearchWorker(self.Session, search_function, search_term, self)
        self.live_search_worker.results_ready.connect(combo_box.update_with_search_results)
        self.live_search_worker.finished.connect(self._on_search_finished)
        self.live_search_worker.start()

    @pyqtSlot()
    def _on_search_finished(self):
        if self.live_search_worker:
            self.live_search_worker.deleteLater()
            self.live_search_worker = None

    def setup_table(self):
        self.table.setColumnCount(17)
        headers_list = ["Date", "Ref No", "MC #", "Product Code", "Lot Number", "Formula No", "Processing Start",
                        "Processing End", "Processing Duration", "Processed By", "Output QTY", "Cleaning Start",
                        "Cleaning End", "Cleaning Duration", "Cleaning RM", "Cleaning QTY", "Remarks"]
        self.table.setHorizontalHeaderLabels(headers_list)
        self.table.setAlternatingRowColors(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        header = self.table.horizontalHeader()
        stretch_columns = {}
        for i, header_text in enumerate(headers_list):
            if header_text in stretch_columns:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def clear_filters(self):
        self.current_filters = {}
        self.search_input.clear()
        self.load_data()
        QMessageBox.information(self, "Filters Cleared", "All filters have been removed.")

    def _create_table_item(self, value):
        item = QTableWidgetItem()
        try:
            float_value = float(value)
            item.setData(Qt.ItemDataRole.DisplayRole, str(value))
            item.setData(Qt.ItemDataRole.EditRole, float_value)
        except (ValueError, TypeError):
            item.setData(Qt.ItemDataRole.DisplayRole, str(value))
        return item

    def show_remarks(self, remarks_text: str):
        dialog = RemarksViewerDialog(remarks_text, self)
        dialog.exec()

    def open_filter_dialog(self):
        dialog = FilterDialog(self.machine_list, self.editor_initial_data, self.current_filters, self)
        dialog.perform_search_requested.connect(self.on_dialog_search_requested)
        if dialog.exec():
            self.current_filters = dialog.get_filters()
            self.load_data()

    def _get_visible_data_as_dataframe(self) -> pd.DataFrame:
        visible_data = []
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                row_data = {}
                detail_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                for col, header in enumerate(headers):
                    if header == "Remarks":
                        row_data[header] = self.full_data.loc[self.full_data['detail_id'] == detail_id, 'Remarks'].iloc[
                            0]
                    else:
                        item = self.table.item(row, col)
                        row_data[header] = item.text() if item else ""
                visible_data.append(row_data)
        df = pd.DataFrame(visible_data)
        numeric_cols = {"Ref No": int, "Output QTY": float, "Cleaning QTY": float}
        for col, col_type in numeric_cols.items():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(col_type)
        return df

    def export_to_excel(self):
        export_menu = QMenu(self)
        excel_action = QAction("Export to Excel...", self)
        pdf_action = QAction("Export to PDF...", self)
        excel_action.triggered.connect(self._handle_export_to_excel)
        pdf_action.triggered.connect(self._handle_export_to_pdf)
        export_menu.addAction(excel_action)
        export_menu.addAction(pdf_action)
        export_button = self.sender()
        menu_position = export_button.mapToGlobal(export_button.rect().bottomLeft())
        export_menu.exec(menu_position)

    def _handle_export_to_pdf(self):
        QMessageBox.information(self, "Coming Soon", "PDF export functionality will be added in a future update.")

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item: return
        menu = QMenu()
        edit_action = menu.addAction("Edit Record...")
        delete_action = menu.addAction("Delete Record...")
        action = menu.exec(self.table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_record()
        elif action == delete_action:
            self.delete_selected_record()

    def get_id_from_selected_row(self) -> int | None:
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select a row to perform this action.")
            return None
        return self.table.item(selected_rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def delete_selected_record(self):
        detail_id = self.get_id_from_selected_row()
        if not detail_id: return
        confirm_dialog = SecureConfirmationDialog("Confirm Deletion",
                                                  f"You are about to permanently delete record with ID {detail_id}. This cannot be undone.",
                                                  self)
        confirm_dialog.setObjectName("SecureConfirmationDialog")
        confirm_dialog.ok_button.setObjectName("PrimaryDialogButton")
        if not confirm_dialog.exec(): return
        session = self.Session()
        try:
            delete_mixer_record(session, detail_id)
            QMessageBox.information(self, "Success", f"Record ID {detail_id} has been deleted.")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Database Error", f"Could not delete the record:\n{e}")
        finally:
            session.close()
            self.load_data()

    def open_restore_dialog(self):
        session = self.Session()
        try:
            deleted_data = get_deleted_mixer_records(session)
            if deleted_data.empty:
                QMessageBox.information(self, "No Records", "There are no deleted records to restore.");
                return
            dialog = RestoreDialog(deleted_data, self)
            if not dialog.exec(): return
            ids_to_restore = dialog.get_selected_ids()
            if ids_to_restore:
                restore_mixer_records(session, ids_to_restore)
                QMessageBox.information(self, "Success", f"{len(ids_to_restore)} record(s) have been restored.")
                self.load_data()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open restore dialog:\n{e}")
        finally:
            session.close()