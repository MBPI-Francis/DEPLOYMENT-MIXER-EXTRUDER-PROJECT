# validators/ExtruderSettingsValidator.py

from pydantic import BaseModel, constr, Field
from typing import List

class ResinValidator(BaseModel):
    """Validates data for creating or updating a Resin."""
    name: constr(strip_whitespace=True, min_length=1, max_length=100)
    abbreviation: constr(strip_whitespace=True, min_length=1, max_length=20)

class ZoneValidator(BaseModel):
    """Validates data for creating or updating a Zone."""
    name: constr(strip_whitespace=True, min_length=1, max_length=50)

class RestoreValidator(BaseModel):
    """Validates a list of IDs for a restore operation."""
    item_ids: List[int] = Field(..., min_items=1)