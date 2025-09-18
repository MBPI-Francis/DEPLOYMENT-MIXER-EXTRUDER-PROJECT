# app/widgets/smart_combo_box.py

from PyQt6.QtWidgets import QComboBox, QCompleter, QLineEdit
from PyQt6.QtCore import Qt, QStringListModel, QTimer, pyqtSignal
from PyQt6.QtGui import QFocusEvent, QKeyEvent
from typing import override, List


class LotComboBox(QComboBox):
    """
    High-performance QComboBox with live search and visual validation,
    with robust support for multiple semicolon-separated entries.
    """
    full_search_requested = pyqtSignal(str)
    validation_changed = pyqtSignal(bool)

    STYLESHEET = """
        QComboBox {
            background-color: white; border: 1px solid #ced4da; border-radius: 6px;
            font-size: 13px; padding-left: 4px; padding-right: 4px;
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
        QComboBox::down-arrow { image: url(app/widgets/widget_icons/chevron-down.svg); width: 12px; height: 12px; }
        QComboBox::down-arrow:on { top: 1px; }
        QComboBox QAbstractItemView {
            background-color: white; color: black; selection-background-color: #007bff;
            selection-color: white; border: 1px solid #ced4da; border-radius: 6px;
            font-size: 14px; padding: 5px;
        }
        QComboBox QLineEdit { background-color: transparent; border: none; padding-top: 0px; padding-bottom: 0px; }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setStyleSheet(self.STYLESHEET)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self._editor = CustomLineEdit(self)
        self.setLineEdit(self._editor)

        # The ComboBox uses a dummy, empty model to prevent its own popup.
        self.setModel(QStringListModel(self))

        # The Completer uses the real model with all the data.
        self.completer_model = QStringListModel(self)

        completer = QCompleter(self)
        completer.setModel(self.completer_model)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setCompleter(completer)

        completer.activated.connect(self._insert_completion)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(300)
        self._search_timer.timeout.connect(self._request_full_search)

        self.lineEdit().textEdited.connect(self._on_text_edited)

        self._initial_list_upper_set = set()
        self._last_searched_term = ""
        self._is_mandatory = False

    # --- NEW: Show all options on click ---
    @override
    def showPopup(self):
        """
        Overrides the default popup behavior. Instead of showing the
        QComboBox's (empty) view, we show the QCompleter's popup with
        all available options.
        """
        if self.completer().popup().isVisible():
            self.completer().popup().hide()
        else:
            self.completer().setCompletionPrefix("")  # Empty prefix = show all
            self.completer().complete()

    # --- NEW: Ensure popup hiding is handled consistently ---
    @override
    def hidePopup(self):
        """
        When the combobox is supposed to hide its popup (e.g., on focus loss),
        we ensure our completer's popup is also hidden.
        """
        self.completer().popup().hide()

    def _insert_completion(self, text: str):
        """
        Custom slot to handle user selection. It intelligently appends the
        selection after the last semicolon.
        """
        self.blockSignals(True)
        base_text, _ = self._get_active_search_term_parts()
        self.setCurrentText(base_text + text)
        self.lineEdit().end(False)
        self.blockSignals(False)
        self.hidePopup()  # Use our override to hide the completer popup
        self._validate_input()

    def _get_active_search_term_parts(self) -> (str, str):
        full_text = self.currentText()
        last_semicolon_index = full_text.rfind(';')
        if last_semicolon_index == -1:
            return "", full_text
        else:
            base = full_text[:last_semicolon_index + 1]
            active = full_text[last_semicolon_index + 1:].lstrip()
            if not base.endswith(" "):
                base += " "
            return base, active

    def set_mandatory(self, mandatory: bool):
        self._is_mandatory = mandatory
        self._validate_input()

    def is_valid(self) -> bool:
        full_text = self.currentText().strip()
        if not self._is_mandatory and not full_text: return True
        if self._is_mandatory and not full_text: return False
        lot_entries = [entry.strip() for entry in full_text.split(';') if entry.strip()]
        if not lot_entries and full_text: return False
        return all(entry.upper() in self._initial_list_upper_set for entry in lot_entries)

    def _validate_input(self):
        is_currently_valid = self.is_valid()
        self.setProperty("valid", is_currently_valid)
        tooltip = ""
        if not is_currently_valid:
            if self._is_mandatory and not self.currentText().strip():
                tooltip = "This field cannot be empty."
            else:
                tooltip = "One or more lot numbers in the list are not valid."
        self.setToolTip(tooltip)
        self.style().unpolish(self);
        self.style().polish(self)
        self.validation_changed.emit(is_currently_valid)

    def populate_initial(self, items: List[str]):
        self.blockSignals(True)
        self._initial_list_upper_set = {item.upper() for item in items}
        self.completer_model.setStringList(items)
        self.setCurrentIndex(-1)
        self.blockSignals(False)
        self._validate_input()

    def update_with_search_results(self, results: List[str]):
        _, active_term = self._get_active_search_term_parts()
        if not active_term or not self._last_searched_term or not active_term.upper().startswith(
                self._last_searched_term.upper()):
            return

        self._initial_list_upper_set.update({r.upper() for r in results})

        current_list = self.completer_model.stringList()
        combined_set = set(current_list) | set(results)
        self.completer_model.setStringList(sorted(list(combined_set)))

        if self.hasFocus():
            self.completer().setCompletionPrefix(active_term)
            self.completer().complete()
        self._validate_input()

    def _on_text_edited(self, text: str):
        self._validate_input()
        _, active_term = self._get_active_search_term_parts()

        if not active_term:
            self._search_timer.stop()
            self.hidePopup()  # Use our override to hide the completer popup
            return

        self.completer().setCompletionPrefix(active_term)
        self.completer().complete()

        if self.completer().completionCount() == 0:
            if not self._last_searched_term or not active_term.upper().startswith(self._last_searched_term.upper()):
                self._search_timer.start()
        else:
            self._search_timer.stop()

    def _request_full_search(self):
        _, search_term = self._get_active_search_term_parts()
        if search_term:
            self._last_searched_term = search_term
            self.full_search_requested.emit(search_term)

    def text(self) -> str:
        return self.currentText().upper()

    @override
    def wheelEvent(self, e):
        e.ignore()


class CustomLineEdit(QLineEdit):
    def __init__(self, parent: LotComboBox):
        super().__init__(parent)
        self.combobox = parent

    def focusOutEvent(self, e: QFocusEvent):
        self.combobox._validate_input()
        super().focusOutEvent(e)

    def keyPressEvent(self, e: QKeyEvent):
        if e.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            if self.combobox.completer().popup().isVisible():
                e.ignore()
                return

        super().keyPressEvent(e)