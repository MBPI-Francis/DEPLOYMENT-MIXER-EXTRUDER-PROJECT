# In app/views/mixer_records/ops.py

import pandas as pd
from sqlalchemy.orm import Session, aliased
from sqlalchemy import select, func, and_, cast, String, or_
from datetime import datetime, timedelta, date, time
from typing import List
import re  # Make sure re is imported

from models import MixerDetail, MixerHeader, MixerMachine, TblProd01
from app.database.legacy_ops import get_initial_lot_numbers, get_initial_product_codes, get_initial_raw_materials, \
    search_all_lot_numbers, search_all_product_codes, search_all_raw_materials, get_all_processed_by_names


# --- Helper function (as before, but now used by our batch function) ---
def _parse_lot_string(lot_str: str):
    lot_str = lot_str.strip().upper()
    part_regex = re.compile(r'^(\d+)([A-Z]+)$')
    if '-' in lot_str:
        parts = lot_str.split('-')
        if len(parts) != 2: return None
        start_part, end_part = parts
        start_match = part_regex.match(start_part)
        end_match = part_regex.match(end_part)
        if not start_match or not end_match: return None
        start_num, start_suffix = int(start_match.group(1)), start_match.group(2)
        end_num, end_suffix = int(end_match.group(1)), end_match.group(2)
        if start_suffix != end_suffix or end_num < start_num: return None
        return start_num, end_num, start_suffix
    else:
        match = part_regex.match(lot_str)
        if not match: return None
        num, suffix = int(match.group(1)), match.group(2)
        return num, num, suffix


# --- NEW: High-performance batch formula resolver ---
def _batch_resolve_formulas(session: Session, df: pd.DataFrame) -> pd.Series:
    """
    Performs a single, highly efficient batch lookup for all formula numbers
    in the provided DataFrame.
    """
    if df.empty:
        return pd.Series(dtype=str)

    unique_product_codes = df['Product Code'].unique()

    # 1. Perform ONE query to get all possible lot ranges for ALL product codes in the DataFrame.
    db_query = select(TblProd01.T_PRODCODE, TblProd01.T_LOTNUM, TblProd01.T_FID).where(
        TblProd01.T_PRODCODE.in_(unique_product_codes))
    all_db_records = session.execute(db_query).all()

    # 2. Build a fast lookup structure (a dictionary) in memory.
    formula_map = {}
    for p_code, lot_num, formula_id in all_db_records:
        if p_code not in formula_map:
            formula_map[p_code] = []
        parsed = _parse_lot_string(lot_num)
        if parsed:
            formula_map[p_code].append(
                {'start': parsed[0], 'end': parsed[1], 'suffix': parsed[2], 'formula': formula_id})

    # 3. Define the core logic to be applied to each row of the DataFrame.
    def resolve_row(row):
        p_code = row["Product Code"]
        user_lot_entry = row["Lot Number"]

        if not p_code or not user_lot_entry or p_code not in formula_map:
            return ""

        db_lot_ranges = formula_map[p_code]
        user_lot_tasks = [entry.strip() for entry in user_lot_entry.split(';') if entry.strip()]

        final_formulas_ordered = []
        for task_lot_str in user_lot_tasks:
            parsed_user_lot = _parse_lot_string(task_lot_str)
            if not parsed_user_lot: continue

            user_start, user_end, user_suffix = parsed_user_lot
            formulas_for_this_task = set()

            # Perform the lookup using the in-memory data (very fast)
            for db_lot in db_lot_ranges:
                if (db_lot['suffix'] == user_suffix and
                        db_lot['start'] <= user_end and
                        db_lot['end'] >= user_start):
                    formulas_for_this_task.add(str(db_lot['formula']))

            final_formulas_ordered.extend(sorted(list(formulas_for_this_task)))

        unique_ordered_formulas = []
        seen = set()
        for formula in final_formulas_ordered:
            if formula not in seen:
                unique_ordered_formulas.append(formula)
                seen.add(formula)

        return "; ".join(unique_ordered_formulas)

    # 4. Apply the fast, in-memory logic to the entire DataFrame at once.
    return df.apply(resolve_row, axis=1)


# Keep this function as it's used elsewhere
def calculate_duration(start_time, end_time):
    if not isinstance(start_time, time) or not isinstance(end_time, time): return None
    start_dt = datetime.combine(date.min, start_time)
    end_dt = datetime.combine(date.min, end_time)
    if end_dt < start_dt: end_dt += timedelta(days=1)
    delta = end_dt - start_dt
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


# --- MODIFIED get_mixer_report_data ---
def get_mixer_report_data(session: Session, filters: dict, offset: int = None, limit: int = None) -> pd.DataFrame:
    md = aliased(MixerDetail, name="md")
    mh = aliased(MixerHeader, name="mh")
    mm = aliased(MixerMachine, name="mm")

    query = (
        select(
            mh.date.label("Date"),
            mh.time_start.label("Shift Time Start"),
            mh.time_end.label("Shift Time End"),
            mh.reference_no.label("Ref No"),
            mm.name.label("MC #"),
            md.product_code.label("Product Code"),
            md.lot_no.label("Lot Number"),
            md.process_time_start.label("Processing Start"),
            md.process_time_end.label("Processing End"),
            md.processed_by.label("Processed By"),
            md.output_qty.label("Output QTY"),
            md.cleaning_time_start.label("Cleaning Start"),
            md.cleaning_time_end.label("Cleaning End"),
            md.cleaning_rm_code.label("Cleaning RM"),
            md.cleaning_qty.label("Cleaning QTY"),
            md.remarks.label("Remarks"),
            md.id.label("detail_id")
        )
        .join(mh, md.mixer_header_id == mh.id)
        .join(mm, md.mc_id == mm.id)
        .where(md.is_deleted == False)
    )

    conditions = []

    # --- UPDATED: Scoped Search Logic ---
    if filters.get("search_term"):
        term = f'%{filters["search_term"]}%'
        field = filters.get("search_field", "All Columns")

        if field == "All Columns":
            conditions.append(or_(
                md.product_code.ilike(term),
                md.lot_no.ilike(term),
                md.processed_by.ilike(term),
                md.cleaning_rm_code.ilike(term),
                mm.name.ilike(term),
                cast(mh.reference_no, String).ilike(term)
            ))
        elif field == "Product Code":
            conditions.append(md.product_code.ilike(term))
        elif field == "Lot Number":
            conditions.append(md.lot_no.ilike(term))
        elif field == "Ref No":
            conditions.append(cast(mh.reference_no, String).ilike(term))
        elif field == "Machine":
            conditions.append(mm.name.ilike(term))
        elif field == "Processed By":
            conditions.append(md.processed_by.ilike(term))

    if filters:
        if "date_from" in filters and "date_to" in filters: conditions.append(
            mh.date.between(filters["date_from"], filters["date_to"]))
        if filters.get("product_code"): conditions.append(md.product_code.ilike(f'%{filters["product_code"]}%'))
        if filters.get("lot_number"): conditions.append(md.lot_no.ilike(f'%{filters["lot_number"]}%'))
        if filters.get("processed_by"): conditions.append(md.processed_by.ilike(f'%{filters["processed_by"]}%'))
        if filters.get("cleaning_rm"): conditions.append(md.cleaning_rm_code.ilike(f'%{filters["cleaning_rm"]}%'))
        if filters.get("mc_name"): conditions.append(mm.name == filters["mc_name"])
        if filters.get("ref_no"): conditions.append(mh.reference_no == filters["ref_no"])
        if filters.get("output_qty_from") is not None: conditions.append(md.output_qty >= filters["output_qty_from"])
        if filters.get("output_qty_to") is not None: conditions.append(md.output_qty <= filters["output_qty_to"])
        if filters.get("cleaning_qty_from") is not None: conditions.append(
            md.cleaning_qty >= filters["cleaning_qty_from"])
        if filters.get("cleaning_qty_to") is not None: conditions.append(md.cleaning_qty <= filters["cleaning_qty_to"])
    if conditions:
        query = query.where(and_(*conditions))

    if conditions:
        query = query.where(and_(*conditions))

    # Order by Date descending to see newest records first
    query = query.order_by(mh.date.desc(), mh.reference_no.desc())

    if offset is not None and limit is not None:
        query = query.offset(offset).limit(limit)

    df = pd.read_sql(query, session.bind)

    final_columns = ["Date", "Shift Time Start", "Shift Time End", "Ref No", "MC #", "Product Code", "Lot Number",
                     "Formula No", "Processing Start", "Processing End", "Processing Duration", "Processed By",
                     "Output QTY", "Cleaning Start", "Cleaning End", "Cleaning Duration", "Cleaning RM", "Cleaning QTY",
                     "Remarks", "detail_id"]
    if df.empty:
        return pd.DataFrame(columns=final_columns)

    # --- PERFORMANCE OPTIMIZATION ---
    # Replace the slow row-by-row apply with the new batch function.
    df["Formula No"] = _batch_resolve_formulas(session, df)
    # --- END OPTIMIZATION ---

    df["Processing Duration"] = df.apply(lambda row: calculate_duration(row["Processing Start"], row["Processing End"]),
                                         axis=1)
    df["Cleaning Duration"] = df.apply(lambda row: calculate_duration(row["Cleaning Start"], row["Cleaning End"]),
                                       axis=1)

    for col in ["Processing Start", "Processing End", "Cleaning Start", "Cleaning End"]:
        if col in df.columns:
            df.loc[:, col] = pd.to_datetime(df[col], format='%H:%M:%S', errors='coerce').dt.strftime('%H:%M')

    return df.reindex(columns=final_columns)


def get_deleted_mixer_records(session: Session) -> pd.DataFrame:
    """
    Fetches soft-deleted records with a specific set of columns for the
    restore dialog, as per user requirements.
    """
    query = (
        select(
            MixerDetail.id.label("detail_id"),
            MixerHeader.date.label("Date"),
            MixerHeader.reference_no.label("Ref No"),
            MixerMachine.name.label("MC #"),
            MixerDetail.product_code.label("Product Code"),
            MixerDetail.lot_no.label("Lot Number"),
            # --- MODIFIED: Added the exact columns requested ---
            MixerDetail.processed_by.label("Processed By"),
            MixerDetail.process_time_start.label("Processing Start"),
            MixerDetail.process_time_end.label("Processing End"),
            MixerDetail.output_qty.label("Output QTY")
        )
        .join(MixerHeader, MixerDetail.mixer_header_id == MixerHeader.id)
        .join(MixerMachine, MixerDetail.mc_id == MixerMachine.id)
        .where(MixerDetail.is_deleted == True)
        .order_by(MixerHeader.date.desc())
    )
    df = pd.read_sql(query, session.bind)

    # --- Post-process time columns for better readability ---
    for col in ["Processing Start", "Processing End"]:
        if col in df.columns and not df[col].empty:
            df[col] = pd.to_datetime(df[col], format='%H:%M:%S', errors='coerce').dt.strftime('%H:%M')

    # --- Ensure a consistent and logical column order ---
    final_columns = [
        "detail_id", "Date", "Ref No", "MC #", "Product Code",
        "Lot Number", "Processed By", "Processing Start",
        "Processing End", "Output QTY"
    ]

    # Reorder the DataFrame according to final_columns, handling missing columns if any
    df = df.reindex(columns=final_columns, fill_value=None)

    return df


def restore_mixer_records(session: Session, ids_to_restore: List[int]):
    """Restores a list of soft-deleted records by their IDs."""
    if not ids_to_restore:
        return

    records = session.scalars(
        select(MixerDetail).where(MixerDetail.id.in_(ids_to_restore))
    ).all()

    for record in records:
        record.is_deleted = False

    session.commit()


def update_mixer_record(session: Session, detail_id: int, updated_data: dict):
    """
    Finds a mixer detail record and its header, and updates both with new data.
    """
    # Find the detail record and eagerly load its header to avoid a second query
    record_to_update = session.get(MixerDetail, detail_id)
    if not record_to_update:
        raise ValueError(f"Record with ID {detail_id} not found.")

    # Get the parent header record from the relationship
    header_to_update = record_to_update.header

    # --- Update MixerDetail fields ---
    detail_fields = [
        "product_code", "lot_no", "process_time_start", "process_time_end",
        "processed_by", "output_qty", "cleaning_time_start", "cleaning_time_end",
        "cleaning_rm_code", "cleaning_qty", "remarks"
    ]
    for field in detail_fields:
        if field in updated_data and hasattr(record_to_update, field):
            setattr(record_to_update, field, updated_data[field])

    # Special handling for Machine Name (MC #)
    if "MC #" in updated_data:
        machine_name = updated_data["MC #"]
        machine = session.scalars(select(MixerMachine).where(MixerMachine.name == machine_name)).first()
        if machine:
            record_to_update.mc_id = machine.id
        else:
            raise ValueError(f"Machine '{machine_name}' not found.")

    # --- NEW: Update MixerHeader fields ---
    header_fields = ["date", "time_start", "time_end"]
    for field in header_fields:
        if field in updated_data and hasattr(header_to_update, field):
            setattr(header_to_update, field, updated_data[field])

    # Commit all changes to both tables at once
    session.commit()


# We are simply making these functions available through the 'ops' module
# for better organization within the reports feature.

def get_editor_initial_data(session: Session) -> dict:
    """Fetches all initial data needed for the editor dialog in one go."""
    return {
        "lot_numbers": get_initial_lot_numbers(session, limit=100),
        "product_codes": get_initial_product_codes(session, limit=100),
        "raw_materials": get_initial_raw_materials(session, limit=100),
        "operators": get_all_processed_by_names(session)
    }


def delete_mixer_record(session: Session, detail_id: int):
    """
    Finds a mixer detail record by its ID and performs a soft delete
    by setting its 'is_deleted' flag to True.
    """
    # Find the specific record to delete using its primary key
    record_to_delete = session.get(MixerDetail, detail_id)

    if record_to_delete:
        record_to_delete.is_deleted = True
        session.commit()
    else:
        # This case handles if the record was somehow deleted by another process
        # between the time the table was loaded and the delete button was clicked.
        raise ValueError(f"Record with ID {detail_id} not found for deletion.")

