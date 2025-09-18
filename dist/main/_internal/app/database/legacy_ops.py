# app/database/legacy_ops.py
from typing import List, Optional, Tuple
import re

from sqlalchemy.orm import Session
from sqlalchemy import select, text, distinct
from models import RawMaterials, TblProd01, MixerDetail
from models.Mixer import OldMixerDetail


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



def get_all_old_mixer_operator_names(session: Session, limit: int = 100) -> list[str]:
    """
    Fetches the first N unique, non-empty operator names using the SQLAlchemy ORM.
    """
    # This query is built using Python objects, which is safer.
    query = (
        select(OldMixerDetail.operator)
        .where(
            OldMixerDetail.operator.isnot(None),
            OldMixerDetail.operator != ''
        )
        .distinct()
        .order_by(OldMixerDetail.operator.asc())
        .limit(limit)
    )
    # The execution is cleaner with the ORM.
    results = session.scalars(query).all()
    return results


# --- Helper function to parse lot strings ---
def _parse_lot_string(lot_str: str) -> Optional[Tuple[int, int, str]]:
    """
    Parses a lot string (e.g., "1001AM" or "1005AM-1008AM") into its parts.
    Returns a tuple of (start_number, end_number, suffix).
    """
    lot_str = lot_str.strip().upper()
    part_regex = re.compile(r'^(\d+)([A-Z]+)$')

    if '-' in lot_str:
        parts = lot_str.split('-')
        if len(parts) != 2: return None
        start_part, end_part = parts
        start_match = part_regex.match(start_part)
        end_match = part_regex.match(end_part)
        if not start_match or not end_match: return None

        start_num, start_suffix = int(start_match.group(1)), start_match.group(2)
        end_num, end_suffix = int(end_match.group(1)), end_match.group(2)

        if start_suffix != end_suffix or end_num < start_num:
            return None
        return start_num, end_num, start_suffix
    else:
        match = part_regex.match(lot_str)
        if not match: return None
        num, suffix = int(match.group(1)), match.group(2)
        return num, num, suffix


# --- NEW: Main function for formula number lookup ---
def get_formula_no_for_lot_range(session: Session, product_code: str, user_lot_entry: str) -> str:
    """
    Performs a sophisticated lookup for formula numbers based on a user's
    lot number entry, which can be a single lot, a range, or multiple
    semicolon-separated entries.
    """
    if not product_code or not user_lot_entry:
        return ""

    # 1. Fetch all relevant database records for the product code ONCE.
    # This is a critical performance optimization.
    db_query = select(TblProd01.T_LOTNUM, TblProd01.T_FID).where(TblProd01.T_PRODCODE == product_code)
    db_records = session.execute(db_query).all()

    # Pre-process database records into a more usable format
    parsed_db_lots = []
    for lot_num, formula_id in db_records:
        parsed = _parse_lot_string(lot_num)
        if parsed:
            parsed_db_lots.append({'start': parsed[0], 'end': parsed[1], 'suffix': parsed[2], 'formula': formula_id})

    # 2. Parse the user's input string into individual lookup tasks.
    user_lot_tasks = [entry.strip() for entry in user_lot_entry.split(';') if entry.strip()]

    final_formulas_ordered = []

    # 3. Process each part of the user's input.
    for task_lot_str in user_lot_tasks:
        parsed_user_lot = _parse_lot_string(task_lot_str)
        if not parsed_user_lot:
            continue

        user_start, user_end, user_suffix = parsed_user_lot
        formulas_for_this_task = set()

        # Find all database records that cover this user's lot range.
        for db_lot in parsed_db_lots:
            # Check for intersection: (StartA <= EndB) and (EndA >= StartB)
            if (db_lot['suffix'] == user_suffix and
                    db_lot['start'] <= user_end and
                    db_lot['end'] >= user_start):
                formulas_for_this_task.add(str(db_lot['formula']))

        # Add the unique formulas found for this task to our final list.
        final_formulas_ordered.extend(sorted(list(formulas_for_this_task)))

    # 4. De-duplicate the final list while preserving the order of first appearance.
    unique_ordered_formulas = []
    seen = set()
    for formula in final_formulas_ordered:
        if formula not in seen:
            unique_ordered_formulas.append(formula)
            seen.add(formula)

    return "; ".join(unique_ordered_formulas)
