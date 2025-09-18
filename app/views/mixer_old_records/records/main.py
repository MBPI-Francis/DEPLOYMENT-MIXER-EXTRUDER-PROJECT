# app/views/mixer_old_records/records/main.py

import os
from typing import Type, Callable

from PyQt6.QtGui import QAction, QKeySequence
from sqlalchemy.orm import sessionmaker
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMenu, QMessageBox, QFileDialog, QLineEdit, QLabel
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


# --- NEW WORKER for LIVE SEARCHING ---
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


class OldMixerRecordsView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.full_data = pd.DataFrame()
        self.machine_list = []
        self.current_filters = {}
        self.initial_dialog_data = {}
        self.live_search_worker = None
        self.setObjectName("OldMixerRecordsView")
        main_layout = QVBoxLayout(self)
        top_bar_layout = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search records...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(300)

        self.refresh_button = QPushButton("Refresh", icon=qta.icon("fa5s.sync-alt"))
        self.refresh_button.setObjectName("ActionButton")

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
        top_bar_layout.addWidget(self.export_button) # Add to layout

        # --- NEW: Notification Label Setup ---
        self.notification_label = QLabel(self)
        self.notification_label.setObjectName("NotificationLabel")
        self.notification_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notification_label.setFixedHeight(0) # Start hidden
        self.notification_label.setStyleSheet("background-color: #28a745; color: white; font-weight: bold; padding: 8px;")


        self.table = QTableWidget()
        self.setup_table()

        main_layout.addLayout(top_bar_layout)
        main_layout.addWidget(self.table)
        main_layout.addWidget(self.notification_label)  # Add to layout

        self.setLayout(main_layout)
        self.search_input.textChanged.connect(self.filter_table_by_search)
        self.refresh_button.clicked.connect(lambda: self.refresh_data(is_manual_refresh=True))
        self.filter_button.clicked.connect(self.open_filter_dialog)
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.restore_button.clicked.connect(self.open_restore_dialog)
        self.export_button.clicked.connect(self.show_export_menu)
        self._load_prerequisites_and_data()
        self._setup_shortcuts()  # Call shortcut setup

        # This code finds and applies the stylesheet
        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f:
                self.setStyleSheet(f.read())

    def _load_prerequisites_and_data(self):
        session = self.Session()
        try:
            active_machines = get_active_machines(session)
            self.machine_list = [m.name for m in active_machines] if active_machines else []
            self.initial_dialog_data = get_editor_initial_data(session)
            self.refresh_data(is_manual_refresh=False)  # Load initial data without notification

        except Exception as e:
            # Provide a more detailed error message for debugging
            import traceback
            error_details = traceback.format_exc()
            QMessageBox.critical(self, "Load Error", f"Could not load initial data:\n\n{e}\n\n{error_details}")
        finally:
            session.close()

    @pyqtSlot(bool)
    def refresh_data(self, is_manual_refresh: bool = True):
        """Main data loading/reloading logic, with notification support."""
        session = self.Session()
        try:
            self.full_data = get_old_mixer_report_data(session, self.current_filters)
            self.populate_table(self.full_data)
            self.filter_table_by_search(self.search_input.text())
            if is_manual_refresh:
                self.show_notification("Old records successfully refreshed!")
        except Exception as e:
            QMessageBox.critical(self, "Refresh Error", f"Could not refresh old records:\n{e}")
        finally:
            session.close()


    def load_data(self):
        """Legacy method for compatibility, now calls the main refresh logic."""
        self.refresh_data()


    # --- NEW: Method to set up keyboard shortcuts ---
    def _setup_shortcuts(self):
        refresh_action = QAction("Refresh Data", self)
        refresh_action.setShortcut(QKeySequence("Ctrl+R"))
        refresh_action.triggered.connect(lambda: self.refresh_data(is_manual_refresh=True))
        self.addAction(refresh_action)

    # --- NEW: Methods to show and hide the notification banner ---
    def show_notification(self, message: str, duration_ms: int = 2000):
        self.notification_label.setText(message)
        self.anim_in = QPropertyAnimation(self.notification_label, b"maximumHeight")
        self.anim_in.setDuration(200); self.anim_in.setStartValue(0); self.anim_in.setEndValue(35)
        self.anim_in.start()
        QTimer.singleShot(duration_ms, self.hide_notification)

    def hide_notification(self):
        self.anim_out = QPropertyAnimation(self.notification_label, b"maximumHeight")
        self.anim_out.setDuration(200); self.anim_out.setStartValue(35); self.anim_out.setEndValue(0)
        self.anim_out.start()

    def setup_table(self):
        headers_list = ["Date", "Ref No", "MC #", "Product Code",
                        "Lot Number", "Processing Start", "Processing End",
                        "Processing Duration", "Processed By", "Output QTY"
                        ]
        self.table.setColumnCount(len(headers_list)); self.table.setHorizontalHeaderLabels(headers_list)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False); self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        header = self.table.horizontalHeader(); header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        stretch_columns = {"Date", "Ref No", "MC #", "Product Code",
                           "Lot Number", "Processing Start", "Processing End",
                           "Processing Duration", "Processed By", "Output QTY"
                           }
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

    def populate_table(self, data: pd.DataFrame):
        self.table.setSortingEnabled(False); self.table.setRowCount(0)
        if data is None or data.empty:
            self.table.setSortingEnabled(True); return
        self.table.setRowCount(len(data))
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        for i, row in data.iterrows():
            for j, col_name in enumerate(headers):
                cell_data = row.get(col_name)
                item = QTableWidgetItem(str(cell_data) if pd.notna(cell_data) else "")
                self.table.setItem(i, j, item)
            self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, row["detail_id"])
        self.table.resizeColumnsToContents(); self.table.setSortingEnabled(True)

    def filter_table_by_search(self, text: str):
        text = text.lower()
        for i in range(self.table.rowCount()):
            match = any(self.table.item(i, j) and text in self.table.item(i, j).text().lower() for j in range(self.table.columnCount()))
            self.table.setRowHidden(i, not match)

    def open_filter_dialog(self):
        """
        Opens the stable filter dialog with the correct arguments.
        """
        # --- CORRECTED: Pass only the arguments the dialog expects ---

        dialog = FilterDialog(
            machine_list=self.machine_list,
            initial_data= self.initial_dialog_data,
            current_filters=self.current_filters,
            parent=self
        )

        # Connect the delegation signal for live search
        dialog.perform_search_requested.connect(self.on_dialog_search_requested)

        if dialog.exec():
            self.current_filters = dialog.get_filters()
            self.load_data()


    @pyqtSlot(object, object, str)
    def on_dialog_search_requested(self, combo_box: SmartComboBox, search_function: Callable, search_term: str):
        if self.live_search_worker and self.live_search_worker.isRunning():
            return
        self.live_search_worker = LiveSearchWorker(self.Session, search_function, search_term, self)
        self.live_search_worker.results_ready.connect(combo_box.update_with_search_results)
        self.live_search_worker.finished.connect(self._on_search_finished)
        self.live_search_worker.start()

    # --- NEW: Slot to clean up the worker thread ---
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
        if action == edit_action: self.edit_selected_record()
        elif action == delete_action: self.delete_selected_record()

    def get_id_from_selected_row(self):
        rows = self.table.selectionModel().selectedRows()
        return self.table.item(rows[0].row(), 0).data(Qt.ItemDataRole.UserRole) if rows else None

    def edit_selected_record(self):
        detail_id = self.get_id_from_selected_row()
        if not detail_id: QMessageBox.warning(self, "Selection Error", "Please select a record to edit."); return
        record_data = self.full_data.loc[self.full_data['detail_id'] == detail_id].iloc[0]
        edit_dialog = EditRecordDialog(record_data=record_data, machine_list=self.machine_list,
                                       initial_data= self.initial_dialog_data, parent=self)
        # --- NEW: Connect the dialog's delegation signal to our handler ---
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
            update_old_mixer_record(session, detail_id, updated_data)
            QMessageBox.information(self, "Success", f"Record ID {detail_id} has been updated successfully.")
        except Exception as e:
            session.rollback();
            QMessageBox.critical(self, "Database Error", f"Could not update the record:\n{e}")
        finally:
            session.close()
            self.load_data()


    def delete_selected_record(self):
        detail_id = self.get_id_from_selected_row()
        if not detail_id: QMessageBox.warning(self, "Selection Error", "Please select a record to delete."); return
        confirm = SecureConfirmationDialog("Confirm Deletion", f"Are you sure you want to delete record ID {detail_id}?")
        if confirm.exec():
            session = self.Session()
            try: delete_old_mixer_record(session, detail_id)
            finally: session.close()
            self.load_data()

    def open_restore_dialog(self):
        session = self.Session()
        try:
            deleted_data = get_deleted_old_mixer_records(session)
            if deleted_data.empty:
                QMessageBox.information(self, "No Records", "There are no deleted records to restore."); return
            dialog = RestoreDialog(deleted_data, self)
            if dialog.exec():
                ids = dialog.get_selected_ids()
                if ids:
                    restore_old_mixer_records(session, ids)
                    self.load_data()
        finally:
            session.close()

    def _get_visible_data_as_dataframe(self) -> pd.DataFrame:
        """Constructs a DataFrame from only the visible rows in the table."""
        visible_data = []
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                row_data = {header: self.table.item(row, col).text() if self.table.item(row, col) else "" for
                            col, header in enumerate(headers)}
                visible_data.append(row_data)
        df = pd.DataFrame(visible_data)
        # Convert numeric columns from text back to numbers for calculations
        if 'Output QTY' in df.columns:
            df['Output QTY'] = pd.to_numeric(df['Output QTY'], errors='coerce').fillna(0)
        return df

    def show_export_menu(self):
        """Shows a menu to choose the export format."""
        export_menu = QMenu(self)
        excel_action = QAction("Export to Excel...", self)
        # pdf_action = QAction("Export to PDF...", self) # Can add this later

        excel_action.triggered.connect(self.handle_export)
        export_menu.addAction(excel_action)

        menu_position = self.export_button.mapToGlobal(self.export_button.rect().bottomLeft())
        export_menu.exec(menu_position)

    def handle_export(self):
        """Handles the process of exporting the data to Excel."""
        visible_df = self._get_visible_data_as_dataframe()
        if visible_df.empty:
            QMessageBox.warning(self, "No Data", "There is no data to export.");
            return

        default_filename = f"Old_Mixer_Report_{QDate.currentDate().toString('yyyy-MM-dd')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Excel Report", default_filename, "Excel Files (*.xlsx)")
        if not file_path: return

        try:
            exporter = OldRecordsExcelExporter(visible_df)
            exporter.export(file_path)
            QMessageBox.information(self, "Export Successful", f"Report successfully saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n{e}")