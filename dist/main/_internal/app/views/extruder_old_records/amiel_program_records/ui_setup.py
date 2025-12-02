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

        # --- LEFT: Search ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search Code, Machine, Remarks...")
        self.search_input.setFixedWidth(300)
        self.filter_layout.addWidget(self.search_input)

        # --- CENTER: Spring ---
        self.filter_layout.addStretch()

        # --- RIGHT: Buttons ---
        self.filter_btn = QPushButton("Filter Options")
        self.filter_btn.setObjectName("ActionButton")
        self.filter_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.filter_btn.setMinimumWidth(120)
        self.filter_layout.addWidget(self.filter_btn)

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

        # --- UPDATED COLUMNS LIST (14 Columns) ---
        columns = [
            "Date Encoded",  # 0
            "Machine",  # 1
            "Code",  # 2
            "Lot No.",  # 3
            "Screw Config",  # 4 (New)
            "Resin used",  # 5 (New)
            "Time Start",  # 6
            "Time End",  # 7
            "Output/Hr",  # 8
            "Total Output",  # 9
            "Output %",  # 10
            "Operator",  # 11 (New)
            "Supervisor",  # 12 (New)
            "Remarks"  # 13
        ]
        self.data_table.setColumnCount(len(columns))
        self.data_table.setHorizontalHeaderLabels(columns)

        # --- COLUMN RESIZING ---
        header = self.data_table.horizontalHeader()

        # Default: Resize to fit content tightly
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        # Specific: Stretch Remarks (Index 13) to fill any remaining gap
        header.setSectionResizeMode(13, QHeaderView.ResizeMode.Stretch)

        header.setMinimumSectionSize(80)

        self.layout.addWidget(self.data_table)