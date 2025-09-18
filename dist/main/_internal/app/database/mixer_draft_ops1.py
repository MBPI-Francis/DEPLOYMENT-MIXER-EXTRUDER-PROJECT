from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from models.Mixer import TempMixerHeader, TempMixerDetail, MixerHeader, MixerDetail
from ..validators.mixer_form_validators import MixerDetailCreateValidator, MixerHeaderDataValidator, \
    MixerFinalSubmissionValidator


def get_next_reference_no(session: Session) -> int:
    """Finds the highest existing reference number and returns the next number."""
    max_ref = session.query(func.max(MixerHeader.reference_no)).scalar()
    return (max_ref or 0) + 1


def get_user_draft(session: Session, user_id: int) -> Optional[TempMixerHeader]:
    """Fetches a user's draft header along with all its detail records."""
    return (
        session.query(TempMixerHeader)
        .options(joinedload(TempMixerHeader.details))
        .filter_by(user_id=user_id)
        .one_or_none()
    )


def sync_draft(session: Session, user_id: int, header_data: MixerHeaderDataValidator,
               details_data: List[MixerDetailCreateValidator]
):
    """Synchronizes the entire state of a user's draft by replacing it."""
    try:
        draft_header = get_user_draft(session, user_id)
        if not draft_header:
            draft_header = TempMixerHeader(user_id=user_id, created_at=datetime.now())
            session.add(draft_header)

        draft_header.reference_no = header_data.reference_no
        draft_header.date = header_data.date
        draft_header.time_start = header_data.time_start
        draft_header.time_end = header_data.time_end

        for detail in draft_header.details:
            session.delete(detail)
        session.flush()

        for detail_data in details_data:
            new_detail = TempMixerDetail(**detail_data.model_dump(), created_at=datetime.now())
            draft_header.details.append(new_detail)
        session.commit()
    except Exception as e:
        session.rollback()
        raise e


def delete_staged_detail(session: Session, detail_id: int):
    """Deletes a single detail item from a user's draft."""
    try:
        detail_to_delete = session.query(TempMixerDetail).filter_by(id=detail_id).one_or_none()
        if detail_to_delete:
            session.delete(detail_to_delete)
            session.commit()
    except Exception as e:
        session.rollback()
        raise e


def clear_user_draft(session: Session, user_id: int):
    """Deletes a user's entire draft."""
    try:
        draft_header = get_user_draft(session, user_id)
        if draft_header:
            session.delete(draft_header)
            session.commit()
    except Exception as e:
        session.rollback()
        raise e


def finalize_draft_to_permanent(session: Session, user_id: int,
                                final_header_data: MixerFinalSubmissionValidator) -> MixerHeader:
    """Moves a user's draft from temp tables to permanent tables."""
    if session.query(
            session.query(MixerHeader).filter_by(reference_no=final_header_data.reference_no).exists()).scalar():
        raise IntegrityError(f"Reference No '{final_header_data.reference_no}' already exists.", params=None, orig=None)

    draft_header = get_user_draft(session, user_id)
    if not draft_header or not draft_header.details:
        raise ValueError("No draft records found to save.")

    try:
        perm_header = MixerHeader(**final_header_data.model_dump(), created_at=datetime.now())
        session.add(perm_header)
        session.flush()

        for temp_detail in draft_header.details:
            perm_detail = MixerDetail(
                mixer_header_id=perm_header.id,
                mc_id=temp_detail.mc_id,
                product_code=temp_detail.product_code,
                lot_no=temp_detail.lot_no,
                lot_count=temp_detail.lot_count,
                process_time_start=temp_detail.process_time_start,
                process_time_end=temp_detail.process_time_end,
                processed_by=temp_detail.processed_by,
                output_qty=temp_detail.output_qty,
                cleaning_time_start=temp_detail.cleaning_time_start,
                cleaning_time_end=temp_detail.cleaning_time_end,
                cleaning_rm_code=temp_detail.cleaning_rm_code,
                cleaning_qty=temp_detail.cleaning_qty,
                remarks=temp_detail.remarks,
                created_at=datetime.now()
            )
            session.add(perm_detail)

        session.delete(draft_header)
        session.commit()
        return perm_header
    except Exception as e:
        session.rollback()
        raise e