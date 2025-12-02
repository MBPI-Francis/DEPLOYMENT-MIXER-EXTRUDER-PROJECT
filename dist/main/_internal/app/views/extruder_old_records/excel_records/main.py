from PyQt6.QtWidgets import QWidget, QTableWidgetItem, QMessageBox, QDialog, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QColor
from typing import Type
from sqlalchemy.orm import Session, sessionmaker

from .ui_setup import ExtruderExcelRecordsUI
from .ops import ExtruderExcelRecordsOps
from .filter_dialog import FilterDialog
from .remarks_dialog import RemarksDialog  # New Import


class ExtruderExcelRecords(QWidget):
    """
    Main View/Controller for Extruder Old Excel Records.
    """

    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory

        self.BATCH_SIZE = 100
        self.current_offset = 0
        self.is_loading = False
        self.has_more_data = True
        self.current_search_term = ""
        self.active_filters = {}

        self.ui = ExtruderExcelRecordsUI()
        self.ui.setup_ui(self)
        self.ops = ExtruderExcelRecordsOps()

        self.ui.refresh_btn.clicked.connect(self.reload_initial_data)
        self.ui.filter_btn.clicked.connect(self.open_filter_dialog)
        self.ui.search_input.textChanged.connect(self.handle_search_input)
        self.ui.data_table.verticalScrollBar().valueChanged.connect(self.on_scroll)

        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.execute_quick_search)

        QTimer.singleShot(100, self.reload_initial_data)

    def reload_initial_data(self):
        self.current_offset = 0
        self.has_more_data = True
        self.current_search_term = ""
        self.active_filters = {}
        self.ui.search_input.clear()

        self.ui.filter_btn.setText("Filter Options")
        self.ui.filter_btn.setStyleSheet("")

        self.ui.data_table.setRowCount(0)
        self.fetch_and_display()

    def handle_search_input(self):
        self.search_timer.start(300)

    def execute_quick_search(self):
        self.current_offset = 0
        self.has_more_data = True
        self.active_filters = {}
        self.current_search_term = self.ui.search_input.text().strip()

        self.ui.filter_btn.setText("Filter Options")
        self.ui.filter_btn.setStyleSheet("")

        self.ui.data_table.setRowCount(0)
        self.fetch_and_display()

    def open_filter_dialog(self):
        dialog = FilterDialog(self.Session, self)
        if self.active_filters:
            dialog.set_current_filters(self.active_filters)

        if dialog.exec() == QDialog.DialogCode.Accepted:
            filters = dialog.get_filters()
            if filters:
                self.apply_advanced_filter(filters)
            else:
                self.reload_initial_data()

    def apply_advanced_filter(self, filters):
        self.current_offset = 0
        self.has_more_data = True
        self.current_search_term = ""
        self.ui.search_input.clear()
        self.active_filters = filters

        count = len(filters)
        self.ui.filter_btn.setText(f"Filters Active ({count})")
        self.ui.filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #0d6efd; 
                color: white; 
                border: 1px solid #0d6efd;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #0b5ed7;
            }
        """)

        self.ui.data_table.setRowCount(0)
        self.fetch_and_display()

    def on_scroll(self, value):
        if self.is_loading or not self.has_more_data:
            return
        if value == self.ui.data_table.verticalScrollBar().maximum():
            self.load_next_batch()

    def load_next_batch(self):
        self.current_offset += self.BATCH_SIZE
        self.fetch_and_display()

    def fetch_and_display(self):
        self.is_loading = True

        with self.Session() as session:
            try:
                if self.active_filters:
                    records = self.ops.fetch_filtered_records(
                        session, self.active_filters, self.BATCH_SIZE, self.current_offset
                    )
                elif self.current_search_term:
                    records = self.ops.search_records(
                        session, self.current_search_term, self.BATCH_SIZE, self.current_offset
                    )
                else:
                    records = self.ops.fetch_records(
                        session, self.BATCH_SIZE, self.current_offset
                    )

                if len(records) < self.BATCH_SIZE:
                    self.has_more_data = False

                self.append_to_table(records)

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load records:\n{e}")
            finally:
                self.is_loading = False

    def append_to_table(self, records):
        if not records:
            return

        self.ui.data_table.setSortingEnabled(False)
        start_row = self.ui.data_table.rowCount()
        self.ui.data_table.setRowCount(start_row + len(records))

        for i, rec in enumerate(records):
            row = start_row + i

            def item(val):
                txt = str(val) if val is not None else ""
                it = QTableWidgetItem(txt)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                return it

            self.ui.data_table.setItem(row, 0, item(rec.id))
            self.ui.data_table.setItem(row, 1, item(rec.date))
            self.ui.data_table.setItem(row, 2, item(rec.code))
            self.ui.data_table.setItem(row, 3, item(rec.customer))
            self.ui.data_table.setItem(row, 4, item(rec.machine_no))
            self.ui.data_table.setItem(row, 5, item(rec.lot_number))
            self.ui.data_table.setItem(row, 6, item(rec.qty_input))
            self.ui.data_table.setItem(row, 7, item(rec.qty_output))
            self.ui.data_table.setItem(row, 8, item(rec.output_per_hour))
            self.ui.data_table.setItem(row, 9, item(rec.screw_config))
            self.ui.data_table.setItem(row, 10, item(rec.rpm))
            self.ui.data_table.setItem(row, 11, item(rec.resin_used))

            # --- REMARKS LOGIC (Column 12) ---
            remarks_content = rec.remarks
            if remarks_content and str(remarks_content).strip():
                # Case A: Has Content -> "View remarks" Button
                container = QWidget()
                layout = QHBoxLayout(container)
                layout.setContentsMargins(5, 0, 5, 0)
                layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

                # Static Text as requested
                view_btn = QPushButton("View remarks")
                view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                view_btn.setStyleSheet(ExtruderExcelRecordsUI.LINK_BUTTON_STYLE)

                # Connect click to open dialog with full text
                view_btn.clicked.connect(lambda checked, r=str(remarks_content): self.open_remarks_dialog(r))

                layout.addWidget(view_btn)
                self.ui.data_table.setCellWidget(row, 12, container)

            else:
                # Case B: Empty -> Italic "No Remarks"
                no_rem_item = QTableWidgetItem("No Remarks")
                font = QFont()
                font.setItalic(True)
                no_rem_item.setFont(font)
                no_rem_item.setForeground(QColor("#adb5bd"))
                no_rem_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.ui.data_table.setItem(row, 12, no_rem_item)

        self.ui.data_table.setSortingEnabled(True)

    def open_remarks_dialog(self, text):
        """Slot to open the dialog."""
        dialog = RemarksDialog(text, self)
        dialog.exec()