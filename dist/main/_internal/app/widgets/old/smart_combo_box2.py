# app/widgets/smart_combo_box.py

from PyQt6.QtWidgets import QComboBox, QCompleter, QListView, QLineEdit
from PyQt6.QtCore import Qt, QStringListModel, QTimer, pyqtSignal
from PyQt6.QtGui import QFocusEvent
from typing import override, List, Callable

class SmartComboBox(QComboBox):
    """
    A high-performance QComboBox that shows an initial limited list and
    performs a live, full database search when the user types.
    STABLE version 3.1 - Disables automatic text completion.
    """
    full_search_requested = pyqtSignal(str)

    STYLESHEET = """
        QComboBox {
            background-color: white; border: 1px solid #ced4da; border-radius: 6px;
            font-size: 13px; padding: 4px 8px;
        }
        QComboBox:hover { background-color: #e7f1ff; border: 1px solid #80bdff; }
        QComboBox:focus { background-color: #e7f1ff; border: 1px solid #80bdff; }
        QComboBox:on {
            border-color: #007bff; border-bottom-left-radius: 0px; border-bottom-right-radius: 0px;
        }
        QComboBox::drop-down {
            subcontrol-origin: padding; subcontrol-position: top right; width: 25px;
            border-left-width: 1px; border-left-color: #ced4da; border-left-style: solid;
            border-top-right-radius: 6px; border-bottom-right-radius: 6px;
            background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1, stop: 0 #f8f9fa, stop: 1 #e9ecef);
        }
        QComboBox::down-arrow {
            image: url(./app/widgets/widget_icons/chevron-down.svg); width: 12px; height: 12px;
        }
        QComboBox::down-arrow:on { top: 1px; }
        QComboBox QAbstractItemView {
            background-color: white; color: black; selection-background-color: #007bff;
            selection-color: white; border: 1px solid #ced4da; border-radius: 6px;
            font-size: 14px; padding: 5px;
        }
        QComboBox QLineEdit { background-color: transparent; border: none; }
    """

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
        
        # --- THIS IS THE FIX ---
        # This mode tells the completer to ONLY show the popup list of suggestions
        # and NEVER automatically change the text in the line edit.
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        # --- END OF FIX ---

        self.setCompleter(completer)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._request_full_search)
        
        self.lineEdit().textEdited.connect(self._on_text_edited)
        
        self._initial_list = []
        self._initial_list_upper_set = set()
        self._last_searched_term = ""

    def populate_initial(self, items: List[str]):
        """Populates the combo box with the initial, limited list of items."""
        self.blockSignals(True)
        self._initial_list = items
        self._initial_list_upper_set = {item.upper() for item in items}
        self.current_model.setStringList(self._initial_list)
        # Set the current index to -1 to ensure nothing is pre-selected
        self.setCurrentIndex(-1)
        self.blockSignals(False)

    def update_with_search_results(self, results: List[str]):
        """Updates the model with the results from a full database search."""
        current_text = self.currentText()
        if not current_text or not self._last_searched_term or not current_text.upper().startswith(self._last_searched_term.upper()):
            return

        print(f"Updating completer with {len(results)} results for '{current_text}'")
        self.blockSignals(True)
        
        combined_set = set(self._initial_list)
        combined_set.update(results)
        self.current_model.setStringList(sorted(list(combined_set)))
        
        self.setCurrentText(current_text)
        self.blockSignals(False)
        
        self.completer().setModel(self.current_model)
        self.completer().setCompletionPrefix(current_text)
        self.completer().complete()

    def _on_text_edited(self, text: str):
        """This is the core logic. It decides when to trigger a full search."""
        text_upper = text.upper()
        if not text_upper:
            self._search_timer.stop()
            self.populate_initial(self._initial_list)
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