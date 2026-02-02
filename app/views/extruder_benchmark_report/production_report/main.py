import os
import pandas as pd
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTreeWidget, QTreeWidgetItem, QLabel,
    QMessageBox, QGroupBox, QDateEdit, QGridLayout,
    QCheckBox, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QDate, QThread, pyqtSignal
from PyQt6.QtGui import QColor

import qtawesome as qta
from .ops import get_production_report_data
from .exporter import DynamicProductionExporter

# --- CONFIG: Column Definitions (Internal Name, Display Name, Default Visible) ---
COLUMN_DEFINITIONS = [
    ("created_at", "Date Encoded", False),  # Usually hidden, redundant if Time Start exists
    ("time_start", "Date/Time Start", True),  # Primary Date Column
    ("time_end", "Date/Time End", True),
    ("machine_number", "Machine", True),
    ("product_code", "Code", True),
    ("formula_number", "Formula", True),
    ("lot_number", "Lot Number", True),
    ("duration_hours", "Duration (Hr)", True),
    ("total_output", "Total Output", True),
    ("output_per_hour", "Output/Hr", True),
    ("expected_output", "Total Input", True),
    ("output_percentage", "Yield %", True),
    ("loss_qty", "Loss", True),
    ("loss_percentage", "Loss %", True),
    ("purging_duration_minutes", "Purging (Min)", True),
    ("operator", "Operator", True)
]


# --- THREAD ---
class ProductionLoaderThread(QThread):
    data_ready = pyqtSignal(object)
    error_occurred = pyqtSignal(str)

    def __init__(self, session_factory, date_from, date_to):
        super().__init__()
        self.session_factory = session_factory
        self.d_from = date_from
        self.d_to = date_to

    def run(self):
        session = self.session_factory()
        try:
            df = get_production_report_data(session, self.d_from, self.d_to)
            self.data_ready.emit(df)
        except Exception as e:
            import traceback
            self.error_occurred.emit(str(e) + "\n" + traceback.format_exc())
        finally:
            session.close()


# --- MAIN VIEW ---
class ExtruderProductionView(QWidget):
    def __init__(self, session_factory, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.data_df = pd.DataFrame()
        self.column_checkboxes = {}

        self.init_ui()
        self.apply_styles()

    def apply_styles(self):
        css_path = os.path.join(os.path.dirname(__file__), "styles.css")
        if os.path.exists(css_path):
            with open(css_path, "r") as f:
                self.setStyleSheet(f.read())

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(0, 0, 0, 0)


        # --- 1. SETTINGS CARD ---
        settings_group = QGroupBox()
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setContentsMargins(10, 0, 10, 0)
        settings_layout.setSpacing(10)

        # Row 1: Date Filters & Action Buttons
        row1_layout = QHBoxLayout()

        def create_field(label, widget):
            c = QWidget()
            l = QVBoxLayout(c)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(4)
            lbl = QLabel(label)
            lbl.setStyleSheet("color: #64748b; font-weight: 700; font-size: 11px; text-transform: uppercase;")
            l.addWidget(lbl)
            l.addWidget(widget)
            return c

        self.date_from = QDateEdit(calendarPopup=True, date=QDate.currentDate().addMonths(-1))
        self.date_to = QDateEdit(calendarPopup=True, date=QDate.currentDate())

        self.btn_refresh = QPushButton("Generate Report", icon=qta.icon("fa5s.sync-alt", color="white"))
        self.btn_refresh.setObjectName("BtnRefresh")
        self.btn_refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_refresh.clicked.connect(self.start_load)
        self.btn_refresh.setFixedHeight(35)

        self.btn_export = QPushButton("Export Visible", icon=qta.icon("fa5s.file-excel", color="white"))
        self.btn_export.setObjectName("BtnExport")
        self.btn_export.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_export.clicked.connect(self.export_excel)
        self.btn_export.setFixedHeight(35)

        # Add to Row 1
        row1_layout.addWidget(create_field("Start Date", self.date_from), 1)
        row1_layout.addWidget(create_field("End Date", self.date_to), 1)
        row1_layout.addStretch(1)  # Spacer
        row1_layout.addWidget(self.btn_refresh)
        row1_layout.addWidget(self.btn_export)

        # Row 2: Column Selector (Styled Frame)
        row2_frame = QFrame()
        row2_frame.setObjectName("ColumnSelector")
        row2_layout = QVBoxLayout(row2_frame)
        row2_layout.setContentsMargins(15, 10, 15, 10)

        lbl_cols = QLabel("VISIBLE COLUMNS:")
        lbl_cols.setStyleSheet("color: #64748b; font-weight: 700; font-size: 11px;")
        row2_layout.addWidget(lbl_cols)

        # Grid of Checkboxes
        chk_grid = QGridLayout()
        chk_grid.setSpacing(10)

        row, col = 0, 0
        max_cols = 6

        for idx, (internal, display, default) in enumerate(COLUMN_DEFINITIONS):
            chk = QCheckBox(display)
            chk.setChecked(default)
            chk.setProperty("col_index", idx)
            chk.stateChanged.connect(self.on_column_toggled)
            self.column_checkboxes[internal] = chk

            chk_grid.addWidget(chk, row, col)
            col += 1
            if col >= max_cols:
                col = 0
                row += 1

        row2_layout.addLayout(chk_grid)

        # Assemble Settings Card
        settings_layout.addLayout(row1_layout)
        settings_layout.addWidget(row2_frame)

        main_layout.addWidget(settings_group)

        # --- 2. PROGRESS ---
        self.loader = QProgressBar()
        self.loader.setFixedHeight(3)
        self.loader.setTextVisible(False)
        self.loader.setRange(0, 0)
        self.loader.setStyleSheet(
            "QProgressBar {border: none; background: transparent;} QProgressBar::chunk { background: #3b82f6; }")
        self.loader.hide()
        main_layout.addWidget(self.loader)

        # --- 3. TABLE ---
        self.tree = QTreeWidget()
        self.tree.setAlternatingRowColors(True)
        self.tree.setIndentation(0)

        headers = [disp for _, disp, _ in COLUMN_DEFINITIONS]
        self.tree.setHeaderLabels(headers)

        header_view = self.tree.header()
        header_view.setSectionsMovable(True)
        header_view.setStretchLastSection(True)
        header_view.setFixedHeight(30)

        # Apply visibility
        for idx, (_, _, visible) in enumerate(COLUMN_DEFINITIONS):
            self.tree.setColumnHidden(idx, not visible)

        main_layout.addWidget(self.tree, 1)

    # --- LOGIC ---
    def on_column_toggled(self):
        sender = self.sender()
        if sender:
            col_idx = sender.property("col_index")
            self.tree.setColumnHidden(col_idx, not sender.isChecked())

    def start_load(self):
        self.tree.clear()
        self.loader.show()
        self.btn_refresh.setEnabled(False)
        self.btn_export.setEnabled(False)

        d_from = self.date_from.date().toPyDate()
        d_to = self.date_to.date().toPyDate()

        self.worker = ProductionLoaderThread(self.Session, d_from, d_to)
        self.worker.data_ready.connect(self.on_data_ready)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.finished.connect(self.on_finished)
        self.worker.start()

    def on_data_ready(self, df):
        self.data_df = df
        if df.empty:
            QMessageBox.information(self, "No Data", "No records found.")
            return

        self.tree.setUpdatesEnabled(False)

        for _, row in df.iterrows():
            item = QTreeWidgetItem(self.tree)

            for idx, (internal_col, _, _) in enumerate(COLUMN_DEFINITIONS):
                val = row.get(internal_col)
                display_val = ""

                # Format Dates
                if internal_col in ["time_start", "time_end", "created_at"]:
                    try:
                        display_val = pd.to_datetime(val).strftime("%Y-%m-%d %H:%M")
                    except:
                        display_val = str(val)
                # Format Numbers
                elif isinstance(val, (int, float)):
                    if internal_col in ["output_percentage", "loss_percentage"]:
                        display_val = f"{val:.2f}%"
                    elif internal_col in ["total_output", "expected_output", "loss_qty"]:
                        display_val = f"{val:,.2f}"
                    else:
                        display_val = str(val)
                else:
                    display_val = str(val) if pd.notna(val) else ""

                item.setText(idx, display_val)

                # Style rows
                item.setForeground(idx, QColor("#334155"))  # Slate 700

                # Color Coding for Yield
                if internal_col == "output_percentage":
                    try:
                        y = float(val)
                        if y < 85:
                            item.setForeground(idx, QColor("#dc2626"))  # Red
                        elif y < 90:
                            item.setForeground(idx, QColor("#ea580c"))  # Orange
                    except:
                        pass

        self.tree.setUpdatesEnabled(True)
        for i in range(len(COLUMN_DEFINITIONS)):
            if not self.tree.isColumnHidden(i):
                self.tree.resizeColumnToContents(i)

    def on_error(self, msg):
        QMessageBox.critical(self, "Error", msg)

    def on_finished(self):
        self.loader.hide()
        self.btn_refresh.setEnabled(True)
        self.btn_export.setEnabled(True)

    def export_excel(self):
        if self.data_df.empty: return
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getSaveFileName(self, "Save Report",
                                              f"Extruder_Production_{QDate.currentDate().toString('yyyy-MM-dd')}.xlsx",
                                              "Excel Files (*.xlsx)")

        if path:
            try:
                # Get Visible Column Order
                header = self.tree.header()
                visible_cols = []
                for visual_idx in range(header.count()):
                    logical_idx = header.logicalIndex(visual_idx)
                    if not self.tree.isColumnHidden(logical_idx):
                        internal = COLUMN_DEFINITIONS[logical_idx][0]
                        display = COLUMN_DEFINITIONS[logical_idx][1]
                        visible_cols.append((internal, display))

                DynamicProductionExporter().export(self.data_df, visible_cols, path)
                QMessageBox.information(self, "Success", "Export Complete!")
            except Exception as e:
                QMessageBox.critical(self, "Export Error", str(e))