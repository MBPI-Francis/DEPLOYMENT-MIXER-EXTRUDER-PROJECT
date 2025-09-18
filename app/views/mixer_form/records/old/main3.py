# app/views/mixer_report/main.py

import os
from typing import Type, Callable

from PyQt6.QtGui import QAction
from sqlalchemy.orm import sessionmaker
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu, QMessageBox,
    QFileDialog, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSlot
import pandas as pd

from app.widgets.smart_combo_box import SmartComboBox
from app.widgets.workers import LiveSearchWorker
from .exporter import ExcelExporter
# --- Corrected and verified imports ---
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


class MixerRecordsView(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.full_data = pd.DataFrame()
        self.machine_list = []
        self.current_filters = {}
        self.editor_initial_data = {}
        # --- NEW: Attribute to hold the worker, ensuring it's owned by this permanent widget ---
        self.live_search_worker = None

        # self.setObjectName("MixerRecordsView")
        main_layout = QVBoxLayout(self)
        top_bar_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search all columns...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(300)
        self.filter_button = QPushButton("Filter Records...")
        self.filter_button.setObjectName("ActionButton")
        self.clear_filters_button = QPushButton("Clear Filters")
        self.clear_filters_button.setObjectName("ActionButton")
        self.restore_button = QPushButton("Restore Records...")
        self.restore_button.setObjectName("ActionButton")
        self.export_button = QPushButton("Export to Excel...")
        self.export_button.setObjectName("ActionButton")
        top_bar_layout.addWidget(self.search_input)
        top_bar_layout.addStretch()
        top_bar_layout.addWidget(self.filter_button)
        top_bar_layout.addWidget(self.clear_filters_button)
        top_bar_layout.addWidget(self.restore_button)
        top_bar_layout.addWidget(self.export_button)
        self.table = QTableWidget()
        self.setup_table()
        main_layout.addLayout(top_bar_layout)
        main_layout.addWidget(self.table)
        self.search_input.textChanged.connect(self.filter_table_by_search)
        self.filter_button.clicked.connect(self.open_filter_dialog)
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.restore_button.clicked.connect(self.open_restore_dialog)
        self.export_button.clicked.connect(self.export_to_excel)
        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f:
                self.setStyleSheet(f.read())

        self._load_prerequisites_and_data()

    def _load_prerequisites_and_data(self):
        session = self.Session()
        try:
            self.machine_list = [m.name for m in get_active_machines(session)]
            self.editor_initial_data = get_editor_initial_data(session)
            self.full_data = get_mixer_report_data(session, self.current_filters)
            self.populate_table(self.full_data)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not load initial data: {e}")
        finally:
            session.close()

    def load_data(self):
        session = self.Session()
        try:
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)
            self.full_data = get_mixer_report_data(session, self.current_filters)
            self.populate_table(self.full_data)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not load report data:\n{e}")
        finally:
            session.close()

    # --- MODIFIED: The `edit_selected_record` method is now correct ---
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
            update_mixer_record(session, detail_id, updated_data)
            QMessageBox.information(self, "Success", f"Record ID {detail_id} has been updated successfully.")
        except Exception as e:
            session.rollback();
            QMessageBox.critical(self, "Database Error", f"Could not update the record:\n{e}")
        finally:
            session.close()
            self.load_data()

    # --- NEW: Slot to handle the search request delegated from the dialog ---
    @pyqtSlot(object, object, str)
    def on_dialog_search_requested(self, combo_box: SmartComboBox, search_function: Callable, search_term: str):
        """Creates and manages the worker thread safely."""
        if self.live_search_worker and self.live_search_worker.isRunning():
            return
        self.live_search_worker = LiveSearchWorker(self.Session, search_function, search_term, self)
        # Connect the result directly to the combo box instance that requested it
        self.live_search_worker.results_ready.connect(combo_box.update_with_search_results)
        self.live_search_worker.finished.connect(self._on_search_finished)
        self.live_search_worker.start()

    # --- NEW: Slot to clean up the worker ---
    @pyqtSlot()
    def _on_search_finished(self):
        """Safely cleans up the worker reference after it's done."""
        if self.live_search_worker:
            self.live_search_worker.deleteLater()
            self.live_search_worker = None

    # --- All other methods below are the stable, working versions ---

    def filter_table_by_search(self, search_text: str):
        search_text = search_text.lower()
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

        stretch_columns = {"Product Code", "Lot Number", "Cleaning RM"}
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

    def populate_table(self, data: pd.DataFrame):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
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

    def show_remarks(self, remarks_text: str):
        dialog = RemarksViewerDialog(remarks_text, self)
        dialog.exec()

    def open_filter_dialog(self):
        dialog = FilterDialog(self.machine_list, self.editor_initial_data, self.current_filters, self)
        if dialog.exec():
            self.current_filters = dialog.get_filters()
            self.load_data()

    # --- NEW HELPER: Gathers only the visible data from the table ---
    def _get_visible_data_as_dataframe(self) -> pd.DataFrame:
        """
        Constructs a DataFrame containing only the data from rows currently
        visible in the QTableWidget (respecting the live search).
        """
        visible_data = []
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]

        for row in range(self.table.rowCount()):
            if not self.table.isRowHidden(row):
                row_data = {}
                detail_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)

                for col, header in enumerate(headers):
                    if header == "Remarks":
                        # Get the full, original remarks text, not just "View"
                        row_data[header] = self.full_data.loc[self.full_data['detail_id'] == detail_id, 'Remarks'].iloc[
                            0]
                    else:
                        item = self.table.item(row, col)
                        row_data[header] = item.text() if item else ""
                visible_data.append(row_data)

        df = pd.DataFrame(visible_data)

        # Convert numeric columns from text back to numbers for calculations
        numeric_cols = {"Ref No": int, "Output QTY": float, "Cleaning QTY": float}
        for col, col_type in numeric_cols.items():
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0).astype(col_type)

        return df

    # --- REPLACED METHOD: This now opens a menu of export options ---
    def export_to_excel(self):  # The button click is now handled here
        """Shows a menu with export options (Excel, PDF)."""
        export_menu = QMenu(self)
        excel_action = QAction("Export to Excel...", self)
        pdf_action = QAction("Export to PDF...", self)

        excel_action.triggered.connect(self._handle_export_to_excel)
        pdf_action.triggered.connect(self._handle_export_to_pdf)  # Placeholder

        export_menu.addAction(excel_action)
        export_menu.addAction(pdf_action)

        # Show the menu below the export button
        export_button = self.sender()
        menu_position = export_button.mapToGlobal(export_button.rect().bottomLeft())
        export_menu.exec(menu_position)

    # --- NEW METHOD: Handles the actual Excel export logic ---
    def _handle_export_to_excel(self):
        """Orchestrates the process of exporting data to an Excel file."""
        visible_df = self._get_visible_data_as_dataframe()

        if visible_df.empty:
            QMessageBox.warning(self, "No Data", "There is no data to export.")
            return

        # Let the user choose where to save the file
        default_filename = f"Mixer_Report_{pd.Timestamp.now().strftime('%Y-%m-%d')}.xlsx"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Excel Report", default_filename, "Excel Files (*.xlsx)"
        )

        if not file_path:
            return  # User cancelled the dialog

        try:
            # Use our dedicated exporter class
            exporter = ExcelExporter(visible_df)
            exporter.export(file_path)
            QMessageBox.information(self, "Export Successful", f"Report successfully saved to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n{e}")

    # --- NEW METHOD: Placeholder for future PDF export ---
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
        """
        Handles the logic for deleting a record with secure confirmation.
        """
        # 1. Get the hidden ID from the currently selected row in the table
        detail_id = self.get_id_from_selected_row()
        if not detail_id:
            return  # A message is already shown by the helper function if no row is selected

        # 2. Create and show the secure confirmation dialog
        confirm_dialog = SecureConfirmationDialog(
            "Confirm Deletion",
            f"You are about to permanently delete record with ID {detail_id}. This cannot be undone.",
            self
        )
        confirm_dialog.setObjectName("SecureConfirmationDialog")
        confirm_dialog.ok_button.setObjectName("PrimaryDialogButton")

        # 3. Proceed only if the user confirms by typing "YES"
        if not confirm_dialog.exec():
            return

        # 4. Perform the database operation
        session = self.Session()
        try:
            # Call the new function in ops.py to perform the soft delete
            delete_mixer_record(session, detail_id)
            QMessageBox.information(self, "Success", f"Record ID {detail_id} has been deleted.")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Database Error", f"Could not delete the record:\n{e}")
        finally:
            session.close()
            # 5. ALWAYS refresh the main table to show the record has been removed
            self.load_data()

    def open_restore_dialog(self):
        """
        Opens the dialog for viewing and restoring soft-deleted records.
        """
        session = self.Session()
        try:
            # 1. Fetch all records where is_deleted = True
            deleted_data = get_deleted_mixer_records(session)

            # 2. Check if there's anything to restore
            if deleted_data.empty:
                QMessageBox.information(self, "No Records", "There are no deleted records to restore.")
                return

            # 3. Create and show the RestoreDialog, passing the deleted records to it
            dialog = RestoreDialog(deleted_data, self)

            # 4. Proceed only if the user clicks the "Restore Selected" button
            if not dialog.exec():
                return

            # 5. Get the list of IDs that the user checked in the dialog
            ids_to_restore = dialog.get_selected_ids()

            if ids_to_restore:
                # 6. Call the existing function in ops.py to restore the records
                restore_mixer_records(session, ids_to_restore)
                QMessageBox.information(self, "Success", f"{len(ids_to_restore)} record(s) have been restored.")
                # 7. Refresh the main table to show the restored records
                self.load_data()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open restore dialog:\n{e}")
        finally:
            session.close()