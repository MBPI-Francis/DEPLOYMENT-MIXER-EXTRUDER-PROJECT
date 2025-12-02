from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QComboBox, QListView, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from sqlalchemy.orm import sessionmaker
from models import ExtruderOldExcelData
from .ops import ExtruderExcelRecordsOps


class LazyComboBox(QComboBox):
    """
    Generic Lazy Loading ComboBox for SQLAlchemy Columns.
    """

    def __init__(self, session_factory: sessionmaker, column_model, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.column_model = column_model


        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(10)

        # Use a QListView for better styling control of the dropdown
        self.view_list = QListView()
        self.setView(self.view_list)
        self.view_list.verticalScrollBar().valueChanged.connect(self.on_scroll)

        # State
        self.current_offset = 0
        self.limit = 20
        self.has_more = True
        self.filter_text = ""

        # Debounce for typing
        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.reload_data)

        self.lineEdit().textEdited.connect(self.on_text_edited)

        # Initial Load
        self.reload_data(initial=True)

    def on_text_edited(self, text):
        self.filter_text = text
        self.search_timer.start(300)

    def on_scroll(self, value):
        if not self.has_more:
            return
        if value >= self.view_list.verticalScrollBar().maximum() - 2:
            self.load_next_batch()

    def reload_data(self, initial=False):
        """
        Reloads the data.
        :param initial: If True, ensures no item is selected (empty display).
        """
        self.clear()
        self.current_offset = 0
        self.has_more = True

        # Always add <blank> as the first option in the list
        self.addItem("<blank>")

        # If user is typing, keep their text in the list/box
        if self.filter_text:
            # We don't add it as an item if it's just the search term,
            # but we ensure the line edit keeps the text.
            pass

        self.fetch_items()

        # LOGIC: Ensure visual state matches requirements
        if initial or not self.filter_text:
            self.setCurrentIndex(-1)  # Visually Empty
        else:
            self.setCurrentText(self.filter_text)

    def load_next_batch(self):
        self.current_offset += self.limit
        self.fetch_items()

    def fetch_items(self):
        with self.Session() as session:
            values = ExtruderExcelRecordsOps.get_distinct_values(
                session,
                self.column_model,
                self.filter_text,
                self.limit,
                self.current_offset
            )

            if len(values) < self.limit:
                self.has_more = False

            for val in values:
                # Prevent duplicates (and don't re-add <blank> if it came from DB somehow)
                if val != "<blank>" and self.findText(val) == -1:
                    self.addItem(val)


class FilterDialog(QDialog):
    # Specific Stylesheet for this Dialog to ensure cleaner look

    def __init__(self, session_factory: sessionmaker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter")
        self.setFixedWidth(500)


        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        # # Header
        # title = QLabel("Filter Records")
        # title.setStyleSheet("font-size: 18px; font-weight: bold; color: #212529; margin-bottom: 10px;")
        # layout.addWidget(title)

        # --- Form ---
        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(15)
        self.form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        # 1. Lazy Combos
        self.input_code = LazyComboBox(session_factory, ExtruderOldExcelData.code)
        self.input_code.setPlaceholderText("Select Product Code")

        self.input_customer = LazyComboBox(session_factory, ExtruderOldExcelData.customer)
        self.input_customer.setPlaceholderText("Select Customer")

        self.input_machine = LazyComboBox(session_factory, ExtruderOldExcelData.machine_no)
        self.input_machine.setPlaceholderText("Select Machine")

        self.input_lot = LazyComboBox(session_factory, ExtruderOldExcelData.lot_number)
        self.input_lot.setPlaceholderText("Select Lot Number")

        self.input_screw = LazyComboBox(session_factory, ExtruderOldExcelData.screw_config)
        self.input_screw.setPlaceholderText("Select Screw Config")

        self.input_resin = LazyComboBox(session_factory, ExtruderOldExcelData.resin_used)
        self.input_resin.setPlaceholderText("Select Resin")

        # 2. Text Inputs
        self.input_rpm = QLineEdit()
        self.input_rpm.setPlaceholderText("RPM")

        self.input_date = QLineEdit()
        self.input_date.setPlaceholderText("Date")

        self.input_remarks = QLineEdit()
        self.input_remarks.setPlaceholderText("Remarks")

        # Add Rows
        self.form_layout.addRow("Code:", self.input_code)
        self.form_layout.addRow("Customer:", self.input_customer)
        self.form_layout.addRow("Machine:", self.input_machine)
        self.form_layout.addRow("Lot #:", self.input_lot)
        self.form_layout.addRow("Screw:", self.input_screw)
        self.form_layout.addRow("Resin:", self.input_resin)
        self.form_layout.addRow("RPM:", self.input_rpm)
        self.form_layout.addRow("Date:", self.input_date)
        self.form_layout.addRow("Remarks:", self.input_remarks)

        layout.addLayout(self.form_layout)

        # --- Separator ---
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #dee2e6;")
        layout.addWidget(line)

        # --- Buttons ---
        btn_layout = QHBoxLayout()
        self.btn_clear = QPushButton("Clear All")
        self.btn_clear.setObjectName("EditDialogCancelButton")
        self.btn_clear.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear_inputs)

        self.btn_apply = QPushButton("Apply Filter")
        self.btn_apply.setObjectName("PrimaryDialogButton")
        self.btn_apply.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_apply.clicked.connect(self.accept)

        btn_layout.addWidget(self.btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_apply)

        layout.addLayout(btn_layout)

    def set_current_filters(self, filters: dict):
        """
        Populates the dialog with existing filter values.
        """
        if not filters:
            return

        def set_combo(combo, key):
            val = filters.get(key)
            if val:
                combo.setCurrentText(val)
            else:
                combo.setCurrentIndex(-1)

        set_combo(self.input_code, 'code')
        set_combo(self.input_customer, 'customer')
        set_combo(self.input_machine, 'machine')
        set_combo(self.input_lot, 'lot')
        set_combo(self.input_screw, 'screw_config')
        set_combo(self.input_resin, 'resin_used')

        if filters.get('rpm'): self.input_rpm.setText(filters['rpm'])
        if filters.get('date'): self.input_date.setText(filters['date'])
        if filters.get('remarks'): self.input_remarks.setText(filters['remarks'])

    def get_filters(self):
        filters = {}

        def get_combo(combo, key):
            txt = combo.currentText().strip()
            if txt:
                filters[key] = txt

        get_combo(self.input_code, 'code')
        get_combo(self.input_customer, 'customer')
        get_combo(self.input_machine, 'machine')
        get_combo(self.input_lot, 'lot')
        get_combo(self.input_screw, 'screw_config')
        get_combo(self.input_resin, 'resin_used')

        if self.input_rpm.text().strip(): filters['rpm'] = self.input_rpm.text().strip()
        if self.input_date.text().strip(): filters['date'] = self.input_date.text().strip()
        if self.input_remarks.text().strip(): filters['remarks'] = self.input_remarks.text().strip()

        return filters

    def clear_inputs(self):
        # Reset Combos
        for combo in [self.input_code, self.input_customer, self.input_machine,
                      self.input_lot, self.input_screw, self.input_resin]:
            combo.clear()
            combo.filter_text = ""
            combo.reload_data(initial=True)  # Forces empty state

        # Reset Text
        self.input_rpm.clear()
        self.input_date.clear()
        self.input_remarks.clear()