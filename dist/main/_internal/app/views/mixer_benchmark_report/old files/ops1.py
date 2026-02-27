# import pandas as pd
# import numpy as np
# from sqlalchemy.orm import Session
# from sqlalchemy import select, and_
# from datetime import datetime, date, timedelta, time
#
# from models import MixerDetail, MixerHeader, MixerMachine, TblProd01
#
#
# def get_filter_options(session: Session):
#     machines = session.scalars(
#         select(MixerMachine.name).where(MixerMachine.is_deleted == False).order_by(MixerMachine.name)).all()
#     products = session.scalars(select(MixerDetail.product_code).distinct().order_by(MixerDetail.product_code)).all()
#
#     formulas = session.scalars(
#         select(TblProd01.T_FID)
#         .join(MixerDetail, TblProd01.T_LOTNUM == MixerDetail.lot_no)
#         .where(MixerDetail.is_deleted == False)
#         .distinct()
#     ).all()
#
#     # Logic: Format for dropdown (Remove decimals)
#     clean_formulas = []
#     for f in formulas:
#         if f is not None:
#             # Convert to int then string to remove ".0"
#             try:
#                 val = int(f)
#                 clean_formulas.append(str(val))
#             except:
#                 clean_formulas.append(str(f))
#
#     formula_list = sorted(list(set(clean_formulas)))  # Unique and sorted
#
#     return {
#         "machines": ["All"] + list(machines),
#         "products": ["All"] + list(products),
#         "formulas": ["All"] + formula_list
#     }
#
#
# def calculate_duration_hours(start, end):
#     if not isinstance(start, time) or not isinstance(end, time): return None
#     dummy_date = date(2000, 1, 1)
#     dt_start = datetime.combine(dummy_date, start)
#     dt_end = datetime.combine(dummy_date, end)
#     if dt_end < dt_start: dt_end += timedelta(days=1)
#     total_seconds = (dt_end - dt_start).total_seconds()
#     return total_seconds / 3600.0 if total_seconds > 0 else None
#
#
# def calculate_duration_minutes(start, end):
#     hours = calculate_duration_hours(start, end)
#     return hours * 60 if hours is not None else None
#
#
# def get_benchmark_data(session: Session, filters: dict):
#     # 1. Query
#     query = (
#         select(
#             MixerHeader.date,
#             MixerHeader.reference_no,
#             MixerMachine.name.label("machine_name"),
#             MixerDetail.product_code,
#             MixerDetail.lot_no,
#             TblProd01.T_FID.label("formula_no"),
#             TblProd01.T_QTYREQ.label("qty_required"),
#             MixerDetail.output_qty,
#             MixerDetail.process_time_start,
#             MixerDetail.process_time_end,
#             MixerDetail.cleaning_time_start,
#             MixerDetail.cleaning_time_end,
#             MixerDetail.cleaning_qty
#         )
#         .join(MixerHeader, MixerDetail.mixer_header_id == MixerHeader.id)
#         .join(MixerMachine, MixerDetail.mc_id == MixerMachine.id)
#         .outerjoin(TblProd01, MixerDetail.lot_no == TblProd01.T_LOTNUM)
#         .where(
#             and_(
#                 MixerDetail.is_deleted == False,
#                 MixerHeader.date.between(filters["date_from"], filters["date_to"])
#             )
#         )
#     )
#
#     if filters.get("machine") and filters["machine"] != "All":
#         query = query.where(MixerMachine.name == filters["machine"])
#     if filters.get("product_code") and filters["product_code"] != "All":
#         query = query.where(MixerDetail.product_code == filters["product_code"])
#
#     # Specific Formula Filter
#     if filters.get("formula_no") and filters["formula_no"] != "All":
#         # Cast to int then str to ensure matching
#         # (Assuming DB stores numeric, passing "123" matches 123)
#         query = query.where(TblProd01.T_FID.cast(str).like(f"{filters['formula_no']}%"))
#         # Note: Exact match logic depends on DB type, using cast is safer for mixed types
#
#     query = query.order_by(MixerHeader.date.desc())
#     df = pd.read_sql(query, session.bind)
#
#     if df.empty:
#         return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
#
#     # 2. Pre-processing & Filtering
#
#     # --- FORMULA PROCESSING ---
#     # Convert to numeric to handle logic, coercing errors to NaN
#     df["fid_temp"] = pd.to_numeric(df["formula_no"], errors='coerce')
#
#     # Masks
#     is_zero = df["fid_temp"] == 0
#     is_null = df["fid_temp"].isna()
#     is_specified = (~is_zero) & (~is_null)
#
#     # Apply Checkbox Logic
#     keep_mask = is_specified.copy()
#
#     # Checkbox 1: Include "0"
#     if filters.get("include_zero", True):
#         keep_mask = keep_mask | is_zero
#
#     # Checkbox 2: Include "Unspecified" (Nulls)
#     if filters.get("include_null", True):
#         keep_mask = keep_mask | is_null
#
#     df = df[keep_mask].copy()
#
#     if df.empty:
#         return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
#
#     # --- FORMATTING (Remove Decimals) ---
#     def format_formula(val):
#         if pd.isna(val):
#             return "Unspecified"
#         # Convert float/decimal to int, then to string to drop ".0"
#         return str(int(val))
#
#     df["formula_no"] = df["fid_temp"].apply(format_formula)
#
#     # Clean up
#     df.drop(columns=["fid_temp"], inplace=True)
#
#     # 3. Calc Metrics (Rounded)
#     df["proc_hours"] = df.apply(lambda x: calculate_duration_hours(x["process_time_start"], x["process_time_end"]),
#                                 axis=1)
#     df["output_rate_hr"] = df.apply(
#         lambda x: (x["output_qty"] / x["proc_hours"]) if (x["proc_hours"] and x["proc_hours"] > 0) else 0,
#         axis=1
#     ).round(2)
#
#     df["cleaning_mins"] = df.apply(
#         lambda x: calculate_duration_minutes(x["cleaning_time_start"], x["cleaning_time_end"]),
#         axis=1
#     ).fillna(0).round(2)
#
#     df["cleaning_qty"] = df["cleaning_qty"].fillna(0).round(2)
#
#     df["yield_pct"] = df.apply(
#         lambda x: (x["output_qty"] / x["qty_required"] * 100) if (
#                     x["qty_required"] and x["qty_required"] > 0) else np.nan,
#         axis=1
#     ).round(2)
#
#     # 4. Aggregation
#     group_cols = ["product_code", "machine_name", "formula_no"]
#
#     summary = df.groupby(group_cols).agg(
#         record_count=("output_qty", "count"),
#         avg_output_rate=("output_rate_hr", "mean"),
#         avg_yield=("yield_pct", "mean")
#     ).reset_index()
#
#     # Conditional Aggregation (Cleaning)
#     valid_clean_time_df = df[df["cleaning_mins"] > 0]
#     if not valid_clean_time_df.empty:
#         clean_time_stats = valid_clean_time_df.groupby(group_cols)["cleaning_mins"].agg(
#             avg_clean_time="mean").reset_index()
#         summary = pd.merge(summary, clean_time_stats, on=group_cols, how="left")
#     else:
#         summary["avg_clean_time"] = 0
#
#     valid_clean_mat_df = df[df["cleaning_qty"] > 0]
#     if not valid_clean_mat_df.empty:
#         clean_mat_stats = valid_clean_mat_df.groupby(group_cols)["cleaning_qty"].agg(avg_clean_mat="mean").reset_index()
#         summary = pd.merge(summary, clean_mat_stats, on=group_cols, how="left")
#     else:
#         summary["avg_clean_mat"] = 0
#
#     summary[["avg_clean_time", "avg_clean_mat"]] = summary[["avg_clean_time", "avg_clean_mat"]].fillna(0)
#     summary = summary.round(2)
#
#     # 5. Split Summary (Valid vs Unspecified Yield)
#     summary_valid = summary[summary["avg_yield"].notna()].copy()
#     summary_invalid = summary[summary["avg_yield"].isna()].copy()
#
#     return summary_valid, summary_invalid, df


import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from datetime import datetime, date, timedelta, time

from models import MixerDetail, MixerHeader, MixerMachine, TblProd01


def get_filter_options(session: Session):
    machines = session.scalars(
        select(MixerMachine.name).where(MixerMachine.is_deleted == False).order_by(MixerMachine.name)).all()
    products = session.scalars(select(MixerDetail.product_code).distinct().order_by(MixerDetail.product_code)).all()

    # Get formulas, excluding deleted Mixer records AND deleted TblProd01 records
    formulas = session.scalars(
        select(TblProd01.T_FID)
        .join(MixerDetail, TblProd01.T_LOTNUM == MixerDetail.lot_no)
        .where(
            and_(
                MixerDetail.is_deleted == False,
                TblProd01.T_DELETED != True  # Exclude deleted Prod01 records
            )
        )
        .distinct()
    ).all()

    # Logic: Format for dropdown (Remove decimals)
    clean_formulas = []
    for f in formulas:
        if f is not None:
            try:
                val = int(f)
                clean_formulas.append(str(val))
            except:
                clean_formulas.append(str(f))

    formula_list = sorted(list(set(clean_formulas)))

    return {
        "machines": ["All"] + list(machines),
        "products": ["All"] + list(products),
        "formulas": ["All"] + formula_list
    }


def calculate_duration_hours(start, end):
    if not isinstance(start, time) or not isinstance(end, time): return None
    dummy_date = date(2000, 1, 1)
    dt_start = datetime.combine(dummy_date, start)
    dt_end = datetime.combine(dummy_date, end)
    if dt_end < dt_start: dt_end += timedelta(days=1)
    total_seconds = (dt_end - dt_start).total_seconds()
    return total_seconds / 3600.0 if total_seconds > 0 else None


def calculate_duration_minutes(start, end):
    hours = calculate_duration_hours(start, end)
    return hours * 60 if hours is not None else None


def get_benchmark_data(session: Session, filters: dict):
    # 1. Query
    query = (
        select(
            MixerHeader.date,
            MixerHeader.reference_no,
            MixerMachine.name.label("machine_name"),
            MixerDetail.product_code,
            MixerDetail.lot_no,
            TblProd01.T_FID.label("formula_no"),
            TblProd01.T_QTYREQ.label("qty_required"),
            MixerDetail.output_qty,
            MixerDetail.process_time_start,
            MixerDetail.process_time_end,
            MixerDetail.cleaning_time_start,
            MixerDetail.cleaning_time_end,
            MixerDetail.cleaning_qty
        )
        .join(MixerHeader, MixerDetail.mixer_header_id == MixerHeader.id)
        .join(MixerMachine, MixerDetail.mc_id == MixerMachine.id)
        # --- FIXED JOIN ---
        # Outer join to TblProd01 BUT only if it is NOT deleted.
        # This prevents deleted history from TblProd01 from attaching to active Mixer records
        # and prevents duplication if multiple Prod01 records exist (one active, one deleted).
        .outerjoin(TblProd01, and_(
            MixerDetail.lot_no == TblProd01.T_LOTNUM,
            TblProd01.T_DELETED != True
        ))
        .where(
            and_(
                MixerDetail.is_deleted == False,
                MixerHeader.date.between(filters["date_from"], filters["date_to"])
            )
        )
    )

    if filters.get("machine") and filters["machine"] != "All":
        query = query.where(MixerMachine.name == filters["machine"])
    if filters.get("product_code") and filters["product_code"] != "All":
        query = query.where(MixerDetail.product_code == filters["product_code"])

    # Specific Formula Filter
    if filters.get("formula_no") and filters["formula_no"] != "All":
        query = query.where(TblProd01.T_FID.cast(str).like(f"{filters['formula_no']}%"))

    query = query.order_by(MixerHeader.date.desc())
    df = pd.read_sql(query, session.bind)

    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 2. Pre-processing & Filtering

    # --- FORMULA PROCESSING ---
    df["fid_temp"] = pd.to_numeric(df["formula_no"], errors='coerce')

    # Masks
    is_zero = df["fid_temp"] == 0
    is_null = df["fid_temp"].isna()
    is_specified = (~is_zero) & (~is_null)

    # Apply Checkbox Logic
    keep_mask = is_specified.copy()

    if filters.get("include_zero", True):
        keep_mask = keep_mask | is_zero

    if filters.get("include_null", True):
        keep_mask = keep_mask | is_null

    df = df[keep_mask].copy()

    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # --- FORMATTING (Remove Decimals) ---
    def format_formula(val):
        if pd.isna(val):
            return "Unspecified"
        return str(int(val))

    df["formula_no"] = df["fid_temp"].apply(format_formula)
    df.drop(columns=["fid_temp"], inplace=True)

    # 3. Calc Metrics (Rounded)
    df["proc_hours"] = df.apply(lambda x: calculate_duration_hours(x["process_time_start"], x["process_time_end"]),
                                axis=1)
    df["output_rate_hr"] = df.apply(
        lambda x: (x["output_qty"] / x["proc_hours"]) if (x["proc_hours"] and x["proc_hours"] > 0) else 0,
        axis=1
    ).round(2)

    df["cleaning_mins"] = df.apply(
        lambda x: calculate_duration_minutes(x["cleaning_time_start"], x["cleaning_time_end"]),
        axis=1
    ).fillna(0).round(2)

    df["cleaning_qty"] = df["cleaning_qty"].fillna(0).round(2)

    df["yield_pct"] = df.apply(
        lambda x: (x["output_qty"] / x["qty_required"] * 100) if (
                    x["qty_required"] and x["qty_required"] > 0) else np.nan,
        axis=1
    ).round(2)

    # 4. Aggregation
    group_cols = ["product_code", "machine_name", "formula_no"]

    summary = df.groupby(group_cols).agg(
        record_count=("output_qty", "count"),
        avg_output_rate=("output_rate_hr", "mean"),
        avg_yield=("yield_pct", "mean")
    ).reset_index()

    # Conditional Aggregation (Cleaning)
    valid_clean_time_df = df[df["cleaning_mins"] > 0]
    if not valid_clean_time_df.empty:
        clean_time_stats = valid_clean_time_df.groupby(group_cols)["cleaning_mins"].agg(
            avg_clean_time="mean").reset_index()
        summary = pd.merge(summary, clean_time_stats, on=group_cols, how="left")
    else:
        summary["avg_clean_time"] = 0

    valid_clean_mat_df = df[df["cleaning_qty"] > 0]
    if not valid_clean_mat_df.empty:
        clean_mat_stats = valid_clean_mat_df.groupby(group_cols)["cleaning_qty"].agg(avg_clean_mat="mean").reset_index()
        summary = pd.merge(summary, clean_mat_stats, on=group_cols, how="left")
    else:
        summary["avg_clean_mat"] = 0

    summary[["avg_clean_time", "avg_clean_mat"]] = summary[["avg_clean_time", "avg_clean_mat"]].fillna(0)
    summary = summary.round(2)

    # 5. Split Summary (Valid vs Unspecified Yield)
    summary_valid = summary[summary["avg_yield"].notna()].copy()
    summary_invalid = summary[summary["avg_yield"].isna()].copy()

    return summary_valid, summary_invalid, df