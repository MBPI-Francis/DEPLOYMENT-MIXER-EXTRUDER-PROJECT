# app/views/extruder_settings/records/handlers.py

from PyQt6.QtWidgets import QMessageBox, QMenu, QTableWidgetItem
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt
import qtawesome as qta
from pydantic import ValidationError
from .widgets import RestoreDialog, ConfirmationDialog


# --- Base Handler with Shared Logic ---
class BasePanelHandlers:
    """Contains logic shared between both Resin and Zone panels."""

    def _setup_common_signals(self):
        """Connects signals that are identical for all panels."""
        self.restore_button.clicked.connect(self._handle_restore)
        self.table.customContextMenuRequested.connect(self.show_table_context_menu)
        self.search_bar.textChanged.connect(self._apply_filters)

    def show_table_context_menu(self, position):
        # This logic is correct and unchanged
        selected_rows = self.table.selectionModel().selectedRows()
        num_selected = len(selected_rows)
        if num_selected == 0: return
        menu = QMenu(self)
        if num_selected == 1:
            edit_action = QAction(qta.icon("fa5s.edit", color="#007bff"), f"Edit {self.config['name_singular']}", self)
            menu.addAction(edit_action)
            # The name column is different for Resin (2) vs Zone (1)
            name_col_idx = 2 if 'check_abbreviation_exists_func' in self.config else 1
            edit_action.triggered.connect(
                lambda: self.table.editItem(self.table.item(selected_rows[0].row(), name_col_idx)))
        delete_text = f"Delete {num_selected} {self.config['name_plural' if num_selected > 1 else 'name_singular']}"
        delete_action = QAction(qta.icon("fa5s.trash-alt", color="#dc3545"), delete_text, self)
        menu.addAction(delete_action)
        delete_action.triggered.connect(self._handle_delete_selection)
        menu.exec(self.table.mapToGlobal(position))

    def _handle_delete_selection(self):
        # This logic is correct and unchanged
        selected_rows = self.table.selectionModel().selectedRows()
        if not selected_rows: return
        ids_to_delete = [int(self.table.item(index.row(), 0).text()) for index in selected_rows]
        name_col_idx = 2 if 'check_abbreviation_exists_func' in self.config else 1
        names_to_delete = [self.table.item(index.row(), name_col_idx).text() for index in selected_rows]
        if len(names_to_delete) == 1:
            confirm_message = f"Are you sure you want to delete '<b>{names_to_delete[0]}</b>'?"
        else:
            display_names = ", ".join(f"'{name}'" for name in names_to_delete[:3])
            ellipsis = "..." if len(names_to_delete) > 3 else ""
            confirm_message = (
                f"Are you sure you want to delete these <b>{len(names_to_delete)}</b> {self.config['name_plural'].lower()}?"
                f"\n({display_names}{ellipsis})")
        dialog = ConfirmationDialog(self, message=confirm_message)
        if dialog.exec():
            session = self.Session()
            try:
                num_deleted = self.config['delete_many_func'](session, ids_to_delete)
                QMessageBox.information(self, "Success",
                                        f"{num_deleted} {self.config['name_plural'].lower()} have been deleted.")
                self._populate_table()
            except Exception as e:
                QMessageBox.critical(self, "Database Error", f"Could not delete items: {e}")
            finally:
                session.close()

    def _handle_restore(self):
        """
        This is the handler for the restore button. It was never being called,
        but the logic itself is correct.
        """
        dialog = RestoreDialog(
            session_factory=self.Session,
            get_deleted_func=self.config['get_deleted_func'],
            restore_func=self.config['restore_func'],
            item_name_plural=self.config['name_plural'],
            parent=self
        )
        dialog.operation_successful.connect(self._populate_table)
        dialog.open()


# --- Resin-specific Handler ---
class ResinPanelHandlers(BasePanelHandlers):
    def setup_handlers(self, config):
        self.config = config
        self._is_handling_change = False
        # Call the base method to connect common signals like the restore button
        self._setup_common_signals()
        # Connect signals specific to this panel
        self.add_button.clicked.connect(self._handle_add_row)
        self.table.itemChanged.connect(self._handle_item_changed)
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
            items = self.config['get_all_func'](session)
            for row, result in enumerate(items):
                item, creator_name = result
                self.table.insertRow(row)
                id_item = QTableWidgetItem(str(item.id))
                abbr_item = QTableWidgetItem(item.abbreviation or "")
                name_item = QTableWidgetItem(item.name)
                creator_item = QTableWidgetItem(creator_name or "N/A")
                date_item = QTableWidgetItem(item.created_at.strftime("%Y-%m-%d"))
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                creator_item.setFlags(creator_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 0, id_item)
                self.table.setItem(row, 1, abbr_item)
                self.table.setItem(row, 2, name_item)
                self.table.setItem(row, 3, creator_item)
                self.table.setItem(row, 4, date_item)
        finally:
            session.close()
            self.table.setSortingEnabled(True)
            self.table.itemChanged.connect(self._handle_item_changed)

    def _handle_add_row(self):
        try:
            self.table.itemChanged.disconnect(self._handle_item_changed)
            self.table.insertRow(0)
            self.table.setItem(0, 0, QTableWidgetItem("-1"))
            abbreviation_item = QTableWidgetItem("")
            self.table.setItem(0, 1, abbreviation_item)
            self.table.setItem(0, 2, QTableWidgetItem(""))
            self.table.setItem(0, 3, QTableWidgetItem("..."))
            self.table.setItem(0, 4, QTableWidgetItem("..."))
            self.table.scrollToItem(abbreviation_item)
            self.table.editItem(abbreviation_item)
        finally:
            self.table.itemChanged.connect(self._handle_item_changed)

    def _handle_item_changed(self, item: QTableWidgetItem):
        if self._is_handling_change or item.column() not in [1, 2]: return
        self._is_handling_change = True
        try:
            row = item.row()
            item_id_str = self.table.item(row, 0).text()
            abbreviation_text = self.table.item(row, 1).text().strip()
            name_text = self.table.item(row, 2).text().strip()
            if not name_text and item_id_str == "-1":
                self.table.removeRow(row)
                return
            session = self.Session()
            try:
                validated_data = self.config['validator'](name=name_text, abbreviation=abbreviation_text or None)
                is_new_item = item_id_str == "-1"
                item_id = None if is_new_item else int(item_id_str)
                if self.config['check_abbreviation_exists_func'](session, abbreviation=validated_data.abbreviation,
                                                                 exclude_id=item_id):
                    QMessageBox.warning(self, "Duplicate Entry",
                                        f"The abbreviation '{validated_data.abbreviation}' is already in use.")
                    if is_new_item: self.table.removeRow(row)
                    return
                if self.config['check_exists_func'](session, name=validated_data.name, exclude_id=item_id):
                    QMessageBox.warning(self, "Duplicate Entry", f"The name '{validated_data.name}' is already in use.")
                    if is_new_item: self.table.removeRow(row)
                    return
                if is_new_item:
                    new_item = self.config['create_func'](session, validated_data)
                    self.table.item(row, 0).setText(str(new_item.id))
                    self.table.item(row, 3).setText("Current User")
                    self.table.item(row, 4).setText(new_item.created_at.strftime("%Y-%m-%d"))
                else:
                    self.config['update_func'](session, item_id, validated_data)
                self.table.sortItems(2, Qt.SortOrder.AscendingOrder)
            except (ValidationError, Exception) as e:
                QMessageBox.critical(self, "Error", f"Could not save changes: {e}")
                if item_id_str == "-1": self.table.removeRow(row)
            finally:
                session.close()
        finally:
            self._is_handling_change = False

    def _apply_filters(self):
        search_text = self.search_bar.text().lower()
        for row in range(self.table.rowCount()):
            abbr_text = self.table.item(row, 1).text().lower()
            name_text = self.table.item(row, 2).text().lower()
            is_match = search_text in abbr_text or search_text in name_text
            self.table.setRowHidden(row, not is_match)


# --- Zone-specific Handler ---
class ZonePanelHandlers(BasePanelHandlers):
    def setup_handlers(self, config):
        self.config = config
        self._is_handling_change = False
        # Call the base method to connect common signals like the restore button
        self._setup_common_signals()
        # Connect signals specific to this panel
        self.add_button.clicked.connect(self._handle_add_row)
        self.table.itemChanged.connect(self._handle_item_changed)
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
            items = self.config['get_all_func'](session)
            for row, result in enumerate(items):
                item, creator_name = result
                self.table.insertRow(row)
                id_item = QTableWidgetItem(str(item.id))
                name_item = QTableWidgetItem(item.name)
                creator_item = QTableWidgetItem(creator_name or "N/A")
                date_item = QTableWidgetItem(item.created_at.strftime("%Y-%m-%d"))
                id_item.setFlags(id_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                creator_item.setFlags(creator_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                date_item.setFlags(date_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row, 0, id_item)
                self.table.setItem(row, 1, name_item)
                self.table.setItem(row, 2, creator_item)
                self.table.setItem(row, 3, date_item)
        finally:
            session.close()
            self.table.setSortingEnabled(True)
            self.table.itemChanged.connect(self._handle_item_changed)

    def _handle_add_row(self):
        try:
            self.table.itemChanged.disconnect(self._handle_item_changed)
            self.table.insertRow(0)
            self.table.setItem(0, 0, QTableWidgetItem("-1"))
            name_item = QTableWidgetItem("")
            self.table.setItem(0, 1, name_item)
            self.table.setItem(0, 2, QTableWidgetItem("..."))
            self.table.setItem(0, 3, QTableWidgetItem("..."))
            self.table.scrollToItem(name_item)
            self.table.editItem(name_item)
        finally:
            self.table.itemChanged.connect(self._handle_item_changed)

    def _handle_item_changed(self, item: QTableWidgetItem):
        if self._is_handling_change or item.column() != 1: return
        self._is_handling_change = True
        try:
            row = item.row()
            item_id_str = self.table.item(row, 0).text()
            name_text = self.table.item(row, 1).text().strip()
            if not name_text and item_id_str == "-1":
                self.table.removeRow(row)
                return
            session = self.Session()
            try:
                validated_data = self.config['validator'](name=name_text)
                is_new_item = item_id_str == "-1"
                item_id = None if is_new_item else int(item_id_str)
                if self.config['check_exists_func'](session, name=validated_data.name, exclude_id=item_id):
                    QMessageBox.warning(self, "Duplicate Entry", f"The name '{validated_data.name}' is already in use.")
                    if is_new_item: self.table.removeRow(row)
                    return
                if is_new_item:
                    new_item = self.config['create_func'](session, validated_data)
                    self.table.item(row, 0).setText(str(new_item.id))
                    self.table.item(row, 2).setText("Current User")
                    self.table.item(row, 3).setText(new_item.created_at.strftime("%Y-%m-%d"))
                else:
                    self.config['update_func'](session, item_id, validated_data)
                self.table.sortItems(1, Qt.SortOrder.AscendingOrder)
            except (ValidationError, Exception) as e:
                QMessageBox.critical(self, "Error", f"Could not save changes: {e}")
                if item_id_str == "-1": self.table.removeRow(row)
            finally:
                session.close()
        finally:
            self._is_handling_change = False

    def _apply_filters(self):
        search_text = self.search_bar.text().lower()
        for row in range(self.table.rowCount()):
            name_text = self.table.item(row, 1).text().lower()
            self.table.setRowHidden(row, not search_text in name_text)