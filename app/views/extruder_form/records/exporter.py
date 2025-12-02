# # app/views/extruder_form/records/exporter.py
#
# import os
# import openpyxl
# from datetime import datetime, timedelta
# from decimal import Decimal
#
# from openpyxl.styles import Border, Side, Alignment
# from openpyxl.worksheet.worksheet import Worksheet
#
# from .ops import ExtruderRecordsOperations
#
#
# class ExcelReportExporter:
#     """
#     Handles populating the extruder report Excel template.
#     Can be used for a single report or as a helper for bulk exports.
#     """
#     TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extruder_report_format.xlsx")
#     REPORT_TOTAL_ROWS = 31
#
#     def __init__(self, ops_controller: ExtruderRecordsOperations):
#         self.controller = ops_controller
#
#     def generate_single_report(self, record_object, output_path: str):
#         """Creates and saves a report for a single record to a new file."""
#         workbook = openpyxl.load_workbook(self.TEMPLATE_PATH)
#         sheet = workbook.active
#         # For single reports, we never overwrite the formulas.
#         self.populate_sheet(sheet, record_object, overwrite_formulas=False)
#         workbook.save(output_path)
#
#     def populate_sheet(self, sheet: Worksheet, record_object, row_offset: int = 0, overwrite_formulas: bool = False):
#         """
#         Fills a given worksheet with data, optionally overwriting formula cells
#         with static values for bulk reports.
#         """
#         self._fill_header_info(sheet, record_object, row_offset)
#         self._fill_summary_and_calculations(sheet, record_object, row_offset)
#         self._fill_output_log(sheet, record_object, row_offset, overwrite_formulas)
#         self._fill_materials_and_lots(sheet, record_object, row_offset, overwrite_formulas)
#         self._fill_purging_info(sheet, record_object, row_offset)
#         self._fill_footer_info(sheet, record_object, row_offset)
#
#     def _fill_header_info(self, sheet, record, row_offset):
#         machine_name = getattr(record.machine, 'name', 'N/A')
#         sheet[f'F{5 + row_offset}'].value = f"Extruder Machine No. {machine_name}"
#
#     def _fill_summary_and_calculations(self, sheet, record, row_offset):
#         sheet[f'A{8 + row_offset}'].value = getattr(record.machine, 'name', 'N/A')
#         sheet[f'B{8 + row_offset}'].value = record.qty_order
#         sheet[f'C{8 + row_offset}'].value = record.customer
#         sheet[f'F{8 + row_offset}'].value = record.product_code
#         sheet[f'G{9 + row_offset}'].value = record.qty_produced
#
#         total_output = sum(out.qty_output for out in record.extruder_outputs if out.qty_output)
#         total_seconds = sum(
#             (out.datetime_end - out.datetime_start).total_seconds()
#             for out in record.extruder_outputs
#             if out.datetime_start and out.datetime_end and out.datetime_end > out.datetime_start
#         )
#         total_hours_decimal = Decimal(total_seconds) / Decimal(3600)
#
#         sheet[f'H{9 + row_offset}'].value = float(total_hours_decimal.quantize(Decimal('0.01')))
#         output_per_hour = (Decimal(total_output) / total_hours_decimal) if total_hours_decimal > 0 else Decimal(0)
#         sheet[f'I{9 + row_offset}'].value = float(output_per_hour.quantize(Decimal('0.01')))
#         sheet[f'J{9 + row_offset}'].value = float(record.target_output_per_hour or 0)
#         sheet[f'K{9 + row_offset}'].value = total_output
#
#         qty_produced_dec = Decimal(record.qty_produced or 0)
#         loss = max(Decimal(0), qty_produced_dec - Decimal(total_output))
#         denominator = Decimal(total_output) + loss
#         output_percentage = (Decimal(total_output) / denominator * 100) if denominator > 0 else Decimal(0)
#         loss_percentage = (loss / denominator * 100) if denominator > 0 else Decimal(0)
#
#         sheet[f'L{9 + row_offset}'].value = f"{output_percentage:.2f}%"
#         sheet[f'M{9 + row_offset}'].value = loss
#         sheet[f'N{9 + row_offset}'].value = f"{loss_percentage:.2f}%"
#
#     def _fill_output_log(self, sheet, record, row_offset, overwrite_formulas):
#         sorted_outputs = sorted(record.extruder_outputs, key=lambda x: (x.datetime_start is None, x.datetime_start))
#         total_duration = timedelta()
#         for i, output in enumerate(sorted_outputs[:13]):
#             row = 12 + i + row_offset
#             if output.datetime_start:
#                 sheet[f'A{row}'].value = output.datetime_start.strftime("%d-%b-%Y %H:%M")
#             if output.datetime_end:
#                 sheet[f'D{row}'].value = output.datetime_end.strftime("%d-%b-%Y %H:%M")
#
#             duration = timedelta()
#             if output.datetime_start and output.datetime_end:
#                 duration = output.datetime_end - output.datetime_start
#                 total_duration += duration
#                 hours, rem = divmod(duration.total_seconds(), 3600)
#                 minutes, _ = divmod(rem, 60)
#                 sheet[f'F{row}'].value = f"{int(hours):02d}:{int(minutes):02d}"
#
#             output_cell = sheet[f'G{row}']
#             output_cell.value = float(output.qty_output or 0)
#             output_cell.number_format = '0.00'
#
#         # --- THIS IS THE FIX (Part 1) ---
#         # Only overwrite the total if the flag is True
#         if overwrite_formulas:
#             total_output = sum(float(o.qty_output or 0) for o in record.extruder_outputs)
#             total_output_cell = sheet[f'G{25 + row_offset}']
#             total_output_cell.value = total_output
#             total_output_cell.number_format = '0.00'
#         # --- END FIX ---
#
#         total_seconds = int(total_duration.total_seconds())
#         hours, rem = divmod(total_seconds, 3600)
#         minutes, seconds = divmod(rem, 60)
#         sheet[f'F{25 + row_offset}'].value = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
#
#     def _fill_materials_and_lots(self, sheet, record, row_offset, overwrite_formulas):
#         start_row = 12 + row_offset
#         valid_materials = []
#
#         if record.production_id:
#             prod_ids = [pid.strip() for pid in record.production_id.split(';') if pid.strip()]
#             if prod_ids:
#                 aggregated_materials = self.controller.get_aggregated_materials_for_production_ids(prod_ids)
#                 valid_materials = [
#                     (mat_code, total_qty)
#                     for mat_code, total_qty in aggregated_materials
#                     if mat_code and mat_code.strip() and total_qty > 0
#                 ]
#                 for i, (mat_code, total_qty) in enumerate(valid_materials[:13]):
#                     current_row = start_row + i
#                     mat_cell = sheet[f'I{current_row}']
#                     mat_cell.value = mat_code
#                     mat_cell.alignment = Alignment(horizontal='left', vertical='center')
#
#                     qty_cell = sheet[f'K{current_row}']
#                     qty_cell.value = float(total_qty)
#                     qty_cell.alignment = Alignment(horizontal='right', vertical='center')
#                     qty_cell.number_format = '0.00'
#
#         # --- THIS IS THE FIX (Part 2) ---
#         # Only overwrite the total if the flag is True
#         if overwrite_formulas:
#             total_input_qty = sum(float(total_qty) for _, total_qty in valid_materials)
#             total_input_cell = sheet[f'K{25 + row_offset}']
#             total_input_cell.value = total_input_qty
#             total_input_cell.number_format = '0.00'
#         # --- END FIX ---
#
#         if record.lot_number:
#             lot_numbers = [lot.strip() for lot in record.lot_number.split(';')]
#             if lot_numbers:
#                 lot_quantities_map = self.controller.get_produced_quantities_for_lots(lot_numbers)
#                 for i, lot in enumerate(lot_numbers[:13]):
#                     row = start_row + i
#                     sheet[f'M{row}'].value = lot
#                     qty_prod = lot_quantities_map.get(lot, Decimal('0.00'))
#                     qty_cell = sheet[f'N{row}']
#                     qty_cell.value = float(qty_prod or 0)
#                     qty_cell.alignment = Alignment(horizontal='right', vertical='center')
#                     qty_cell.number_format = '0.00'
#
#     def _fill_purging_info(self, sheet, record, row_offset):
#         if not record.purging_headers:
#             return
#         header = record.purging_headers[0]
#         sheet[f'B{26 + row_offset}'].value = header.product_code
#         start_str = header.time_start.strftime("%H:%M") if header.time_start else ""
#         end_str = header.time_end.strftime("%H:%M") if header.time_end else ""
#         sheet[f'B{27 + row_offset}'].value = f"{start_str} – {end_str}"
#
#         if header.time_start and header.time_end:
#             dummy_date = datetime.now().date()
#             start_dt = datetime.combine(dummy_date, header.time_start)
#             end_dt = datetime.combine(dummy_date, header.time_end)
#             if end_dt < start_dt: end_dt += timedelta(days=1)
#             duration = end_dt - start_dt
#             total_seconds = int(duration.total_seconds())
#             hours, rem = divmod(total_seconds, 3600)
#             minutes, _ = divmod(rem, 60)
#             sheet[f'E{27 + row_offset}'].value = f"{int(hours):02d}:{int(minutes):02d}"
#
#         resin_details_str = ", ".join(
#             [f"{getattr(d.resin, 'abbreviation', 'N/A')} = {d.qty}" for d in header.purging_details]
#         )
#         sheet[f'B{28 + row_offset}'].value = resin_details_str
#         sheet[f'B{29 + row_offset}'].value = header.siever_used
#         sheet[f'B{30 + row_offset}'].value = header.palletizer_used
#
#     def _fill_footer_info(self, sheet, record, row_offset):
#         remarks_text = record.remarks or ""
#         if record.machine_details and record.machine_details.is_vacuum_on:
#             if remarks_text:
#                 remarks_text = f"VACUUM ON\n{remarks_text}"
#             else:
#                 remarks_text = "VACUUM ON"
#         sheet[f'G{26 + row_offset}'].value = remarks_text
#
#         operators, supervisors = [], []
#         for p in record.extruder_personnels:
#             if not p.employee or not p.position: continue
#             full_name = f"{p.employee.first_name} {p.employee.last_name}"
#             pos_name = p.position.name.lower()
#             if "supervisor" in pos_name:
#                 supervisors.append(full_name)
#             elif "operator" in pos_name:
#                 operators.append(full_name)
#             elif "reliever" in pos_name:
#                 operators.append(f"{full_name} (Reliever)")
#
#         operators_text = ", ".join(operators) if operators else "N/A"
#         sheet[f'M{28 + row_offset}'].value = operators_text
#         supervisors_text = ", ".join(supervisors) if supervisors else "N/A"
#         sheet[f'M{29 + row_offset}'].value = supervisors_text


# app/views/extruder_form/records/exporter.py

import os
import openpyxl
from datetime import datetime, timedelta
from decimal import Decimal

from openpyxl.styles import Border, Side, Alignment
from openpyxl.worksheet.worksheet import Worksheet

from .ops import ExtruderRecordsOperations


class ExcelReportExporter:
    """
    Handles populating the extruder report Excel template.
    Can be used for a single report or as a helper for bulk exports.
    """
    TEMPLATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "extruder_report_format.xlsx")
    REPORT_TOTAL_ROWS = 31

    def __init__(self, ops_controller: ExtruderRecordsOperations):
        self.controller = ops_controller

    def generate_single_report(self, record_object, output_path: str):
        """Creates and saves a report for a single record to a new file."""
        workbook = openpyxl.load_workbook(self.TEMPLATE_PATH)
        sheet = workbook.active
        self.populate_sheet(sheet, record_object, overwrite_formulas=False)
        workbook.save(output_path)

    def populate_sheet(self, sheet: Worksheet, record_object, row_offset: int = 0, overwrite_formulas: bool = False):
        """
        Fills a given worksheet with data, optionally overwriting formula cells
        with static values for bulk reports.
        """
        self._fill_header_info(sheet, record_object, row_offset)
        self._fill_summary_and_calculations(sheet, record_object, row_offset)
        self._fill_output_log(sheet, record_object, row_offset, overwrite_formulas)
        self._fill_materials_and_lots(sheet, record_object, row_offset, overwrite_formulas)
        self._fill_purging_info(sheet, record_object, row_offset)
        self._fill_footer_info(sheet, record_object, row_offset)

    def _fill_header_info(self, sheet, record, row_offset):
        machine_name = getattr(record.machine, 'name', 'N/A')
        sheet[f'F{5 + row_offset}'].value = f"Extruder Machine No. {machine_name}"

    def _fill_summary_and_calculations(self, sheet, record, row_offset):
        sheet[f'A{8 + row_offset}'].value = getattr(record.machine, 'name', 'N/A')
        sheet[f'B{8 + row_offset}'].value = record.qty_order
        sheet[f'C{8 + row_offset}'].value = record.customer
        sheet[f'F{8 + row_offset}'].value = record.product_code
        sheet[f'G{9 + row_offset}'].value = record.qty_produced

        total_output = sum(out.qty_output for out in record.extruder_outputs if out.qty_output)
        total_seconds = sum(
            (out.datetime_end - out.datetime_start).total_seconds()
            for out in record.extruder_outputs
            if out.datetime_start and out.datetime_end and out.datetime_end > out.datetime_start
        )
        total_hours_decimal = Decimal(total_seconds) / Decimal(3600)

        sheet[f'H{9 + row_offset}'].value = float(total_hours_decimal.quantize(Decimal('0.01')))
        output_per_hour = (Decimal(total_output) / total_hours_decimal) if total_hours_decimal > 0 else Decimal(0)
        sheet[f'I{9 + row_offset}'].value = float(output_per_hour.quantize(Decimal('0.01')))
        sheet[f'J{9 + row_offset}'].value = float(record.target_output_per_hour or 0)
        sheet[f'K{9 + row_offset}'].value = total_output

        qty_produced_dec = Decimal(record.qty_produced or 0)
        loss = max(Decimal(0), qty_produced_dec - Decimal(total_output))
        denominator = Decimal(total_output) + loss
        output_percentage = (Decimal(total_output) / denominator * 100) if denominator > 0 else Decimal(0)
        loss_percentage = (loss / denominator * 100) if denominator > 0 else Decimal(0)

        sheet[f'L{9 + row_offset}'].value = f"{output_percentage:.2f}%"
        sheet[f'M{9 + row_offset}'].value = loss
        sheet[f'N{9 + row_offset}'].value = f"{loss_percentage:.2f}%"

    def _fill_output_log(self, sheet, record, row_offset, overwrite_formulas):
        sorted_outputs = sorted(record.extruder_outputs, key=lambda x: (x.datetime_start is None, x.datetime_start))
        total_duration = timedelta()
        for i, output in enumerate(sorted_outputs[:13]):
            row = 12 + i + row_offset
            if output.datetime_start:
                sheet[f'A{row}'].value = output.datetime_start.strftime("%d-%b-%Y %H:%M")
            if output.datetime_end:
                sheet[f'D{row}'].value = output.datetime_end.strftime("%d-%b-%Y %H:%M")

            duration = timedelta()
            if output.datetime_start and output.datetime_end:
                duration = output.datetime_end - output.datetime_start
                total_duration += duration
                hours, rem = divmod(duration.total_seconds(), 3600)
                minutes, _ = divmod(rem, 60)
                sheet[f'F{row}'].value = f"{int(hours):02d}:{int(minutes):02d}"

            output_cell = sheet[f'G{row}']
            output_cell.value = float(output.qty_output or 0)
            output_cell.number_format = '0.00'

        if overwrite_formulas:
            total_output = sum(float(o.qty_output or 0) for o in record.extruder_outputs)
            total_output_cell = sheet[f'G{25 + row_offset}']
            total_output_cell.value = total_output
            total_output_cell.number_format = '0.00'

        total_seconds = int(total_duration.total_seconds())
        hours, rem = divmod(total_seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        sheet[f'F{25 + row_offset}'].value = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _fill_materials_and_lots(self, sheet, record, row_offset, overwrite_formulas):
        start_row = 12 + row_offset
        valid_materials = []
        total_lot_qty_prod = 0.0  # Initialize accumulator for N column total

        if record.production_id:
            prod_ids = [pid.strip() for pid in record.production_id.split(';') if pid.strip()]
            if prod_ids:
                aggregated_materials = self.controller.get_aggregated_materials_for_production_ids(prod_ids)
                valid_materials = [
                    (mat_code, total_qty)
                    for mat_code, total_qty in aggregated_materials
                    if mat_code and mat_code.strip() and total_qty > 0
                ]
                for i, (mat_code, total_qty) in enumerate(valid_materials[:13]):
                    current_row = start_row + i
                    mat_cell = sheet[f'I{current_row}']
                    mat_cell.value = mat_code
                    mat_cell.alignment = Alignment(horizontal='left', vertical='center')

                    qty_cell = sheet[f'K{current_row}']
                    qty_cell.value = float(total_qty)
                    qty_cell.alignment = Alignment(horizontal='right', vertical='center')
                    qty_cell.number_format = '0.00'

        if record.lot_number:
            lot_numbers = [lot.strip() for lot in record.lot_number.split(';')]
            if lot_numbers:
                lot_quantities_map = self.controller.get_produced_quantities_for_lots(lot_numbers)
                for i, lot in enumerate(lot_numbers[:13]):
                    row = start_row + i
                    sheet[f'M{row}'].value = lot

                    qty_prod = lot_quantities_map.get(lot, Decimal('0.00'))
                    qty_prod_float = float(qty_prod or 0)
                    total_lot_qty_prod += qty_prod_float  # Add to our running total

                    qty_cell = sheet[f'N{row}']
                    qty_cell.value = qty_prod_float
                    qty_cell.alignment = Alignment(horizontal='right', vertical='center')
                    qty_cell.number_format = '0.00'

        if overwrite_formulas:
            # Handle K25 Total Input
            total_input_qty = sum(float(total_qty) for _, total_qty in valid_materials)
            total_input_cell = sheet[f'K{25 + row_offset}']
            total_input_cell.value = total_input_qty
            total_input_cell.number_format = '0.00'

            # --- THIS IS THE FIX ---
            # Handle N25 Total Produced from Lots
            total_lot_qty_cell = sheet[f'N{25 + row_offset}']
            total_lot_qty_cell.value = total_lot_qty_prod
            total_lot_qty_cell.number_format = '0.00'
            total_lot_qty_cell.alignment = Alignment(horizontal='right', vertical='center')
            # --- END FIX ---

    def _fill_purging_info(self, sheet, record, row_offset):
        if not record.purging_headers:
            return
        header = record.purging_headers[0]
        sheet[f'B{26 + row_offset}'].value = header.product_code
        start_str = header.time_start.strftime("%H:%M") if header.time_start else ""
        end_str = header.time_end.strftime("%H:%M") if header.time_end else ""
        sheet[f'B{27 + row_offset}'].value = f"{start_str} – {end_str}"

        if header.time_start and header.time_end:
            dummy_date = datetime.now().date()
            start_dt = datetime.combine(dummy_date, header.time_start)
            end_dt = datetime.combine(dummy_date, header.time_end)
            if end_dt < start_dt: end_dt += timedelta(days=1)
            duration = end_dt - start_dt
            total_seconds = int(duration.total_seconds())
            hours, rem = divmod(total_seconds, 3600)
            minutes, _ = divmod(rem, 60)
            sheet[f'E{27 + row_offset}'].value = f"{int(hours):02d}:{int(minutes):02d}"

        resin_details_str = ", ".join(
            [f"{getattr(d.resin, 'abbreviation', 'N/A')} = {d.qty}" for d in header.purging_details]
        )
        sheet[f'B{28 + row_offset}'].value = resin_details_str
        sheet[f'B{29 + row_offset}'].value = header.siever_used
        sheet[f'B{30 + row_offset}'].value = header.palletizer_used

    def _fill_footer_info(self, sheet, record, row_offset):
        remarks_text = record.remarks or ""
        if record.machine_details and record.machine_details.is_vacuum_on:
            if remarks_text:
                remarks_text = f"VACUUM ON\n{remarks_text}"
            else:
                remarks_text = "VACUUM ON"
        sheet[f'G{26 + row_offset}'].value = remarks_text

        operators, supervisors = [], []
        for p in record.extruder_personnels:
            if not p.employee or not p.position: continue
            full_name = f"{p.employee.first_name} {p.employee.last_name}"
            pos_name = p.position.name.lower()
            if "supervisor" in pos_name:
                supervisors.append(full_name)
            elif "operator" in pos_name:
                operators.append(full_name)
            elif "reliever" in pos_name:
                operators.append(f"{full_name} (Reliever)")

        operators_text = ", ".join(operators) if operators else "N/A"
        sheet[f'M{28 + row_offset}'].value = operators_text
        supervisors_text = ", ".join(supervisors) if supervisors else "N/A"
        sheet[f'M{29 + row_offset}'].value = supervisors_text