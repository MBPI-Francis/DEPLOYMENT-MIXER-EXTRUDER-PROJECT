# app/views/mixer_report/main.py

import os
from typing import Type
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QGroupBox, QLabel, QComboBox,
    QDateEdit, QPushButton, QFileDialog, QMessageBox, QMenu, QCheckBox, QHBoxLayout
)
from PyQt6.QtCore import QDate
from PyQt6.QtGui import QAction

from .ops import get_report_prerequisites, get_mixer_summary_report_data
from .exporter import ReportExporter


class MixerReportView(QWidget):
    def __init__(self, session_factory: Type[Session], parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.setObjectName("MixerReportView")

        main_layout = QVBoxLayout(self)

        # --- Filter UI ---
        filter_box = QGroupBox("1. Filter Data")
        filter_box.setObjectName("FilterBox")
        filter_layout = QGridLayout(filter_box)

        self.date_from = QDateEdit(calendarPopup=True, date=QDate.currentDate().addMonths(-1))
        self.date_to = QDateEdit(calendarPopup=True, date=QDate.currentDate())
        self.machine_combo = QComboBox()
        self.product_code_combo = QComboBox()

        filter_layout.addWidget(QLabel("Date From:"), 0, 0);
        filter_layout.addWidget(self.date_from, 0, 1)
        filter_layout.addWidget(QLabel("Date To:"), 0, 2);
        filter_layout.addWidget(self.date_to, 0, 3)
        filter_layout.addWidget(QLabel("Machine Number:"), 1, 0);
        filter_layout.addWidget(self.machine_combo, 1, 1)
        filter_layout.addWidget(QLabel("Product Code:"), 1, 2);
        filter_layout.addWidget(self.product_code_combo, 1, 3)

        # --- NEW: Grouping UI ---
        grouping_box = QGroupBox("2. Group Report By (Select one or more)")
        grouping_layout = QHBoxLayout(grouping_box)
        # Define the meaningful columns the user can group by
        self.groupable_columns = ["Machine Number", "Product Code", "Formula No"]
        self.grouping_checkboxes = {}
        for col in self.groupable_columns:
            checkbox = QCheckBox(col)
            self.grouping_checkboxes[col] = checkbox
            grouping_layout.addWidget(checkbox)
        grouping_layout.addStretch()
        # Set a default grouping
        self.grouping_checkboxes["Machine Number"].setChecked(True)
        self.grouping_checkboxes["Product Code"].setChecked(True)

        # --- Export Button ---
        self.export_button = QPushButton("3. Generate and Export Report")
        self.export_button.setObjectName("ExportButton")

        main_layout.addWidget(filter_box)
        main_layout.addWidget(grouping_box)  # Add the new box to the layout
        main_layout.addWidget(self.export_button)
        main_layout.addStretch()
        self.setLayout(main_layout)

        self._load_combobox_data()
        self.export_button.clicked.connect(self.show_export_menu)
        self._load_stylesheet()

    def _load_stylesheet(self):
        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f:
                self.setStyleSheet(f.read())

    def _load_combobox_data(self):
        """Populates filter combo boxes with data from the database."""
        session = self.Session()
        try:
            data = get_report_prerequisites(session)
            self.machine_combo.addItems(["All"] + data["machines"])
            self.product_code_combo.addItems(["All"] + data["product_codes"])
        finally:
            session.close()

    def show_export_menu(self):
        """Creates and shows a menu to choose the export format."""
        export_menu = QMenu(self)
        excel_action = QAction("Export to Excel...", self)
        pdf_action = QAction("Export to PDF...", self)

        excel_action.triggered.connect(lambda: self.run_export(file_type="excel"))
        pdf_action.triggered.connect(lambda: self.run_export(file_type="pdf"))

        export_menu.addAction(excel_action)
        export_menu.addAction(pdf_action)

        # Show the menu below the export button
        menu_pos = self.export_button.mapToGlobal(self.export_button.rect().bottomLeft())
        export_menu.exec(menu_pos)

    def run_export(self, file_type: str):
        """Handles the entire export process, now with dynamic grouping."""
        # 1. Gather filters from the UI
        filters = {
            "date_from": self.date_from.date().toPyDate(),
            "date_to": self.date_to.date().toPyDate(),
            "machine": self.machine_combo.currentText() if self.machine_combo.currentText() != "All" else None,
            "product_code": self.product_code_combo.currentText() if self.product_code_combo.currentText() != "All" else None,
        }

        # --- NEW: Gather selected grouping columns from checkboxes ---
        group_by_cols = [col for col, checkbox in self.grouping_checkboxes.items() if checkbox.isChecked()]
        if not group_by_cols:
            QMessageBox.warning(self, "No Grouping Selected",
                                "Please select at least one column to group the report by.")
            return

        # 2. Get the summary data, passing the grouping columns
        session = self.Session()
        try:
            summary_df = get_mixer_summary_report_data(session, filters, group_by_cols)
        except Exception as e:
            QMessageBox.critical(self, "Data Error", f"An error occurred while generating the report data:\n{e}")
            return
        finally:
            session.close()

        if summary_df.empty:
            QMessageBox.warning(self, "No Data", "No data found for the selected filters.")
            return

        # 3. Get save file path from user
        title = f"Mixer Performance Summary Report from {filters['date_from']} to {filters['date_to']}"

        if file_type == "excel":
            ext = "Excel Files (*.xlsx)"
            default_name = f"Mixer_Report_{QDate.currentDate().toString('yyyy-MM-dd')}.xlsx"
        else:  # pdf
            ext = "PDF Files (*.pdf)"
            default_name = f"Mixer_Report_{QDate.currentDate().toString('yyyy-MM-dd')}.pdf"

        filepath, _ = QFileDialog.getSaveFileName(self, f"Save {file_type.title()} Report", default_name, ext)
        if not filepath:
            return

        # 4. Export the file
        try:
            exporter = ReportExporter()
            if file_type == "excel":
                exporter.export_to_excel(summary_df, filepath, title)
            else:
                exporter.export_to_pdf(summary_df, filepath, title)
            QMessageBox.information(self, "Success", f"Report successfully saved to:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"An error occurred during export:\n{e}")