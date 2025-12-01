from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, cast, String, distinct
from models.ExtruderOld import ExtruderOldAmielData
import logging


class ExtruderOldProgramRecordsOps:

    @staticmethod
    def fetch_records(session: Session, limit=100, offset=0):
        try:
            records = (
                session.query(ExtruderOldAmielData)
                .order_by(desc(ExtruderOldAmielData.process_id))
                .limit(limit)
                .offset(offset)
                .all()
            )
            return records
        except Exception as e:
            logging.error(f"Error fetching Program records: {e}")
            return []

    @staticmethod
    def search_records(session: Session, search_text: str, limit=100, offset=0):
        try:
            term = f"%{search_text}%"
            records = (
                session.query(ExtruderOldAmielData)
                .filter(
                    or_(
                        ExtruderOldAmielData.product_code.ilike(term),
                        ExtruderOldAmielData.customer.ilike(term),
                        ExtruderOldAmielData.machine.ilike(term),
                        ExtruderOldAmielData.remarks.ilike(term),
                        # Cast Array to string for simple text searching
                        cast(ExtruderOldAmielData.lot_number, String).ilike(term)
                    )
                )
                .order_by(desc(ExtruderOldAmielData.process_id))
                .limit(limit)
                .offset(offset)
                .all()
            )
            return records
        except Exception as e:
            logging.error(f"Error searching Program records: {e}")
            return []

    @staticmethod
    def get_distinct_values(session: Session, column, filter_text: str = "", limit=20, offset=0):
        """
        Generic method for Lazy ComboBoxes.
        """
        try:
            query = session.query(column).distinct()
            query = query.filter(column != None)

            if filter_text:
                query = query.filter(cast(column, String).ilike(f"%{filter_text}%"))

            results = (
                query.order_by(column)
                .limit(limit)
                .offset(offset)
                .all()
            )
            return [str(r[0]) for r in results if r[0] is not None]
        except Exception as e:
            logging.error(f"Error fetching distinct values for {column}: {e}")
            return []

    @staticmethod
    def fetch_filtered_records(session: Session, filters: dict, search_text: str = "", limit=100, offset=0):
        """
        Master Query Method.
        Applies Advanced Filters (AND) + Quick Search (OR) simultaneously.
        """
        try:
            query = session.query(ExtruderOldAmielData)

            # --- 1. Apply Advanced Filters (AND Logic) ---
            # If a user selects "Customer A", we strictly limit to Customer A
            if filters:
                def apply_col_filter(col_model, key):
                    nonlocal query
                    val = filters.get(key)
                    if not val: return
                    if val == "<blank>":
                        query = query.filter(or_(col_model == None, col_model == ""))
                    else:
                        query = query.filter(col_model.ilike(f"%{val}%"))

                apply_col_filter(ExtruderOldAmielData.product_code, 'code')
                apply_col_filter(ExtruderOldAmielData.customer, 'customer')
                apply_col_filter(ExtruderOldAmielData.machine, 'machine')
                apply_col_filter(ExtruderOldAmielData.screw_config, 'screw_config')
                apply_col_filter(ExtruderOldAmielData.resin, 'resin')
                apply_col_filter(ExtruderOldAmielData.operator, 'operator')
                apply_col_filter(ExtruderOldAmielData.supervisor, 'supervisor')
                apply_col_filter(ExtruderOldAmielData.remarks, 'remarks')

                if filters.get('lot'):
                    query = query.filter(cast(ExtruderOldAmielData.lot_number, String).ilike(f"%{filters['lot']}%"))
                if filters.get('date'):
                    query = query.filter(cast(ExtruderOldAmielData.encoded_on, String).ilike(f"%{filters['date']}%"))

            # --- 2. Apply Quick Search (OR Logic) ---
            # If user typed "text" in search bar, we look for "text" in key columns.
            # Crucially, this is chained AFTER the specific filters, so it acts as:
            # WHERE (Customer='A') AND (Code LIKE '%text%' OR Machine LIKE '%text%' ...)
            if search_text:
                term = f"%{search_text}%"
                query = query.filter(
                    or_(
                        ExtruderOldAmielData.product_code.ilike(term),
                        ExtruderOldAmielData.customer.ilike(term),
                        ExtruderOldAmielData.machine.ilike(term),
                        ExtruderOldAmielData.remarks.ilike(term),
                        cast(ExtruderOldAmielData.lot_number, String).ilike(term)
                    )
                )

            # --- 3. Final Ordering & Pagination ---
            records = query.order_by(desc(ExtruderOldAmielData.process_id)).limit(limit).offset(offset).all()
            return records

        except Exception as e:
            logging.error(f"Error filtering Program records: {e}")
            return []