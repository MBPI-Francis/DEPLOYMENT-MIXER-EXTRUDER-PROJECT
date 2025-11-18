# app/views/extruder_form/records/view_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QLabel, QGridLayout, QVBoxLayout, QHBoxLayout, QGroupBox,
    QFormLayout, QTableWidget, QHeaderView, QTextBrowser, QPushButton, QTableWidgetItem, QScrollArea, QWidget
)
from PyQt6.QtCore import Qt
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, time, timedelta


class ExtruderRecordViewDialog(QDialog):
    """
    A resizable and scrollable dialog for viewing the complete details of a record.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("View Extruder Production Record")

        # --- THIS IS THE FIX (Part 1) ---
        # Set a good starting size and make the window resizable.
        self.resize(1400, 900)
        self.setSizeGripEnabled(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowMinMaxButtonsHint)
        # --- END FIX ---

        self._setup_ui()

    def _setup_ui(self):
        """
        --- THIS METHOD IS NOW UPDATED ---
        Creates the UI and wraps the main grid of group boxes in a QScrollArea.
        """
        # This is the main layout for the entire dialog window.
        main_layout = QVBoxLayout(self)

        # 1. Create the Scroll Area that will contain all the group boxes.
        scroll_area = QScrollArea()
        scroll_area.setObjectName("scroll_area")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # 2. Create a container widget that will hold the grid layout.
        scroll_content_widget = QWidget()
        scroll_content_widget.setObjectName("scroll_content_widget")
        # 3. Create the grid layout and set it on the container widget.
        grid_layout = QGridLayout(scroll_content_widget)

        # 4. Add all your group boxes to the grid layout, just as before.
        grid_layout.addWidget(self._create_production_details_group(), 0, 0)
        grid_layout.addWidget(self._create_machine_config_group(), 0, 1)
        grid_layout.addWidget(self._create_zones_group(), 0, 2)
        grid_layout.addWidget(self._create_output_log_group(), 1, 0, 2, 1)
        grid_layout.addWidget(self._create_purging_resin_group(), 1, 1, 1, 2)
        grid_layout.addWidget(self._create_remarks_personnel_group(), 2, 1)
        grid_layout.addWidget(self._create_summary_group(), 2, 2)

        # 5. Set the column stretches on the grid layout, just as before.
        grid_layout.setColumnStretch(0, 1)
        grid_layout.setColumnStretch(1, 1)
        grid_layout.setColumnStretch(2, 1)

        # 6. Place the container widget (with the grid on it) inside the scroll area.
        scroll_area.setWidget(scroll_content_widget)

        # 7. Add the scroll area to the dialog's main layout.
        main_layout.addWidget(scroll_area)

        # 8. Add the "Close" button at the bottom, outside the scroll area.
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)

    def _create_production_details_group(self):
        group = QGroupBox("Production Details")
        layout = QFormLayout(group)
        self.lot_number_label = QLabel()
        self.product_code_label = QLabel()
        self.customer_label = QLabel()
        self.qty_order_label = QLabel()
        self.qty_produced_label = QLabel()
        self.target_output_hr_label = QLabel()
        layout.addRow("Input Lot Number(s):", self.lot_number_label)
        layout.addRow("Product Code:", self.product_code_label)
        layout.addRow("Customer:", self.customer_label)
        layout.addRow("QTY. Order (kg):", self.qty_order_label)
        layout.addRow("Qty. Produced (kg):", self.qty_produced_label)
        layout.addRow("Target Output per Hour (Kg/Hr):", self.target_output_hr_label)
        return group

    def _create_machine_config_group(self):
        group = QGroupBox("Machine and Configuration")
        layout = QFormLayout(group)
        self.shift_label = QLabel()
        self.mc_no_label = QLabel()
        self.feed_rate_label = QLabel()
        self.rpm_label = QLabel()
        self.screen_size_label = QLabel()
        self.screw_config_label = QLabel()
        self.vacuum_on_label = QLabel()
        layout.addRow("Shift:", self.shift_label)
        layout.addRow("MC No.:", self.mc_no_label)
        layout.addRow("Feed Rate:", self.feed_rate_label)
        layout.addRow("RPM:", self.rpm_label)
        layout.addRow("Screen Size:", self.screen_size_label)
        layout.addRow("Screw Config.:", self.screw_config_label)
        layout.addRow("Vacuum ON:", self.vacuum_on_label)
        return group

    def _create_zones_group(self):
        group = QGroupBox("Extruder Zone Temperatures")
        layout = QGridLayout(group)
        self.zone_labels = {}
        zones = ["Z12", "Z11", "Z10", "Z9", "Z8", "Z7", "Z6", "Z5", "Z4", "Z3", "Z2", "Z1"]
        for i, name in enumerate(zones):
            row, col = divmod(i, 3)
            self.zone_labels[name] = QLabel("0")
            layout.addWidget(QLabel(name), row * 2, col)
            layout.addWidget(self.zone_labels[name], row * 2 + 1, col)
        return group

    def _create_output_log_group(self):
        group = QGroupBox("Extruder Output Log")
        layout = QVBoxLayout(group)
        self.output_log_table = QTableWidget(0, 5)
        self.output_log_table.setHorizontalHeaderLabels(["Date", "Time Start", "Time End", "Time Used", "Output (kg)"])
        self.output_log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.output_log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.output_log_table)
        return group

    def _create_purging_resin_group(self):
        group = QGroupBox("Purging and Resin Details")
        layout = QVBoxLayout(group)
        self.no_purging_label = QLabel()
        layout.addWidget(self.no_purging_label)
        h_layout = QHBoxLayout()
        purging_sub = QGroupBox("Purging")
        p_layout = QFormLayout(purging_sub)
        self.purging_prod_code_label = QLabel()
        self.purging_start_label = QLabel()
        self.purging_end_label = QLabel()
        self.purging_time_used_label = QLabel()
        self.purging_resin_label = QLabel()
        self.purging_palletizer_label = QLabel()
        self.purging_siever_label = QLabel()
        p_layout.addRow("Product Code:", self.purging_prod_code_label)
        p_layout.addRow("Start Time:", self.purging_start_label)
        p_layout.addRow("End Time:", self.purging_end_label)
        p_layout.addRow("Time Used (HH:mm):", self.purging_time_used_label)
        p_layout.addRow("Resin:", self.purging_resin_label)
        p_layout.addRow("Pelletizer:", self.purging_palletizer_label)
        p_layout.addRow("Siever:", self.purging_siever_label)
        resin_sub = QGroupBox("Resin Consumption")
        r_layout = QVBoxLayout(resin_sub)
        self.resin_table = QTableWidget(0, 3)
        self.resin_table.setHorizontalHeaderLabels(["Resin", "Qty (Kg.)", "Notes/Additives",])
        self.resin_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.resin_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        r_layout.addWidget(self.resin_table)
        h_layout.addWidget(purging_sub, 1)
        h_layout.addWidget(resin_sub, 1)
        layout.addLayout(h_layout)
        return group

    def _create_remarks_personnel_group(self):
        group = QGroupBox("Remarks and Personnel")
        layout = QVBoxLayout(group)
        layout.addWidget(QLabel("Remarks:"))
        self.remarks_browser = QTextBrowser()
        self.remarks_browser.setFixedHeight(80)
        layout.addWidget(self.remarks_browser)
        personnel_layout = QFormLayout()
        self.prepared_by_label = QLabel()
        personnel_layout.addRow("Prepared By:", self.prepared_by_label)
        self.personnel_layout = QVBoxLayout()
        personnel_layout.addRow("Personnel:", self.personnel_layout)
        layout.addLayout(personnel_layout)
        return group

    def _create_summary_group(self):
        group = QGroupBox("Production Summary")
        layout = QFormLayout(group)
        self.summary_total_output_label = QLabel()
        self.summary_total_time_label = QLabel()
        self.summary_output_per_hour_label = QLabel()
        self.summary_resin_qty_label = QLabel()
        self.summary_output_percent_label = QLabel()
        self.summary_gain_label = QLabel()
        self.summary_gain_percent_label = QLabel()
        self.summary_loss_label = QLabel()
        self.summary_loss_percent_label = QLabel()
        layout.addRow("Total Output (kg):", self.summary_total_output_label)
        layout.addRow("Total Time Used (HH:mm):", self.summary_total_time_label)
        layout.addRow("Output per Hour (kg/hr):", self.summary_output_per_hour_label)
        layout.addRow("Total Resin QTY (kg):", self.summary_resin_qty_label)
        layout.addRow("Output %:", self.summary_output_percent_label)
        layout.addRow("Gain (kg):", self.summary_gain_label)
        layout.addRow("Gain %:", self.summary_gain_percent_label)
        layout.addRow("Loss (kg):", self.summary_loss_label)
        layout.addRow("Loss %:", self.summary_loss_percent_label)
        return group

    def populate_data(self, record):
        """
        --- THIS METHOD IS NOW CORRECTED ---
        Safely fills the UI and explicitly clears fields when data is not present.
        """
        if not record: return

        def to_str(val, default="N/A"):
            return str(val) if val is not None else default

        def to_dec(val):
            return f"{val or 0:.2f}"

        # --- All calculation logic is correct and unchanged ---
        D = Decimal
        qty_produced = D(record.qty_produced or 0).quantize(D('0.01'), rounding=ROUND_HALF_UP)
        total_output = D(sum(out.qty_output for out in record.extruder_outputs if out.qty_output)).quantize(D('0.01'),
                                                                                                            rounding=ROUND_HALF_UP)
        total_resin_qty = D(0)
        for header in record.purging_headers: total_resin_qty += D(
            sum(detail.qty for detail in header.purging_details if detail.qty))
        total_resin_qty = total_resin_qty.quantize(D('0.01'), rounding=ROUND_HALF_UP)
        total_duration_seconds = sum(
            (out.datetime_end - out.datetime_start).total_seconds() for out in record.extruder_outputs if
            out.datetime_start and out.datetime_end and out.datetime_end > out.datetime_start)
        total_seconds_int = int(total_duration_seconds)
        hours, remainder = divmod(total_seconds_int, 3600);
        minutes, _ = divmod(remainder, 60)
        total_time_str = f"{hours:02}:{minutes:02}"
        total_hours = D(total_duration_seconds) / D(3600)
        output_per_hour = (total_output / total_hours) if total_hours > 0 else D(0)
        gain = max(D(0), total_output - qty_produced);
        loss = max(D(0), qty_produced - total_output)
        output_percent = (total_output / qty_produced * 100) if qty_produced > 0 else D(0)
        gain_percent = (gain / qty_produced * 100) if qty_produced > 0 else D(0)
        loss_percent = (loss / qty_produced * 100) if qty_produced > 0 else D(0)

        # --- Population of other sections is correct and unchanged ---
        self.lot_number_label.setText(to_str(record.lot_number));
        self.product_code_label.setText(to_str(record.product_code));
        self.customer_label.setText(to_str(record.customer))
        self.qty_order_label.setText(to_dec(record.qty_order));
        self.qty_produced_label.setText(to_dec(record.qty_produced))
        self.target_output_hr_label.setText(to_dec(getattr(record, 'target_output_per_hour', None)))
        self.shift_label.setText(to_str(getattr(record.shift, 'name', None)));
        self.mc_no_label.setText(to_str(getattr(record.machine, 'name', None)))
        if record.machine_details:
            self.feed_rate_label.setText(to_str(record.machine_details.feed_rate));
            self.rpm_label.setText(to_str(record.machine_details.rpm))
            self.screen_size_label.setText(to_str(getattr(record.machine_details.screen_size, 'size', None)))
            self.screw_config_label.setText(to_str(getattr(record.machine_details.screw_config, 'name', None)))
            self.vacuum_on_label.setText("Yes" if record.machine_details.is_vacuum_on else "No")
        for temp in record.machine_temps:
            if temp.zone and temp.zone.name in self.zone_labels: self.zone_labels[temp.zone.name].setText(
                to_str(temp.temp_value))
        self.output_log_table.setRowCount(0)
        for output in sorted(record.extruder_outputs, key=lambda x: (x.datetime_start is None, x.datetime_start)):
            row_pos = self.output_log_table.rowCount();
            self.output_log_table.insertRow(row_pos)
            date_str = output.datetime_start.strftime("%Y-%m-%d") if output.datetime_start else "N/A"
            start_str = output.datetime_start.strftime("%H:%M") if output.datetime_start else "N/A"
            end_str = output.datetime_end.strftime("%H:%M") if output.datetime_end else "N/A"
            time_used_str = "00:00"
            if output.datetime_start and output.datetime_end:
                duration = output.datetime_end - output.datetime_start;
                seconds = int(duration.total_seconds())
                hours, rem = divmod(seconds, 3600);
                minutes, _ = divmod(rem, 60)
                time_used_str = f"{hours:02}:{minutes:02}"
            self.output_log_table.setItem(row_pos, 0, QTableWidgetItem(date_str));
            self.output_log_table.setItem(row_pos, 1, QTableWidgetItem(start_str))
            self.output_log_table.setItem(row_pos, 2, QTableWidgetItem(end_str));
            self.output_log_table.setItem(row_pos, 3, QTableWidgetItem(time_used_str))
            self.output_log_table.setItem(row_pos, 4, QTableWidgetItem(to_dec(output.qty_output)))

        # --- THIS IS THE DEFINITIVE FIX ---
        if not record.purging_headers:
            self.no_purging_label.setText("<b>No Purging Done</b>");
            self.no_purging_label.setVisible(True)
            # Explicitly clear all the purging and resin fields
            self.purging_prod_code_label.setText("N/A")
            self.purging_start_label.setText("N/A")
            self.purging_end_label.setText("N/A")
            self.purging_time_used_label.setText("00:00")
            self.purging_resin_label.setText("N/A")
            self.purging_palletizer_label.setText("N/A")
            self.purging_siever_label.setText("N/A")
            self.resin_table.setRowCount(0)
        else:
            self.no_purging_label.setVisible(False)
            purging = record.purging_headers[0]
            self.purging_prod_code_label.setText(to_str(purging.product_code))
            self.purging_start_label.setText(purging.time_start.strftime("%H:%M") if purging.time_start else "N/A")
            self.purging_end_label.setText(purging.time_end.strftime("%H:%M") if purging.time_end else "N/A")
            purging_time_used_str = "00:00"
            if purging.time_start and purging.time_end:
                dummy_date = datetime.now().date()
                start_dt = datetime.combine(dummy_date, purging.time_start)
                end_dt = datetime.combine(dummy_date, purging.time_end)
                if end_dt < start_dt: end_dt += timedelta(days=1)
                duration = end_dt - start_dt;
                total_seconds = int(duration.total_seconds())
                hours, remainder = divmod(total_seconds, 3600);
                minutes, _ = divmod(remainder, 60)
                purging_time_used_str = f"{hours:02}:{minutes:02}"
            self.purging_time_used_label.setText(purging_time_used_str)
            self.purging_resin_label.setText(to_str(getattr(purging.resin_used, 'abbreviation', None)))
            self.purging_palletizer_label.setText(to_str(purging.palletizer_used))
            self.purging_siever_label.setText(to_str(purging.siever_used))
            self.resin_table.setRowCount(0)
            for detail in purging.purging_details:
                row = self.resin_table.rowCount();
                self.resin_table.insertRow(row)
                self.resin_table.setItem(row, 0, QTableWidgetItem(to_str(getattr(detail.resin, 'abbreviation', None))))
                self.resin_table.setItem(row, 1, QTableWidgetItem(to_dec(detail.qty)))
                self.resin_table.setItem(row, 2, QTableWidgetItem(to_str(detail.notes)))

        # --- END FIX ---

        self.remarks_browser.setText(to_str(record.remarks))
        self.prepared_by_label.setText(to_str(record.prepared_by))
        while self.personnel_layout.count():
            child = self.personnel_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        for p in record.extruder_personnels:
            emp = f"{p.employee.first_name} {p.employee.last_name}" if p.employee else "N/A"
            pos = p.position.name if p.position else "N/A"
            self.personnel_layout.addWidget(QLabel(f"- {emp} ({pos})"))
        self.summary_total_output_label.setText(f"{total_output:.2f} kg")
        self.summary_total_time_label.setText(total_time_str)
        self.summary_output_per_hour_label.setText(f"{output_per_hour:.2f} kg/hr")
        self.summary_resin_qty_label.setText(f"{total_resin_qty:.2f} kg")
        self.summary_output_percent_label.setText(f"{output_percent:.2f} %")
        self.summary_gain_label.setText(f"{gain:.2f} kg")
        self.summary_gain_percent_label.setText(f"{gain_percent:.2f} %")
        self.summary_loss_label.setText(f"{loss:.2f} kg")
        self.summary_loss_percent_label.setText(f"{loss_percent:.2f} %")