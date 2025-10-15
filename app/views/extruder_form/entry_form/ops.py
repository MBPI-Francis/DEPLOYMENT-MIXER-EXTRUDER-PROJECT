# app/views/extruder_form/entry_form/ops.py
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, sessionmaker, joinedload
from typing import Type, List, Dict, Any

# Import all necessary models
from models import (
    TblProd01, TblFormula01, TblFormula02, Customer, ExtruderMachine,
    Zone, ProductionEmployee, EmployeePosition, Resin, ScreenSize,
    ExtruderFormData  # Add other models as needed
)


class ExtruderOpsController:
    """
    Handles all business logic and database operations for the Extruder Entry Form.
    """

    def __init__(self, session_factory: Type[sessionmaker]):
        self.Session = session_factory

    # --- THIS IS THE NEW METHOD ---
    def get_total_batch_weight_for_lots(self, lot_numbers: List[str]) -> Decimal:
        """
        Calculates the sum of the batch weights (T_QTYREQ) for a given
        list of lot numbers.
        """
        if not lot_numbers:
            return Decimal("0.00")

        with self.Session() as session:
            # Query for the T_QTYREQ column for all matching, non-deleted lots
            results = session.query(TblProd01.T_QTYREQ).filter(
                TblProd01.T_LOTNUM.in_(lot_numbers),
                TblProd01.T_DELETED.is_(False)
            ).all()

            # Sum the results, ensuring None values are treated as 0
            total_weight = sum(qty for (qty,) in results if qty is not None)

            return total_weight

    # --- NEW METHOD: The core of the new feature ---
    def calculate_total_input(self, lot_numbers: List[str], formula_numbers: List[str]) -> Decimal:
        """
        Calculates the total input quantity based on the sum of materials for
        selected formulas, accounting for how many selected lots use each formula.
        """
        if not lot_numbers or not formula_numbers:
            return Decimal("0.00")

        with self.Session() as session:
            # 1. Find which of the selected formulas is used by each selected lot.
            # This creates a mapping of {lot_num: formula_id}
            lot_to_formula_map = dict(session.query(
                TblProd01.T_LOTNUM,
                TblProd01.T_FID
            ).filter(
                TblProd01.T_LOTNUM.in_(lot_numbers),
                TblProd01.T_DELETED.is_(False)
            ).all())

            # 2. Count how many times each selected formula is actually used by the selected lots.
            formula_usage_count = {}
            for lot, fid in lot_to_formula_map.items():
                fid_str = str(fid)
                if fid_str in formula_numbers:  # Only count if the user selected this formula
                    formula_usage_count[fid_str] = formula_usage_count.get(fid_str, 0) + 1

            if not formula_usage_count:
                return Decimal("0.00")

            # 3. Get the sum of material quantities (T_CON) for each required formula ID in a single query.
            # This returns a list of tuples like [(formula_id, total_qty), ...]
            formula_material_sums = session.query(
                TblFormula02.T_UID,
                func.sum(TblFormula02.T_CON)
            ).filter(
                TblFormula02.T_UID.in_([int(f) for f in formula_usage_count.keys()]),
                TblFormula02.T_DELETED.is_(False)
            ).group_by(TblFormula02.T_UID).all()

            formula_totals_map = {str(uid): total for uid, total in formula_material_sums}

            # 4. Calculate the final total input.
            total_input = Decimal(0)
            for fid, count in formula_usage_count.items():
                # Multiply the sum of materials for a formula by the number of lots that use it.
                total_input += formula_totals_map.get(fid, Decimal(0)) * count

            return total_input


    def get_lot_numbers_paginated(self, page: int = 1,
                                  page_size: int = 100,
                                  search_term: str = None,
                                  product_code: str = None,
                                  customer: str = None) -> List[Dict[str, Any]]:
        """
        Fetches a paginated list of lot numbers.
        Supports searching AND filtering by a specific product code.
        """
        with self.Session() as session:
            query = session.query(
                TblProd01.T_PRODID,
                TblProd01.T_LOTNUM,
                TblProd01.T_PRODCODE,
                TblProd01.T_QTYREQ,  # <-- ADDED
                TblProd01.T_CUSTOMER  # <-- ADDED
            ).filter(
                TblProd01.T_LOTNUM.isnot(None),
                TblProd01.T_LOTNUM != '',
                TblProd01.T_DELETED.isnot(True),
                TblProd01.T_FID.isnot(None),
                TblProd01.T_FID !=0,
            )

            if search_term:
                query = query.filter(TblProd01.T_LOTNUM.ilike(f"%{search_term}%"))


            if product_code:
                query = query.filter(TblProd01.T_PRODCODE == product_code)


            if customer:
                query = query.filter(TblProd01.T_CUSTOMER == customer)

            query = query.order_by(TblProd01.T_PRODDATE.desc()) \
                .offset((page - 1) * page_size) \
                .limit(page_size)

            results = query.all()

            return [
                {
                    "prod_id": r.T_PRODID,
                    "lot_num": r.T_LOTNUM,
                    "product_code": r.T_PRODCODE,
                    "batch_weight": r.T_QTYREQ,  # <-- ADDED,
                    "customer": r.T_CUSTOMER
                } for r in results
            ]

    def get_details_for_lot(self, lot_number: str) -> Dict | None:
        """
        Finds the product code and customer for a single, specific lot number.
        Returns a dictionary or None if not found.
        """
        if not lot_number:
            return None

        with self.Session() as session:
            result = session.query(
                TblProd01.T_PRODCODE,
                TblProd01.T_CUSTOMER
            ).filter(
                TblProd01.T_LOTNUM == lot_number,
                TblProd01.T_DELETED.is_(False)
            ).first()

            if result:
                return {"product_code": result.T_PRODCODE, "customer": result.T_CUSTOMER}
            return None


    # --- METHOD MODIFIED: Remove the old, incorrect total_input calculation ---
    def get_data_for_lot_numbers(self, lot_numbers: List[str]) -> Dict[str, Any]:
        """
        Given a list of lot numbers, fetches and aggregates key production data.
        Total input is now calculated separately.
        """
        if not lot_numbers:
            return {}

        with self.Session() as session:
            records = session.query(TblProd01).filter(
                TblProd01.T_LOTNUM.in_(lot_numbers),
                TblProd01.T_DELETED.is_(False)
            ).all()

            if not records:
                return {}

            production_ids = sorted([str(r.T_PRODID) for r in records])
            product_codes = sorted(list(set([r.T_PRODCODE for r in records if r.T_PRODCODE])))
            order_nos = sorted(list(set([r.T_ORDERNUM for r in records if r.T_ORDERNUM])))
            customer_name = records[0].T_CUSTOMER if records else ""

            return {
                "production_id": "; ".join(production_ids),
                "product_code": "; ".join(product_codes),
                "order_no": "; ".join(order_nos),
                "customer_name": customer_name
                # The incorrect total_input calculation has been removed from here.
            }



    def get_details_for_lots(self, lot_numbers: List[str]) -> Dict[str, List[Dict]]:
        """
        Fetches all associated formula IDs and their materials for a given list of lot numbers.
        """
        if not lot_numbers:
            return {}

        with self.Session() as session:
            # First, find the unique Formula IDs (T_FID) from TblProd01 for the given lots
            prod_records = session.query(TblProd01.T_FID).filter(TblProd01.T_LOTNUM.in_(lot_numbers),
                                                                 TblProd01.T_DELETED.isnot(True)
                                                                 ).distinct().all()
            formula_ids = [fid for (fid,) in prod_records if fid is not None]

            if not formula_ids:
                return {}

            # Now, fetch the formula headers and their associated materials (details)
            # using the found formula IDs. A joinedload is very efficient here.
            formulas = session.query(TblFormula01).options(
                joinedload(TblFormula01.details)
            ).filter(
                TblFormula01.T_UID.in_(formula_ids),

            ).all()

            # Structure the data for the dialog
            results = {}
            for formula in formulas:
                materials = [
                    {
                        "mat_code": detail.T_MATCODE,
                        "qty": detail.T_CON
                    }
                    for detail in formula.details
                    if detail.T_MATCODE and not detail.T_DELETED
                ]
                results[str(formula.T_UID)] = materials

            return results



    def get_machines(self) -> List[ExtruderMachine]:
        """Fetches all extruder machines for the ComboBox."""
        with self.Session() as session:
            return session.query(ExtruderMachine).filter_by(is_deleted=False).order_by(ExtruderMachine.name).all()

    def save_full_form(self, form_data: Dict[str, Any]):
        """
        Saves all data from the main form and its sub-forms to the database.
        This will be a transactional operation.
        """
        print("--- SIMULATING SAVE ---")
        import json
        print(json.dumps(form_data, indent=2))
        print("--- SAVE COMPLETE (SIMULATED) ---")

    def get_product_code_for_lot(self, lot_number: str) -> str | None:
        """
        Finds the product code for a single, specific lot number.
        Returns the product code string or None if not found.
        """
        if not lot_number:
            return None

        with self.Session() as session:
            result = session.query(TblProd01.T_PRODCODE).filter(
                TblProd01.T_LOTNUM == lot_number
            ).first()

            return result[0] if result else None
