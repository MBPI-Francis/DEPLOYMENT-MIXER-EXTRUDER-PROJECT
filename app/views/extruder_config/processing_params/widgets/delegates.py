
# app/views/extruder_config/processing_params/widgets/delegates.py

from PyQt6.QtWidgets import QStyledItemDelegate, QComboBox, QLineEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator
from typing import List


# class ComboBoxDelegate(QStyledItemDelegate):
#     """A delegate for showing a QComboBox in a table cell."""
#     def __init__(self, items: List, parent=None):
#         super().__init__(parent)
#         # items is a list of tuples: [(id, 'Display Name'), ...]
#         self.items = items
#
#     def createEditor(self, parent, option, index):
#         editor = QComboBox(parent)
#         for item_id, display_name in self.items:
#             editor.addItem(display_name, userData=item_id)
#         return editor
#
#     def setEditorData(self, editor, index):
#         current_id = index.model().data(index, Qt.ItemDataRole.UserRole)
#         if current_id:
#             editor_index = editor.findData(current_id)
#             if editor_index >= 0:
#                 editor.setCurrentIndex(editor_index)
#
#     def setModelData(self, editor, model, index):
#         model.setData(index, editor.currentText(), Qt.ItemDataRole.DisplayRole)
#         model.setData(index, editor.currentData(), Qt.ItemDataRole.UserRole)


from PyQt6.QtWidgets import QStyledItemDelegate, QComboBox, QLineEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator
from typing import List, Dict


# This is the original, simple delegate for the Resin and Zone rows/columns.
class ComboBoxDelegate(QStyledItemDelegate):
    def __init__(self, items: List, parent=None, editable=False):
        super().__init__(parent)
        self.items = items
        self.is_editable = editable

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.setEditable(self.is_editable)
        if self.is_editable: editor.lineEdit().setPlaceholderText("Select or type...")
        if self.items:
            if isinstance(self.items[0], str):
                editor.addItems(self.items)
            elif isinstance(self.items[0], tuple):
                for item_id, display_name in self.items: editor.addItem(display_name, userData=item_id)
        return editor

    def setEditorData(self, editor, index):
        current_text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        editor_index = editor.findText(current_text)
        if editor_index >= 0:
            editor.setCurrentIndex(editor_index)
        elif self.is_editable:
            editor.setCurrentText(current_text)

    def setModelData(self, editor, model, index):
        current_text, editor_index = editor.currentText(), editor.findText(editor.currentText(),
                                                                           Qt.MatchFlag.MatchFixedString)
        is_tuple_based = self.items and isinstance(self.items[0], tuple)
        if is_tuple_based:
            selected_id = editor.itemData(editor_index) if editor_index >= 0 else None
            model.setData(index, current_text, Qt.ItemDataRole.DisplayRole)
            model.setData(index, selected_id, Qt.ItemDataRole.UserRole)
        else:
            model.setData(index, current_text, Qt.ItemDataRole.DisplayRole)


# --- NEW: The smart, row-aware delegate for RPM and Feed Rate ---
class CascadingComboBoxDelegate(QStyledItemDelegate):
    """
    A smart delegate for a column that shows different dropdowns based on the row.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rpm_items = []
        self.feed_rate_items = []

    def set_items(self, rpms: List[str], feed_rates: List[str]):
        """Set the item lists for both potential dropdowns."""
        self.rpm_items = rpms
        self.feed_rate_items = feed_rates

    def createEditor(self, parent, option, index):
        """Checks the row and creates the appropriate editor."""
        editor = QComboBox(parent)
        editor.setEditable(True)

        row = index.row()
        if row == 1:  # Main Motor RPM row
            editor.addItems(self.rpm_items)
        elif row == 2:  # Feed Rate row
            editor.addItems(self.feed_rate_items)

        return editor

    def setEditorData(self, editor, index):
        current_text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        editor.setCurrentText(current_text)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.DisplayRole)


# --- NumericDelegate is unchanged ---
class NumericDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setValidator(QDoubleValidator(bottom=0, decimals=2, parent=editor))
        return editor