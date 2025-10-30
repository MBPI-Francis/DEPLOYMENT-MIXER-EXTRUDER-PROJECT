# app/views/extruder_form/records/ui_setup.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QAbstractItemView,
    QHeaderView, QLabel, QDateEdit, QCheckBox, QGroupBox, QSpacerItem, QSizePolicy
)
from PyQt6.QtCore import QDate, Qt


class Ui_ExtruderRecordsList(object):
    def setupUi(self, Form: QWidget):
        Form.setObjectName("ExtruderRecordsList")
        Form.setWindowTitle("Extruder Production Records")
        self.main_layout = QVBoxLayout(Form)

        self.filter_group_box = QGroupBox("Filter and Search")
        self.filter_layout = QHBoxLayout(self.filter_group_box)

        # --- MODIFIED: Re-arranged the filter bar ---
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Global Search (Lot, Product, Customer...)")
        self.filter_layout.addWidget(self.search_input, 2)  # Give search more space

        self.date_from_label = QLabel("From:")
        self.date_from_input = QDateEdit()
        self.date_from_input.setCalendarPopup(True)
        self.date_from_input.setFixedWidth(120)
        self.date_from_input.setDate(QDate.currentDate().addMonths(-1))  # Default to last month

        self.date_to_label = QLabel("To:")
        self.date_to_input = QDateEdit()
        self.date_to_input.setCalendarPopup(True)
        self.date_to_input.setFixedWidth(120)
        self.date_to_input.setDate(QDate.currentDate())

        self.filter_layout.addWidget(self.date_from_label)
        self.filter_layout.addWidget(self.date_from_input)
        self.filter_layout.addWidget(self.date_to_label)
        self.filter_layout.addWidget(self.date_to_input)

        # --- MODIFIED: Changed the checkbox text and added it to the layout ---
        self.show_only_deleted_checkbox = QCheckBox("Show Only Deleted Records")
        self.filter_layout.addWidget(self.show_only_deleted_checkbox)

        self.filter_layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Minimum))

        # --- NEW: Add Advanced Filter and Clear buttons ---
        self.advanced_filter_button = QPushButton("Advanced Filters...")
        self.filter_layout.addWidget(self.advanced_filter_button)

        self.clear_filters_button = QPushButton("Clear All Filters")
        self.filter_layout.addWidget(self.clear_filters_button)

        self.filter_layout.addStretch()
        self.main_layout.addWidget(self.filter_group_box)

        self.table_widget = QTableWidget()
        self.table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.verticalHeader().setVisible(False)

        # --- MODIFIED: Re-enable sorting ---
        self.table_widget.setSortingEnabled(True)

        self._setup_table_columns()
        self.main_layout.addWidget(self.table_widget, 1)

    def _setup_table_columns(self):
        self.table_widget.setColumnCount(13)
        self.table_widget.setHorizontalHeaderLabels([
            "ID", "Date Encoded", "Machine No.", "Product Code", "Lot Number",
            "Time Start", "Time End", "Output/hr (kg)", "Target Output/hr",
            "Total Output (kg)", "Purging to Code", "Total Purging Time", "Operator(s)"
        ])
        self.table_widget.setColumnHidden(0, True)
        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(12, QHeaderView.ResizeMode.Stretch)