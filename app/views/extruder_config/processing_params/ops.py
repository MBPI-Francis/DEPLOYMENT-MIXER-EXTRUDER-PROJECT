from collections import defaultdict

from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, distinct
from typing import List, Dict, Any

from models.ExtruderConfig import Resin, Zone, ExtruderMachine, ResinParams, ProcessingParams
from models.User import User


def get_all_resins_for_dropdown(session: Session) -> List[Resin]:
    return session.query(Resin).filter(Resin.is_deleted == False, Resin.abbreviation != None).order_by(
        Resin.abbreviation).all()


def get_all_zones_for_dropdown(session: Session) -> List[Zone]:
    return session.query(Zone).filter(Zone.is_deleted == False).order_by(Zone.name).all()


# --- NEW: Function to get existing machine names ---
def get_all_machine_names(session: Session) -> List[str]:
    """Fetches a list of all active extruder machine names."""
    return [name for name, in session.query(ExtruderMachine.name).filter(ExtruderMachine.is_deleted == False).order_by(
        ExtruderMachine.name).all()]


def get_all_processing_sets_for_main_table(session: Session) -> List:
    """
    Fetches a DISTINCT list of machines that have entries in the ProcessingParams table.
    The ORDER BY clause is corrected to comply with PostgreSQL's DISTINCT ON rule.
    """

    return (
        session.query(
            ExtruderMachine,
            User.username.label("created_by_username")
        )
        .join(ProcessingParams, ExtruderMachine.id == ProcessingParams.machine_id)
        .outerjoin(User, ExtruderMachine.created_by_id == User.user_id)
        .filter(ExtruderMachine.is_deleted == False)
        .distinct(ExtruderMachine.id)  # This generates: DISTINCT ON (tbl_extruder_machines.id)

        # --- THE CRITICAL FIX IS HERE ---
        # The ORDER BY must start with the same column(s) as DISTINCT ON.
        # We order by ID first, then by name for the final sorting.
        .order_by(ExtruderMachine.id, ExtruderMachine.name)

        .all()
    )


def create_processing_parameter_set(session: Session, data: Dict[str, Any], user_id: int) -> ExtruderMachine:
    """
    Performs a multi-table transaction to create a complete processing parameter set.
    """
    # --- Check if machine exists or create a new one ---
    machine_name = data['machine_name']
    machine = session.query(ExtruderMachine).filter(ExtruderMachine.name == machine_name).first()
    if not machine:
        machine = ExtruderMachine(name=machine_name, created_by_id=user_id)
        session.add(machine)
        session.flush()  # Flush to get the new machine.id

    # ... The rest of the function is correct and unchanged
    column_to_resin_param_id = {}
    for col_idx, resin_param_data in data['resin_params'].items():
        new_resin_param = ResinParams(
            resin_id=resin_param_data['resin_id'],
            motor_rpm=resin_param_data['motor_rpm'],
            feed_rate=resin_param_data['feed_rate'],
            created_by_id=user_id
        )
        session.add(new_resin_param)
        session.flush()
        column_to_resin_param_id[col_idx] = new_resin_param.id

    for temp_data in data['temperatures']:
        resin_param_id = column_to_resin_param_id.get(temp_data['col_idx'])
        if not resin_param_id:
            raise ValueError(f"Could not find a resin parameter mapping for column index {temp_data['col_idx']}")

        # Check for existing temperature setting for this combination to prevent duplicates
        existing_temp = session.query(ProcessingParams).filter_by(
            machine_id=machine.id,
            resin_params_id=resin_param_id,
            zone_id=temp_data['zone_id']
        ).first()

        if existing_temp:
            raise ValueError(f"A temperature setting for this Machine, Resin, and Zone combination already exists.")

        new_processing_param = ProcessingParams(
            machine_id=machine.id,
            resin_params_id=resin_param_id,
            zone_id=temp_data['zone_id'],
            temp_value=temp_data['temp_value'],
            created_by_id=user_id
        )
        session.add(new_processing_param)

    session.commit()
    return machine

def get_params_for_resin(session: Session, resin_id: int) -> Dict[str, List[str]]:
    """
    Fetches all unique motor_rpm and feed_rate values associated with a given resin_id.
    """
    if not resin_id:
        return {'rpms': [], 'feed_rates': []}

    rpms = session.query(distinct(ResinParams.motor_rpm)).filter(ResinParams.resin_id == resin_id).all()
    feed_rates = session.query(distinct(ResinParams.feed_rate)).filter(ResinParams.resin_id == resin_id).all()

    return {
        'rpms': [rpm for rpm, in rpms],
        'feed_rates': [rate for rate, in feed_rates]
    }

# --- NEW: Function to fetch details for the Edit Dialog ---
def get_processing_set_details(session: Session, machine_id: int) -> Dict[str, Any]:
    """
    Fetches all details for a given machine_id to populate the edit dialog.
    """
    machine = session.get(ExtruderMachine, machine_id)
    if not machine:
        return {}

    # Fetches all related processing parameters
    params = (
        session.query(ProcessingParams)
        .filter(ProcessingParams.machine_id == machine_id)
        .options(
            joinedload(ProcessingParams.resin_params).joinedload(ResinParams.resin),
            joinedload(ProcessingParams.zone)
        )
        .all()
    )

    # Group the parameters by resin, which corresponds to a column in the dialog
    resin_params_map = defaultdict(lambda: {'temps': {}})
    for p in params:
        rp_id = p.resin_params_id
        resin_params_map[rp_id]['resin_id'] = p.resin_params.resin_id
        resin_params_map[rp_id]['motor_rpm'] = p.resin_params.motor_rpm
        resin_params_map[rp_id]['feed_rate'] = p.resin_params.feed_rate
        resin_params_map[rp_id]['temps'][p.zone_id] = p.temp_value

    return {
        "machine_name": machine.name,
        "resin_params_data": list(resin_params_map.values())
    }

# # --- NEW: Function to update an existing record set ---
# def update_processing_parameter_set(session: Session, machine_id: int, data: Dict[str, Any], user_id: int):
#     """
#     Updates a parameter set by deleting the old parameters and creating new ones.
#     """
#     machine = session.get(ExtruderMachine, machine_id)
#     if not machine:
#         raise ValueError(f"Machine with ID {machine_id} not found.")
#
#     # 1. Update machine name
#     machine.name = data['machine_name']
#     # You might want to set an 'updated_by_id' field here if you have one
#     # machine.updated_by_id = user_id
#
#     # 2. Delete all existing parameters for this machine
#     processing_params_to_delete = session.query(ProcessingParams).filter_by(machine_id=machine_id).all()
#     resin_params_ids_to_delete = {p.resin_params_id for p in processing_params_to_delete}
#     for p in processing_params_to_delete:
#         session.delete(p)
#     if resin_params_ids_to_delete:
#         session.query(ResinParams).filter(ResinParams.id.in_(resin_params_ids_to_delete)).delete(synchronize_session=False)
#     session.flush()
#
#     # 3. Re-create all parameters from the submitted data (using same logic as create)
#     column_to_resin_param_id = {}
#     for col_idx, resin_param_data in data['resin_params'].items():
#         new_resin_param = ResinParams(
#             resin_id=resin_param_data['resin_id'], motor_rpm=resin_param_data['motor_rpm'],
#             feed_rate=resin_param_data['feed_rate'], created_by_id=user_id)
#         session.add(new_resin_param)
#         session.flush()
#         column_to_resin_param_id[col_idx] = new_resin_param.id
#
#     for temp_data in data['temperatures']:
#         resin_param_id = column_to_resin_param_id.get(temp_data['col_idx'])
#         if not resin_param_id: continue
#         new_processing_param = ProcessingParams(
#             machine_id=machine.id, resin_params_id=resin_param_id, zone_id=temp_data['zone_id'],
#             temp_value=temp_data['temp_value'], created_by_id=user_id)
#         session.add(new_processing_param)


def update_processing_parameter_set(session: Session, machine_id: int, data: Dict[str, Any], user_id: int):
    """
    Updates a parameter set by performing an in-place reconciliation.
    - It finds or creates ResinParams without deleting.
    - It updates, creates, or deletes ProcessingParams to match the dialog.
    - It transfers records by updating their machine_id.
    """
    # --- Stage 1: Resolve Target Machine ID ---
    machine_being_edited = session.get(ExtruderMachine, machine_id)
    if not machine_being_edited:
        raise ValueError(f"Machine with ID {machine_id} not found.")

    new_name = data['machine_name'].strip()
    if not new_name:
        raise ValueError("Machine Name cannot be empty.")

    target_machine_id = machine_being_edited.id

    if new_name != machine_being_edited.name:
        target_machine_in_db = session.query(ExtruderMachine).filter(
            ExtruderMachine.name == new_name, ExtruderMachine.is_deleted == False
        ).first()

        if not target_machine_in_db:
            machine_being_edited.name = new_name
        else:
            has_params = session.query(ProcessingParams).filter(
                ProcessingParams.machine_id == target_machine_in_db.id, ProcessingParams.is_deleted == False
            ).first() is not None
            if has_params:
                raise ValueError(
                    f"Cannot move parameters to '{new_name}'. That machine already has its own parameters."
                )
            else:
                target_machine_id = target_machine_in_db.id

    # --- Stage 2: Prepare the final state from the dialog data ---

    # First, find or create the necessary ResinParams records
    column_to_resin_param_id = {}
    for col_idx, resin_param_data in data['resin_params'].items():
        rpm = resin_param_data['motor_rpm']
        feed = resin_param_data['feed_rate']
        resin_id = resin_param_data['resin_id']

        # Find if this exact combination already exists
        rp = session.query(ResinParams).filter_by(
            resin_id=resin_id, motor_rpm=rpm, feed_rate=feed
        ).first()

        if rp:
            column_to_resin_param_id[col_idx] = rp.id
        else:
            # Create it if it doesn't exist
            new_rp = ResinParams(
                resin_id=resin_id, motor_rpm=rpm, feed_rate=feed, created_by_id=user_id
            )
            session.add(new_rp)
            session.flush()  # Flush to get the new ID
            column_to_resin_param_id[col_idx] = new_rp.id

    # Second, build a map of the desired final ProcessingParams state
    final_state_map = {}  # Key: (resin_params_id, zone_id), Value: temp_value
    for temp_data in data['temperatures']:
        col_idx = temp_data['col_idx']
        resin_params_id = column_to_resin_param_id.get(col_idx)
        if not resin_params_id: continue

        key = (resin_params_id, temp_data['zone_id'])
        final_state_map[key] = temp_data['temp_value']

    # --- Stage 3: Reconcile the current state with the final state ---

    # Get all current ProcessingParams for the machine being edited
    current_proc_params = session.query(ProcessingParams).filter_by(machine_id=machine_being_edited.id).all()

    for param in current_proc_params:
        key = (param.resin_params_id, param.zone_id)
        if key in final_state_map:
            # This record exists in both the DB and the final state. Update it.
            new_temp = final_state_map[key]

            # Update machine_id if it's a transfer
            if param.machine_id != target_machine_id:
                param.machine_id = target_machine_id

            # Update temperature if it has changed
            if param.temp_value != new_temp:
                param.temp_value = new_temp

            # Remove from map so we know it has been processed
            del final_state_map[key]
        else:
            # This record is in the DB but not the final state. Delete it.
            session.delete(param)

    # Any remaining items in the map are new records that need to be created
    for (resin_params_id, zone_id), temp_value in final_state_map.items():
        new_param = ProcessingParams(
            machine_id=target_machine_id,
            resin_params_id=resin_params_id,
            zone_id=zone_id,
            temp_value=temp_value,
            created_by_id=user_id
        )
        session.add(new_param)


def soft_delete_parameter_set(session: Session, machine_id: int, user_id: int):
    """
    Soft-deletes an entire parameter set by marking the machine and all its
    associated processing parameters as deleted.
    """
    machine = session.get(ExtruderMachine, machine_id)
    if not machine:
        raise ValueError(f"Machine with ID {machine_id} not found.")

    # Mark the main machine record as deleted
    machine.is_deleted = True
    machine.deleted_by_id = user_id  # Assuming you have this column from AuditMixin

    # Mark all associated processing parameters as deleted
    params_to_delete = session.query(ProcessingParams).filter_by(machine_id=machine_id).all()
    for param in params_to_delete:
        param.is_deleted = True
        param.deleted_by_id = user_id

    # NOTE: We do NOT delete the ResinParams records, as they may be shared
    # by other non-deleted parameter sets.


def get_soft_deleted_machines(session: Session) -> List[ExtruderMachine]:
    """
    Fetches a list of all machines that have been soft-deleted and have
    associated processing parameters.
    """
    return (
        session.query(ExtruderMachine)
        .filter(ExtruderMachine.is_deleted == True)
        .order_by(ExtruderMachine.name)
        .all()
    )


def restore_parameter_set(session: Session, machine_id: int):
    """
    Restores a soft-deleted parameter set by marking the machine and its
    associated processing parameters as active again.
    """
    machine = session.get(ExtruderMachine, machine_id)
    if not machine:
        raise ValueError(f"Machine with ID {machine_id} not found.")

    # Before restoring, check if another active machine with the same name exists
    active_duplicate = session.query(ExtruderMachine).filter(
        ExtruderMachine.name == machine.name,
        ExtruderMachine.is_deleted == False
    ).first()

    if active_duplicate:
        raise ValueError(f"Cannot restore '{machine.name}'. An active machine with that name already exists.")

    # Restore the main machine record
    machine.is_deleted = False
    machine.deleted_by_id = None

    # Restore all associated processing parameters
    params_to_restore = session.query(ProcessingParams).filter_by(machine_id=machine_id).all()
    for param in params_to_restore:
        param.is_deleted = False
        param.deleted_by_id = None
