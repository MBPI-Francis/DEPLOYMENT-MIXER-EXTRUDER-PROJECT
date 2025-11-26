# # app/views/extruder_old_records/excel_records/ui_setup.py
# from PyQt6.QtCore import Qt
# from PyQt6.QtWidgets import (
#     QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
#     QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
# )
#
#
# class ExtruderExcelRecordsUI:
#     """
#     Defines the UI components for the Old Extruder Excel Records module.
#     """
#
#     def setup_ui(self, main_widget):
#         # Apply styles handled by style.css (parent should load it)
#
#         self.layout = QVBoxLayout(main_widget)
#         self.layout.setSpacing(15)
#         self.layout.setContentsMargins(20, 20, 20, 20)
#
#         # 2. Toolbar
#         self.toolbar_layout = QHBoxLayout()
#         self.toolbar_layout.setSpacing(10)
#
#         self.search_input = QLineEdit()
#         self.search_input.setPlaceholderText("Quick Search (Code, Customer, Lot)...")
#         self.search_input.setFixedWidth(350)
#         self.toolbar_layout.addWidget(self.search_input)
#
#         # --- SPACER to push buttons to Right Side ---
#         self.toolbar_layout.addStretch()
#
#
#         # Filter Button (New)
#         self.filter_btn = QPushButton("Filter Records")
#         self.filter_btn.setObjectName("ActionButton")
#         self.filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
#         self.filter_btn.setMinimumWidth(120)
#
#         # Refresh Button
#         self.refresh_btn = QPushButton("Refresh")
#         self.refresh_btn.setObjectName("ActionButton")
#         self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
#
#         self.toolbar_layout.addWidget(self.search_input)
#         self.toolbar_layout.addWidget(self.filter_btn)  # Added here
#         self.toolbar_layout.addWidget(self.refresh_btn)
#         self.toolbar_layout.addStretch()
#
#         self.layout.addLayout(self.toolbar_layout)
#
#         # 3. Data Table
#         self.data_table = QTableWidget()
#         self.data_table.setAlternatingRowColors(False)
#         self.data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
#         self.data_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
#         self.data_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
#         self.data_table.verticalHeader().setVisible(False)
#         self.data_table.setShowGrid(True)
#
#         columns = [
#             "ID", "Date", "Code", "Customer", "Machine No",
#             "Lot Number", "Qty Input", "Qty Output", "Output/Hr",
#             "Screw Config", "RPM", "Resin Used", "Remarks"
#         ]
#         self.data_table.setColumnCount(len(columns))
#         self.data_table.setHorizontalHeaderLabels(columns)
#
#         header = self.data_table.horizontalHeader()
#         header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
#         header.setStretchLastSection(True)
#
#         # Default Widths
#         self.data_table.setColumnWidth(0, 60)  # ID
#         self.data_table.setColumnWidth(1, 100)  # Date
#         self.data_table.setColumnWidth(2, 120)  # Code
#         self.data_table.setColumnWidth(3, 180)  # Customer
#         self.data_table.setColumnWidth(4, 80)  # Machine
#         self.data_table.setColumnWidth(5, 120)  # Lot
#
#         self.layout.addWidget(self.data_table)


# app/views/extruder_old_records/excel_records/ui_setup.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSizePolicy, QSpacerItem
)


class ExtruderExcelRecordsUI:
    def setup_ui(self, main_widget):
        # 1. Main Vertical Layout
        self.layout = QVBoxLayout(main_widget)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(20, 20, 20, 20)



        # 2. Toolbar / Filter Layout (Using the logic you provided)
        self.filter_layout = QHBoxLayout()

        # --- LEFT SIDE CONTENT ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Quick Search (Code, Customer, Lot)...")
        self.search_input.setFixedWidth(300)  # Keep search bar a reasonable size
        self.filter_layout.addWidget(self.search_input)

        # --- THE KEY FIX: PUSH CONTENT TO THE RIGHT ---
        # Adding a stretch here acts like a spring, pushing everything
        # added AFTER it to the far right corner.
        self.filter_layout.addStretch()

        # --- RIGHT SIDE BUTTONS ---

        # Advanced Filter Button
        self.filter_btn = QPushButton("Filter Options")
        self.filter_btn.setObjectName("ActionButton")
        self.filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_btn.setMinimumWidth(120)
        self.filter_layout.addWidget(self.filter_btn)

        # # Optional Spacer between buttons (visual breathing room)
        # self.filter_layout.addSpacerItem(
        #     QSpacerItem(5, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        # )

        # Refresh Button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("ActionButton")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_layout.addWidget(self.refresh_btn)

        # Add this horizontal layout to the main vertical layout
        self.layout.addLayout(self.filter_layout)

        # 3. Data Table
        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(False)
        self.data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.data_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.data_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.data_table.verticalHeader().setVisible(False)
        self.data_table.setShowGrid(True)

        # Columns
        columns = [
            "ID", "Date", "Code", "Customer", "Machine No",
            "Lot Number", "Qty Input", "Qty Output", "Output/Hr",
            "Screw Config", "RPM", "Resin Used", "Remarks"
        ]
        self.data_table.setColumnCount(len(columns))
        self.data_table.setHorizontalHeaderLabels(columns)

        header = self.data_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        # Default Column Widths
        self.data_table.setColumnWidth(0, 60)  # ID
        self.data_table.setColumnWidth(1, 100)  # Date
        self.data_table.setColumnWidth(2, 120)  # Code
        self.data_table.setColumnWidth(3, 180)  # Customer
        self.data_table.setColumnWidth(4, 80)  # Machine
        self.data_table.setColumnWidth(5, 120)  # Lot

        self.layout.addWidget(self.data_table)