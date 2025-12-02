# app/views/extruder_old_records/excel_records/ops.py
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_, distinct ,cast, String
from models import ExtruderOldExcelData
import logging


class ExtruderExcelRecordsOps:
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
    def get_distinct_values(session: Session, column, filter_text: str = "", limit=20, offset=0):
        """
        Generic method to fetch distinct values for a Combobox.
        Handles both String and Integer columns.
        """
        try:
            # Cast to string for consistent searching (needed for Machine No)
            query = session.query(column).distinct()

            # Filter out NULLs explicitly (handled by <blank> option)
            query = query.filter(column != None)

            if filter_text:
                # Ensure we search against a string representation
                query = query.filter(cast(column, String).ilike(f"%{filter_text}%"))

            results = (
                query.order_by(column)
                .limit(limit)
                .offset(offset)
                .all()
            )

            # Flatten results: [('A',), ('B',)] -> ['A', 'B']
            # Convert to string to ensure Combobox compatibility
            return [str(r[0]) for r in results if r[0] is not None]
        except Exception as e:
            logging.error(f"Error fetching distinct values for {column}: {e}")
            return []

    @staticmethod
    def fetch_filtered_records(session: Session, filters: dict, limit=100, offset=0):
        """
        Filters records based on dictionary.
        Handles '<blank>' logic and wildcard searching.
        """
        try:
            query = session.query(ExtruderOldExcelData)

            # Helper to apply standard filter logic
            def apply_filter(col_model, key, is_numeric=False):
                nonlocal query
                val = filters.get(key)
                if not val:
                    return

                if val == "<blank>":
                    # Handle Blank: NULL or Empty String
                    if is_numeric:
                        query = query.filter(col_model == None)
                    else:
                        query = query.filter(or_(col_model == None, col_model == ""))
                else:
                    # Handle Standard Search
                    if is_numeric:
                        try:
                            # For Machine No, if user typed manually vs selected
                            # But since it comes from Combobox as string, and we need exact or ILIKE
                            # The requirement says "like %...%" for screw, implying fuzzy for others too?
                            # Usually Machine No is exact, but let's stick to safe string casting if fuzzy needed
                            # Or strict equality for ints if not fuzzy.
                            # Let's use strict equality for Machine if it's a number, else ignore
                            i_val = int(val)
                            query = query.filter(col_model == i_val)
                        except:
                            pass
                    else:
                        # String Fuzzy Match (covers the Screw Config requirement)
                        # "use like %screw_config_value% ... spaces" -> ILIKE handles the case insensitive part
                        # Adding %..% handles the "contains" logic
                        query = query.filter(col_model.ilike(f"%{val.strip()}%"))

            # Apply Filters
            apply_filter(ExtruderOldExcelData.code, 'code')
            apply_filter(ExtruderOldExcelData.customer, 'customer')
            apply_filter(ExtruderOldExcelData.machine_no, 'machine', is_numeric=True)
            apply_filter(ExtruderOldExcelData.lot_number, 'lot')
            apply_filter(ExtruderOldExcelData.screw_config, 'screw_config')
            apply_filter(ExtruderOldExcelData.resin_used, 'resin_used')

            # Date and RPM (Left as Text inputs based on previous step, but can use apply_filter if they become combos)
            if filters.get('rpm'):
                query = query.filter(ExtruderOldExcelData.rpm.ilike(f"%{filters['rpm']}%"))
            if filters.get('date'):
                query = query.filter(ExtruderOldExcelData.date.ilike(f"%{filters['date']}%"))
            if filters.get('remarks'):
                query = query.filter(ExtruderOldExcelData.remarks.ilike(f"%{filters['remarks']}%"))

            records = query.order_by(desc(ExtruderOldExcelData.id)).limit(limit).offset(offset).all()
            return records

        except Exception as e:
            logging.error(f"Error filtering records: {e}")
            return []