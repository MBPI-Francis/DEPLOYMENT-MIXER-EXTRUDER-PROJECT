# app/views/extruder_config/processing_params/handlers.py

from PyQt6.QtWidgets import QMessageBox
from .widgets.dialogs import CreateProcessingParamsDialog
from . import ops


class ProcessingParamsHandlers:
    def __init__(self, parent_view):
        self.parent_view = parent_view

    def setup_handlers(self, config):
        self.config = config
        self.parent_view.create_button.clicked.connect(self._handle_create)
        self.populate_table()

    def populate_table(self):
        # This logic is correct and doesn't need to change
        self.parent_view.table.setRowCount(0)
        session = self.Session()
        try:
            records = ops.get_all_processing_sets_for_main_table(session)
            self.parent_view.table.setRowCount(len(records))
            for row, result in enumerate(records):
                machine, creator = result
                self.parent_view.table.setItem(row, 0, self.parent_view.create_item(machine.name))
                self.parent_view.table.setItem(row, 1, self.parent_view.create_item(creator or "N/A"))
        finally:
            session.close()

    # --- THE STABLE FIX ---
    def _handle_create(self):
        """
        Manages the entire "Create" operation with a single, stable session.
        """
        # 1. Create ONE session that will live for the entire operation.
        session = self.Session()
        try:
            # 2. Pass this single session object to the dialog.
            dialog = CreateProcessingParamsDialog(session, self.parent_view.window())

            if dialog.exec():
                try:
                    # 3. Get the validated data from the dialog.
                    data = dialog.get_data()
                    # 4. Use the SAME session to perform the database transaction.
                    ops.create_processing_parameter_set(session, data, user_id=1)
                    QMessageBox.information(self.parent_view, "Success",
                                            "New processing parameter set created successfully.")
                    self.populate_table()  # Refresh the main table on success
                except ValueError as ve:
                    # Show validation errors from get_data() or the ops function
                    QMessageBox.warning(self.parent_view, "Validation Error", str(ve))
                except Exception as e:
                    # If any other error occurs, roll back the transaction
                    session.rollback()
                    QMessageBox.critical(self.parent_view, "Database Error", f"An error occurred while saving: {e}")
        finally:
            # 5. ALWAYS close the session when the operation is complete.
            session.close()