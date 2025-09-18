# app/widgets/validating_combo_box.py

from PyQt6.QtWidgets import QComboBox, QCompleter, QLineEdit
from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtGui import QValidator
from typing import override

class ValidatingComboBox(QComboBox):
    """
    A custom QComboBox that merges modern styling, filter autocompletion,
    and real-time visual validation.
    """
    
    # --- STYLING (from ModifiedComboBox) ---
    STYLESHEET = """
        QComboBox {
            background-color: white;
            border: 1px solid #ced4da;
            border-radius: 6px;
            font-size: 13px;
            padding: 4px 8px; /* Added padding for better text alignment */
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
        QComboBox::down-arrow {
            image: url(./app/widgets/widget_icons/chevron-down.svg);
            width: 12px;
            height: 12px;
        }
        QComboBox::down-arrow:on { top: 1px; }
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
        /* --- NEW: Style for the QLineEdit inside the QComboBox --- */
        QComboBox QLineEdit {
            background-color: transparent;
            border: none;
        }
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(self.STYLESHEET)
        self.setEditable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self.p_validator = CustomValidator(self)
        self.setValidator(self.p_validator)
        
        # Connect signals for real-time validation feedback
        self.lineEdit().textEdited.connect(self._trigger_validation)
        self.currentIndexChanged.connect(self._trigger_validation)

    def set_shared_model(self, model: QStringListModel):
        """
        Sets the shared model for the combo box and its completer.
        This is the core of the performance improvement.
        """
        self.setModel(model)
        
        # The completer also uses the same shared model
        completer = QCompleter(model, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)
        
        # Update the validator with the items from the new model
        self.p_validator.set_valid_items(model.stringList())

    def text(self) -> str:
        """Returns the current text, always in uppercase."""
        return self.currentText().upper()
    
    def setText(self, text: str):
        """Sets the current text of the combo box and triggers validation."""
        self.setCurrentText(text)
        self._trigger_validation()

    def _trigger_validation(self):
        """Checks the current text against the validator and applies styling."""
        editor = self.lineEdit()
        text = editor.text()
        state, _, _ = self.validator().validate(text, 0)

        # The stylesheet for the QLineEdit is inside the QComboBox's main stylesheet
        # We only need to set a "state" property to toggle the style
        if state == QValidator.State.Acceptable:
            editor.setProperty("state", "acceptable")
            editor.setToolTip("")
        else:
            editor.setProperty("state", "invalid")
            editor.setToolTip(f"'{text}' is not a valid entry.")
        
        # Re-polish the widget to apply the new style based on the property
        self.style().unpolish(editor)
        self.style().polish(editor)

    @override
    def showPopup(self):
        """Ensures the dropdown list also has a pointing hand cursor."""
        self.view().setCursor(Qt.CursorShape.PointingHandCursor)
        super().showPopup()

    @override
    def wheelEvent(self, e):
        """Prevents the mouse wheel from changing the selected item."""
        e.ignore()


class CustomValidator(QValidator):
    """A simple validator that checks if input is in a predefined list."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._valid_items = set()

    def set_valid_items(self, items: list[str]):
        """Sets the list of valid strings, converted to uppercase for case-insensitive check."""
        self._valid_items = {item.upper() for item in items}

    def validate(self, text: str, pos: int) -> tuple[QValidator.State, str, int]:
        """Performs the validation."""
        # During initial load, the list might be empty. Accept anything to avoid false errors.
        if not self._valid_items:
            return QValidator.State.Acceptable, text, pos

        text_upper = text.upper()
        
        # Perfect match
        if text_upper in self._valid_items:
            return QValidator.State.Acceptable, text, pos
        
        # If the user has cleared the box, it's an intermediate state (not invalid)
        if not text_upper:
            return QValidator.State.Intermediate, text, pos
            
        # The text is a valid prefix of at least one item (allows autocompletion to work)
        if any(item.startswith(text_upper) for item in self._valid_items):
            return QValidator.State.Intermediate, text, pos
            
        # The input is completely different from any valid item
        return QValidator.State.Invalid, text, pos