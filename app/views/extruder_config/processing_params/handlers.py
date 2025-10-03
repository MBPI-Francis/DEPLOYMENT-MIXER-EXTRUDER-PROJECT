# app/views/extruder_config/processing_params/handlers.py
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QMessageBox, QMenu
# --- UPDATED: Import dialogs from the new refactored file ---
from .widgets.dialogs import CreateProcessingParamsDialog, EditProcessingParamsDialog
from . import ops


class ProcessingParamsHandlers:
    def __init__(self, parent_view):
        self.parent_view = parent_view
        self.Session = None  # Will be set by the view

    def setup_handlers(self, config):
        self.config = config
        self.parent_view.create_button.clicked.connect(self._handle_create)

        # --- NEW: Connect the context menu signal ---
        self.parent_view.table.customContextMenuRequested.connect(self._show_context_menu)

        self.populate_table()

    def populate_table(self):
        self.parent_view.table.setRowCount(0)
        session = self.Session()
        try:
            records = ops.get_all_processing_sets_for_main_table(session)
            self.parent_view.table.setRowCount(len(records))
            for row, result in enumerate(records):
                machine, creator = result
                # --- UPDATED: Store the machine.id in the first item of each row ---
                self.parent_view.table.setItem(row, 0, self.parent_view.create_item(machine.name, data=machine.id))
                self.parent_view.table.setItem(row, 1, self.parent_view.create_item(creator or "N/A"))
        finally:
            session.close()

    def _handle_create(self):
        session = self.Session()
        try:
            dialog = CreateProcessingParamsDialog(session, self.parent_view.window())

            if dialog.exec():
                try:
                    data = dialog.get_data()
                    ops.create_processing_parameter_set(session, data, user_id=1)  # Assuming user_id=1
                    session.commit()  # Commit the transaction
                    QMessageBox.information(self.parent_view, "Success",
                                            "New processing parameter set created successfully.")
                    self.populate_table()
                except ValueError as ve:
                    session.rollback()
                    QMessageBox.warning(self.parent_view, "Validation Error", str(ve))
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self.parent_view, "Database Error", f"An error occurred while saving: {e}")
        finally:
            session.close()

    # --- NEW: Method to show the context menu ---
    def _show_context_menu(self, pos):
        selected_item = self.parent_view.table.itemAt(pos)
        if not selected_item:
            return

        menu = QMenu()
        edit_action = menu.addAction("Edit")
        # You can add "View" and "Delete" actions here in the future

        action = menu.exec(self.parent_view.table.mapToGlobal(pos))

        if action == edit_action:
            self._handle_edit()

    # --- NEW: Method to handle the entire edit process ---
    def _handle_edit(self):
        selected_row = self.parent_view.table.currentRow()
        if selected_row < 0:
            return

        machine_id_item = self.parent_view.table.item(selected_row, 0)
        machine_id = machine_id_item.data(Qt.ItemDataRole.UserRole)

        if not machine_id:
            QMessageBox.warning(self.parent_view, "Error", "Could not identify the selected record.")
            return

        session = self.Session()
        try:
            dialog = EditProcessingParamsDialog(session, machine_id, self.parent_view.window())

            if dialog.exec():
                try:
                    data = dialog.get_data()
                    ops.update_processing_parameter_set(session, machine_id, data, user_id=1)  # Assuming user_id=1
                    session.commit()  # Commit the transaction
                    QMessageBox.information(self.parent_view, "Success", "Parameter set updated successfully.")
                    self.populate_table()
                except ValueError as ve:
                    session.rollback()
                    QMessageBox.warning(self.parent_view, "Validation Error", str(ve))
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self.parent_view, "Database Error", f"An error occurred while updating: {e}")
        finally:
            session.close()
