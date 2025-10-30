# app/views/extruder_form/entry_form/widgets/lazy_loading_combo.py

from PyQt6.QtCore import pyqtSlot, QTimer
from PyQt6.QtWidgets import QComboBox, QListView
from typing import Callable, List

class LazyLoadingComboBox(QComboBox):
    """
    A QComboBox that supports lazy loading (infinite scroll) and
    debounced server-side searching as the user types.
    """
    PAGE_SIZE = 50

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setView(QListView(self))

        self.current_page = 1
        self.is_loading = False
        self.can_load_more = True
        self.data_fetcher_func: Callable | None = None

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(350)
        self.search_timer.timeout.connect(self._trigger_search)

        self.lineEdit().textEdited.connect(self.search_timer.start)
        self.view().verticalScrollBar().valueChanged.connect(self._on_scroll)

    def set_data_fetcher(self, fetcher_func: Callable[[int, int, str], List[str]]):
        self.data_fetcher_func = fetcher_func

    def load_initial_data(self):
        self._trigger_search()

    @pyqtSlot(int)
    def _on_scroll(self, value: int):
        scrollbar = self.view().verticalScrollBar()
        if value >= scrollbar.maximum() * 0.95 and self.can_load_more and not self.is_loading:
            self.current_page += 1
            self._load_data(reset=False)

    @pyqtSlot()
    def _trigger_search(self):
        self.current_page = 1
        self.can_load_more = True
        self._load_data(reset=True)

    def _load_data(self, reset: bool = False):
        """
        Fetches data and updates the list while preserving the user's typed text.
        """
        if not self.data_fetcher_func:
            return

        self.is_loading = True
        search_term = self.lineEdit().text()

        # --- THIS IS THE NEW, CORRECT LOGIC ---
        # 1. Save the user's current text and cursor position.
        original_text = self.lineEdit().text()
        cursor_pos = self.lineEdit().cursorPosition()

        # 2. Block signals to prevent chaotic feedback loops while we modify the list.
        self.blockSignals(True)

        # 3. Clear only the dropdown items if it's a new search.
        if reset:
            super().clear()

        # 4. Fetch the new data from the controller.
        new_items = self.data_fetcher_func(
            page=self.current_page,
            page_size=self.PAGE_SIZE,
            search_term=search_term
        )

        # 5. Add the new items to the dropdown list.
        if new_items:
            self.addItems(new_items)

        # 6. CRITICAL: Restore the user's original text and cursor position.
        #    This overrides any "helpful" changes made by addItems().
        self.lineEdit().setText(original_text)
        self.lineEdit().setCursorPosition(cursor_pos)

        # 7. Unblock signals now that the operation is complete.
        self.blockSignals(False)
        # --- END OF NEW LOGIC ---

        if len(new_items) < self.PAGE_SIZE:
            self.can_load_more = False

        self.is_loading = False

    def clear(self):
        """Overrides clear to reset everything, used by the main form's 'Clear' button."""
        self.blockSignals(True)
        super().clear()
        self.lineEdit().clear()
        self.setCurrentIndex(-1)
        self.blockSignals(False)
        self.current_page = 1
        self.can_load_more = True