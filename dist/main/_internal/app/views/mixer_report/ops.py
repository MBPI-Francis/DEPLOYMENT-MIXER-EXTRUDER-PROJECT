# app/views/mixer_report/ops.py

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from datetime import timedelta

from models import MixerDetail, MixerHeader, MixerMachine, TblProd01

def get_report_prerequisites(session: Session) -> dict:
    """Fetches the unique machine names and product codes for the filter UI."""
    machines = session.scalars(select(MixerMachine.name).where(MixerMachine.is_deleted == False).distinct().order_by(MixerMachine.name)).all()
    product_codes = session.scalars(select(MixerDetail.product_code).distinct().order_by(MixerDetail.product_code)).all()
    return {
        "machines": machines,
        "product_codes": product_codes
    }

# def get_mixer_summary_report_data(session: Session, filters: dict) -> pd.DataFrame:
#     """
#     Fetches raw mixer data, applies filters, performs calculations, and
#     returns a summarized report DataFrame.
#     """
#     # Base query joining all necessary tables
#     query = (
#         select(
#             MixerMachine.name.label("Machine Number"),
#             MixerDetail.product_code.label("Product Code"),
#             MixerDetail.output_qty,
#             (func.extract('epoch', MixerDetail.process_time_end - MixerDetail.process_time_start) / 3600).label("processing_hours"),
#             (func.extract('epoch', MixerDetail.cleaning_time_end - MixerDetail.cleaning_time_start) / 60).label("cleaning_minutes"),
#             MixerDetail.cleaning_qty,
#             (MixerDetail.output_qty / func.nullif(TblProd01.T_QTYREQ, 0) * 100).label("yield_percent")
#         )
#         .join(MixerHeader, MixerDetail.mixer_header_id == MixerHeader.id)
#         .join(MixerMachine, MixerDetail.mc_id == MixerMachine.id)
#         .outerjoin(TblProd01, MixerDetail.lot_no == TblProd01.T_LOTNUM)
#         .where(MixerDetail.is_deleted == False)
#     )
#
#     # Apply filters from the UI
#     if filters.get("date_from") and filters.get("date_to"):
#         query = query.where(MixerHeader.date.between(filters["date_from"], filters["date_to"]))
#     if filters.get("machine"):
#         query = query.where(MixerMachine.name == filters["machine"])
#     if filters.get("product_code"):
#         query = query.where(MixerDetail.product_code == filters["product_code"])
#
#     # Execute query and load into a DataFrame
#     raw_df = pd.read_sql(query, session.bind)
#     if raw_df.empty:
#         return pd.DataFrame()
#
#     # --- START OF MODIFICATION: Implement Method 1 ---
#
#     # We no longer calculate kg/hr per row. Instead, we group and sum first.
#     # The 'agg' function can perform multiple operations at once.
#     grouped_df = raw_df.groupby(["Machine Number", "Product Code"]).agg(
#         total_output_qty=('output_qty', 'sum'),
#         total_processing_hours=('processing_hours', 'sum'),
#         total_cleaning_minutes=('cleaning_minutes', 'sum'),
#         total_cleaning_qty=('cleaning_qty', 'sum'),
#         avg_yield_percent=('yield_percent', 'mean'),
#         record_count=('output_qty', 'count')  # Get the number of records in each group
#     ).reset_index()
#
#     # Now, perform the final calculations based on the sums (Method 1)
#     # Use a small epsilon to avoid division by zero if total hours is 0
#     epsilon = 1e-9
#
#     # Average Output KG / HR = Sum of output / Sum of hours
#     grouped_df["Average Output KG / HR"] = grouped_df['total_output_qty'] / (
#                 grouped_df['total_processing_hours'] + epsilon)
#
#     # Average Cleaning Time = Sum of minutes / Number of records
#     grouped_df["Average Cleaning Time (Minutes)"] = grouped_df['total_cleaning_minutes'] / (
#                 grouped_df['record_count'] + epsilon)
#
#     # Average Cleaning Material = Sum of material / Number of records
#     grouped_df["Average Cleaning Material (KG)"] = grouped_df['total_cleaning_qty'] / (
#                 grouped_df['record_count'] + epsilon)
#
#     # Rename the yield column
#     grouped_df.rename(columns={"avg_yield_percent": "Average Yield %"}, inplace=True)
#
#     # --- END OF MODIFICATION ---
#
#     # Select and reorder the final columns for the report
#     final_columns = [
#         "Machine Number",
#         "Product Code",
#         "Average Output KG / HR",
#         "Average Cleaning Time (Minutes)",
#         "Average Cleaning Material (KG)",
#         "Average Yield %"
#     ]
#     summary_df = grouped_df[final_columns]
#
#     return summary_df
#


def get_mixer_summary_report_data(session: Session, filters: dict, group_by_columns: list) -> pd.DataFrame:
    """
    Fetches raw mixer data and generates a summary report, now with a
    dynamic list of columns to group the data by.
    """
    # Define a mapping from user-friendly names to database columns
    column_mapping = {
        "Machine Number": MixerMachine.name.label("Machine Number"),  # Added .label()
        "Product Code": MixerDetail.product_code.label("Product Code"),  # Added .label()
        "Formula No": TblProd01.T_FID.label("Formula No")  # Added .label()
    }

    if not group_by_columns:
        raise ValueError("Grouping columns must be provided.")

    selected_group_columns = [column_mapping[col] for col in group_by_columns if col in column_mapping]
    if not selected_group_columns:
        raise ValueError("At least one valid grouping column is required.")

    # --- START OF MODIFICATION ---
    # The query now reliably uses the correct labels for all columns.
    query_columns = selected_group_columns + [
        MixerDetail.output_qty.label("output_qty"),  # Added labels for clarity
        (func.extract('epoch', MixerDetail.process_time_end - MixerDetail.process_time_start) / 3600).label(
            "processing_hours"),
        (func.extract('epoch', MixerDetail.cleaning_time_end - MixerDetail.cleaning_time_start) / 60).label(
            "cleaning_minutes"),
        MixerDetail.cleaning_qty.label("cleaning_qty"),  # Added labels for clarity
        (MixerDetail.output_qty / func.nullif(TblProd01.T_QTYREQ, 0) * 100).label("yield_percent")
    ]
    # --- END OF MODIFICATION ---

    query = (
        select(*query_columns)
        .join(MixerHeader, MixerDetail.mixer_header_id == MixerHeader.id)
        .join(MixerMachine, MixerDetail.mc_id == MixerMachine.id)
        .outerjoin(TblProd01, MixerDetail.lot_no == TblProd01.T_LOTNUM)
        .where(MixerDetail.is_deleted == False)
    )

    if filters.get("date_from") and filters.get("date_to"):
        query = query.where(MixerHeader.date.between(filters["date_from"], filters["date_to"]))
    if filters.get("machine"):
        query = query.where(MixerMachine.name == filters["machine"])
    if filters.get("product_code"):
        query = query.where(MixerDetail.product_code == filters["product_code"])

    raw_df = pd.read_sql(query, session.bind)
    if raw_df.empty:
        return pd.DataFrame()

    # The rest of the function is correct and remains the same.
    # The groupby will now work because the column names in raw_df will
    # match the strings in the group_by_columns list (e.g., "Machine Number").
    grouped_df = raw_df.groupby(group_by_columns).agg(
        total_output_qty=('output_qty', 'sum'),
        total_processing_hours=('processing_hours', 'sum'),
        total_cleaning_minutes=('cleaning_minutes', 'sum'),
        total_cleaning_qty=('cleaning_qty', 'sum'),
        avg_yield_percent=('yield_percent', 'mean'),
        record_count=('output_qty', 'count')
    ).reset_index()

    epsilon = 1e-9
    grouped_df["Average Output KG / HR"] = grouped_df['total_output_qty'] / (
                grouped_df['total_processing_hours'] + epsilon)
    grouped_df["Average Cleaning Time (Minutes)"] = grouped_df['total_cleaning_minutes'] / (
                grouped_df['record_count'] + epsilon)
    grouped_df["Average Cleaning Material (KG)"] = grouped_df['total_cleaning_qty'] / (
                grouped_df['record_count'] + epsilon)
    grouped_df.rename(columns={"avg_yield_percent": "Average Yield %"}, inplace=True)

    final_columns = group_by_columns + [
        "Average Output KG / HR",
        "Average Cleaning Time (Minutes)",
        "Average Cleaning Material (KG)",
        "Average Yield %"
    ]
    summary_df = grouped_df[final_columns]

    return summary_df