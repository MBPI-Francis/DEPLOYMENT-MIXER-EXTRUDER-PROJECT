# app/views/extruder_config/processing_params/widgets/delegates.py

from PyQt6.QtWidgets import QStyledItemDelegate, QComboBox, QLineEdit
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QDoubleValidator
from typing import List


# The incorrect import "from .resin_params_table import ResinParamsTable" has been REMOVED.
# This file now has NO KNOWLEDGE of any specific table, which resolves the circular import.

class ComboBoxDelegate(QStyledItemDelegate):
    def __init__(self, items: List, parent=None, editable=False):
        super().__init__(parent)
        self.items = items
        self.is_editable = editable

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.setEditable(self.is_editable)
        if self.is_editable:
            editor.lineEdit().setPlaceholderText("Select or type...")
        if self.items:
            if self.items and isinstance(self.items[0], str):
                editor.addItems(self.items)
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
        is_tuple_based = self.items and isinstance(self.items[0], tuple)

        if is_tuple_based:
            selected_id = editor.itemData(editor_index) if editor_index >= 0 else None
            model.setData(index, current_text, Qt.ItemDataRole.DisplayRole)
            model.setData(index, selected_id, Qt.ItemDataRole.UserRole)
        else:
            model.setData(index, current_text, Qt.ItemDataRole.DisplayRole)


class CascadingComboBoxDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.rpm_items = []
        self.feed_rate_items = []

    def set_items(self, rpms: List[str], feed_rates: List[str]):
        self.rpm_items = rpms
        self.feed_rate_items = feed_rates

    def createEditor(self, parent, option, index):
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


class NumericDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setValidator(QDoubleValidator(bottom=0, decimals=2, parent=editor))
        return editor