import os
from typing import Type, Callable

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStackedWidget, QPushButton, QScrollArea, QFrame
)
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QFont
from sqlalchemy.orm import Session
import qtawesome as qta

from app.helpers import load_styles
from app.views.extruder_report import ExtruderReportView
from app.views.mixer_form import MixerFormView
from app.views.extruder_form import ExtruderFormView
from app.views.mixer_report import MixerReportView
from app.views.base.side_menu import SideMenu
from .status_bar import BottomStatusBar
from ..mixer_machine.main import MixerMachineMainView

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

        # --- CORRECTED INITIALIZATION ORDER ---
        # 1. Create an instance of the SideMenu handler/factory class.
        side_menu_handler = SideMenu()
        
        # 2. Call the factory method to get the actual QWidget for the side menu.
        self.side_menu = side_menu_handler.side_menu_widget(dashboard=self)
        main_layout.addWidget(self.side_menu)
        
        # 3. Create the container for the right side of the screen.
        right_side_container = QWidget()
        right_side_layout = QVBoxLayout(right_side_container)
        right_side_layout.setContentsMargins(0, 0, 0, 0)
        right_side_layout.setSpacing(0)
        main_layout.addWidget(right_side_container, 1)

        # 4. Create the UI elements that will be placed on the right side.
        top_bar = self._create_top_bar()
        main_content_area = self._create_main_content_area()
        
        right_side_layout.addWidget(top_bar)
        right_side_layout.addWidget(main_content_area, 1)

        # --- Post-UI Initialization ---
        self._initialize_pages()
        # 5. Now that self.stacked_widget exists, call the handler to connect the signals.
        side_menu_handler.connect_buttons()
        self.apply_styles()
        
        self.animation = QPropertyAnimation(self.side_menu, b"maximumWidth")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

    def _create_top_bar(self) -> QWidget:
        """Creates the top bar widget with a hamburger menu and user profile."""
        top_bar = QWidget()
        top_bar.setObjectName("TopBar")
        top_bar.setFixedHeight(50)
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(10, 0, 10, 0)

        self.hamburger_button = QPushButton(icon=qta.icon("fa5s.times", color="#2c3e50"))
        self.hamburger_button.setIconSize(QSize(20, 20))
        self.hamburger_button.setObjectName("TopBarButton")
        self.hamburger_button.clicked.connect(self.toggle_side_menu)
        layout.addWidget(self.hamburger_button)
        layout.addStretch()
        
        notification_button = QPushButton()
        notification_button.setIcon(qta.icon("fa5s.bell", color="#2c3e50"))
        notification_button.setObjectName("TopBarButton")
        layout.addWidget(notification_button)
        
        profile_widget = QWidget()
        profile_widget.setObjectName("TopBarProfileWidget")
        profile_layout = QHBoxLayout(profile_widget)
        profile_layout.setContentsMargins(0,0,0,0)
        profile_layout.setSpacing(10)
        user_label = QLabel(f"<strong>{self.username.title()}</strong>")
        user_label.setObjectName("TopBarUserLabel")
        profile_layout.addWidget(user_label)
        user_icon = QLabel()
        user_icon.setPixmap(qta.icon("fa5s.user-circle", color="#2c3e50").pixmap(30, 30))
        profile_layout.addWidget(user_icon)
        layout.addWidget(profile_widget)
        return top_bar

    def _create_main_content_area(self) -> QWidget:
        """Creates the container for the page title and the QStackedWidget."""
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)

        self.page_title_label = QLabel("Page Title")
        self.page_title_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.page_title_label.setObjectName("PageTitle")
        layout.addWidget(self.page_title_label)

        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget, 1)
        return content_widget

    def _initialize_pages(self):
        """Adds all pages to the stack and sets up the status bar."""
        self.add_stack_page("Mixer Machines", MixerMachineMainView(session_factory=self.Session))
        self.add_stack_page("Mixer Form", MixerFormView(session_factory=self.Session))
        self.add_stack_page("Mixer Report", MixerReportView(session_factory=self.Session))
        self.add_stack_page("Extruder Form", ExtruderFormView(session_factory=self.Session))
        self.add_stack_page("Extruder Report", ExtruderReportView(session_factory=self.Session))

        self.stacked_widget.currentChanged.connect(self.on_page_changed)
        self.on_page_changed(0)

        bottom_status_bar = BottomStatusBar()
        bottom_status_bar.setup_status_bar(dashboard=self)

    def toggle_side_menu(self):
        """Animates the collapsing and expanding of the side menu."""
        if self.side_menu_is_expanded:
            self.animation.setStartValue(200)
            self.animation.setEndValue(0)
            self.hamburger_button.setIcon(qta.icon("fa5s.bars", color="#2c3e50"))
        else:
            self.animation.setStartValue(0)
            self.animation.setEndValue(200)
            self.hamburger_button.setIcon(qta.icon("fa5s.times", color="#2c3e50"))
        
        self.side_menu_is_expanded = not self.side_menu_is_expanded
        self.animation.start()

    def on_page_changed(self, index: int):
        """Updates the main page title when the view changes."""
        if 0 <= index < len(self.page_titles):
            self.page_title_label.setText(self.page_titles[index])

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