# app/widgets/fast_combo_box.py

from PyQt6.QtWidgets import QComboBox, QCompleter, QListView
from PyQt6.QtCore import Qt, QStringListModel
from typing import override, List

class FastComboBox(QComboBox):
    """
    A high-performance QComboBox that uses signal blocking for fast population
    and an optimized view/completer for a responsive user experience.
    This is the definitive, stable version.
    """
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
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        
        # We use a standard QStringListModel, which is efficient for strings.
        self.string_list_model = QStringListModel(self)
        self.setModel(self.string_list_model)
        
        # Apply performance tweaks to the view and completer
        self._tweak_view_performance()
        self._tweak_completer_performance()

    def _tweak_view_performance(self):
        """Applies performance hints to the QComboBox's main popup view."""
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContentsOnFirstShow)
        view = self.view()
        view.setUniformItemSizes(True)
        view.setLayoutMode(QListView.LayoutMode.Batched)
        view.setBatchSize(100)
    
    def _tweak_completer_performance(self):
        """Applies performance hints to the QCompleter."""
        completer = QCompleter(self)
        completer.setModel(self.model()) # Completer uses the same model
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        completer.setModelSorting(QCompleter.ModelSorting.CaseInsensitivelySortedModel)
        self.setCompleter(completer)

    def populate(self, items: List[str]):
        """
        Populates the combo box efficiently using the "signal blocking trick".
        This is now fast enough to run on the main UI thread.
        """
        current_text = self.currentText()
        
        # --- THE "BOSS'S TRICK" ---
        self.blockSignals(True)
        
        # Use the underlying QStringListModel for maximum speed
        self.string_list_model.setStringList(items)
        
        self.setCurrentText(current_text)
        self.blockSignals(False)
        # --- END OF TRICK ---

    def text(self) -> str:
        return self.currentText().upper()
        
    def setText(self, text: str):
        self.setCurrentText(text)
        
    @override
    def wheelEvent(self, e):
        e.ignore()