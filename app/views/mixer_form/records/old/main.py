import os
from typing import Type, List
from sqlalchemy.orm import sessionmaker, Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMenu, QMessageBox,
    QFileDialog
)
from PyQt6.QtCore import Qt, QDateTime
import pandas as pd
import qtawesome as qta

from .ops import get_mixer_report_data, get_deleted_mixer_records, restore_mixer_records
from .widgets import FilterDialog, RemarksViewerDialog, RestoreDialog, SecureConfirmationDialog
from models import MixerDetail
from app.database.mixer_machine_ops import get_active_machines


class MixerRecordsView(QWidget):
    """The main view for the Mixer Report module."""

    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.full_data = pd.DataFrame()
        self.machine_list = []
        self.current_filters = {}  # Stores the current filter state

        self.setObjectName("MixerReportView")

        main_layout = QVBoxLayout(self)

        # --- NEW: Simplified Action Bar ---
        action_layout = QHBoxLayout()
        self.filter_button = QPushButton("Filter Records...")
        self.filter_button.setObjectName("ActionButton")
        self.clear_filters_button = QPushButton("Clear Filters")
        self.clear_filters_button.setObjectName("ActionButton")
        self.restore_button = QPushButton("Restore Records...")
        self.restore_button.setObjectName("ActionButton")
        self.export_button = QPushButton("Export to Excel...")
        self.export_button.setObjectName("ActionButton")

        action_layout.addWidget(self.filter_button)
        action_layout.addWidget(self.clear_filters_button)
        action_layout.addWidget(self.restore_button)
        action_layout.addStretch()
        action_layout.addWidget(self.export_button)

        # --- Data Table ---
        self.table = QTableWidget()
        self.setup_table()

        main_layout.addLayout(action_layout)
        main_layout.addWidget(self.table)

        # --- Connections ---
        self.filter_button.clicked.connect(self.open_filter_dialog)
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.restore_button.clicked.connect(self.open_restore_dialog)
        self.export_button.clicked.connect(self.export_to_excel)

        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f:
                self.setStyleSheet(f.read())

        self.load_data()

    def setup_table(self):
        """Initializes the properties of the QTableWidget."""
        self.table.setColumnCount(17)  # 15 display columns + 1 hidden ID column
        self.table.setHorizontalHeaderLabels([
            "Date", "Ref No", "MC #", "Product Code", "Lot Number", "Formula No",
            "Processing Start", "Processing End", "Processing Duration",
            "Processed By", "Output QTY",
            "Cleaning Start", "Cleaning End", "Cleaning Duration",
            "Cleaning RM", "Cleaning QTY", "Remarks"
        ])

        # Modern table styling and behavior
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        # Context Menu for Edit/Delete
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

    def clear_filters(self):
        """Resets the filters and reloads the table to show all records."""
        self.current_filters = {}
        self.load_data()
        QMessageBox.information(self, "Filters Cleared", "All filters have been removed.")

    def load_data(self):
        """Fetches data using the current filters and populates the table."""
        session = self.Session()
        try:
            if not self.machine_list:
                self.machine_list = [m.name for m in get_active_machines(session)]

            self.full_data = get_mixer_report_data(session, self.current_filters)
            self.populate_table(self.full_data)
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not load report data:\n{e}")
        finally:
            session.close()

    def populate_table(self, data: pd.DataFrame):
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        self.table.setRowCount(len(data))

        visible_columns = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]

        for i, row in data.iterrows():
            for j, col_name in enumerate(visible_columns):
                if col_name == "Remarks":
                    remarks_text = str(row.get(col_name, ''))
                    if remarks_text:
                        btn = QPushButton("View")
                        btn.setObjectName("RemarksButton")
                        btn.clicked.connect(lambda _, rt=remarks_text: self.show_remarks(rt))
                        self.table.setCellWidget(i, j, btn)
                    else:
                        self.table.setItem(i, j, QTableWidgetItem(""))
                else:
                    item = QTableWidgetItem(str(row.get(col_name, '')))
                    self.table.setItem(i, j, item)

            self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, row["detail_id"])

        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

    def show_remarks(self, remarks_text: str):
        """Opens the dialog to show the full remarks."""
        dialog = RemarksViewerDialog(remarks_text, self)
        dialog.exec()

    def open_filter_dialog(self):
        """Opens the modal dialog for setting filters."""
        dialog = FilterDialog(self.machine_list, self.current_filters, self)
        if dialog.exec():
            self.current_filters = dialog.get_filters()
            self.load_data() # Reload data with new filters

    def open_restore_dialog(self):
        """Opens the dialog for restoring deleted records."""
        session = self.Session()
        try:
            deleted_data = get_deleted_mixer_records(session)
            if deleted_data.empty:
                QMessageBox.information(self, "No Records", "There are no deleted records to restore.")
                return

            dialog = RestoreDialog(deleted_data, self)
            if dialog.exec():
                ids_to_restore = dialog.get_selected_ids()
                if ids_to_restore:
                    restore_mixer_records(session, ids_to_restore)
                    QMessageBox.information(self, "Success", f"{len(ids_to_restore)} record(s) have been restored.")
                    self.load_data()  # Refresh the main table
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not open restore dialog:\n{e}")
        finally:
            session.close()

    def export_to_excel(self):
        """Exports the CURRENTLY visible data to an Excel file."""
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "No Data", "There is no data in the table to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export to Excel", "", "Excel Files (*.xlsx)")
        if not file_path:
            return

        # Reconstruct DataFrame from the visible table items
        data = []
        headers = [self.table.horizontalHeaderItem(i).text() for i in range(self.table.columnCount())]
        for row in range(self.table.rowCount()):
            row_data = {}
            for col, header in enumerate(headers):
                if header == "Remarks":
                    # Get the original remarks text from the full dataframe
                    detail_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
                    row_data[header] = self.full_data.loc[self.full_data['detail_id'] == detail_id, 'Remarks'].iloc[0]
                else:
                    row_data[header] = self.table.item(row, col).text()
            data.append(row_data)

        export_df = pd.DataFrame(data)

        try:
            export_df.to_excel(file_path, index=False, engine='openpyxl')
            QMessageBox.information(self, "Success", f"Report successfully exported to:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n{e}")

    def show_context_menu(self, pos):
        """Shows the right-click context menu for the table."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return

        menu = QMenu()
        edit_action = menu.addAction("Edit Record...")
        delete_action = menu.addAction("Delete Record...")

        action = menu.exec(self.table.mapToGlobal(pos))

        if action == edit_action:
            self.edit_selected_record()
        elif action == delete_action:
            self.delete_selected_record()

    def get_id_from_selected_row(self) -> int | None:
        """Helper to get the hidden detail_id from the selected row."""
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        # The ID is stored in the first item of the row
        return self.table.item(selected_rows[0].row(), 0).data(Qt.ItemDataRole.UserRole)

    def edit_selected_record(self):
        """Handles the logic for editing a record."""
        detail_id = self.get_id_from_selected_row()
        if not detail_id:
            return

        dialog = SecureConfirmationDialog(
            "Confirm Edit",
            f"You are about to edit record with ID {detail_id}. This action is permanent.",
            self
        )
        if dialog.exec():
            # The actual editing logic would go here.
            # For example, opening a pre-filled MixerEntryFormView.
            QMessageBox.information(self, "Edit", f"Proceeding to edit record ID: {detail_id}")
            # TODO: Implement the edit screen logic
            self.load_data()  # Refresh data after edit

    def delete_selected_record(self):
        """Handles the logic for deleting a record with secure confirmation."""
        detail_id = self.get_id_from_selected_row()
        if not detail_id:
            return

        dialog = SecureConfirmationDialog(
            "Confirm Deletion",
            f"You are about to permanently delete record with ID {detail_id}. This cannot be undone.",
            self
        )
        if dialog.exec():
            session = self.Session()
            try:
                # Use the is_deleted flag for a "soft delete"
                record_to_delete = session.get(MixerDetail, detail_id)
                if record_to_delete:
                    record_to_delete.is_deleted = True
                    session.commit()
                    QMessageBox.information(self, "Success", f"Record ID {detail_id} has been deleted.")
                else:
                    QMessageBox.warning(self, "Not Found", "The selected record could not be found.")
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Database Error", f"Could not delete the record:\n{e}")
            finally:
                session.close()
                self.load_data()  # Refresh data after delete