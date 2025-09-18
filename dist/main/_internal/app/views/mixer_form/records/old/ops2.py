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
    search_all_product_codes, search_all_raw_materials
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

def get_mixer_report_data(session: Session, filters: dict) -> pd.DataFrame:
    """
    Fetches and processes mixer details based on a dictionary of filter criteria.
    """
    md = aliased(MixerDetail, name="md")
    mh = aliased(MixerHeader, name="mh")
    mm = aliased(MixerMachine, name="mm")
    prod = aliased(TblProd01, name="prod")

    query = (
        select(
            mh.date.label("Date"), mh.reference_no.label("Ref No"),
            mm.name.label("MC #"), md.product_code.label("Product Code"),
            md.lot_no.label("Lot Number"), prod.T_FID.label("Formula No"),
            md.process_time_start.label("Processing Start"),
            md.process_time_end.label("Processing End"), md.processed_by.label("Processed By"),
            md.output_qty.label("Output QTY"), md.cleaning_time_start.label("Cleaning Start"),
            md.cleaning_time_end.label("Cleaning End"), md.cleaning_rm_code.label("Cleaning RM"),
            md.cleaning_qty.label("Cleaning QTY"), md.remarks.label("Remarks"),
            md.id.label("detail_id")
        )
        .join(mh, md.mixer_header_id == mh.id)
        .outerjoin(prod, md.lot_no == prod.T_LOTNUM)
        .join(mm, md.mc_id == mm.id)
        .where(md.is_deleted == False)
    )

    # This list will hold all our filter conditions
    conditions = []

    if filters:
        # Date range is always present
        if "date_from" in filters and "date_to" in filters:
            conditions.append(mh.date.between(filters["date_from"], filters["date_to"]))

        # --- Handle all other optional filters safely ---
        if filters.get("product_code"):
            conditions.append(md.product_code.ilike(f'%{filters["product_code"]}%'))
        if filters.get("lot_number"):
            conditions.append(md.lot_no.ilike(f'%{filters["lot_number"]}%'))
        if filters.get("processed_by"):
            conditions.append(md.processed_by.ilike(f'%{filters["processed_by"]}%'))
        if filters.get("cleaning_rm"):
            conditions.append(md.cleaning_rm_code.ilike(f'%{filters["cleaning_rm"]}%'))
        if filters.get("mc_name"):
            conditions.append(mm.name == filters["mc_name"])
        if filters.get("ref_no"):
            conditions.append(mh.reference_no == filters["ref_no"])

        # Handle numeric ranges independently and safely
        if filters.get("output_qty_from") is not None:
            conditions.append(md.output_qty >= filters.get("output_qty_from"))
        if filters.get("output_qty_to") is not None:
            conditions.append(md.output_qty <= filters.get("output_qty_to"))

        if filters.get("cleaning_qty_from") is not None:
            conditions.append(md.cleaning_qty >= filters.get("cleaning_qty_from"))
        if filters.get("cleaning_qty_to") is not None:
            conditions.append(md.cleaning_qty <= filters.get("cleaning_qty_to"))

    # If any conditions were added, apply them to the query
    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(mh.date.desc(), mh.reference_no.desc())
    df = pd.read_sql(query, session.bind)

    if df.empty:
        return df

    # --- Post-processing (no changes here) ---
    df["Processing Duration"] = df.apply(lambda row: calculate_duration(row["Processing Start"], row["Processing End"]), axis=1)
    df["Cleaning Duration"] = df.apply(lambda row: calculate_duration(row["Cleaning Start"], row["Cleaning End"]), axis=1)
    for col in ["Processing Start", "Processing End", "Cleaning Start", "Cleaning End"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], format='%H:%M:%S', errors='coerce').dt.strftime('%H:%M')
    final_columns = [
        "Date", "Ref No", "MC #", "Product Code", "Lot Number", "Formula No",
        "Processing Start", "Processing End", "Processing Duration",
        "Processed By", "Output QTY",
        "Cleaning Start", "Cleaning End", "Cleaning Duration",
        "Cleaning RM", "Cleaning QTY", "Remarks", "detail_id"
    ]
    df = df[final_columns]
    return df


# --- No changes needed for get_deleted_mixer_records or restore_mixer_records for this feature ---
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
    Finds a mixer detail record by its ID and updates it with new data.
    """
    # First, find the record to update
    record_to_update = session.get(MixerDetail, detail_id)
    if not record_to_update:
        raise ValueError(f"Record with ID {detail_id} not found.")

    # Update attributes from the dictionary
    for key, value in updated_data.items():
        if hasattr(record_to_update, key):
            setattr(record_to_update, key, value)

    # Special handling for Machine Name, which needs to be converted to mc_id
    if "MC #" in updated_data:
        machine_name = updated_data["MC #"]
        machine = session.scalars(
            select(MixerMachine).where(MixerMachine.name == machine_name)
        ).first()

        if machine:
            record_to_update.mc_id = machine.id
        else:
            # Handle case where the machine name is somehow invalid
            raise ValueError(f"Machine '{machine_name}' not found.")

    # Commit the changes to the database
    session.commit()


# We are simply making these functions available through the 'ops' module
# for better organization within the reports feature.

def get_editor_initial_data(session: Session) -> dict:
    """Fetches all initial data needed for the editor dialog in one go."""
    return {
        "lot_numbers": get_initial_lot_numbers(session, limit=100),
        "product_codes": get_initial_product_codes(session, limit=100),
        "raw_materials": get_initial_raw_materials(session, limit=100),
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