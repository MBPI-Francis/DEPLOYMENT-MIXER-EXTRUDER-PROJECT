# app/views/extruder_benchmark_report/ops.py

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, cast, String
from datetime import datetime, time

from models.ViewModels import ViewExtruderSummary


def get_filter_options(session: Session):
    machines = session.scalars(
        select(ViewExtruderSummary.machine_number).distinct().order_by(ViewExtruderSummary.machine_number)).all()
    products = session.scalars(
        select(ViewExtruderSummary.product_code).distinct().order_by(ViewExtruderSummary.product_code)).all()
    formulas = session.scalars(select(ViewExtruderSummary.formula_number).distinct()).all()

    clean_formulas = []
    for f in formulas:
        if f is not None:
            try:
                val = float(f)
                if val.is_integer():
                    clean_formulas.append(str(int(val)))
                else:
                    clean_formulas.append(str(f))
            except:
                clean_formulas.append(str(f))

    formula_list = sorted(list(set(clean_formulas)))

    return {
        "machines": ["All"] + [m for m in machines if m],
        "products": ["All"] + [p for p in products if p],
        "formulas": ["All"] + formula_list
    }


def get_benchmark_data(session: Session, filters: dict):
    # 1. Base Query
    query = select(ViewExtruderSummary)

    # 2. Date Filter (using time_start from view)
    start_dt = datetime.combine(filters["date_from"], time.min)
    end_dt = datetime.combine(filters["date_to"], time.max)
    query = query.where(ViewExtruderSummary.time_start.between(start_dt, end_dt))

    # 3. Dropdown Filters
    if filters.get("machine") and filters["machine"] != "All":
        query = query.where(ViewExtruderSummary.machine_number == filters["machine"])
    if filters.get("product_code") and filters["product_code"] != "All":
        query = query.where(ViewExtruderSummary.product_code == filters["product_code"])
    if filters.get("formula_no") and filters["formula_no"] != "All":
        query = query.where(cast(ViewExtruderSummary.formula_number, String) == filters["formula_no"])

    df = pd.read_sql(query, session.bind)

    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # ---------------------------------------------------------
    # PRE-PROCESSING
    # ---------------------------------------------------------

    # Clean Formula
    def clean_formula_str(val):
        if val is None: return np.nan
        try:
            f_float = float(val)
            if f_float.is_integer(): return int(f_float)
            return val
        except:
            return val

    df["fid_temp"] = df["formula_number"].apply(clean_formula_str)

    # Checkbox Logic
    is_zero = df["fid_temp"] == 0
    is_null = df["fid_temp"].isna() | (df["fid_temp"] == "")
    is_specified = (~is_zero) & (~is_null)

    keep_mask = is_specified.copy()
    if filters.get("include_zero", True): keep_mask = keep_mask | is_zero
    if filters.get("include_null", True): keep_mask = keep_mask | is_null

    df = df[keep_mask].copy()

    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def final_formula_label(val):
        if pd.isna(val) or val == "": return "Unspecified"
        return str(val)

    df["formula_number"] = df["fid_temp"].apply(final_formula_label)

    # Ensure Numeric Columns
    cols_to_numeric = [
        "output_per_hour", "purging_duration_minutes",
        "total_cleaning_material", "yield_value", "expected_output"
    ]
    for col in cols_to_numeric:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

    # Round Raw Data
    df["output_per_hour"] = df["output_per_hour"].round(2)
    df["purging_duration_minutes"] = df["purging_duration_minutes"].round(2)
    df["total_cleaning_material"] = df["total_cleaning_material"].round(2)
    df["yield_value"] = df["yield_value"].round(2)

    # ---------------------------------------------------------
    # AGGREGATION
    # ---------------------------------------------------------
    group_cols = ["product_code", "machine_number", "formula_number"]

    # 1. Main Stats (Output)
    summary = df.groupby(group_cols).agg(
        record_count=("form_id", "count"),
        avg_output_rate=("output_per_hour", "mean"),
        std_output_rate=("output_per_hour", "std")
    ).reset_index()

    # 2. Cleaning Time Stats (Only > 0)
    valid_time = df[df["purging_duration_minutes"] > 0]
    if not valid_time.empty:
        time_stats = valid_time.groupby(group_cols)["purging_duration_minutes"].agg(
            avg_purge_mins="mean", std_purge_mins="std"
        ).reset_index()
        summary = pd.merge(summary, time_stats, on=group_cols, how="left")
    else:
        summary["avg_purge_mins"] = 0;
        summary["std_purge_mins"] = 0

    # 3. Cleaning Material Stats (Only > 0) - NEW
    valid_mat = df[df["total_cleaning_material"] > 0]
    if not valid_mat.empty:
        mat_stats = valid_mat.groupby(group_cols)["total_cleaning_material"].agg(
            avg_purge_mat="mean", std_purge_mat="std"
        ).reset_index()
        summary = pd.merge(summary, mat_stats, on=group_cols, how="left")
    else:
        summary["avg_purge_mat"] = 0;
        summary["std_purge_mat"] = 0

    # 4. Yield Stats (Only where expected_output > 0) - NEW
    valid_yield = df[df["expected_output"] > 0]
    if not valid_yield.empty:
        yield_stats = valid_yield.groupby(group_cols)["yield_value"].agg(
            avg_yield="mean", std_yield="std"
        ).reset_index()
        summary = pd.merge(summary, yield_stats, on=group_cols, how="left")
    else:
        summary["avg_yield"] = np.nan;
        summary["std_yield"] = 0

    # Fill NaNs for stats
    summary[["avg_purge_mins", "std_purge_mins", "avg_purge_mat", "std_purge_mat", "std_output_rate", "std_yield"]] = \
        summary[["avg_purge_mins", "std_purge_mins", "avg_purge_mat", "std_purge_mat", "std_output_rate",
                 "std_yield"]].fillna(0)

    summary = summary.round(2)

    # ---------------------------------------------------------
    # SPLIT VALID vs UNSPECIFIED YIELDS
    # ---------------------------------------------------------
    # If avg_yield is NaN (meaning all records in group had 0 expected output), it goes to invalid
    summary_valid = summary[summary["avg_yield"].notna()].copy()
    summary_invalid = summary[summary["avg_yield"].isna()].copy()

    return summary_valid, summary_invalid, df