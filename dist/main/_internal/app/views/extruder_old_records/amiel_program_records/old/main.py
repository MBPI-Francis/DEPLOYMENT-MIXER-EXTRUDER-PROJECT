from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import QWidget, QTableWidgetItem, QMessageBox, QDialog, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer
from typing import Type
from sqlalchemy.orm import Session, sessionmaker

from .remarks_dialog import RemarksDialog
from .ui_setup import ExtruderOldProgramRecordsUI
from .ops import ExtruderOldProgramRecordsOps
from .filter_dialog import FilterDialog


class ExtruderOldProgramRecords(QWidget):
    def __init__(self, session_factory: Type[sessionmaker], parent=None):
        super().__init__(parent)
        self.Session = session_factory

        self.BATCH_SIZE = 100
        self.current_offset = 0
        self.is_loading = False
        self.has_more_data = True

        self.current_search_term = ""
        self.active_filters = {}

        self.ui = ExtruderOldProgramRecordsUI()
        self.ui.setup_ui(self)
        self.ops = ExtruderOldProgramRecordsOps()

        self.ui.refresh_btn.clicked.connect(self.reload_initial_data)
        self.ui.filter_btn.clicked.connect(self.open_filter_dialog)  # Connected!
        self.ui.search_input.textChanged.connect(self.handle_search_input)
        self.ui.data_table.verticalScrollBar().valueChanged.connect(self.on_scroll)

        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.execute_quick_search)

        QTimer.singleShot(100, self.reload_initial_data)

    def reload_initial_data(self):
        """
        Total Reset (Refresh Button).
        Clears BOTH filters and search.
        """
        self.current_offset = 0
        self.has_more_data = True

        # Clear Both States
        self.current_search_term = ""
        self.active_filters = {}

        # Clear UI Elements
        self.ui.search_input.clear()
        self.ui.filter_btn.setText("Filter Options")
        self.ui.filter_btn.setStyleSheet("")

        self.ui.data_table.setRowCount(0)
        self.fetch_and_display()

    def handle_search_input(self):
        self.search_timer.start(300)

    def execute_quick_search(self):
        """
        Called when typing in search bar.
        Update: Does NOT clear active_filters.
        """
        self.current_offset = 0
        self.has_more_data = True

        # Capture the text
        self.current_search_term = self.ui.search_input.text().strip()

        # Note: We do NOT clear self.active_filters here anymore.

        # Reset Table
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
        """
        Called when applying from Dialog.
        Update: Does NOT clear current_search_term.
        """
        self.current_offset = 0
        self.has_more_data = True

        # Capture the filters
        self.active_filters = filters

        # Note: We do NOT clear self.current_search_term or self.ui.search_input here.

        # Update Button Style
        count = len(filters)
        self.ui.filter_btn.setText(f"Filters Active ({count})")
        self.ui.filter_btn.setStyleSheet("""
            QPushButton { background-color: #0d6efd; color: white; border: 1px solid #0d6efd; font-weight: bold; }
            QPushButton:hover { background-color: #0b5ed7; }
        """)

        self.ui.data_table.setRowCount(0)
        self.fetch_and_display()

    def on_scroll(self, value):
        if self.is_loading or not self.has_more_data: return
        if value == self.ui.data_table.verticalScrollBar().maximum():
            self.load_next_batch()

    def load_next_batch(self):
        self.current_offset += self.BATCH_SIZE
        self.fetch_and_display()

    def fetch_and_display(self):
        """
        Single source of truth for fetching data.
        Combines active_filters and current_search_term.
        """
        self.is_loading = True

        with self.Session() as session:
            try:
                # We always use fetch_filtered_records now, passing both states.
                # If both are empty/None, the Ops logic handles it gracefully (or you can check here).

                if not self.active_filters and not self.current_search_term:
                    # Pure default load
                    records = self.ops.fetch_records(session, self.BATCH_SIZE, self.current_offset)
                else:
                    # Combined load
                    records = self.ops.fetch_filtered_records(
                        session,
                        self.active_filters,
                        self.current_search_term,
                        self.BATCH_SIZE,
                        self.current_offset
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

            # Helper for standard text items
            def item(val):
                txt = str(val) if val is not None else ""
                it = QTableWidgetItem(txt)
                it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                return it

            # 1. Standard Columns
            self.ui.data_table.setItem(row, 0, item(rec.process_id))
            self.ui.data_table.setItem(row, 1, item(rec.encoded_on))
            self.ui.data_table.setItem(row, 2, item(rec.product_code))
            self.ui.data_table.setItem(row, 3, item(rec.customer))
            self.ui.data_table.setItem(row, 4, item(rec.machine))

            # Lot Number Handling
            lot_val = ""
            if rec.lot_number and isinstance(rec.lot_number, list):
                lot_val = ", ".join([str(l) for l in rec.lot_number if l])
            self.ui.data_table.setItem(row, 5, item(lot_val))

            self.ui.data_table.setItem(row, 6, item(rec.qty_order))
            self.ui.data_table.setItem(row, 7, item(rec.total_output))
            self.ui.data_table.setItem(row, 8, item(rec.output_percent))

            # 2. REMARKS COLUMN LOGIC (Column 9)
            remarks_content = rec.remarks

            if remarks_content and str(remarks_content).strip():
                # Case A: Has Remarks -> Link Button

                # Container widget to center/align the button if needed (optional, button direct is fine too)
                container = QWidget()
                layout = QHBoxLayout(container)
                layout.setContentsMargins(5, 0, 5, 0)
                layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

                view_btn = QPushButton("View remarks")
                view_btn.setObjectName("RemarksButton")
                view_btn.setCursor(Qt.CursorShape.PointingHandCursor)

                # Connect click using a closure to capture specific text
                # We use default arg r=remarks_content to capture the value at this iteration
                view_btn.clicked.connect(lambda checked, r=remarks_content: self.open_remarks_dialog(r))

                layout.addWidget(view_btn)
                self.ui.data_table.setCellWidget(row, 9, container)

            else:
                # Case B: Empty -> Italic "No Remarks"
                no_rem_item = QTableWidgetItem("No Remarks")
                font = QFont()
                font.setItalic(True)
                no_rem_item.setFont(font)
                no_rem_item.setForeground(QColor("#adb5bd"))  # Gray color
                no_rem_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.ui.data_table.setItem(row, 9, no_rem_item)

        self.ui.data_table.setSortingEnabled(True)

    def open_remarks_dialog(self, text):
        """Slot to open the dialog."""
        dialog = RemarksDialog(text, self)
        dialog.exec()