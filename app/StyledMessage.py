from PyQt6.QtWidgets import QMessageBox

class StyledMessageBox(QMessageBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
            }
            QMessageBox QLabel {
                color: #333333;
                font-size: 14px;
            }  
            QMessageBox QPushButton {
                background-color: #0078d7;
                color: white;
                min-width: 80px;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
            }             
        """)

    @classmethod
    def information(cls, parent, title, message):
        msg = cls(parent)
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        msg.exec()
        
        return msg

    @classmethod
    def warning(cls, parent, title, message):
        msg = cls(parent)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        
        msg.exec()
        
        return msg

    @classmethod
    def critical(cls, parent, title, message):
        msg = cls(parent)
        msg.setIcon(QMessageBox.Icon.Critical)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)

        msg.exec()
        
        return msg

    @classmethod
    def question(cls, parent, title, message):
        msg = cls(parent)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(
            QMessageBox.StandardButton.Yes | 
            QMessageBox.StandardButton.No
        )
        
        return msg.exec()