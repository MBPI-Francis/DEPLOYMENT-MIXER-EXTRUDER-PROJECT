# app/views/extruder_form/records/ui_setup.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLineEdit,
    QPushButton, QTableWidget, QAbstractItemView,
    QHeaderView, QLabel, QDateEdit, QCheckBox, QGroupBox
)
from PyQt6.QtCore import QDate, Qt


class Ui_ExtruderRecordsList(object):
    """
    Defines the UI for the Extruder Records List module.
    This class is responsible only for building and laying out static widgets.
    """

    def setupUi(self, Form: QWidget):
        Form.setObjectName("ExtruderRecordsList")
        Form.setWindowTitle("Extruder Production Records")

        # Main Vertical Layout
        self.main_layout = QVBoxLayout(Form)

        # --- Filtering and Search Group ---
        self.filter_group_box = QGroupBox("Filter and Search")
        self.filter_layout = QHBoxLayout(self.filter_group_box)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by Lot No, Product Code, Customer...")
        self.filter_layout.addWidget(self.search_input, 1)  # Stretch factor of 1

        self.date_filter_label = QLabel("Filter by Date:")
        self.date_filter_input = QDateEdit()
        self.date_filter_input.setCalendarPopup(True)
        self.date_filter_input.setDate(QDate.currentDate())
        self.date_filter_input.setFixedWidth(120)

        self.clear_date_button = QPushButton("Clear Date")
        self.clear_date_button.setFixedWidth(80)

        self.filter_layout.addWidget(self.date_filter_label)
        self.filter_layout.addWidget(self.date_filter_input)
        self.filter_layout.addWidget(self.clear_date_button) # Add it to the layout

        self.show_deleted_checkbox = QCheckBox("Show Deleted Records")
        self.filter_layout.addWidget(self.show_deleted_checkbox)

        self.main_layout.addWidget(self.filter_group_box)

        # --- Actions Group ---
        self.actions_group_box = QGroupBox("Actions")
        self.action_buttons_layout = QHBoxLayout(self.actions_group_box)

        self.edit_view_button = QPushButton("View / Edit Record")
        self.delete_button = QPushButton("Delete Record")
        self.restore_button = QPushButton("Restore Record")

        self.action_buttons_layout.addWidget(self.edit_view_button)
        self.action_buttons_layout.addWidget(self.delete_button)
        self.action_buttons_layout.addWidget(self.restore_button)
        self.action_buttons_layout.addStretch()  # Pushes buttons to the left

        self.main_layout.addWidget(self.actions_group_box)

        # --- Table for displaying records ---
        self.table_widget = QTableWidget()
        self.table_widget.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table_widget.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_widget.setAlternatingRowColors(True)
        self.table_widget.verticalHeader().setVisible(False)
        self.table_widget.setSortingEnabled(True) # Enable column sorting
        self._setup_table_columns()

        self.main_layout.addWidget(self.table_widget, 1)

    def _setup_table_columns(self):
        """Initializes the new columns for the QTableWidget."""
        self.table_widget.setColumnCount(13)  # Add one for the hidden ID
        self.table_widget.setHorizontalHeaderLabels([
            "ID",  # Hidden
            "Date Encoded", "Machine No.", "Product Code", "Lot Number",
            "Time Start", "Time End", "Output/hr (kg)", "Target Output/hr",
            "Total Output (kg)", "Purging to Code", "Total Purging Time", "Operator(s)"
        ])

        self.table_widget.setColumnHidden(0, True)

        header = self.table_widget.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(12, QHeaderView.ResizeMode.Stretch)