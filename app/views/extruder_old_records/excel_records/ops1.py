# app/views/extruder_old_records/excel_records/ops.py
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_, asc
from models import ExtruderOldExcelData
import logging


class ExtruderExcelRecordsOps:
    """
    Handles business logic and database operations.
    """

    @staticmethod
    def fetch_records(session: Session, limit=100, offset=0):
        try:
            records = (
                session.query(ExtruderOldExcelData)
                .order_by(asc(ExtruderOldExcelData.id))
                .limit(limit)
                .offset(offset)
                .all()
            )
            return records
        except Exception as e:
            logging.error(f"Error fetching: {e}")
            return []

    @staticmethod
    def search_records(session: Session, search_text: str, limit=100, offset=0):
        try:
            term = f"%{search_text}%"
            records = (
                session.query(ExtruderOldExcelData)
                .filter(
                    or_(
                        ExtruderOldExcelData.code.ilike(term),
                        ExtruderOldExcelData.customer.ilike(term),
                        ExtruderOldExcelData.lot_number.ilike(term),
                        ExtruderOldExcelData.remarks.ilike(term),
                        ExtruderOldExcelData.resin_used.ilike(term)
                    )
                )
                .order_by(desc(ExtruderOldExcelData.id))
                .limit(limit)
                .offset(offset)
                .all()
            )
            return records
        except Exception as e:
            logging.error(f"Error searching: {e}")
            return []

    @staticmethod
    def fetch_filtered_records(session: Session, filters: dict, limit=100, offset=0):
        """
        Fetches records based on specific criteria (AND logic).
        """
        try:
            query = session.query(ExtruderOldExcelData)

            # Apply filters dynamically
            if 'code' in filters:
                query = query.filter(ExtruderOldExcelData.code.ilike(f"%{filters['code']}%"))

            if 'customer' in filters:
                query = query.filter(ExtruderOldExcelData.customer.ilike(f"%{filters['customer']}%"))

            if 'machine' in filters:
                # Machine is integer in DB, but text in input. Try exact match or cast.
                # If user types '1', we find 1.
                try:
                    m_id = int(filters['machine'])
                    query = query.filter(ExtruderOldExcelData.machine_no == m_id)
                except ValueError:
                    pass  # Invalid integer input for machine, ignore filter

            if 'lot' in filters:
                query = query.filter(ExtruderOldExcelData.lot_number.ilike(f"%{filters['lot']}%"))

            if 'remarks' in filters:
                query = query.filter(ExtruderOldExcelData.remarks.ilike(f"%{filters['remarks']}%"))

            # Order, Limit, Offset
            records = query.order_by(desc(ExtruderOldExcelData.id)).limit(limit).offset(offset).all()
            return records

        except Exception as e:
            logging.error(f"Error filtering records: {e}")
            return []