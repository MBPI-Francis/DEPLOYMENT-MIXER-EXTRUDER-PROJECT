from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QComboBox, QListView, QFrame
)
from PyQt6.QtCore import Qt, QTimer
from sqlalchemy.orm import sessionmaker
from models.ExtruderOld import ExtruderOldAmielData
from .ops import ExtruderOldProgramRecordsOps


class LazyComboBox(QComboBox):
    """
    Generic Lazy Loading ComboBox.
    """

    def __init__(self, session_factory: sessionmaker, column_model, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.column_model = column_model

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.setMaxVisibleItems(10)

        self.view_list = QListView()
        self.setView(self.view_list)
        self.view_list.verticalScrollBar().valueChanged.connect(self.on_scroll)

        self.current_offset = 0
        self.limit = 20
        self.has_more = True
        self.filter_text = ""

        self.search_timer = QTimer()
        self.search_timer.setSingleShot(True)
        self.search_timer.timeout.connect(self.reload_data)

        self.lineEdit().textEdited.connect(self.on_text_edited)
        self.reload_data(initial=True)

    def on_text_edited(self, text):
        self.filter_text = text
        self.search_timer.start(300)

    def on_scroll(self, value):
        if not self.has_more: return
        if value >= self.view_list.verticalScrollBar().maximum() - 2:
            self.load_next_batch()

    def reload_data(self, initial=False):
        self.clear()
        self.current_offset = 0
        self.has_more = True

        self.addItem("<blank>")

        if self.filter_text: pass

        self.fetch_items()

        if initial or not self.filter_text:
            self.setCurrentIndex(-1)
        else:
            self.setCurrentText(self.filter_text)

    def load_next_batch(self):
        self.current_offset += self.limit
        self.fetch_items()

    def fetch_items(self):
        with self.Session() as session:
            values = ExtruderOldProgramRecordsOps.get_distinct_values(
                session, self.column_model, self.filter_text, self.limit, self.current_offset
            )
            if len(values) < self.limit: self.has_more = False
            for val in values:
                if val != "<blank>" and self.findText(val) == -1:
                    self.addItem(val)


class FilterDialog(QDialog):
    STYLESHEET = """
        QDialog { background-color: #ffffff; }
        QLabel { font-size: 14px; color: #2c3e50; font-weight: 500; }
        QLineEdit, QComboBox {
            border: 1px solid #ced4da; border-radius: 4px; padding: 6px 10px; font-size: 14px; background-color: #ffffff;
        }
        QLineEdit:focus, QComboBox:focus { border: 1px solid #3b82f6; }
        QComboBox QAbstractItemView {
            background-color: #ffffff; border: 1px solid #ced4da; selection-background-color: #e7f5ff; selection-color: #000000; outline: none; padding: 5px;
        }
        QPushButton { padding: 8px 16px; border-radius: 4px; font-size: 14px; font-weight: bold; }
        QPushButton#EditDialogCancelButton { background-color: #ffffff; color: #495057; border: 1px solid #ced4da; }
        QPushButton#EditDialogCancelButton:hover { background-color: #f1f3f5; }
        QPushButton#PrimaryDialogButton { background-color: #0d6efd; color: white; border: none; }
        QPushButton#PrimaryDialogButton:hover { background-color: #0b5ed7; }
    """

    def __init__(self, session_factory: sessionmaker, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Advanced Filter")
        self.setFixedWidth(500)
        self.setStyleSheet(self.STYLESHEET)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(20)

        title = QLabel("Filter Program Records")
        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #212529; margin-bottom: 10px;")
        layout.addWidget(title)

        self.form_layout = QFormLayout()
        self.form_layout.setSpacing(15)

        # --- Lazy Combos ---
        self.input_code = LazyComboBox(session_factory, ExtruderOldAmielData.product_code)
        self.input_code.setPlaceholderText("Select Code")

        self.input_customer = LazyComboBox(session_factory, ExtruderOldAmielData.customer)
        self.input_customer.setPlaceholderText("Select Customer")

        self.input_machine = LazyComboBox(session_factory, ExtruderOldAmielData.machine)
        self.input_machine.setPlaceholderText("Select Machine")

        self.input_screw = LazyComboBox(session_factory, ExtruderOldAmielData.screw_config)
        self.input_screw.setPlaceholderText("Select Screw")

        self.input_resin = LazyComboBox(session_factory, ExtruderOldAmielData.resin)
        self.input_resin.setPlaceholderText("Select Resin")

        self.input_operator = LazyComboBox(session_factory, ExtruderOldAmielData.operator)
        self.input_operator.setPlaceholderText("Select Operator")

        self.input_supervisor = LazyComboBox(session_factory, ExtruderOldAmielData.supervisor)
        self.input_supervisor.setPlaceholderText("Select Supervisor")

        # --- Text Inputs ---
        self.input_lot = QLineEdit()
        self.input_lot.setPlaceholderText("Lot Number")

        self.input_date = QLineEdit()
        self.input_date.setPlaceholderText("Encoded On (Date)")

        self.input_remarks = QLineEdit()
        self.input_remarks.setPlaceholderText("Remarks")

        # Layout
        self.form_layout.addRow("Code:", self.input_code)
        self.form_layout.addRow("Customer:", self.input_customer)
        self.form_layout.addRow("Machine:", self.input_machine)
        self.form_layout.addRow("Lot Number:", self.input_lot)
        self.form_layout.addRow("Screw Config:", self.input_screw)
        self.form_layout.addRow("Resin:", self.input_resin)
        self.form_layout.addRow("Operator:", self.input_operator)
        self.form_layout.addRow("Supervisor:", self.input_supervisor)
        self.form_layout.addRow("Encoded On:", self.input_date)
        self.form_layout.addRow("Remarks:", self.input_remarks)

        layout.addLayout(self.form_layout)

        line = QFrame();
        line.setFrameShape(QFrame.Shape.HLine);
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("background-color: #dee2e6;")
        layout.addWidget(line)

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
        if not filters: return

        def set_c(combo, k):
            if filters.get(k):
                combo.setCurrentText(filters[k])
            else:
                combo.setCurrentIndex(-1)

        set_c(self.input_code, 'code')
        set_c(self.input_customer, 'customer')
        set_c(self.input_machine, 'machine')
        set_c(self.input_screw, 'screw_config')
        set_c(self.input_resin, 'resin')
        set_c(self.input_operator, 'operator')
        set_c(self.input_supervisor, 'supervisor')

        if filters.get('lot'): self.input_lot.setText(filters['lot'])
        if filters.get('date'): self.input_date.setText(filters['date'])
        if filters.get('remarks'): self.input_remarks.setText(filters['remarks'])

    def get_filters(self):
        filters = {}

        def get_c(combo, k):
            if combo.currentText().strip(): filters[k] = combo.currentText().strip()

        get_c(self.input_code, 'code')
        get_c(self.input_customer, 'customer')
        get_c(self.input_machine, 'machine')
        get_c(self.input_screw, 'screw_config')
        get_c(self.input_resin, 'resin')
        get_c(self.input_operator, 'operator')
        get_c(self.input_supervisor, 'supervisor')

        if self.input_lot.text().strip(): filters['lot'] = self.input_lot.text().strip()
        if self.input_date.text().strip(): filters['date'] = self.input_date.text().strip()
        if self.input_remarks.text().strip(): filters['remarks'] = self.input_remarks.text().strip()
        return filters

    def clear_inputs(self):
        for combo in [self.input_code, self.input_customer, self.input_machine, self.input_screw,
                      self.input_resin, self.input_operator, self.input_supervisor]:
            combo.clear();
            combo.filter_text = "";
            combo.reload_data(initial=True)
        self.input_lot.clear();
        self.input_date.clear();
        self.input_remarks.clear()