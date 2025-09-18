# app/widgets/smart_combo_box.py

from PyQt6.QtWidgets import QComboBox, QCompleter, QListView, QLineEdit
from PyQt6.QtCore import Qt, QStringListModel, QTimer, pyqtSignal
from PyQt6.QtGui import QFocusEvent
from typing import override, List, Callable

class SmartComboBox(QComboBox):
    """
    High-performance QComboBox with live search and visual validation.
    """
    full_search_requested = pyqtSignal(str)
    # --- NEW: Signal to notify parent when validation state changes ---
    validation_changed = pyqtSignal(bool)

    STYLESHEET = """
        QComboBox {
            background-color: white; 
            border: 1px solid #ced4da; 
            border-radius: 6px;
            font-size: 13px; 
            
            /* Change 1: Use specific padding to avoid vertical issues */
            padding-left: 4px;
            padding-right: 4px;
            

        }
        QComboBox:hover { background-color: #e7f1ff; border: 1px solid #80bdff; }
        QComboBox:focus { background-color: #e7f1ff; border: 1px solid #80bdff; }
        QComboBox:on {
            border-color: #007bff; border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;
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
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f8f9fa, stop: 1 #e9ecef);
        }
        QComboBox::down-arrow {
            image: url(app/widgets/widget_icons/chevron-down.svg); 
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
        QComboBox QLineEdit { 
            background-color: transparent; 
            border: none; 
            
            /* Change 3: Vertically center the text in the line edit area */
            padding-top: 0px;
            padding-bottom: 0px;
        }
    """
    # --- END OF FIX ---



    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet(self.STYLESHEET)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        
        self._editor = CustomLineEdit(self)
        self.setLineEdit(self._editor)

        self.current_model = QStringListModel(self)
        self.setModel(self.current_model)
        
        completer = QCompleter(self)
        completer.setModel(self.current_model)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._request_full_search)
        
        # --- THIS IS THE FIX ---
        # 1. We connect to the high-level currentTextChanged signal. This
        #    fires for both user edits and completer activations.
        self.currentTextChanged.connect(self._on_text_changed)
        # 2. We no longer need the lineEdit().textEdited connection.
        # --- END OF FIX ---
        
        self._initial_list = []
        self._initial_list_upper_set = set()
        self._last_searched_term = ""
        self._is_mandatory = False

    def set_mandatory(self, mandatory: bool):
        self._is_mandatory = mandatory
        self._validate_input()

    def is_valid(self) -> bool:
        text = self.currentText()
        if self._is_mandatory and not text.strip():
            return False
        if not text.strip():
            return True
        return text.upper() in self._initial_list_upper_set

    def _validate_input(self):
        """Checks the current text and applies styling via dynamic properties."""
        is_currently_valid = self.is_valid()
        
        self.setProperty("valid", is_currently_valid)
        
        if is_currently_valid:
            self.setToolTip("")
        else:
            if self._is_mandatory and not self.currentText().strip():
                self.setToolTip("This field cannot be empty.")
            else:
                self.setToolTip(f"'{self.currentText()}' is not a valid entry.")
        
        self.style().unpolish(self)
        self.style().polish(self)
        
        self.validation_changed.emit(is_currently_valid)

    def populate_initial(self, items: List[str]):
        self.blockSignals(True)
        self._initial_list = items
        self._initial_list_upper_set = {item.upper() for item in items}
        self.current_model.setStringList(self._initial_list)
        self.setCurrentIndex(-1)
        self.blockSignals(False)
        self._validate_input()

    def update_with_search_results(self, results: List[str]):
        """Updates the model with the results from a full database search."""
        current_text = self.currentText()
        if not current_text or not self._last_searched_term or not current_text.upper().startswith(self._last_searched_term.upper()):
            return
        
        # Add new results to our known valid items
        self._initial_list_upper_set.update({r.upper() for r in results})
        
        self.blockSignals(True)
        combined_set = set(self.current_model.stringList())
        combined_set.update(results)
        self.current_model.setStringList(sorted(list(combined_set)))
        self.setCurrentText(current_text)
        self.blockSignals(False)
        
        self.completer().setModel(self.current_model)
        self.completer().setCompletionPrefix(current_text)
        self.completer().complete()
        self._validate_input()

    def _on_text_edited(self, text: str):
        """Decides when to trigger a full search and validates input."""
        self._validate_input() # Validate on every keystroke
        text_upper = text.upper()
        if not text_upper:
            self._search_timer.stop()
            self._last_searched_term = ""
            return

        if self._last_searched_term and text_upper.startswith(self._last_searched_term.upper()):
            return

        if any(item.startswith(text_upper) for item in self._initial_list_upper_set):
            self._search_timer.stop()
            return

        self._search_timer.start()

    def _request_full_search(self):
        """Emits the signal to tell the main view to start a background search."""
        search_term = self.currentText()
        if search_term:
            self._last_searched_term = search_term
            self.full_search_requested.emit(search_term)
        
    def text(self) -> str:
        return self.currentText().upper()
        
    @override
    def wheelEvent(self, e):
        e.ignore()



    def _on_text_changed(self, text: str):
        """
        This single method now handles all text changes.
        It validates and decides when to trigger a full search.
        """
        # --- THIS IS THE FIX ---
        # 1. ALWAYS validate first. This is the most important step.
        self._validate_input()
        # --- END OF FIX ---
        
        text_upper = text.upper()
        if not text_upper:
            self._search_timer.stop()
            self._last_searched_term = ""
            # Do not re-populate here, let the user clear the text
            return

        if self._last_searched_term and text_upper.startswith(self._last_searched_term.upper()):
            return

        if any(item.startswith(text_upper) for item in self._initial_list_upper_set):
            self._search_timer.stop()
            return

        self._search_timer.start()    

class CustomLineEdit(QLineEdit):
    """A custom LineEdit that prevents auto-selection of the first item on focus out."""
    def __init__(self, parent: SmartComboBox):
        super().__init__(parent)
        self.combobox = parent

    def focusOutEvent(self, e: QFocusEvent):
        """
        When the user clicks away, if the text is empty or invalid,
        ensure it stays that way.
        """
        current_text = self.text()
        index = self.combobox.findText(current_text, Qt.MatchFlag.MatchFixedString)
        if index == -1:
            self.combobox.setCurrentIndex(-1)
            self.combobox.setCurrentText(current_text)

        super().focusOutEvent(e)