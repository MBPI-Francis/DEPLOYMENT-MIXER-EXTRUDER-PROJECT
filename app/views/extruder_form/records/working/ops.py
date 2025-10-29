# app/views/extruder_form/records/ops.py

from sqlalchemy.orm import sessionmaker, Session, joinedload, selectinload
from sqlalchemy import func, text
from typing import Type, List, Tuple
import decimal

# Import all necessary models
from models.ExtruderCore import (
    ExtruderFormData, ExtruderOutput, PurgingHeader, ExtruderPersonnel, MachineDetail, MachineTemp, PurgingDetail,
ScreenSize, ScrewConfig,
)
from models.ExtruderConfig import ExtruderMachine,  Zone, Resin
from models.ProductionEmployees import ProductionEmployee, EmployeePosition

# --- NEW: Import the legacy functions to be used ---
from app.database.legacy_ops import (
    get_initial_product_codes as legacy_get_initial_product_codes,
    search_all_product_codes as legacy_search_product_codes,
    get_initial_lot_numbers as legacy_get_initial_lot_numbers,
    search_all_lot_numbers as legacy_search_lot_numbers,
)


class ExtruderRecordsOperations:
    def __init__(self, session_factory: Type[Session]):
        self.Session = session_factory


    def get_initial_product_codes(self, limit: int = 100) -> List[str]:
        """
        Gets initial product codes by calling the legacy database function.
        """
        session = self.Session()
        try:
            # Delegate the call to the imported legacy function
            return legacy_get_initial_product_codes(session, limit=limit)
        finally:
            session.close()

    def search_product_codes(self, search_term: str) -> List[str]:
        """
        Searches product codes by calling the legacy database function.
        """
        session = self.Session()
        try:
            # Delegate the call to the imported legacy function
            return legacy_search_product_codes(session, search_term=search_term)
        finally:
            session.close()

    def get_initial_lot_numbers(self, limit: int = 100) -> List[str]:
        """
        Gets initial lot numbers by calling the legacy database function.
        """
        session = self.Session()
        try:
            # Delegate the call to the imported legacy function
            return legacy_get_initial_lot_numbers(session, limit=limit)
        finally:
            session.close()

    def search_lot_numbers(self, search_term: str) -> List[str]:
        """
        Searches lot numbers by calling the legacy database function.
        """
        session = self.Session()
        try:
            # Delegate the call to the imported legacy function
            return legacy_search_lot_numbers(session, search_term=search_term)
        finally:
            session.close()


    def get_records_with_details(self, filters: dict = None):
        """
        Fetches ExtruderFormData records with all necessary child relationships
        eagerly loaded, applying a dynamic set of filters from a dictionary.
        """
        if filters is None:
            filters = {}

        session = self.Session()
        try:
            # Base query with all necessary eager loading for performance
            query = session.query(ExtruderFormData).options(
                joinedload(ExtruderFormData.machine),
                selectinload(ExtruderFormData.extruder_outputs),
                selectinload(ExtruderFormData.purging_headers),
                selectinload(ExtruderFormData.extruder_personnels).joinedload(ExtruderPersonnel.employee)
            )


            # --- DYNAMIC FILTERING ---

            # --- MODIFIED: Logic for handling deleted records ---
            if filters.get('show_only_deleted', False):
                # If the box is checked, ONLY show deleted records.
                query = query.filter(ExtruderFormData.is_deleted == True)
            else:
                # If the box is NOT checked (the default state), ONLY show active records.
                query = query.filter(ExtruderFormData.is_deleted == False)

            # Show/Hide Deleted Records
            if not filters.get('show_deleted', False):
                query = query.filter(ExtruderFormData.is_deleted == False)

            # Global Search Term
            if search_term := filters.get('search_term'):
                search_ilike = f"%{search_term}%"
                query = query.filter(
                    (ExtruderFormData.lot_number.ilike(search_ilike)) |
                    (ExtruderFormData.product_code.ilike(search_ilike)) |
                    (ExtruderFormData.customer.ilike(search_ilike))
                )

            # Date Range
            if date_from := filters.get('date_from'):
                query = query.filter(func.date(ExtruderFormData.created_at) >= date_from)
            if date_to := filters.get('date_to'):
                query = query.filter(func.date(ExtruderFormData.created_at) <= date_to)

            # ---- ADVANCED FILTERS ----
            if machine_id := filters.get('machine_id'):
                query = query.filter(ExtruderFormData.machine_id == machine_id)
            if product_code := filters.get('product_code'):
                query = query.filter(ExtruderFormData.product_code == product_code)
            if lot_number := filters.get('lot_number'):
                query = query.filter(ExtruderFormData.lot_number.ilike(f"%{lot_number}%"))
            if lot_number_exact := filters.get('lot_number_exact'):
                query = query.filter(ExtruderFormData.lot_number == lot_number_exact)

            # Filtering on related tables (requires joins)
            if operator_id := filters.get('operator_id'):
                query = query.join(ExtruderPersonnel).filter(ExtruderPersonnel.employee_id == operator_id)

            # Filtering on aggregated values (requires subqueries/CTEs or HAVING clauses)
            # For simplicity and performance, we will filter these in Python for now.
            # A pure SQL HAVING clause would be more complex to integrate with the ORM object loading.

            # --- Ordering and Execution ---
            query = query.order_by(ExtruderFormData.created_at.desc())

            results = query.all()

            # --- Post-query filtering for calculated fields ---
            # This is a trade-off: it's slightly less efficient than a pure SQL `HAVING` clause,
            # but it is much simpler to implement and keeps the ORM objects clean.
            # For the number of records typically displayed, this is perfectly acceptable.

            final_results = []

            # Check if any numeric filters exist
            has_numeric_filter = any(
                k in filters for k in ['total_output_min', 'total_output_max', 'output_hr_min', 'output_hr_max'])

            if not has_numeric_filter:
                return results

            for record in results:
                total_output = sum(out.qty_output for out in record.extruder_outputs if out.qty_output)

                # Conditions for filtering
                passes_filter = True
                if min_val := filters.get('total_output_min'):
                    if total_output < min_val: passes_filter = False
                if max_val := filters.get('total_output_max'):
                    if total_output > max_val: passes_filter = False

                # Output/hr filtering is complex, so we skip it for now but the structure is here
                # to add it later if needed.

                if passes_filter:
                    final_results.append(record)

            return final_results

        finally:
            session.close()

    # --- NEW: Helper methods to populate the Filter Dialog ---

    def get_distinct_machines(self) -> List[Tuple[int, str]]:
        session = self.Session()
        try:
            return session.query(ExtruderMachine.id, ExtruderMachine.name).filter(
                ExtruderMachine.is_deleted == False).order_by(ExtruderMachine.name).all()
        finally:
            session.close()

    def get_distinct_product_codes(self) -> List[str]:
        session = self.Session()
        try:
            results = session.query(ExtruderFormData.product_code).distinct().order_by(
                ExtruderFormData.product_code).all()
            return [row[0] for row in results if row[0]]  # Return a simple list of strings
        finally:
            session.close()

    def get_distinct_operators(self) -> List[Tuple[int, str]]:
        session = self.Session()
        try:
            results = session.query(ProductionEmployee.id, ProductionEmployee.first_name, ProductionEmployee.last_name) \
                .filter(ProductionEmployee.is_deleted == False) \
                .order_by(ProductionEmployee.first_name, ProductionEmployee.last_name).all()
            return [(r.id, f"{r.first_name} {r.last_name}") for r in results]
        finally:
            session.close()




    def get_full_record_by_id(self, record_id: int):
        session = self.Session()
        try:
            return session.query(ExtruderFormData).filter(ExtruderFormData.id == record_id).options(
                joinedload(ExtruderFormData.machine),
                joinedload(ExtruderFormData.shift),
                joinedload(ExtruderFormData.machine_details).joinedload(MachineDetail.screen_size),
                joinedload(ExtruderFormData.machine_details).joinedload(MachineDetail.screw_config),
                selectinload(ExtruderFormData.machine_temps).joinedload(MachineTemp.zone),
                selectinload(ExtruderFormData.extruder_outputs),
                selectinload(ExtruderFormData.extruder_personnels).joinedload(ExtruderPersonnel.employee),
                selectinload(ExtruderFormData.extruder_personnels).joinedload(ExtruderPersonnel.position),
                selectinload(ExtruderFormData.purging_headers).joinedload(PurgingHeader.resin_used),
                selectinload(ExtruderFormData.purging_headers).selectinload(PurgingHeader.purging_details).joinedload(PurgingDetail.resin)
            ).first()
        finally:
            session.close()

    def soft_delete_record(self, record_id: int):
        session = self.Session()
        try:
            record = session.query(ExtruderFormData).filter_by(id=record_id).first()
            if record:
                record.is_deleted = True
                session.commit()
                return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    def restore_record(self, record_id: int):
        session = self.Session()
        try:
            record = session.query(ExtruderFormData).filter_by(id=record_id).first()
            if record:
                record.is_deleted = False
                session.commit()
                return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()