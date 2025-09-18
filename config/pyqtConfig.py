from PyQt6.QtWidgets import QStyleFactory
from PyQt6.QtGui import QPalette, QColor
from sqlalchemy.engine import Engine
from typing import Type

def print_connection_status(is_connected: bool, engine: Type[Engine]):
    """Prints a formatted database connection status message"""
    status = "SUCCESSFULLY CONNECTED" if is_connected else "FAILED TO CONNECT"
    color_code = "\033[92m" if is_connected else "\033[91m"  # Green or Red
    reset_code = "\033[0m"
    
    border = "=" * 60
    print(f"\n{border}")
    print(f"{color_code} DATABASE CONNECTION STATUS: {status}{reset_code}")
    print(f"{border}\n")
    
    if is_connected:
        print(f"• Connection established to: {engine.url}")
        print("• Database engine ready for operations")
    else:
        print("• Please check your database configuration")
        print("• Verify the server is running and accessible")
        print("• Check network connectivity if using remote database")

def enforce_light_theme(app): 
    # 1. Force Fusion style (light)
    app.setStyle(QStyleFactory.create("Fusion"))
    
    # 2. Set a light color palette
    palette = app.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.Base, QColor(255, 255, 255))
    palette.setColor(QPalette.ColorRole.Button, QColor(240, 240, 240))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.Text, QColor(0, 0, 0))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(0, 0, 0))
    
    app.setPalette(palette)
    
    # 3. Optional: Apply a light QSS
    app.setStyleSheet("QToolTip { color: #000000; background-color: #ffffff; }")