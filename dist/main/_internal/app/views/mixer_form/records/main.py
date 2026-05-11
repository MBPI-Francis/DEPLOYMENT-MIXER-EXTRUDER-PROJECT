# app/views/mixer_records/main.py
import math
import os
import time
from typing import Type, Callable
from datetime import timedelta

from PyQt6.QtGui import QAction, QKeySequence, QIntValidator
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu, QMessageBox,
    QFileDialog, QLineEdit, QLabel, QDialog, QProgressBar,
    QGroupBox, QGridLayout, QComboBox, QFrame
)


from PyQt6.QtCore import Qt, pyqtSlot, QThread, pyqtSignal, QPropertyAnimation, QTimer, QEasingCurve

import pandas as pd
import qtawesome as qta

from app.widgets.smart_combo_box import SmartComboBox
from app.widgets.workers import LiveSearchWorker
from .exporter import ExcelExporter
from .ops import (
    delete_mixer_record, get_mixer_report_data, get_deleted_mixer_records, restore_mixer_records,
    update_mixer_record, get_editor_initial_data, get_mixer_record_count, get_mixer_summary_aggregates
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


class DataLoaderWorker(QThread):
    """Handles all DB fetching in background to prevent UI lag."""
    finished = pyqtSignal(int, pd.DataFrame, dict)  # total_count, table_data, summary_stats
    error = pyqtSignal(str)

    def __init__(self, session_factory, filters, offset, limit):
        super().__init__()
        self.session_factory = session_factory
        self.filters = filters
        self.offset = offset
        self.limit = limit

    def run(self):
        session = self.session_factory()
        try:
            # 1. Get total count
            total = get_mixer_record_count(session, self.filters)

            # 2. Get Page Data
            df = get_mixer_report_data(session, self.filters, self.offset, self.limit)

            # 3. Get SQL Aggregates for Summary Box
            stats = get_mixer_summary_aggregates(session, self.filters)

            self.finished.emit(total, df, stats)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            session.close()

class MixerRecordsView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.data_frames = []
        self.data_loader_worker = None
        self.loading_dialog = None
        self.full_data = pd.DataFrame()
        self.machine_list = []
        self.current_filters = {}
        self.editor_initial_data = {}
        self.live_search_worker = None
        self.export_worker = None
        self.RECORDS_PER_PAGE_OPTIONS = ["50", "100", "250", "500", "1000"]
        self.PAGE_SIZE = 200
        self.records_per_page = 100
        self.current_offset = 0
        self._is_loading_more = False
        self._all_data_loaded = False
        self._setup_ui()
        self._connect_signals()
        self._setup_shortcuts()
        self._load_prerequisites()
        self._start_database_monitor()

        # --- INITIALIZE PAGINATION STATE HERE ---
        self.current_page = 1
        self.page_size = 100  # Default page size
        self.total_records = 0
        # ----------------------------------------

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        top_bar_layout = QHBoxLayout()

        # --- NEW: Enhanced Search Bar Container ---
        search_container = QHBoxLayout()
        search_container.setSpacing(5)

        # Scoped Search Dropdown
        self.search_scope_combo = SmartComboBox()
        self.search_scope_combo.set_mandatory(False)
        self.search_scope_combo.addItems([
            "All Columns",
            "Product Code",
            "Lot Number",
            "Ref No",
            "Machine",
            "Processed By"
        ])
        self.search_scope_combo.setFixedWidth(120)

        self.search_input = QLineEdit(placeholderText="Enter search text...")
        self.search_input.setFixedWidth(250)

        self.search_button = QPushButton(icon=qta.icon("fa5s.search"), objectName="ActionButton")

        search_container.addWidget(self.search_scope_combo)
        search_container.addWidget(self.search_input)
        search_container.addWidget(self.search_button)
        # --- END SEARCH BAR ---



        self.refresh_button = QPushButton("Refresh", icon=qta.icon("fa5s.sync-alt"), objectName="ActionButton",
                                          toolTip="Refresh the data from the database (Ctrl+R)")
        self.filter_button = QPushButton("Filter Records...", objectName="ActionButton")
        self.clear_filters_button = QPushButton("Clear Filters", objectName="ActionButton")
        self.restore_button = QPushButton("Restore Records...", objectName="ActionButton")
        self.export_button = QPushButton("Export List", objectName="ActionButton")

        self.pagination_container = QWidget()
        self.pagination_container.setObjectName("paginationWidget")
        pagination_layout = QHBoxLayout(self.pagination_container)

        self.records_per_page_combo = SmartComboBox()
        self.records_per_page_combo.addItems(self.RECORDS_PER_PAGE_OPTIONS)
        self.records_per_page_combo.setCurrentText(str(self.records_per_page))
        self.records_per_page_combo.setEditable(True)
        self.records_per_page_combo.setValidator(QIntValidator(1, 999999))
        self.records_per_page_combo.setFixedWidth(80)

        pagination_layout.addWidget(QLabel("Records per page:"))
        pagination_layout.addWidget(self.records_per_page_combo)
        pagination_layout.addStretch()

        self.first_page_btn = QPushButton("<< First")
        self.prev_page_btn = QPushButton("< Prev")
        self.page_label = QLabel("Page 1 of 1")
        self.next_page_btn = QPushButton("Next >")
        self.last_page_btn = QPushButton("Last >>")

        pagination_layout.addWidget(self.first_page_btn)
        pagination_layout.addWidget(self.prev_page_btn)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_page_btn)
        pagination_layout.addWidget(self.last_page_btn)


        top_bar_layout.addLayout(search_container)
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
        main_layout.addWidget(self.pagination_container)  # Add the pagination widget
        main_layout.addWidget(self.notification_label)
        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f: self.setStyleSheet(f.read())


    def _connect_signals(self):
        # NEW: Manual Search Trigger
        self.search_button.clicked.connect(self.initiate_search)
        self.search_input.returnPressed.connect(self.initiate_search)  # Hitting Enter key

        # We can also search immediately when the user changes the dropdown scope
        self.search_scope_combo.currentIndexChanged.connect(self.initiate_search)


        self.refresh_button.clicked.connect(lambda: self.refresh_data(is_manual_refresh=True))
        self.filter_button.clicked.connect(self.open_filter_dialog)
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.restore_button.clicked.connect(self.open_restore_dialog)
        self.export_button.clicked.connect(self.export_to_excel)

        self.first_page_btn.clicked.connect(self.go_to_first_page)
        self.last_page_btn.clicked.connect(self.go_to_last_page)
        self.prev_page_btn.clicked.connect(self.prev_page)
        self.next_page_btn.clicked.connect(self.next_page)

        # # Using currentTextChanged to handle the editable combo box
        # self.records_per_page_combo.currentTextChanged.connect(self.change_page_size)

        self.records_per_page_combo.activated.connect(self.change_page_size)

        # 2. Trigger when the user types a value and hits the ENTER key
        self.records_per_page_combo.lineEdit().returnPressed.connect(self.change_page_size)


    def go_to_first_page(self):
        self.current_page = 1
        self.refresh_data(is_manual_refresh=False)

    def go_to_last_page(self):
        total_pages = math.ceil(self.total_records / self.records_per_page)
        self.current_page = max(1, total_pages)
        self.refresh_data(is_manual_refresh=False)

    def next_page(self):
        total_pages = math.ceil(self.total_records / self.records_per_page)
        if self.current_page < total_pages:
            self.current_page += 1
            self.refresh_data(is_manual_refresh=False)

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.refresh_data(is_manual_refresh=False)

    def change_page_size(self):
        """
        Triggered only on selection or pressing Enter.
        Prevents the infinite loading loop.
        """
        text = self.records_per_page_combo.currentText()
        try:
            val = int(text)
            if val > 0:
                self.records_per_page = val
                self.current_page = 1  # Reset to page 1
                self.refresh_data(is_manual_refresh=False)
            else:
                # Reset to default if user enters 0 or negative
                self.records_per_page_combo.setCurrentText(str(self.records_per_page))
        except ValueError:
            # Reset to previous valid value if user enters text
            self.records_per_page_combo.setCurrentText(str(self.records_per_page))



    def initiate_search(self):
        """Triggered by button, Enter key, or dropdown change."""
        term = self.search_input.text().strip()
        scope = self.search_scope_combo.currentText()

        if term:
            self.current_filters["search_term"] = term
            self.current_filters["search_field"] = scope
        else:
            # Clear search filters if input is empty
            self.current_filters.pop("search_term", None)
            self.current_filters.pop("search_field", None)

        self.refresh_data(is_manual_refresh=False)

        if term:
            self.show_notification(f"Searching {scope} for: '{term}'")


    def showEvent(self, event):
        super().showEvent(event)
        if not hasattr(self, '_initial_load_done'):
            self._initial_load_done = True
            self.refresh_data(is_manual_refresh=False)


    # def refresh_data(self, is_manual_refresh: bool = True):
    #     if self.data_loader_worker and self.data_loader_worker.isRunning():
    #         return
    #
    #     # Show Loading Dialog to prevent user from clicking things while loading
    #     self.loading_dialog = LoadingDialog(self)
    #     self.loading_dialog.set_text("Loading records...")
    #     self.loading_dialog.show()
    #
    #     offset = (self.current_page - 1) * self.records_per_page
    #
    #     self.data_loader_worker = DataLoaderWorker(
    #         self.Session, self.current_filters, offset, self.records_per_page
    #     )
    #     self.data_loader_worker.finished.connect(self.on_data_loaded)
    #     self.data_loader_worker.error.connect(self.on_load_error)
    #     self.data_loader_worker.finished.connect(self.loading_dialog.close)
    #     self.data_loader_worker.start()

    def refresh_data(self, is_manual_refresh: bool = True):
        # 1. Prevent overlapping loads
        if self.data_loader_worker and self.data_loader_worker.isRunning():
            return

        # 2. Setup Loading Dialog
        self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.set_text("Fetching records...")

        # 3. Only show the dialog if it's a manual refresh or a large change
        # This prevents the 'blinking' for small pagination jumps
        self.loading_dialog.show()

        offset = (self.current_page - 1) * self.records_per_page

        self.data_loader_worker = DataLoaderWorker(
            self.Session, self.current_filters, offset, self.records_per_page
        )
        self.data_loader_worker.finished.connect(self.on_data_loaded)
        self.data_loader_worker.error.connect(self.on_load_error)

        # Ensure the dialog closes when the worker finishes
        self.data_loader_worker.finished.connect(self.loading_dialog.close)

        self.data_loader_worker.start()

    def on_data_loaded(self, total, df, stats):
        self.total_records = total

        # 1. Update Pagination UI
        total_pages = math.ceil(self.total_records / self.records_per_page) if self.total_records > 0 else 1
        self.page_label.setText(f"Page {self.current_page} of {total_pages}")
        self.first_page_btn.setEnabled(self.current_page > 1)
        self.prev_page_btn.setEnabled(self.current_page > 1)
        self.next_page_btn.setEnabled(self.current_page < total_pages)
        self.last_page_btn.setEnabled(self.current_page < total_pages)

        # 2. Update Table
        self.table.setRowCount(0)
        self.full_data = df
        self._append_to_table(df)

        # 3. Update Summary Box with the pre-calculated stats from DB
        self._apply_summary_stats(stats)

    def _apply_summary_stats(self, stats):
        """Processes raw seconds from DB into HH:MM and Decimal for the UI."""

        def format_time(total_seconds):
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            decimal = hours + (minutes / 60)
            return f"{hours}:{minutes:02}", f"{decimal:.2f}"

        proc_str, proc_dec = format_time(stats["proc_seconds"])
        clean_str, clean_dec = format_time(stats["clean_seconds"])

        self.total_output_label.setText(f"{stats['total_output']:,.2f}")
        self.total_cleaning_qty_label.setText(f"{stats['total_cleaning']:,.2f}")
        self.total_proc_duration_label.setText(proc_str)
        self.total_clean_duration_label.setText(clean_str)
        self.proc_excel_decimal_label.setText(proc_dec)
        self.clean_excel_decimal_label.setText(clean_dec)
        self.visible_records_label.setText(f"{self.total_records:,}")

    def on_load_error(self, message):
        if self.loading_dialog: self.loading_dialog.close()
        QMessageBox.critical(self, "Server Error", f"Failed to fetch data:\n{message}")


    def _load_all_filtered_data(self):
        """Loads all data matching the current filters in one go."""
        if self._is_loading_more: return
        self._is_loading_more = True
        self._all_data_loaded = True  # Since we load all, no more pages

        session = self.Session()
        try:
            all_data = get_mixer_report_data(session, self.current_filters)
            if not all_data.empty:
                self.data_frames.append(all_data)
                self.full_data = pd.concat(self.data_frames, ignore_index=True)
                self._append_to_table(all_data)
                self._update_summary_box()
        finally:
            session.close()
            self._is_loading_more = False

    def _on_scroll(self, value):
        scrollbar = self.table.verticalScrollBar()
        if value == scrollbar.maximum() and not self._is_loading_more and not self._all_data_loaded:
            self._load_more_data()

    def _load_more_data(self):
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

    def _append_to_table(self, data: pd.DataFrame):
        self.table.setUpdatesEnabled(False)
        self.table.setSortingEnabled(False)

        start_row = self.table.rowCount()
        self.table.setRowCount(start_row + len(data))

        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        numeric_cols = {"Ref No", "Output QTY", "Cleaning QTY"}

        # Create a mapping from UI header to DataFrame column name once
        col_map = {header: header for header in headers}

        for i, row in enumerate(data.iterrows(), start=start_row):
            index, row_data = row
            for j, col_name in enumerate(headers):
                cell_data = row_data.get(col_map[col_name], '')

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
                    item = QTableWidgetItem(str(cell_data) if pd.notna(cell_data) else "")
                    self.table.setItem(i, j, item)

            first_item = self.table.item(i, 0)
            if first_item:
                first_item.setData(Qt.ItemDataRole.UserRole, row_data["detail_id"])

        self.table.setSortingEnabled(True)
        self.table.setUpdatesEnabled(True)

    def _create_table_item(self, value):
        item = QTableWidgetItem()
        display_value = ""
        if value is None or (isinstance(value, float) and math.isnan(value)):
            display_value = "0"
        else:
            try:
                if float(value) == int(float(value)):
                    display_value = f"{int(float(value)):,}"
                else:
                    display_value = f"{float(value):,.2f}"
            except (ValueError, TypeError):
                display_value = str(value)
        item.setData(Qt.ItemDataRole.DisplayRole, display_value)
        return item

    def _load_prerequisites(self):
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
        headers = ["Date Compounded",
                   "Ref No",
                   "MC #",
                   "Product Code",
                   "Lot Number",
                   "Formula No",
                   "Processing Start",
                   "Processing End",
                   "Processing Duration",
                   "Output QTY (kg)",
                   "Cleaning RM",
                   "Cleaning QTY (kg)",
                   "Cleaning Start",
                   "Cleaning End",
                   "Cleaning Duration",
                   "Processed By",
                   "Remarks"]
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        header = self.table.horizontalHeader()
        stretch_columns = {}
        for i, h in enumerate(headers):
            mode = QHeaderView.ResizeMode.Stretch if h in stretch_columns else QHeaderView.ResizeMode.ResizeToContents
            header.setSectionResizeMode(i, mode)

    def filter_table_by_search(self, search_text: str):
        search_text = search_text.lower()
        for row_index in range(self.table.rowCount()):
            match_found = any(
                self.table.item(row_index, col) and search_text in self.table.item(row_index, col).text().lower() for
                col in range(self.table.columnCount()))
            self.table.setRowHidden(row_index, not match_found)

    def _handle_export_to_excel(self):
        if self.export_worker and self.export_worker.isRunning():
            QMessageBox.warning(self, "Export in Progress", "An export is already running.")
            return

        # 1. Fetch ALL filtered data from the database (ignoring pagination)
        session = self.Session()
        try:
            # We call the same ops function but WITHOUT offset and limit
            df_to_export = get_mixer_report_data(session, self.current_filters, offset=None, limit=None)
        except Exception as e:
            QMessageBox.critical(self, "Export Data Error", f"Could not fetch data for export:\n{e}")
            return
        finally:
            session.close()

        if df_to_export.empty:
            QMessageBox.warning(self, "No Data", "There is no data to export.")
            return

        # 2. Get file path
        default_filename = f"Mixer_Report_{pd.Timestamp.now().strftime('%Y-%m-%d')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel Report", default_filename, "Excel Files (*.xlsx)")
        if not file_path: return

        # 3. Start the worker
        self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.set_text("Exporting ALL filtered records, please wait...")
        self.export_worker = ExportWorker(df_to_export, file_path)
        self.export_worker.success.connect(self._on_export_success)
        self.export_worker.error.connect(self._on_export_error)
        self.export_worker.finished.connect(self.loading_dialog.close)
        self.export_worker.start()
        self.loading_dialog.exec()

    def load_data(self):
        self.refresh_data(is_manual_refresh=True)

    def clear_filters(self):
        if not self.current_filters: return  # Do nothing if no filters are active
        self.current_filters = {}
        self.search_input.clear()
        self.search_scope_combo.setCurrentIndex(0)  # Reset to "All Columns"
        self.refresh_data(is_manual_refresh=False)
        QMessageBox.information(self, "Filters Cleared", "All filters have been removed.")

    def open_filter_dialog(self):
        dialog = FilterDialog(self.machine_list, self.editor_initial_data, self.current_filters, self)
        dialog.perform_search_requested.connect(self.on_dialog_search_requested)
        if dialog.exec():
            self.current_filters = dialog.get_filters()
            self.refresh_data(is_manual_refresh=False)



    # --- THIS IS THE NEW UI FOR THE SUMMARY BOX ---
    def _create_summary_box(self) -> QGroupBox:
        """Creates the GroupBox container with the 6 required summary fields."""
        summary_box = QGroupBox()
        summary_box.setObjectName("SummaryBox")

        layout = QGridLayout(summary_box)
        layout.setSpacing(10)

        # Create all the required value labels
        self.visible_records_label = QLabel("0")
        self.total_output_label = QLabel("0.00")
        self.total_cleaning_qty_label = QLabel("0.00")
        self.total_proc_duration_label = QLabel("0:00")
        self.total_clean_duration_label = QLabel("0:00")
        self.proc_excel_decimal_label = QLabel("0.00")
        self.clean_excel_decimal_label = QLabel("0.00")

        all_value_labels = [
            self.visible_records_label,
            self.total_output_label, self.total_cleaning_qty_label,
            self.total_proc_duration_label, self.total_clean_duration_label,
            self.proc_excel_decimal_label, self.clean_excel_decimal_label
        ]
        for label in all_value_labels:
            label.setObjectName("SummaryValueLabel")
            label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # Layout the 6 fields in a 2-row, 3-column grid
        layout.addWidget(QLabel("<b>Total Output Qty:</b>"), 0, 0)
        layout.addWidget(self.total_output_label, 0, 1)

        layout.addWidget(QLabel("<b>Total Cleaning Qty:</b>"), 1, 0)
        layout.addWidget(self.total_cleaning_qty_label, 1, 1)

        layout.addWidget(QLabel("<b>Total Processing Duration:</b>"), 0, 3)
        layout.addWidget(self.total_proc_duration_label, 0, 4)

        layout.addWidget(QLabel("<b>Total Cleaning Duration:</b>"), 1, 3)
        layout.addWidget(self.total_clean_duration_label, 1, 4)

        layout.addWidget(QLabel("<b>Processing Duration (Decimal):</b>"), 0, 6)
        layout.addWidget(self.proc_excel_decimal_label, 0, 7)


        layout.addWidget(QLabel("<b>Cleaning Duration (Decimal):</b>"), 1, 6)
        layout.addWidget(self.clean_excel_decimal_label, 1, 7)

        layout.addWidget(QLabel("<b>Loaded Records:</b>"), 0, 9)
        layout.addWidget(self.visible_records_label, 0, 10)


        # Use stretch factors to space them out
        layout.setColumnStretch(2, 1)
        layout.setColumnStretch(5, 1)
        layout.setColumnStretch(8, 1)

        return summary_box

    # --- THIS IS THE NEW CALCULATION LOGIC FOR THE SUMMARY BOX ---
    def _update_summary_box(self):
        """Calculates and displays the 6 required summaries."""
        df_to_summarize = self.full_data

        if df_to_summarize.empty:
            self.visible_records_label.setText("0")
            self.total_output_label.setText("0.00")
            self.total_cleaning_qty_label.setText("0.00")
            self.total_proc_duration_label.setText("0:00")
            self.total_clean_duration_label.setText("0:00")
            self.proc_excel_decimal_label.setText("0.00")
            self.clean_excel_decimal_label.setText("0.00")
            return
        self.visible_records_label.setText(f"{len(df_to_summarize):,}")
        # 1. Sum of Quantities
        total_output = df_to_summarize['Output QTY'].sum()
        total_cleaning = df_to_summarize['Cleaning QTY'].sum()

        # 2. Sum of Durations (HH:MM)
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

        # 3. Excel-style Decimal Duration Calculation
        proc_total_seconds = total_proc_delta.total_seconds()
        proc_total_hours = int(proc_total_seconds // 3600)
        proc_total_minutes = int((proc_total_seconds % 3600) // 60)

        clean_total_seconds = total_clean_delta.total_seconds()
        clean_total_hours = int(clean_total_seconds // 3600)
        clean_total_minutes = int((clean_total_seconds % 3600) // 60)

        proc_excel_decimal = proc_total_hours + (proc_total_minutes / 60)
        clean_excel_decimal = clean_total_hours + (clean_total_minutes / 60)

        # 4. Update all UI labels
        self.total_output_label.setText(f"{total_output:,.2f}")
        self.total_cleaning_qty_label.setText(f"{total_cleaning:,.2f}")
        self.total_proc_duration_label.setText(f"{proc_total_hours}:{proc_total_minutes:02}")
        self.total_clean_duration_label.setText(f"{clean_total_hours}:{clean_total_minutes:02}")
        self.proc_excel_decimal_label.setText(f"{proc_excel_decimal:.2f}")
        self.clean_excel_decimal_label.setText(f"{clean_excel_decimal:.2f}")

    def _update_summary_box_full_set(self, session):
        """Calculates summary for the ENTIRE filtered result, not just the page."""
        if self.page_size is None:
            self._update_summary_box()  # Use data already in table
            return

        # Call get_mixer_report_data without offset/limit to get the true total
        all_filtered_data = get_mixer_report_data(session, self.current_filters)

        # Temporarily swap full_data to calculate totals
        original_full_data = self.full_data
        self.full_data = all_filtered_data
        self._update_summary_box()
        self.full_data = original_full_data

    # --- THE FOLLOWING TWO METHODS ARE RESTORED ---
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
    # --- END OF FIX ---

    def show_remarks(self, remarks_text: str):
        dialog = RemarksViewerDialog(remarks_text, self)
        dialog.exec()

    @pyqtSlot(str)
    def _on_export_success(self, filepath: str):
        # Ask user if they want to open the file
        reply = QMessageBox.question(
            self, "Export Successful",
            f"Report saved to:\n{filepath}\n\nDo you want to open the file now?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.startfile(filepath)  # For Windows
            except Exception as e:
                QMessageBox.warning(self, "Error Opening File", f"Could not open file automatically:\n{e}")

    @pyqtSlot(str)
    def _on_export_error(self, error_message: str):
        QMessageBox.critical(self, "Export Error", error_message)

    def _handle_export_to_pdf(self):
        QMessageBox.information(self, "Coming Soon", "PDF export functionality will be added in a future update.")

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos)
        if not item: return
        menu = QMenu(self)
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


    def _get_visible_data_as_dataframe(self) -> pd.DataFrame:
        """
        --- THIS IS THE FIX ---
        Returns the DataFrame of ALL currently loaded data. This ensures that
        the export function and the summary box are always in sync.
        It no longer reads from the slow QTableWidget.
        """
        # The live search only hides rows in the UI; it doesn't affect the
        # underlying complete dataset that the user expects to export.
        return self.full_data

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
            QMessageBox.critical(self, "Error", "Could not find the selected record's data.")
            return
        edit_dialog = EditRecordDialog(record_data=record_data, machine_list=self.machine_list,
                                       initial_data=self.editor_initial_data, parent=self)
        edit_dialog.perform_search_requested.connect(self.on_dialog_search_requested)
        if not edit_dialog.exec(): return
        updated_data = edit_dialog.get_updated_data()
        confirm_dialog = SecureConfirmationDialog("Confirm Edit",
                                                  f"Are you sure you want to save the changes for record ID {detail_id}?",
                                                  self)
        confirm_dialog.setObjectName("SecureConfirmationDialog")
        confirm_dialog.ok_button.setObjectName("PrimaryDialogButton")
        if not confirm_dialog.exec(): return
        session = self.Session()
        try:
            update_mixer_record(session, detail_id, updated_data)
            QMessageBox.information(self, "Success", f"Record ID {detail_id} has been updated successfully.")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Database Error", f"Could not update the record:\n{e}")
        finally:
            session.close()
            self.refresh_data(is_manual_refresh=False)
