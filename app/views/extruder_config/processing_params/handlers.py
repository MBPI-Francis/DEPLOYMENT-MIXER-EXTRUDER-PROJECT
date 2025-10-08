# app/views/extruder_config/processing_params/handlers.py
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMessageBox, QMenu, QDialog

from .widgets.confirmation_dialog import ConfirmationDialog
from .widgets.create_dialog import CreateProcessingParamsDialog
from .edit_dialog import EditProcessingParamsDialog
from .widgets.restore_dialog import RestoreDialog
from .widgets.view_dialog import ViewProcessingParamsDialog
from . import ops
import qtawesome as qta

class ProcessingParamsHandlers:
    def __init__(self, parent_view):
        self.parent_view = parent_view
        self.Session = None

    def setup_handlers(self, config):
        self.config = config
        self.parent_view.create_button.clicked.connect(self._handle_create)
        self.parent_view.restore_button.clicked.connect(self._handle_restore)
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
                    ops.create_processing_parameter_set(session, data, user_id=1)
                    session.commit()
                    QMessageBox.information(self.parent_view, "Success", "New processing parameter set created successfully.")
                    self.populate_table()
                except ValueError as ve: session.rollback(); QMessageBox.warning(self.parent_view, "Validation Error", str(ve))
                except Exception as e: session.rollback(); QMessageBox.critical(self.parent_view, "Database Error", f"An error occurred: {e}")
        finally: session.close()

    # def _show_context_menu(self, pos):
    #     selected_item = self.parent_view.table.itemAt(pos)
    #     if not selected_item: return
    #
    #     menu = QMenu(self)
    #     # --- NEW: Add the View action to the menu ---
    #     view_action = menu.addAction("View Details")
    #     edit_action = menu.addAction("Edit")
    #     menu.addSeparator()
    #     delete_action = menu.addAction("Delete") # Placeholder for the next step
    #
    #
    #     action = menu.exec(self.parent_view.table.mapToGlobal(pos))
    #
    #     if action == view_action:
    #         self._handle_view()
    #     elif action == edit_action:
    #         self._handle_edit()
    #     elif action == delete_action:
    #         self._handle_delete()

    # --- THIS IS THE REWRITTEN CONTEXT MENU FUNCTION ---
    def _show_context_menu(self, pos):
        """
        Shows a modern context menu with icons using the QAction pattern.
        """
        selected_item = self.parent_view.table.itemAt(pos)
        if not selected_item:
            return

        # Parent the menu to the main view to ensure proper styling and memory management
        menu = QMenu(self.parent_view)

        # 1. Create QAction objects for each menu item with icons and colored text
        view_action = QAction(qta.icon("fa5s.eye", color="#17a2b8"), "View Machine Settings", self.parent_view)
        edit_action = QAction(qta.icon("fa5s.edit", color="#007bff"), "Edit Machine Settings", self.parent_view)
        delete_action = QAction(qta.icon("fa5s.trash-alt", color="#dc3545"), "Delete Machine Settings", self.parent_view)

        # 2. Connect the 'triggered' signal of each action directly to its handler method
        view_action.triggered.connect(self._handle_view)
        edit_action.triggered.connect(self._handle_edit)
        delete_action.triggered.connect(self._handle_delete)

        # 3. Add the actions and a separator to the menu
        menu.addAction(view_action)
        menu.addAction(edit_action)
        menu.addSeparator()
        menu.addAction(delete_action)

        # 4. Execute the menu at the cursor's position
        # We no longer need the old if/elif block to check which action was clicked.
        menu.exec(self.parent_view.table.mapToGlobal(pos))




    # def _get_selected_machine_id(self):
    #     """Helper to get the ID of the currently selected row."""
    #     selected_row = self.parent_view.table.currentRow()
    #     if selected_row < 0: return None
    #     machine_id_item = self.parent_view.table.item(selected_row, 0)
    #     return machine_id_item.data(Qt.ItemDataRole.UserRole)

    # We restore the simple, original helper function for View and Edit.
    def _get_selected_machine_id(self):
        """Helper to get ONLY the ID of the currently selected row."""
        selected_row = self.parent_view.table.currentRow()
        if selected_row < 0:
            return None
        item = self.parent_view.table.item(selected_row, 0)
        if not item:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    # We keep the new helper function, but it will ONLY be used by the Delete handler.
    def _get_selected_machine_id_and_name(self):
        """Helper to get BOTH the ID and name for the Delete confirmation."""
        selected_row = self.parent_view.table.currentRow()
        if selected_row < 0: return None, None

        id_item = self.parent_view.table.item(selected_row, 0)
        if not id_item: return None, None

        name = id_item.text()
        machine_id = id_item.data(Qt.ItemDataRole.UserRole)
        return machine_id, name

    def _handle_view(self):
        """Opens the read-only view dialog."""
        # --- FIXED: Now calls the simple helper function ---
        machine_id = self._get_selected_machine_id()
        if not machine_id: return

        session = self.Session()
        try:
            dialog = ViewProcessingParamsDialog(session, machine_id, self.parent_view.window())
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._handle_edit()
        finally:
            session.close()

    def _handle_edit(self):
        """Opens the dialog to edit a record."""
        # --- FIXED: Now calls the simple helper function ---
        machine_id = self._get_selected_machine_id()
        if not machine_id:
            QMessageBox.warning(self.parent_view, "No Selection", "Please select a record to edit.")
            return

        session = self.Session()
        try:
            dialog = EditProcessingParamsDialog(session, machine_id, self.parent_view.window())
            if dialog.exec():
                try:
                    data = dialog.get_data()
                    ops.update_processing_parameter_set(session, machine_id, data, user_id=1)
                    session.commit()
                    QMessageBox.information(self.parent_view, "Success", "Parameter set updated successfully.")
                    self.populate_table()
                except ValueError as ve:
                    session.rollback(); QMessageBox.warning(self.parent_view, "Validation Error", str(ve))
                except Exception as e:
                    session.rollback(); QMessageBox.critical(self.parent_view, "Database Error",
                                                             f"An error occurred: {e}")
        finally:
            session.close()

    # def _handle_delete(self):
    #     """Handles the soft-deletion of a parameter set."""
    #     # This function correctly uses the helper that gets both ID and name.
    #     machine_id, machine_name = self._get_selected_machine_id_and_name()
    #     if not machine_id:
    #         QMessageBox.warning(self.parent_view, "No Selection", "Please select a record to delete.")
    #         return
    #
    #     reply = QMessageBox.question(
    #         self.parent_view, "Confirm Deletion",
    #         f"Are you sure you want to delete '{machine_name}' and all of its associated parameters?",
    #         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    #         QMessageBox.StandardButton.No
    #     )
    #     if reply == QMessageBox.StandardButton.Yes:
    #         session = self.Session()
    #         try:
    #             ops.soft_delete_parameter_set(session, machine_id, user_id=1)
    #             session.commit()
    #             QMessageBox.information(self.parent_view, "Success", f"'{machine_name}' has been deleted.")
    #             self.populate_table()
    #         except Exception as e:
    #             session.rollback()
    #             QMessageBox.critical(self.parent_view, "Error", f"An error occurred during deletion: {e}")
    #         finally:
    #             session.close()

    # --- THIS IS THE REVISED DELETE HANDLER ---
    def _handle_delete(self):
        """
        Handles the soft-deletion of a parameter set using the custom ConfirmationDialog.
        """
        machine_id, machine_name = self._get_selected_machine_id_and_name()
        if not machine_id:
            QMessageBox.warning(self.parent_view, "No Selection", "Please select a record to delete.")
            return

        # 1. Create the detailed confirmation message.
        message = (f"You are about to delete <b>'{machine_name}'</b> and all of its "
                   f"associated processing parameters. This action cannot be undone directly, "
                   f"but the record can be recovered from the Restore menu.")

        # 2. Instantiate and show your custom dialog.
        dialog = ConfirmationDialog(parent=self.parent_view.window(), message=message)

        # 3. Check if the user accepted (dialog.exec() returns True).
        if dialog.exec():
            # User typed "YES" and clicked Proceed.
            session = self.Session()
            try:
                ops.soft_delete_parameter_set(session, machine_id, user_id=1)  # Assuming user_id=1
                session.commit()
                self.populate_table()
                QMessageBox.information(self.parent_view, "Success", f"'{machine_name}' has been deleted.")

            except Exception as e:
                session.rollback()
                QMessageBox.critical(self.parent_view, "Error", f"An error occurred during deletion: {e}")
            finally:
                session.close()

    def _handle_restore(self):
        """Opens the dialog to restore deleted records."""
        # This function is correct and unchanged
        session = self.Session()
        try:
            dialog = RestoreDialog(session, self.parent_view.window())
            if dialog.exec():
                machine_id_to_restore = dialog.selected_machine_id
                if machine_id_to_restore is None: return
                try:
                    ops.restore_parameter_set(session, machine_id_to_restore)
                    session.commit()
                    QMessageBox.information(self.parent_view, "Success", "The record has been successfully restored.")
                    self.populate_table()
                except ValueError as ve:
                    session.rollback()
                    QMessageBox.warning(self.parent_view, "Restore Error", str(ve))
                except Exception as e:
                    session.rollback()
                    QMessageBox.critical(self.parent_view, "Error", f"An error occurred during restoration: {e}")
        finally:
            session.close()