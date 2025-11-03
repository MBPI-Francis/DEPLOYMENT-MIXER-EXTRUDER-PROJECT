# app/views/mixer_old_records/records/main.py

import os
from typing import Type, Callable

from PyQt6.QtGui import QAction, QKeySequence
from sqlalchemy.orm import sessionmaker
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMenu, QMessageBox, QFileDialog, QLineEdit, QLabel,
    QApplication, QDialog, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSlot, QPropertyAnimation, QTimer, QThread, pyqtSignal, QDate
import pandas as pd
import qtawesome as qta

from app.widgets.smart_combo_box import SmartComboBox
from .exporter import OldRecordsExcelExporter
from .ops import (
    delete_old_mixer_record, get_old_mixer_report_data, get_deleted_old_mixer_records,
    restore_old_mixer_records, update_old_mixer_record, get_editor_initial_data
)
from .widgets import FilterDialog, RestoreDialog, SecureConfirmationDialog, EditRecordDialog
from app.database.mixer_machine_ops import get_active_machines


# --- Worker for Live Searching (no changes needed) ---
class LiveSearchWorker(QThread):
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, session_factory: Callable, search_function: Callable, search_term: str, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.search_function = search_function
        self.search_term = search_term

    def run(self):
        session = self.Session()
        try:
            results = self.search_function(session, self.search_term)
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(f"Live search failed: {e}")
        finally:
            session.close()


class ExportWorker(QThread):
    success = pyqtSignal(str)
    error = pyqtSignal(str)
    def __init__(self, session_factory: Type[sessionmaker], filters: dict, filepath: str, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.filters = filters
        self.filepath = filepath
    def run(self):
        session = self.Session()
        try:
            # --- MODIFICATION: Fetch ALL data for export, ignoring pagination ---
            full_df = get_old_mixer_report_data(session, self.filters, limit=None, offset=0)
            if full_df.empty:
                self.error.emit("There is no data matching the current filters to export.")
                return
            exporter = OldRecordsExcelExporter(full_df)
            exporter.export(self.filepath)
            self.success.emit(self.filepath)
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.error.emit(f"An error occurred during export:\n\n{e}\n\n{error_details}")
        finally:
            session.close()


# --- NEW: A simple, reusable loading dialog ---
class LoadingDialog(QDialog):
    """A simple modal dialog to show during long operations."""

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


class OldMixerRecordsView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.full_data = pd.DataFrame()
        self.machine_list = []
        self.current_filters = {}
        self.initial_dialog_data = {}
        self.live_search_worker = None
        self.export_worker = None
        self.setObjectName("OldMixerRecordsView")

        # --- NEW: State variables for lazy loading ---
        self.current_offset = 0
        self.batch_size = 100  # Load 100 records at a time
        self.is_loading = False  # Flag to prevent multiple concurrent loads
        self.all_data_loaded = False  # Flag to stop loading when all data is fetched

        main_layout = QVBoxLayout(self)
        top_bar_layout = QHBoxLayout()

        # --- MODIFICATION: The live search input is now disabled ---
        # It is incompatible with lazy loading. Users should use the Filter dialog.
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Use 'Filter Records' to search...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(300)
        self.search_input.setEnabled(False)  # Disable the search bar

        self.refresh_button = QPushButton("Refresh", icon=qta.icon("fa5s.sync-alt"))
        self.filter_button = QPushButton("Filter Records...")
        self.clear_filters_button = QPushButton("Clear Filters")
        self.restore_button = QPushButton("Restore Records...")
        self.export_button = QPushButton("Export...")
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
            "background-color: #28a745; color: white; font-weight: bold; padding: 8px;")

        self.table = QTableWidget()
        self.setup_table()

        main_layout.addLayout(top_bar_layout)
        main_layout.addWidget(self.table)
        main_layout.addWidget(self.notification_label)
        self.setLayout(main_layout)

        # --- MODIFICATION: Connect scrollbar signal for lazy loading ---
        self.table.verticalScrollBar().valueChanged.connect(self._on_scroll)

        self.refresh_button.clicked.connect(lambda: self.refresh_data(is_manual_refresh=True))
        self.filter_button.clicked.connect(self.open_filter_dialog)
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.restore_button.clicked.connect(self.open_restore_dialog)
        self.export_button.clicked.connect(self.show_export_menu)
        self._load_prerequisites_and_data()
        self._setup_shortcuts()
        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f: self.setStyleSheet(f.read())

    # --- NEW: Scroll event handler to trigger lazy loading ---
    def _on_scroll(self, value):
        """Checks if the scrollbar is at the bottom and loads more data."""
        scrollbar = self.table.verticalScrollBar()
        # Trigger when scroll is at 95% of max to be proactive
        if value >= scrollbar.maximum() * 0.95:
            self._load_next_batch()

    # --- MODIFIED: Handles export by fetching ALL data in a worker ---
    def handle_export(self):
        if self.export_worker and self.export_worker.isRunning():
            QMessageBox.warning(self, "Export in Progress", "An export is already running. Please wait.")
            return

        default_filename = f"Old_Mixer_Report_{QDate.currentDate().toString('yyyy-MM-dd')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel Report", default_filename, "Excel Files (*.xlsx)")
        if not file_path: return

        self.loading_dialog = LoadingDialog(self)
        self.loading_dialog.set_text("Exporting to Excel, please wait...")

        # Pass the session factory and filters to the worker
        self.export_worker = ExportWorker(self.Session, self.current_filters, file_path)
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

    def _load_prerequisites_and_data(self):
        session = self.Session()
        try:
            self.machine_list = [m.name for m in get_active_machines(session)]
            self.initial_dialog_data = get_editor_initial_data(session)
            # Load initial batch of data
            self.refresh_data(is_manual_refresh=False)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not load initial data:\n{e}")
        finally:
            session.close()

    # --- MODIFIED: refresh_data now resets and loads the FIRST batch ---
    @pyqtSlot(bool)
    def refresh_data(self, is_manual_refresh: bool = True):
        """Resets the view and loads the first batch of data."""
        self.current_offset = 0
        self.all_data_loaded = False
        self.full_data = pd.DataFrame()  # Clear the master dataframe
        self.table.setRowCount(0)  # Clear the table UI

        # Now load the very first batch
        self._load_next_batch()

        if is_manual_refresh:
            self.show_notification("Old records successfully refreshed!")

    # --- NEW: Core lazy loading logic ---
    def _load_next_batch(self):
        """Fetches the next batch of data from the database and appends it."""
        if self.is_loading or self.all_data_loaded:
            return  # Prevent re-entry

        self.is_loading = True
        session = self.Session()
        try:
            new_data = get_old_mixer_report_data(
                session,
                self.current_filters,
                limit=self.batch_size,
                offset=self.current_offset
            )

            if not new_data.empty:
                # Append to the main dataframe and the UI table
                self.full_data = pd.concat([self.full_data, new_data], ignore_index=True)
                self._append_to_table(new_data)
                self.current_offset += len(new_data)

            # If we received fewer records than we asked for, we've reached the end
            if len(new_data) < self.batch_size:
                self.all_data_loaded = True

        except Exception as e:
            QMessageBox.critical(self, "Data Load Error", f"Could not load next batch of records:\n{e}")
        finally:
            session.close()
            self.is_loading = False

    # (load_data is now an alias for the new refresh_data)
    def load_data(self):
        self.refresh_data()

    def _setup_shortcuts(self):
        refresh_action = QAction("Refresh Data", self)
        refresh_action.setShortcut(QKeySequence("Ctrl+R"))
        refresh_action.triggered.connect(lambda: self.refresh_data(is_manual_refresh=True))
        self.addAction(refresh_action)

    # (Notification methods are unchanged)
    def show_notification(self, message: str, duration_ms: int = 2000):
        self.notification_label.setText(message)
        anim = QPropertyAnimation(self.notification_label, b"maximumHeight")
        anim.setDuration(200);
        anim.setStartValue(0);
        anim.setEndValue(35)
        anim.start()
        QTimer.singleShot(duration_ms, self.hide_notification)

    def hide_notification(self):
        anim = QPropertyAnimation(self.notification_label, b"maximumHeight")
        anim.setDuration(200);
        anim.setStartValue(35);
        anim.setEndValue(0)
        anim.start()

    # (setup_table is unchanged)
    def setup_table(self):
        headers_list = ["Date", "Ref No", "MC #", "Product Code", "Lot Number", "Processing Start", "Processing End",
                        "Processing Duration", "Processed By", "Output QTY"]
        self.table.setColumnCount(len(headers_list));
        self.table.setHorizontalHeaderLabels(headers_list)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False);
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        header = self.table.horizontalHeader();
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        stretch_columns = {"Date", "Ref No", "MC #", "Product Code", "Lot Number", "Processing Start", "Processing End",
                           "Processing Duration", "Processed By", "Output QTY"}
        for i, header_text in enumerate(headers_list):
            if header_text in stretch_columns:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    # --- MODIFIED: clear_filters now triggers a full refresh ---
    def clear_filters(self):
        self.current_filters = {}
        self.search_input.clear()
        self.refresh_data(is_manual_refresh=False)  # This will reset and load the first page
        QMessageBox.information(self, "Filters Cleared", "All filters have been removed.")

    # --- MODIFIED: populate_table is now only for full replacements (though unused) ---
    def populate_table(self, data: pd.DataFrame):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(data))
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        for i, row in data.iterrows():
            for j, col_name in enumerate(headers):
                item = QTableWidgetItem(str(row.get(col_name, "")))
                self.table.setItem(i, j, item)
            self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, row["detail_id"])
        self.table.setSortingEnabled(True)

    def _append_to_table(self, data: pd.DataFrame):
        """
        Appends a DataFrame to the QTableWidget, correctly handling column names
        with spaces or special characters.
        """
        self.table.setSortingEnabled(False)
        start_row = self.table.rowCount()
        self.table.setRowCount(start_row + len(data))
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]

        # Use iterrows() which provides a Series for each row. This correctly
        # preserves the original column names for lookup.
        for i, (index, row_data) in enumerate(data.iterrows()):
            current_row = start_row + i
            for j, col_name in enumerate(headers):
                # Access the data from the row Series using the original column name as a key.
                cell_data = row_data.get(col_name, "")
                item = QTableWidgetItem(str(cell_data))
                self.table.setItem(current_row, j, item)

            # Get the detail_id from the Series and set it as the UserRole data.
            detail_id = row_data['detail_id']
            self.table.item(current_row, 0).setData(Qt.ItemDataRole.UserRole, detail_id)

        self.table.setSortingEnabled(True)

    # --- DEPRECATED by lazy loading ---
    def filter_table_by_search(self, text: str):
        # This local-only search is no longer used.
        pass

    def open_filter_dialog(self):
        dialog = FilterDialog(
            machine_list=self.machine_list,
            initial_data=self.initial_dialog_data,
            current_filters=self.current_filters,
            parent=self
        )
        dialog.perform_search_requested.connect(self.on_dialog_search_requested)
        if dialog.exec():
            self.current_filters = dialog.get_filters()
            self.refresh_data(is_manual_refresh=False)  # Reset and load page 1 of new filtered data

    # (Dialog search, context menu, and CRUD operations remain unchanged as they operate on self.full_data)
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

    def show_context_menu(self, pos):
        item = self.table.itemAt(pos);
        if not item: return
        menu = QMenu()
        edit_action = menu.addAction("Edit Record...")
        delete_action = menu.addAction("Delete Record...")
        action = menu.exec(self.table.mapToGlobal(pos))
        if action == edit_action:
            self.edit_selected_record()
        elif action == delete_action:
            self.delete_selected_record()

    def get_id_from_selected_row(self):
        rows = self.table.selectionModel().selectedRows()
        return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole) if rows else None

    def edit_selected_record(self):
        detail_id = self.get_id_from_selected_row()
        if not detail_id: QMessageBox.warning(self, "Selection Error", "Please select a record to edit."); return
        # Find the record in our master dataframe
        record_data = self.full_data.loc[self.full_data['detail_id'] == detail_id].iloc[0]
        edit_dialog = EditRecordDialog(record_data=record_data, machine_list=self.machine_list,
                                       initial_data=self.initial_dialog_data, parent=self)
        edit_dialog.perform_search_requested.connect(self.on_dialog_search_requested)
        if not edit_dialog.exec(): return
        updated_data = edit_dialog.get_updated_data()
        confirm_dialog = SecureConfirmationDialog("Confirm Edit",
                                                  f"Are you sure you want to save the changes for record ID {detail_id}?",
                                                  self)
        if not confirm_dialog.exec(): return
        session = self.Session()
        try:
            update_old_mixer_record(session, detail_id, updated_data)
            QMessageBox.information(self, "Success", f"Record ID {detail_id} has been updated successfully.")
        except Exception as e:
            session.rollback();
            QMessageBox.critical(self, "Database Error", f"Could not update the record:\n{e}")
        finally:
            session.close()
            self.refresh_data(is_manual_refresh=False)  # Refresh to show changes

    def delete_selected_record(self):
        detail_id = self.get_id_from_selected_row()
        if not detail_id: QMessageBox.warning(self, "Selection Error", "Please select a record to delete."); return
        confirm = SecureConfirmationDialog("Confirm Deletion",
                                           f"Are you sure you want to delete record ID {detail_id}?")
        if confirm.exec():
            session = self.Session()
            try:
                delete_old_mixer_record(session, detail_id)
            finally:
                session.close()
            self.refresh_data(is_manual_refresh=False)  # Refresh to remove the row

    def open_restore_dialog(self):
        session = self.Session()
        try:
            deleted_data = get_deleted_old_mixer_records(session)
            if deleted_data.empty:
                QMessageBox.information(self, "No Records", "There are no deleted records to restore.");
                return
            dialog = RestoreDialog(deleted_data, self)
            if dialog.exec():
                ids = dialog.get_selected_ids()
                if ids:
                    restore_old_mixer_records(session, ids)
                    self.refresh_data(is_manual_refresh=False)
        finally:
            session.close()

    # --- DEPRECATED: This function is unreliable with lazy loading. Export now fetches its own data. ---
    def _get_visible_data_as_dataframe(self) -> pd.DataFrame:
        # This should no longer be used for critical operations like exporting.
        return self.full_data  # Return the currently loaded data

    def show_export_menu(self):
        export_menu = QMenu(self)
        excel_action = QAction("Export to Excel...", self)
        excel_action.triggered.connect(self.handle_export)
        export_menu.addAction(excel_action)
        menu_position = self.export_button.mapToGlobal(self.export_button.rect().bottomLeft())
        export_menu.exec(menu_position)