from sqlalchemy.orm import Session
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