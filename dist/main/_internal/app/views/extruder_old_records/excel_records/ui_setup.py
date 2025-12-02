from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QSizePolicy, QSpacerItem
)


class ExtruderExcelRecordsUI:
    # --- ADDED: Style for the View Remarks button ---
    LINK_BUTTON_STYLE = """
        QPushButton {
            background-color: transparent;
            border: none;
            color: #0d6efd;
            text-align: left;
            font-size: 13px;
            padding: 0px;
        }
        QPushButton:hover {
            text-decoration: underline;
            color: #0a58ca;
        }
        QPushButton:pressed {
            color: #0a58ca;
        }
    """

    def setup_ui(self, main_widget):
        # 1. Main Vertical Layout
        self.layout = QVBoxLayout(main_widget)
        self.layout.setSpacing(15)
        self.layout.setContentsMargins(20, 20, 20, 20)

        # 2. Toolbar / Filter Layout
        self.filter_layout = QHBoxLayout()

        # --- LEFT SIDE CONTENT ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Quick Search (Code, Customer, Lot)...")
        self.search_input.setFixedWidth(300)
        self.filter_layout.addWidget(self.search_input)

        # --- PUSH CONTENT TO THE RIGHT ---
        self.filter_layout.addStretch()

        # --- RIGHT SIDE BUTTONS ---
        self.filter_btn = QPushButton("Filter Options")
        self.filter_btn.setObjectName("ActionButton")
        self.filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_btn.setMinimumWidth(120)
        self.filter_layout.addWidget(self.filter_btn)

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

        columns = [
            "ID", "Date", "Code", "Customer", "Machine",
            "Lot No.", "Total Input", "Total Output", "Output/Hr",
            "Screw Config", "RPM", "Resin used", "Remarks"
        ]
        self.data_table.setColumnCount(len(columns))
        self.data_table.setHorizontalHeaderLabels(columns)

        header = self.data_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)

        # Default Column Widths
        self.data_table.setColumnWidth(0, 60)
        self.data_table.setColumnWidth(1, 100)
        self.data_table.setColumnWidth(2, 120)
        self.data_table.setColumnWidth(3, 180)
        self.data_table.setColumnWidth(4, 80)
        self.data_table.setColumnWidth(5, 120)

        self.layout.addWidget(self.data_table)