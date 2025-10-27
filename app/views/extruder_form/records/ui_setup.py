# app/views/extruder_form/records/ui_setup.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QAbstractItemView,
    QHeaderView, QLabel, QDateEdit, QCheckBox, QGroupBox
)
from PyQt6.QtCore import QDate, Qt

class Ui_ExtruderRecordsList(object):
    def setupUi(self, Form: QWidget):
        Form.setObjectName("ExtruderRecordsList")
        Form.setWindowTitle("Extruder Production Records")
        self.main_layout = QVBoxLayout(Form)

        self.filter_group_box = QGroupBox("Filter and Search")
        self.filter_layout = QHBoxLayout(self.filter_group_box)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Lot No, Product Code, Customer...")
        self.filter_layout.addWidget(self.search_input, 1)

        self.date_from_label = QLabel("Date From:")
        self.date_from_input = QDateEdit()
        self.date_from_input.setCalendarPopup(True)
        self.date_from_input.setFixedWidth(120)
        self.date_from_input.setSpecialValueText(" ")
        self.date_from_input.setDate(QDate())

        self.date_to_label = QLabel("Date To:")
        self.date_to_input = QDateEdit()
        self.date_to_input.setCalendarPopup(True)
        self.date_to_input.setFixedWidth(120)
        self.date_to_input.setSpecialValueText(" ")
        self.date_to_input.setDate(QDate())

        self.filter_layout.addWidget(self.date_from_label)
        self.filter_layout.addWidget(self.date_from_input)
        self.filter_layout.addWidget(self.date_to_label)
        self.filter_layout.addWidget(self.date_to_input)

        self.show_deleted_checkbox = QCheckBox("Show Deleted Records")
        self.filter_layout.addWidget(self.show_deleted_checkbox)
        self.filter_layout.addStretch()
        self.main_layout.addWidget(self.filter_group_box)

        self.table_widget = QTableWidget()
        self.table_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.verticalHeader().setVisible(False)
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