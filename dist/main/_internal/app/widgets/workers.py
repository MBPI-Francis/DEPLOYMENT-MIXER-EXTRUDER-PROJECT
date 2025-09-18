# app/widgets/workers.py

from PyQt6.QtCore import QThread, pyqtSignal
from typing import Callable

from app.database.legacy_ops import get_formula_no_for_lot_range


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


class FormulaLookupWorker(QThread):
    """Background worker to look up formula numbers without freezing the UI."""
    formula_ready = pyqtSignal(object, str)  # Emits the row widget and the result string

    def __init__(self, session_factory: Callable, product_code: str, lot_no: str, target_row, parent=None):
        super().__init__(parent)
        self.Session = session_factory
        self.product_code = product_code
        self.lot_no = lot_no
        self.target_row = target_row

    def run(self):
        session = self.Session()
        try:
            formula_str = get_formula_no_for_lot_range(session, self.product_code, self.lot_no)
            self.formula_ready.emit(self.target_row, formula_str)
        except Exception as e:
            print(f"Formula lookup failed: {e}")
            self.formula_ready.emit(self.target_row, "Error")
        finally:
            session.close()