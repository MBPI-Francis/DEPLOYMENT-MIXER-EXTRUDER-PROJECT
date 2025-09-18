# app/views/base/base.py

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QStackedWidget, QPushButton
)
from PyQt6.QtCore import QPropertyAnimation, QEasingCurve, QSize
from PyQt6.QtGui import QFont
from typing import Type, Callable
from sqlalchemy.orm import Session
import qtawesome as qta
import os

from app.views.extruder_report import ExtruderReportView
from app.views.mixer_form import MixerFormView
from app.views.extruder_form import ExtruderFormView
from app.helpers import load_styles
from app.views.mixer_report import MixerReportView
from app.views.base.side_menu import SideMenu
from .status_bar import BottomStatusBar
from ..mixer_machine.main import MixerMachineMainView


class Base(QMainWindow):
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

        # Initialization
        self.Session = session_factory
        self.username = username
        self.role = role
        self.login_widget = login_widget
        self.side_menu_is_expanded = True
        self.page_titles = []

        self.setWindowTitle("Mixer & Extruder Program")
        # self.setGeometry(100, 100, 1300, 800)
        self.resize(1600, 720)
        self.setWindowIcon(qta.icon("fa5s.cogs", color="steelblue"))




        # --- RESTRUCTURED LAYOUT ---
        # The central widget's layout is now HORIZONTAL.
        # It will contain: [Side Menu] [Right Side Content]
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)



        # 1. SIDE MENU (Left side of the QHBoxLayout)
        side_menu_bar = SideMenu()
        self.side_menu = side_menu_bar.side_menu_widget(dashboard=self)
        main_layout.addWidget(self.side_menu)

        # 2. RIGHT SIDE CONTAINER (Right side of the QHBoxLayout)
        # This container will be a VERTICAL layout holding the Top Bar and the Main Content.
        right_side_container = QWidget()
        right_side_layout = QVBoxLayout(right_side_container)
        right_side_layout.setContentsMargins(0, 0, 0, 0)
        right_side_layout.setSpacing(0)
        main_layout.addWidget(right_side_container, 1)  # Add with stretch factor

        # 2a. Add Top Bar to the top of the right-side container
        top_bar = self._create_top_bar()
        right_side_layout.addWidget(top_bar)

        # 2b. Add Main Content Area to the bottom of the right-side container
        main_content_area = self._create_main_content_area()
        right_side_layout.addWidget(main_content_area, 1)  # Add with stretch factor

        # --- ANIMATION SETUP ---
        # Animation still targets the side menu, which will cause the right_side_container to stretch.
        self.animation = QPropertyAnimation(self.side_menu, b"maximumWidth")
        self.animation.setDuration(300)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)

        # --- INITIALIZE OTHER COMPONENTS ---
        self._initialize_pages()
        self.apply_styles()

    def _create_top_bar(self):
        """Creates the top status bar. This widget will now stretch correctly."""
        top_bar = QWidget()
        top_bar.setObjectName("TopBar")
        top_bar.setFixedHeight(50)
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        # HAMBURGER BUTTON (Left)
        self.hamburger_button = QPushButton()
        self.hamburger_button.setIcon(qta.icon("fa5s.times", color="#2c3e50"))
        self.hamburger_button.setIconSize(QSize(20, 20))
        self.hamburger_button.setObjectName("TopBarButton")  # Can use a more generic ID now
        self.hamburger_button.clicked.connect(self.toggle_side_menu)
        layout.addWidget(self.hamburger_button)

        layout.addStretch()

        # NOTIFICATION BUTTON (Right)
        notification_button = QPushButton()
        notification_button.setIcon(qta.icon("fa5s.bell", color="#2c3e50"))
        notification_button.setObjectName("TopBarButton")
        layout.addWidget(notification_button)

        # USER PROFILE (Far Right)
        profile_widget = QWidget()
        profile_widget.setObjectName("TopBarProfileWidget")
        profile_layout = QHBoxLayout(profile_widget)
        profile_layout.setContentsMargins(0, 0, 0, 0)
        profile_layout.setSpacing(10)

        user_label = QLabel(f"<strong>{self.username.title()}</strong>")
        user_label.setObjectName("TopBarUserLabel")
        profile_layout.addWidget(user_label)

        user_icon = QLabel()
        user_icon.setPixmap(qta.icon("fa5s.user-circle", color="#2c3e50").pixmap(30, 30))
        profile_layout.addWidget(user_icon)

        layout.addWidget(profile_widget)

        return top_bar

    def _create_main_content_area(self):
        """Creates the container for the page title and stacked widget."""
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        # We add margins here to create space between the top bar and content
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)

        self.page_title_label = QLabel("Page Title")
        self.page_title_label.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self.page_title_label.setObjectName("PageTitle")
        layout.addWidget(self.page_title_label)

        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        return content_widget

    def _initialize_pages(self):
        """Helper to add all pages to the stack and setup status bar."""
        self.add_stack_page("Mixer Machines", "Manage all mixer machine records",
                            MixerMachineMainView(session_factory=self.Session))
        self.add_stack_page("Mixer Form", "Create a new mixer production form",
                            MixerFormView(session_factory=self.Session))
        self.add_stack_page("Mixer Report", "View and generate mixer reports",
                            MixerReportView(session_factory=self.Session))
        self.add_stack_page("Extruder Form", "Create a new extruder production form",
                            ExtruderFormView(session_factory=self.Session))
        self.add_stack_page("Extruder Report", "View and generate extruder reports",
                            ExtruderReportView(session_factory=self.Session))

        self.stacked_widget.currentChanged.connect(self.on_page_changed)
        self.on_page_changed(0)

        bottom_status_bar = BottomStatusBar()
        bottom_status_bar.setup_status_bar(dashboard=self)

    def toggle_side_menu(self):
        if self.side_menu_is_expanded:
            self.animation.setStartValue(200)
            self.animation.setEndValue(0)
            self.side_menu_is_expanded = False
            self.hamburger_button.setIcon(qta.icon("fa5s.bars", color="#2c3e50"))
        else:
            self.animation.setStartValue(0)
            self.animation.setEndValue(200)
            self.side_menu_is_expanded = True
            self.hamburger_button.setIcon(qta.icon("fa5s.times", color="#2c3e50"))
        self.animation.start()

    # --- Other methods remain unchanged ---
    def on_page_changed(self, index: int):
        if 0 <= index < len(self.page_titles):
            self.page_title_label.setText(self.page_titles[index])

    def add_stack_page(self, title: str, message: str, widget_instance: Type[QWidget]):
        self.page_titles.append(title)
        page = self.create_stack_page(message, widget_instance)
        self.stacked_widget.addWidget(page)

    def create_stack_page(self, message: str, widget_instance: Type[QWidget]):
        main_page = QWidget()
        layout = QVBoxLayout(main_page)
        layout.setContentsMargins(0, 0, 0, 0)
        # layout.setSpacing(15)
        layout.setSpacing(10)
        # message_label = QLabel(message)
        # message_label.setFont(QFont("Segoe UI", 14))
        # message_label.setWordWrap(True)
        # message_label.setObjectName("PageMessage")
        # layout.addWidget(message_label)
        layout.addWidget(widget_instance)
        layout.addStretch()
        return main_page

    def set_username(self, value):
        self.username = value

    def set_role(self, value):
        self.role = value

    def apply_styles(self):
        qss_path = os.path.join(os.path.dirname(__file__), "styles", "base.css")
        load_styles(qss_path, self)

    def close_dashboard_main_window(self):
        self.close()
        self.login_widget.show()