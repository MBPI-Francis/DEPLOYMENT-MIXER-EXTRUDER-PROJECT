# app/views/extruder_settings/records/ops.py

from sqlalchemy.orm import Session
from typing import List, Optional

from models.ExtruderConfig import Resin, Zone
from models.User import User
from ....validators.ExtruderSettingsValidator import ResinValidator, ZoneValidator, RestoreValidator

CURRENT_USER_ID = 1

# --- Resin Operations ---
# get_all, get_deleted, create, update, check_exists, and restore_resins functions remain unchanged...

def check_resin_name_exists(session: Session, name: str, exclude_id: Optional[int] = None) -> bool:
    query = session.query(Resin).filter(Resin.name == name)
    if exclude_id:
        query = query.filter(Resin.id != exclude_id)
    return session.query(query.exists()).scalar()

# NEW: Function to check for duplicate abbreviations.
def check_resin_abbreviation_exists(session: Session, abbreviation: str, exclude_id: Optional[int] = None) -> bool:
    """Checks if a Resin with the given abbreviation already exists."""
    if not abbreviation:  # An empty abbreviation isn't a duplicate.
        return False
    query = session.query(Resin).filter(Resin.abbreviation == abbreviation)
    if exclude_id:
        query = query.filter(Resin.id != exclude_id)
    return session.query(query.exists()).scalar()



def get_all_resins_with_creator(session: Session) -> List:
    return (
        session.query(Resin, User.username.label("created_by_username"))
        .outerjoin(User, Resin.created_by_id == User.user_id)
        .filter(Resin.is_deleted == False)
        .order_by(Resin.name)
        .all()
    )

def get_deleted_resins(session: Session) -> List[Resin]:
    return session.query(Resin).filter(Resin.is_deleted == True).order_by(Resin.name).all()

def create_resin(session: Session, validated_data: ResinValidator) -> Resin:
    new_resin = Resin(name=validated_data.name,
                      abbreviation=validated_data.abbreviation,
                      created_by_id=CURRENT_USER_ID)
    session.add(new_resin)
    session.commit()
    return new_resin

def update_resin(session: Session, resin_id: int, validated_data: ResinValidator) -> Resin:
    resin = session.query(Resin).filter(Resin.id == resin_id).one()
    resin.name = validated_data.name
    resin.abbreviation = validated_data.abbreviation
    resin.updated_by_id = CURRENT_USER_ID
    session.commit()
    return resin

def restore_resins(session: Session, validated_data: RestoreValidator) -> int:
    resins = session.query(Resin).filter(Resin.id.in_(validated_data.item_ids)).all()
    for resin in resins:
        resin.is_deleted = False
        resin.deleted_by_id = None
    session.commit()
    return len(resins)

# --- NEW: Bulk Delete Function for Resins ---
def soft_delete_resins(session: Session, resin_ids: List[int]) -> int:
    """Soft-deletes multiple Resins in a single transaction."""
    resins_to_delete = session.query(Resin).filter(Resin.id.in_(resin_ids)).all()
    for resin in resins_to_delete:
        resin.is_deleted = True
        resin.deleted_by_id = CURRENT_USER_ID
    session.commit()
    return len(resins_to_delete)


# --- Zone Operations ---
# get_all, get_deleted, create, update, check_exists, and restore_zones functions remain unchanged...

def check_zone_name_exists(session: Session, name: str, exclude_id: Optional[int] = None) -> bool:
    query = session.query(Zone).filter(Zone.name == name)
    if exclude_id:
        query = query.filter(Zone.id != exclude_id)
    return session.query(query.exists()).scalar()

def get_all_zones_with_creator(session: Session) -> List:
    return (
        session.query(Zone, User.username.label("created_by_username"))
        .outerjoin(User, Zone.created_by_id == User.user_id)
        .filter(Zone.is_deleted == False)
        .order_by(Zone.name)
        .all()
    )

def get_deleted_zones(session: Session) -> List[Zone]:
    return session.query(Zone).filter(Zone.is_deleted == True).order_by(Zone.name).all()

def create_zone(session: Session, validated_data: ZoneValidator) -> Zone:
    new_zone = Zone(name=validated_data.name, created_by_id=CURRENT_USER_ID)
    session.add(new_zone)
    session.commit()
    return new_zone

def update_zone(session: Session, zone_id: int, validated_data: ZoneValidator) -> Zone:
    zone = session.query(Zone).filter(Zone.id == zone_id).one()
    zone.name = validated_data.name
    zone.updated_by_id = CURRENT_USER_ID
    session.commit()
    return zone

def restore_zones(session: Session, validated_data: RestoreValidator) -> int:
    zones = session.query(Zone).filter(Zone.id.in_(validated_data.item_ids)).all()
    for zone in zones:
        zone.is_deleted = False
        zone.deleted_by_id = None
    session.commit()
    return len(zones)

# --- NEW: Bulk Delete Function for Zones ---
def soft_delete_zones(session: Session, zone_ids: List[int]) -> int:
    """Soft-deletes multiple Zones in a single transaction."""
    zones_to_delete = session.query(Zone).filter(Zone.id.in_(zone_ids)).all()
    for zone in zones_to_delete:
        zone.is_deleted = True
        zone.deleted_by_id = CURRENT_USER_ID
    session.commit()
    return len(zones_to_delete)