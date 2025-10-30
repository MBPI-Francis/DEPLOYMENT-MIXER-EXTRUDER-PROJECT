# _ProductionProgramPoject/validators/mixer_machine_validators.py

from pydantic import BaseModel, Field, conint
from typing import List

class MixerMachineValidator(BaseModel):
    """
    Validates the data for creating or updating a mixer machine.
    The 'name' field must be a non-empty string.
    """
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="The name of the mixer machine cannot be empty."
    )

    class Config:
        form_attributes = True


class RestoreValidator(BaseModel):
    """
    Validates the list of IDs for the restore operation.
    Ensures that the input is a list of positive integers.
    """
    machine_ids: List[conint(gt=0)] = Field(
        ...,
        min_items=1,
        description="At least one machine ID must be provided for restoration."
    )