from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QMessageBox,
    QInputDialog
)
from PyQt6.QtGui import QFont, QPixmap
from PyQt6.QtCore import Qt, QSize
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Callable

from app.views.base.base import Base
from app.StyledMessage import StyledMessageBox

# import models here
from models import User, AuthLog

# registration
from app.auth.registration import Registration

# helpers
from app.helpers import button_cursor_pointer, record_auth_log, load_styles

# super password
from constants.Enums import ITCredentials, AuthLogStatus

import sys
import hashlib
import socket
import os
import qtawesome as qta

class LoginForm(QWidget):
    """
    A PyQt6 widget for user login interface.

    Provides username and password inputs, login button, and user registration option.
    Uses SQLAlchemy session factory for database access and validates user credentials.
    Displays dashboard on successful login and handles auth logging.

    Args:
        session_factory (Callable[..., Session]): Factory function to create SQLAlchemy sessions.
        *args: Additional positional arguments for QWidget.
        **kwargs: Additional keyword arguments for QWidget.
    """

    def __init__(self, session_factory: Callable[..., Session], *args, **kwargs):
        """
        Initialize the login form UI and setup signals and styles.

        Raises:
            SQLAlchemyError: If the database connection cannot be established.
        """

        super().__init__(*args, **kwargs)
        self.setWindowTitle("User Login")
        self.setFixedSize(400, 550)
        self.setWindowIcon(qta.icon("fa5s.lock", color="steelblue"))

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(40, 40, 40, 40)
        self.main_layout.setSpacing(20)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # LOGO
        self.logo_label = QLabel()
        pixmap = QPixmap(
            self.style()
            .standardIcon(self.style().StandardPixmap.SP_ComputerIcon)
            .pixmap(QSize(80, 80))
        )
        self.logo_label.setPixmap(pixmap)
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # TITLE
        self.title_label = QLabel("Welcome Back")
        self.title_label.setFont(QFont("Segoe UI", 22, QFont.Weight.Bold))
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # SUBTITLE
        self.subtitle_label = QLabel("Sign in to continue")
        self.subtitle_label.setFont(QFont("Segoe UI", 12))
        self.subtitle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.subtitle_label.setStyleSheet("color:#555;")

        # INPUT FIELDS
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)

        # BUTTONS
        self.login_button = QPushButton("LOGIN")
        self.login_button.setFixedHeight(45)
        self.create_user_button = QPushButton("Create New User")
        self.create_user_button.setObjectName("CreateUserButton")

        # ADD WIDGET TO LAYOUT
        self.main_layout.addWidget(self.logo_label)
        self.main_layout.addWidget(self.title_label)
        self.main_layout.addWidget(self.subtitle_label)
        self.main_layout.addSpacing(20)
        self.main_layout.addWidget(self.username_input)
        self.main_layout.addWidget(self.password_input)
        self.main_layout.addSpacing(10)
        self.main_layout.addWidget(self.login_button)
        self.main_layout.addStretch(1)
        self.main_layout.addWidget(self.create_user_button)

        self.setLayout(self.main_layout)
        self.apply_styles()
        self.connect_signals()

        try:
            self.Session = session_factory
            self.dashboard_window = None
        except SQLAlchemyError as e:
            QMessageBox.critical(
                None, "Database Error",
                f"Could not connect to database: {e}\n\n"
                "Please check your connection details and ensure the server is running."
            )

            sys.exit(1)

    def apply_styles(self):
        """
        Apply styles and cursor changes to buttons and load stylesheet from file.

        If the stylesheet file is missing, falls back to default styles and prints a warning.
        """

        button_cursor_pointer(self.login_button)
        button_cursor_pointer(self.create_user_button)
        qss_path = os.path.join(os.path.dirname(__file__), "styles", "login.css")

        load_styles(qss_path, self)

    def connect_signals(self):
        """
        Connect UI signals to their respective slot methods.

        - Login button and pressing Enter triggers login.
        - Create user button opens registration form.
        """

        self.login_button.clicked.connect(self.handle_login)
        self.create_user_button.clicked.connect(self.open_registration_form)
        self.username_input.returnPressed.connect(self.handle_login)
        self.password_input.returnPressed.connect(self.handle_login)

    def hash_password(self, password):
        """
        Hash the given password using SHA-256.

        Args:
            password (str): Plain text password.

        Returns:
            str: Hexadecimal SHA-256 hash of the password.
        """

        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def get_workstation_name(self):
        """
        Get the hostname of the current workstation.

        Returns:
            str: Hostname of the computer.
        """

        return socket.gethostname()

    def handle_login(self):
        """
        Handle user login attempt.

        Validates input, hashes password, queries database for matching user.
        Shows message boxes for errors or success.
        Records authentication logs for success or failure.
        Opens dashboard window if login is successful.
        """

        username = self.username_input.text().strip()
        password = self.password_input.text()

        if username is None or password is None:
            QMessageBox.warning(
                self,
                "Input Error",
                "Username and password cannot be empty."
            )

        # hashed the password here
        hashed_password = self.hash_password(password)

        workstation_name = self.get_workstation_name()

        # start the session here
        session = self.Session()

        try:
            user = session.query(User).filter_by(
                username=username,
                password=hashed_password
            ).first()

            if not user:
                QMessageBox.warning(
                    self,
                    "Login failed",
                    "Invalid username or password"
                )

                # log failed attempt
                record_auth_log(
                    session=session,
                    data_required={
                        "username": username,
                        "event_type": AuthLogStatus.get_event_type("login"),
                        "status": AuthLogStatus.FAILED.value,
                        "additional_info": f"Attempted from {workstation_name}"
                    },
                    auth_log_model=AuthLog,
                    commit=True
                )

                return

            # login is successful
            record_auth_log(
                session=session,
                data_required={
                    "user_id": user.user_id,
                    "username": user.username,
                    "event_type": AuthLogStatus.get_event_type("login"),
                    "status": AuthLogStatus.SUCCESS.value,
                    "additional_info": f"Logged in from {workstation_name}"
                },
                auth_log_model=AuthLog,
                commit=True
            )

            # StyledMessageBox.information(
            #     self,
            #     "Login Success",
            #     f"Welcome, {user.username}"
            # )

            # if the login is successful get the role of the current user with username of that.
            # OPEN THE MAIN DASHBAORD
            self.open_dashboard_main_window(
                session_factory=self.Session,
                username=username,
                role=user.role.value,
                open_win=True
            )

        except SQLAlchemyError as e:
            StyledMessageBox.critical(
                self,
                "Database Error",
                f"An error occured during login: {e}"
            )

    def open_dashboard_main_window(
        self,
        username: str,
        role: str,
        session_factory: Callable[..., Session],
        open_win=False
    ):
        """
        Open the main dashboard window and close the login form if specified.

        Args:
            username (str): Username of logged in user.
            role (str): Role of logged in user.
            session_factory (Callable[..., Session]): Factory for creating DB sessions.
            open_win (bool): Whether to open the dashboard window. Defaults to False.
        """

        if open_win:
            # CLOSE THIS LOGIN INTERFACE
            self.close()

            # OPEN THE DASHBOARD WINDOW
            self.dashboard_window = Base(
                session_factory=session_factory,
                username=username,
                role=role,
                login_widget=self
            )
            self.dashboard_window.show()

    def open_registration_form(self):
        """
        Prompt for super password and open user registration form if authenticated.

        Displays a warning message if the super password is incorrect.
        """

        super_password, ok = QInputDialog.getText(
            self,
            "Admin Authentication",
            "Enter super password to create new user:",
            QLineEdit.EchoMode.Password
        )

        if ok:
            if super_password == ITCredentials.SUPER_PASSWORD.value:
                self.registration_widget = Registration(session_factory=self.Session)
                self.registration_widget.show()
            else:
                StyledMessageBox.warning(
                    self,
                    "Access Denied",
                    "Incorrect super password"
                )
