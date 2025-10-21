# app/views/extruder_form/entry_form/ops.py

from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, or_, cast, String
from typing import Type, List, Dict, Any
from decimal import Decimal

from models import (
    TblProd01, TblProd02, ExtruderMachine, ScreenSize, Resin, Zone,
    ProductionEmployee, EmployeePosition, ExtruderFormData, MachineConfig,
    UsedMaterial, ExtruderOutput, MachineTemp, ExtruderPersonnel,
    PurgingHeader, TblIncoming2
)


class ExtruderOpsController:
    """
    Handles all business logic and database operations for the Extruder Entry Form.
    """

    def __init__(self, session_factory: Type[sessionmaker]):
        self.Session = session_factory

    # --- NEW METHOD ---
    def get_order_qty_by_order_number(self, order_number: str) -> Decimal | None:
        """
        Finds the corresponding record in tbl_incoming2 using the order number
        and returns the quantity (t_qty).
        """
        if not order_number:
            return None

        with self.Session() as session:
            # Query TblIncoming2 for the t_qty where t_ctrlnum matches the order_number
            # .scalar() returns the first value of the first row, or None if no rows found.
            quantity = session.query(TblIncoming2.t_qty).filter(
                TblIncoming2.t_ctrlnum == order_number
            ).scalar()

            return quantity

    def get_all_machines(self) -> List[ExtruderMachine]:
        with self.Session() as session:
            return session.query(ExtruderMachine).filter_by(is_deleted=False).order_by(ExtruderMachine.name).all()

    def get_all_screen_sizes(self) -> List[ScreenSize]:
        with self.Session() as session:
            return session.query(ScreenSize).filter_by(is_deleted=False).order_by(ScreenSize.size).all()

    def get_all_resins(self) -> List[Resin]:
        with self.Session() as session:
            return session.query(Resin).filter_by(is_deleted=False).order_by(Resin.name).all()

    def get_all_zones(self) -> List[Zone]:
        """Fetches all zones for temperature settings."""
        with self.Session() as session:
            return session.query(Zone).filter_by(is_deleted=False).order_by(Zone.id).all()

    def get_all_employees(self) -> List[ProductionEmployee]:
        with self.Session() as session:
            return session.query(ProductionEmployee).filter_by(is_deleted=False).order_by(
                ProductionEmployee.last_name).all()

    def get_all_positions(self) -> List[EmployeePosition]:
        with self.Session() as session:
            return session.query(EmployeePosition).filter_by(is_deleted=False).order_by(EmployeePosition.name).all()

    # --- Methods from Lot Number Dialog (retained) ---

    # --- Lot Number Dialog Methods ---

    def get_lot_numbers_paginated(self, page: int = 1, page_size: int = 100, search_term: str = None,
                                  product_code: str = None, customer: str = None) -> List[Dict[str, Any]]:
        """
        Fetches a paginated list of lot numbers with a more robust filter.
        """
        with self.Session() as session:
            query = session.query(
                TblProd01.T_PRODID, TblProd01.T_LOTNUM, TblProd01.T_PRODCODE,
                TblProd01.T_QTYREQ, TblProd01.T_CUSTOMER, TblProd01.T_FID,
                TblProd01.T_ORDERNUM
            ).filter(
                TblProd01.T_LOTNUM.isnot(None),
                TblProd01.T_LOTNUM != '',
                # --- THE FIX IS HERE: Accept records where T_DELETED is False OR NULL ---
                or_(TblProd01.T_DELETED.is_(False), TblProd01.T_DELETED.is_(None))
            )

            if search_term:
                search_filter = or_(
                    TblProd01.T_LOTNUM.ilike(f"%{search_term}%"),
                    cast(TblProd01.T_PRODID, String).ilike(f"%{search_term}%")
                )
                query = query.filter(search_filter)
            if product_code:
                query = query.filter(TblProd01.T_PRODCODE == product_code)
            if customer:
                query = query.filter(TblProd01.T_CUSTOMER == customer)

            results = query.order_by(TblProd01.T_PRODDATE.desc()).offset((page - 1) * page_size).limit(page_size).all()

            return [{"prod_id": r.T_PRODID, "lot_num": r.T_LOTNUM, "product_code": r.T_PRODCODE,
                     "batch_weight": r.T_QTYREQ, "customer": r.T_CUSTOMER, "formula_id": r.T_FID,
                     "order_no": r.T_ORDERNUM} for r in results]

    def get_materials_for_prod_ids(self, prod_ids: List[Decimal]) -> List[Dict[str, Any]]:
        # This method remains correct and unchanged
        if not prod_ids: return []
        with self.Session() as session:
            records = session.query(TblProd02.T_MATCODE, TblProd02.T_WT).filter(
                TblProd02.T_PRODID.in_(prod_ids), TblProd02.T_DELETED.is_(False), TblProd02.T_WT != 0
            ).order_by(TblProd02.T_SEQ).all()
            return [{"mat_code": r.T_MATCODE, "qty": r.T_WT} for r in records]

    def get_details_for_lot(self, lot_number: str) -> Dict | None:
        # This method remains correct and unchanged
        if not lot_number: return None
        with self.Session() as session:
            result = session.query(
                TblProd01.T_PRODCODE, TblProd01.T_CUSTOMER, TblProd01.T_ORDERNUM, TblProd01.T_QTYREQ
            ).filter(
                TblProd01.T_LOTNUM == lot_number, TblProd01.T_DELETED.is_(False)
            ).first()
            if result:
                return {"product_code": result.T_PRODCODE, "customer": result.T_CUSTOMER,
                        "order_no": result.T_ORDERNUM, "qty_order": result.T_QTYREQ}
            return None

    # --- THE FIX IS HERE: The missing method is now restored. ---
    def get_total_batch_weight_for_lots(self, lot_numbers: List[str]) -> Decimal:
        """
        Calculates the sum of the batch weights (T_QTYREQ) for a given list of lot numbers.
        """
        if not lot_numbers:
            return Decimal("0.00")
        with self.Session() as session:
            # Use func.sum to aggregate in the database, which is more efficient
            total_weight = session.query(func.sum(TblProd01.T_QTYREQ)).filter(
                TblProd01.T_LOTNUM.in_(lot_numbers),
                or_(TblProd01.T_DELETED.is_(False), TblProd01.T_DELETED.is_(None))
            ).scalar()
            # The result can be None if no records are found, so handle that case
            return total_weight or Decimal("0.00")


    # --- CORRECTED Save Method ---

    def save_full_form(self, form_data: Dict[str, Any], zone_mapping: Dict[str, int]):
        """
        Saves all data from the main form and its related child objects.
        """
        with self.Session() as session:
            with session.begin():
                main_info = form_data.get("main", {})
                new_form_entry = ExtruderFormData(
                    lot_number=main_info.get('lot_number'),
                    production_id=str(main_info.get('prod_id')),
                    product_code=main_info.get('product_code'),
                    customer=main_info.get('customer'),
                    qty_order=Decimal(main_info.get('qty_order', '0')),
                    prepared_by=main_info.get('prepared_by_name'),
                    machine_id=main_info.get('machine_id'),
                    total_input=form_data.get("summary", {}).get("resin_qty_total")
                )

                mc_info = form_data.get("machine_config", {})
                new_mc_config = MachineConfig(
                    feed_rate=mc_info.get('feed_rate'),
                    rpm=mc_info.get('rpm'),
                    screen_size_id=mc_info.get('screen_size_id'),
                    screw_config=mc_info.get('screw_config')
                )
                new_form_entry.machine_configs.append(new_mc_config)

                purging_info = form_data.get("purging", {})
                # Only create a purging header if a valid resin was selected
                if purging_info and purging_info.get('resin_id') is not None:
                    new_purging_header = PurgingHeader(
                        product_code=purging_info.get('product_code_name'),
                        time_start=purging_info.get('start_time'),
                        time_end=purging_info.get('end_time'),
                        resin_used_id=purging_info.get('resin_id'),
                        palletizer_used=Decimal(purging_info.get('palletizer', '0')),
                        siever_used=Decimal(purging_info.get('siever', '0'))
                    )
                    new_form_entry.purging_headers.append(new_purging_header)

                for resin_data in form_data.get("resin_consumption", []):
                    new_resin = UsedMaterial(
                        material=resin_data.get('resin_name'),
                        qty=Decimal(resin_data.get('qty', '0'))
                    )
                    new_form_entry.used_materials.append(new_resin)

                for output_data in form_data.get("output_log", []):
                    new_output = ExtruderOutput(
                        date=output_data.get('date'),
                        time_start=output_data.get('time_start'),
                        time_end=output_data.get('time_end'),
                        qty_output=Decimal(output_data.get('output', '0')),
                        qty_loss=Decimal(output_data.get('loss', '0'))
                    )
                    new_form_entry.extruder_outputs.append(new_output)

                zone_temps = form_data.get("zone_temps", {})
                for zone_name, temp_value in zone_temps.items():
                    zone_id = zone_mapping.get(zone_name)
                    if zone_id:
                        new_temp = MachineTemp(
                            zone_id=zone_id,
                            temp_value=Decimal(temp_value or '0')
                        )
                        new_form_entry.machine_temps.append(new_temp)

                for person_data in form_data.get("personnel", []):
                    if person_data.get('employee_id') and person_data.get('position_id'):
                        new_personnel = ExtruderPersonnel(
                            employee_id=person_data.get('employee_id'),
                            position_id=person_data.get('position_id')
                        )
                        new_form_entry.extruder_personnels.append(new_personnel)

                # Add the fully constructed object to the session
                session.add(new_form_entry)

            print("--- SIMULATING SAVE ---")
            import json
            # Using a custom default function to handle non-serializable types like Decimal
            def custom_serializer(obj):
                if isinstance(obj, Decimal):
                    return str(obj)
                if hasattr(obj, '__str__'):
                    return str(obj)
                raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")

            print(json.dumps(form_data, indent=2, default=custom_serializer))
            print("--- SAVE COMPLETE (SIMULATED) ---")