# app/views/extruder_form/records/edit_dialog.py

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QScrollArea
from PyQt6.QtCore import Qt
from sqlalchemy.orm import sessionmaker
from typing import Type

# Import the existing entry form view
from app.views.extruder_form.entry_form.main import ExtruderEntryFormView


class ExtruderEditDialog(QDialog):
    """
    A resizable and scrollable dialog for editing an existing Extruder Production Record.
    It hosts the main ExtruderEntryFormView inside a QScrollArea.
    """

    def __init__(self, session_factory: Type[sessionmaker], record_to_edit, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Extruder Production Record")

        self.setObjectName("EditDialog")
        self.resize(1400, 900)
        self.setSizeGripEnabled(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)



        # The main layout for the dialog window itself
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # --- THIS IS THE FIX (Part 2) ---
        # 1. Create a QScrollArea
        scroll_area = QScrollArea()
        scroll_area.setObjectName("scroll_area")
        # This is critical: it tells the scroll area's content to resize horizontally
        scroll_area.setWidgetResizable(True)
        # Optional: hide the horizontal scrollbar if the content always fits width-wise
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 2. The ExtruderEntryFormView will be the content of the scroll area
        self.form_view = ExtruderEntryFormView(session_factory)
        self.form_view.setObjectName("scroll_content_widget")

        # 3. Set the form as the widget for the scroll area
        scroll_area.setWidget(self.form_view)


        # 4. Add the scroll_area (not the form itself) to the dialog's main layout
        layout.addWidget(scroll_area)
        # --- END FIX ---

        # Populate the form with the data of the record being edited
        self.form_view.populate_form_for_editing(record_to_edit)

        # When the form successfully saves its data, this dialog will accept (close).
        self.form_view.data_saved.connect(self.accept)