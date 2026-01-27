import pandas as pd
import numpy as np
import re
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from datetime import datetime, date, timedelta, time

# Import Models
from models import MixerDetail, MixerHeader, MixerMachine, TblProd01


# --- HELPER: LOT PARSER ---
def parse_lot(lot_str):
    """
    Parses a lot string into (start_num, end_num, suffix).
    Examples:
      "1004AN" -> (1004, 1004, "AN")
      "1001AN-1005AN" -> (1001, 1005, "AN")
    Returns None if invalid.
    """
    if not isinstance(lot_str, str) or not lot_str:
        return None

    lot_str = lot_str.strip().upper()

    # Regex to capture Number and Suffix
    # Matches "1001" and "AN"
    pattern = r'^(\d+)([A-Z]*)$'

    if '-' in lot_str:
        parts = lot_str.split('-')
        if len(parts) != 2: return None

        start_part, end_part = parts[0].strip(), parts[1].strip()

        m_start = re.match(pattern, start_part)
        m_end = re.match(pattern, end_part)

        if not m_start or not m_end: return None

        start_num, start_suf = int(m_start.group(1)), m_start.group(2)
        end_num, end_suf = int(m_end.group(1)), m_end.group(2)

        # Suffixes must match (e.g. 1001AN-1005AN)
        if start_suf != end_suf: return None

        return (start_num, end_num, start_suf)
    else:
        # Single lot
        m = re.match(pattern, lot_str)
        if not m: return None
        return (int(m.group(1)), int(m.group(1)), m.group(2))


# --- HELPER: DURATION CALCS ---
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


def get_filter_options(session: Session):
    # Standard filter fetching
    machines = session.scalars(
        select(MixerMachine.name).where(MixerMachine.is_deleted == False).order_by(MixerMachine.name)).all()
    products = session.scalars(select(MixerDetail.product_code).distinct().order_by(MixerDetail.product_code)).all()

    # We fetch formulas directly from TblProd01 for the dropdown
    # (Checking distinct FIDs that exist)
    formulas = session.scalars(
        select(TblProd01.T_FID)
        .where(TblProd01.T_DELETED != True)
        .distinct()
    ).all()

    clean_formulas = []
    for f in formulas:
        if f is not None and f != 0:
            clean_formulas.append(str(int(f)))  # Remove decimals

    formula_list = sorted(list(set(clean_formulas)))

    return {
        "machines": ["All"] + list(machines),
        "products": ["All"] + list(products),
        "formulas": ["All"] + formula_list
    }


def get_benchmark_data(session: Session, filters: dict):
    # -------------------------------------------------------
    # STEP 1: Fetch Base Mixer Data (No Joins to Prod01 yet)
    # -------------------------------------------------------
    query = (
        select(
            MixerHeader.date,
            MixerHeader.reference_no,
            MixerMachine.name.label("machine_name"),
            MixerDetail.product_code,
            MixerDetail.lot_no,
            MixerDetail.output_qty,
            MixerDetail.process_time_start,
            MixerDetail.process_time_end,
            MixerDetail.cleaning_time_start,
            MixerDetail.cleaning_time_end,
            MixerDetail.cleaning_qty
        )
        .join(MixerHeader, MixerDetail.mixer_header_id == MixerHeader.id)
        .join(MixerMachine, MixerDetail.mc_id == MixerMachine.id)
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

    query = query.order_by(MixerHeader.date.desc())
    df = pd.read_sql(query, session.bind)

    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # -------------------------------------------------------
    # STEP 2: Build Lookup Cache from TblProd01
    # -------------------------------------------------------
    # We only fetch Prod01 records for the Product Codes present in our Mixer Data
    unique_products = df["product_code"].unique().tolist()

    prod_query = (
        select(
            TblProd01.T_PRODCODE,
            TblProd01.T_LOTNUM,
            TblProd01.T_FID,
            TblProd01.T_QTYBATCH,
            TblProd01.T_QTYPROD
        )
        .where(
            and_(
                TblProd01.T_PRODCODE.in_(unique_products),
                TblProd01.T_DELETED != True
            )
        )
    )

    prod_records = session.execute(prod_query).all()

    # Organize into Dictionary: lookup[prod_code][suffix] = [List of Ranges]
    # This makes searching O(N) instead of O(N^2)
    prod_lookup = {}

    for rec in prod_records:
        p_code = rec.T_PRODCODE
        raw_lot = rec.T_LOTNUM

        parsed = parse_lot(raw_lot)
        if not parsed: continue

        start, end, suffix = parsed

        if p_code not in prod_lookup: prod_lookup[p_code] = {}
        if suffix not in prod_lookup[p_code]: prod_lookup[p_code][suffix] = []

        prod_lookup[p_code][suffix].append({
            "start": start,
            "end": end,
            "fid": rec.T_FID,
            "qty_batch": float(rec.T_QTYBATCH or 0),
            "qty_prod": float(rec.T_QTYPROD or 0)
        })

    # -------------------------------------------------------
    # STEP 3: Resolve Formula & Yield Row-by-Row
    # -------------------------------------------------------

    def resolve_row(row):
        # Default Returns
        res = {
            "formula_no": "Unspecified",
            "expected_output": 0.0,
            "yield_pct": np.nan
        }

        mixer_lot_str = row["lot_no"]
        p_code = row["product_code"]
        actual_output = row["output_qty"]

        # Parse Mixer Lot
        parsed_mix = parse_lot(mixer_lot_str)
        if not parsed_mix: return pd.Series(res)

        m_start, m_end, m_suffix = parsed_mix

        # Check Lookup
        if p_code in prod_lookup and m_suffix in prod_lookup[p_code]:
            candidates = prod_lookup[p_code][m_suffix]

            # Find the Parent Range
            for cand in candidates:
                # Logic: Mixer Range must be INSIDE Parent Range
                if m_start >= cand["start"] and m_end <= cand["end"]:

                    # 1. Get Formula
                    try:
                        res["formula_no"] = str(int(cand["fid"]))
                    except:
                        res["formula_no"] = str(cand["fid"]) if cand["fid"] else "Unspecified"

                    # 2. Compute Qty Per Lot (The Validation Logic)
                    t_qty_prod = cand["qty_prod"]
                    t_qty_batch = cand["qty_batch"]

                    if t_qty_batch > 0:
                        # Round to nearest whole number as per requirement
                        expected_lots_in_prod = round(t_qty_prod / t_qty_batch)
                        actual_lots_in_prod = (cand["end"] - cand["start"]) + 1

                        # Validate: If counts match (or logic says we trust T_QTYBATCH)
                        # We assume T_QTYBATCH is the weight of ONE lot

                        # 3. Compute Expected Output for Mixer Record
                        mixer_lot_count = (m_end - m_start) + 1
                        expected_output = mixer_lot_count * t_qty_batch
                        res["expected_output"] = expected_output

                        # 4. Compute Yield
                        if expected_output > 0:
                            res["yield_pct"] = (actual_output / expected_output) * 100

                    break  # Stop after finding the first valid match

        return pd.Series(res)

    # Apply the Resolver
    resolved_data = df.apply(resolve_row, axis=1)
    df = pd.concat([df, resolved_data], axis=1)

    # -------------------------------------------------------
    # STEP 4: Standard Metrics Calc
    # -------------------------------------------------------

    # Output Rate
    df["proc_hours"] = df.apply(lambda x: calculate_duration_hours(x["process_time_start"], x["process_time_end"]),
                                axis=1)
    df["output_rate_hr"] = df.apply(
        lambda x: (x["output_qty"] / x["proc_hours"]) if (x["proc_hours"] and x["proc_hours"] > 0) else 0,
        axis=1
    ).round(2)

    # Cleaning
    df["cleaning_mins"] = df.apply(
        lambda x: calculate_duration_minutes(x["cleaning_time_start"], x["cleaning_time_end"]),
        axis=1
    ).fillna(0).round(2)
    df["cleaning_qty"] = df["cleaning_qty"].fillna(0).round(2)

    # Round Yield
    df["yield_pct"] = df["yield_pct"].round(2)

    # -------------------------------------------------------
    # STEP 5: Filtering & Aggregation
    # -------------------------------------------------------

    # Formula Filtering (Post-Resolution)
    if filters.get("formula_no") and filters["formula_no"] != "All":
        df = df[df["formula_no"] == filters["formula_no"]]

    # Checkbox Filters
    is_zero = df["formula_no"] == "0"
    is_unspec = df["formula_no"] == "Unspecified"
    is_specified = (~is_zero) & (~is_unspec)

    keep_mask = is_specified.copy()
    if filters.get("include_zero", True): keep_mask = keep_mask | is_zero
    if filters.get("include_null", True): keep_mask = keep_mask | is_unspec

    df = df[keep_mask].copy()

    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # Aggregation
    group_cols = ["product_code", "machine_name", "formula_no"]

    summary = df.groupby(group_cols).agg(
        record_count=("output_qty", "count"),
        avg_output_rate=("output_rate_hr", "mean"),
        avg_yield=("yield_pct", "mean")  # Ignores NaNs automatically
    ).reset_index()

    # Clean Stats
    valid_ct = df[df["cleaning_mins"] > 0]
    if not valid_ct.empty:
        ct_stats = valid_ct.groupby(group_cols)["cleaning_mins"].agg(avg_clean_time="mean").reset_index()
        summary = pd.merge(summary, ct_stats, on=group_cols, how="left")
    else:
        summary["avg_clean_time"] = 0

    valid_cm = df[df["cleaning_qty"] > 0]
    if not valid_cm.empty:
        cm_stats = valid_cm.groupby(group_cols)["cleaning_qty"].agg(avg_clean_mat="mean").reset_index()
        summary = pd.merge(summary, cm_stats, on=group_cols, how="left")
    else:
        summary["avg_clean_mat"] = 0

    summary = summary.fillna(0).round(2)

    # Split
    summary_valid = summary[summary["avg_yield"] > 0].copy()  # Yield > 0 means it was calculated
    summary_invalid = summary[summary["avg_yield"] == 0].copy()  # Yield 0 likely means no match or 0 expected

    # Re-verify invalid: If expected_output was 0, yield is NaN in logic but might be 0 here.
    # To be precise, check if we found a match.
    # Simpler: If avg_yield is 0, check if it's because output was 0 or expected was 0.
    # We'll stick to > 0 is valid.

    return summary_valid, summary_invalid, df