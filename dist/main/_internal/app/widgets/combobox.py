from PyQt6.QtWidgets import QComboBox, QCompleter
from PyQt6.QtCore import Qt, QStringListModel
from typing import override

class ModifiedComboBox(QComboBox):
    """
    A custom QComboBox with modern styling, search/filter autocompletion,
    and improved user experience features like disabled mouse wheel scrolling.
    """
    
    # --- STYLESHEET WITH THE CORRECTED ICON PATH ---
    STYLESHEET = """
        QComboBox {
            background-color: white;
            border: 1px solid #ced4da;
            border-radius: 6px;
            font-size: 13px;
        }

        QComboBox:hover {
            background-color: #e7f1ff;
            border: 1px solid #80bdff;
        }

        QComboBox:focus {
            background-color: #e7f1ff;
            border: 1px solid #80bdff;
        }

        QComboBox:on {
            border-color: #007bff;
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
        }

        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 25px;
            border-left-width: 1px;
            border-left-color: #ced4da;
            border-left-style: solid;
            border-top-right-radius: 6px;
            border-bottom-right-radius: 6px;
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                        stop: 0 #f8f9fa, stop: 1 #e9ecef);
        }

        /* --- THIS IS THE CORRECTED PART --- */
        /* The actual arrow icon using the SVG file you just created. */
        /* This path is relative to where your main.py is executed. */
        QComboBox::down-arrow {
            image: url(./app/widgets/widget_icons/chevron-down.svg);
            width: 12px;
            height: 12px;
        }
        
        QComboBox::down-arrow:on {
            top: 1px;
        }

        /* Styling for the dropdown list (popup) itself */
        QComboBox QAbstractItemView {
            background-color: white;
            color: black;
            selection-background-color: #007bff;
            selection-color: white;
            border: 1px solid #ced4da;
            border-radius: 6px;
            font-size: 14px;
            padding: 5px;
        }
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        self.setStyleSheet(self.STYLESHEET)
        
        self.setEditable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._completer_model = QStringListModel()
        self._completer = QCompleter(self._completer_model, self)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)

        self.setCompleter(self._completer)
    
    @override
    def showPopup(self):
        """Ensures the dropdown list also has a pointing hand cursor."""
        self.view().setCursor(Qt.CursorShape.PointingHandCursor)
        super().showPopup()

    @override
    def wheelEvent(self, e):
        """
        Prevents the mouse wheel from changing the selected item.
        """
        e.ignore()
    
    @override
    def addItems(self, items: list[str]) -> None:
        """Overrides addItems to keep the completer model in sync."""
        super().addItems(items)
        all_items = [self.itemText(i) for i in range(self.count())]
        self._completer_model.setStringList(all_items)
    
    @override
    def addItem(self, item: str, userData=None) -> None:
        """Overrides addItem to keep the completer model in sync."""
        super().addItem(item, userData)
        all_items = [self.itemText(i) for i in range(self.count())]
        self._completer_model.setStringList(all_items)