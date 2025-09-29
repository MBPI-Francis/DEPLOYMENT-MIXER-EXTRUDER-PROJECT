# app/views/extruder_config/resin_params/ops.py

from sqlalchemy.orm import Session, aliased
from sqlalchemy import and_
from typing import List, Optional

from models.ExtruderConfig import Resin, ResinParams
from models.User import User
from ....validators.ExtruderSettingsValidator import ResinParamsValidator, RestoreValidator

CURRENT_USER_ID = 1

def get_all_resins(session: Session) -> List[Resin]:
    """Helper to fetch all active resins for populating combo boxes."""
    return session.query(Resin).filter(Resin.is_deleted == False).order_by(Resin.name).all()

def check_resin_param_exists(session: Session, resin_id: int, motor_rpm: str, feed_rate: str, exclude_id: Optional[int] = None) -> bool:
    """Checks for duplicates across the three key columns."""
    query = session.query(ResinParams).filter(
        and_(
            ResinParams.resin_id == resin_id,
            ResinParams.motor_rpm == motor_rpm,
            ResinParams.feed_rate == feed_rate
        )
    )
    if exclude_id:
        query = query.filter(ResinParams.id != exclude_id)
    return session.query(query.exists()).scalar()

def get_all_resin_params_with_details(session: Session) -> List:
    """
    UPDATED: Fetches all active Resin Parameters with all necessary creator
    and updater details for the new columns.
    """
    # Create aliases for the User table to join it twice
    CreatedByUser = aliased(User, name="created_by_user")
    UpdatedByUser = aliased(User, name="updated_by_user")

    return (
        session.query(
            ResinParams,
            Resin.name.label("resin_name"),
            CreatedByUser.username.label("created_by_username"),
            UpdatedByUser.username.label("updated_by_username")
        )
        .join(Resin, ResinParams.resin_id == Resin.id)
        .outerjoin(CreatedByUser, ResinParams.created_by_id == CreatedByUser.user_id)
        .outerjoin(UpdatedByUser, ResinParams.updated_by_id == UpdatedByUser.user_id)
        .filter(ResinParams.is_deleted == False)
        .order_by(Resin.name, ResinParams.motor_rpm)
        .all()
    )

def create_resin_param(session: Session, validated_data: ResinParamsValidator) -> ResinParams:
    """Creates a new Resin Parameter record."""
    new_param = ResinParams(
        resin_id=validated_data.resin_id,
        motor_rpm=validated_data.motor_rpm,
        feed_rate=validated_data.feed_rate,
        created_by_id=CURRENT_USER_ID
    )
    session.add(new_param)
    session.commit()
    return new_param

def update_resin_param(session: Session, param_id: int, validated_data: ResinParamsValidator) -> ResinParams:
    """Updates an existing Resin Parameter record."""
    param = session.query(ResinParams).filter(ResinParams.id == param_id).one()
    param.resin_id = validated_data.resin_id
    param.motor_rpm = validated_data.motor_rpm
    param.feed_rate = validated_data.feed_rate
    param.updated_by_id = CURRENT_USER_ID
    session.commit()
    return param

def soft_delete_resin_params(session: Session, param_ids: List[int]) -> int:
    """Soft-deletes multiple Resin Parameter records."""
    params_to_delete = session.query(ResinParams).filter(ResinParams.id.in_(param_ids)).all()
    for param in params_to_delete:
        param.is_deleted = True
        param.deleted_by_id = CURRENT_USER_ID
    session.commit()
    return len(params_to_delete)

# --- NEW: Restore Functionality ---

def get_deleted_resin_params(session: Session) -> List:
    """Fetches all soft-deleted Resin Parameters for the restore dialog."""
    return (
        session.query(ResinParams, Resin.name.label("resin_name"))
        .join(Resin, ResinParams.resin_id == Resin.id)
        .filter(ResinParams.is_deleted == True)
        .order_by(Resin.name)
        .all()
    )

def restore_resin_params(session: Session, validated_data: RestoreValidator) -> int:
    """Restores multiple soft-deleted Resin Parameters."""
    params_to_restore = session.query(ResinParams).filter(ResinParams.id.in_(validated_data.item_ids)).all()
    for param in params_to_restore:
        param.is_deleted = False
        param.deleted_by_id = None
    session.commit()
    return len(params_to_restore)