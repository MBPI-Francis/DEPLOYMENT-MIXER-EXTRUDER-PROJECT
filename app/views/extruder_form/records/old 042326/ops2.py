# app/views/extruder_form/records/ops.py

from sqlalchemy.orm import sessionmaker, Session, joinedload, selectinload
from sqlalchemy import func, text, String, or_
from typing import Type, List, Tuple, Dict, cast
import decimal

from models import TblProd02, TblProd01
# Import all necessary models
from models.ExtruderCore import (
    ExtruderFormData, ExtruderOutput, PurgingHeader, ExtruderPersonnel, MachineDetail, MachineTemp, PurgingDetail,
    ScreenSize, ScrewConfig,
)
from models.ExtruderConfig import ExtruderMachine, Zone, Resin
from models.ProductionEmployees import ProductionEmployee, EmployeePosition

# Import the legacy functions
from app.database.legacy_ops import (
    get_initial_product_codes as legacy_get_initial_product_codes,
    search_all_product_codes as legacy_search_product_codes,
    get_initial_lot_numbers as legacy_get_initial_lot_numbers,
    search_all_lot_numbers as legacy_search_lot_numbers,
)

from datetime import datetime, timedelta


class ExtruderRecordsOperations:
    def __init__(self, session_factory: Type[Session]):
        self.Session = session_factory

    def get_produced_quantities_for_lots(self, lot_numbers: List[str]) -> Dict[str, decimal.Decimal]:
        """Fetches the produced quantity (T_QTYPROD) for a list of lot numbers."""
        if not lot_numbers:
            return {}
        with self.Session() as session:
            results = session.query(TblProd01.T_LOTNUM, TblProd01.T_QTYPROD).filter(
                TblProd01.T_LOTNUM.in_(lot_numbers)).all()
            return {lot_num: qty_prod for lot_num, qty_prod in results}

    def get_aggregated_materials_for_production_ids(self, prod_ids: List[str]) -> List[Tuple[str, decimal.Decimal]]:
        """Fetches materials for a given list of production IDs."""
        if not prod_ids:
            return []
        numeric_prod_ids = []
        for pid in prod_ids:
            try:
                numeric_prod_ids.append(decimal.Decimal(pid))
            except (decimal.InvalidOperation, ValueError):
                continue
        if not numeric_prod_ids:
            return []
        with self.Session() as session:
            results = session.query(
                TblProd02.T_MATCODE,
                func.sum(TblProd02.T_WT).label("total_weight")
            ).filter(
                TblProd02.T_PRODID.in_(numeric_prod_ids),
                TblProd02.T_DELETED.is_not(True)
            ).group_by(TblProd02.T_MATCODE).order_by(TblProd02.T_MATCODE).all()
            return results

    def get_initial_product_codes(self, limit: int = 100) -> List[str]:
        session = self.Session()
        try:
            return legacy_get_initial_product_codes(session, limit=limit)
        finally:
            session.close()

    def search_product_codes(self, search_term: str) -> List[str]:
        session = self.Session()
        try:
            return legacy_search_product_codes(session, search_term=search_term)
        finally:
            session.close()

    def get_initial_lot_numbers(self, limit: int = 100) -> List[str]:
        session = self.Session()
        try:
            return legacy_get_initial_lot_numbers(session, limit=limit)
        finally:
            session.close()

    def search_lot_numbers(self, search_term: str) -> List[str]:
        session = self.Session()
        try:
            return legacy_search_lot_numbers(session, search_term=search_term)
        finally:
            session.close()

    # def get_records_with_details(self, filters: dict = None):
    #     """
    #     Fetches ExtruderFormData records by applying all filters at the database level.
    #     Includes FIX for DetachedInstanceError by eager loading PurgingDetails AND Resin.
    #     """
    #     if filters is None:
    #         filters = {}
    #
    #     session = self.Session()
    #     try:
    #         # --- QUERY LOADING STRATEGY ---
    #         # We use selectinload for collections and joinedload for single items (like Resin)
    #         query = session.query(ExtruderFormData).options(
    #             joinedload(ExtruderFormData.machine),
    #             selectinload(ExtruderFormData.extruder_outputs),
    #
    #             # FIX IS HERE: Chain the loading to get Resin inside PurgingDetails
    #             selectinload(ExtruderFormData.purging_headers)
    #             .selectinload(PurgingHeader.purging_details)
    #             .joinedload(PurgingDetail.resin),
    #
    #             selectinload(ExtruderFormData.extruder_personnels).joinedload(ExtruderPersonnel.employee)
    #         )
    #
    #         # --- DYNAMIC FILTERING ---
    #         if filters.get('show_only_deleted', False):
    #             query = query.filter(ExtruderFormData.is_deleted == True)
    #         else:
    #             query = query.filter(ExtruderFormData.is_deleted == False)
    #
    #         if search_term := filters.get('search_term'):
    #             search_ilike = f"%{search_term}%"
    #             search_conditions = [
    #                 ExtruderFormData.lot_number.ilike(search_ilike),
    #                 ExtruderFormData.product_code.ilike(search_ilike),
    #                 ExtruderFormData.customer.ilike(search_ilike)
    #             ]
    #             if search_term.isdigit():
    #                 ref_no_condition = ExtruderFormData.ref_no.cast(String).like(search_ilike)
    #                 search_conditions.append(ref_no_condition)
    #             query = query.filter(or_(*search_conditions))
    #
    #         if date_from := filters.get('date_from'):
    #             query = query.filter(func.date(ExtruderFormData.created_at) >= date_from)
    #         if date_to := filters.get('date_to'):
    #             query = query.filter(func.date(ExtruderFormData.created_at) <= date_to)
    #
    #         if machine_id := filters.get('machine_id'):
    #             query = query.filter(ExtruderFormData.machine_id == machine_id)
    #         if product_code := filters.get('product_code'):
    #             query = query.filter(ExtruderFormData.product_code == product_code)
    #         if lot_number_exact := filters.get('lot_number_exact'):
    #             query = query.filter(ExtruderFormData.lot_number == lot_number_exact)
    #         if operator_id := filters.get('operator_id'):
    #             query = query.join(ExtruderPersonnel).filter(ExtruderPersonnel.employee_id == operator_id)
    #
    #         query = query.order_by(ExtruderFormData.created_at.desc())
    #         results = query.all()
    #         return results
    #
    #     finally:
    #         session.close()

    # --- Helper methods to populate the Filter Dialog ---

    def get_records_with_details(self, filters: dict = None):
        """
        Fetches ExtruderFormData records.
        DATE FILTER IS NOW APPLIED TO THE `datetime_start` of the output logs.
        """
        if filters is None:
            filters = {}

        session = self.Session()
        try:
            query = session.query(ExtruderFormData).options(
                joinedload(ExtruderFormData.machine),
                selectinload(ExtruderFormData.extruder_outputs),
                selectinload(ExtruderFormData.purging_headers).selectinload(PurgingHeader.purging_details).joinedload(
                    PurgingDetail.resin),
                selectinload(ExtruderFormData.extruder_personnels).joinedload(ExtruderPersonnel.employee)
            )

            if filters.get('show_only_deleted', False):
                query = query.filter(ExtruderFormData.is_deleted == True)
            else:
                query = query.filter(ExtruderFormData.is_deleted == False)

            if search_term := filters.get('search_term'):
                search_ilike = f"%{search_term}%"
                search_conditions = [
                    ExtruderFormData.lot_number.ilike(search_ilike),
                    ExtruderFormData.product_code.ilike(search_ilike),
                    ExtruderFormData.customer.ilike(search_ilike)
                ]
                if search_term.isdigit():
                    ref_no_condition = ExtruderFormData.ref_no.cast(String).like(search_ilike)
                    search_conditions.append(ref_no_condition)
                query = query.filter(or_(*search_conditions))

            # --- THIS IS THE CORRECTED DATE FILTER LOGIC ---
            date_conditions = []
            if date_from := filters.get('date_from'):
                # Filter where the date part of datetime_start is on or after date_from
                date_conditions.append(func.date(ExtruderOutput.datetime_start) >= date_from)
            if date_to := filters.get('date_to'):
                # Filter where the date part of datetime_start is on or before date_to
                date_conditions.append(func.date(ExtruderOutput.datetime_start) <= date_to)

            if date_conditions:
                # If any date filters are present, we must JOIN to the ExtruderOutput table
                # and apply the conditions. We also add distinct() to prevent duplicate rows.
                query = query.join(ExtruderFormData.extruder_outputs).filter(*date_conditions).distinct()
            # --- END OF CORRECTION ---

            if machine_id := filters.get('machine_id'):
                query = query.filter(ExtruderFormData.machine_id == machine_id)
            if product_code := filters.get('product_code'):
                query = query.filter(ExtruderFormData.product_code == product_code)
            if lot_number_exact := filters.get('lot_number_exact'):
                query = query.filter(ExtruderFormData.lot_number == lot_number_exact)
            if operator_id := filters.get('operator_id'):
                query = query.join(ExtruderPersonnel).filter(ExtruderPersonnel.employee_id == operator_id)

            query = query.order_by(ExtruderFormData.created_at.desc())
            results = query.all()
            return results
        finally:
            session.close()

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
            return [row[0] for row in results if row[0]]
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

    def restore_multiple_records(self, record_ids: List[int]) -> bool:
        if not record_ids:
            return False
        session = self.Session()
        try:
            session.query(ExtruderFormData) \
                .filter(ExtruderFormData.id.in_(record_ids)) \
                .update({"is_deleted": False}, synchronize_session=False)
            session.commit()
            return True
        except Exception:
            session.rollback()
            return False
        finally:
            session.close()

    # --- UPDATED: Optimized Data Fetching for Export ---
    def get_export_data(self, filters: dict = None):
        """
        Fetches flattened data specifically for the Summary List Export.
        """
        records = self.get_records_with_details(filters)

        export_data = []

        for r in records:
            # 1. Calculate Time & Duration
            start_times = [o.datetime_start for o in r.extruder_outputs if o.datetime_start]
            end_times = [o.datetime_end for o in r.extruder_outputs if o.datetime_end]

            time_start = min(start_times) if start_times else None
            time_end = max(end_times) if end_times else None

            # Total Extrusion Duration
            total_ext_seconds = sum(
                (o.datetime_end - o.datetime_start).total_seconds()
                for o in r.extruder_outputs
                if o.datetime_start and o.datetime_end and o.datetime_end > o.datetime_start
            )

            ext_total_minutes = int(total_ext_seconds // 60)
            ext_hours = ext_total_minutes // 60
            ext_minutes = ext_total_minutes % 60
            ext_duration_str = f"{ext_hours:02}:{ext_minutes:02}"

            # 2. Outputs
            total_output = sum(o.qty_output or 0 for o in r.extruder_outputs)

            total_hours_float = total_ext_seconds / 3600.0
            out_per_hr = (float(total_output) / total_hours_float) if total_hours_float > 0 else 0.0

            # 3. Purging (Time & Materials)
            total_purge_seconds = 0
            purge_codes = set()

            total_cleaning_qty = 0.0
            cleaning_materials = set()

            for p in r.purging_headers:
                if p.product_code:
                    purge_codes.add(p.product_code)

                if p.time_start and p.time_end:
                    dummy_date = datetime.min.date()
                    s = datetime.combine(dummy_date, p.time_start)
                    e = datetime.combine(dummy_date, p.time_end)
                    if e < s: e += timedelta(days=1)
                    total_purge_seconds += (e - s).total_seconds()

                # Iterate Details for Materials
                for d in p.purging_details:
                    if d.qty:
                        total_cleaning_qty += float(d.qty)

                    # SAFE ACCESS: Resin is now eager loaded
                    if d.resin:
                        mat_name = d.resin.abbreviation or d.resin.name
                        if mat_name:
                            cleaning_materials.add(mat_name)

            # Format Strings
            purge_total_minutes = int(total_purge_seconds // 60)
            p_hours = purge_total_minutes // 60
            p_minutes = purge_total_minutes % 60
            purge_duration_str = f"{p_hours:02}:{p_minutes:02}"

            purge_code_str = ", ".join(sorted(purge_codes))
            cleaning_mat_str = ", ".join(sorted(cleaning_materials))

            # 4. Operators
            operators = set()
            for p in r.extruder_personnels:
                if p.employee:
                    name = f"{p.employee.first_name} {p.employee.last_name}".strip()
                    operators.add(name)
            operator_str = ", ".join(sorted(operators))

            # 5. Build Row
            row = {
                'Date Encoded': r.created_at.strftime("%Y-%m-%d %H:%M") if r.created_at else "",
                'Reference No': r.ref_no,
                'Machine Name': r.machine.name if r.machine else "",
                'Product Code': r.product_code,
                'Formula No': r.formula_no,
                'Lot Number': r.lot_number,
                'Customer': r.customer,
                'Total Output': float(total_output),
                'Target Output': float(r.target_output_per_hour or 0),
                'Date Time Start': time_start.strftime("%Y-%m-%d %H:%M") if time_start else "",
                'Date Time End': time_end.strftime("%Y-%m-%d %H:%M") if time_end else "",
                'Extrusion Duration': ext_duration_str,
                'Total Output per/hr': float(f"{out_per_hr:.2f}"),
                'Purging Duration': purge_duration_str,
                'Purging To Code': purge_code_str,
                'Cleaning Material': cleaning_mat_str,
                'Total Cleaning QTY': total_cleaning_qty,
                'Operators': operator_str
            }
            export_data.append(row)

        return export_data