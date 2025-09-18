import re
from datetime import date, time
from typing import List, Optional
from pydantic import BaseModel, Field, conint, confloat, validator


def validate_time_format(value: str) -> time:
    """A reusable Pydantic validator for HH:MM time strings."""
    if not re.match(r'^(?:[01]\d|2[0-3]):[0-5]\d$', value):
        raise ValueError('Invalid time format, expected HH:MM (e.g., 08:30 or 17:00)')

    hour, minute = map(int, value.split(':'))
    return time(hour, minute)


class MixerDetailCreateValidator(BaseModel):
    """Validates the data for a single detail row as entered by the user."""
    mc_id: conint(gt=0, strict=True)
    product_code: str = Field(..., min_length=1, max_length=50)
    lot_no: str = Field(..., min_length=1, max_length=50)
    lot_count: conint(gt=0)
    process_time_start: str
    process_time_end: str
    processed_by: str = Field(..., min_length=1, max_length=20)
    output_qty: confloat(gt=0.0)
    cleaning_time_start: str
    cleaning_time_end: str
    cleaning_rm_code: str = Field(..., min_length=1, max_length=30)
    cleaning_qty: confloat(gt=0.0)
    remarks: Optional[str] = None

    _validate_process_start = validator('process_time_start', allow_reuse=True)(validate_time_format)
    _validate_process_end = validator('process_time_end', allow_reuse=True)(validate_time_format)
    _validate_cleaning_start = validator('cleaning_time_start', allow_reuse=True)(validate_time_format)
    _validate_cleaning_end = validator('cleaning_time_end', allow_reuse=True)(validate_time_format)


class MixerHeaderDataValidator(BaseModel):
    """Validates only the data for the header section of the form."""
    reference_no: Optional[conint(gt=0)] = None
    date: date
    time_start: str
    time_end: str

    _validate_time_start = validator('time_start', allow_reuse=True)(validate_time_format)
    _validate_time_end = validator('time_end', allow_reuse=True)(validate_time_format)


class MixerFinalSubmissionValidator(MixerHeaderDataValidator):
    """Validates the entire data package for final submission."""
    reference_no: conint(gt=0)