import traceback

from app.features.maintenance_checker import check_maintenance_status
from config.db import is_connected, engine
from sqlalchemy.orm import sessionmaker
from app.auth.login import LoginForm
from PyQt6.QtWidgets import QApplication, QMessageBox
from config.pyqtConfig import print_connection_status, enforce_light_theme
import sys
from qt_material import apply_stylesheet # <--- Import this

from maintenance_page import MaintenancePage


def global_exception_hook(exctype, value, tb):
    """
    A global hook to catch any uncaught exception and display it in a QMessageBox.
    """
    # Format the traceback into a detailed, readable string
    traceback_details = "".join(traceback.format_exception(exctype, value, tb))

    # Create and display the error message box
    error_msg = f"An unexpected error occurred:\n\n{traceback_details}"
    error_box = QMessageBox()
    error_box.setIcon(QMessageBox.Icon.Critical)
    error_box.setText(error_msg)
    error_box.setWindowTitle("Application Error")
    error_box.exec()

    # Also print to console for logging purposes
    sys.__excepthook__(exctype, value, tb)
    QApplication.quit()


if __name__ == "__main__":
    print_connection_status(is_connected, engine)

    if is_connected:
        app = QApplication(sys.argv)
        enforce_light_theme(app)
        sys.excepthook = global_exception_hook

        # ----> APPLY THE THEME HERE <----
        # apply_stylesheet(app, theme='dark_teal.xml')  # Choose your favorite theme

        # load the login application here
        session_factory = sessionmaker(engine)

        # 1. Check Maintenance Status
        is_maint, finish_time = check_maintenance_status(session_factory)

        if is_maint:
            # Show the separate Maintenance Page
            maint_view = MaintenancePage(finish_time)
            maint_view.show()
            sys.exit(app.exec())
        else:
            # 2. Show Login Form if NOT under maintenance
            login_view = LoginForm(session_factory=session_factory)
            login_view.show()
            sys.exit(app.exec())
    else:
        # Handle DB connection failure
        app = QApplication(sys.argv)
        QMessageBox.critical(None, "Database Error", "Unable to connect to the database.")
        sys.exit(1)
