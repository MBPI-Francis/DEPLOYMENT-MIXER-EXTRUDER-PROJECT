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
from .ops import get_benchmark_data, get_filter_options
from .exporter import ExtruderBenchmarkExporter


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


class ExtruderReportView(QWidget):
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
        # Re-use the Mixer styles if they are identical, or create a copy
        # Assuming you want consistency, we can point to the same qss file if path allows,
        # otherwise create a local styles.qss in this folder with the same content.
        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f:
                self.setStyleSheet(f.read())

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(0, 0, 0, 0)

        # --- 1. FILTER CARD ---
        filter_group = QGroupBox()
        card_layout = QVBoxLayout(filter_group)
        card_layout.setContentsMargins(20, 20, 20, 20)
        card_layout.setSpacing(15)

        # Helper
        def create_field_box(label_text, widget):
            container = QWidget()
            l = QVBoxLayout(container)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(5)
            lbl = QLabel(label_text)
            lbl.setStyleSheet("color: #5f6368; font-weight: 600; font-size: 11px; text-transform: uppercase;")
            l.addWidget(lbl)
            l.addWidget(widget)
            return container

        # Inputs
        self.date_from = QDateEdit(calendarPopup=True, date=QDate.currentDate().addMonths(-1))
        self.date_to = QDateEdit(calendarPopup=True, date=QDate.currentDate())

        self.combo_product = SmartComboBox()
        self.combo_product.setPlaceholderText("Select Product...")

        self.combo_formula = SmartComboBox()
        self.combo_formula.setPlaceholderText("Search Formula...")
        # Note: Extruder formula search might just filter existing items if list is small,
        # but we can implement the search logic if needed. For now, standard filter.

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

        # Layout Rows
        row1 = QHBoxLayout()
        row1.setSpacing(15)
        row1.addWidget(create_field_box("Start Date", self.date_from), 1)
        row1.addWidget(create_field_box("End Date", self.date_to), 1)
        row1.addWidget(create_field_box("Machine", self.combo_machine), 1)
        row1.addWidget(create_field_box("Product Code", self.combo_product), 1)
        row1.addWidget(create_field_box("Formula No", self.combo_formula), 1)

        row2 = QHBoxLayout()
        row2.setSpacing(20)
        row2.addWidget(self.chk_include_null)
        row2.addWidget(self.chk_include_zero)
        row2.addStretch()
        row2.addWidget(self.btn_refresh)
        row2.addWidget(self.btn_export)

        card_layout.addLayout(row1)
        card_layout.addLayout(row2)


        main_layout.addWidget(filter_group)

        # --- 2. PROGRESS ---
        self.loader = QProgressBar()
        self.loader.setRange(0, 0)
        self.loader.setFixedHeight(4)
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
            "Output (kg/hr)", "Clean Time", "Clean Mat", "Yield %", "Details / Remarks"
        ])
        self.tree.setAlternatingRowColors(True)
        self.tree.setIndentation(15)

        header = self.tree.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        header.setFixedHeight(30)
        header.resizeSection(7, 300)

        main_layout.addWidget(self.tree, 1)

        # --- 4. STAT CARDS ---
        stats_container = QWidget()
        stats_layout = QHBoxLayout(stats_container)
        stats_layout.setContentsMargins(0, 5, 0, 0)

        def create_stat_card(title, color):
            card = QFrame()
            card.setObjectName("StatCard")
            card.setFixedHeight(80)
            l = QVBoxLayout(card)
            l.setContentsMargins(15, 10, 15, 10)
            l.setSpacing(4)

            t = QLabel(title)
            t.setObjectName("CardTitle")
            v = QLabel("-")
            v.setObjectName("CardValue")
            v.setStyleSheet(f"color: {color};")

            l.addWidget(t)
            l.addWidget(v)
            l.addStretch()
            return card, v

        footer_group = QGroupBox()
        footer_layout = QHBoxLayout(footer_group)
        footer_layout.setContentsMargins(10, 10, 10, 10)
        footer_layout.setSpacing(15)

        w_out, self.lbl_std_output = create_stat_card("Output Dev", "#2563eb")
        w_time, self.lbl_std_ct = create_stat_card("Time Dev", "#d97706")
        w_mat, self.lbl_std_cm = create_stat_card("Mat Dev", "#059669")
        w_yield, self.lbl_std_yield = create_stat_card("Yield Dev", "#dc2626")

        footer_layout.addWidget(w_out)
        footer_layout.addWidget(w_time)
        footer_layout.addWidget(w_mat)
        footer_layout.addWidget(w_yield)

        main_layout.addWidget(footer_group)

    # --- LOGIC ---
    def load_initial_options(self):
        session = self.Session()
        try:
            opts = get_filter_options(session)
            self.combo_machine.populate_initial(opts["machines"])
            self.combo_product.populate_initial(opts["products"])
            self.combo_formula.populate_initial(opts["formulas"])
        except Exception as e:
            print(f"Error: {e}")
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
        QMessageBox.critical(self, "Error", f"An error occurred:\n{message}")

    def on_load_finished(self):
        self.loader.hide()
        self.btn_refresh.setEnabled(True)
        self.btn_export.setEnabled(True)

    def populate_tree(self):
        self.tree.setUpdatesEnabled(False)

        def get_yield_remark_and_color(yield_val):
            if pd.isna(yield_val): return "Yield not calculated", "#6c757d"
            if yield_val >= 95:
                return "Acceptable yield. Within normal limits.", "#198754"
            elif yield_val >= 90:
                return "Low yield. Monitoring required.", "#d97706"
            elif yield_val >= 85:
                return "Alarming yield. Investigation required.", "#fd7e14"
            else:
                return "Critical yield loss. Action required.", "#dc3545"

        def add_rows(df, is_valid):
            for _, row in df.iterrows():
                item = QTreeWidgetItem(self.tree)
                item.setText(0, str(row["product_code"]))
                item.setText(1, str(row["machine_number"]))
                item.setText(2, str(row["formula_number"]))
                item.setText(3, f"{row['avg_output_rate']:.2f}")
                item.setText(4, f"{row['avg_purge_mins']:.2f}")
                item.setText(5, f"{row['avg_purge_mat']:.2f}")

                y_val = row.get('avg_yield')
                if pd.notna(y_val):
                    item.setText(6, f"{y_val:.2f}%")
                else:
                    item.setText(6, "N/A")

                # Parent Details: Just count
                count_str = f"{row['record_count']} batches"
                if not is_valid: count_str += " (Unspec Yield)"
                item.setText(7, count_str)

                # Parent Style
                for i in range(8):
                    font = item.font(i)
                    font.setBold(True)
                    item.setFont(i, font)
                    item.setBackground(i, QColor("#ffffff"))
                    item.setForeground(i, QColor("#2c3e50"))

                # Drill Down
                subset = self.raw_df[
                    (self.raw_df["product_code"] == row["product_code"]) &
                    (self.raw_df["machine_number"] == row["machine_number"]) &
                    (self.raw_df["formula_number"] == row["formula_number"])
                    ]

                for _, det in subset.iterrows():
                    child = QTreeWidgetItem(item)
                    child.setText(0, str(det["time_start"]))
                    child.setText(1, str(det["reference_number"]))
                    child.setText(2, str(det["lot_number"]))
                    child.setText(3, f"{det['output_per_hour']:.2f}")
                    child.setText(4, f"{det['purging_duration_minutes']:.2f}")
                    child.setText(5, f"{det['total_cleaning_material']:.2f}")

                    y_raw = det.get("yield_value")
                    if pd.notna(y_raw):
                        child.setText(6, f"{y_raw:.2f}%")
                        # Child Remarks
                        rem_text, rem_color = get_yield_remark_and_color(y_raw)
                        child.setText(7, rem_text)
                        child.setForeground(7, QBrush(QColor(rem_color)))
                    else:
                        child.setText(6, "-")
                        child.setText(7, "-")

                    # Child Style
                    bg_color = QColor("#f8f9fa")
                    text_color = QColor("#5f6368")
                    for k in range(7):
                        child.setBackground(k, bg_color)
                        child.setForeground(k, text_color)
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
            s_ct = self.summary_valid["avg_purge_mins"].std()
            s_cm = self.summary_valid["avg_purge_mat"].std()
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
                                              f"Extruder_Benchmark_{QDate.currentDate().toString('yyyy-MM-dd')}.xlsx",
                                              "Excel Files (*.xlsx)")
        if path:
            try:
                ExtruderBenchmarkExporter().export(self.summary_valid, self.summary_invalid, self.raw_df, path)
                QMessageBox.information(self, "Success", "Export Complete!")
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))