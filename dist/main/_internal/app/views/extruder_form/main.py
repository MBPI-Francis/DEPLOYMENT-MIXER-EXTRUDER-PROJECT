from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout, QMessageBox
from typing import Type
from sqlalchemy.orm import Session
from models import User

class ExtruderFormView(QWidget):
    def __init__(self, session_factory: Type[Session], parent=None):
        super().__init__(parent)

        self.main_layout = QVBoxLayout()
        self.mixer_label = QLabel("Extruder Form")
        self.Session = session_factory

        self.main_layout.addWidget(self.mixer_label)
        self.setLayout(self.main_layout)
        self.add_details()

    def add_details(self):
        try:
            session = self.Session()
            model = User

            instance = session.query(model).all()


        finally:
            session.close()