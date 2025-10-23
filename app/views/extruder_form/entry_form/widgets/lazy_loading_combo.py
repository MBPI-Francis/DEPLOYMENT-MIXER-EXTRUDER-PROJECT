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
        self.setView(QListView(self)) # Allows us to access the scrollbar

        # State variables
        self.current_page = 1
        self.is_loading = False
        self.can_load_more = True
        self.data_fetcher_func: Callable | None = None

        # Timer for debouncing search queries
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(350) # 350ms delay
        self.search_timer.timeout.connect(self._trigger_search)

        # Connect signals
        self.lineEdit().textEdited.connect(self.search_timer.start)
        self.view().verticalScrollBar().valueChanged.connect(self._on_scroll)

    def set_data_fetcher(self, fetcher_func: Callable[[int, int, str], List[str]]):
        """
        Sets the function that will be called to fetch data.
        The function must accept (page, page_size, search_term).
        """
        self.data_fetcher_func = fetcher_func

    def load_initial_data(self):
        """Loads the first page of data."""
        self._trigger_search()

    @pyqtSlot(int)
    def _on_scroll(self, value: int):
        """Handles scrolling to the bottom of the list to load more items."""
        scrollbar = self.view().verticalScrollBar()
        # Load more when scroll is at 95% of the maximum
        if value >= scrollbar.maximum() * 0.95 and self.can_load_more and not self.is_loading:
            self.current_page += 1
            self._load_data(reset=False)

    @pyqtSlot()
    def _trigger_search(self):
        """Resets pagination and initiates a new search."""
        self.current_page = 1
        self.can_load_more = True
        self._load_data(reset=True)

    def _load_data(self, reset: bool = False):
        """Fetches data using the provided fetcher function and updates the list."""
        if not self.data_fetcher_func:
            return

        self.is_loading = True
        search_term = self.lineEdit().text()

        if reset:
            self.clear() # Clear existing items for a new search

        # Call the external function to get a new batch of data
        new_items = self.data_fetcher_func(
            page=self.current_page,
            page_size=self.PAGE_SIZE,
            search_term=search_term
        )

        if new_items:
            self.addItems(new_items)

        # If the returned batch is smaller than the page size, we've reached the end
        if len(new_items) < self.PAGE_SIZE:
            self.can_load_more = False

        self.is_loading = False

    def clear(self):
        """Overrides the default clear to also reset state and selection."""
        # Block signals to prevent any partial updates while we are clearing
        self.blockSignals(True)
        super().clear()
        self.lineEdit().clear()
        self.setCurrentIndex(-1)  # Explicitly set index to "no selection"
        self.blockSignals(False)

        # Reset pagination state
        self.current_page = 1
        self.can_load_more = True