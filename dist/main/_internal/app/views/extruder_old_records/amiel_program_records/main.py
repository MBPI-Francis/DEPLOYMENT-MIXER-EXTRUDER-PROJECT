from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import QWidget, QTableWidgetItem, QMessageBox, QDialog, QPushButton, QHBoxLayout
from PyQt6.QtCore import Qt, QTimer
from typing import Type
from sqlalchemy.orm import Session, sessionmaker
from datetime import datetime

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
        self.ui.filter_btn.clicked.connect(self.open_filter_dialog)
        self.ui.search_input.textChanged.connect(self.handle_search_input)
        self.ui.data_table.verticalScrollBar().valueChanged.connect(self.on_scroll)

        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.execute_quick_search)

        QTimer.singleShot(100, self.reload_initial_data)

    def reload_initial_data(self):
        """Total Reset."""
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
        """Quick search without clearing active filters."""
        self.current_offset = 0
        self.has_more_data = True
        self.current_search_term = self.ui.search_input.text().strip()
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
        self.active_filters = filters

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
        self.is_loading = True

        with self.Session() as session:
            try:
                if not self.active_filters and not self.current_search_term:
                    records = self.ops.fetch_records(session, self.BATCH_SIZE, self.current_offset)
                else:
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

    # def append_to_table(self, records):
    #     if not records:
    #         return
    #
    #     self.ui.data_table.setSortingEnabled(False)
    #     start_row = self.ui.data_table.rowCount()
    #     self.ui.data_table.setRowCount(start_row + len(records))
    #
    #     for i, rec in enumerate(records):
    #         row = start_row + i
    #
    #         # Helper for standard text items
    #         def item(val):
    #             txt = str(val) if val is not None else ""
    #             it = QTableWidgetItem(txt)
    #             it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    #             return it
    #
    #         # Helper to format datetime
    #         def format_dt(dt_val):
    #             if isinstance(dt_val, datetime):
    #                 return dt_val.strftime("%Y-%m-%d %H:%M")
    #             return str(dt_val) if dt_val else ""
    #
    #         # --- MAPPING COLUMNS ---
    #         # 0. Date Encoded (encoded_on)
    #         self.ui.data_table.setItem(row, 0, item(rec.encoded_on))
    #
    #         # 1. Machine (machine)
    #         self.ui.data_table.setItem(row, 1, item(rec.machine))
    #
    #         # 2. Code (product_code)
    #         self.ui.data_table.setItem(row, 2, item(rec.product_code))
    #
    #         # 3. Lot No. (lot_number - Array)
    #         lot_val = ""
    #         if rec.lot_number and isinstance(rec.lot_number, list):
    #             lot_val = ", ".join([str(l) for l in rec.lot_number if l])
    #         self.ui.data_table.setItem(row, 3, item(lot_val))
    #
    #         # 4. Time Start (machine_start)
    #         self.ui.data_table.setItem(row, 4, item(format_dt(rec.machine_start)))
    #
    #         # 5. Time End (machine_off)
    #         self.ui.data_table.setItem(row, 5, item(format_dt(rec.machine_off)))
    #
    #         # 6. Output Per hr (output_per_hour)
    #         self.ui.data_table.setItem(row, 6, item(rec.output_per_hour))
    #
    #         # 7. Total Output (total_output)
    #         self.ui.data_table.setItem(row, 7, item(rec.total_output))
    #
    #         # 8. Output % (output_percent)
    #         self.ui.data_table.setItem(row, 8, item(rec.output_percent))
    #
    #         # 9. Remarks (remarks) - With Button Logic
    #         remarks_content = rec.remarks
    #         if remarks_content and str(remarks_content).strip():
    #             # Case A: Has Remarks -> Link Button
    #             container = QWidget()
    #             layout = QHBoxLayout(container)
    #             layout.setContentsMargins(5, 0, 5, 0)
    #             layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
    #
    #             view_btn = QPushButton("View remarks")
    #             view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    #             # Apply the Link Style defined in UI
    #             view_btn.setStyleSheet(ExtruderOldProgramRecordsUI.LINK_BUTTON_STYLE)
    #
    #             # Connect click
    #             view_btn.clicked.connect(lambda checked, r=remarks_content: self.open_remarks_dialog(r))
    #
    #             layout.addWidget(view_btn)
    #             self.ui.data_table.setCellWidget(row, 9, container)
    #         else:
    #             # Case B: Empty -> Italic "No Remarks"
    #             no_rem_item = QTableWidgetItem("No Remarks")
    #             font = QFont()
    #             font.setItalic(True)
    #             no_rem_item.setFont(font)
    #             no_rem_item.setForeground(QColor("#adb5bd"))  # Gray color
    #             no_rem_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    #             self.ui.data_table.setItem(row, 9, no_rem_item)
    #
    #     self.ui.data_table.setSortingEnabled(True)

    # def append_to_table(self, records):
    #     if not records:
    #         return
    #
    #     self.ui.data_table.setSortingEnabled(False)
    #     start_row = self.ui.data_table.rowCount()
    #     self.ui.data_table.setRowCount(start_row + len(records))
    #
    #     for i, rec in enumerate(records):
    #         row = start_row + i
    #
    #         # Helper for standard text items
    #         def item(val):
    #             txt = str(val) if val is not None else ""
    #             it = QTableWidgetItem(txt)
    #             it.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    #             return it
    #
    #         # Helper to format datetime
    #         def format_dt(dt_val):
    #             from datetime import datetime
    #             if isinstance(dt_val, datetime):
    #                 return dt_val.strftime("%Y-%m-%d %H:%M")
    #             return str(dt_val) if dt_val else ""
    #
    #         # --- MAPPING COLUMNS ---
    #         self.ui.data_table.setItem(row, 0, item(rec.encoded_on))
    #         self.ui.data_table.setItem(row, 1, item(rec.machine))
    #         self.ui.data_table.setItem(row, 2, item(rec.product_code))
    #
    #         lot_val = ""
    #         if rec.lot_number and isinstance(rec.lot_number, list):
    #             lot_val = ", ".join([str(l) for l in rec.lot_number if l])
    #         self.ui.data_table.setItem(row, 3, item(lot_val))
    #
    #         self.ui.data_table.setItem(row, 4, item(format_dt(rec.machine_start)))
    #         self.ui.data_table.setItem(row, 5, item(format_dt(rec.machine_off)))
    #         self.ui.data_table.setItem(row, 6, item(rec.output_per_hour))
    #         self.ui.data_table.setItem(row, 7, item(rec.total_output))
    #         self.ui.data_table.setItem(row, 8, item(rec.output_percent))
    #
    #         # --- NEW REMARKS LOGIC ---
    #         remarks_content = rec.remarks
    #         if remarks_content and str(remarks_content).strip():
    #             # 1. Prepare the display text (Truncate to ~50 chars)
    #             full_text = str(remarks_content).strip()
    #             display_text = full_text
    #             if len(full_text) > 50:
    #                 display_text = full_text[:50] + "..."
    #
    #             # 2. Container for alignment
    #             container = QWidget()
    #             layout = QHBoxLayout(container)
    #             layout.setContentsMargins(5, 0, 5, 0)
    #             layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
    #
    #             # 3. Create the Link Button with the PARTIAL text
    #             view_btn = QPushButton(display_text)
    #             view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
    #             view_btn.setToolTip(full_text)  # Hover shows full text
    #
    #             # Apply the Link Style (Blue, Underline on hover)
    #             view_btn.setStyleSheet(ExtruderOldProgramRecordsUI.LINK_BUTTON_STYLE)
    #
    #             # 4. Connect to Dialog
    #             view_btn.clicked.connect(lambda checked, r=full_text: self.open_remarks_dialog(r))
    #
    #             layout.addWidget(view_btn)
    #             self.ui.data_table.setCellWidget(row, 9, container)
    #         else:
    #             # Case B: Empty -> Italic "No Remarks"
    #             no_rem_item = QTableWidgetItem("No Remarks")
    #             font = QFont()
    #             font.setItalic(True)
    #             no_rem_item.setFont(font)
    #             no_rem_item.setForeground(QColor("#adb5bd"))
    #             no_rem_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
    #             self.ui.data_table.setItem(row, 9, no_rem_item)
    #
    #     self.ui.data_table.setSortingEnabled(True)

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

            # Helper to format datetime
            def format_dt(dt_val):
                from datetime import datetime
                if isinstance(dt_val, datetime):
                    return dt_val.strftime("%Y-%m-%d %H:%M")
                return str(dt_val) if dt_val else ""

            # --- MAPPING COLUMNS ---
            # 0. Date Encoded
            self.ui.data_table.setItem(row, 0, item(rec.encoded_on))

            # 1. Machine
            self.ui.data_table.setItem(row, 1, item(rec.machine))

            # 2. Code
            self.ui.data_table.setItem(row, 2, item(rec.product_code))

            # 3. Lot No.
            lot_val = ""
            if rec.lot_number and isinstance(rec.lot_number, list):
                lot_val = ", ".join([str(l) for l in rec.lot_number if l])
            self.ui.data_table.setItem(row, 3, item(lot_val))

            # --- NEW COLUMN ---
            # 4. Screw Config
            self.ui.data_table.setItem(row, 4, item(rec.screw_config))

            # 5. Resin
            self.ui.data_table.setItem(row, 5, item(rec.resin))
            # -------------------

            # 6. Time Start
            self.ui.data_table.setItem(row, 6, item(format_dt(rec.machine_start)))

            # 7. Time End
            self.ui.data_table.setItem(row, 7, item(format_dt(rec.machine_off)))

            # 8. Output/Hr
            self.ui.data_table.setItem(row, 8, item(rec.output_per_hour))

            # 9. Total Output
            self.ui.data_table.setItem(row, 9, item(rec.total_output))

            # 10. Output %
            self.ui.data_table.setItem(row, 10, item(rec.output_percent))

            # 11. Operator
            self.ui.data_table.setItem(row, 11, item(rec.operator))

            # 12. Supervisor
            self.ui.data_table.setItem(row, 12, item(rec.supervisor))

            # 13. Remarks (Partial View Logic)
            remarks_content = rec.remarks
            if remarks_content and str(remarks_content).strip():
                # Case A: Has Remarks -> Link Button
                container = QWidget()
                layout = QHBoxLayout(container)
                layout.setContentsMargins(5, 0, 5, 0)
                layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

                view_btn = QPushButton("View remarks")
                view_btn.setCursor(Qt.CursorShape.PointingHandCursor)
                # Apply the Link Style defined in UI
                view_btn.setStyleSheet(ExtruderOldProgramRecordsUI.LINK_BUTTON_STYLE)

                # Connect click
                view_btn.clicked.connect(lambda checked, r=remarks_content: self.open_remarks_dialog(r))

                layout.addWidget(view_btn)
                self.ui.data_table.setCellWidget(row, 13, container)
            else:
                # Case B: Empty -> Italic "No Remarks"
                no_rem_item = QTableWidgetItem("No Remarks")
                font = QFont()
                font.setItalic(True)
                no_rem_item.setFont(font)
                no_rem_item.setForeground(QColor("#adb5bd"))  # Gray color
                no_rem_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                self.ui.data_table.setItem(row, 13, no_rem_item)

        self.ui.data_table.setSortingEnabled(True)

    def open_remarks_dialog(self, text):
        """Slot to open the dialog."""
        dialog = RemarksDialog(text, self)
        dialog.exec()