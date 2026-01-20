# app/views/extruder_benchmark_report/exporter.py

import pandas as pd
from openpyxl.styles import Font, PatternFill, Alignment


class ExtruderBenchmarkExporter:
    def export(self, summary_valid: pd.DataFrame, summary_invalid: pd.DataFrame, raw_df: pd.DataFrame, filepath: str):
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:

            # --- SHEET 1: RAW DATA ---
            raw_export = raw_df[[
                "report_date", "ref_no", "product_code", "machine_name", "formula_no", "lot_number",
                "total_output_qty", "total_proc_hours", "output_rate_hr",
                "clean_mins", "clean_mat", "yield_pct"
            ]].copy()

            raw_export.rename(columns={
                "report_date": "Date", "ref_no": "Ref No",
                "product_code": "Product Code", "machine_name": "Machine",
                "formula_no": "Formula", "lot_number": "Lot No",
                "total_output_qty": "Total Output (kg)", "total_proc_hours": "Total Duration (hr)",
                "output_rate_hr": "Output Rate (kg/hr)",
                "clean_mins": "Clean Time (min)",
                "clean_mat": "Clean Mat (kg)",
                "yield_pct": "Yield %"
            }, inplace=True)

            raw_export.to_excel(writer, sheet_name="Raw Data", index=False)

            # --- MAPPING & HELPER ---
            col_map = {
                "product_code": "Product Code", "machine_name": "Extruder Machine Number",
                "formula_no": "Formula No", "avg_output_rate": "Average Output/Hr",
                "avg_clean_time": "Average Cleaning Time (min)",
                "avg_clean_mat": "Average Kg Cleaning Material", "avg_yield": "Average Yield %"
            }
            main_cols = list(col_map.values())

            def create_stats_df(df):
                try:
                    std_out = df["avg_output_rate"].std()
                    std_ct = df["avg_clean_time"].std()
                    std_cm = df["avg_clean_mat"].std()
                    std_yld = df["avg_yield"].std() if "avg_yield" in df else 0
                except:
                    std_out = 0;
                    std_ct = 0;
                    std_cm = 0;
                    std_yld = 0

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

            # --- SHEET 2: BENCHMARK (Valid) ---
            if not summary_valid.empty:
                rep_ex = summary_valid.rename(columns=col_map)
                valid_cols = [c for c in main_cols if c in rep_ex.columns]
                rep_ex[valid_cols].to_excel(writer, sheet_name="Benchmark Report", index=False, startcol=0)

                stats_df = create_stats_df(summary_valid)
                stats_df.to_excel(writer, sheet_name="Benchmark Report", index=False, startcol=9)

            # --- SHEET 3: INVALID ---
            if not summary_invalid.empty:
                inv_ex = summary_invalid.rename(columns=col_map)
                valid_cols = [c for c in main_cols if c in inv_ex.columns]
                inv_ex[valid_cols].to_excel(writer, sheet_name="Unspecified Yields", index=False)

                stats_inv = create_stats_df(summary_invalid)
                stats_inv.to_excel(writer, sheet_name="Unspecified Yields", index=False, startcol=9)

            # --- FORMATTING ---
            wb = writer.book
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
            center_align = Alignment(horizontal='center')

            target_sheets = []
            if "Benchmark Report" in wb.sheetnames: target_sheets.append(wb["Benchmark Report"])
            if "Unspecified Yields" in wb.sheetnames: target_sheets.append(wb["Unspecified Yields"])

            for ws in target_sheets:
                for col_idx in range(1, 8):
                    ws.cell(row=1, column=col_idx).font = header_font
                    ws.cell(row=1, column=col_idx).fill = header_fill
                    ws.cell(row=1, column=col_idx).alignment = center_align
                for col_idx in range(10, 12):
                    ws.cell(row=1, column=col_idx).font = header_font
                    ws.cell(row=1, column=col_idx).fill = header_fill
                    ws.cell(row=1, column=col_idx).alignment = center_align

                for row in range(2, ws.max_row + 1):
                    for col in [4, 5, 6, 7]:
                        cell = ws.cell(row=row, column=col)
                        if cell.value is not None: cell.number_format = '#,##0.00'
                for row in range(2, 6):
                    cell = ws.cell(row=row, column=11)
                    if cell.value is not None: cell.number_format = '#,##0.00'

                from openpyxl.utils import get_column_letter
                for col_idx in range(1, 12):
                    col_letter = get_column_letter(col_idx)
                    if ws.column_dimensions[col_letter].width == 0:
                        ws.column_dimensions[col_letter].width = 22