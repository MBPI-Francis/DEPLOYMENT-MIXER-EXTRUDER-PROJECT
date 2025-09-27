# app/views/extruder_machines/records/ops.py

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional

from models.ExtruderConfig import ExtruderMachine
from models.User import User
from ....validators.ExtruderMachineValidator import ExtruderMachineValidator, RestoreValidator

# Placeholder for the current user's ID. In a real application,
# this would be determined after user login.
CURRENT_USER_ID = 1

def check_machine_name_exists(session: Session, name: str, exclude_id: Optional[int] = None) -> bool:
    """
    Checks if an extruder machine with the given name already exists.
    Can exclude a specific ID from the check, which is useful for updates.
    """
    query = session.query(ExtruderMachine).filter(ExtruderMachine.name == name)
    if exclude_id:
        query = query.filter(ExtruderMachine.id != exclude_id)
    return session.query(query.exists()).scalar()

def get_all_machines_with_creator(session: Session) -> List[ExtruderMachine]:
    """
    Fetches all active extruder machines and joins with the User table
    to get the creator's username.
    """
    return (
        session.query(ExtruderMachine, User.username.label("created_by_username"))
        .outerjoin(User, ExtruderMachine.created_by_id == User.user_id)
        .filter(ExtruderMachine.is_deleted == False)
        .order_by(ExtruderMachine.name)
        .all()
    )

def get_deleted_machines(session: Session) -> List[ExtruderMachine]:
    """Fetches all soft-deleted machines."""
    return session.query(ExtruderMachine).filter(ExtruderMachine.is_deleted == True).order_by(ExtruderMachine.name).all()

def create_machine(session: Session, validated_data: ExtruderMachineValidator) -> ExtruderMachine:
    """Creates a new machine record."""
    new_machine = ExtruderMachine(
        name=validated_data.name,
        created_by_id=CURRENT_USER_ID
    )
    session.add(new_machine)
    session.commit()
    session.refresh(new_machine)
    return new_machine

def update_machine(session: Session, machine_id: int, validated_data: ExtruderMachineValidator) -> ExtruderMachine:
    """Updates an existing machine's name."""
    machine = session.query(ExtruderMachine).filter(ExtruderMachine.id == machine_id).one()
    machine.name = validated_data.name
    machine.updated_by_id = CURRENT_USER_ID
    session.commit()
    return machine

def soft_delete_machine(session: Session, machine_id: int) -> bool:
    """Soft-deletes a machine."""
    machine = session.query(ExtruderMachine).filter(ExtruderMachine.id == machine_id).one_or_none()
    if machine:
        machine.is_deleted = True
        machine.deleted_by_id = CURRENT_USER_ID
        session.commit()
        return True
    return False

def restore_machines(session: Session, validated_data: RestoreValidator) -> int:
    """Restores multiple machines based on a list of IDs."""
    machines_to_restore = session.query(ExtruderMachine).filter(ExtruderMachine.id.in_(validated_data.machine_ids)).all()
    for machine in machines_to_restore:
        machine.is_deleted = False
        machine.deleted_by_id = None
    session.commit()
    return len(machines_to_restore)