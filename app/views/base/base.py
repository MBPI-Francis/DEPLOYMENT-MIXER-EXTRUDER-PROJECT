# app/views/base/base.py

import os
from typing import Type, Callable

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStackedWidget, QPushButton, QScrollArea, QFrame
)
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QSize
from sqlalchemy.orm import Session
import qtawesome as qta

from app.helpers import load_styles
from app.views.extruder_report import ExtruderReportView
from app.views.extruder_form import ExtruderFormView
from app.views.mixer_report import MixerReportView
from app.views.base.side_menu import SideMenu
# --- Import the new TopNavBar ---
from .top_navbar import TopNavBar
from .status_bar import BottomStatusBar
from ..mixer_form import MixerFormMainView
from ..mixer_machine.main import MixerMachineMainView
from app.features.sync_legacy_db import SyncController
from ..mixer_old_records.main_view import MixerOldRecordsView


class Base(QMainWindow):
    """
    The main window and base layout for the entire application, featuring a
    collapsible side menu and a dynamic, scrollable content area.
    """

    def __init__(
            self,
            session_factory: Callable[..., Session],
            username: str,
            role: str,
            login_widget: QWidget,
            *args,
            **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.Session = session_factory
        self.username = username
        self.role = role
        self.login_widget = login_widget
        self.side_menu_is_expanded = True
        self.page_titles = []

        self.setWindowTitle("Mixer & Extruder Program")
        self.resize(1600, 800)
        self.setWindowIcon(qta.icon("fa5s.cogs", color="steelblue"))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        side_menu_handler = SideMenu()
        self.side_menu = side_menu_handler.side_menu_widget(dashboard=self)
        main_layout.addWidget(self.side_menu)

        right_side_container = QWidget()
        right_side_layout = QVBoxLayout(right_side_container)
        right_side_layout.setContentsMargins(0, 0, 0, 0)
        right_side_layout.setSpacing(0)
        main_layout.addWidget(right_side_container, 1)

        # --- MODIFIED: Use the new TopNavBar class ---
        # 1. Create an instance of the new TopNavBar. It needs a reference
        #    to this Base window to connect its buttons.
        self.top_bar = TopNavBar(dashboard=self)

        # 2. The main content area is now much simpler.
        main_content_area = self._create_main_content_area()

        right_side_layout.addWidget(self.top_bar)
        right_side_layout.addWidget(main_content_area, 1)
        # --- END MODIFICATION ---

        self._initialize_pages()
        side_menu_handler.connect_buttons()
        self.apply_styles()

        self.animation = QPropertyAnimation(self.side_menu, b"maximumWidth")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self.sync_controller = SyncController(engine=self.Session().bind, parent_widget=self)

    def _create_main_content_area(self) -> QWidget:
        """
        Creates the container for the QStackedWidget.
        The page title has been removed from here.
        """
        content_widget = QWidget()
        # Add some padding to the content area so it's not flush against the top bar
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(15)

        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget, 1)
        return content_widget

    def _initialize_pages(self):
        """Adds all pages to the stack and sets up the status bar."""
        self.add_stack_page("Mixer Machines", MixerMachineMainView(session_factory=self.Session))
        self.add_stack_page("Mixer Form", MixerFormMainView(session_factory=self.Session))
        self.add_stack_page("Mixer Old Records", MixerOldRecordsView(session_factory=self.Session))
        self.add_stack_page("Mixer Report", MixerReportView(session_factory=self.Session))
        self.add_stack_page("Extruder Form", ExtruderFormView(session_factory=self.Session))
        self.add_stack_page("Extruder Report", ExtruderReportView(session_factory=self.Session))

        self.stacked_widget.currentChanged.connect(self.on_page_changed)
        self.on_page_changed(0)

        bottom_status_bar = BottomStatusBar()
        bottom_status_bar.setup_status_bar(dashboard=self)

    def toggle_side_menu(self):
        """Animates the collapsing and expanding of the side menu."""
        # --- MODIFIED: Get the button from the top_bar instance ---
        if self.side_menu_is_expanded:
            self.animation.setStartValue(200)
            self.animation.setEndValue(0)
            self.top_bar.hamburger_button.setIcon(qta.icon("fa5s.bars", color="#2c3e50"))
        else:
            self.animation.setStartValue(0)
            self.animation.setEndValue(200)
            self.top_bar.hamburger_button.setIcon(qta.icon("fa5s.times", color="#2c3e50"))

        self.side_menu_is_expanded = not self.side_menu_is_expanded
        self.animation.start()

    def on_page_changed(self, index: int):
        """Updates the page title in the TopNavBar when the view changes."""
        if 0 <= index < len(self.page_titles):
            # --- MODIFIED: Call the method on the top_bar instance ---
            self.top_bar.set_page_title(self.page_titles[index])

    def add_stack_page(self, title: str, widget_instance: Type[QWidget]):
        """Creates a scrollable page for the given widget and adds it to the stack."""
        self.page_titles.append(title)
        page = self.create_scrollable_page(widget_instance)
        self.stacked_widget.addWidget(page)

    def create_scrollable_page(self, widget_instance: Type[QWidget]) -> QScrollArea:
        """
        Takes a widget and wraps it in a QScrollArea.
        This is the core of the scrolling feature.
        """
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(widget_instance)
        return scroll_area

    def set_username(self, value):
        self.username = value

    def set_role(self, value):
        self.role = value

    def apply_styles(self):
        """Loads the stylesheet for this base module."""
        qss_path = os.path.join(os.path.dirname(__file__), "styles", "base.css")
        load_styles(qss_path, self)

    def close_dashboard_main_window(self):
        """Handles closing the main window."""
        self.close()
        if self.login_widget:
            self.login_widget.show()

    def start_db_sync(self):
        """
        Starts the database synchronization process by calling the controller.
        """
        # --- MODIFIED: Get the button from the top_bar instance ---
        self.top_bar.sync_db_button.setEnabled(False)
        self.top_bar.sync_db_button.setText(" Syncing...")

        self.sync_controller.run_sync()

        # Connect signals to re-enable the button when the sync is done
        self.sync_controller.sync_worker.finished.connect(
            lambda: self.top_bar.sync_db_button.setEnabled(True))
        self.sync_controller.sync_worker.finished.connect(
            lambda: self.top_bar.sync_db_button.setText(" Sync Legacy DB"))
        self.sync_controller.sync_worker.error.connect(
            lambda: self.top_bar.sync_db_button.setEnabled(True))
        self.sync_controller.sync_worker.error.connect(
            lambda: self.top_bar.sync_db_button.setText(" Sync Legacy DB"))