# import pandas as pd
# from openpyxl.styles import Font, PatternFill, Alignment
#
#
# class BenchmarkExporter:
#     def export(self, summary_valid: pd.DataFrame, summary_invalid: pd.DataFrame, raw_df: pd.DataFrame, filepath: str):
#         with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
#
#             # --- SHEET 1: RAW DATA ---
#             raw_export = raw_df[[
#                 "date", "reference_no", "product_code", "machine_name", "formula_no", "lot_no",
#                 "output_qty", "proc_hours", "output_rate_hr",
#                 "cleaning_mins", "cleaning_qty", "yield_pct"
#             ]].copy()
#
#             raw_export.rename(columns={
#                 "date": "Date", "reference_no": "Ref No",
#                 "product_code": "Product Code", "machine_name": "Machine",
#                 "formula_no": "Formula", "lot_no": "Lot No",
#                 "output_qty": "Output (kg)", "proc_hours": "Duration (hr)",
#                 "output_rate_hr": "Output Rate (kg/hr)",
#                 "cleaning_mins": "Clean Time (min)",
#                 "cleaning_qty": "Clean Mat (kg)",
#                 "yield_pct": "Yield %"
#             }, inplace=True)
#
#             raw_export.to_excel(writer, sheet_name="Raw Data", index=False)
#
#             # --- COLUMN MAPPING ---
#             col_map = {
#                 "product_code": "Product Code",
#                 "machine_name": "Mixer Machine Number",
#                 "formula_no": "Formula No",
#                 "avg_output_rate": "Average Output/Hr",
#                 "avg_clean_time": "Average Cleaning Time (min)",
#                 "avg_clean_mat": "Average Kg Cleaning Material",
#                 "avg_yield": "Average Yield %"
#             }
#             main_cols = list(col_map.values())
#
#             # --- SHEET 2: BENCHMARK REPORT (Valid Yields) ---
#             if not summary_valid.empty:
#                 report_export = summary_valid.rename(columns=col_map)
#                 valid_cols = [c for c in main_cols if c in report_export.columns]
#                 report_export[valid_cols].to_excel(writer, sheet_name="Benchmark Report", index=False, startcol=0)
#
#                 # Stats Table (Std Dev)
#                 try:
#                     std_out = summary_valid["avg_output_rate"].std()
#                     std_ct = summary_valid["avg_clean_time"].std()
#                     std_cm = summary_valid["avg_clean_mat"].std()
#                     std_yld = summary_valid["avg_yield"].std()
#                 except:
#                     std_out = 0;
#                     std_ct = 0;
#                     std_cm = 0;
#                     std_yld = 0
#
#                 stats_data = {
#                     "Average Types": [
#                         "Average Output/Hr", "Average Cleaning Time (min)",
#                         "Average Kg Cleaning Material", "Average Yield %"
#                     ],
#                     "Std Deviation": [std_out, std_ct, std_cm, std_yld]
#                 }
#                 pd.DataFrame(stats_data).to_excel(writer, sheet_name="Benchmark Report", index=False, startcol=9)
#
#             # --- SHEET 3: UNSPECIFIED YIELDS (Separate Sheet) ---
#             if not summary_invalid.empty:
#                 invalid_export = summary_invalid.rename(columns=col_map)
#                 valid_cols = [c for c in main_cols if c in invalid_export.columns]
#                 invalid_export[valid_cols].to_excel(writer, sheet_name="Unspecified Yields", index=False)
#
#             # --- FORMATTING (Apply to all sheets) ---
#             wb = writer.book
#
#             header_font = Font(bold=True, color="FFFFFF")
#             header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
#             center_align = Alignment(horizontal='center')
#
#             sheets_to_format = []
#             if "Benchmark Report" in wb.sheetnames: sheets_to_format.append(wb["Benchmark Report"])
#             if "Unspecified Yields" in wb.sheetnames: sheets_to_format.append(wb["Unspecified Yields"])
#
#             for ws in sheets_to_format:
#                 # Format Main Headers
#                 for col_idx in range(1, 8):
#                     cell = ws.cell(row=1, column=col_idx)
#                     cell.font = header_font;
#                     cell.fill = header_fill;
#                     cell.alignment = center_align
#
#                 # Format Numbers
#                 for row in range(2, ws.max_row + 1):
#                     for col in [4, 5, 6, 7]:
#                         cell = ws.cell(row=row, column=col)
#                         if cell.value is not None: cell.number_format = '#,##0.00'
#
#                 # Auto width
#                 from openpyxl.utils import get_column_letter
#                 for col_idx in range(1, 12):
#                     col_letter = get_column_letter(col_idx)
#                     ws.column_dimensions[col_letter].width = 22
#
#             # Specific format for Stats table in Benchmark Report
#             if "Benchmark Report" in wb.sheetnames:
#                 ws = wb["Benchmark Report"]
#                 for col_idx in range(10, 12):
#                     cell = ws.cell(row=1, column=col_idx)
#                     cell.font = header_font;
#                     cell.fill = header_fill;
#                     cell.alignment = center_align
#                 for row in range(2, 6):
#                     cell = ws.cell(row=row, column=11)
#                     if cell.value is not None: cell.number_format = '#,##0.00'


import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment


class BenchmarkExporter:
    def export(self, summary_valid: pd.DataFrame, summary_invalid: pd.DataFrame, raw_df: pd.DataFrame, filepath: str):
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:

            # ---------------------------------------------------------
            # SHEET 1: RAW DATA
            # ---------------------------------------------------------
            raw_export = raw_df[[
                "date", "reference_no", "product_code", "machine_name", "formula_no", "lot_no",
                "output_qty", "proc_hours", "output_rate_hr",
                "cleaning_mins", "cleaning_qty", "yield_pct"
            ]].copy()

            raw_export.rename(columns={
                "date": "Date", "reference_no": "Ref No",
                "product_code": "Product Code", "machine_name": "Machine",
                "formula_no": "Formula", "lot_no": "Lot No",
                "output_qty": "Output (kg)", "proc_hours": "Duration (hr)",
                "output_rate_hr": "Output Rate (kg/hr)",
                "cleaning_mins": "Clean Time (min)",
                "cleaning_qty": "Clean Mat (kg)",
                "yield_pct": "Yield %"
            }, inplace=True)

            raw_export.to_excel(writer, sheet_name="Raw Data", index=False)

            # --- COLUMN MAPPING ---
            col_map = {
                "product_code": "Product Code",
                "machine_name": "Mixer Machine Number",
                "formula_no": "Formula No",
                "avg_output_rate": "Average Output/Hr",
                "avg_clean_time": "Average Cleaning Time (min)",
                "avg_clean_mat": "Average Kg Cleaning Material",
                "avg_yield": "Average Yield %"
            }
            main_cols = list(col_map.values())

            # Helper function to create Stats DataFrame
            def create_stats_df(df):
                try:
                    std_out = df["avg_output_rate"].std()
                    std_ct = df["avg_clean_time"].std()
                    std_cm = df["avg_clean_mat"].std()
                    # Yield might be all NaN for the invalid sheet, so handle safely
                    std_yld = df["avg_yield"].std() if "avg_yield" in df and not df["avg_yield"].isna().all() else 0
                except:
                    std_out = 0;
                    std_ct = 0;
                    std_cm = 0;
                    std_yld = 0

                # Fill NaN with 0
                if pd.isna(std_out): std_out = 0
                if pd.isna(std_ct): std_ct = 0
                if pd.isna(std_cm): std_cm = 0
                if pd.isna(std_yld): std_yld = 0

                return pd.DataFrame({
                    "Average Types": [
                        "Average Output/Hr", "Average Cleaning Time (min)",
                        "Average Kg Cleaning Material", "Average Yield %"
                    ],
                    "Std Deviation": [std_out, std_ct, std_cm, std_yld]
                })

            # ---------------------------------------------------------
            # SHEET 2: BENCHMARK REPORT (Valid Yields)
            # ---------------------------------------------------------
            if not summary_valid.empty:
                # 1. Main Table
                report_export = summary_valid.rename(columns=col_map)
                valid_cols = [c for c in main_cols if c in report_export.columns]
                report_export[valid_cols].to_excel(writer, sheet_name="Benchmark Report", index=False, startcol=0)

                # 2. Stats Table (Cols J-K)
                stats_df = create_stats_df(summary_valid)
                stats_df.to_excel(writer, sheet_name="Benchmark Report", index=False, startcol=9)

            # ---------------------------------------------------------
            # SHEET 3: UNSPECIFIED YIELDS (Invalid Yields)
            # ---------------------------------------------------------
            if not summary_invalid.empty:
                # 1. Main Table
                invalid_export = summary_invalid.rename(columns=col_map)
                valid_cols = [c for c in main_cols if c in invalid_export.columns]
                invalid_export[valid_cols].to_excel(writer, sheet_name="Unspecified Yields", index=False)

                # 2. Stats Table (Cols J-K) - NEW REQUEST
                # We calculate stats for Output/CleanTime/CleanMat. Yield StdDev will likely be 0.
                stats_invalid_df = create_stats_df(summary_invalid)
                stats_invalid_df.to_excel(writer, sheet_name="Unspecified Yields", index=False, startcol=9)

            # ---------------------------------------------------------
            # FORMATTING
            # ---------------------------------------------------------
            wb = writer.book

            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            center_align = Alignment(horizontal='center')

            # Identify which sheets need formatting
            target_sheets = []
            if "Benchmark Report" in wb.sheetnames: target_sheets.append(wb["Benchmark Report"])
            if "Unspecified Yields" in wb.sheetnames: target_sheets.append(wb["Unspecified Yields"])

            for ws in target_sheets:
                # Format Main Table Headers (Cols A-G)
                for col_idx in range(1, 8):
                    cell = ws.cell(row=1, column=col_idx)
                    cell.font = header_font;
                    cell.fill = header_fill;
                    cell.alignment = center_align

                # Format Stats Table Headers (Cols J-K)
                for col_idx in range(10, 12):
                    cell = ws.cell(row=1, column=col_idx)
                    cell.font = header_font;
                    cell.fill = header_fill;
                    cell.alignment = center_align

                # Format Numbers (Main Table Data)
                for row in range(2, ws.max_row + 1):
                    for col in [4, 5, 6, 7]:
                        cell = ws.cell(row=row, column=col)
                        if cell.value is not None: cell.number_format = '#,##0.00'

                # Format Numbers (Stats Table Data: Rows 2-5, Col K)
                for row in range(2, 6):
                    cell = ws.cell(row=row, column=11)
                    if cell.value is not None: cell.number_format = '#,##0.00'

                # Auto width
                from openpyxl.utils import get_column_letter
                for col_idx in range(1, 12):
                    col_letter = get_column_letter(col_idx)
                    if ws.column_dimensions[col_letter].width == 0:
                        ws.column_dimensions[col_letter].width = 22