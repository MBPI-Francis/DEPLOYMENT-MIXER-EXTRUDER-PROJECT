# app/views/extruder_form/records/exporter.py
import os

import openpyxl
from datetime import datetime, timedelta
from decimal import Decimal


class ExcelReportExporter:
    """

    Handles populating the extruder report Excel template with data
    from a single, fully-loaded ExtruderFormData record.
    """

    def __init__(self, record_object):
        self.record = record_object

        # --- THIS IS THE DEFINITIVE FIX FOR FileNotFoundError ---
        # 1. Get the directory where THIS exporter.py file is located.
        current_dir = os.path.dirname(os.path.abspath(__file__))

        # 2. Construct a full, absolute path to the template file.
        template_path = os.path.join(current_dir, "extruder_report_format.xlsx")

        # 3. Load the workbook using the absolute path.
        self.workbook = openpyxl.load_workbook(template_path)
        # --- END FIX ---

        self.sheet = self.workbook.active

    def generate_report(self, output_path: str):
        """
        Main method to fill all sections of the report and save the file.
        """
        self._fill_header_info()
        self._fill_summary_and_calculations()
        self._fill_output_log()
        self._fill_materials_and_lots()
        self._fill_purging_info()
        self._fill_footer_info()

        self.workbook.save(output_path)

    def _fill_header_info(self):
        # Requirement a: F5
        machine_name = getattr(self.record.machine, 'name', 'N/A')
        self.sheet['F5'] = f"Extruder Machine No. {machine_name}"

    def _fill_summary_and_calculations(self):
        # Requirement b, c, d, e, f
        self.sheet['A8'] = getattr(self.record.machine, 'name', 'N/A')
        self.sheet['B8'] = self.record.qty_order
        self.sheet['C8'] = self.record.customer
        self.sheet['F8'] = self.record.product_code
        self.sheet['G9'] = self.record.qty_produced

        # Calculations for g, h, i, j, k, l, m, n
        total_output = sum(out.qty_output for out in self.record.extruder_outputs if out.qty_output)
        total_seconds = sum(
            (out.datetime_end - out.datetime_start).total_seconds() for out in self.record.extruder_outputs
            if out.datetime_start and out.datetime_end and out.datetime_end > out.datetime_start
        )
        total_hours_decimal = Decimal(total_seconds) / Decimal(3600)

        # g. Total time used in decimal
        self.sheet['H9'] = float(total_hours_decimal.quantize(Decimal('0.01')))

        # h. Output per hour
        output_per_hour = (Decimal(total_output) / total_hours_decimal) if total_hours_decimal > 0 else Decimal(0)
        self.sheet['I9'] = float(output_per_hour.quantize(Decimal('0.01')))

        # i. Target Output
        self.sheet['J9'] = self.record.target_output_per_hour

        # j. Total Output
        self.sheet['K9'] = total_output

        # k, l, m, n: Loss, Gain, and Percentages
        qty_produced_dec = Decimal(self.record.qty_produced or 0)
        loss = max(Decimal(0), qty_produced_dec - Decimal(total_output))
        denominator = Decimal(total_output) + loss

        output_percentage = (Decimal(total_output) / denominator * 100) if denominator > 0 else Decimal(0)
        loss_percentage = (loss / denominator * 100) if denominator > 0 else Decimal(0)

        self.sheet['L9'] = f"{output_percentage:.2f}%"
        self.sheet['M9'] = loss
        self.sheet['N9'] = f"{loss_percentage:.2f}%"

    def _fill_output_log(self):
        # Requirements n, o, p, q, r
        sorted_outputs = sorted(self.record.extruder_outputs,
                                key=lambda x: (x.datetime_start is None, x.datetime_start))

        total_duration = timedelta()

        for i, output in enumerate(sorted_outputs[:13]):  # Limit to 13 rows (A12-A24)
            row = 12 + i
            # --- THIS IS THE FIX ---
            # Use the format string "%d-%b-%Y %H:%M"
            if output.datetime_start:
                self.sheet[f'A{row}'] = output.datetime_start.strftime("%d-%b-%Y %H:%M")
            if output.datetime_end:
                self.sheet[f'D{row}'] = output.datetime_end.strftime("%d-%b-%Y %H:%M")
            # --- END FIX ---

            duration = timedelta()
            if output.datetime_start and output.datetime_end:
                duration = output.datetime_end - output.datetime_start
                total_duration += duration
                # Format as hh:mm
                hours, rem = divmod(duration.total_seconds(), 3600)
                minutes, _ = divmod(rem, 60)
                self.sheet[f'F{row}'] = f"{int(hours):02d}:{int(minutes):02d}"

            self.sheet[f'G{row}'] = output.qty_output

        # Requirement r: Total time used in hh:mm:ss format
        total_seconds = int(total_duration.total_seconds())
        hours, rem = divmod(total_seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        self.sheet['F25'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _fill_materials_and_lots(self):
        # Requirements s, t, u, v, w
        # This assumes we need to fetch material data based on production_id, similar to the entry form.
        # For simplicity, this part is left as a placeholder. You would need to add a controller method
        # to fetch materials based on the `record.production_id`.

        # Requirement w: Lot Numbers
        if self.record.lot_number:
            lot_numbers = [lot.strip() for lot in self.record.lot_number.split(';')]
            for i, lot in enumerate(lot_numbers[:13]):  # Limit to 13 rows
                row = 12 + i
                self.sheet[f'M{row}'] = lot

    def _fill_purging_info(self):
        # Requirements x, y, z, aa, bb, cc, dd, ee
        if not self.record.purging_headers:
            return

        header = self.record.purging_headers[0]
        self.sheet['B26'] = header.product_code

        # Format Start - End time
        start_str = header.time_start.strftime("%H:%M") if header.time_start else ""
        end_str = header.time_end.strftime("%H:%M") if header.time_end else ""
        self.sheet['B27'] = f"{start_str} – {end_str}"

        # Duration
        if header.time_start and header.time_end:
            dummy_date = datetime.now().date()
            start_dt = datetime.combine(dummy_date, header.time_start)
            end_dt = datetime.combine(dummy_date, header.time_end)
            if end_dt < start_dt: end_dt += timedelta(days=1)
            duration = end_dt - start_dt
            total_seconds = int(duration.total_seconds())
            hours, rem = divmod(total_seconds, 3600)
            minutes, _ = divmod(rem, 60)
            self.sheet['E27'] = f"{int(hours):02d}:{int(minutes):02d}"

        # Resin details
        resin_details_str = ", ".join([
            f"{getattr(d.resin, 'abbreviation', 'N/A')} = {d.qty}"
            for d in header.purging_details
        ])
        self.sheet['B28'] = resin_details_str

        self.sheet['B29'] = header.siever_used
        self.sheet['B30'] = header.palletizer_used

    def _fill_footer_info(self):
        # Requirements ff, gg, hh
        self.sheet['G26'] = self.record.remarks

        operators = []
        supervisors = []

        for p in self.record.extruder_personnels:
            if not p.employee or not p.position: continue

            full_name = f"{p.employee.first_name} {p.employee.last_name}"

            if "supervisor" in p.position.name.lower():
                supervisors.append(full_name)
            elif "operator" in p.position.name.lower():
                operators.append(full_name)
            elif "reliever" in p.position.name.lower():
                operators.append(f"{full_name} (Reliever)")

        self.sheet['M28'] = ", ".join(operators)
        self.sheet['M29'] = ", ".join(supervisors)