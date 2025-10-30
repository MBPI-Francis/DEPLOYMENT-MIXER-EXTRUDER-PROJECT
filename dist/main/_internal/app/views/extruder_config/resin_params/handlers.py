# app/views/extruder_config/resin_params/handlers.py

from PyQt6.QtWidgets import QMessageBox, QMenu, QTableWidgetItem
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
import qtawesome as qta
from pydantic import ValidationError

from . import ops
from .widgets import ComboBoxDelegate, ConfirmationDialog, RestoreDialog

# --- The configuration-driven column definition ---
COLUMN_CONFIG = [
    {'key': 'id', 'header': 'ID', 'hidden': True, 'editable': False},
    {'key': 'resin_name', 'header': 'Resin', 'stretch': True, 'editable': True},
    {'key': 'motor_rpm', 'header': 'Motor RPM', 'stretch': True, 'editable': True},
    {'key': 'feed_rate', 'header': 'Feed Rate', 'stretch': True, 'editable': True},
    {'key': 'created_by_username', 'header': 'Created By', 'editable': False},
    {'key': 'updated_at', 'header': 'Date Modified', 'editable': False},
    {'key': 'updated_by_username', 'header': 'Modified By', 'editable': False},
]


class ResinParamsPanelHandlers:
    def setup_handlers(self, config):
        self.config = config
        self._is_handling_change = False

        self.COLUMN_CONFIG = COLUMN_CONFIG
        self.KEY_TO_INDEX = {col['key']: i for i, col in enumerate(self.COLUMN_CONFIG)}

        session = self.Session()
        all_resins = ops.get_all_resins(session)
        session.close()
        resin_list = [(r.id, r.name) for r in all_resins]

        resin_col_idx = self.KEY_TO_INDEX['resin_name']
        self.resin_delegate = ComboBoxDelegate(resin_list, self.table)
        self.table.setItemDelegateForColumn(resin_col_idx, self.resin_delegate)

        self.add_button.clicked.connect(self._handle_add_row)
        self.restore_button.clicked.connect(self._handle_restore)
        self.table.itemChanged.connect(self._handle_item_changed)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        self.search_bar.textChanged.connect(self._apply_filters)
        self._populate_table()

    def _populate_table(self):
        try:
            self.table.itemChanged.disconnect(self._handle_item_changed)
        except TypeError:
            pass
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)
        session = self.Session()
        try:
            params = self.config['get_all_func'](session)
            for row, result in enumerate(params):
                self.table.insertRow(row)
                for col_idx, col_conf in enumerate(self.COLUMN_CONFIG):
                    key = col_conf['key']
                    data = getattr(result, key, None) or getattr(result.ResinParams, key, None)
                    if key == 'updated_at' and data:
                        display_text = data.strftime("%Y-%m-%d %H:%M")
                    else:
                        display_text = str(data or "")
                    item = QTableWidgetItem(display_text)
                    if key == 'resin_name':
                        item.setData(Qt.ItemDataRole.UserRole, result.ResinParams.resin_id)
                    if not col_conf['editable']:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.table.setItem(row, col_idx, item)
        finally:
            session.close()
            self.table.setSortingEnabled(True)
            self.table.itemChanged.connect(self._handle_item_changed)

    def _handle_add_row(self):
        try:
            self.table.itemChanged.disconnect(self._handle_item_changed)
            self.table.insertRow(0)
            edit_item = None
            for col_idx, col_conf in enumerate(self.COLUMN_CONFIG):
                display_text = "-1" if col_conf['key'] == 'id' else ""
                item = QTableWidgetItem(display_text)
                if not col_conf['editable']:
                    item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(0, col_idx, item)
                if col_conf['key'] == 'resin_name':
                    edit_item = item
            if edit_item:
                self.table.scrollToItem(edit_item)
                self.table.editItem(edit_item)
        finally:
            self.table.itemChanged.connect(self._handle_item_changed)

    # --- *** DEFINITIVE, CORRECTED VERSION OF THIS FUNCTION *** ---
    def _handle_item_changed(self, item: QTableWidgetItem):
        if self._is_handling_change: return

        col_conf = self.COLUMN_CONFIG[item.column()]
        if not col_conf['editable']: return

        self._is_handling_change = True
        try:
            row = item.row()
            id_str = self.table.item(row, self.KEY_TO_INDEX['id']).text()

            resin_item = self.table.item(row, self.KEY_TO_INDEX['resin_name'])
            rpm_item = self.table.item(row, self.KEY_TO_INDEX['motor_rpm'])
            feed_item = self.table.item(row, self.KEY_TO_INDEX['feed_rate'])

            if not all([resin_item, rpm_item, feed_item]): return

            resin_id = resin_item.data(Qt.ItemDataRole.UserRole)
            resin_text = resin_item.text().strip()
            motor_rpm = rpm_item.text().strip()
            feed_rate = feed_item.text().strip()

            is_new_item = (id_str == "-1")

            # --- STATE-AWARE VALIDATION LOGIC ---

            if is_new_item:
                # --- LOGIC FOR A NEW ROW ---
                # The "gate": only proceed if all three text fields have been filled.
                # This PREVENTS validation from firing while the user is tabbing through.
                if not all([resin_text, motor_rpm, feed_rate]):
                    return  # Do nothing, let the user continue editing.

                # If the gate is passed, THEN perform detailed validation.
                if resin_id is None:
                    QMessageBox.warning(self, "Invalid Resin",
                                        f"The resin '<b>{resin_text}</b>' is not a valid selection.")
                    self.table.removeRow(row)
                    return
            else:
                # --- LOGIC FOR AN EXISTING ROW ---
                # For existing rows, any empty required field is an immediate error.
                if not resin_id:
                    QMessageBox.warning(self, "Invalid Data", "Resin cannot be empty. Please select a valid option.")
                    self._populate_table()  # Revert
                    return
                if not motor_rpm:
                    QMessageBox.warning(self, "Invalid Data", "Motor RPM cannot be empty.")
                    self._populate_table()  # Revert
                    return
                if not feed_rate:
                    QMessageBox.warning(self, "Invalid Data", "Feed Rate cannot be empty.")
                    self._populate_table()  # Revert
                    return

            # --- If we reach here, the row is ready for a database operation ---
            session = self.Session()
            try:
                validated_data = self.config['validator'](resin_id=resin_id, motor_rpm=motor_rpm, feed_rate=feed_rate)
                item_id = None if is_new_item else int(id_str)

                # Uniqueness check (3 columns)
                if self.config['check_exists_func'](session, resin_id=resin_id, motor_rpm=motor_rpm,
                                                    feed_rate=feed_rate, exclude_id=item_id):
                    QMessageBox.warning(self, "Duplicate Record",
                                        "A parameter with this exact Resin, Motor RPM, and Feed Rate already exists.")
                    if is_new_item:
                        self.table.removeRow(row)
                    else:
                        self._populate_table()
                    return

                # Perform DB action
                if is_new_item:
                    self.config['create_func'](session, validated_data)
                else:
                    self.config['update_func'](session, item_id, validated_data)

                self._populate_table()  # Refresh the entire table to show the final, correct state.

            except (ValidationError, Exception) as e:
                QMessageBox.critical(self, "Error", f"Could not save the parameter: {e}")
                if is_new_item: self.table.removeRow(row)
            finally:
                session.close()
        finally:
            self._is_handling_change = False


    def _handle_restore(self):
        dialog = RestoreDialog(session_factory=self.Session, parent=self)
        dialog.operation_successful.connect(self._populate_table)
        dialog.open()

    def show_table_context_menu(self, position):
        selected_rows = self.table.selectionModel().selectedRows()
        num_selected = len(selected_rows)
        if num_selected == 0: return
        menu = QMenu(self)

        if num_selected == 1:
            edit_action = QAction(qta.icon("fa5s.edit", color="#007bff"), f"Edit {self.config['name_singular']}", self)

            menu.addAction(edit_action)
            menu.addSeparator()
            edit_action.triggered.connect(lambda: self.table.editItem(self.table.item(selected_rows[0].row(), self.KEY_TO_INDEX['resin_name'])))


        delete_text = f"Delete {num_selected} selected items"
        delete_action = QAction(qta.icon("fa5s.trash-alt", color="#dc3545"), delete_text, self)
        menu.addAction(delete_action)
        delete_action.triggered.connect(self._handle_delete_selection)
        menu.exec(self.table.mapToGlobal(position))

    def _handle_delete_selection(self):
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows: return
        ids_to_delete = [int(self.table.item(index.row(), 0).text()) for index in selected_rows]
        confirm_message = f"Are you sure you want to delete these <b>{len(ids_to_delete)}</b> parameters?"
        dialog = ConfirmationDialog(self, message=confirm_message)
        if dialog.exec():
            session = self.Session()
            try:
                num_deleted = self.config['delete_many_func'](session, ids_to_delete)
                QMessageBox.information(self, "Success", f"{num_deleted} parameters have been deleted.")
                self._populate_table()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not delete items: {e}")
            finally:
                session.close()

    def _apply_filters(self):
        search_text = self.search_bar.text().lower()
        for row in range(self.table.rowCount()):
            texts = [self.table.item(row, self.KEY_TO_INDEX[key]).text().lower() for key in
                     ['resin_name', 'motor_rpm', 'feed_rate']]
            is_match = any(search_text in text for text in texts)
            self.table.setRowHidden(row, not is_match)