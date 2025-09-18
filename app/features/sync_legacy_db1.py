# app/features/sync_legacy_db.py

import os
from decimal import Decimal, InvalidOperation as DecimalInvalidOperation
from typing import Set, Tuple, Any

import dbfread
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QThread, Qt
from PyQt6.QtWidgets import QProgressDialog, QMessageBox
from sqlalchemy.orm import sessionmaker

# Import your SQLAlchemy models
from models import TblProd01, TblFormula01, TblFormula02


# --- DATABASE FILE PATHS ---
DBF_PATH = r'\\system-server\SYSTEM-NEW-OLD'
PRODUCTION_DBF_PATH = os.path.join(DBF_PATH, 'tbl_prod01.dbf')
FORMULA01_DBF_PATH = os.path.join(DBF_PATH, 'tbl_formula01.dbf')
FORMULA02_DBF_PATH = os.path.join(DBF_PATH, 'tbl_formula02.dbf')


# --- Helper Functions for Safe Data Conversion ---
# These functions will prevent crashes when encountering bad data in DBF files.

def safe_decimal(value: Any) -> Decimal | None:
    """Safely converts a value to a Decimal, returning None on failure."""
    if value is None:
        return None
    try:
        # dbfread can return float, int, or Decimal. Standardize to Decimal.
        return Decimal(value)
    except (ValueError, TypeError, DecimalInvalidOperation):
        # This catches errors like converting b'\x00\x00' or other non-numeric data.
        return None

def safe_int(value: Any) -> int | None:
    """Safely converts a value to an integer, returning None on failure."""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None

def safe_bool(value: Any) -> bool | None:
    """Safely converts a value to a boolean."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    # DBF logical fields are often 'T' or 'F'
    if isinstance(value, str):
        return value.strip().upper() in ('T', 'Y', 'TRUE')
    return bool(value)


class SyncController:
    # ... (This class remains unchanged from the previous version)
    """
    This class orchestrates the UI part of the sync process,
    managing the thread and progress dialog.
    """
    def __init__(self, engine, parent_widget):
        self.engine = engine
        self.parent = parent_widget
        self.sync_thread = None
        self.sync_worker = None

    def run_sync(self):
        """Initializes and runs the database sync worker in a separate thread."""
        self.progress_dialog = QProgressDialog(
            "Starting database synchronization...", "Cancel", 0, 100, self.parent
        )
        self.progress_dialog.setWindowTitle("Sync in Progress")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        # Create worker and thread
        self.sync_thread = QThread()
        self.sync_worker = SyncWorker(self.engine)
        self.sync_worker.moveToThread(self.sync_thread)

        # Connect signals
        self.sync_thread.started.connect(self.sync_worker.run)
        self.sync_worker.progress.connect(self.update_progress)
        self.sync_worker.finished.connect(self.on_sync_finished)
        self.sync_worker.error.connect(self.on_sync_error)

        # Cleanup connections
        self.sync_worker.finished.connect(self.sync_thread.quit)
        self.sync_worker.error.connect(self.sync_thread.quit)
        self.sync_worker.finished.connect(self.sync_worker.deleteLater)
        self.sync_thread.finished.connect(self.sync_thread.deleteLater)
        self.progress_dialog.canceled.connect(self.sync_thread.quit)

        self.sync_thread.start()

    def update_progress(self, message, value):
        self.progress_dialog.setLabelText(message)
        self.progress_dialog.setValue(value)

    def on_sync_finished(self, result_message):
        """Handles the successful completion of the sync process."""
        self.progress_dialog.close()
        QMessageBox.information(self.parent, "Sync Complete", result_message)

    def on_sync_error(self, error_message):
        self.progress_dialog.close()
        QMessageBox.critical(self.parent, "Sync Failed", error_message)


# app/features/sync_legacy_db.py

# ... (keep all imports and helper functions)
# ... (SyncController class remains the same)

class SyncWorker(QObject):
    """Worker object that runs the actual DBF-to-PostgreSQL sync process."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str, int)

    def __init__(self, engine, parent=None):
        super().__init__(parent)
        self.engine = engine

    @pyqtSlot()
    def run(self):
        """Main method that executes the full sync process."""
        session = None
        try:
            Session = sessionmaker(bind=self.engine)
            session = Session()

            # --- THIS IS THE NEW, CORRECT LOGIC ---
            self.progress.emit("Reading legacy formulas...", 10)
            
            # 1. Fetch existing legacy IDs to avoid duplicates.
            existing_header_uids: Set[int] = {row.T_UID for row in session.query(TblFormula01.T_UID).all()}
            existing_detail_keys: Set[Tuple[int, int]] = {
                (row.T_UID, row.T_SEQ) for row in session.query(TblFormula02.T_UID, TblFormula02.T_SEQ).all()
            }

            # 2. Create a dictionary to hold new parent objects in memory.
            #    This maps the old legacy T_UID to the new SQLAlchemy object.
            new_headers_map = {}

            # 3. Process Formula Headers (tbl_formula01)
            self.progress.emit("Processing formula headers...", 20)
            dbf_headers = dbfread.DBF(FORMULA01_DBF_PATH, encoding='latin1')._iter_records()
            for record in dbf_headers:
                t_uid = safe_int(record.get('T_UID'))
                if not t_uid or t_uid in existing_header_uids:
                    continue

                new_header = TblFormula01(
                    T_UID=t_uid, T_INDEX=record.get('T_INDEX'), T_DATE=record.get('T_DATE'),
                    # ... map all other formula01 fields ...
                    T_CUSTOMER=record.get('T_CUSTOMER'), T_PRODCODE=record.get('T_PRODCODE'),
                    T_PRODCOLO=record.get('T_PRODCOLO'), T_DOSAGE=safe_decimal(record.get('T_DOSAGE')),
                    T_LD=safe_decimal(record.get('T_LD')), T_TOTALCON=safe_decimal(record.get('T_TOTALCON')),
                    T_MIX=record.get('T_MIX'), T_RESIN=record.get('T_RESIN'), T_APP=record.get('T_APP'),
                    T_CMNUM=record.get('T_CMNUM'), T_CMDATE=record.get('T_CMDATE'), T_MATCHBY=record.get('T_MATCHBY'),
                    T_ENCODEDB=record.get('T_ENCODEDB'), T_REM=record.get('T_REM'), T_USER=record.get('T_USER'),
                    T_DELETED=safe_bool(record.get('T_DELETED')), T_USED=safe_bool(record.get('T_USED')),
                    T_UPDATEBY=record.get('T_UPDATEBY'), T_UDATE=record.get('T_UDATE')
                )
                session.add(new_header) # Add to the session immediately
                new_headers_map[t_uid] = new_header # Store in our map

            # 4. Process Formula Details (tbl_formula02) and link them to headers
            self.progress.emit("Processing formula details...", 40)
            dbf_details = dbfread.DBF(FORMULA02_DBF_PATH, encoding='latin1')._iter_records()
            for record in dbf_details:
                t_uid, t_seq = safe_int(record.get('T_UID')), safe_int(record.get('T_SEQ'))
                if not t_uid or not t_seq or (t_uid, t_seq) in existing_detail_keys:
                    continue
                
                # Find the parent object from our map
                parent_header = new_headers_map.get(t_uid)
                if parent_header:
                    new_detail = TblFormula02(
                        T_UID=t_uid, T_SEQ=t_seq,
                        T_MATCODE=record.get('T_MATCODE'), T_CON=safe_decimal(record.get('T_CON')),
                        T_DELETED=safe_bool(record.get('T_DELETED')),
                        T_UPDATEBY=record.get('T_UPDATEBY'), T_UDATE=record.get('T_UDATE')
                    )
                    # THIS IS THE KEY: Append the child to the parent's relationship list.
                    # SQLAlchemy will handle setting the foreign key.
                    parent_header.details.append(new_detail)

            # 5. Process Production Records (tbl_prod01) - This can still be separate
            self.progress.emit("Processing production records...", 70)
            p1_new = self._sync_prod01(session) # Re-use the existing separate method for this

            # 6. Commit everything at once
            self.progress.emit("Committing changes to database...", 95)
            session.commit()

            result_message = (
                "Database Synchronization Successful!\n\n"
                f"New Formula Headers: {len(new_headers_map)}\n"
                # Note: We don't have a simple count for details anymore, but this is fine.
                f"New Production Records: {p1_new}"
            )
            self.finished.emit(result_message)

        except Exception as e:
            if session:
                session.rollback()
            import traceback
            error_details = traceback.format_exc()
            print(f"Sync Error: {error_details}")
            self.error.emit(f"An error occurred during synchronization:\n\n{e}")
        finally:
            if session:
                session.close()
    
    # This method is now only used for tbl_prod01, which has no dependencies
    def _sync_prod01(self, session) -> int:
        """Syncs tbl_prod01, safely handling data conversion errors."""
        existing_prodids: Set[Decimal] = {row.T_PRODID for row in session.query(TblProd01.T_PRODID).all()}
        records_to_add = []
        try:
            dbf_records = dbfread.DBF(PRODUCTION_DBF_PATH, encoding='latin1')._iter_records()
        except dbfread.exceptions.DBFNotFound:
            raise FileNotFoundError(f"File not found: {PRODUCTION_DBF_PATH}")

        for record in dbf_records:
            t_prodid = safe_decimal(record.get('T_PRODID'))
            if not t_prodid or t_prodid in existing_prodids:
                continue
            
            try:
                new_prod = TblProd01(
                    T_PRODID=t_prodid, T_PRODDATE=record.get('T_PRODDATE'), T_CUSTOMER=record.get('T_CUSTOMER'),
                    T_FID=safe_int(record.get('T_FID')), T_INDEX=record.get('T_INDEX'), T_PRODCODE=record.get('T_PRODCODE'),
                    T_PRODCOLO=record.get('T_PRODCOLO'), T_DOSAGE=safe_decimal(record.get('T_DOSAGE')),
                    T_LD=safe_decimal(record.get('T_LD')), T_QTYREQ=safe_decimal(record.get('T_QTYREQ')),
                    T_QTYBATCH=safe_decimal(record.get('T_QTYBATCH')), T_QTYPROD=safe_decimal(record.get('T_QTYPROD')),
                    T_LOTNUM=record.get('T_LOTNUM'), T_ORDERNUM=record.get('T_ORDERNUM'), T_CMNUM=record.get('T_CMNUM'),
                    T_CMDATE=record.get('T_CMDATE'), T_MIXTIME=record.get('T_MIXTIME'), T_MACHINE=record.get('T_MACHINE'),
                    T_REMARKS=record.get('T_REMARKS'), T_NOTE=record.get('T_NOTE'), T_USERID=record.get('T_USERID'),
                    T_PREPARED=record.get('T_PREPARED'), T_ENCODEDB=record.get('T_ENCODEDB'),
                    T_ENCODEDO=record.get('T_ENCODEDO'), T_DELETED=safe_bool(record.get('T_DELETED')),
                    T_JDONE=record.get('T_JDONE'), T_CDATE=record.get('T_CDATE'), T_SDATE=record.get('T_SDATE'),
                    T_FTYPE=record.get('T_FTYPE')
                )
                records_to_add.append(new_prod)
            except Exception as e:
                print(f"Skipping corrupt record in tbl_prod01 for T_PRODID={t_prodid}. Error: {e}")
                continue

        if records_to_add:
            # You can add directly to the session here
            session.add_all(records_to_add)
        return len(records_to_add)