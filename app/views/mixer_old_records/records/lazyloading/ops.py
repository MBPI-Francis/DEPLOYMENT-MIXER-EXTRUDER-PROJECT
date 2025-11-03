# app/views/mixer_old_records/records/ops.py

import pandas as pd
from sqlalchemy.orm import Session, aliased
from sqlalchemy import select, func, and_, or_
from datetime import datetime, timedelta, date, time
from typing import List, Optional

from app.database.legacy_ops import get_initial_lot_numbers, get_initial_product_codes, get_initial_raw_materials, \
    get_all_old_mixer_operator_names
from models.Mixer import OldMixerDetail, OldMixerHeader, MixerMachine


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



# --- MODIFICATION: Added limit and offset parameters for lazy loading ---
def get_old_mixer_report_data(
    session: Session,
    filters: dict,
    limit: Optional[int] = None, # How many records to fetch
    offset: int = 0             # How many records to skip
) -> pd.DataFrame:
    """
    Fetches and processes OLD mixer details, now with pagination support.
    If 'limit' is None, it will fetch all matching records.
    """
    omd = aliased(OldMixerDetail, name="omd")
    omh = aliased(OldMixerHeader, name="omh")
    mm = aliased(MixerMachine, name="mm")

    query = (
        select(
            omh.date.label("Date"),
            omh.reference_no.label("Ref No"),
            func.coalesce(mm.name, 'N/A').label("MC #"),
            omd.product_code.label("Product Code"),
            omd.lot_no.label("Lot Number"),
            omd.time_start.label("Processing Start"),
            omd.time_end.label("Processing End"),
            omd.operator.label("Processed By"),
            omd.quantity.label("Output QTY"),
            omd.id.label("detail_id")
        )
        .join(omh, omd.header_id == omh.id)
        .outerjoin(mm, omd.machine_id == mm.id)
        .where(omd.is_deleted == False)
    )

    conditions = []
    if filters:
        # ... (all your filtering logic is correct and does not need to change) ...
        if filters.get("date_from") and filters.get("date_to"): conditions.append(
            omh.date.between(filters["date_from"], filters["date_to"]))
        if filters.get("ref_no"): conditions.append(omh.reference_no.ilike(f'%{filters["ref_no"]}%'))
        if filters.get("mc_name"): conditions.append(mm.name == filters["mc_name"])
        if filters.get("product_code"): conditions.append(omd.product_code.ilike(f'%{filters["product_code"]}%'))
        if filters.get("lot_number"):
            if filters["lot_number"] == "<BLANK>":
                conditions.append(or_(omd.lot_no.is_(None), omd.lot_no == '', omd.lot_no.ilike('nan'), omd.lot_no.ilike('None')))
            else:
                conditions.append(omd.lot_no.ilike(f'%{filters["lot_number"]}%'))
        if filters.get("processed_by"):
            if filters["processed_by"] == "" or filters["processed_by"] is None:
                conditions.append(omd.operator.is_(None) | (omd.operator == ''))
            else:
                conditions.append(omd.operator.ilike(f'%{filters["processed_by"]}%'))
        if filters.get("output_qty_from") is not None: conditions.append(omd.quantity >= filters["output_qty_from"])
        if filters.get("output_qty_to") is not None: conditions.append(omd.quantity <= filters["output_qty_to"])

    if conditions: query = query.where(and_(*conditions))

    # Apply sorting first, which is crucial for consistent pagination
    query = query.order_by(omh.date.desc(), omh.reference_no.desc())

    # --- MODIFICATION: Apply pagination to the query ---
    if offset > 0:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    # --- END OF MODIFICATION ---

    df = pd.read_sql(query, session.bind)

    final_columns = ["Date", "Ref No", "MC #", "Product Code", "Lot Number", "Processing Start", "Processing End",
                     "Processing Duration", "Processed By", "Output QTY", "detail_id"]
    if df.empty:
        return pd.DataFrame(columns=final_columns)

    # Data processing and cleaning logic remains the same.
    df["Processing Duration"] = df.apply(lambda row: calculate_duration(row["Processing Start"], row["Processing End"]), axis=1)
    for col in ["Processing Start", "Processing End"]:
        if col in df.columns:
            df.loc[:, col] = pd.to_datetime(df[col], format='%H:%M:%S', errors='coerce').dt.strftime('%H:%M')
    df = df.reindex(columns=final_columns)
    for col in df.columns:
        if col != 'detail_id':
            df[col] = df[col].astype(str)
    df.replace(['nan', 'NaT', '<NA>', 'None'], '', inplace=True)
    return df

def delete_old_mixer_record(session: Session, detail_id: int):
    record = session.get(OldMixerDetail, detail_id)
    if record:
        record.is_deleted = True
        session.commit()


def get_deleted_old_mixer_records(session: Session) -> pd.DataFrame:
    query = (select(OldMixerDetail.id.label("detail_id"), OldMixerHeader.date.label("Date"),
                    OldMixerHeader.reference_no.label("Ref No"), func.coalesce(MixerMachine.name, 'N/A').label("MC #"),
                    OldMixerDetail.product_code.label("Product Code"), OldMixerDetail.lot_no.label("Lot Number")).join(
        OldMixerHeader, OldMixerDetail.header_id == OldMixerHeader.id).outerjoin(MixerMachine,
                                                                                 OldMixerDetail.machine_id == MixerMachine.id).where(
        OldMixerDetail.is_deleted == True).order_by(OldMixerHeader.date.desc()))
    return pd.read_sql(query, session.bind)


def restore_old_mixer_records(session: Session, ids_to_restore: List[int]):
    records = session.scalars(select(OldMixerDetail).where(OldMixerDetail.id.in_(ids_to_restore)))
    for record in records:
        record.is_deleted = False
    session.commit()


def update_old_mixer_record(session: Session, detail_id: int, updated_data: dict):
    record = session.get(OldMixerDetail, detail_id)
    if not record: return

    header = record.header
    if "date" in updated_data: header.date = updated_data["date"]

    if "MC #" in updated_data:
        machine_name = updated_data["MC #"]
        if machine_name and machine_name != "N/A":
            machine = session.scalars(select(MixerMachine).where(MixerMachine.name == machine_name)).first()
            record.machine_id = machine.id if machine else None
        else:
            record.machine_id = None

    record.product_code = updated_data.get("product_code") or None
    record.lot_no = updated_data.get("lot_no") or None
    record.operator = updated_data.get("operator") or None
    record.time_start = updated_data.get("time_start")
    record.time_end = updated_data.get("time_end")
    record.quantity = updated_data.get("quantity")
    session.commit()


def get_editor_initial_data(session: Session) -> dict:
    """Fetches all initial data needed for the editor dialog in one go."""
    return {
        "lot_numbers": get_initial_lot_numbers(session, limit=100),
        "product_codes": get_initial_product_codes(session, limit=100),
        "raw_materials": get_initial_raw_materials(session, limit=100),
        "operators": get_all_old_mixer_operator_names(session, limit=100)
    }

