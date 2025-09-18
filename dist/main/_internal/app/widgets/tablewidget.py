# THIS WILL BE A REUSABLE TABLE ACROSS ALL THE FORMS THAT WILL BE GENERATED

from PyQt6.QtWidgets import (
    QWidget, QSizePolicy, QVBoxLayout, QHBoxLayout,
    QTableWidget, QScrollArea, QPushButton, QFileDialog, QHeaderView,
    QTableWidgetItem, QMenu, QLabel, QComboBox, QInputDialog, QLineEdit
)

from PyQt6.QtCore import Qt, pyqtSignal

from typing import Union, Callable, Type, Literal
from sqlalchemy.orm import Session, DeclarativeMeta
from app.helpers import button_cursor_pointer, load_styles
from app.StyledMessage import StyledMessageBox
from constants.Enums import TableHeader
import pandas as pd
import os

class TableWidget(QWidget):
    double_clicked = pyqtSignal(str)

    def __init__(
        self,
        session_factory: Callable[..., Session],
        db_model: Type[DeclarativeMeta] = None,
        view_type: Union[
            Literal[
                "endorsement-list", 
                "endorsement-create"
            ], 
            None
        ] = None,
        parent=None,
        items_per_page: int = 20, # New: items per page for pagination
    ):
        super().__init__(parent)
        self.export_btn = QPushButton("Export Excel")
        self.export_btn.setObjectName("endorsement-export-btn")

        self.valid_views_to_show_export_btn = [
            "endorsement-list",
        ]

        self.excluded_views_for_show_export_btn = [
            "endorsement-create"
        ]

        if view_type in self.excluded_views_for_show_export_btn:
            self.export_btn.hide()

        self.Session = session_factory
        self.db_model = db_model
        self.view_type = view_type
        self.items_per_page = items_per_page # Store items per page
        self.current_page = 1 # Initialize current page
        self.total_pages = 1 # Initialize total pages
        self.filtered_results = None

        self.init_ui()
        self.load_data()
        self.apply_styles()

    def init_ui(self):
        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )
        self.layout = QVBoxLayout(self)

        # CREATE THE ACTUAL TABLE HERE
        self.table = QTableWidget()
        self.table.setObjectName("endorsementTable")
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setMinimumHeight(700)

        # THIS IS FOR HAVING A RIGHT CLICK BUTTON THE ROWS
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)

        # self.table.setHorizontalHeaderLabels()

        # IF ELSE STATEMENT HERE TO CHANGE THE COLUMN BASED ON CONDITION
        # if selfF.view_type and self.view_type == self.valid_views_to_show_export_btn[0]:

        if self.view_type and self.view_type.startswith("endorsement"):
            self.header_labels = TableHeader.get_header("endorsement")
            
            # CONFIGURE HEADERS (make this dynamic based on the )
            self.table.setColumnCount(len(self.header_labels))
            self.table.setHorizontalHeaderLabels(self.header_labels)

        self.table.horizontalHeader().setStretchLastSection(True)

        # CREATING A CONTAINER WIDGET FOR PROPER RESIZING
        container = QWidget()
        container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        container.setLayout(QVBoxLayout())
        container.layout().setContentsMargins(0, 0, 0, 0)
        container.layout().addWidget(self.table)

        # ADD SCROLL AREA
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setWidget(container)

        self.layout.addWidget(scroll_area)

        # CONNECT SIGNALS
        self.table.doubleClicked.connect(self.on_row_double_click)

        # Pagination controls
        self.pagination_layout = QHBoxLayout()
        self.prev_btn = QPushButton("Previous")
        self.prev_btn.clicked.connect(self.prev_page)
        self.prev_btn.setObjectName("tablewidget-prev-btn")

        self.page_label = QLabel(f"Page {self.current_page} of {self.total_pages}")
        self.page_label.setObjectName("table-widget-page-label")
        
        self.next_btn = QPushButton("Next")
        self.next_btn.clicked.connect(self.next_page)
        self.next_btn.setObjectName("tablewidget-next-btn")

        self.items_per_page_combo = QComboBox()
        self.items_per_page_combo.addItems(["10", "20", "50", "100"])
        self.items_per_page_combo.setCurrentText(str(self.items_per_page))
        self.items_per_page_combo.currentIndexChanged.connect(self.update_items_per_page)
        self.items_per_page_combo.setObjectName("table-widget-items-per-page-combo")

        # refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.reload_table)

        self.items_per_page_label = QLabel("Items per page:")
        self.items_per_page_label.setObjectName("table-widget-items-per-page-label")

        self.pagination_layout.addWidget(self.items_per_page_label)
        self.pagination_layout.addWidget(self.items_per_page_combo)
        self.pagination_layout.addWidget(self.refresh_btn)
        self.pagination_layout.addStretch()
        self.pagination_layout.addWidget(self.prev_btn)
        self.pagination_layout.addWidget(self.page_label)
        self.pagination_layout.addWidget(self.next_btn)

        self.layout.addLayout(self.pagination_layout)

        btn_container = QHBoxLayout()
        btn_container.addWidget(self.export_btn)
        btn_container.addStretch()
        self.layout.addLayout(btn_container)
        self.export_btn.clicked.connect(self.export_to_excel)

    def reload_table(self):
        self.load_data()

    def apply_styles(self):
        qss_path = os.path.join(os.path.dirname(__file__), "styles", "table.css")
        button_cursor_pointer(self.export_btn)
        button_cursor_pointer(self.prev_btn)
        button_cursor_pointer(self.next_btn)

        self.table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)

        # This is correct: The scrollbar will appear only if needed
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # -------------- load the styling here ------------------
        load_styles(qss_path, self)
        
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)

        # Set column widths (adjust as needed)
        for i in range(len(self.header_labels)):
            self.table.setColumnWidth(i, 150)
            # Add these lines to explicitly set resize mode for each column.
            self.table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)

    def export_to_excel(self):
        """Export table data to Excel file."""
        try:
            # Get save file path
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Save as Excel",
                "Endorsement_Summary",
                "Excel Files (*.xlsx)"
            )

            if not path:
                return

            # Create DataFrame from table data
            data = []

            for row in range(self.table.rowCount()):
                row_data = []

                for col in range(self.table.columnCount()):
                    item = self.table.item(row, col)
                    row_data.append(item.text() if item else "")

                data.append(row_data)

            headers = [
                self.table.horizontalHeaderItem(i).text()
                for i in range(self.table.columnCount())
            ]

            df = pd.DataFrame(data, columns=headers)

            # Export using pandas
            df.to_excel(path, index=False)
            StyledMessageBox.information(
                self,
                "Success",
                f"Exported to {path}"
            )

        except Exception as e:
            StyledMessageBox.critical(
                self,
                "Error",
                f"Export failed: {str(e)}"
            )

    def load_data(self):
        """Load data from the endorsement_combined view with pagination."""
        try:
            session = self.Session()
            model = self.db_model

            # Debug: Verify total count
            total_items = session.query(model).count()
            # print(f"Total items in view: {total_items}")  # Should match pgAdmin
            
            self.total_pages = max(1, (total_items + self.items_per_page - 1) // self.items_per_page)
            # print(f"Total pages: {self.total_pages}")

            offset = (self.current_page - 1) * self.items_per_page
            limit = self.items_per_page
            # print(f"Loading page {self.current_page} (offset {offset}, limit {limit})")

            if model.__tablename__ == "endorsement_combined":
                # Get fresh results with explicit ordering
                results = session.query(model)\
                    .order_by(model.t_lot_number.asc())\
                    .offset(offset).limit(limit).all()

                # Debug: Print all fetched records
                # print(f"Fetched {len(results)} records:")
                # for i, r in enumerate(results):
                #     print(f"{i}: {r.t_refno} | {r.t_lot_number} | {r.t_total_quantity}")

                self.table.setRowCount(len(results))
                
                # Correct column mapping (0-7)
                for row_idx, record in enumerate(results):
                    self._set_table_item(row_idx, 0, record.t_refno)
                    self._set_table_item(row_idx, 1, record.t_date_endorsed.strftime("%Y-%m-%d"))  # Fixed column index
                    self._set_table_item(row_idx, 2, record.t_category)
                    self._set_table_item(row_idx, 3, record.t_prodcode)
                    self._set_table_item(row_idx, 4, record.t_lot_number)
                    self._set_table_item(row_idx, 5, f"{float(record.t_total_quantity):.2f}")
                    self._set_table_item(row_idx, 6, record.t_status)
                    self._set_table_item(row_idx, 7, record.t_endorsed_by)
                    self._set_table_item(row_idx, 8, record.t_source_table)
                    self._set_table_item(row_idx, 9, record.t_has_excess)

                self.update_pagination_controls()
        except Exception as e:
            print(f"Error loading data: {str(e)}")
            raise
        finally:
            session.close()
    
    # def update_table_with_results(self, results, apply_pagination=True):
    #     """Update the table widget with filtered results"""
    #     self.filtered_results = results
        
    #     if apply_pagination:
    #         total_items = len(results)
    #         self.total_pages = max(1, (total_items + self.items_per_page - 1) // self.items_per_page)
    #         self.current_page = min(self.current_page, self.total_pages)  # Ensure current page is valid
    #         # Apply pagination
    #         offset = (self.current_page - 1) * self.items_per_page
    #         paginated_results = results[offset:offset + self.items_per_page]
        
    #     else:
    #         # Show all results without pagination
    #         paginated_results = results
    #         self.total_pages = 1
    #         self.current_page = 1

    #     self.table.setRowCount(len(results))
    #     for row_idx, record in enumerate(results):
    #         self._set_table_item(row_idx, 0, record.t_refno)
    #         self._set_table_item(row_idx, 1, record.t_date_endorsed.strftime("%Y-%m-%d"))
    #         self._set_table_item(row_idx, 2, record.t_category)
    #         self._set_table_item(row_idx, 3, record.t_prodcode)
    #         self._set_table_item(row_idx, 4, record.t_lot_number)
    #         self._set_table_item(row_idx, 5, f"{float(record.t_total_quantity):.2f}")
    #         self._set_table_item(row_idx, 6, record.t_status)
    #         self._set_table_item(row_idx, 7, record.t_endorsed_by)
    #         self._set_table_item(row_idx, 8, record.t_source_table)
    #         self._set_table_item(row_idx, 9, record.t_has_excess)
        
    #     # Disable pagination controls when filtering
    #     self.prev_btn.setEnabled(False)
    #     self.next_btn.setEnabled(False)
    #     self.page_label.setText(f"Showing {len(results)} filtered records")

    def update_table_with_results(self, results, apply_pagination=False):
        """Update the table widget with filtered results"""
        self.filtered_results = results  # Store the full filtered results
        
        if apply_pagination:
            # Calculate pagination
            total_items = len(results)
            self.total_pages = max(1, (total_items + self.items_per_page - 1) // self.items_per_page)
            self.current_page = min(self.current_page, self.total_pages)  # Ensure current page is valid
            
            # Apply pagination
            offset = (self.current_page - 1) * self.items_per_page
            paginated_results = results[offset:offset + self.items_per_page]
        else:
            # Show all results without pagination
            paginated_results = results
            self.total_pages = 1
            self.current_page = 1
        
        # Update the table
        self.table.setRowCount(len(paginated_results))
        
        for row_idx, record in enumerate(paginated_results):
            self._set_table_item(row_idx, 0, record.t_refno)
            self._set_table_item(row_idx, 1, record.t_date_endorsed.strftime("%Y-%m-%d"))
            self._set_table_item(row_idx, 2, record.t_category)
            self._set_table_item(row_idx, 3, record.t_prodcode)
            self._set_table_item(row_idx, 4, record.t_lot_number)
            self._set_table_item(row_idx, 5, f"{float(record.t_total_quantity):.2f}")
            self._set_table_item(row_idx, 6, record.t_status)
            self._set_table_item(row_idx, 7, record.t_endorsed_by)
            self._set_table_item(row_idx, 8, record.t_source_table)
            self._set_table_item(row_idx, 9, record.t_has_excess)
        
        # Update pagination controls
        self.update_pagination_controls()
        self.page_label.setText(f"Page {self.current_page} of {self.total_pages} ({len(results)} total matches)")

    def _set_table_item(self, row: int, col: int, value: str):
        """Helper method to set table items."""
        item = QTableWidgetItem(str(value))
        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.table.setItem(row, col, item)

    def on_row_double_click(self, index):
        """Emit signal when row is double-clicked."""
        ref_no = self.table.item(index.row(), 0).text()
        self.double_clicked.emit(ref_no)

    def show_context_menu(self, pos):
        # Get the clicked row
        row = self.table.rowAt(pos.y())

        if row < 0:  # Clicked outside a row
            return

        # EXTRACT SPECIFIC VALUES FROM THE ROW
        # the number should match the index based on the table layout
        ref_no = self.table.item(row, 0).text() if self.table.item(row, 0) else "N/A"
        product_code = self.table.item(row, 3).text() if self.table.item(row, 3) else "N/A"

        # Create the menu
        menu = QMenu(self)

        # Add actions
        edit_action = menu.addAction("Edit Record")
        # delete_action = menu.addAction("Delete Record")
        # add_action = menu.addAction("Add New Record")

        # Connect actions to functions
        # TODO: Add a dialog box before they edit anything
        edit_action.triggered.connect(lambda: print(f"Edit action triggered - Row: {row}, Ref No: {ref_no}, Product Code: {product_code}"))

        # Show the menu at the cursor position
        menu.exec(self.table.viewport().mapToGlobal(pos))
    
    def show_edit_confirmation_message(self):
        warehouse_password, ok = QInputDialog.getText(
            self,
            "Warehouse Authentication",
            "Enter warehouse password to modify this entry:",
            QLineEdit.EchoMode.Password
        )

        # TODO: CONTINUE THIS CODE ON MONDAY
        # REFERENCE: https://chatgpt.com/c/686878e2-1b0c-8003-971b-f06228f30ec9
        if ok:
            if warehouse_password == "test":
                pass

    def prev_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self.load_data()

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self.load_data()

    def update_pagination_controls(self):
        self.page_label.setText(f"Page {self.current_page} of {self.total_pages}")
        self.prev_btn.setEnabled(self.current_page > 1)
        self.next_btn.setEnabled(self.current_page < self.total_pages)

    def update_items_per_page(self):
        self.items_per_page = int(self.items_per_page_combo.currentText())
        self.current_page = 1 # Reset to first page when items per page changes
        self.load_data()