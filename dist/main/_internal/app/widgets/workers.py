# app/widgets/workers.py

from PyQt6.QtCore import QThread, pyqtSignal
from typing import Callable

class LiveSearchWorker(QThread):
    """
    A reusable background worker for performing live database searches
    without freezing the UI.
    """
    results_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, session_factory: Callable, search_function: Callable, search_term: str, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.search_function = search_function
        self.search_term = search_term

    def run(self):
        session = self.Session()
        try:
            results = self.search_function(session, self.search_term)
            self.results_ready.emit(results)
        except Exception as e:
            self.error.emit(f"Live search failed: {e}")
        finally:
            session.close()