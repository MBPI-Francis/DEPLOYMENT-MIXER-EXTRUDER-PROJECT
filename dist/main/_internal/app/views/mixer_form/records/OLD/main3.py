# app/views/mixer_records/main.py

import os
import time
from typing import Type, Callable
from datetime import timedelta

from PyQt6.QtGui import QAction, QKeySequence
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu, QMessageBox,
    QFileDialog, QLineEdit, QLabel, QDialog, QProgressBar,
    QGroupBox, QGridLayout
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


# --- Worker and Dialog classes (unchanged) ---
class DatabaseMonitorThread(QThread):
    database_changed = pyqtSignal()

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
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Processing...")
        self.setModal(True)
        self.setFixedSize(300, 100)
        layout = QVBoxLayout(self)
        self.label = QLabel("Please wait...", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 0)
        layout.addWidget(self.label)
        layout.addWidget(self.progress_bar)

    def set_text(self, text: str):
        self.label.setText(text)


class MixerRecordsView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory

        # --- MODIFICATION: Use a list for efficient appends ---
        self.data_frames = []
        self.full_data = pd.DataFrame()

        self.machine_list = []
        self.current_filters = {}
        self.editor_initial_data = {}

        self.live_search_worker = None
        self.export_worker = None

        # --- State variables for lazy loading ---
        self.PAGE_SIZE = 100
        self.current_offset = 0
        self._is_loading_more = False
        self._all_data_loaded = False

        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._load_prerequisites()
        self._start_database_monitor()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        top_bar_layout = QHBoxLayout()

        self.search_input = QLineEdit(placeholderText="Search all loaded columns...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(300)
        self.refresh_button = QPushButton("Refresh", icon=qta.icon("fa5s.sync-alt"), objectName="ActionButton",
                                          toolTip="Refresh the data from the database (Ctrl+R)")
        self.filter_button = QPushButton("Filter Records...", objectName="ActionButton")
        self.clear_filters_button = QPushButton("Clear Filters", objectName="ActionButton")
        self.restore_button = QPushButton("Restore Records...", objectName="ActionButton")
        self.export_button = QPushButton("Export...", objectName="ActionButton")

        top_bar_layout.addWidget(self.search_input)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.refresh_button)
        top_bar_layout.addWidget(self.filter_button)
        top_bar_layout.addWidget(self.clear_filters_button)
        top_bar_layout.addWidget(self.restore_button)
        top_bar_layout.addWidget(self.export_button)

        self.notification_label = QLabel(objectName="NotificationLabel", alignment=Qt.AlignmentFlag.AlignCenter)
        self.notification_label.setFixedHeight(0)
        self.notification_label.setStyleSheet(
            "QLabel#NotificationLabel { background-color: #28a745; color: white; font-weight: bold; font-size: 10pt; padding: 8px; }")

        self.table = QTableWidget()
        self.setup_table()

        self.summary_box = self._create_summary_box()

        main_layout.addLayout(top_bar_layout)
        main_layout.addWidget(self.table, 1)
        main_layout.addWidget(self.summary_box)
        main_layout.addWidget(self.notification_label)

        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f: self.setStyleSheet(f.read())

    def _connect_signals(self):
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)
        self.search_input.textChanged.connect(self.filter_table_by_search)
        self.refresh_button.clicked.connect(lambda: self.refresh_data(is_manual_refresh=True))
        self.filter_button.clicked.connect(self.open_filter_dialog)
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.restore_button.clicked.connect(self.open_restore_dialog)
        self.export_button.clicked.connect(self.export_to_excel)

    def showEvent(self, event):
        """Lazy-loads data the first time the widget is shown."""
        super().showEvent(event)
        if not hasattr(self, '_initial_load_done'):
            self._initial_load_done = True
            self.refresh_data(is_manual_refresh=False)

    def refresh_data(self, is_manual_refresh: bool = True):
        """Resets the view and loads the first page of data."""
        self.current_offset = 0
        self.data_frames.clear()
        self._all_data_loaded = False
        self.table.setRowCount(0)
        self._update_summary_box()
        self._load_more_data()
        if is_manual_refresh:
            self.show_notification("Data successfully refreshed!")

    def _on_scroll(self, value):
        """Triggers loading more data when the scrollbar hits the bottom."""
        scrollbar = self.table.verticalScrollBar()
        if value == scrollbar.maximum() and not self._is_loading_more and not self._all_data_loaded:
            self._load_more_data()

    def _load_more_data(self):
        """Fetches the next page of records and appends them."""
        if self._is_loading_more: return
        self._is_loading_more = True

        print(f"Loading records... (offset: {self.current_offset})")
        session = self.Session()
        try:
            new_data = get_mixer_report_data(session, self.current_filters, offset=self.current_offset,
                                             limit=self.PAGE_SIZE)

            if new_data.empty or len(new_data) < self.PAGE_SIZE:
                self._all_data_loaded = True
                print("All records have been loaded.")

            if not new_data.empty:
                self.data_frames.append(new_data)
                self.full_data = pd.concat(self.data_frames, ignore_index=True)
                self._append_to_table(new_data)
                self.current_offset += len(new_data)
                self._update_summary_box()

        except Exception as e:
            QMessageBox.critical(self, "Load More Error", f"Could not load more records:\n{e}")
        finally:
            session.close()
            self._is_loading_more = False

    # def _append_to_table(self, data: pd.DataFrame):
    #     """Efficiently appends a DataFrame to the end of the QTableWidget."""
    #     self.table.setUpdatesEnabled(False)
    #     self.table.setSortingEnabled(False)
    #
    #     start_row = self.table.rowCount()
    #     self.table.setRowCount(start_row + len(data))
    #
    #     headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
    #     numeric_cols = {"Ref No", "Output QTY", "Cleaning QTY"}
    #
    #     for i, row in enumerate(data.itertuples(index=False), start=start_row):
    #         for j, col_name in enumerate(headers):
    #             # FIX: Account for mangled names from itertuples
    #             attr_name = col_name.replace(' ', '_').replace('#', '_no')
    #             cell_data = getattr(row, attr_name, '')
    #
    #             if col_name == "Remarks":
    #                 if cell_data:
    #                     btn = QPushButton("View", objectName="ViewRemarksButton")
    #                     btn.clicked.connect(lambda _, rt=cell_data: self.show_remarks(rt))
    #                     self.table.setCellWidget(i, j, btn)
    #             elif col_name in numeric_cols:
    #                 item = self._create_table_item(cell_data)
    #                 item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    #                 self.table.setItem(i, j, item)
    #             else:
    #                 item = QTableWidgetItem(str(cell_data))
    #                 self.table.setItem(i, j, item)
    #
    #         first_item = self.table.item(i, 0)
    #         if first_item:
    #             first_item.setData(Qt.ItemDataRole.UserRole, row.detail_id)
    #
    #     self.table.setSortingEnabled(True)
    #     self.table.setUpdatesEnabled(True)

    def _append_to_table(self, data: pd.DataFrame):
        """
        Efficiently appends a DataFrame to the end of the QTableWidget.
        This version correctly handles all column names.
        """
        # Disable UI updates for a massive performance boost during population
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)

        start_row = self.table.rowCount()
        self.table.setRowCount(start_row + len(data))

        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        numeric_cols = {"Ref No", "Output QTY", "Cleaning QTY"}

        # Use itertuples for performance. index=False is crucial.
        for i, row in enumerate(data.itertuples(index=False), start=start_row):
            for j, col_name in enumerate(headers):

                # --- THIS IS THE DEFINITIVE FIX ---
                # Access data by its numerical index (j) from the tuple.
                # This is faster and completely avoids the name-mangling problem.
                cell_data = row[j]
                # --- END FIX ---

                if col_name == "Remarks":
                    if cell_data:
                        btn = QPushButton("View", objectName="ViewRemarksButton")
                        btn.clicked.connect(lambda _, rt=cell_data: self.show_remarks(rt))
                        self.table.setCellWidget(i, j, btn)
                elif col_name in numeric_cols:
                    item = self._create_table_item(cell_data)
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    self.table.setItem(i, j, item)
                else:
                    # Ensure all data is converted to a string for display
                    item = QTableWidgetItem(str(cell_data) if pd.notna(cell_data) else "")
                    self.table.setItem(i, j, item)

            # Set the hidden detail_id for the row
            first_item = self.table.item(i, 0)
            if first_item:
                # We can still access detail_id by name as it's a valid attribute name
                first_item.setData(Qt.ItemDataRole.UserRole, row.detail_id)

        # Re-enable UI updates and sorting now that the work is done
        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)

    def _load_prerequisites(self):
        """Loads small, essential data at startup."""
        session = self.Session()
        try:
            active_machines = get_active_machines(session)
            self.machine_list = [m.name for m in active_machines] if active_machines is not None else []
            self.editor_initial_data = get_editor_initial_data(session)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not load prerequisites:\n{e}")
        finally:
            session.close()

    def setup_table(self):
        """Configures the main table's appearance and behavior."""
        headers = ["Date", "Ref No", "MC #", "Product Code", "Lot Number", "Formula No", "Processing Start",
                   "Processing End", "Processing Duration", "Processed By", "Output QTY", "Cleaning Start",
                   "Cleaning End", "Cleaning Duration", "Cleaning RM", "Cleaning QTY", "Remarks"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        header = self.table.horizontalHeader()
        stretch_columns = {"Product Code", "Lot Number", "Cleaning RM"}
        for i, h in enumerate(headers):
            mode = QHeaderView.ResizeMode.Stretch if h in stretch_columns else QHeaderView.ResizeMode.Interactive
            header.setSectionResizeMode(i, mode)

    def _update_summary_box(self):
        """Calculates and displays summaries based on ALL loaded data."""
        df_to_summarize = self.full_data

        if df_to_summarize.empty:
            self.visible_records_label.setText("0")
            self.total_output_label.setText("0.00");
            self.avg_output_label.setText("0.00")
            self.total_cleaning_qty_label.setText("0.00");
            self.avg_cleaning_qty_label.setText("0.00")
            self.total_proc_duration_label.setText("0.00");
            self.total_clean_duration_label.setText("0.00")
            return

        self.visible_records_label.setText(f"{len(df_to_summarize):,}")
        total_output = df_to_summarize['Output QTY'].sum()
        avg_output = df_to_summarize['Output QTY'].mean()
        total_cleaning = df_to_summarize['Cleaning QTY'].sum()
        avg_cleaning = df_to_summarize['Cleaning QTY'].mean()

        total_proc_delta = timedelta()
        for duration_str in df_to_summarize['Processing Duration'].dropna().astype(str):
            if ':' in duration_str:
                try:
                    hours, minutes = map(int, duration_str.split(':'))
                    total_proc_delta += timedelta(hours=hours, minutes=minutes)
                except (ValueError, TypeError):
                    continue

        total_clean_delta = timedelta()
        for duration_str in df_to_summarize['Cleaning Duration'].dropna().astype(str):
            if ':' in duration_str:
                try:
                    hours, minutes = map(int, duration_str.split(':'))
                    total_clean_delta += timedelta(hours=hours, minutes=minutes)
                except (ValueError, TypeError):
                    continue

        proc_decimal_hours = total_proc_delta.total_seconds() / 3600
        clean_decimal_hours = total_clean_delta.total_seconds() / 3600

        self.total_output_label.setText(f"{total_output:,.2f}")
        self.avg_output_label.setText(f"{avg_output:,.2f}")
        self.total_cleaning_qty_label.setText(f"{total_cleaning:,.2f}")
        self.avg_cleaning_qty_label.setText(f"{avg_cleaning:,.2f}")
        self.total_proc_duration_label.setText(f"{proc_decimal_hours:.2f}")
        self.total_clean_duration_label.setText(f"{clean_decimal_hours:.2f}")

    def filter_table_by_search(self, search_text: str):
        """Client-side search that operates on visible rows."""
        search_text = search_text.lower()
        for row_index in range(self.table.rowCount()):
            match_found = any(
                self.table.item(row_index, col) and search_text in self.table.item(row_index, col).text().lower() for
                col in range(self.table.columnCount()))
            self.table.setRowHidden(row_index, not match_found)

    def _handle_export_to_excel(self):
        """Exports all loaded data to an Excel file using a background worker."""
        if self.export_worker and self.export_worker.isRunning():
            QMessageBox.warning(self, "Export in Progress", "An export is already running. Please wait.")
            return

        df_to_export = self.full_data
        if df_to_export.empty:
            QMessageBox.warning(self, "No Data", "There is no data to export.");
            return

        default_filename = f"Mixer_Report_{pd.Timestamp.now().strftime('%Y-%m-%d')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel Report", default_filename, "Excel Files (*.xlsx)")
        if not file_path: return

        self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.set_text("Exporting to Excel, please wait...")
        self.export_worker = ExportWorker(df_to_export, file_path)
        self.export_worker.success.connect(self._on_export_success)
        self.export_worker.error.connect(self._on_export_error)
        self.export_worker.finished.connect(self.loading_dialog.close)
        self.export_worker.finished.connect(self.export_worker.deleteLater)
        self.export_worker.start()
        self.loading_dialog.exec()

    def load_data(self):
        self.refresh_data(is_manual_refresh=True)

    def clear_filters(self):
        self.current_filters = {}
        self.search_input.clear()
        self.refresh_data(is_manual_refresh=False)
        QMessageBox.information(self, "Filters Cleared", "All filters have been removed.")

    def open_filter_dialog(self):
        dialog = FilterDialog(self.machine_list, self.editor_initial_data, self.current_filters, self)
        dialog.perform_search_requested.connect(self.on_dialog_search_requested)
        if dialog.exec():
            self.current_filters = dialog.get_filters()
            self.refresh_data(is_manual_refresh=False)

    def _create_summary_box(self):
        summary_box = QGroupBox()
        summary_box.setObjectName("SummaryBox")
        layout = QGridLayout(summary_box)
        layout.setSpacing(10)
        self.visible_records_label = QLabel("0")
        self.total_output_label = QLabel("0.00");
        self.avg_output_label = QLabel("0.00")
        self.total_cleaning_qty_label = QLabel("0.00");
        self.avg_cleaning_qty_label = QLabel("0.00")
        self.total_proc_duration_label = QLabel("0.00");
        self.total_clean_duration_label = QLabel("0.00")
        all_value_labels = [self.visible_records_label, self.total_output_label, self.avg_output_label,
                            self.total_cleaning_qty_label, self.avg_cleaning_qty_label, self.total_proc_duration_label,
                            self.total_clean_duration_label]
        for label in all_value_labels:
            label.setObjectName("SummaryValueLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(QLabel("<b>Total Output Qty:</b>"), 0, 0);
        layout.addWidget(self.total_output_label, 0, 1)
        layout.addWidget(QLabel("<b>Average Output Qty:</b>"), 1, 0);
        layout.addWidget(self.avg_output_label, 1, 1)
        layout.addWidget(QLabel("<b>Total Cleaning Qty:</b>"), 0, 3);
        layout.addWidget(self.total_cleaning_qty_label, 0, 4)
        layout.addWidget(QLabel("<b>Average Cleaning Qty:</b>"), 1, 3);
        layout.addWidget(self.avg_cleaning_qty_label, 1, 4)
        layout.addWidget(QLabel("<b>Total Processing (Decimal Hours):</b>"), 0, 6);
        layout.addWidget(self.total_proc_duration_label, 0, 7)
        layout.addWidget(QLabel("<b>Total Cleaning (Decimal Hours):</b>"), 1, 6);
        layout.addWidget(self.total_clean_duration_label, 1, 7)
        layout.addWidget(QLabel("<b>Loaded Records:</b>"), 0, 9);
        layout.addWidget(self.visible_records_label, 0, 10)
        layout.setColumnStretch(2, 1);
        layout.setColumnStretch(5, 1);
        layout.setColumnStretch(8, 1)
        return summary_box

    def _create_table_item(self, value):
        item = QTableWidgetItem()
        try:
            item.setData(Qt.ItemDataRole.DisplayRole, f"{float(value):,}" if value else "0")
        except (ValueError, TypeError):
            item.setData(Qt.ItemDataRole.DisplayRole, str(value))
        return item

    def show_remarks(self, remarks_text: str):
        dialog = RemarksViewerDialog(remarks_text, self)
        dialog.exec()

    @pyqtSlot(str)
    def _on_export_success(self, filepath: str):
        QMessageBox.information(self, "Export Successful", f"Report successfully saved to:\n{filepath}")

    @pyqtSlot(str)
    def _on_export_error(self, error_message: str):
        QMessageBox.critical(self, "Export Error", error_message)

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
            self.refresh_data(is_manual_refresh=False)

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
                self.refresh_data(is_manual_refresh=False)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open restore dialog:\n{e}")
        finally:
            session.close()

    def _start_database_monitor(self):
        self.db_monitor_thread = DatabaseMonitorThread(self.Session, self)
        self.db_monitor_thread.database_changed.connect(self.on_database_changed)
        self.db_monitor_thread.start()

    def _setup_shortcuts(self):
        refresh_action = QAction("Refresh Data", self)
        refresh_action.setShortcut(QKeySequence("Ctrl+R"))
        refresh_action.triggered.connect(lambda: self.refresh_data(is_manual_refresh=True))
        self.addAction(refresh_action)

    def on_database_changed(self):
        print("Database change detected. Auto-refreshing table...")
        self.refresh_data(is_manual_refresh=False)

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
            self.refresh_data(is_manual_refresh=False)