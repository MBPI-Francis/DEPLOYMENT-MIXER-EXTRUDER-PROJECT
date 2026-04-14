# app/views/extruder_form/entry_form/ops.py

from sqlalchemy.orm import sessionmaker
from sqlalchemy import func, or_, cast, String, distinct, not_
from typing import Type, List, Dict, Any
from decimal import Decimal

from models import (
    TblProd01, TblProd02, ExtruderMachine, ScreenSize, Resin, Zone,
    ProductionEmployee, EmployeePosition, ExtruderFormData, MachineDetail,
    ExtruderOutput, MachineTemp, ExtruderPersonnel,
    PurgingHeader, TblIncoming2, Shift
)
from models.ExtruderCore import ScrewConfig, PurgingDetail


class ExtruderOpsController:
    """
    Handles all business logic and database operations for the Extruder Entry Form.
    """

    def __init__(self, session_factory: Type[sessionmaker]):
        self.Session = session_factory

    def get_total_produced_weight_for_lots(self, lot_numbers: List[str]) -> Decimal:
        """
        Calculates the sum of the PRODUCED weights (T_QTYPROD) for a given list of lot numbers.
        """
        if not lot_numbers:
            return Decimal("0.00")
        with self.Session() as session:
            total_weight = session.query(func.sum(TblProd01.T_QTYPROD)).filter(
                TblProd01.T_LOTNUM.in_(lot_numbers),
                or_(TblProd01.T_DELETED.is_(False), TblProd01.T_DELETED.is_(None))
            ).scalar()
            return total_weight or Decimal("0.00")


    # --- NEW METHODS ---
    def get_all_shifts(self) -> List[Shift]:
        """Fetches all shifts for the ComboBox."""
        with self.Session() as session:
            return session.query(Shift).filter_by(is_deleted=False).order_by(Shift.name).all()

    def get_all_screw_configs(self) -> List[ScrewConfig]:
        """Fetches all screw configurations for the ComboBox."""
        with self.Session() as session:
            return session.query(ScrewConfig).filter_by(is_deleted=False).order_by(ScrewConfig.name).all()


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

        # --- NEW METHOD ---



    # def get_distinct_product_codes_paginated(self, page: int = 1, page_size: int = 50, search_term: str = None,
    #                                          limit: int = None) -> List[str]:
    #     """
    #     Fetches a unique, paginated, and searchable list of T_PRODCODE values.
    #     Can be limited for an initial fast load.
    #     """
    #     with self.Session() as session:
    #         query = session.query(distinct(TblProd01.T_PRODCODE)).filter(
    #             TblProd01.T_PRODCODE.isnot(None),
    #             TblProd01.T_PRODCODE != ''
    #         )
    #
    #         if search_term:
    #             query = query.filter(TblProd01.T_PRODCODE.ilike(f"%{search_term}%"))
    #
    #         # --- THIS IS THE FIX ---
    #         # 1. Apply the ORDER BY clause first. This is always needed.
    #         query = query.order_by(TblProd01.T_PRODCODE)
    #
    #         # 2. Now, conditionally apply either the limit or the pagination.
    #         if limit:
    #             query = query.limit(limit)
    #         else:
    #             query = query.offset((page - 1) * page_size).limit(page_size)
    #
    #         # 3. Execute the fully constructed query.
    #         results = query.all()
    #         # --- END FIX ---
    #
    #         return [code for (code,) in results]

    def get_distinct_product_codes_paginated(self, page: int = 1, page_size: int = 50, search_term: str = None,
                                             limit: int = None) -> List[str]:
        """
        Fetches a unique, paginated, and searchable list of T_PRODCODE values.
        It now ensures that "CMA" is always included in the results.
        """
        with self.Session() as session:
            query = session.query(distinct(TblProd01.T_PRODCODE)).filter(
                TblProd01.T_PRODCODE.isnot(None),
                TblProd01.T_PRODCODE != ''
            )

            if search_term:
                query = query.filter(TblProd01.T_PRODCODE.ilike(f"%{search_term}%"))

            query = query.order_by(TblProd01.T_PRODCODE)

            if limit:
                query = query.limit(limit)
            else:
                query = query.offset((page - 1) * page_size).limit(page_size)

            results = query.all()

            # Get the codes from the database
            db_codes = [code for (code,) in results]

            # --- THIS IS THE FIX ---
            # 1. Create a set for efficient uniqueness checks.
            final_codes_set = set(db_codes)

            # 2. Add "CMA". The set automatically handles duplicates if "CMA" was already in the list.
            final_codes_set.add("CMA")

            # 3. Convert back to a sorted list for consistent ordering in the UI.
            final_list = sorted(list(final_codes_set))

            return final_list
            # --- END FIX ---


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
        with self.Session() as session:
            query = session.query(
                TblProd01.T_PRODID,
                TblProd01.T_LOTNUM,
                TblProd01.T_PRODCODE,
                TblProd01.T_QTYREQ,
                TblProd01.T_CUSTOMER,
                TblProd01.T_FID,
                TblProd01.T_ORDERNUM,
                TblProd01.T_QTYPROD
            ).filter(
                func.trim(TblProd01.T_LOTNUM).isnot(None),
                func.trim(TblProd01.T_LOTNUM) != '',
                or_(TblProd01.T_DELETED.is_(False), TblProd01.T_DELETED.is_(None))
            )

            # --- NEW FEATURE: Filter to exclude DC Product Codes ---
            # Define the patterns for DC codes using regular expressions.
            # Pattern 1: Starts with two letters, then a hyphen (e.g., 'DP-V15273E')
            dc_compound_filter = TblProd01.T_PRODCODE.op("~")("^[A-Za-z]{2}-")
            # Pattern 2: Starts with numbers and ends with one letter (e.g., '7081X')
            dc_colorant_filter = TblProd01.T_PRODCODE.op("~")("^[0-9]+[A-Za-z]$")

            # Apply a filter to exclude records matching either of the DC patterns.
            query = query.filter(
                not_(
                    or_(
                        dc_compound_filter,
                        dc_colorant_filter
                    )
                )
            )
            # --- END NEW FEATURE ---

            if search_term:
                search_filter = or_(
                    TblProd01.T_LOTNUM.ilike(f"%{search_term}%"),
                    cast(TblProd01.T_PRODID, String).ilike(f"%{search_term}%")
                )
                query = query.filter(search_filter)
            if product_code: query = query.filter(TblProd01.T_PRODCODE == product_code)
            # if customer: query = query.filter(TblProd01.T_CUSTOMER == customer)
            # results = query.order_by(TblProd01.T_PRODDATE.desc()).offset((page - 1) * page_size).limit(page_size).all()
            results = query.filter(
                (TblProd01.T_DELETED.is_(False)) | (TblProd01.T_DELETED.is_(None))
            ).order_by(
                TblProd01.T_PRODDATE.desc()
            ).offset((page - 1) * page_size).limit(page_size).all()

            return [{
                "prod_id": r.T_PRODID,
                "lot_num": r.T_LOTNUM,
                "product_code": r.T_PRODCODE,
                "batch_weight": r.T_QTYREQ,
                "customer": r.T_CUSTOMER,
                "formula_id": r.T_FID,
                "order_no": r.T_ORDERNUM,
                "qty_produced": r.T_QTYPROD
            } for r in results]

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


    def get_all_encoders(self) -> List[ProductionEmployee]:
        """Fetches all production employees who are marked as encoders."""
        with self.Session() as session:
            return session.query(ProductionEmployee).filter(
                ProductionEmployee.is_encoder == True,
                ProductionEmployee.is_deleted == False
            ).order_by(ProductionEmployee.nickname).all()



    def save_full_form(self, form_data: Dict[str, Any], zone_mapping: Dict[str, int]):
        """
        Saves all data from the UI by building a nested structure of SQLAlchemy objects.
        """
        with self.Session() as session:
            with session.begin():  # Start a transaction
                main_info = form_data.get("main", {})

                # 1. Create the top-level ExtruderFormData object
                new_form_entry = ExtruderFormData(
                    lot_number=main_info.get('lot_number'),
                    production_id=main_info.get('production_id'),
                    formula_no=main_info.get('formula_no'),
                    order_no=main_info.get('order_no'),
                    ref_no=main_info.get('ref_no'),
                    product_code=main_info.get('product_code'),
                    customer=main_info.get('customer'),
                    qty_order=Decimal(main_info.get('qty_order', '0')),
                    qty_produced=Decimal(main_info.get('qty_produced', '0')),
                    target_output_per_hour=Decimal(main_info.get('target_output_per_hour', '0')),
                    prepared_by=main_info.get('prepared_by_name'),
                    machine_id=main_info.get('machine_id'),
                    shift_id=main_info.get('shift_id'),
                    remarks=form_data.get('remarks')
                )

                # 2. Create the child MachineDetail object and attach it
                mc_info = form_data.get("machine_details", {})
                new_machine_details = MachineDetail(
                    feed_rate=mc_info.get('feed_rate'),
                    rpm=mc_info.get('rpm'),
                    screen_size_id=mc_info.get('screen_size_id'),
                    screw_config_id=mc_info.get('screw_config_id'),
                    is_vacuum_on=mc_info.get('is_vacuum_on', False)
                )
                new_form_entry.machine_details = new_machine_details

                # 3. Create the child ExtruderPersonnel objects and attach them
                for person_data in form_data.get("personnel", []):
                    if person_data.get('employee_id') and person_data.get('position_id'):
                        new_personnel = ExtruderPersonnel(
                            employee_id=person_data.get('employee_id'),
                            position_id=person_data.get('position_id')
                        )
                        new_form_entry.extruder_personnels.append(new_personnel)

                # 4. Create the child ExtruderOutput objects
                for output_data in form_data.get("output_log", []):
                    # --- FIX: Save to the new datetime columns ---
                    new_output = ExtruderOutput(
                        datetime_start=output_data.get('datetime_start'),
                        datetime_end=output_data.get('datetime_end'),
                        qty_output=Decimal(output_data.get('output', '0'))
                    )
                    new_form_entry.extruder_outputs.append(new_output)

                # 5. Create the child MachineTemp objects
                zone_temps = form_data.get("zone_temps", {})
                for zone_name, temp_value in zone_temps.items():
                    zone_id = zone_mapping.get(zone_name)
                    if zone_id and (temp_value or '0').isdigit():
                        new_temp = MachineTemp(
                            zone_id=zone_id,
                            temp_value=Decimal(temp_value or '0')
                        )
                        new_form_entry.machine_temps.append(new_temp)

                # 6. Create the PurgingHeader and its child PurgingDetail objects
                header_info = form_data.get("purging_header")
                details_list = form_data.get("purging_details", [])
                if header_info and header_info.get('resin_id') is not None:
                    new_purging_header = PurgingHeader(
                        product_code=header_info.get('product_code_name'),
                        time_start=header_info.get('start_time'),
                        time_end=header_info.get('end_time'),
                        resin_used_id=header_info.get('resin_id'),
                        palletizer_used=Decimal(header_info.get('palletizer', '0')),
                        siever_used=Decimal(header_info.get('siever', '0')),
                        water_temp=Decimal(header_info.get('water_temp', '0'))
                    )
                    for detail_data in details_list:
                        if detail_data.get('resin_id'):
                            new_purging_detail = PurgingDetail(
                                resin_id=detail_data.get('resin_id'),
                                notes=detail_data.get('notes'),
                                qty=Decimal(detail_data.get('qty', '0'))
                            )
                            new_purging_header.purging_details.append(new_purging_detail)
                    new_form_entry.purging_headers.append(new_purging_header)

                # 7. Add the single, top-level object to the session.
                #    SQLAlchemy will automatically save all the attached child objects.
                session.add(new_form_entry)

            # --- SIMULATION IS REMOVED, THIS IS NOW A REAL SAVE ---
            # You can add a logging statement here if desired
            print("--- Database Save Successful ---")

    def update_full_form(self, record_id: int, form_data: Dict[str, Any], zone_mapping: Dict[str, int]):
        """
        --- THIS METHOD IS NOW CORRECTED ---
        Updates an existing record, ensuring all string numbers are converted to Decimal.
        """
        with self.Session() as session:
            with session.begin():
                record_to_update = session.query(ExtruderFormData).filter_by(id=record_id).with_for_update().one()
                main_info = form_data.get("main", {})
                record_to_update.lot_number = main_info.get('lot_number')
                record_to_update.production_id = main_info.get('production_id')
                record_to_update.formula_no = main_info.get('formula_no')
                record_to_update.order_no = main_info.get('order_no')
                record_to_update.product_code = main_info.get('product_code')
                record_to_update.customer = main_info.get('customer')
                record_to_update.qty_order = Decimal(main_info.get('qty_order', '0'))
                record_to_update.qty_produced = Decimal(main_info.get('qty_produced', '0'))
                record_to_update.target_output_per_hour = Decimal(main_info.get('target_output_per_hour', '0'))
                record_to_update.prepared_by = main_info.get('prepared_by_name')
                record_to_update.machine_id = main_info.get('machine_id')
                record_to_update.shift_id = main_info.get('shift_id')
                record_to_update.remarks = form_data.get('remarks')
                record_to_update.ref_no = main_info.get('ref_no')

                mc_info = form_data.get("machine_details", {})
                if record_to_update.machine_details:
                    record_to_update.machine_details.feed_rate = mc_info.get('feed_rate')
                    record_to_update.machine_details.rpm = mc_info.get('rpm')
                    record_to_update.machine_details.screen_size_id = mc_info.get('screen_size_id')
                    record_to_update.machine_details.screw_config_id = mc_info.get('screw_config_id')
                    record_to_update.machine_details.is_vacuum_on = mc_info.get('is_vacuum_on', False)



                # 1. Get data from the form and map existing DB objects by their ID
                form_personnel_data = form_data.get("personnel", [])
                existing_personnel_map = {p.id: p for p in record_to_update.extruder_personnels}


                form_ids = set()

                # 2. Loop through UI data to UPDATE existing and CREATE new records
                for person_data in form_personnel_data:
                    person_id = person_data.get("id")

                    if person_id in existing_personnel_map:
                        # This is an existing record, so UPDATE it
                        person_to_update = existing_personnel_map[person_id]
                        person_to_update.employee_id = person_data["employee_id"]
                        person_to_update.position_id = person_data["position_id"]
                        form_ids.add(person_id)
                    else:
                        if person_data.get('employee_id') and person_data.get('position_id'):
                            new_personnel = ExtruderPersonnel(
                                employee_id=person_data["employee_id"],
                                position_id=person_data["position_id"]
                            )
                            # Add to the parent's collection AND explicitly to the session
                            record_to_update.extruder_personnels.append(new_personnel)
                            session.add(new_personnel)

                # 3. Determine which records to DELETE
                ids_to_delete = set(existing_personnel_map.keys()) - form_ids
                if ids_to_delete:
                    # Create a list of objects to remove from the collection.
                    # SQLAlchemy's delete-orphan cascade will handle the database DELETE.
                    personnel_to_remove = [p for p in record_to_update.extruder_personnels if p.id in ids_to_delete]
                    for p in personnel_to_remove:
                        record_to_update.extruder_personnels.remove(p)

                # --- END OF PERSONNEL FIX ---

                record_to_update.machine_temps.clear()
                record_to_update.extruder_outputs.clear()
                # record_to_update.extruder_personnels.clear()
                record_to_update.purging_headers.clear()



                for output_data in form_data.get("output_log", []):
                    record_to_update.extruder_outputs.append(ExtruderOutput(
                        datetime_start=output_data.get('datetime_start'), datetime_end=output_data.get('datetime_end'),
                        qty_output=Decimal(output_data.get('output', '0'))
                    ))

                zone_temps = form_data.get("zone_temps", {})
                for zone_name, temp_value in zone_temps.items():
                    if zone_id := zone_mapping.get(zone_name):
                        record_to_update.machine_temps.append(MachineTemp(
                            zone_id=zone_id, temp_value=Decimal(temp_value or '0')
                        ))

                if header_info := form_data.get("purging_header"):
                    new_header = PurgingHeader(
                        product_code=header_info.get('product_code_name'), time_start=header_info.get('start_time'),
                        time_end=header_info.get('end_time'), resin_used_id=header_info.get('resin_id'),
                        palletizer_used=Decimal(header_info.get('palletizer', '0')),
                        siever_used=Decimal(header_info.get('siever', '0')),
                        water_temp=Decimal(header_info.get('water_temp', '0'))
                    )
                    for detail_data in form_data.get("purging_details", []):
                        if detail_data.get('resin_id'):
                            new_header.purging_details.append(PurgingDetail(
                                resin_id=detail_data.get('resin_id'), notes=detail_data.get('notes'),
                                qty=Decimal(detail_data.get('qty', '0'))
                            ))
                    record_to_update.purging_headers.append(new_header)




    # --- NEW METHODS FOR REFERENCE NUMBER ---
    def get_latest_reference_number(self) -> int:
        """Finds the highest existing ref_no in the database."""
        with self.Session() as session:
            # func.max() efficiently finds the maximum value in a column
            max_ref = session.query(func.max(ExtruderFormData.ref_no)).scalar()
            return max_ref or 0 # Return 0 if the table is empty



    # def check_if_ref_no_exists(self, ref_no: int, exclude_id: int = None) -> bool:
    #     """
    #     Checks if a reference number already exists in the database.
    #
    #     Args:
    #         ref_no: The reference number to check for.
    #         exclude_id: An optional record ID to exclude from the search. This is
    #                     used during an update to prevent a record from finding itself.
    #     Returns:
    #         True if the ref_no exists on another record, False otherwise.
    #     """
    #     with self.Session() as session:
    #         query = session.query(ExtruderFormData).filter(ExtruderFormData.ref_no == ref_no)
    #
    #         # --- THIS IS THE FIX ---
    #         # If an ID to exclude is provided, add another filter condition.
    #         if exclude_id is not None:
    #             query = query.filter(ExtruderFormData.id != exclude_id)
    #         # --- END FIX ---
    #
    #         # Use exists() for an efficient check without retrieving the full object
    #         return session.query(query.exists()).scalar()

    def check_if_ref_no_exists(self, ref_no: int, exclude_id: int = None) -> bool:
        """
        Checks if a reference number already exists as an ACTIVE record in the database.
        Soft-deleted records (is_deleted = True) are ignored, allowing their ref_no to be reused.

        Args:
            ref_no: The reference number to check for.
            exclude_id: An optional record ID to exclude from the search. This is
                        used during an update to prevent a record from finding itself.
        Returns:
            True if the ref_no exists on another ACTIVE record, False otherwise.
        """
        with self.Session() as session:
            # --- THIS IS THE FIX ---
            # We filter by ref_no AND ensure the record is NOT deleted.
            # Assuming your AuditMixin uses 'is_deleted' as the column name.
            query = session.query(ExtruderFormData).filter(
                ExtruderFormData.ref_no == ref_no,
                (ExtruderFormData.is_deleted.is_(False)) | (ExtruderFormData.is_deleted.is_(None))
            )
            # --- END FIX ---

            # If an ID to exclude is provided, add another filter condition.
            if exclude_id is not None:
                query = query.filter(ExtruderFormData.id != exclude_id)

            # Use exists() for an efficient check without retrieving the full object
            return session.query(query.exists()).scalar()
