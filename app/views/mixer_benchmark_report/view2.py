import os
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QHeaderView,
    QMessageBox, QGroupBox, QDateEdit, QGridLayout, QFrame,
    QCheckBox, QProgressBar, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QColor

import qtawesome as qta

# Custom Widgets
from app.widgets.smart_combo_box import SmartComboBox
from .ops import get_benchmark_data, get_filter_options
from .exporter import BenchmarkExporter


# --- WORKER THREAD ---
class ReportLoaderThread(QThread):
    data_ready = pyqtSignal(object, object, object)
    error_occurred = pyqtSignal(str)

    def __init__(self, session_factory, filters):
        super().__init__()
        self.session_factory = session_factory
        self.filters = filters

    def run(self):
        session = self.session_factory()
        try:
            valid, invalid, raw = get_benchmark_data(session, self.filters)
            self.data_ready.emit(valid, invalid, raw)
        except Exception as e:
            import traceback
            self.error_occurred.emit(str(e) + "\n" + traceback.format_exc())
        finally:
            session.close()


class MixerBenchmarkView(QWidget):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.Session = session_factory

        self.summary_valid = pd.DataFrame()
        self.summary_invalid = pd.DataFrame()
        self.raw_df = pd.DataFrame()

        self.init_ui()
        self.apply_styles()
        self.load_initial_options()

    def apply_styles(self):
        css_path = os.path.join(os.path.dirname(__file__), "styles.qss")
        if os.path.exists(css_path):
            with open(css_path, "r") as f:
                self.setStyleSheet(f.read())

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(20)  # More breathing room
        main_layout.setContentsMargins(30, 30, 30, 30)

        # --- HEADER ---
        header_layout = QHBoxLayout()
        title_icon = QLabel()
        title_icon.setPixmap(qta.icon("fa5s.chart-bar", color="#3b82f6").pixmap(32, 32))

        title = QLabel("Mixer Benchmark Report")
        title.setStyleSheet("font-size: 20pt; font-weight: 800; color: #1e293b; font-family: 'Segoe UI';")

        header_layout.addWidget(title_icon)
        header_layout.addWidget(title)
        header_layout.addStretch()
        main_layout.addLayout(header_layout)

        # --- FILTER CARD ---
        filter_group = QGroupBox("Report Criteria")
        filter_layout = QGridLayout(filter_group)
        filter_layout.setSpacing(15)
        filter_layout.setContentsMargins(20, 25, 20, 20)  # Top margin for title

        self.date_from = QDateEdit(calendarPopup=True, date=QDate.currentDate().addMonths(-1))
        self.date_to = QDateEdit(calendarPopup=True, date=QDate.currentDate())

        self.combo_product = SmartComboBox()
        self.combo_product.setPlaceholderText("Select Product...")

        self.combo_formula = SmartComboBox()
        self.combo_formula.setPlaceholderText("Select Formula...")

        self.combo_machine = SmartComboBox()
        self.combo_machine.setPlaceholderText("Select Machine...")

        self.chk_include_null = QCheckBox("Include 'Unspecified' Formulas")
        self.chk_include_null.setChecked(True)
        self.chk_include_zero = QCheckBox("Include '0' Value Formulas")
        self.chk_include_zero.setChecked(True)

        self.btn_refresh = QPushButton("Generate Report", icon=qta.icon("fa5s.sync-alt", color="white"))
        self.btn_refresh.setObjectName("BtnRefresh")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.start_data_load)

        self.btn_export = QPushButton("Export to Excel", icon=qta.icon("fa5s.file-excel", color="white"))
        self.btn_export.setObjectName("BtnExport")
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self.export_to_excel)

        # Labels (Styled by QSS)
        filter_layout.addWidget(QLabel("Date From:"), 0, 0)
        filter_layout.addWidget(QLabel("Date To:"), 0, 1)
        filter_layout.addWidget(QLabel("Product Code:"), 0, 2)
        filter_layout.addWidget(QLabel("Formula No:"), 0, 3)
        filter_layout.addWidget(QLabel("Machine:"), 0, 4)

        # Inputs
        filter_layout.addWidget(self.date_from, 1, 0)
        filter_layout.addWidget(self.date_to, 1, 1)
        filter_layout.addWidget(self.combo_product, 1, 2)
        filter_layout.addWidget(self.combo_formula, 1, 3)
        filter_layout.addWidget(self.combo_machine, 1, 4)

        # Controls Row
        ctrl_layout = QHBoxLayout()
        ctrl_layout.addWidget(self.chk_include_null)
        ctrl_layout.addSpacing(15)
        ctrl_layout.addWidget(self.chk_include_zero)
        ctrl_layout.addStretch()
        ctrl_layout.addWidget(self.btn_refresh)
        ctrl_layout.addWidget(self.btn_export)

        filter_layout.addLayout(ctrl_layout, 2, 0, 1, 5)
        main_layout.addWidget(filter_group)

        # --- PROGRESS BAR ---
        self.loader = QProgressBar()
        self.loader.setRange(0, 0)
        self.loader.setTextVisible(False)
        self.loader.setFixedHeight(4)  # Thin, modern line
        self.loader.setStyleSheet(
            "QProgressBar {border: none; background: #e0e0e0; border-radius: 2px;} QProgressBar::chunk { background: #3b82f6; border-radius: 2px;}")
        self.loader.hide()
        main_layout.addWidget(self.loader)

        # --- REPORT TABLE ---
        self.tree = QTreeWidget()
        self.tree.setObjectName("BenchmarkTable")
        self.tree.setHeaderLabels([
            "Product", "Machine", "Formula",
            "Avg Output/Hr", "Avg Clean Time", "Avg Clean Mat", "Avg Yield %", "Details"
        ])
        self.tree.setAlternatingRowColors(True)
        self.tree.setIndentation(20)

        # Header setup
        header = self.tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setStretchLastSection(True)
        header.setFixedHeight(35)

        main_layout.addWidget(self.tree, 1)

        # --- FOOTER STATS CARD ---
        self.stats_frame = QFrame()
        self.stats_frame.setObjectName("StatsFooter")
        stats_layout = QHBoxLayout(self.stats_frame)
        stats_layout.setContentsMargins(20, 15, 20, 15)

        stats_layout.addWidget(QLabel("Standard Deviation (Valid Yields):", objectName="StatLabel"))

        # Values
        self.lbl_std_output = QLabel("-", objectName="StatValue")
        self.lbl_std_ct = QLabel("-", objectName="StatValue")
        self.lbl_std_cm = QLabel("-", objectName="StatValue")
        self.lbl_std_yield = QLabel("-", objectName="StatValue")

        # Spacers and Pairs
        stats_layout.addStretch(1)

        stats_layout.addWidget(QLabel("Output:", objectName="StatLabel"))
        stats_layout.addSpacing(5)
        stats_layout.addWidget(self.lbl_std_output)
        stats_layout.addSpacing(30)

        stats_layout.addWidget(QLabel("Time:", objectName="StatLabel"))
        stats_layout.addSpacing(5)
        stats_layout.addWidget(self.lbl_std_ct)
        stats_layout.addSpacing(30)

        stats_layout.addWidget(QLabel("Material:", objectName="StatLabel"))
        stats_layout.addSpacing(5)
        stats_layout.addWidget(self.lbl_std_cm)
        stats_layout.addSpacing(30)

        stats_layout.addWidget(QLabel("Yield:", objectName="StatLabel"))
        stats_layout.addSpacing(5)
        stats_layout.addWidget(self.lbl_std_yield)

        main_layout.addWidget(self.stats_frame)

    def load_initial_options(self):
        session = self.Session()
        try:
            opts = get_filter_options(session)
            self.combo_machine.populate_initial(opts["machines"])
            self.combo_product.populate_initial(opts["products"])
            self.combo_formula.populate_initial(opts["formulas"])
        except Exception as e:
            print(f"Error loading filters: {e}")
        finally:
            session.close()

    def start_data_load(self):
        self.tree.clear()
        self.loader.show()
        self.btn_refresh.setEnabled(False)
        self.btn_export.setEnabled(False)

        filters = {
            "date_from": self.date_from.date().toPyDate(),
            "date_to": self.date_to.date().toPyDate(),
            "machine": self.combo_machine.currentText(),
            "product_code": self.combo_product.currentText(),
            "formula_no": self.combo_formula.currentText(),
            "include_null": self.chk_include_null.isChecked(),
            "include_zero": self.chk_include_zero.isChecked()
        }

        self.worker = ReportLoaderThread(self.Session, filters)
        self.worker.data_ready.connect(self.on_data_loaded)
        self.worker.error_occurred.connect(self.on_load_error)
        self.worker.finished.connect(self.on_load_finished)
        self.worker.start()

    def on_data_loaded(self, valid, invalid, raw):
        self.summary_valid = valid
        self.summary_invalid = invalid
        self.raw_df = raw

        if valid.empty and invalid.empty:
            QMessageBox.information(self, "No Data", "No records found matching your filters.")
        else:
            self.populate_tree()
            self.update_footer_stats()

    def on_load_error(self, message):
        QMessageBox.critical(self, "Calculation Error", f"An error occurred:\n{message}")

    def on_load_finished(self):
        self.loader.hide()
        self.btn_refresh.setEnabled(True)
        self.btn_export.setEnabled(True)

    def populate_tree(self):
        self.tree.setUpdatesEnabled(False)

        def add_rows(df, is_valid):
            for _, row in df.iterrows():
                item = QTreeWidgetItem(self.tree)
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

                count_str = f"{row['record_count']} batches"
                if not is_valid: count_str += " (Unspec Yield)"
                item.setText(7, count_str)

                # Parent Styling: Bold and Darker Text
                for i in range(8):
                    font = item.font(i)
                    font.setBold(True)
                    item.setFont(i, font)
                    # We leave background transparent to let alternating colors work
                    # Or force white if we prefer card look
                    item.setBackground(i, QColor("#ffffff"))
                    item.setForeground(i, QColor("#1e293b"))

                # --- Drill Down Children ---
                subset = self.raw_df[
                    (self.raw_df["product_code"] == row["product_code"]) &
                    (self.raw_df["machine_name"] == row["machine_name"]) &
                    (self.raw_df["formula_no"] == row["formula_no"])
                    ]

                for _, det in subset.iterrows():
                    child = QTreeWidgetItem(item)
                    child.setText(0, str(det["date"]))
                    child.setText(1, str(det["reference_no"]))
                    child.setText(2, str(det["lot_no"]))
                    child.setText(3, f"{det['output_rate_hr']:.2f}")
                    child.setText(4, f"{det['cleaning_mins']:.2f}")
                    child.setText(5, f"{det['cleaning_qty']:.2f}")

                    y_raw = det.get("yield_pct")
                    child.setText(6, f"{y_raw:.2f}%" if pd.notna(y_raw) else "-")

                    # Child Styling: Light Gray Background
                    child_bg = QColor("#f8fafc")
                    child_text = QColor("#64748b")
                    for k in range(8):
                        child.setBackground(k, child_bg)
                        child.setForeground(k, child_text)

        add_rows(self.summary_valid, True)
        add_rows(self.summary_invalid, False)

        self.tree.expandAll()
        for i in range(8): self.tree.resizeColumnToContents(i)
        self.tree.setUpdatesEnabled(True)

    def update_footer_stats(self):
        if self.summary_valid.empty:
            for lbl in [self.lbl_std_output, self.lbl_std_ct, self.lbl_std_cm, self.lbl_std_yield]:
                lbl.setText("-")
            return

        try:
            s_out = self.summary_valid["avg_output_rate"].std()
            s_ct = self.summary_valid["avg_clean_time"].std()
            s_cm = self.summary_valid["avg_clean_mat"].std()
            s_yld = self.summary_valid["avg_yield"].std()

            # Formatting with +/- sign
            s_out = 0.0 if pd.isna(s_out) else s_out
            s_ct = 0.0 if pd.isna(s_ct) else s_ct
            s_cm = 0.0 if pd.isna(s_cm) else s_cm
            s_yld = 0.0 if pd.isna(s_yld) else s_yld

            self.lbl_std_output.setText(f"±{s_out:.2f}")
            self.lbl_std_ct.setText(f"±{s_ct:.2f}")
            self.lbl_std_cm.setText(f"±{s_cm:.2f}")
            self.lbl_std_yield.setText(f"±{s_yld:.2f}")
        except Exception as e:
            print(f"Stats Error: {e}")

    def export_to_excel(self):
        if self.summary_valid.empty and self.summary_invalid.empty:
            return

        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Save Report",
                                              f"Mixer_Benchmark_{QDate.currentDate().toString('yyyy-MM-dd')}.xlsx",
                                              "Excel Files (*.xlsx)")
        if path:
            try:
                BenchmarkExporter().export(self.summary_valid, self.summary_invalid, self.raw_df, path)
                QMessageBox.information(self, "Success", "Report exported successfully!")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))