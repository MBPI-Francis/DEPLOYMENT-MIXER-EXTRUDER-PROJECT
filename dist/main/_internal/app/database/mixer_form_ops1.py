from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

# IMPORTANT: Ensure your models file has the MixerHeader and MixerDetail classes
from models import MixerHeader, MixerDetail
# We'll create the validator in the next step
from ..validators.mixer_form_validators import     MixerFinalSubmissionValidator


def check_reference_no_exists(session: Session, ref_no: int) -> bool:
    """
    Checks if a MixerHeader with the given reference number already exists.
    This prevents creating duplicate header entries.

    Args:
        session: The SQLAlchemy Session object.
        ref_no: The reference number to check.

    Returns:
        True if the reference number exists, False otherwise.
    """
    return session.query(
        session.query(MixerHeader).filter(MixerHeader.reference_no == ref_no).exists()
    ).scalar()


def create_mixer_submission(session: Session, submission_data:     MixerFinalSubmissionValidator, user_id: int) -> MixerHeader:
    """
    Creates a new MixerHeader and all of its associated MixerDetail records
    within a single, atomic database transaction.

    Args:
        session: The SQLAlchemy Session object.
        submission_data: A validated Pydantic model containing the header and all detail records.
        user_id: The ID of the user performing this action.

    Returns:
        The newly created MixerHeader object.

    Raises:
        IntegrityError: If the reference_no already exists.
        Exception: For any other database-related errors.
    """
    # First, perform a business logic check for the reference number
    if check_reference_no_exists(session, ref_no=submission_data.reference_no):
        # Raise a specific, catchable error for duplicates
        raise IntegrityError(f"Reference No '{submission_data.reference_no}' already exists.", params=None, orig=None)

    try:
        # Create the header object from the Pydantic model
        header_dict = submission_data.model_dump(exclude={'details'})
        new_header = MixerHeader(
            **header_dict,
            created_at=datetime.now(),
            # created_by=user_id  # Assuming you have this column
        )
        session.add(new_header)

        # We MUST flush the session here. This sends the pending INSERT for the header
        # to the database and populates `new_header.id` with the new primary key
        # without committing the overall transaction.
        session.flush()

        # Now, create the detail records, linking them with the new header's ID
        for detail_data in submission_data.details:
            detail_dict = detail_data.model_dump()
            new_detail = MixerDetail(
                **detail_dict,
                mixer_header_id=new_header.id,  # Link to the header
                created_at=datetime.now(),
                # created_by=user_id # Assuming you have this column
            )
            session.add(new_detail)

        # If all details are added successfully, commit the entire transaction.
        session.commit()
        return new_header

    except Exception as e:
        # If any error occurs at any step, roll back the entire transaction.
        # This ensures data integrity (no orphaned headers or details).
        session.rollback()
        # Re-raise the exception to be handled by the GUI layer
        raise e