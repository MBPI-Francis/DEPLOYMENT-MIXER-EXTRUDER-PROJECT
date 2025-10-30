# app/widgets/multi_select_combo.py

from PyQt6.QtWidgets import QComboBox, QListView, QLineEdit
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt, pyqtSignal


class MultiSelectComboBox(QComboBox):
    """A custom QComboBox that supports multiple item selection with checkboxes."""
    selection_changed = pyqtSignal()

    def __init__(self, placeholder_text="All", parent=None):
        super().__init__(parent)

        self._placeholder_text = placeholder_text
        self._list_view = QListView(self)
        self._model = QStandardItemModel(self)
        self._list_view.setModel(self._model)

        # Use a non-editable line edit to display the selection summary
        self._line_edit = QLineEdit(self)
        self._line_edit.setReadOnly(True)
        self.setLineEdit(self._line_edit)

        self.setView(self._list_view)

        self.view().pressed.connect(self.handle_item_pressed)

        self._changed = False
        self._update_display_text()

    def handle_item_pressed(self, index):
        """Toggles the check state of the clicked item."""
        item = self._model.itemFromIndex(index)
        if item.checkState() == Qt.CheckState.Checked:
            item.setCheckState(Qt.CheckState.Unchecked)
        else:
            item.setCheckState(Qt.CheckState.Checked)
        self._changed = True

    def hidePopup(self):
        """Update display text and emit signal only if the selection changed."""
        if self._changed:
            self._update_display_text()
            self.selection_changed.emit()
        self._changed = False
        super().hidePopup()

    def _update_display_text(self):
        """Updates the combo box's main text based on the selection."""
        selected = self.get_selected_data()
        if not selected:
            self._line_edit.setText(self._placeholder_text)
        elif len(selected) == 1:
            # Find the text corresponding to the single selected data item
            for i in range(self._model.rowCount()):
                if self._model.item(i).data() == selected[0]:
                    self._line_edit.setText(self._model.item(i).text())
                    break
        else:
            self._line_edit.setText(f"{len(selected)} items selected")

    def populate_items(self, items: list[tuple[str, any]]):
        """Populates the dropdown with items (text, data) and checkboxes."""
        self._model.clear()
        for text, data in items:
            item = QStandardItem(text)
            item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            item.setData(data, Qt.ItemDataRole.UserRole)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._model.appendRow(item)
        self._update_display_text()

    def get_selected_data(self) -> list:
        """Returns a list of the data of all checked items."""
        selected = []
        for i in range(self._model.rowCount()):
            item = self._model.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data())
        return selected