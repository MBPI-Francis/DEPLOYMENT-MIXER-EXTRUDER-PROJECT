from sqlalchemy.orm import sessionmaker, Session, aliased, joinedload, selectinload
from sqlalchemy import func, case, text
from sqlalchemy.sql.expression import literal_column
from typing import Type
import decimal

# Import all necessary models
from models.ExtruderCore import (
    ExtruderFormData, ExtruderOutput, PurgingHeader, ExtruderPersonnel, MachineDetail, MachineTemp, PurgingDetail
)
from models.ExtruderConfig import ExtruderMachine
from models.ProductionEmployees import ProductionEmployee


class ExtruderRecordsOperations:
    def __init__(self, session_factory: Type[Session]):
        self.Session = session_factory

    def get_records_with_details(self, search_term=None, filter_date=None, show_deleted=False):
        """
        Fetches ExtruderFormData records with calculated and aggregated columns.
        Uses PostgreSQL-compatible `string_agg` function.
        """
        session = self.Session()
        try:
            # 1. Subquery for Extruder Output calculations
            output_sq = session.query(
                ExtruderOutput.extruder_form_data_id,
                func.min(ExtruderOutput.datetime_start).label('datetime_start'),
                func.max(ExtruderOutput.datetime_end).label('datetime_end'),
                func.sum(ExtruderOutput.qty_output).label('total_output_qty')
            ).group_by(ExtruderOutput.extruder_form_data_id).subquery('output_sq')

            # 2. Subquery for Purging calculations (using STRING_AGG)
            purging_sq = session.query(
                PurgingHeader.extruder_form_data_id,
                func.string_agg(PurgingHeader.product_code, text("', '")).label('purging_to_code'),
                func.sum(PurgingHeader.time_end - PurgingHeader.time_start).label('total_purging_time')
            ).group_by(PurgingHeader.extruder_form_data_id).subquery('purging_sq')

            # 3. Subquery for Personnel aggregation (using STRING_AGG)
            personnel_sq = session.query(
                ExtruderPersonnel.extruder_form_data_id,
                func.string_agg(ProductionEmployee.first_name + ' ' + ProductionEmployee.last_name, text("', '")).label(
                    'operators')
            ).join(ProductionEmployee, ExtruderPersonnel.employee_id == ProductionEmployee.id) \
                .group_by(ExtruderPersonnel.extruder_form_data_id).subquery('personnel_sq')

            # --- Main Query ---
            query = session.query(
                ExtruderFormData,
                ExtruderMachine.name.label('machine_name'),
                output_sq.c.datetime_start,
                output_sq.c.datetime_end,
                output_sq.c.total_output_qty,
                purging_sq.c.purging_to_code,
                purging_sq.c.total_purging_time,
                personnel_sq.c.operators
            )

            # --- Joins ---
            query = query.outerjoin(ExtruderMachine, ExtruderFormData.machine_id == ExtruderMachine.id)\
                         .outerjoin(output_sq, ExtruderFormData.id == output_sq.c.extruder_form_data_id)\
                         .outerjoin(purging_sq, ExtruderFormData.id == purging_sq.c.extruder_form_data_id)\
                         .outerjoin(personnel_sq, ExtruderFormData.id == personnel_sq.c.extruder_form_data_id)

            # --- Filtering ---
            if not show_deleted:
                query = query.filter(ExtruderFormData.is_deleted == False)

            if search_term:
                search_ilike = f"%{search_term}%"
                query = query.filter(
                    (ExtruderFormData.lot_number.ilike(search_ilike)) |
                    (ExtruderFormData.product_code.ilike(search_ilike))
                )

            if filter_date:
                query = query.filter(func.date(ExtruderFormData.created_at) == filter_date)

            query = query.order_by(ExtruderFormData.created_at.desc())

            results = query.all()
            return self._process_results(results)

        finally:
            session.close()

    def _process_results(self, results):
        """Processes raw query results to calculate derived values and create dicts."""
        processed_data = []
        for row in results:
            form_data, machine_name, dt_start, dt_end, total_qty, purging_code, purging_time, operators = row

            total_hours = 0
            if dt_start and dt_end and dt_end > dt_start:
                total_duration = dt_end - dt_start
                total_hours = total_duration.total_seconds() / 3600.0

            output_per_hour = decimal.Decimal(0)
            if total_qty and total_hours > 0:
                output_per_hour = decimal.Decimal(total_qty) / decimal.Decimal(total_hours)

            processed_data.append({
                "form_data": form_data,
                "machine_name": machine_name,
                "datetime_start": dt_start,
                "datetime_end": dt_end,
                "total_output_qty": total_qty or decimal.Decimal(0),
                "output_per_hour": output_per_hour,
                "purging_to_code": purging_code,
                "total_purging_time": purging_time,
                "operators": operators
            })
        return processed_data

    def get_full_record_by_id(self, record_id: int):
        """
        Fetches a single, complete ExtruderFormData record with ALL of its related
        children and grandchildren, using efficient eager loading strategies.
        This is used to populate the complex entry form for editing.
        """
        session = self.Session()
        try:
            query = session.query(ExtruderFormData).filter(ExtruderFormData.id == record_id)

            # Chain multiple options to load the entire object graph
            query = query.options(
                # Load the one-to-one MachineDetail and its own relationships (many-to-one)
                joinedload(ExtruderFormData.machine_details).joinedload(MachineDetail.screen_size),
                joinedload(ExtruderFormData.machine_details).joinedload(MachineDetail.screw_config),

                # Use selectinload for one-to-many relationships to prevent row explosion
                # Then, chain joinedload to get the "grandchild" data for each child
                selectinload(ExtruderFormData.machine_temps).joinedload(MachineTemp.zone),

                selectinload(ExtruderFormData.extruder_outputs),

                selectinload(ExtruderFormData.extruder_personnels).joinedload(ExtruderPersonnel.employee),
                selectinload(ExtruderFormData.extruder_personnels).joinedload(ExtruderPersonnel.position),

                # Handle the nested relationships in Purging
                selectinload(ExtruderFormData.purging_headers).joinedload(PurgingHeader.resin_used),
                selectinload(ExtruderFormData.purging_headers)
                .selectinload(PurgingHeader.purging_details).joinedload(PurgingDetail.resin)
            )

            return query.first()
        finally:
            session.close()

    def soft_delete_record(self, record_id: int):
        """
        Soft deletes an ExtruderFormData record.
        """
        session = self.Session()
        try:
            record = session.query(ExtruderFormData).filter_by(id=record_id).first()
            if record:
                record.is_deleted = True
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"Error soft-deleting record: {e}")
            return False
        finally:
            session.close()

    def restore_record(self, record_id: int):
        """
        Restores a soft-deleted record.
        """
        session = self.Session()
        try:
            record = session.query(ExtruderFormData).filter_by(id=record_id).first()
            if record:
                record.is_deleted = False
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            print(f"Error restoring record: {e}")
            return False
        finally:
            session.close()