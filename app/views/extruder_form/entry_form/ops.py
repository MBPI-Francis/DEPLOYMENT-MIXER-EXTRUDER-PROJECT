# app/views/extruder_form/entry_form/ops.py

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

    def get_lot_numbers_paginated(self, page: int = 1, page_size: int = 100, search_term: str = None,
                                  product_code: str = None) -> List[Dict[str, Any]]:
        """
        Fetches a paginated list of lot numbers.
        Supports searching AND filtering by a specific product code.
        """
        with self.Session() as session:
            query = session.query(
                TblProd01.T_PRODID,
                TblProd01.T_LOTNUM,
                TblProd01.T_PRODCODE
            ).filter(
                TblProd01.T_LOTNUM.isnot(None),
                TblProd01.T_LOTNUM != ''
            )

            if search_term:
                query = query.filter(TblProd01.T_LOTNUM.ilike(f"%{search_term}%"))

            # --- NEW FEATURE ---
            if product_code:
                query = query.filter(TblProd01.T_PRODCODE == product_code)
            # --- END NEW FEATURE ---

            query = query.order_by(TblProd01.T_PRODDATE.desc()) \
                .offset((page - 1) * page_size) \
                .limit(page_size)

            results = query.all()

            return [
                {
                    "prod_id": r.T_PRODID,
                    "lot_num": r.T_LOTNUM,
                    "product_code": r.T_PRODCODE
                } for r in results
            ]

    def get_data_for_lot_numbers(self, lot_numbers: List[str]) -> Dict[str, Any]:
        """
        Given a list of lot numbers, fetches and aggregates key production data.
        """
        if not lot_numbers:
            return {}

        with self.Session() as session:
            # Query the database for all records matching the lot numbers
            records = session.query(TblProd01).filter(TblProd01.T_LOTNUM.in_(lot_numbers)).all()

            if not records:
                return {}

            # Aggregate the data
            production_ids = sorted([str(r.T_PRODID) for r in records])
            product_codes = sorted(list(set([r.T_PRODCODE for r in records if r.T_PRODCODE])))
            order_nos = sorted(list(set([r.T_ORDERNUM for r in records if r.T_ORDERNUM])))
            total_input = sum([r.T_QTYPROD for r in records if r.T_QTYPROD is not None])

            # For customer, we'll just pick the first one found as a default
            customer_name = records[0].T_CUSTOMER if records else ""

            return {
                "production_id": "; ".join(production_ids),
                "product_code": "; ".join(product_codes),
                "order_no": "; ".join(order_nos),
                "total_input": total_input,
                "customer_name": customer_name
            }

    def get_details_for_lots(self, lot_numbers: List[str]) -> Dict[str, List[Dict]]:
        """
        Fetches all associated formula IDs and their materials for a given list of lot numbers.
        """
        if not lot_numbers:
            return {}

        with self.Session() as session:
            # First, find the unique Formula IDs (T_FID) from TblProd01 for the given lots
            prod_records = session.query(TblProd01.T_FID).filter(TblProd01.T_LOTNUM.in_(lot_numbers)).distinct().all()
            formula_ids = [fid for (fid,) in prod_records if fid is not None]

            if not formula_ids:
                return {}

            # Now, fetch the formula headers and their associated materials (details)
            # using the found formula IDs. A joinedload is very efficient here.
            formulas = session.query(TblFormula01).options(
                joinedload(TblFormula01.details)
            ).filter(
                TblFormula01.T_UID.in_(formula_ids)
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

    def get_customers(self) -> List[Customer]:
        """Fetches all customers for the ComboBox."""
        with self.Session() as session:
            return session.query(Customer).filter_by(is_deleted=False).order_by(Customer.name).all()

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
