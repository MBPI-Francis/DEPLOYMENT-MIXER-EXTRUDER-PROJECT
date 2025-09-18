# app/views/mixer_report/ops.py
from typing import List

from sqlalchemy.orm import Session, aliased
from sqlalchemy import select, func, and_
from datetime import datetime, timedelta, date, time

from models import MixerDetail, MixerHeader, MixerMachine
import pandas as pd

from models import TblProd01


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
    p01 = aliased(TblProd01, name="p01")

    query = (
        select(
            mh.date.label("Date"), mh.reference_no.label("Ref No"),
            mm.name.label("MC #"), md.product_code.label("Product Code"),
            md.lot_no.label("Lot Number"), p01.T_FID.label("Formula No"),
            md.process_time_start.label("Processing Start"),
            md.process_time_end.label("Processing End"), md.processed_by.label("Processed By"),
            md.output_qty.label("Output QTY"), md.cleaning_time_start.label("Cleaning Start"),
            md.cleaning_time_end.label("Cleaning End"), md.cleaning_rm_code.label("Cleaning RM"),
            md.cleaning_qty.label("Cleaning QTY"), md.remarks.label("Remarks"),
            md.id.label("detail_id")
        )
        .join(mh, md.mixer_header_id == mh.id)
        .join(mm, md.mc_id == mm.id)
        .join(p01, md.lot_no == p01.T_LOTNUM)
        .where(md.is_deleted == False)
    )

    # --- DYNAMIC FILTERING LOGIC ---
    conditions = []
    if filters:
        # Text-based filters (case-insensitive 'contains' search)
        if filters.get("product_code"):
            conditions.append(md.product_code.ilike(f'%{filters["product_code"]}%'))
        if filters.get("lot_number"):
            conditions.append(md.lot_no.ilike(f'%{filters["lot_number"]}%'))
        if filters.get("processed_by"):
            conditions.append(md.processed_by.ilike(f'%{filters["processed_by"]}%'))
        if filters.get("cleaning_rm"):
            conditions.append(md.cleaning_rm_code.ilike(f'%{filters["cleaning_rm"]}%'))

        # Exact match filters
        if filters.get("mc_name"):
            conditions.append(mm.name == filters["mc_name"])
        if filters.get("ref_no"):
            conditions.append(mh.reference_no == filters["ref_no"])

        # Range filters
        if filters.get("date_from") and filters.get("date_to"):
            conditions.append(mh.date.between(filters["date_from"], filters["date_to"]))
        if filters.get("output_qty_from") is not None and filters.get("output_qty_to") is not None:
            conditions.append(md.output_qty.between(filters["output_qty_from"], filters["output_qty_to"]))
        if filters.get("cleaning_qty_from") is not None and filters.get("cleaning_qty_to") is not None:
            conditions.append(md.cleaning_qty.between(filters["cleaning_qty_from"], filters["cleaning_qty_to"]))

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(mh.date.desc(), mh.reference_no.desc())

    df = pd.read_sql(query, session.bind)

    if df.empty:
        return df

    # --- Post-processing (as before) ---
    df["Processing Duration"] = df.apply(lambda row: calculate_duration(row["Processing Start"], row["Processing End"]),
                                         axis=1)
    df["Cleaning Duration"] = df.apply(lambda row: calculate_duration(row["Cleaning Start"], row["Cleaning End"]),
                                       axis=1)

    for col in ["Processing Start", "Processing End", "Cleaning Start", "Cleaning End"]:
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

def get_deleted_mixer_records(session: Session) -> pd.DataFrame:
    """Fetches all SOFT-DELETED mixer records for the restore dialog."""
    query = (
        select(
            MixerDetail.id.label("detail_id"),
            MixerHeader.date.label("Date"),
            MixerHeader.reference_no.label("Ref No"),
            MixerMachine.name.label("MC #"),
            MixerDetail.product_code.label("Product Code"),
            MixerDetail.lot_no.label("Lot Number")
        )
        .join(MixerHeader, MixerDetail.mixer_header_id == MixerHeader.id)
        .join(MixerMachine, MixerDetail.mc_id == MixerMachine.id)
        .where(MixerDetail.is_deleted == True)
        .order_by(MixerHeader.date.desc())
    )
    return pd.read_sql(query, session.bind)


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