from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSizePolicy, QSpacerItem
)


class ExtruderOldProgramRecordsUI:
    """
    UI Definition for Old Program Records (Amiel Data).
    """

    def setup_ui(self, main_widget):
        # 1. Main Vertical Layout
        self.layout = QVBoxLayout(main_widget)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(20, 20, 20, 20)

        # 2. Toolbar / Filter Layout
        self.filter_layout = QHBoxLayout()

        # --- LEFT: Search ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Code, Customer, Remarks...")
        self.search_input.setFixedWidth(300)
        self.filter_layout.addWidget(self.search_input)

        # --- CENTER: Spring ---
        self.filter_layout.addStretch()

        # --- RIGHT: Buttons ---

        # Placeholder for future Filter button (kept simple for now as requested)
        self.filter_btn = QPushButton("Filter Options")
        self.filter_btn.setObjectName("ActionButton")
        self.filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_btn.setMinimumWidth(120)
        self.filter_layout.addWidget(self.filter_btn)

        # Spacer
        self.filter_layout.addSpacerItem(
            QSpacerItem(10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum)
        )

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setObjectName("ActionButton")
        self.refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_layout.addWidget(self.refresh_btn)

        self.layout.addLayout(self.filter_layout)

        # 3. Data Table
        self.data_table = QTableWidget()
        self.data_table.setAlternatingRowColors(False)
        self.data_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.data_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.data_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.data_table.verticalHeader().setVisible(False)
        self.data_table.setShowGrid(True)

        # Key Columns for ExtruderOldAmielData
        columns = [
            "ID", "Date", "Code", "Customer", "Machine",
            "Lot Number", "Qty Order", "Total Output", "Efficiency %", "Remarks"
        ]
        self.data_table.setColumnCount(len(columns))
        self.data_table.setHorizontalHeaderLabels(columns)

        header = self.data_table.horizontalHeader()
        # header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        # header.setStretchLastSection(True)
        #
        # # Default Widths
        # self.data_table.setColumnWidth(0, 60)  # Process ID
        # self.data_table.setColumnWidth(1, 100)  # Encoded On
        # self.data_table.setColumnWidth(2, 120)  # Product Code
        # self.data_table.setColumnWidth(3, 180)  # Customer
        # self.data_table.setColumnWidth(4, 100)  # Machine
        # self.data_table.setColumnWidth(5, 120)  # Lot Number

        # This sets ALL columns to automatically resize to fit their content
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)

        # Optional: Set a minimum width for the stretch columns so they don't get too small
        header.setMinimumSectionSize(100)


        self.layout.addWidget(self.data_table)