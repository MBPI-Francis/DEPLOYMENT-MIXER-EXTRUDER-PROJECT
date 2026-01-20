import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, func
from datetime import datetime, date, timedelta, time

# Import Extruder Models
from models import (
    ExtruderFormData, ExtruderMachine, ExtruderOutput,
    PurgingHeader, PurgingDetail
)


def get_filter_options(session: Session):
    machines = session.scalars(
        select(ExtruderMachine.name).where(ExtruderMachine.is_deleted == False).order_by(ExtruderMachine.name)).all()
    products = session.scalars(
        select(ExtruderFormData.product_code).where(ExtruderFormData.is_deleted == False).distinct().order_by(
            ExtruderFormData.product_code)).all()
    formulas = session.scalars(
        select(ExtruderFormData.formula_no).where(ExtruderFormData.is_deleted == False).distinct()).all()

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
        "machines": ["All"] + list(machines),
        "products": ["All"] + list(products),
        "formulas": ["All"] + formula_list
    }


def calculate_duration_hours(start, end):
    if not isinstance(start, datetime) or not isinstance(end, datetime): return 0.0
    delta = end - start
    total_seconds = delta.total_seconds()
    return total_seconds / 3600.0 if total_seconds > 0 else 0.0


def calculate_time_diff_minutes(t_start, t_end):
    if not isinstance(t_start, time) or not isinstance(t_end, time): return 0.0
    dummy_date = date(2000, 1, 1)
    dt_start = datetime.combine(dummy_date, t_start)
    dt_end = datetime.combine(dummy_date, t_end)
    if dt_end < dt_start: dt_end += timedelta(days=1)
    delta = dt_end - dt_start
    return delta.total_seconds() / 60.0


def get_benchmark_data(session: Session, filters: dict):
    # 1. Find relevant IDs
    relevant_ids_stmt = (
        select(ExtruderOutput.extruder_form_data_id)
        .where(func.date(ExtruderOutput.datetime_start).between(filters["date_from"], filters["date_to"]))
        .distinct()
    )
    relevant_ids = session.scalars(relevant_ids_stmt).all()

    if not relevant_ids:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 2. Fetch Forms
    q_forms = (
        select(
            ExtruderFormData.id,
            ExtruderFormData.ref_no,
            ExtruderFormData.product_code,
            ExtruderFormData.formula_no,
            ExtruderFormData.qty_order,
            ExtruderFormData.qty_produced,  # Yield Denom
            ExtruderFormData.lot_number,
            ExtruderMachine.name.label("machine_name")
        )
        .join(ExtruderMachine, ExtruderFormData.machine_id == ExtruderMachine.id)
        .where(
            and_(
                ExtruderFormData.id.in_(relevant_ids),
                ExtruderFormData.is_deleted == False
            )
        )
    )

    if filters.get("machine") and filters["machine"] != "All":
        q_forms = q_forms.where(ExtruderMachine.name == filters["machine"])
    if filters.get("product_code") and filters["product_code"] != "All":
        q_forms = q_forms.where(ExtruderFormData.product_code == filters["product_code"])
    if filters.get("formula_no") and filters["formula_no"] != "All":
        q_forms = q_forms.where(ExtruderFormData.formula_no == filters["formula_no"])

    df_forms = pd.read_sql(q_forms, session.bind)
    if df_forms.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    final_form_ids = df_forms["id"].tolist()

    # 3. Fetch Children
    q_outputs = select(ExtruderOutput.extruder_form_data_id.label("id"), ExtruderOutput.qty_output,
                       ExtruderOutput.datetime_start, ExtruderOutput.datetime_end).where(
        ExtruderOutput.extruder_form_data_id.in_(final_form_ids))
    df_outputs = pd.read_sql(q_outputs, session.bind)

    q_purge_head = select(PurgingHeader.extruder_form_data_id.label("id"), PurgingHeader.time_start,
                          PurgingHeader.time_end).where(PurgingHeader.extruder_form_data_id.in_(final_form_ids))
    df_purge_head = pd.read_sql(q_purge_head, session.bind)

    q_purge_det = select(PurgingHeader.extruder_form_data_id.label("id"), PurgingDetail.qty).join(PurgingHeader,
                                                                                                  PurgingDetail.purging_header_id == PurgingHeader.id).where(
        PurgingHeader.extruder_form_data_id.in_(final_form_ids))
    df_purge_det = pd.read_sql(q_purge_det, session.bind)

    # 4. Aggregation
    if not df_outputs.empty:
        df_outputs["duration_hr"] = df_outputs.apply(
            lambda x: calculate_duration_hours(x["datetime_start"], x["datetime_end"]), axis=1)
        df_outputs["date_val"] = pd.to_datetime(df_outputs["datetime_start"]).dt.date
        output_agg = df_outputs.groupby("id").agg(
            total_output_qty=("qty_output", "sum"),
            total_proc_hours=("duration_hr", "sum"),
            report_date=("date_val", "min")
        ).reset_index()
    else:
        output_agg = pd.DataFrame(columns=["id", "total_output_qty", "total_proc_hours", "report_date"])

    if not df_purge_head.empty:
        df_purge_head["clean_mins"] = df_purge_head.apply(
            lambda x: calculate_time_diff_minutes(x["time_start"], x["time_end"]), axis=1)
        purge_time_agg = df_purge_head.groupby("id")["clean_mins"].sum().reset_index()
    else:
        purge_time_agg = pd.DataFrame(columns=["id", "clean_mins"])

    if not df_purge_det.empty:
        purge_mat_agg = df_purge_det.groupby("id")["qty"].sum().reset_index()
    else:
        purge_mat_agg = pd.DataFrame(columns=["id", "qty"])

    # 5. Merge & Handle Columns Safely
    df = pd.merge(df_forms, output_agg, on="id", how="left")
    df = pd.merge(df, purge_time_agg, on="id", how="left")
    df = pd.merge(df, purge_mat_agg, on="id", how="left")

    # --- FIXED COLUMN HANDLING ---
    # 1. Rename 'qty' to 'clean_mat' if it exists (from purge_mat_agg)
    if "qty" in df.columns:
        df.rename(columns={"qty": "clean_mat"}, inplace=True)
    else:
        df["clean_mat"] = 0.0  # Create if missing

    # 2. Ensure other columns exist
    if "clean_mins" not in df.columns: df["clean_mins"] = 0.0
    if "total_output_qty" not in df.columns: df["total_output_qty"] = 0.0
    if "total_proc_hours" not in df.columns: df["total_proc_hours"] = 0.0

    # 3. Fill NaNs now that columns definitively exist
    fill_cols = ["total_output_qty", "total_proc_hours", "clean_mins", "clean_mat"]
    df[fill_cols] = df[fill_cols].fillna(0)

    # 6. Calculations (Rounded)
    df["output_rate_hr"] = df.apply(
        lambda x: (x["total_output_qty"] / x["total_proc_hours"]) if x["total_proc_hours"] > 0 else 0, axis=1).round(2)

    df["yield_pct"] = df.apply(lambda x: (x["total_output_qty"] / x["qty_produced"] * 100) if (
                x["qty_produced"] and x["qty_produced"] > 0) else np.nan, axis=1).round(2)

    df["clean_mins"] = df["clean_mins"].round(2)
    df["clean_mat"] = df["clean_mat"].round(2)

    # 7. Formula Filtering
    def clean_formula_str(val):
        if val is None: return np.nan
        try:
            f_float = float(val)
            if f_float.is_integer(): return int(f_float)
            return val
        except:
            return val

    df["fid_temp"] = df["formula_no"].apply(clean_formula_str)

    is_zero = df["fid_temp"] == 0
    is_null = df["fid_temp"].isna() | (df["fid_temp"] == "")
    is_specified = (~is_zero) & (~is_null)

    keep_mask = is_specified.copy()
    if filters.get("include_zero", True): keep_mask = keep_mask | is_zero
    if filters.get("include_null", True): keep_mask = keep_mask | is_null

    df = df[keep_mask].copy()
    if df.empty: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    def final_formula_label(val):
        if pd.isna(val) or val == "": return "Unspecified"
        return str(val)

    df["formula_no"] = df["fid_temp"].apply(final_formula_label)

    # 8. Aggregation
    group_cols = ["product_code", "machine_name", "formula_no"]
    summary = df.groupby(group_cols).agg(
        record_count=("total_output_qty", "count"),
        avg_output_rate=("output_rate_hr", "mean"),
        avg_yield=("yield_pct", "mean")
    ).reset_index()

    valid_ct = df[df["clean_mins"] > 0]
    if not valid_ct.empty:
        ct_stats = valid_ct.groupby(group_cols)["clean_mins"].agg(avg_clean_time="mean").reset_index()
        summary = pd.merge(summary, ct_stats, on=group_cols, how="left")
    else:
        summary["avg_clean_time"] = 0

    valid_cm = df[df["clean_mat"] > 0]
    if not valid_cm.empty:
        cm_stats = valid_cm.groupby(group_cols)["clean_mat"].agg(avg_clean_mat="mean").reset_index()
        summary = pd.merge(summary, cm_stats, on=group_cols, how="left")
    else:
        summary["avg_clean_mat"] = 0

    summary[["avg_clean_time", "avg_clean_mat"]] = summary[["avg_clean_time", "avg_clean_mat"]].fillna(0)
    summary = summary.round(2)

    summary_valid = summary[summary["avg_yield"].notna()].copy()
    summary_invalid = summary[summary["avg_yield"].isna()].copy()

    return summary_valid, summary_invalid, df