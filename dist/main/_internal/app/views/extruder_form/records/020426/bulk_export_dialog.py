# app/views/extruder_form/records/bulk_export_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGroupBox, QRadioButton,
    QLabel, QDialogButtonBox,
)
from PyQt6.QtCore import Qt

class BulkExportDialog(QDialog):
    """
    A dialog for choosing the format of a bulk Excel export.
    """
    # Define constants for the export options for clarity
    SEPARATE_FILES = 1
    SEPARATE_SHEETS = 2
    SINGLE_SHEET = 3

    def __init__(self, record_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bulk Export Options")
        self.setMinimumWidth(450)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        self.selected_option = self.SEPARATE_FILES  # Default selection

        layout = QVBoxLayout(self)

        # Instruction Label
        instruction_label = QLabel(
            f"You are about to export <b>{record_count} records</b>.<br>"
            "Please choose how you would like the reports to be saved."
        )
        instruction_label.setWordWrap(True)
        layout.addWidget(instruction_label)

        # Options GroupBox
        options_group = QGroupBox("Export Format")
        options_layout = QVBoxLayout(options_group)

        self.radio_separate_files = QRadioButton(
            "Save each report as a separate Excel file (in a new folder)."
        )
        self.radio_separate_sheets = QRadioButton(
            "Save all reports in a single Excel file (each on a different sheet)."
        )
        self.radio_single_sheet = QRadioButton(
            "Save all reports in a single Excel file (on one continuous sheet)."
        )

        self.radio_separate_files.setChecked(True)  # Default option

        options_layout.addWidget(self.radio_separate_files)
        options_layout.addWidget(self.radio_separate_sheets)
        options_layout.addWidget(self.radio_single_sheet)

        layout.addWidget(options_group)

        # Dialog Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

    def get_selected_option(self) -> int:
        """Returns the constant corresponding to the user's selected option."""
        if self.radio_separate_sheets.isChecked():
            return self.SEPARATE_SHEETS
        elif self.radio_single_sheet.isChecked():
            return self.SINGLE_SHEET
        else:
            return self.SEPARATE_FILES # Default