# _ProductionProgramPoject/database/mixer_machine_ops.py

from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func

# IMPORTANT: You must have a User model defined in models/models.py
# that SQLAlchemy can use for the join operation.
from models.Mixer import MixerMachine
from models.User import User
from ..validators.mixer_machine_validators import MixerMachineValidator, RestoreValidator


def get_all_machines_with_creator(session: Session) -> List:
    """
    Fetches all active mixer machines and joins with the User table
    to retrieve the name of the user who created the record.
    """
    return (
        session.query(
            MixerMachine.id,
            MixerMachine.name,
            MixerMachine.created_at,
            User.username.label("created_by_username")
        )
        # CORRECTED JOIN CONDITION: Use user_id instead of id
        .join(User, MixerMachine.created_by == User.user_id, isouter=True)
        .filter(MixerMachine.is_deleted == False)
        .all()
    )


def get_deleted_machines(session: Session) -> List[MixerMachine]:
    """Fetches all softly-deleted mixer machines for the restore dialog."""
    return session.query(MixerMachine).filter(MixerMachine.is_deleted == True).all()


def create_machine(session: Session, machine_data: MixerMachineValidator, user_id: int) -> MixerMachine:
    """Creates a new machine record."""
    try:
        new_machine = MixerMachine(
            **machine_data.model_dump(),
            created_by=user_id,
            created_at=datetime.now()
        )
        session.add(new_machine)
        session.commit()
        return new_machine
    except Exception as e:
        session.rollback()
        raise e


def check_machine_name_exists(session: Session, name: str, exclude_id: Optional[int] = None) -> bool:
    """
    Checks if a mixer machine name already exists in the database.

    This is crucial for preventing duplicate entries.

    Args:
        session: The SQLAlchemy Session object.
        name: The machine name to check for.
        exclude_id: An optional machine ID to exclude from the search. This is
                    used during an update to check if the new name conflicts with
                    any *other* machine.

    Returns:
        True if the name exists, False otherwise.
    """
    query = session.query(MixerMachine).filter(func.lower(MixerMachine.name) == func.lower(name))

    # If we are updating a machine, we need to make sure we don't
    # conflict with our own existing name.
    if exclude_id is not None:
        query = query.filter(MixerMachine.id != exclude_id)

    return session.query(query.exists()).scalar()


def update_machine(session: Session, machine_id: int, machine_data: MixerMachineValidator, user_id: int) -> Optional[
    MixerMachine]:
    """Updates an existing machine record."""
    try:
        machine = session.query(MixerMachine).filter_by(id=machine_id).one_or_none()
        if not machine:
            return None

        machine.name = machine_data.name
        machine.modified_by = user_id
        machine.modified_at = datetime.now()
        session.commit()
        return machine
    except Exception as e:
        session.rollback()
        raise e


def soft_delete_machine(session: Session, machine_id: int, user_id: int) -> bool:
    """Softly deletes a machine."""
    try:
        machine = session.query(MixerMachine).filter_by(id=machine_id).one_or_none()
        if machine:
            machine.is_deleted = True
            machine.modified_by = user_id
            machine.modified_at = datetime.now()
            session.commit()
            return True
        return False
    except Exception as e:
        session.rollback()
        raise e


def restore_machines(session: Session, restore_data: RestoreValidator, user_id: int) -> int:
    """Restores a list of machines by their IDs."""
    try:
        num_restored = (
            session.query(MixerMachine)
            .filter(MixerMachine.id.in_(restore_data.machine_ids))
            .update({
                "is_deleted": False,
                "modified_by": user_id,
                "modified_at": datetime.now()
            }, synchronize_session=False)
        )
        session.commit()
        return num_restored
    except Exception as e:
        session.rollback()
        raise e

def get_active_machines(session: Session) -> List[MixerMachine]:
    """
    Fetches all non-deleted mixer machines, primarily for populating dropdowns.

    Args:
        session: The SQLAlchemy Session object.

    Returns:
        A list of active MixerMachine objects, ordered by name.
    """
    return (
        session.query(MixerMachine)
        .filter(MixerMachine.is_deleted == False)
        .order_by(MixerMachine.name)
        .all()
    )