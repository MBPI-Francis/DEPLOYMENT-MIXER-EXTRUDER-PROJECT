import os
from typing import Type, Callable

from PyQt6.QtGui import QAction, QKeySequence
from sqlalchemy.orm import sessionmaker, Session
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QMenu, QMessageBox, QFileDialog, QLineEdit, QLabel,
    QApplication, QDialog, QProgressBar
)
from PyQt6.QtCore import Qt, pyqtSlot, QPropertyAnimation, QTimer, QThread, pyqtSignal, QDate
import pandas as pd
import qtawesome as qta

from app.widgets.smart_combo_box import SmartComboBox
from models import User


class ExtruderResinView(QWidget):
    def __init__(self, session_factory: Type[Session], parent=None):
        super().__init__(parent)

        self.main_layout = QVBoxLayout()
        self.label = QLabel("Resin")
        self.Session = session_factory

        self.main_layout.addWidget(self.label)
        self.setLayout(self.main_layout)
        self.add_details()

    def add_details(self):
        try:
            session = self.Session()
            model = User

            instance = session.query(model).all()


        finally:
            session.close()