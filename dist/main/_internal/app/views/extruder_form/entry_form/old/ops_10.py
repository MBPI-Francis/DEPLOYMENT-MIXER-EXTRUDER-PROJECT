# # app/views/extruder_form/entry_form/ops.py
#
# from sqlalchemy.orm import Session, sessionmaker
# from sqlalchemy import func
# from typing import Type, List, Dict, Any
# from decimal import Decimal
#
# from models import (
#     TblProd01, TblProd02, Customer, ExtruderMachine
# )
#
#
# class ExtruderOpsController:
#     """
#     Handles all business logic and database operations for the Extruder Entry Form.
#     """
#
#     def __init__(self, session_factory: Type[sessionmaker]):
#         self.Session = session_factory
#
#     def get_lot_numbers_paginated(self, page: int = 1, page_size: int = 100, search_term: str = None,
#                                   product_code: str = None, customer: str = None) -> List[Dict[str, Any]]:
#         """
#         Fetches a paginated list of lot numbers, including all necessary details
#         for filtering and display.
#         """
#         with self.Session() as session:
#             query = session.query(
#                 TblProd01.T_PRODID,
#                 TblProd01.T_LOTNUM,
#                 TblProd01.T_PRODCODE,
#                 TblProd01.T_QTYREQ,
#                 TblProd01.T_CUSTOMER,
#                 TblProd01.T_FID
#             ).filter(
#                 TblProd01.T_LOTNUM.isnot(None),
#                 TblProd01.T_LOTNUM != '',
#                 TblProd01.T_DELETED.is_(False),
#             )
#
#             if search_term:
#                 query = query.filter(TblProd01.T_LOTNUM.ilike(f"%{search_term}%"))
#             if product_code:
#                 query = query.filter(TblProd01.T_PRODCODE == product_code)
#             if customer:
#                 query = query.filter(TblProd01.T_CUSTOMER == customer)
#
#             query = query.order_by(TblProd01.T_PRODDATE.desc()) \
#                 .offset((page - 1) * page_size) \
#                 .limit(page_size)
#
#             results = query.all()
#
#             return [
#                 {
#                     "prod_id": r.T_PRODID,
#                     "lot_num": r.T_LOTNUM,
#                     "product_code": r.T_PRODCODE,
#                     "batch_weight": r.T_QTYREQ,
#                     "customer": r.T_CUSTOMER,
#                     "formula_id": r.T_FID
#                 } for r in results
#             ]
#
#     def get_materials_for_prod_ids(self, prod_ids: List[Decimal]) -> List[Dict[str, Any]]:
#         """
#         Fetches all material records from TblProd02 for a given list of T_PRODID values.
#         """
#         if not prod_ids:
#             return []
#
#         with self.Session() as session:
#             records = session.query(
#                 TblProd02.T_MATCODE,
#                 TblProd02.T_WT
#             ).filter(
#                 TblProd02.T_PRODID.in_(prod_ids),
#                 TblProd02.T_DELETED.is_(False)
#             ).order_by(TblProd02.T_SEQ).all()
#
#             return [
#                 {"mat_code": r.T_MATCODE, "qty": r.T_WT} for r in records
#             ]
#
#     def get_details_for_lot(self, lot_number: str) -> Dict | None:
#         """
#         Finds the product code and customer for a single, specific lot number.
#         """
#         if not lot_number:
#             return None
#         with self.Session() as session:
#             result = session.query(
#                 TblProd01.T_PRODCODE,
#                 TblProd01.T_CUSTOMER
#             ).filter(
#                 TblProd01.T_LOTNUM == lot_number,
#                 TblProd01.T_DELETED.is_(False)
#             ).first()
#             if result:
#                 return {"product_code": result.T_PRODCODE, "customer": result.T_CUSTOMER}
#             return None
#
#     def get_total_batch_weight_for_lots(self, lot_numbers: List[str]) -> Decimal:
#         """
#         Calculates the sum of the batch weights (T_QTYREQ) for a given list of lot numbers.
#         """
#         if not lot_numbers:
#             return Decimal("0.00")
#         with self.Session() as session:
#             results = session.query(TblProd01.T_QTYREQ).filter(
#                 TblProd01.T_LOTNUM.in_(lot_numbers),
#                 TblProd01.T_DELETED.is_(False)
#             ).all()
#             total_weight = sum(qty for (qty,) in results if qty is not None)
#             return total_weight
#
#     def get_machines(self) -> List[ExtruderMachine]:
#         """Fetches all extruder machines for the ComboBox."""
#         with self.Session() as session:
#             return session.query(ExtruderMachine).filter_by(is_deleted=False).order_by(ExtruderMachine.name).all()
#
#     def save_full_form(self, form_data: Dict[str, Any]):
#         """Saves all data from the main form."""
#         print("--- SIMULATING SAVE ---")
#         import json
#         print(json.dumps(form_data, indent=2, default=str))
#         print("--- SAVE COMPLETE (SIMULATED) ---")

# app/views/extruder_form/entry_form/ops.py

from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy import func, or_, cast, String
from typing import Type, List, Dict, Any
from decimal import Decimal

from models import (
    TblProd01, TblProd02, Customer, ExtruderMachine
)


class ExtruderOpsController:
    """
    Handles all business logic and database operations for the Extruder Entry Form.
    """

    def __init__(self, session_factory: Type[sessionmaker]):
        self.Session = session_factory

    # --- THIS IS THE ONLY METHOD THAT IS CHANGED ---
    def get_lot_numbers_paginated(self, page: int = 1, page_size: int = 100, search_term: str = None,
                                  product_code: str = None, customer: str = None) -> List[Dict[str, Any]]:
        """
        Fetches a paginated list of lot numbers, including all necessary details.
        Search is now performed on both T_PRODID and T_LOTNUM.
        """
        with self.Session() as session:
            query = session.query(
                TblProd01.T_PRODID,
                TblProd01.T_LOTNUM,
                TblProd01.T_PRODCODE,
                TblProd01.T_QTYREQ,
                TblProd01.T_CUSTOMER,
                TblProd01.T_FID,
                TblProd01.T_ORDERNUM
            ).filter(
                TblProd01.T_LOTNUM.isnot(None),
                TblProd01.T_LOTNUM != '',
                TblProd01.T_DELETED.is_(False)
            )

            # --- MODIFIED: Enhanced search logic ---
            if search_term:
                # Search across both Lot Number and Production ID (cast to string)
                search_filter = or_(
                    TblProd01.T_LOTNUM.ilike(f"%{search_term}%"),
                    cast(TblProd01.T_PRODID, String).ilike(f"%{search_term}%")
                )
                query = query.filter(search_filter)
            # --- END MODIFIED ---

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
                    "batch_weight": r.T_QTYREQ,
                    "customer": r.T_CUSTOMER,
                    "formula_id": r.T_FID,
                    "order_no": r.T_ORDERNUM
                } for r in results
            ]

    def get_materials_for_prod_ids(self, prod_ids: List[Decimal]) -> List[Dict[str, Any]]:
        """
        Fetches all material records from TblProd02 for a given list of T_PRODID values.
        """
        if not prod_ids:
            return []
        with self.Session() as session:
            records = session.query(
                TblProd02.T_MATCODE,
                TblProd02.T_WT
            ).filter(
                TblProd02.T_PRODID.in_(prod_ids),
                TblProd02.T_DELETED.is_(False),
                TblProd02.T_WT != 0
            ).order_by(TblProd02.T_SEQ).all()
            return [{"mat_code": r.T_MATCODE, "qty": r.T_WT} for r in records]

    def get_details_for_lot(self, lot_number: str) -> Dict | None:
        """
        Finds the product code and customer for a single, specific lot number.
        """
        if not lot_number:
            return None
        with self.Session() as session:
            result = session.query(
                TblProd01.T_PRODCODE,
                TblProd01.T_CUSTOMER,
                TblProd01.T_ORDERNUM
            ).filter(
                TblProd01.T_LOTNUM == lot_number,
                TblProd01.T_DELETED.is_(False)
            ).first()
            if result:
                return {"product_code": result.T_PRODCODE,
                        "customer": result.T_CUSTOMER,
                        "order_no": result.T_ORDERNUM
                        }
            return None

    def get_total_batch_weight_for_lots(self, lot_numbers: List[str]) -> Decimal:
        """
        Calculates the sum of the batch weights (T_QTYREQ) for a given list of lot numbers.
        """
        if not lot_numbers:
            return Decimal("0.00")
        with self.Session() as session:
            results = session.query(TblProd01.T_QTYREQ).filter(
                TblProd01.T_LOTNUM.in_(lot_numbers),
                TblProd01.T_DELETED.is_(False)
            ).all()
            total_weight = sum(qty for (qty,) in results if qty is not None)
            return total_weight

    def get_machines(self) -> List[ExtruderMachine]:
        """Fetches all extruder machines for the ComboBox."""
        with self.Session() as session:
            return session.query(ExtruderMachine).filter_by(is_deleted=False).order_by(ExtruderMachine.name).all()

    def save_full_form(self, form_data: Dict[str, Any]):
        """Saves all data from the main form."""
        print("--- SIMULATING SAVE ---")
        import json
        print(json.dumps(form_data, indent=2, default=str))
        print("--- SAVE COMPLETE (SIMULATED) ---")