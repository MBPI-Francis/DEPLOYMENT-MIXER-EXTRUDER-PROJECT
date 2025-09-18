from PyQt6.QtWidgets import (
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QComboBox,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from typing import Callable

from app.helpers import button_cursor_pointer, record_auth_log, add_new_user, load_styles
from app.StyledMessage import StyledMessageBox
from models import User, AuthLog
from constants.Enums import Department, UserRole, AuthLogStatus

import hashlib
import socket
import os

class Registration(QWidget):
    """
    A PyQt6 widget for user registration.

    Provides UI for creating a new user account with fields for username, password,
    password confirmation, role, and department selection.

    The registration process:
    - Validates input fields
    - Ensures password confirmation matches
    - Hashes the password with SHA-256
    - Checks if username already exists in the database
    - Creates a new user record using SQLAlchemy session
    - Records an authentication log entry for registration
    - Handles database errors and shows user feedback via message boxes

    Args:
        session_factory (Callable[..., Session]): Factory function to create SQLAlchemy sessions.
        parent (QWidget, optional): Parent widget for this registration form. Defaults to None.
    """

    def __init__(
        self, 
        session_factory: Callable[..., Session], 
        parent=None
    ):
        """
        Initialize the registration form UI components, layout, and styles.
        """
        super().__init__(parent)
        self.Session = session_factory

        self.setWindowTitle("User Registration")
        self.setFixedSize(400, 500)

        # MAIN LAYOUT
        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(30, 30, 30, 30)
        self.main_layout.setSpacing(15)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # TITLE
        self.title = QLabel("Create New Account")
        self.title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.role_label = QLabel("Role:")
        self.department_label = QLabel("Department:")

        # INPUT FIELDS
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Username")

        self.password_input = QLineEdit()
        self.password_input.setPlaceholderText("Password")
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        
        self.confirm_password_input = QLineEdit()
        self.confirm_password_input.setPlaceholderText("Confirm Password")
        self.confirm_password_input.setEchoMode(QLineEdit.EchoMode.Password)

        # COMBO BOX
        self.role_input = QComboBox()
        self.role_input.addItems([role.name for role in UserRole])

        self.department_input = QComboBox()
        self.department_input.addItems([dept.name for dept in Department])

        # BUTTONS
        self.register_button = QPushButton("Register")
        self.register_button.clicked.connect(self.handle_registration)

        self.main_layout.addWidget(self.title)
        self.main_layout.addWidget(self.username_input)
        self.main_layout.addWidget(self.password_input)
        self.main_layout.addWidget(self.confirm_password_input)
        # self.main_layout.addWidget(QLabel("Role:"))
        self.main_layout.addWidget(self.role_label)
        self.main_layout.addWidget(self.role_input)
        # self.main_layout.addWidget(QLabel("Department:"))
        self.main_layout.addWidget(self.department_label)
        self.main_layout.addWidget(self.department_input)
        self.main_layout.addSpacing(10)
        self.main_layout.addWidget(self.register_button)

        self.setLayout(self.main_layout)
        self.apply_styles()

    def apply_styles(self):
        """
        Load and apply external CSS stylesheet for styling the registration widget.

        Sets pointer cursor on register button. Falls back to default style if CSS file not found.
        """
        qss_path = os.path.join(os.path.dirname(__file__), "styles", "registration.css")
        button_cursor_pointer(self.register_button)
            
        load_styles(qss_path, self)

    def hash_password(self, password):
        """
        Hash a plaintext password using SHA-256.

        Args:
            password (str): Plain text password.

        Returns:
            str: Hexadecimal SHA-256 hash of the input password.
        """

        return hashlib.sha256(password.encode("utf-8")).hexdigest()

    def get_workstation_name(self):
        """
        Retrieve the hostname of the current workstation.

        Returns:
            str: Hostname of the computer running the app.
        """

        return socket.gethostname()

    def handle_registration(self):
        """
        Validate inputs and handle the user registration process.

        Steps:
        - Check for empty username/password fields.
        - Verify password and confirmation match.
        - Hash password.
        - Verify username uniqueness in database.
        - Add new user to the database.
        - Record successful registration event in auth log.
        - Commit changes to database.
        - Show success or error messages to the user.
        """
        
        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()
        role = self.role_input.currentText()
        department = self.department_input.currentText()

        if not username or not password:
            StyledMessageBox.warning(
                self,
                "Input Error",
                "Username and password cannot be empty."
            )
            return

        if password != confirm_password:
            StyledMessageBox.warning(
                self,
                "Input Error",
                "Please confirm the password if correct."
            )
            return

        hashed_password = self.hash_password(password)
        workstation_name = self.get_workstation_name()

        # initialize the session here that was imported in the Login widget
        session = self.Session()
        try:
            # Check if user exists
            if session.query(User).filter_by(username=username).first():
                StyledMessageBox.warning(
                    self,
                    "Registration Failed",
                    "Username already exists."
                )
                return
 
            # record new user in the User model
            user_details = {
                "username": username.lower(),
                "password": hashed_password,
                "workstation_name": workstation_name,
                "role": UserRole[role].value,
                "department": Department[department].value
            }

            new_user = add_new_user(
                session=session,
                data_required=user_details,
                user_model=User
            )

            record_auth_log(
                session=session,
                data_required={
                    "user_id": new_user.user_id,
                    "username": new_user.username,
                    "event_type": AuthLogStatus.get_event_type("registration"),
                    "status": AuthLogStatus.SUCCESS.value
                },
                auth_log_model=AuthLog
            )
        except SQLAlchemyError as e:
            session.rollback()
            StyledMessageBox.critical(
                self,
                "Database Error",
                f"An error occurred: {e}"
            )
            print(f"SQLAlchemyError: {e}")
        except TypeError as e:
            session.rollback()
            
            StyledMessageBox.critical(
                self,
                "Program Error",
                f"An error occurred: {e}"
            )

            print(f"TypeError: {e}")
        else:
             # commit everything if there is no failed transaction on both helper function 
            session.commit()

            StyledMessageBox.information(
                self,
                "Success",
                "User registered successfully."
            )
            self.close()
        finally:
            session.close()
