
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


class DynamicComboBoxDelegate(QStyledItemDelegate):
    """
    A more advanced delegate whose item list can be updated dynamically.
    It can also be configured to be editable or not.
    """

    def __init__(self, parent=None, editable=False):
        super().__init__(parent)
        self.items = []
        self.is_editable = editable


    def set_items(self, items: List):
        """Allows updating the list of items for the dropdown."""
        self.items = items

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.setEditable(self.is_editable)

        if self.is_editable:
            editor.lineEdit().setPlaceholderText("Select or type...")

        # If items are simple strings, add them directly
        if self.items and isinstance(self.items[0], str):
            editor.addItems(self.items)
        # If items are (id, name) tuples
        elif self.items and isinstance(self.items[0], tuple):
            for item_id, display_name in self.items:
                editor.addItem(display_name, userData=item_id)

        return editor

    def setEditorData(self, editor, index):
        current_text = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        editor_index = editor.findText(current_text)
        if editor_index >= 0:
            editor.setCurrentIndex(editor_index)
        elif self.is_editable:
            editor.setCurrentText(current_text)

    def setModelData(self, editor, model, index):
        current_text = editor.currentText()
        editor_index = editor.findText(current_text, Qt.MatchFlag.MatchFixedString)

        # If it's a tuple-based delegate (like Resins), save the ID
        if self.items and isinstance(self.items[0], tuple):
            selected_id = editor.itemData(editor_index) if editor_index >= 0 else None
            model.setData(index, current_text, Qt.ItemDataRole.DisplayRole)
            model.setData(index, selected_id, Qt.ItemDataRole.UserRole)
        else:  # For simple string-based delegates (RPM, Feed Rate), just save the text
            model.setData(index, current_text, Qt.ItemDataRole.DisplayRole)

class NumericDelegate(QStyledItemDelegate):
    """A delegate for allowing only numeric (float/decimal) input."""
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        # Allow decimals
        editor.setValidator(QDoubleValidator(bottom=0, decimals=2, parent=editor))
        return editor
