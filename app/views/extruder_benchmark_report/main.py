# app/views/extruder_benchmark_report/main.py

import pandas as pd
from typing import Type
from sqlalchemy.orm import Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QHeaderView,
    QMessageBox, QGroupBox, QDateEdit, QComboBox, QGridLayout, QFrame, QCheckBox, QFileDialog
)
from PyQt6.QtCore import Qt, QDate
import qtawesome as qta

# Import logic from sibling files
from .ops import get_benchmark_data, get_filter_options
from .exporter import ExtruderBenchmarkExporter


class ExtruderReportView(QWidget):
    def __init__(self, session_factory: Type[Session], parent=None):
        super().__init__(parent)
        self.Session = session_factory

        # Data containers
        self.summary_valid = pd.DataFrame()
        self.summary_invalid = pd.DataFrame()
        self.raw_df = pd.DataFrame()

        self._setup_ui()
        self._load_filter_options()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # --- 1. FILTERS GROUP ---
        filter_group = QGroupBox("Extruder Benchmark Filters")
        filter_layout = QGridLayout(filter_group)
        filter_layout.setContentsMargins(10, 10, 10, 10)

        # Date Inputs
        self.date_from = QDateEdit(calendarPopup=True, date=QDate.currentDate().addMonths(-1))
        self.date_to = QDateEdit(calendarPopup=True, date=QDate.currentDate())

        # Combos
        self.combo_product = QComboBox()
        self.combo_formula = QComboBox()
        self.combo_machine = QComboBox()

        # Checkboxes
        self.chk_include_null = QCheckBox("Include 'Unspecified' Formulas")
        self.chk_include_null.setChecked(True)
        self.chk_include_zero = QCheckBox("Include '0' Value Formulas")
        self.chk_include_zero.setChecked(True)

        # Buttons
        btn_refresh = QPushButton("Generate Report", icon=qta.icon("fa5s.search"))
        btn_refresh.clicked.connect(self.load_data)

        btn_export = QPushButton("Export Excel", icon=qta.icon("fa5s.file-excel"))
        btn_export.clicked.connect(self.export_to_excel)

        # Place Widgets in Grid
        filter_layout.addWidget(QLabel("Date From:"), 0, 0)
        filter_layout.addWidget(self.date_from, 0, 1)
        filter_layout.addWidget(QLabel("Date To:"), 0, 2)
        filter_layout.addWidget(self.date_to, 0, 3)

        filter_layout.addWidget(QLabel("Product:"), 1, 0)
        filter_layout.addWidget(self.combo_product, 1, 1)
        filter_layout.addWidget(QLabel("Formula:"), 1, 2)
        filter_layout.addWidget(self.combo_formula, 1, 3)
        filter_layout.addWidget(QLabel("Machine:"), 1, 4)
        filter_layout.addWidget(self.combo_machine, 1, 5)

        # Checkboxes Row
        chk_layout = QHBoxLayout()
        chk_layout.addWidget(self.chk_include_null)
        chk_layout.addWidget(self.chk_include_zero)
        chk_layout.addStretch()
        filter_layout.addLayout(chk_layout, 2, 0, 1, 6)

        # Buttons Row
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        btn_layout.addWidget(btn_refresh)
        btn_layout.addWidget(btn_export)
        filter_layout.addLayout(btn_layout, 3, 0, 1, 6)

        layout.addWidget(filter_group)

        # --- 2. REPORT TABLE ---
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            "Product", "Machine", "Formula",
            "Output (kg/hr)", "Clean Time (min)", "Clean Mat (kg)", "Yield %", "Count"
        ])
        self.tree.setAlternatingRowColors(True)
        # Resize logic
        header = self.tree.header()
        for i in range(8):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.tree, 1)

        # --- 3. STATS FOOTER ---
        self.footer_frame = QFrame()
        self.footer_frame.setStyleSheet("background-color: #f0f0f0; border-top: 1px solid #ccc;")
        footer_layout = QHBoxLayout(self.footer_frame)
        footer_layout.addWidget(QLabel("<b>Std Dev (Valid Yields):</b>"))

        self.lbl_std_output = QLabel("-")
        self.lbl_std_ct = QLabel("-")
        self.lbl_std_cm = QLabel("-")
        self.lbl_std_yield = QLabel("-")

        for lbl in [self.lbl_std_output, self.lbl_std_ct, self.lbl_std_cm, self.lbl_std_yield]:
            lbl.setStyleSheet("margin-left: 10px; color: #333;")
            footer_layout.addWidget(lbl)

        footer_layout.addStretch()
        layout.addWidget(self.footer_frame)

    def _load_filter_options(self):
        """Loads data into dropdowns on init."""
        session = self.Session()
        try:
            options = get_filter_options(session)
            self.combo_machine.addItems(options["machines"])
            self.combo_product.addItems(options["products"])
            self.combo_formula.addItems(options["formulas"])
        except Exception as e:
            print(f"Error loading filters: {e}")
        finally:
            session.close()

    def load_data(self):
        self.tree.clear()
        session = self.Session()
        try:
            filters = {
                "date_from": self.date_from.date().toPyDate(),
                "date_to": self.date_to.date().toPyDate(),
                "machine": self.combo_machine.currentText(),
                "product_code": self.combo_product.currentText(),
                "formula_no": self.combo_formula.currentText(),
                "include_null": self.chk_include_null.isChecked(),
                "include_zero": self.chk_include_zero.isChecked()
            }

            # Get 3 dataframes: Valid Summary, Invalid Summary, and Raw Data
            self.summary_valid, self.summary_invalid, self.raw_df = get_benchmark_data(session, filters)

            if self.summary_valid.empty and self.summary_invalid.empty:
                QMessageBox.information(self, "No Data", "No records found matching filters.")
                self._update_footer(empty=True)
                return

            self.populate_tree()
            self._update_footer()

        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Error generating report:\n{e}")
        finally:
            session.close()

    def _update_footer(self, empty=False):
        if empty or self.summary_valid.empty:
            self.lbl_std_output.setText("Output: -")
            self.lbl_std_ct.setText("Clean Time: -")
            self.lbl_std_cm.setText("Clean Mat: -")
            self.lbl_std_yield.setText("Yield: -")
            return
        try:
            s_out = self.summary_valid["avg_output_rate"].std()
            s_ct = self.summary_valid["avg_clean_time"].std()
            s_cm = self.summary_valid["avg_clean_mat"].std()
            s_yld = self.summary_valid["avg_yield"].std()

            self.lbl_std_output.setText(f"Output: ±{s_out:.2f}")
            self.lbl_std_ct.setText(f"Clean Time: ±{s_ct:.2f}")
            self.lbl_std_cm.setText(f"Clean Mat: ±{s_cm:.2f}")
            self.lbl_std_yield.setText(f"Yield: ±{s_yld:.2f}")
        except:
            pass

    def populate_tree(self):
        self.tree.setUpdatesEnabled(False)

        def add_summary_rows(df):
            for _, row in df.iterrows():
                item = QTreeWidgetItem(self.tree)
                # Ensure strings to prevent crashes
                item.setText(0, str(row["product_code"]))
                item.setText(1, str(row["machine_name"]))
                item.setText(2, str(row["formula_no"]))
                item.setText(3, f"{row['avg_output_rate']:.2f}")
                item.setText(4, f"{row['avg_clean_time']:.2f}")
                item.setText(5, f"{row['avg_clean_mat']:.2f}")

                y_val = row.get('avg_yield')
                if pd.notna(y_val):
                    item.setText(6, f"{y_val:.2f}%")
                else:
                    item.setText(6, "N/A")
                item.setText(7, str(row["record_count"]))

                # Drill Down Logic
                subset = self.raw_df[
                    (self.raw_df["product_code"] == row["product_code"]) &
                    (self.raw_df["machine_name"] == row["machine_name"]) &
                    (self.raw_df["formula_no"] == row["formula_no"])
                    ]

                for _, det in subset.iterrows():
                    child = QTreeWidgetItem(item)
                    child.setText(0, str(det["report_date"]))
                    child.setText(1, str(det["ref_no"]))
                    child.setText(2, str(det["lot_number"]))
                    child.setText(3, f"{det['output_rate_hr']:.2f}")
                    child.setText(4, f"{det['clean_mins']:.2f}")
                    child.setText(5, f"{det['clean_mat']:.2f}")
                    y_raw = det.get("yield_pct")
                    child.setText(6, f"{y_raw:.2f}%" if pd.notna(y_raw) else "-")

        # Add Valid Yields first, then Unspecified
        add_summary_rows(self.summary_valid)
        add_summary_rows(self.summary_invalid)

        self.tree.expandAll()
        self.tree.setUpdatesEnabled(True)

    def export_to_excel(self):
        if self.summary_valid.empty and self.summary_invalid.empty:
            return

        default_name = f"Extruder_Benchmark_{QDate.currentDate().toString('yyyy-MM-dd')}.xlsx"
        path, _ = QFileDialog.getSaveFileName(self, "Save Report", default_name, "Excel Files (*.xlsx)")

        if path:
            try:
                ExtruderBenchmarkExporter().export(self.summary_valid, self.summary_invalid, self.raw_df, path)
                QMessageBox.information(self, "Success", "Export Complete!")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))