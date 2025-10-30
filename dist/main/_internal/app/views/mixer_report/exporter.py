# app/views/mixer_report/exporter.py

import pandas as pd
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from fpdf import FPDF


class ReportExporter:
    """Creates formatted Excel and PDF reports from a summary DataFrame."""

    def export_to_excel(self, df: pd.DataFrame, filepath: str, title: str):
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name="Mixer Summary Report", index=False, startrow=3)
            ws = writer.sheets["Mixer Summary Report"]

            # --- Formatting ---
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="345b8a", end_color="4F81BD", fill_type="solid")
            thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), top=Side(style='thin'),
                                 bottom=Side(style='thin'))

            # Add Title and Date Range
            ws.cell(row=3, column=1, value=title).font = Font(bold=True, color="FFFFFF", size=16)
            ws.cell(row=3, column=1, value=title).fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            ws.cell(row=3, column=1, value=title).border = thin_border
            ws.merge_cells(start_row=3, start_column=1, end_row=3, end_column=len(df.columns))
            ws.cell(row=3, column=1).alignment = Alignment(horizontal='center')

            # Format Header
            for cell in ws[4]:  # Headers are on row 4
                cell.font = header_font;
                cell.fill = header_fill;
                cell.border = thin_border

            # --- START OF MODIFICATION ---
            # Define which columns should get the special decimal formatting
            decimal_format_columns = [
                "Average Output KG / HR",
                "Average Cleaning Time (Minutes)",
                "Average Cleaning Material (KG)",
                "Average Yield %"
            ]

            # Find the column indexes for the headers we want to format
            headers = [cell.value for cell in ws[4]]
            decimal_format_indexes = [i for i, h in enumerate(headers) if h in decimal_format_columns]

            # Format Data Cells
            # Iterate through all data cells and apply formatting conditionally
            for row in ws.iter_rows(min_row=5, max_col=len(df.columns), max_row=ws.max_row):
                for col_idx, cell in enumerate(row):
                    cell.border = thin_border
                    # Apply decimal format ONLY if the column index is one of our targets
                    if col_idx in decimal_format_indexes:
                        cell.number_format = '#,##0.00'
                    # Center align the Formula No column if it exists
                    elif headers[col_idx] == "Formula No":
                        cell.alignment = Alignment(horizontal='center')
            # --- END OF MODIFICATION ---

            # Auto-fit Columns
            for col_idx, column_cells in enumerate(ws.columns, 1):
                max_length = max(len(str(cell.value)) for cell in column_cells if cell.value)
                ws.column_dimensions[get_column_letter(col_idx)].width = max_length + 2

    def export_to_pdf(self, df: pd.DataFrame, filepath: str, title: str):
        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)

        pdf.cell(0, 10, title, 0, 1, "C")
        pdf.set_font("Arial", "", 12)

        pdf.ln(10)

        # --- MODIFICATION: Dynamic Column Widths ---
        num_columns = len(df.columns)
        # Available width is 297mm (A4 landscape) - 20mm margins
        available_width = 277

        # Assign widths based on number of columns to prevent overflow
        if num_columns <= 4:
            col_widths = [60, 70, 50, 50]
        elif num_columns == 5:
            col_widths = [45, 55, 45, 45, 45]
        else:  # Default for 6 columns
            col_widths = [40, 50, 40, 40, 40, 35]

        col_widths = col_widths[:num_columns]  # Ensure list size matches column count

        # Table Header
        pdf.set_font("Arial", "B", 9)
        pdf.set_fill_color(79, 129, 189)
        pdf.set_text_color(255, 255, 255)
        for i, header in enumerate(df.columns):
            pdf.cell(col_widths[i], 10, header, 1, 0, "C", fill=True)
        pdf.ln()

        # Table Data
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(0, 0, 0)
        for _, row in df.iterrows():
            for i, item in enumerate(row):
                if isinstance(item, (int, float)):
                    pdf.cell(col_widths[i], 10, f"{item:,.2f}", 1, 0, "R")
                else:
                    pdf.cell(col_widths[i], 10, str(item), 1, 0, "L")
            pdf.ln()

        pdf.output(filepath)