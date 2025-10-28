# app/views/extruder_form/records/edit_dialog.py

from PyQt6.QtWidgets import QDialog, QVBoxLayout
from sqlalchemy.orm import sessionmaker
from typing import Type

# Import the existing entry form view
from app.views.extruder_form.entry_form.main import ExtruderEntryFormView


class ExtruderEditDialog(QDialog):
    """
    A dialog for editing an existing Extruder Production Record.
    It hosts the main ExtruderEntryFormView and puts it into an "edit" state.
    """

    def __init__(self, session_factory: Type[sessionmaker], record_to_edit, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Extruder Production Record")
        self.setMinimumSize(1400, 900)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Create an instance of the comprehensive entry form
        self.form_view = ExtruderEntryFormView(session_factory)

        # Populate the form with the data of the record being edited

        self.form_view.populate_form_for_editing(record_to_edit)

        # When the form successfully saves its data, this dialog will accept (close).

        self.form_view.data_saved.connect(self.accept)






        layout.addWidget(self.form_view)