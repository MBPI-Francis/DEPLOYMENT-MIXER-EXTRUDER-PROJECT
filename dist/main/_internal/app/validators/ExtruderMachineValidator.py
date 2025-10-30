# validators/ExtruderMachineValidator.py

from pydantic import BaseModel, constr, Field
from typing import List

class ExtruderMachineValidator(BaseModel):
    """
    Validates the data for creating or updating an extruder machine.
    Ensures the name is not empty and has a reasonable length.
    """
    name: constr(strip_whitespace=True, min_length=1, max_length=50)

class RestoreValidator(BaseModel):
    """
    Validates the list of machine IDs for the restore operation.
    """
    machine_ids: List[int] = Field(..., min_items=1)