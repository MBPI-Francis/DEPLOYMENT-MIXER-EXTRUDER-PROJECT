# app/views/mixer_report/ops.py
from typing import List

from sqlalchemy.orm import Session, aliased
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta, date, time

from models import MixerDetail, MixerHeader, MixerMachine, TblProd01
import pandas as pd

# (Add these functions at the end of the file)
from app.database.legacy_ops import (
    get_initial_lot_numbers, get_initial_product_codes,
    get_initial_raw_materials, search_all_lot_numbers,
    search_all_product_codes, search_all_raw_materials, get_all_processed_by_names, get_formula_no_for_lot_range
)


def calculate_duration(start_time, end_time):
    if not isinstance(start_time, time) or not isinstance(end_time, time):
        return None
    start_dt = datetime.combine(date.min, start_time)
    end_dt = datetime.combine(date.min, end_time)
    if end_dt < start_dt:
        end_dt += timedelta(days=1)
    delta = end_dt - start_dt
    total_seconds = int(delta.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    return f"{hours:02d}:{minutes:02d}"


# def get_mixer_report_data(session: Session, filters: dict) -> pd.DataFrame:
#     """
#     Fetches and processes mixer details. This version performs a sophisticated,
#     range-aware lookup for the 'Formula No' after the main query.
#     """
#     md = aliased(MixerDetail, name="md")
#     mh = aliased(MixerHeader, name="mh")
#     mm = aliased(MixerMachine, name="mm")
#
#     # --- MODIFICATION 1: The query no longer joins the legacy formula table ---
#     query = (
#         select(
#             mh.date.label("Date"),
#             mh.time_start.label("Shift Time Start"),
#             mh.time_end.label("Shift Time End"),
#             mh.reference_no.label("Ref No"),
#             mm.name.label("MC #"),
#             md.product_code.label("Product Code"),
#             md.lot_no.label("Lot Number"),
#             # Note: "Formula No" is intentionally missing here. We will add it later.
#             md.process_time_start.label("Processing Start"),
#             md.process_time_end.label("Processing End"),
#             md.processed_by.label("Processed By"),
#             md.output_qty.label("Output QTY"),
#             md.cleaning_time_start.label("Cleaning Start"),
#             md.cleaning_time_end.label("Cleaning End"),
#             md.cleaning_rm_code.label("Cleaning RM"),
#             md.cleaning_qty.label("Cleaning QTY"),
#             md.remarks.label("Remarks"),
#             md.id.label("detail_id")
#         )
#         .join(mh, md.mixer_header_id == mh.id)
#         .join(mm, md.mc_id == mm.id)
#         .where(md.is_deleted == False)
#     )
#
#     # Filtering logic remains unchanged
#     conditions = []
#     if filters:
#         if "date_from" in filters and "date_to" in filters: conditions.append(
#             mh.date.between(filters["date_from"], filters["date_to"]))
#         if filters.get("product_code"):
#             conditions.append(md.product_code.ilike(f'%{filters["product_code"]}%'))
#
#         if filters.get("lot_number"):
#             conditions.append(md.lot_no.ilike(f'%{filters["lot_number"]}%'))
#
#         if filters.get("processed_by"):
#             conditions.append(md.processed_by.ilike(f'%{filters["processed_by"]}%'))
#
#         if filters.get("cleaning_rm"):
#             conditions.append(md.cleaning_rm_code.ilike(f'%{filters["cleaning_rm"]}%'))
#
#         if filters.get("mc_name"):
#             conditions.append(mm.name == filters["mc_name"])
#
#         if filters.get("ref_no"):
#             conditions.append(mh.reference_no == filters["ref_no"])
#
#         if filters.get("output_qty_from") is not None:
#             conditions.append(md.output_qty >= filters["output_qty_from"])
#
#         if filters.get("output_qty_to") is not None:
#             conditions.append(md.output_qty <= filters["output_qty_to"])
#
#         # Add filters for the Cleaning Quantity range.
#         if filters.get("cleaning_qty_from") is not None:
#             conditions.append(md.cleaning_qty >= filters["cleaning_qty_from"])
#
#         if filters.get("cleaning_qty_to") is not None:
#             conditions.append(md.cleaning_qty <= filters["cleaning_qty_to"])
#     if conditions:
#         query = query.where(and_(*conditions))
#
#     query = query.order_by(mh.date.desc(), mh.reference_no.desc())
#     df = pd.read_sql(query, session.bind)
#
#     if df.empty:
#         all_columns = ["Date", "Shift Time Start", "Shift Time End", "Ref No", "MC #", "Product Code", "Lot Number",
#                        "Formula No", "Processing Start", "Processing End", "Processing Duration", "Processed By",
#                        "Output QTY", "Cleaning Start", "Cleaning End", "Cleaning Duration", "Cleaning RM",
#                        "Cleaning QTY", "Remarks", "detail_id"]
#         return pd.DataFrame(columns=all_columns)
#
#     # --- MODIFICATION 2: Intelligent post-processing to find Formula No ---
#     # This is more efficient than calling the function for every row.
#     # We create a cache of product codes to avoid redundant database queries.
#     product_code_cache = {}
#
#     def resolve_formula(row):
#         p_code = row["Product Code"]
#         lot_num = row["Lot Number"]
#
#         # This lambda-like check is just to avoid re-querying the DB
#         # for product codes we've already seen.
#         if p_code not in product_code_cache:
#             # The function handles the complex logic internally
#             product_code_cache[p_code] = True  # Mark as processed
#
#         return get_formula_no_for_lot_range(session, p_code, lot_num)
#
#     # Apply the sophisticated lookup function to each row
#     df["Formula No"] = df.apply(resolve_formula, axis=1)
#     # --- END OF MODIFICATION 2 ---
#
#     # Post-processing for durations and times remains the same
#     df["Processing Duration"] = df.apply(lambda row: calculate_duration(row["Processing Start"], row["Processing End"]),
#                                          axis=1)
#     df["Cleaning Duration"] = df.apply(lambda row: calculate_duration(row["Cleaning Start"], row["Cleaning End"]),
#                                        axis=1)
#     for col in ["Processing Start", "Processing End", "Cleaning Start", "Cleaning End"]:
#         if col in df.columns:
#             df.loc[:, col] = pd.to_datetime(df[col], format='%H:%M:%S', errors='coerce').dt.strftime('%H:%M')
#
#     final_columns = [
#         "Date", "Shift Time Start", "Shift Time End", "Ref No", "MC #", "Product Code",
#         "Lot Number", "Formula No", "Processing Start", "Processing End",
#         "Processing Duration", "Processed By", "Output QTY", "Cleaning Start",
#         "Cleaning End", "Cleaning Duration", "Cleaning RM", "Cleaning QTY",
#         "Remarks", "detail_id"
#     ]
#
#     return df.reindex(columns=final_columns)

# --- No changes needed for get_deleted_mixer_records or restore_mixer_records for this feature ---

def get_mixer_report_data(session: Session, filters: dict, offset: int = 0, limit: int = 100) -> pd.DataFrame:
    """
    Fetches a paginated set of mixer details and performs the sophisticated,
    range-aware lookup for the 'Formula No'.
    """
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

    # Filtering logic is correct and does not need to change
    conditions = []
    if filters:
        # ... (all your existing filter conditions are correct) ...
        if "date_from" in filters and "date_to" in filters: conditions.append(
            mh.date.between(filters["date_from"], filters["date_to"]))
        if filters.get("product_code"): conditions.append(md.product_code.ilike(f'%{filters["product_code"]}%'))
        if filters.get("lot_number"): conditions.append(md.lot_no.ilike(f'%{filters["lot_number"]}%'))
        if filters.get("processed_by"): conditions.append(md.processed_by.ilike(f'%{filters["processed_by"]}%'))
        if filters.get("cleaning_rm"): conditions.append(md.cleaning_rm_code.ilike(f'%{filters["cleaning_rm"]}%'))
        if filters.get("mc_name"): conditions.append(mm.name == filters["mc_name"])
        if filters.get("ref_no"): conditions.append(mh.reference_no == filters["ref_no"])
        if filters.get("output_qty_from") is not None:
            conditions.append(md.output_qty >= filters["output_qty_from"])
        if filters.get("output_qty_to") is not None:
            conditions.append(md.output_qty <= filters["output_qty_to"])
        if filters.get("cleaning_qty_from") is not None:
            conditions.append(md.cleaning_qty >= filters["cleaning_qty_from"])
        if filters.get("cleaning_qty_to") is not None:
            conditions.append(md.cleaning_qty <= filters["cleaning_qty_to"])

    if conditions:
        query = query.where(and_(*conditions))

    # --- THIS IS THE KEY MODIFICATION FOR PAGINATION ---
    query = query.order_by(mh.date.desc(), mh.reference_no.desc()).offset(offset).limit(limit)
    # --- END MODIFICATION ---

    df = pd.read_sql(query, session.bind)

    # The rest of the function (post-processing for Formula No, durations, etc.)
    # is correct and does not need to change. It will now operate on the paginated data.
    if df.empty:
        # ... (return empty DataFrame logic is correct) ...
        all_columns = ["Date", "Shift Time Start", "Shift Time End", "Ref No", "MC #", "Product Code", "Lot Number", "Formula No", "Processing Start", "Processing End", "Processing Duration", "Processed By", "Output QTY", "Cleaning Start", "Cleaning End", "Cleaning Duration", "Cleaning RM", "Cleaning QTY", "Remarks", "detail_id"]
        return pd.DataFrame(columns=all_columns)


    df["Formula No"] = df.apply(
        lambda row: get_formula_no_for_lot_range(session, row["Product Code"], row["Lot Number"]),
        axis=1
    )
    df["Processing Duration"] = df.apply(lambda row: calculate_duration(row["Processing Start"], row["Processing End"]), axis=1)
    df["Cleaning Duration"] = df.apply(lambda row: calculate_duration(row["Cleaning Start"], row["Cleaning End"]), axis=1)
    for col in ["Processing Start", "Processing End", "Cleaning Start", "Cleaning End"]:
        if col in df.columns:
            df.loc[:, col] = pd.to_datetime(df[col], format='%H:%M:%S', errors='coerce').dt.strftime('%H:%M')
    final_columns = ["Date", "Shift Time Start", "Shift Time End", "Ref No", "MC #", "Product Code", "Lot Number", "Formula No", "Processing Start", "Processing End", "Processing Duration", "Processed By", "Output QTY", "Cleaning Start", "Cleaning End", "Cleaning Duration", "Cleaning RM", "Cleaning QTY", "Remarks", "detail_id"]
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