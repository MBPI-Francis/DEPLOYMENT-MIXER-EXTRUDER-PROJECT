# app/views/mixer_report/exporter.py

import pandas as pd
from datetime import timedelta
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter


class ExcelExporter:
    """Handles the creation of the multi-sheet, formatted Excel report."""

    def __init__(self, dataframe: pd.DataFrame):
        self.df = dataframe.copy()
        # Ensure 'Date' column is in datetime format for grouping
        self.df['Date'] = pd.to_datetime(self.df['Date'])

    def _calculate_totals(self, df_subset: pd.DataFrame) -> dict:
        """Calculates all required totals for a given subset of data."""
        if df_subset.empty:
            return {}

        # 2. Compute the total Processing OUTPUT and Cleaning QTY.
        total_output_qty = df_subset['Output QTY'].sum()
        total_cleaning_qty = df_subset['Cleaning QTY'].sum()

        # 3. Compute the total Cleaning Durations and Total Processing Durations.
        total_proc_delta = timedelta()
        for duration_str in df_subset['Processing Duration'].dropna():
            try:
                hours, minutes = map(int, duration_str.split(':'))
                total_proc_delta += timedelta(hours=hours, minutes=minutes)
            except (ValueError, TypeError):
                continue

        total_clean_delta = timedelta()
        for duration_str in df_subset['Cleaning Duration'].dropna():
            try:
                hours, minutes = map(int, duration_str.split(':'))
                total_clean_delta += timedelta(hours=hours, minutes=minutes)
            except (ValueError, TypeError):
                continue

        # Convert total durations back to a readable format
        proc_total_seconds = total_proc_delta.total_seconds()
        proc_total_hours = int(proc_total_seconds // 3600)
        proc_total_minutes = int((proc_total_seconds % 3600) // 60)

        clean_total_seconds = total_clean_delta.total_seconds()
        clean_total_hours = int(clean_total_seconds // 3600)
        clean_total_minutes = int((clean_total_seconds % 3600) // 60)

        # 4. And Also compute this for cleaning time and processing time
        proc_decimal_hours = (proc_total_minutes / 60) + proc_total_hours
        clean_decimal_hours = (clean_total_minutes / 60) + clean_total_hours

        return {
            "Total Output QTY": f"{total_output_qty:,.2f}",
            "Total Cleaning QTY": f"{total_cleaning_qty:,.2f}",
            "Total Processing Duration (HH:MM)": f"{proc_total_hours}:{proc_total_minutes:02}",
            "Total Cleaning Duration (HH:MM)": f"{clean_total_hours}:{clean_total_minutes:02}",
            "Total Processing Duration (Decimal Hours)": f"{proc_decimal_hours:.2f}",
            "Total Cleaning Duration (Decimal Hours)": f"{clean_decimal_hours:.2f}",
        }

    def _format_worksheet(self, ws, title: str, totals: dict, num_columns: int):
        """Applies styling and adds title/totals to a worksheet."""
        # --- Styles ---
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        title_font = Font(bold=True, size=16)
        totals_label_font = Font(bold=True)
        thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'),
                             bottom=Side(style='thin'))

        # --- Title & Header Rows (Data starts on row 3) ---
        ws.insert_rows(1, 2)
        # Headers are now on row 3
        header_row = ws[3]

        # --- Header Formatting ---
        for cell in header_row:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = Alignment(horizontal='center', vertical='center')
            cell.border = thin_border

        # --- Data Formatting ---
        for row in ws.iter_rows(min_row=4, max_col=num_columns, max_row=ws.max_row):
            for cell in row:
                cell.border = thin_border

        # --- MODIFICATION START: Corrected Order of Operations ---

        # 1. Auto-fit Column Widths FIRST, while all cells are still standard.
        for col_idx, column_cells in enumerate(ws.columns, 1):
            # Do not resize beyond the number of actual data columns
            if col_idx > num_columns:
                break

            max_length = 0
            # Get the column letter (e.g., 'A', 'B')
            column_letter = get_column_letter(col_idx)

            for cell in column_cells:
                try:
                    # Find the length of the longest cell value in the column
                    if cell.value:
                        cell_length = len(str(cell.value))
                        if cell_length > max_length:
                            max_length = cell_length
                except:
                    pass

            # Set the column width with a little extra padding
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column_letter].width = adjusted_width

        # 2. Add and Merge the Title Cell SECOND.
        #    This is safe now because column sizing is already complete.
        title_cell = ws.cell(row=1, column=1, value=title)
        title_cell.font = title_font
        title_cell.alignment = Alignment(horizontal='center')
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=num_columns)

        # --- MODIFICATION END ---

        # --- Totals Block ---
        if totals:
            start_row = ws.max_row + 2
            ws.cell(row=start_row, column=1, value="SUMMARY TOTALS").font = Font(bold=True, size=12)
            for i, (label, value) in enumerate(totals.items()):
                label_cell = ws.cell(row=start_row + i + 1, column=1, value=label)
                value_cell = ws.cell(row=start_row + i + 1, column=2, value=value)
                label_cell.font = totals_label_font
                label_cell.alignment = Alignment(horizontal='right')

    def export(self, filepath: str):
        """Main export method to generate the complete Excel file."""
        # 1. Define the specific column order for export
        column_order = [
            "Date", "Ref No", "MC #", "Product Code", "Lot Number", "Formula No",
            "Processing Start", "Processing End", "Processing Duration", "Processed By", "Output QTY",
            "Cleaning Start", "Cleaning End", "Cleaning Duration", "Cleaning RM", "Cleaning QTY",
            "Remarks",
        ]
        # Filter the DataFrame to only include and order these columns
        export_df = self.df[[col for col in column_order if col in self.df.columns]]

        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            # 5. The first sheet should contain the overall record
            overall_totals = self._calculate_totals(export_df)
            export_df.to_excel(writer, sheet_name="Overall Report", index=False, startrow=2)
            ws_overall = writer.sheets["Overall Report"]
            self._format_worksheet(ws_overall, "OVERALL MIXER REPORT", overall_totals, len(export_df.columns))

            # 5.1. The exported data will be categorized by month and year.
            grouped = export_df.groupby(pd.Grouper(key='Date', freq='ME'))
            for month_end_date, group_df in grouped:
                if group_df.empty:
                    continue

                # Format sheet title: MAR, 2025
                sheet_name = month_end_date.strftime("%b, %Y").upper()

                # 6. EACH SHEET SHOULD HAVE A TITLE
                report_title = f"MIXER REPORT FOR THE MONTH OF {month_end_date.strftime('%B %Y').upper()}"

                month_totals = self._calculate_totals(group_df)
                group_df.to_excel(writer, sheet_name=sheet_name, index=False, startrow=2)
                ws_month = writer.sheets[sheet_name]
                self._format_worksheet(ws_month, report_title, month_totals, len(group_df.columns))