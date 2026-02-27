import os
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QHeaderView,
    QMessageBox, QGroupBox, QDateEdit, QGridLayout, QFrame,
    QCheckBox, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QBrush

import qtawesome as qta

# Custom Widgets
from app.widgets.smart_combo_box import SmartComboBox
from .ops import get_benchmark_data, get_filter_options, search_formulas
from .exporter import BenchmarkExporter


# --- THREADS (Unchanged) ---
class FormulaSearchWorker(QThread):
    results_ready = pyqtSignal(list)

    def __init__(self, session_factory, search_term):
        super().__init__()
        self.session_factory = session_factory
        self.search_term = search_term

    def run(self):
        session = self.session_factory()
        try:
            # Passing empty search term loads initial list
            results = search_formulas(session, self.search_term)
            self.results_ready.emit(results)
        except:
            self.results_ready.emit([])
        finally:
            session.close()


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


# --- MAIN VIEW ---
class MixerBenchmarkView(QWidget):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.summary_valid = pd.DataFrame()
        self.summary_invalid = pd.DataFrame()
        self.raw_df = pd.DataFrame()
        self.search_worker = None

        self.init_ui()
        self.apply_styles()
        self.load_initial_options()

    def apply_styles(self):
        css_path = os.path.join(os.path.dirname(__file__), "styles.css")  # Ensure extension is correct
        if os.path.exists(css_path):
            with open(css_path, "r") as f:
                self.setStyleSheet(f.read())

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- 1. FILTER CARD ---
        filter_group = QGroupBox()
        main_filter_layout = QVBoxLayout(filter_group)
        main_filter_layout.setContentsMargins(15, 0, 15, 0)
        main_filter_layout.setSpacing(10)

        # --- Grid for Inputs ---
        grid_layout = QGridLayout()
        grid_layout.setVerticalSpacing(10)
        grid_layout.setHorizontalSpacing(10)

        # Initialize Inputs
        self.date_from = QDateEdit(calendarPopup=True, date=QDate.currentDate().addMonths(-1))
        self.date_to = QDateEdit(calendarPopup=True, date=QDate.currentDate())

        self.combo_product = SmartComboBox()
        self.combo_product.setPlaceholderText("Select Product...")

        self.combo_formula = SmartComboBox()
        self.combo_formula.setPlaceholderText("Type to search...")  # Changed hint
        self.combo_formula.full_search_requested.connect(self.on_formula_search)

        self.combo_machine = SmartComboBox()
        self.combo_machine.setPlaceholderText("Select Machine...")

        self.chk_include_null = QCheckBox("Include 'Unspecified'")
        self.chk_include_null.setChecked(True)
        self.chk_include_zero = QCheckBox("Include '0' Values")
        self.chk_include_zero.setChecked(True)

        self.btn_refresh = QPushButton("Generate", icon=qta.icon("fa5s.sync-alt", color="white"))
        self.btn_refresh.setObjectName("BtnRefresh")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.start_data_load)
        self.btn_refresh.setFixedHeight(35)

        self.btn_export = QPushButton("Export", icon=qta.icon("fa5s.file-excel", color="white"))
        self.btn_export.setObjectName("BtnExport")
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self.export_to_excel)
        self.btn_export.setFixedHeight(35)

        # --- Helper to create Label+Input Stack ---
        def create_field_box(label_text, widget):
            container = QWidget()
            layout = QVBoxLayout(container)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)

            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #64748b; font-weight: bold; font-size: 11px; text-transform: uppercase;")

            layout.addWidget(lbl)
            layout.addWidget(widget)
            return container

        # --- Placing Widgets in Grid ---
        grid_layout.addWidget(create_field_box("Start Date", self.date_from), 0, 0)
        grid_layout.addWidget(create_field_box("End Date", self.date_to), 0, 1)

        grid_layout.addWidget(create_field_box("Product Code", self.combo_product), 0, 2)
        grid_layout.addWidget(create_field_box("Machine", self.combo_machine), 0, 3)
        grid_layout.addWidget(create_field_box("Formula No", self.combo_formula), 0, 4)

        main_filter_layout.addLayout(grid_layout)

        # --- Bottom Row ---
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(20)
        bottom_row.addWidget(self.chk_include_null)
        bottom_row.addWidget(self.chk_include_zero)
        bottom_row.addStretch()
        bottom_row.addWidget(self.btn_refresh)
        bottom_row.addWidget(self.btn_export)

        main_filter_layout.addLayout(bottom_row)
        main_layout.addWidget(filter_group)

        # --- 2. PROGRESS ---
        self.loader = QProgressBar()
        self.loader.setRange(0, 0)
        self.loader.setFixedHeight(3)
        self.loader.setTextVisible(False)
        self.loader.setStyleSheet(
            "QProgressBar {border: none; background: transparent;} QProgressBar::chunk { background: #3b82f6; }")
        self.loader.hide()
        main_layout.addWidget(self.loader)

        # --- 3. TABLE ---
        self.tree = QTreeWidget()
        self.tree.setObjectName("BenchmarkTable")
        self.tree.setHeaderLabels([
            "Product Code", "Machine", "Formula",
            "Output (kg/hr)", "Clean Time", "Clean Mat", "Yield %", "Details / Remarks"
        ])
        self.tree.setAlternatingRowColors(True)
        self.tree.setIndentation(15)

        header = self.tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setFixedHeight(30)
        header.resizeSection(7, 300)  # Give Remarks more space

        main_layout.addWidget(self.tree, 1)

        # --- 4. STAT CARDS ---
        stats_container = QWidget()
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(0, 5, 0, 0)
        stats_layout.setSpacing(0)

        def create_stat_card(title, color):
            card = QFrame()
            card.setObjectName("StatCard")
            card.setFixedHeight(70)

            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(10, 10, 10, 10)

            vbox = QVBoxLayout()
            vbox.setSpacing(2)

            lbl_title = QLabel(title)
            lbl_title.setObjectName("CardTitle")

            lbl_value = QLabel("-")
            lbl_value.setObjectName("CardValue")
            lbl_value.setStyleSheet(f"color: {color};")

            vbox.addWidget(lbl_title)
            vbox.addWidget(lbl_value)
            vbox.addStretch()

            card_layout.addLayout(vbox)
            return card, lbl_value

        footer_group = QGroupBox()
        footer_layout = QHBoxLayout(footer_group)
        footer_layout.setContentsMargins(10, 0, 10, 0)
        footer_layout.setSpacing(10)

        card_out, self.lbl_std_output = create_stat_card("AVG Output/hr Deviation", "#2563eb")
        card_time, self.lbl_std_ct = create_stat_card("AVG Cleaning Time Deviation", "#d97706")
        card_mat, self.lbl_std_cm = create_stat_card("AVG Cleaning Material Used", "#059669")
        card_yield, self.lbl_std_yield = create_stat_card("Yield Deviation", "#dc2626")

        footer_layout.addWidget(card_out)
        footer_layout.addWidget(card_time)
        footer_layout.addWidget(card_mat)
        footer_layout.addWidget(card_yield)

        main_layout.addWidget(footer_group)

    # --- LOGIC ---
    def load_initial_options(self):
        session = self.Session()
        try:
            opts = get_filter_options(session)
            self.combo_machine.populate_initial(opts["machines"])
            self.combo_product.populate_initial(opts["products"])

            # FIX 1: Pre-populate Formula Box with top 50
            initial_formulas = search_formulas(session, "")
            self.combo_formula.populate_initial(initial_formulas)

        except Exception as e:
            print(f"Error: {e}")
        finally:
            session.close()

    def on_formula_search(self, term):
        if self.search_worker and self.search_worker.isRunning(): return
        self.search_worker = FormulaSearchWorker(self.Session, term)
        self.search_worker.results_ready.connect(self.combo_formula.update_with_search_results)
        self.search_worker.start()

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
        QMessageBox.critical(self, "Error", f"An error occurred:\n{message}")

    def on_load_finished(self):
        self.loader.hide()
        self.btn_refresh.setEnabled(True)
        self.btn_export.setEnabled(True)

    def populate_tree(self):
        self.tree.setUpdatesEnabled(False)

        # --- YIELD REMARK LOGIC ---
        def get_yield_remark_and_color(yield_val):
            if pd.isna(yield_val): return "No Yield Data", "#6c757d"  # Gray

            if yield_val >= 95:
                return "Acceptable yield. Within normal process limits.", "#198754"  # Green
            elif yield_val >= 90:
                return "Low yield. Monitoring required.", "#d97706"  # Dark Gold
            elif yield_val >= 85:
                return "Alarming yield. Investigation required.", "#fd7e14"  # Orange
            else:
                return "Critical yield loss. Immediate action required.", "#dc3545"  # Red

        def add_rows(df, is_valid):
            for _, row in df.iterrows():
                # --- PARENT ROW ---
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

                # Parent Details: Just the count
                count_str = f"{row['record_count']} batches"
                if not is_valid: count_str += " (Unspec Yield)"
                item.setText(7, count_str)

                # Parent Style (Standard Black)
                for i in range(8):
                    font = item.font(i)
                    font.setBold(True)
                    item.setFont(i, font)
                    item.setBackground(i, QColor("#ffffff"))
                    item.setForeground(i, QColor("#2c3e50"))  # Standard Dark Gray

                # --- CHILD ROWS (Sub Records) ---
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
                    if pd.notna(y_raw):
                        child.setText(6, f"{y_raw:.2f}%")
                        # --- REMARK LOGIC ONLY FOR CHILDREN ---
                        rem_text, rem_color_hex = get_yield_remark_and_color(y_raw)
                        child.setText(7, rem_text)
                        child.setForeground(7, QBrush(QColor(rem_color_hex)))
                    else:
                        child.setText(6, "-")
                        child.setText(7, "-")

                    # Child Style (Standard for other columns)
                    bg_color = QColor("#f8f9fa")
                    text_color = QColor("#5f6368")
                    for k in range(7):  # Only 0-6 get standard color
                        child.setBackground(k, bg_color)
                        child.setForeground(k, text_color)
                    # Col 7 background matches, but foreground set by remark logic
                    child.setBackground(7, bg_color)

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

            s_out = 0.0 if pd.isna(s_out) else s_out
            s_ct = 0.0 if pd.isna(s_ct) else s_ct
            s_cm = 0.0 if pd.isna(s_cm) else s_cm
            s_yld = 0.0 if pd.isna(s_yld) else s_yld

            self.lbl_std_output.setText(f"±{s_out:.2f}")
            self.lbl_std_ct.setText(f"±{s_ct:.2f}")
            self.lbl_std_cm.setText(f"±{s_cm:.2f}")
            self.lbl_std_yield.setText(f"±{s_yld:.2f}")
        except:
            pass

    def export_to_excel(self):
        if self.summary_valid.empty and self.summary_invalid.empty: return
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Save Report",
                                              f"Mixer_Benchmark_{QDate.currentDate().toString('yyyy-MM-dd')}.xlsx",
                                              "Excel Files (*.xlsx)")
        if path:
            try:
                BenchmarkExporter().export(self.summary_valid, self.summary_invalid, self.raw_df, path)
                QMessageBox.information(self, "Success", "Export Complete!")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))