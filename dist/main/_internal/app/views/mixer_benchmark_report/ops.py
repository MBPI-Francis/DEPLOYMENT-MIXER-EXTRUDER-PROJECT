import pandas as pd
import numpy as np
import re
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from datetime import datetime, date, timedelta, time

# Import cast and String inside function or at top
from sqlalchemy import cast, String

# Import Models
from models import MixerDetail, MixerHeader, MixerMachine, TblProd01


# --- HELPER: LOT PARSER ---
def parse_lot(lot_str):
    """
    Parses a lot string into (start_num, end_num, suffix).
    Returns None if invalid.
    """
    if not isinstance(lot_str, str) or not lot_str:
        return None

    lot_str = lot_str.strip().upper()
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

        if start_suf != end_suf: return None
        if end_num < start_num: return None  # Invalid range

        return (start_num, end_num, start_suf)
    else:
        m = re.match(pattern, lot_str)
        if not m: return None
        return (int(m.group(1)), int(m.group(1)), m.group(2))


# --- HELPERS: TIME ---
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


# --- OPTIMIZED FILTER OPTIONS ---
def get_filter_options(session: Session):
    """
    Only loads Machines and Products initially.
    Formulas are now loaded asynchronously via search_formulas to prevent lag.
    """
    machines = session.scalars(
        select(MixerMachine.name).where(MixerMachine.is_deleted == False).order_by(MixerMachine.name)).all()
    products = session.scalars(select(MixerDetail.product_code).distinct().order_by(MixerDetail.product_code)).all()

    # NOTE: We DO NOT load formulas here anymore. It's too heavy.

    return {
        "machines": ["All"] + list(machines),
        "products": ["All"] + list(products)
    }


# --- NEW: LIVE SEARCH FUNCTION ---
# def search_formulas(session: Session, search_term: str):
#     """
#     Searches TblProd01 for formulas matching the term.
#     Limits results to 50 to ensure high performance.
#     """
#     if not search_term:
#         return []
#
#     # Clean the term
#     term = search_term.strip()
#
#     # Query distinct formulas from TblProd01
#     # We cast to TEXT to allow string searching (LIKE '10%')
#     query = (
#         select(TblProd01.T_FID)
#         .where(
#             and_(
#                 TblProd01.T_DELETED != True,
#                 # Cast integer ID to string for searching
#                 cast(TblProd01.T_FID, String).like(f"{term}%")
#             )
#         )
#         .distinct()
#         .limit(50)  # Limit is crucial for performance
#     )
#
#
#     results = session.scalars(query).all()
#
#     # Format results (remove decimals)
#     clean_results = []
#     for r in results:
#         if r is not None and r != 0:
#             try:
#                 clean_results.append(str(int(r)))
#             except:
#                 clean_results.append(str(r))
#
#     return sorted(list(set(clean_results)))


# --- UPDATED SEARCH FUNCTION ---
def search_formulas(session: Session, search_term: str):
    """
    Searches formulas. If search_term is empty, returns the first 50 results.
    """
    query = select(TblProd01.T_FID).where(TblProd01.T_DELETED != True).distinct()

    if search_term:
        term = search_term.strip()
        query = query.where(cast(TblProd01.T_FID, String).like(f"{term}%"))

    # Always limit to prevents lag
    query = query.limit(50)

    results = session.scalars(query).all()

    clean_results = []
    for r in results:
        if r is not None and r != 0:
            try:
                clean_results.append(str(int(r)))
            except:
                clean_results.append(str(r))

    return sorted(list(set(clean_results)))


def get_benchmark_data(session: Session, filters: dict):
    # -------------------------------------------------------
    # STEP 1: Fetch Base Mixer Data
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

    # Lookup Structure: lookup[product][suffix] = [Range Objects]
    prod_lookup = {}

    for rec in prod_records:
        p_code = rec.T_PRODCODE
        raw_lot = rec.T_LOTNUM

        parsed = parse_lot(raw_lot)
        if not parsed: continue

        start, end, suffix = parsed

        # Calculate Unit Batch Weight (Weight for 1 Lot)
        unit_weight = float(rec.T_QTYBATCH or 0)

        if p_code not in prod_lookup: prod_lookup[p_code] = {}
        if suffix not in prod_lookup[p_code]: prod_lookup[p_code][suffix] = []

        prod_lookup[p_code][suffix].append({
            "start": start,
            "end": end,
            "fid": rec.T_FID,
            "unit_weight": unit_weight
        })

    # -------------------------------------------------------
    # STEP 3: Advanced Resolution (Split by ; and Sum Ranges)
    # -------------------------------------------------------

    def resolve_row(row):
        res = {
            "formula_no": "Unspecified",
            "expected_output": 0.0,
            "yield_pct": np.nan
        }

        mixer_lot_full_str = row["lot_no"]
        p_code = row["product_code"]
        actual_output = row["output_qty"]

        # --- NEW LOGIC: Split by semicolon for combined lots ---
        # e.g., "1001AN-1003AN; 2001AN" -> ["1001AN-1003AN", "2001AN"]
        lot_segments = [s.strip() for s in mixer_lot_full_str.split(';') if s.strip()]

        if not lot_segments:
            return pd.Series(res)

        total_expected_output = 0.0
        found_formulas = set()

        # Process each segment
        for segment in lot_segments:
            parsed_mix = parse_lot(segment)
            if not parsed_mix: continue

            m_start, m_end, m_suffix = parsed_mix

            # Check lookup for this segment
            if p_code in prod_lookup and m_suffix in prod_lookup[p_code]:
                candidates = prod_lookup[p_code][m_suffix]

                # Iterate EVERY LOT number in this segment (e.g. 1001, 1002, 1003)
                # to find its specific parent range and add its specific weight
                for current_lot_num in range(m_start, m_end + 1):

                    matched = False
                    for cand in candidates:
                        if cand["start"] <= current_lot_num <= cand["end"]:
                            # Found the source record for this specific lot
                            total_expected_output += cand["unit_weight"]

                            if cand["fid"]:
                                found_formulas.add(int(cand["fid"]))

                            matched = True
                            break

                            # If not matched, we add 0 for that lot (it's missing in Prod01)

        # Finalize Data for this Row
        res["expected_output"] = total_expected_output

        # Determine Formula Label
        if len(found_formulas) == 1:
            res["formula_no"] = str(list(found_formulas)[0])
        elif len(found_formulas) > 1:
            sorted_f = sorted(list(found_formulas))
            res["formula_no"] = "; ".join([str(f) for f in sorted_f])
        else:
            res["formula_no"] = "Unspecified"

        # Compute Yield
        if total_expected_output > 0:
            res["yield_pct"] = (actual_output / total_expected_output) * 100

        return pd.Series(res)

    resolved_data = df.apply(resolve_row, axis=1)
    df = pd.concat([df, resolved_data], axis=1)

    # -------------------------------------------------------
    # STEP 4: Standard Metrics Calc
    # -------------------------------------------------------
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

    df["yield_pct"] = df["yield_pct"].round(2)

    # -------------------------------------------------------
    # STEP 5: Filtering & Aggregation
    # -------------------------------------------------------

    # Formula Filter
    if filters.get("formula_no") and filters["formula_no"] != "All":
        df = df[df["formula_no"].astype(str).str.contains(filters["formula_no"])]

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
        avg_yield=("yield_pct", "mean")
    ).reset_index()

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

    # Split (Valid Yield if > 0)
    summary_valid = summary[summary["avg_yield"] > 0].copy()
    summary_invalid = summary[summary["avg_yield"] == 0].copy()

    return summary_valid, summary_invalid, df
