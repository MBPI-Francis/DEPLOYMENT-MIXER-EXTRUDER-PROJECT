# app/database/legacy_ops.py

from sqlalchemy.orm import Session
# --- ADD 'and_' TO YOUR IMPORTS ---
from sqlalchemy import select, distinct, and_

from models import TblProd01 # Make sure this import path is correct

def get_unique_lot_numbers(session: Session) -> list[str]:
    """Fetches all unique, non-empty lot numbers from the legacy production table."""
    
    # --- THIS IS THE FIX ---
    # Wrap the multiple conditions in an `and_()` clause for clarity and correctness.
    query = (
        select(distinct(TblProd01.T_LOTNUM))
        .where(
            and_(
                TblProd01.T_LOTNUM.is_not(None), 
                TblProd01.T_LOTNUM != ''
            )
        )
        .order_by(TblProd01.T_LOTNUM)
    )
    results = session.scalars(query).all()
    return results

def get_unique_product_codes(session: Session) -> list[str]:
    """Fetches all unique, non-empty product codes from the legacy production table."""
    
    # --- APPLY THE SAME FIX HERE ---
    query = (
        select(distinct(TblProd01.T_PRODCODE))
        .where(
            and_(
                TblProd01.T_PRODCODE.is_not(None),
                TblProd01.T_PRODCODE != ''
            )
        )
        .order_by(TblProd01.T_PRODCODE)
    )
    results = session.scalars(query).all()
    return results