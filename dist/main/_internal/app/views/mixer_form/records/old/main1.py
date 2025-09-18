# app/views/mixer_report/main.py

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

from ..ops import get_mixer_report_data, get_deleted_mixer_records, restore_mixer_records
from ..widgets import FilterDialog, RemarksViewerDialog, RestoreDialog, SecureConfirmationDialog
from models import MixerDetail
from app.database.mixer_machine_ops import get_active_machines

class MixerRecordsView(QWidget):
    """The main view for the Mixer Report module."""

    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.full_data = pd.DataFrame()
        self.machine_list = []
        self.current_filters = {}

        self.setObjectName("MixerReportView")
        main_layout = QVBoxLayout(self)

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

        self.table = QTableWidget()
        self.setup_table()

        main_layout.addLayout(action_layout)
        main_layout.addWidget(self.table)

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
        self.table.setColumnCount(16)
        headers_list = [
            "Date", "Ref No", "MC #", "Product Code", "Lot Number",
            "Processing Start", "Processing End", "Processing Duration",
            "Processed By", "Output QTY",
            "Cleaning Start", "Cleaning End", "Cleaning Duration",
            "Cleaning RM", "Cleaning QTY", "Remarks"
        ]
        self.table.setHorizontalHeaderLabels(headers_list)

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()

        # --- MODIFICATION START: Implement balanced, multi-column stretching ---

        # Define which columns should stretch to fill available space.
        # These are typically columns with variable-length text.
        stretch_columns = {"Product Code", "Lot Number", "Cleaning RM"}

        # Set the resize mode for each column individually
        for i, header_text in enumerate(headers_list):
            if header_text in stretch_columns:
                # These columns will share the extra space, making the layout balanced
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                # These columns will be sized based on their content and then
                # the user can resize them if they wish.
                header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
        # --- MODIFICATION END ---

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)


    def clear_filters(self):
        self.current_filters = {}
        self.load_data()
        QMessageBox.information(self, "Filters Cleared", "All filters have been removed.")

    def load_data(self):
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

    def _create_table_item(self, value):
        """Creates a QTableWidgetItem and sets its data correctly for sorting."""
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
                        btn.setObjectName("RemarksButton")
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
        
        # This still auto-fits the 'Interactive' columns to their content.
        # The 'Stretch' columns will handle the rest of the space.
        self.table.resizeColumnsToContents()
        self.table.setSortingEnabled(True)

    def show_remarks(self, remarks_text: str):
        dialog = RemarksViewerDialog(remarks_text, self)
        dialog.exec()

    def open_filter_dialog(self):
        """Opens the modal dialog for setting filters."""

        dialog = FilterDialog(self.machine_list, self.current_filters, self)

        if dialog.exec():
            print("HELLO")
            self.current_filters = dialog.get_filters()

            # --- DEBUGGING STEP ---
            # This will print the exact dictionary being sent to the database function.
            # If this is empty when you've filled the dialog, the problem is in widgets.py.
            print("--- DEBUG: Filters being applied ---")
            print(self.current_filters)
            print("------------------------------------")

            self.load_data() # Reload data with new filters

   

    def open_restore_dialog(self):
        pass

    def export_to_excel(self):
        pass

    def show_context_menu(self, pos):
        pass

    def get_id_from_selected_row(self) -> int | None:
        pass

    def edit_selected_record(self):
        pass

    def delete_selected_record(self):
        pass