# # app/views/extruder_form/records/exporter.py
# import os
# import openpyxl
# from datetime import datetime, timedelta
# from decimal import Decimal
#
# # --- NEW: Import Border and Side for styling ---
# from openpyxl.styles import Border, Side
#
# # Import the operations controller for data fetching
# from .ops import ExtruderRecordsOperations
#
#
# class ExcelReportExporter:
#     """
#     Handles populating the extruder report Excel template with data
#     from a single, fully-loaded ExtruderFormData record.
#     """
#
#     def __init__(self, record_object, ops_controller: ExtruderRecordsOperations):
#         self.record = record_object
#         self.controller = ops_controller  # Store the controller instance
#
#         current_dir = os.path.dirname(os.path.abspath(__file__))
#         template_path = os.path.join(current_dir, "extruder_report_format.xlsx")
#         self.workbook = openpyxl.load_workbook(template_path)
#         self.sheet = self.workbook.active
#
#     def generate_report(self, output_path: str):
#         """
#         Main method to fill all sections of the report and save the file.
#         """
#         self._fill_header_info()
#         self._fill_summary_and_calculations()
#         self._fill_output_log()
#         self._fill_materials_and_lots()
#         self._fill_purging_info()
#         self._fill_footer_info()
#
#         self.workbook.save(output_path)
#
#     def _fill_header_info(self):
#         machine_name = getattr(self.record.machine, 'name', 'N/A')
#         self.sheet['F5'] = f"Extruder Machine No. {machine_name}"
#
#     def _fill_summary_and_calculations(self):
#         self.sheet['A8'] = getattr(self.record.machine, 'name', 'N/A')
#         self.sheet['B8'] = self.record.qty_order
#         self.sheet['C8'] = self.record.customer
#         self.sheet['F8'] = self.record.product_code
#         self.sheet['G9'] = self.record.qty_produced
#
#         total_output = sum(out.qty_output for out in self.record.extruder_outputs if out.qty_output)
#         total_seconds = sum(
#             (out.datetime_end - out.datetime_start).total_seconds() for out in self.record.extruder_outputs
#             if out.datetime_start and out.datetime_end and out.datetime_end > out.datetime_start
#         )
#         total_hours_decimal = Decimal(total_seconds) / Decimal(3600)
#
#         self.sheet['H9'] = float(total_hours_decimal.quantize(Decimal('0.01')))
#         output_per_hour = (Decimal(total_output) / total_hours_decimal) if total_hours_decimal > 0 else Decimal(0)
#         self.sheet['I9'] = float(output_per_hour.quantize(Decimal('0.01')))
#         self.sheet['J9'] = float(self.record.target_output_per_hour or 0)
#         self.sheet['K9'] = total_output
#
#         qty_produced_dec = Decimal(self.record.qty_produced or 0)
#         loss = max(Decimal(0), qty_produced_dec - Decimal(total_output))
#         denominator = Decimal(total_output) + loss
#         output_percentage = (Decimal(total_output) / denominator * 100) if denominator > 0 else Decimal(0)
#         loss_percentage = (loss / denominator * 100) if denominator > 0 else Decimal(0)
#
#         self.sheet['L9'] = f"{output_percentage:.2f}%"
#         self.sheet['M9'] = loss
#         self.sheet['N9'] = f"{loss_percentage:.2f}%"
#
#     def _fill_output_log(self):
#         sorted_outputs = sorted(self.record.extruder_outputs,
#                                 key=lambda x: (x.datetime_start is None, x.datetime_start))
#         total_duration = timedelta()
#         for i, output in enumerate(sorted_outputs[:13]):
#             row = 12 + i
#             if output.datetime_start:
#                 self.sheet[f'A{row}'] = output.datetime_start.strftime("%d-%b-%Y %H:%M")
#             if output.datetime_end:
#                 self.sheet[f'D{row}'] = output.datetime_end.strftime("%d-%b-%Y %H:%M")
#             duration = timedelta()
#             if output.datetime_start and output.datetime_end:
#                 duration = output.datetime_end - output.datetime_start
#                 total_duration += duration
#                 hours, rem = divmod(duration.total_seconds(), 3600)
#                 minutes, _ = divmod(rem, 60)
#                 self.sheet[f'F{row}'] = f"{int(hours):02d}:{int(minutes):02d}"
#             self.sheet[f'G{row}'] = output.qty_output
#
#         total_seconds = int(total_duration.total_seconds())
#         hours, rem = divmod(total_seconds, 3600)
#         minutes, seconds = divmod(rem, 60)
#         self.sheet['F25'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
#
#     def _fill_materials_and_lots(self):
#         """
#         Unmerges the target cell ranges, restores the necessary border,
#         and then populates the material data row by row.
#         """
#         start_row = 12
#         end_row = 24
#         material_name_col_letter = 'I'
#         material_qty_col_letter = 'K'
#
#         merged_to_remove = []
#         for merged_range in self.sheet.merged_cells.ranges:
#             if merged_range.min_row <= end_row and merged_range.max_row >= start_row:
#                 if merged_range.min_col <= 11 and merged_range.max_col >= 9:
#                     merged_to_remove.append(str(merged_range))
#
#         for merged_ref in merged_to_remove:
#             self.sheet.unmerge_cells(merged_ref)
#
#         # --- FIX: Restore the top border of cell J12 ---
#         # 1. Define the solid border style. 'thin' is the standard solid line.
#         solid_thin_side = Side(style='thin')
#
#         # 2. Get the cell you want to modify.
#         cell_j12 = self.sheet['J12']
#
#         # 3. Create a new Border object, applying the style ONLY to the top.
#         #    This preserves any other existing borders on the cell.
#         cell_j12.border = Border(top=solid_thin_side,
#                                  left=cell_j12.border.left,
#                                  right=cell_j12.border.right,
#                                  bottom=cell_j12.border.bottom)
#         # --- END FIX ---
#
#         if self.record.production_id:
#             prod_ids = [pid.strip() for pid in self.record.production_id.split(';') if pid.strip()]
#             if prod_ids:
#                 aggregated_materials = self.controller.get_aggregated_materials_for_production_ids(prod_ids)
#                 for i, (mat_code, total_qty) in enumerate(aggregated_materials[:13]):
#                     current_row = start_row + i
#                     self.sheet[f'{material_name_col_letter}{current_row}'] = mat_code
#                     self.sheet[f'{material_qty_col_letter}{current_row}'] = float(total_qty)
#
#         if self.record.lot_number:
#             lot_numbers = [lot.strip() for lot in self.record.lot_number.split(';')]
#             for i, lot in enumerate(lot_numbers[:13]):
#                 row = 12 + i
#                 self.sheet[f'M{row}'] = lot
#
#     def _fill_purging_info(self):
#         if not self.record.purging_headers:
#             return
#         header = self.record.purging_headers[0]
#         self.sheet['B26'] = header.product_code
#         start_str = header.time_start.strftime("%H:%M") if header.time_start else ""
#         end_str = header.time_end.strftime("%H:%M") if header.time_end else ""
#         self.sheet['B27'] = f"{start_str} – {end_str}"
#         if header.time_start and header.time_end:
#             dummy_date = datetime.now().date()
#             start_dt = datetime.combine(dummy_date, header.time_start)
#             end_dt = datetime.combine(dummy_date, header.time_end)
#             if end_dt < start_dt: end_dt += timedelta(days=1)
#             duration = end_dt - start_dt
#             total_seconds = int(duration.total_seconds())
#             hours, rem = divmod(total_seconds, 3600)
#             minutes, _ = divmod(rem, 60)
#             self.sheet['E27'] = f"{int(hours):02d}:{int(minutes):02d}"
#
#         resin_details_str = ", ".join(
#             [f"{getattr(d.resin, 'abbreviation', 'N/A')} = {d.qty}" for d in header.purging_details]
#         )
#         self.sheet['B28'] = resin_details_str
#         self.sheet['B29'] = header.siever_used
#         self.sheet['B30'] = header.palletizer_used
#
#     def _fill_footer_info(self):
#         self.sheet['G26'] = self.record.remarks
#         operators = []
#         supervisors = []
#         for p in self.record.extruder_personnels:
#             if not p.employee or not p.position: continue
#             full_name = f"{p.employee.first_name} {p.employee.last_name}"
#             pos_name = p.position.name.lower()
#             if "supervisor" in pos_name:
#                 supervisors.append(full_name)
#             elif "operator" in pos_name:
#                 operators.append(full_name)
#             elif "reliever" in pos_name:
#                 operators.append(f"{full_name} (Reliever)")
#         self.sheet['M28'] = ", ".join(operators)
#         self.sheet['M29'] = ", ".join(supervisors)


# app/views/extruder_form/records/exporter.py
import os
import openpyxl
from datetime import datetime, timedelta
from decimal import Decimal

# Import Border and Side for styling
from openpyxl.styles import Border, Side, Alignment

# Import the operations controller for data fetching
from .ops import ExtruderRecordsOperations


class ExcelReportExporter:
    """
    Handles populating the extruder report Excel template with data
    from a single, fully-loaded ExtruderFormData record.
    """

    def __init__(self, record_object, ops_controller: ExtruderRecordsOperations):
        self.record = record_object
        self.controller = ops_controller  # Store the controller instance

        current_dir = os.path.dirname(os.path.abspath(__file__))
        template_path = os.path.join(current_dir, "extruder_report_format.xlsx")
        self.workbook = openpyxl.load_workbook(template_path)
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
        machine_name = getattr(self.record.machine, 'name', 'N/A')
        self.sheet['F5'] = f"Extruder Machine No. {machine_name}"

    def _fill_summary_and_calculations(self):
        self.sheet['A8'] = getattr(self.record.machine, 'name', 'N/A')
        self.sheet['B8'] = self.record.qty_order
        self.sheet['C8'] = self.record.customer
        self.sheet['F8'] = self.record.product_code
        self.sheet['G9'] = self.record.qty_produced

        total_output = sum(out.qty_output for out in self.record.extruder_outputs if out.qty_output)
        total_seconds = sum(
            (out.datetime_end - out.datetime_start).total_seconds() for out in self.record.extruder_outputs
            if out.datetime_start and out.datetime_end and out.datetime_end > out.datetime_start
        )
        total_hours_decimal = Decimal(total_seconds) / Decimal(3600)

        self.sheet['H9'] = float(total_hours_decimal.quantize(Decimal('0.01')))
        output_per_hour = (Decimal(total_output) / total_hours_decimal) if total_hours_decimal > 0 else Decimal(0)
        self.sheet['I9'] = float(output_per_hour.quantize(Decimal('0.01')))
        self.sheet['J9'] = float(self.record.target_output_per_hour or 0)
        self.sheet['K9'] = total_output

        qty_produced_dec = Decimal(self.record.qty_produced or 0)
        loss = max(Decimal(0), qty_produced_dec - Decimal(total_output))
        denominator = Decimal(total_output) + loss
        output_percentage = (Decimal(total_output) / denominator * 100) if denominator > 0 else Decimal(0)
        loss_percentage = (loss / denominator * 100) if denominator > 0 else Decimal(0)

        self.sheet['L9'] = f"{output_percentage:.2f}%"
        self.sheet['M9'] = loss
        self.sheet['N9'] = f"{loss_percentage:.2f}%"

    def _fill_output_log(self):
        sorted_outputs = sorted(self.record.extruder_outputs,
                                key=lambda x: (x.datetime_start is None, x.datetime_start))
        total_duration = timedelta()
        for i, output in enumerate(sorted_outputs[:13]):
            row = 12 + i
            if output.datetime_start:
                self.sheet[f'A{row}'] = output.datetime_start.strftime("%d-%b-%Y %H:%M")
            if output.datetime_end:
                self.sheet[f'D{row}'] = output.datetime_end.strftime("%d-%b-%Y %H:%M")
            duration = timedelta()
            if output.datetime_start and output.datetime_end:
                duration = output.datetime_end - output.datetime_start
                total_duration += duration
                hours, rem = divmod(duration.total_seconds(), 3600)
                minutes, _ = divmod(rem, 60)
                self.sheet[f'F{row}'] = f"{int(hours):02d}:{int(minutes):02d}"
            self.sheet[f'G{row}'] = output.qty_output

        total_seconds = int(total_duration.total_seconds())
        hours, rem = divmod(total_seconds, 3600)
        minutes, seconds = divmod(rem, 60)
        self.sheet['F25'] = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _fill_materials_and_lots(self):
        """
        Unmerges cells, restores borders, filters the material list, and
        populates the valid data row by row.
        """
        start_row = 12
        end_row = 24
        material_name_col_letter = 'I'
        material_qty_col_letter = 'K'

        merged_to_remove = []
        for merged_range in self.sheet.merged_cells.ranges:
            if merged_range.min_row <= end_row and merged_range.max_row >= start_row:
                if merged_range.min_col <= 11 and merged_range.max_col >= 9:
                    merged_to_remove.append(str(merged_range))

        for merged_ref in merged_to_remove:
            self.sheet.unmerge_cells(merged_ref)

        solid_thin_side = Side(style='thin')
        cell_j12 = self.sheet['J12']
        cell_j12.border = Border(top=solid_thin_side,
                                 left=cell_j12.border.left,
                                 right=cell_j12.border.right,
                                 bottom=cell_j12.border.bottom)

        if self.record.production_id:
            prod_ids = [pid.strip() for pid in self.record.production_id.split(';') if pid.strip()]
            if prod_ids:
                aggregated_materials = self.controller.get_aggregated_materials_for_production_ids(prod_ids)

                # --- THIS IS THE FIX ---
                # 1. Create a new list containing only valid materials.
                #    A material is valid if its code is not blank AND its quantity is greater than zero.
                valid_materials = [
                    (mat_code, total_qty)
                    for mat_code, total_qty in aggregated_materials
                    if mat_code and mat_code.strip() and total_qty > 0
                ]
                # --- END FIX ---

                # 2. Now, iterate over the filtered 'valid_materials' list.
                # for i, (mat_code, total_qty) in enumerate(valid_materials[:13]):  # Still limit to 13 rows
                #     current_row = start_row + i
                #     self.sheet[f'{material_name_col_letter}{current_row}'] = mat_code
                #     self.sheet[f'{material_qty_col_letter}{current_row}'] = float(total_qty)

                for i, (mat_code, total_qty) in enumerate(valid_materials[:13]):
                    current_row = start_row + i

                    # 1. Get the cell for the material name (Column I)
                    mat_cell = self.sheet[f'{material_name_col_letter}{current_row}']
                    mat_cell.value = mat_code
                    # 2. Apply left alignment
                    mat_cell.alignment = Alignment(horizontal='left', vertical='center')

                    # 3. Get the cell for the quantity (Column K)
                    qty_cell = self.sheet[f'{material_qty_col_letter}{current_row}']
                    qty_cell.value = float(total_qty)
                    # 4. Apply right alignment
                    qty_cell.alignment = Alignment(horizontal='right', vertical='center')

        if self.record.lot_number:
            lot_numbers = [lot.strip() for lot in self.record.lot_number.split(';')]
            for i, lot in enumerate(lot_numbers[:13]):
                row = 12 + i
                self.sheet[f'M{row}'] = lot

    def _fill_purging_info(self):
        if not self.record.purging_headers:
            return
        header = self.record.purging_headers[0]
        self.sheet['B26'] = header.product_code
        start_str = header.time_start.strftime("%H:%M") if header.time_start else ""
        end_str = header.time_end.strftime("%H:%M") if header.time_end else ""
        self.sheet['B27'] = f"{start_str} – {end_str}"
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

        resin_details_str = ", ".join(
            [f"{getattr(d.resin, 'abbreviation', 'N/A')} = {d.qty}" for d in header.purging_details]
        )
        self.sheet['B28'] = resin_details_str
        self.sheet['B29'] = header.siever_used
        self.sheet['B30'] = header.palletizer_used

    def _fill_footer_info(self):
        self.sheet['G26'] = self.record.remarks
        operators = []
        supervisors = []
        for p in self.record.extruder_personnels:
            if not p.employee or not p.position: continue
            full_name = f"{p.employee.first_name} {p.employee.last_name}"
            pos_name = p.position.name.lower()
            if "supervisor" in pos_name:
                supervisors.append(full_name)
            elif "operator" in pos_name:
                operators.append(full_name)
            elif "reliever" in pos_name:
                operators.append(f"{full_name} (Reliever)")
        self.sheet['M28'] = ", ".join(operators)
        self.sheet['M29'] = ", ".join(supervisors)