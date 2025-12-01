# app/views/extruder_old_records/excel_records/ops.py
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_, distinct
from models import ExtruderOldExcelData
import logging


class ExtruderExcelRecordsOps:

    # ... (Keep fetch_records and search_records as they are) ...

    @staticmethod
    def fetch_records(session: Session, limit=100, offset=0):
        """Fetches a batch of records."""
        try:
            records = (
                session.query(ExtruderOldExcelData)
                .order_by(desc(ExtruderOldExcelData.id))
                .limit(limit)
                .offset(offset)
                .all()
            )
            return records
        except Exception as e:
            logging.error(f"Error fetching Excel records: {e}")
            return []

    @staticmethod
    def search_records(session: Session, search_text: str, limit=100, offset=0):
        """Performs a case-insensitive search with pagination."""
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
            logging.error(f"Error searching Excel records: {e}")
            return []

    @staticmethod
    def get_distinct_codes(session: Session, filter_text: str = "", limit=20, offset=0):
        """
        Fetches unique product codes for the lazy-loading combobox.
        """
        try:
            query = session.query(ExtruderOldExcelData.code).distinct()

            if filter_text:
                query = query.filter(ExtruderOldExcelData.code.ilike(f"%{filter_text}%"))

            # Order by code for consistent pagination
            results = (
                query.order_by(ExtruderOldExcelData.code)
                .limit(limit)
                .offset(offset)
                .all()
            )
            # Flatten list of tuples [('Code1',), ('Code2',)] -> ['Code1', 'Code2']
            return [r[0] for r in results if r[0]]
        except Exception as e:
            logging.error(f"Error fetching codes: {e}")
            return []

    @staticmethod
    def fetch_filtered_records(session: Session, filters: dict, limit=100, offset=0):
        """
        Expanded to include Screw, Resin, RPM, and Date.
        """
        try:
            query = session.query(ExtruderOldExcelData)

            if filters.get('code'):
                query = query.filter(ExtruderOldExcelData.code == filters['code'])  # Exact match for combobox

            if filters.get('customer'):
                query = query.filter(ExtruderOldExcelData.customer.ilike(f"%{filters['customer']}%"))

            if filters.get('machine'):
                try:
                    m_id = int(filters['machine'])
                    query = query.filter(ExtruderOldExcelData.machine_no == m_id)
                except ValueError:
                    pass

            if filters.get('lot'):
                query = query.filter(ExtruderOldExcelData.lot_number.ilike(f"%{filters['lot']}%"))

            if filters.get('remarks'):
                query = query.filter(ExtruderOldExcelData.remarks.ilike(f"%{filters['remarks']}%"))

            # --- NEW FIELDS ---
            if filters.get('screw_config'):
                query = query.filter(ExtruderOldExcelData.screw_config.ilike(f"%{filters['screw_config']}%"))

            if filters.get('resin_used'):
                query = query.filter(ExtruderOldExcelData.resin_used.ilike(f"%{filters['resin_used']}%"))

            if filters.get('rpm'):
                query = query.filter(ExtruderOldExcelData.rpm.ilike(f"%{filters['rpm']}%"))

            if filters.get('date'):
                # Date is a string in DB, doing text match
                query = query.filter(ExtruderOldExcelData.date.ilike(f"%{filters['date']}%"))

            records = query.order_by(desc(ExtruderOldExcelData.id)).limit(limit).offset(offset).all()
            return records

        except Exception as e:
            logging.error(f"Error filtering records: {e}")
            return []