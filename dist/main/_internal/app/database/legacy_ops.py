# app/database/legacy_ops.py
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import select, text, distinct
from models import RawMaterials, TblProd01, MixerDetail


def get_initial_lot_numbers(session: Session, limit: int = 100) -> list[str]:
    """Fetches the first N unique, non-empty lot numbers."""
    query = text("""
        SELECT "T_LOTNUM" 
        FROM public.tbl_prod01
        WHERE "T_LOTNUM" IS NOT NULL AND "T_LOTNUM" != ''
        GROUP BY "T_LOTNUM"
        ORDER BY "T_LOTNUM" ASC
        LIMIT :limit
    """)
    results = session.execute(query, {"limit": limit}).scalars().all()
    return results

def get_initial_product_codes(session: Session, limit: int = 100) -> list[str]:
    """Fetches the first N unique, non-empty product codes."""
    query = text("""
        SELECT "T_PRODCODE"
        FROM public.tbl_prod01
        WHERE "T_PRODCODE" IS NOT NULL AND "T_PRODCODE" != ''
        GROUP BY "T_PRODCODE"
        ORDER BY "T_PRODCODE" ASC
        LIMIT :limit
    """)
    results = session.execute(query, {"limit": limit}).scalars().all()
    return results

def search_all_lot_numbers(session: Session, search_term: str) -> list[str]:
    """Searches ALL lot numbers that start with the given term."""
    query = text("""
        SELECT DISTINCT "T_LOTNUM"
        FROM public.tbl_prod01
        WHERE "T_LOTNUM" ILIKE :term
        ORDER BY "T_LOTNUM" ASC
    """)
    # The ILIKE operator is case-insensitive, and '%' is the wildcard
    results = session.execute(query, {"term": f"{search_term}%"}).scalars().all()
    return results

def search_all_product_codes(session: Session, search_term: str) -> list[str]:
    """Searches ALL product codes that start with the given term."""
    query = text("""
        SELECT DISTINCT "T_PRODCODE"
        FROM public.tbl_prod01
        WHERE "T_PRODCODE" ILIKE :term
        ORDER BY "T_PRODCODE" ASC
    """)
    results = session.execute(query, {"term": f"{search_term}%"}).scalars().all()
    return results

# --- NEW: Function to get initial Raw Materials ---
def get_initial_raw_materials(session: Session, limit: int = 100) -> list[str]:
    """Fetches the first N unique, non-empty raw material codes."""
    # This query uses your tbl_raw_materials and rm_code column
    query = text("""
        SELECT "rm_code"
        FROM public.tbl_raw_materials
        WHERE "rm_code" IS NOT NULL AND "rm_code" != ''
        GROUP BY "rm_code"
        ORDER BY "rm_code" ASC
        LIMIT :limit
    """)
    results = session.execute(query, {"limit": limit}).scalars().all()
    return results

# --- NEW: Function to search all Raw Materials ---
def search_all_raw_materials(session: Session, search_term: str) -> list[str]:
    """Searches ALL raw material codes that start with the given term."""
    query = text("""
        SELECT DISTINCT "rm_code"
        FROM public.tbl_raw_materials
        WHERE "rm_code" ILIKE :term
        ORDER BY "rm_code" ASC
    """)
    results = session.execute(query, {"term": f"{search_term}%"}).scalars().all()
    return results


def get_all_lot_numbers_for_product(session: Session, product_code: str) -> List[str]:
    """
    Fetches all existing lot number records for a single, specific product code.

    This is used by the validation logic to check if a user's entry is valid.

    Args:
        session: The SQLAlchemy session.
        product_code: The product code to filter by.

    Returns:
        A list of lot number strings associated with that product.
    """
    if not product_code:
        return []

    # Assuming your model is TblProd01 and the columns are 'prod_code' and 'lot_no'
    # Please adjust the model and column names if they are different.
    return session.query(TblProd01.T_LOTNUM) \
        .filter(TblProd01.T_PRODCODE == product_code) \
        .all()


def get_all_processed_by_names(session: Session) -> List[str]:
    """
    Fetches a unique, sorted list of all 'processed_by' names from the
    permanent MixerDetail records.

    Args:
        session: The SQLAlchemy session.

    Returns:
        A sorted list of unique names.
    """
    # Query for distinct names, filter out None or empty strings, and order them
    results = session.query(distinct(MixerDetail.processed_by)) \
        .filter(MixerDetail.processed_by.isnot(None), MixerDetail.processed_by != '') \
        .order_by(MixerDetail.processed_by) \
        .all()

    # The result is a list of tuples, e.g., [('USER A',), ('USER B',)], so we extract the first element
    return [name for name, in results]