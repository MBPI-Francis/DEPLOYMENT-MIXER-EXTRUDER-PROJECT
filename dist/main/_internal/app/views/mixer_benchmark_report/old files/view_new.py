# import os
# import pandas as pd
# from PyQt6.QtWidgets import (
#     QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
#     QTreeWidget, QTreeWidgetItem, QLabel, QHeaderView,
#     QMessageBox, QGroupBox, QDateEdit, QGridLayout, QFrame,
#     QCheckBox, QProgressBar, QSizePolicy
# )
# from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
# from PyQt6.QtGui import QColor
#
# import qtawesome as qta
#
# # Custom Widgets
# from app.widgets.smart_combo_box import SmartComboBox
# from .ops import get_benchmark_data, get_filter_options, search_formulas
# from .exporter import BenchmarkExporter
#
#
# # --- THREADS (Unchanged) ---
# class FormulaSearchWorker(QThread):
#     results_ready = pyqtSignal(list)
#
#     def __init__(self, session_factory, search_term):
#         super().__init__()
#         self.session_factory = session_factory
#         self.search_term = search_term
#
#     def run(self):
#         session = self.session_factory()
#         try:
#             results = search_formulas(session, self.search_term)
#             self.results_ready.emit(results)
#         except:
#             self.results_ready.emit([])
#         finally:
#             session.close()
#
#
# class ReportLoaderThread(QThread):
#     data_ready = pyqtSignal(object, object, object)
#     error_occurred = pyqtSignal(str)
#
#     def __init__(self, session_factory, filters):
#         super().__init__()
#         self.session_factory = session_factory
#         self.filters = filters
#
#     def run(self):
#         session = self.session_factory()
#         try:
#             valid, invalid, raw = get_benchmark_data(session, self.filters)
#             self.data_ready.emit(valid, invalid, raw)
#         except Exception as e:
#             import traceback
#             self.error_occurred.emit(str(e) + "\n" + traceback.format_exc())
#         finally:
#             session.close()
#
#
# # --- MAIN VIEW ---
# class MixerBenchmarkView(QWidget):
#     def __init__(self, session_factory, parent=None):
#         super().__init__(parent)
#         self.Session = session_factory
#         self.summary_valid = pd.DataFrame()
#         self.summary_invalid = pd.DataFrame()
#         self.raw_df = pd.DataFrame()
#         self.search_worker = None
#
#         self.init_ui()
#         self.apply_styles()
#         self.load_initial_options()
#
#     def apply_styles(self):
#         css_path = os.path.join(os.path.dirname(__file__), "styles.css")
#         if os.path.exists(css_path):
#             with open(css_path, "r") as f:
#                 self.setStyleSheet(f.read())
#
#     def init_ui(self):
#         main_layout = QVBoxLayout(self)
#         main_layout.setSpacing(10)  # Reduced global spacing
#         main_layout.setContentsMargins(15, 15, 15, 15)  # Reduced global margins
#
#         # --- HEADER (Compact) ---
#         header_layout = QHBoxLayout()
#
#         main_layout.addLayout(header_layout)
#
#         # --- 1. FILTER CARD (Compact) ---
#         filter_group = QGroupBox("Filter Criteria")
#         # Tight margins: Top needs space for title (~15-20), others small
#         filter_layout = QGridLayout(filter_group)
#         filter_layout.setContentsMargins(10, 20, 10, 10)
#         filter_layout.setVerticalSpacing(8)  # Tighter rows
#         filter_layout.setHorizontalSpacing(10)
#
#         # Inputs
#         self.date_from = QDateEdit(calendarPopup=True, date=QDate.currentDate().addMonths(-1))
#         self.date_to = QDateEdit(calendarPopup=True, date=QDate.currentDate())
#
#         self.combo_product = SmartComboBox()
#         self.combo_product.setPlaceholderText("Product...")
#
#         self.combo_formula = SmartComboBox()
#         self.combo_formula.setPlaceholderText("Formula...")
#         self.combo_formula.full_search_requested.connect(self.on_formula_search)
#
#         self.combo_machine = SmartComboBox()
#         self.combo_machine.setPlaceholderText("Machine...")
#
#         self.chk_include_null = QCheckBox("Unspecified")
#         self.chk_include_null.setChecked(True)
#         self.chk_include_zero = QCheckBox("0 Value")
#         self.chk_include_zero.setChecked(True)
#
#         self.btn_refresh = QPushButton("Generate", icon=qta.icon("fa5s.sync-alt", color="white"))
#         self.btn_refresh.setObjectName("BtnRefresh")
#         self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
#         self.btn_refresh.clicked.connect(self.start_data_load)
#
#         self.btn_export = QPushButton("Export", icon=qta.icon("fa5s.file-excel", color="white"))
#         self.btn_export.setObjectName("BtnExport")
#         self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
#         self.btn_export.clicked.connect(self.export_to_excel)
#
#         # Row 0: Labels
#         filter_layout.addWidget(QLabel("Date Range:"), 0, 0)
#         filter_layout.addWidget(QLabel("to"), 0, 2)
#         filter_layout.addWidget(QLabel("Product:"), 0, 3)
#         filter_layout.addWidget(QLabel("Formula:"), 0, 4)
#         filter_layout.addWidget(QLabel("Machine:"), 0, 5)
#
#         # Row 1: Inputs
#         filter_layout.addWidget(self.date_from, 0, 1)
#         filter_layout.addWidget(self.date_to, 0,
#                                 3)  # Merged slightly into label row logic for compactness? No, grid is better.
#
#         # Let's re-arrange for maximum compactness: 2 Rows Only.
#
#         # Row 0: Dates & Machine
#         filter_layout.addWidget(QLabel("From:"), 0, 0)
#         filter_layout.addWidget(self.date_from, 0, 1)
#         filter_layout.addWidget(QLabel("To:"), 0, 2)
#         filter_layout.addWidget(self.date_to, 0, 3)
#         filter_layout.addWidget(QLabel("Machine:"), 0, 4)
#         filter_layout.addWidget(self.combo_machine, 0, 5)
#
#         # Row 1: Product, Formula, Buttons
#         filter_layout.addWidget(QLabel("Product:"), 1, 0)
#         filter_layout.addWidget(self.combo_product, 1, 1)
#         filter_layout.addWidget(QLabel("Formula:"), 1, 2)
#         filter_layout.addWidget(self.combo_formula, 1, 3)
#
#         # Checkboxes in Row 1 (Cols 4-5)
#         chk_layout = QHBoxLayout()
#         chk_layout.setSpacing(10)
#         chk_layout.setContentsMargins(0, 0, 0, 0)
#         chk_layout.addWidget(self.chk_include_null)
#         chk_layout.addWidget(self.chk_include_zero)
#         filter_layout.addLayout(chk_layout, 1, 4, 1, 2)
#
#         # Row 2: Buttons (Span all)
#         btn_layout = QHBoxLayout()
#         btn_layout.addStretch()
#         btn_layout.addWidget(self.btn_refresh)
#         btn_layout.addWidget(self.btn_export)
#         filter_layout.addLayout(btn_layout, 2, 0, 1, 6)
#
#         main_layout.addWidget(filter_group)
#
#         # --- 2. PROGRESS BAR ---
#         self.loader = QProgressBar()
#         self.loader.setRange(0, 0)
#         self.loader.setTextVisible(False)
#         self.loader.setFixedHeight(3)
#         self.loader.setStyleSheet(
#             "QProgressBar {border: none; background: #e0e0e0;} QProgressBar::chunk { background: #409eff; }")
#         self.loader.hide()
#         main_layout.addWidget(self.loader)
#
#         # --- 3. TABLE (Expands to fill space) ---
#         self.tree = QTreeWidget()
#         self.tree.setObjectName("BenchmarkTable")
#         self.tree.setHeaderLabels([
#             "Product Code", "Machine", "Formula",
#             "Avg Output/Hr", "Avg Clean Time", "Avg Clean Mat", "Avg Yield %", "Details"
#         ])
#         self.tree.setAlternatingRowColors(True)
#         self.tree.setIndentation(15)
#
#         header = self.tree.header()
#         header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
#         header.setStretchLastSection(True)
#         header.setFixedHeight(30)
#
#         # Stretch factor 1 makes this widget consume all available extra space
#         main_layout.addWidget(self.tree, 1)
#
#         # --- 4. FOOTER STATS (Compact Card) ---
#         self.stats_group = QGroupBox("Standard Deviation (Valid Yields)")
#         self.stats_group.setObjectName("StatsGroup")
#
#         stats_layout = QHBoxLayout(self.stats_group)
#         # Very tight margins for footer
#         stats_layout.setContentsMargins(15, 20, 15, 10)
#         stats_layout.setSpacing(30)
#
#         def create_stat_block(title, obj_name):
#             container = QWidget()
#             vbox = QVBoxLayout(container)
#             vbox.setContentsMargins(0, 0, 0, 0)
#             vbox.setSpacing(2)
#
#             lbl_t = QLabel(title)
#             lbl_t.setObjectName("StatLabel")
#             lbl_t.setAlignment(Qt.AlignmentFlag.AlignCenter)
#
#             lbl_v = QLabel("-")
#             lbl_v.setObjectName("StatValue")
#             lbl_v.setAlignment(Qt.AlignmentFlag.AlignCenter)
#
#             vbox.addWidget(lbl_t)
#             vbox.addWidget(lbl_v)
#             return container, lbl_v
#
#         w_out, self.lbl_std_output = create_stat_block("Output", "StdOutput")
#         w_time, self.lbl_std_ct = create_stat_block("Cleaning Time", "StdTime")
#         w_mat, self.lbl_std_cm = create_stat_block("Cleaning Mat", "StdMat")
#         w_yield, self.lbl_std_yield = create_stat_block("Yield", "StdYield")
#
#         stats_layout.addStretch()
#         stats_layout.addWidget(w_out)
#         stats_layout.addWidget(w_time)
#         stats_layout.addWidget(w_mat)
#         stats_layout.addWidget(w_yield)
#         stats_layout.addStretch()
#
#         main_layout.addWidget(self.stats_group)
#
#     # --- FUNCTIONALITY (Unchanged) ---
#     def load_initial_options(self):
#         session = self.Session()
#         try:
#             opts = get_filter_options(session)
#             self.combo_machine.populate_initial(opts["machines"])
#             self.combo_product.populate_initial(opts["products"])
#         except Exception as e:
#             print(f"Error: {e}")
#         finally:
#             session.close()
#
#     def on_formula_search(self, term):
#         if self.search_worker and self.search_worker.isRunning(): return
#         self.search_worker = FormulaSearchWorker(self.Session, term)
#         self.search_worker.results_ready.connect(self.combo_formula.update_with_search_results)
#         self.search_worker.start()
#
#     def start_data_load(self):
#         self.tree.clear()
#         self.loader.show()
#         self.btn_refresh.setEnabled(False)
#         self.btn_export.setEnabled(False)
#
#         filters = {
#             "date_from": self.date_from.date().toPyDate(),
#             "date_to": self.date_to.date().toPyDate(),
#             "machine": self.combo_machine.currentText(),
#             "product_code": self.combo_product.currentText(),
#             "formula_no": self.combo_formula.currentText(),
#             "include_null": self.chk_include_null.isChecked(),
#             "include_zero": self.chk_include_zero.isChecked()
#         }
#
#         self.worker = ReportLoaderThread(self.Session, filters)
#         self.worker.data_ready.connect(self.on_data_loaded)
#         self.worker.error_occurred.connect(self.on_load_error)
#         self.worker.finished.connect(self.on_load_finished)
#         self.worker.start()
#
#     def on_data_loaded(self, valid, invalid, raw):
#         self.summary_valid = valid
#         self.summary_invalid = invalid
#         self.raw_df = raw
#
#         if valid.empty and invalid.empty:
#             QMessageBox.information(self, "No Data", "No records found matching your filters.")
#         else:
#             self.populate_tree()
#             self.update_footer_stats()
#
#     def on_load_error(self, message):
#         QMessageBox.critical(self, "Error", f"An error occurred:\n{message}")
#
#     def on_load_finished(self):
#         self.loader.hide()
#         self.btn_refresh.setEnabled(True)
#         self.btn_export.setEnabled(True)
#
#     def populate_tree(self):
#         self.tree.setUpdatesEnabled(False)
#
#         def add_rows(df, is_valid):
#             for _, row in df.iterrows():
#                 item = QTreeWidgetItem(self.tree)
#                 item.setText(0, str(row["product_code"]))
#                 item.setText(1, str(row["machine_name"]))
#                 item.setText(2, str(row["formula_no"]))
#                 item.setText(3, f"{row['avg_output_rate']:.2f}")
#                 item.setText(4, f"{row['avg_clean_time']:.2f}")
#                 item.setText(5, f"{row['avg_clean_mat']:.2f}")
#
#                 y_val = row.get('avg_yield')
#                 if pd.notna(y_val):
#                     item.setText(6, f"{y_val:.2f}%")
#                 else:
#                     item.setText(6, "N/A")
#
#                 count_str = f"{row['record_count']} batches"
#                 if not is_valid: count_str += " (Unspec Yield)"
#                 item.setText(7, count_str)
#
#                 for i in range(8):
#                     font = item.font(i)
#                     font.setBold(True)
#                     item.setFont(i, font)
#                     item.setBackground(i, QColor("#ffffff"))
#                     item.setForeground(i, QColor("#2c3e50"))
#
#                 subset = self.raw_df[
#                     (self.raw_df["product_code"] == row["product_code"]) &
#                     (self.raw_df["machine_name"] == row["machine_name"]) &
#                     (self.raw_df["formula_no"] == row["formula_no"])
#                     ]
#
#                 for _, det in subset.iterrows():
#                     child = QTreeWidgetItem(item)
#                     child.setText(0, str(det["date"]))
#                     child.setText(1, str(det["reference_no"]))
#                     child.setText(2, str(det["lot_no"]))
#                     child.setText(3, f"{det['output_rate_hr']:.2f}")
#                     child.setText(4, f"{det['cleaning_mins']:.2f}")
#                     child.setText(5, f"{det['cleaning_qty']:.2f}")
#                     y_raw = det.get("yield_pct")
#                     child.setText(6, f"{y_raw:.2f}%" if pd.notna(y_raw) else "-")
#
#                     bg_color = QColor("#f8f9fa")
#                     text_color = QColor("#5f6368")
#                     for k in range(8):
#                         child.setBackground(k, bg_color)
#                         child.setForeground(k, text_color)
#
#         add_rows(self.summary_valid, True)
#         add_rows(self.summary_invalid, False)
#
#         self.tree.expandAll()
#         for i in range(8): self.tree.resizeColumnToContents(i)
#         self.tree.setUpdatesEnabled(True)
#
#     def update_footer_stats(self):
#         if self.summary_valid.empty:
#             for lbl in [self.lbl_std_output, self.lbl_std_ct, self.lbl_std_cm, self.lbl_std_yield]:
#                 lbl.setText("-")
#             return
#         try:
#             s_out = self.summary_valid["avg_output_rate"].std()
#             s_ct = self.summary_valid["avg_clean_time"].std()
#             s_cm = self.summary_valid["avg_clean_mat"].std()
#             s_yld = self.summary_valid["avg_yield"].std()
#
#             s_out = 0.0 if pd.isna(s_out) else s_out
#             s_ct = 0.0 if pd.isna(s_ct) else s_ct
#             s_cm = 0.0 if pd.isna(s_cm) else s_cm
#             s_yld = 0.0 if pd.isna(s_yld) else s_yld
#
#             self.lbl_std_output.setText(f"±{s_out:.2f}")
#             self.lbl_std_ct.setText(f"±{s_ct:.2f}")
#             self.lbl_std_cm.setText(f"±{s_cm:.2f}")
#             self.lbl_std_yield.setText(f"±{s_yld:.2f}")
#         except:
#             pass
#
#     def export_to_excel(self):
#         if self.summary_valid.empty and self.summary_invalid.empty: return
#         from PyQt6.QtWidgets import QFileDialog
#         path, _ = QFileDialog.getSaveFileName(self, "Save Report",
#                                               f"Mixer_Benchmark_{QDate.currentDate().toString('yyyy-MM-dd')}.xlsx",
#                                               "Excel Files (*.xlsx)")
#         if path:
#             try:
#                 BenchmarkExporter().export(self.summary_valid, self.summary_invalid, self.raw_df, path)
#                 QMessageBox.information(self, "Success", "Export Complete!")
#             except Exception as e:
#                 QMessageBox.critical(self, "Error", str(e))


import os
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel, QHeaderView,
    QMessageBox, QGroupBox, QDateEdit, QGridLayout, QFrame,
    QCheckBox, QProgressBar, QSizePolicy
)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QColor

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
        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f:
                self.setStyleSheet(f.read())

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # --- 1. FILTER CARD ---
        filter_group = QGroupBox("Filter Criteria")
        # Ensure layout doesn't clip the rounded corners
        filter_layout = QGridLayout(filter_group)
        filter_layout.setContentsMargins(15, 25, 15, 15)
        filter_layout.setVerticalSpacing(10)
        filter_layout.setHorizontalSpacing(15)

        # Date Inputs
        self.date_from = QDateEdit(calendarPopup=True, date=QDate.currentDate().addMonths(-1))
        self.date_to = QDateEdit(calendarPopup=True, date=QDate.currentDate())

        # Smart Combos
        self.combo_product = SmartComboBox()
        self.combo_product.setPlaceholderText("Select Product...")

        self.combo_formula = SmartComboBox()
        self.combo_formula.setPlaceholderText("Search Formula...")
        self.combo_formula.full_search_requested.connect(self.on_formula_search)

        self.combo_machine = SmartComboBox()
        self.combo_machine.setPlaceholderText("Select Machine...")

        # Checkboxes
        self.chk_include_null = QCheckBox("Include 'Unspecified'")
        self.chk_include_null.setChecked(True)
        self.chk_include_zero = QCheckBox("Include '0' Values")
        self.chk_include_zero.setChecked(True)

        # Buttons
        self.btn_refresh = QPushButton("Generate", icon=qta.icon("fa5s.sync-alt", color="white"))
        self.btn_refresh.setObjectName("BtnRefresh")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.start_data_load)
        self.btn_refresh.setFixedHeight(32)

        self.btn_export = QPushButton("Export", icon=qta.icon("fa5s.file-excel", color="white"))
        self.btn_export.setObjectName("BtnExport")
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self.export_to_excel)
        self.btn_export.setFixedHeight(32)

        # -- Layout --
        # Row 0: Dates & Machine
        filter_layout.addWidget(QLabel("Date Range:"), 0, 0)
        filter_layout.addWidget(self.date_from, 0, 1)
        filter_layout.addWidget(QLabel("to"), 0, 2)
        filter_layout.addWidget(self.date_to, 0, 3)
        filter_layout.addWidget(QLabel("Machine:"), 0, 4)
        filter_layout.addWidget(self.combo_machine, 0, 5)

        # Row 1: Product, Formula
        filter_layout.addWidget(QLabel("Product:"), 1, 0)
        filter_layout.addWidget(self.combo_product, 1, 1, 1, 3)  # Span 3
        filter_layout.addWidget(QLabel("Formula:"), 1, 4)
        filter_layout.addWidget(self.combo_formula, 1, 5)

        # Row 2: Checkboxes & Buttons
        chk_layout = QHBoxLayout()
        chk_layout.addWidget(self.chk_include_null)
        chk_layout.addSpacing(15)
        chk_layout.addWidget(self.chk_include_zero)
        chk_layout.addStretch()

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addWidget(self.btn_refresh)
        btn_layout.addWidget(self.btn_export)

        filter_layout.addLayout(chk_layout, 2, 0, 1, 4)
        filter_layout.addLayout(btn_layout, 2, 4, 1, 2)

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
            "Product", "Machine", "Formula",
            "Output (kg/hr)", "Clean Time", "Clean Mat", "Yield %", "Details"
        ])
        self.tree.setAlternatingRowColors(True)
        self.tree.setIndentation(15)

        header = self.tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setFixedHeight(30)

        main_layout.addWidget(self.tree, 1)

        # --- 4. STAT CARDS (NEW LAYOUT) ---
        # Container widget for the cards
        stats_container = QWidget()
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(0, 5, 0, 0)
        stats_layout.setSpacing(15)

        # Helper to create a nice card
        def create_stat_card(title, icon_name, color):
            card = QFrame()
            card.setObjectName("StatCard")
            card.setFixedHeight(80)  # Fixed height for uniformity

            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(15, 10, 15, 10)

            # Left: Icon (Optional, text for now) or just Title/Value vertical
            vbox = QVBoxLayout()
            vbox.setSpacing(2)

            lbl_title = QLabel(title)
            lbl_title.setObjectName("CardTitle")

            lbl_value = QLabel("-")
            lbl_value.setObjectName("CardValue")
            lbl_value.setStyleSheet(f"color: {color};")  # Dynamic color for value

            vbox.addWidget(lbl_title)
            vbox.addWidget(lbl_value)
            vbox.addStretch()

            card_layout.addLayout(vbox)
            return card, lbl_value

        # Create 4 Cards
        # We put them in a groupbox just for the label "Standard Deviation"

        footer_group = QGroupBox("Standard Deviation (Valid Yields)")
        footer_layout = QHBoxLayout(footer_group)
        footer_layout.setContentsMargins(10, 25, 10, 10)
        footer_layout.setSpacing(15)

        card_out, self.lbl_std_output = create_stat_card("Output Deviation", , "#2563eb")  # Blue
        card_time, self.lbl_std_ct = create_stat_card("Time Deviation", "clock", "#d97706")  # Amber
        card_mat, self.lbl_std_cm = create_stat_card("Material Deviation", "box", "#059669")  # Emerald
        card_yield, self.lbl_std_yield = create_stat_card("Yield Deviation", "percent", "#dc2626")  # Red

        footer_layout.addWidget(card_out)
        footer_layout.addWidget(card_time)
        footer_layout.addWidget(card_mat)
        footer_layout.addWidget(card_yield)

        main_layout.addWidget(footer_group)

    # --- FUNCTIONALITY (Unchanged) ---
    def load_initial_options(self):
        session = self.Session()
        try:
            opts = get_filter_options(session)
            self.combo_machine.populate_initial(opts["machines"])
            self.combo_product.populate_initial(opts["products"])
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

                for i in range(8):
                    font = item.font(i)
                    font.setBold(True)
                    item.setFont(i, font)
                    item.setBackground(i, QColor("#ffffff"))
                    item.setForeground(i, QColor("#2c3e50"))

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

                    bg_color = QColor("#f8f9fa")
                    text_color = QColor("#5f6368")
                    for k in range(8):
                        child.setBackground(k, bg_color)
                        child.setForeground(k, text_color)

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