import os
from decimal import Decimal, InvalidOperation as DecimalInvalidOperation
from typing import Set, Tuple, Any

import dbfread
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QThread, Qt
from PyQt6.QtWidgets import QProgressDialog, QMessageBox
from dbfread import FieldParser
# --- NEW IMPORTS ---
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

# Import your SQLAlchemy models
# Assuming your new RawMaterials model is in a file with your other models
from models import TblProd01, TblFormula01, TblFormula02, RawMaterials, Customer, TblProd02, TblIncoming2
from os import getenv
# --- END NEW IMPORTS ---


# --- DATABASE FILE PATHS (Unchanged) ---
DBF_PATH = r'\\system-server\SYSTEM-NEW-OLD'
PRODUCTION01_DBF_PATH = os.path.join(DBF_PATH, 'tbl_prod01.dbf')
PRODUCTION02_DBF_PATH = os.path.join(DBF_PATH, 'tbl_prod02.dbf')
FORMULA01_DBF_PATH = os.path.join(DBF_PATH, 'tbl_formula01.dbf')
FORMULA02_DBF_PATH = os.path.join(DBF_PATH, 'tbl_formula02.dbf')
CUSTOMER_DBF_PATH = os.path.join(DBF_PATH, 'tbl_customer01.dbf')
INCOMING02_DBF_PATH = os.path.join(DBF_PATH, 'tbl_incoming2.dbf')

# --- NEW: Configuration for the external Raw Materials database ---
DB_CONFIG_RAW_MATERIALS = {
    "host": getenv("DB_HOST"),
    "port": getenv("DB_PORT"),
    "dbname": "RMManagementSystemDB",
    "user": getenv("DB_USER"),
    "password": getenv("DB_PASSWORD")
}
# --- END NEW ---


# --- Helper Functions for Safe Data Conversion ---
# These functions will prevent crashes when encountering bad data in DBF files.


# --- NEW: Custom Field Parser to handle invalid dates ---
class SafeFieldParser(FieldParser):
    def parseD(self, field, data):
        """
        Custom date parser that returns None for invalid date strings.
        This prevents crashes on 'zero dates' like b'00000000'.
        """
        try:
            # Attempt to parse the date using the default dbfread method
            return super().parseD(field, data)
        except ValueError:
            # If it fails (e.g., year 0), return None instead of crashing
            return None


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
    """This class orchestrates the UI part of the sync process."""
    def __init__(self, engine, parent_widget):
        self.engine = engine
        # Store the parent QWidget correctly
        self.parent_widget = parent_widget
        self.sync_thread = None
        self.sync_worker = None

    def run_sync(self):
        """Initializes and runs the database sync worker in a separate thread."""
        # Use the stored parent widget when creating the dialog
        self.progress_dialog = QProgressDialog("Starting database synchronization...", "Cancel", 0, 100, self.parent_widget)
        self.progress_dialog.setWindowTitle("Sync in Progress")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        # --- MODIFIED: Pass the main engine AND the new RM engine config ---
        self.sync_thread = QThread()
        self.sync_worker = SyncWorker(self.engine, DB_CONFIG_RAW_MATERIALS)
        self.sync_worker.moveToThread(self.sync_thread)
        # --- END MODIFICATION ---

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
        # --- THIS IS THE FIX ---
        # Use `self.parent_widget` as the parent for the message box.
        QMessageBox.information(self.parent_widget, "Sync Complete", result_message)

    def on_sync_error(self, error_message):
        """Handles a failure in the sync process."""
        self.progress_dialog.close()
        # --- THIS IS THE FIX ---
        # Use `self.parent_widget` as the parent for the message box.
        QMessageBox.critical(self.parent_widget, "Sync Failed", error_message)


class SyncWorker(QObject):
    """Worker object that syncs data from DBF files and external PostgreSQL."""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str, int)

    def __init__(self, main_engine, rm_db_config, parent=None):
        super().__init__(parent)
        self.main_engine = main_engine
        self.rm_db_config = rm_db_config
        self.engine_rm = None

    def _connect_rm_db(self):
        """Establishes a connection to the external Raw Materials database."""
        if self.engine_rm:
            return True
        try:
            rm_db_url = (f"postgresql+psycopg2://{self.rm_db_config['user']}:{self.rm_db_config['password']}"
                         f"@{self.rm_db_config['host']}:{self.rm_db_config['port']}/{self.rm_db_config['dbname']}")
            self.engine_rm = create_engine(rm_db_url, pool_pre_ping=True, connect_args={'connect_timeout': 5})
            # Test the connection
            with self.engine_rm.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except OperationalError as e:
            self.error.emit(f"Could not connect to the Raw Materials database.\nPlease check the connection details and network.\n\nError: {e}")
            return False
        except Exception as e:
            self.error.emit(f"An unexpected error occurred while connecting to the Raw Materials database:\n\n{e}")
            return False

    @pyqtSlot()
    def run(self):
        """Main method that executes the full sync process."""
        # --- NEW: Connect to RM DB first ---
        if not self._connect_rm_db():
            return # Stop if connection fails

        main_session = None
        try:
            MainSession = sessionmaker(bind=self.main_engine)
            main_session = MainSession()

            # --- THIS IS THE NEW, CORRECT LOGIC ---
            self.progress.emit("Fetching Records.", 5)

            # 1. Fetch existing legacy IDs to avoid duplicates.
            existing_header_uids: Set[int] = {row.T_UID for row in main_session.query(TblFormula01.T_UID).all()}
            existing_detail_keys: Set[Tuple[int, int]] = {
                (row.T_UID, row.T_SEQ) for row in main_session.query(TblFormula02.T_UID, TblFormula02.T_SEQ).all()
            }

            # 2. Create a dictionary to hold new parent objects in memory.
            #    This maps the old legacy T_UID to the new SQLAlchemy object.
            new_headers_map = {}

            # 3. Process Formula Headers (tbl_formula01)
            self.progress.emit("Fetching Records..", 15)
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
                main_session.add(new_header) # Add to the session immediately
                new_headers_map[t_uid] = new_header # Store in our map

            # 4. Process Formula Details (tbl_formula02) and link them to headers
            self.progress.emit("Fetching Records...", 40)
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


            self.progress.emit("Syncing Records", 30)
            p1_new = self._sync_prod01(main_session)

            self.progress.emit("Syncing Records.", 45)
            p2_new = self._sync_prod02(main_session)

            # --- NEW: Sync Raw Materials ---
            self.progress.emit("Syncing Records..", 60)
            rm_new = self._sync_raw_materials(main_session)


            self.progress.emit("Syncing Records...", 75)
            cust_new = self._sync_customers(main_session)


            # --- NEW: Call the incoming2 sync method ---
            self.progress.emit("Syncing Records....", 85)
            inc2_new = self._sync_incoming2(main_session)
            
            self.progress.emit("Almost Done.....", 95)
            main_session.commit()

            result_message = (
                "Database Synchronization Successful!"
            )
            self.finished.emit(result_message)

        except Exception as e:
            if main_session:
                main_session.rollback()
            import traceback
            self.error.emit(f"An error occurred during synchronization:\n\n{traceback.format_exc()}")
        finally:
            if main_session:
                main_session.close()
            if self.engine_rm:
                self.engine_rm.dispose()

    # --- NEW METHOD: Logic for syncing TblProd02 ---
    def _sync_prod02(self, session) -> int:
        """
        Syncs tbl_prod02.dbf to the TblProd02 table.
        Prevents duplicates based on a composite key of (T_PRODID, T_SEQ).
        """
        # A composite key (prodid, seq) is a reliable way to identify unique records.
        existing_keys: Set[Tuple[Decimal, int]] = {
            (row.T_PRODID, row.T_SEQ) for row in session.query(TblProd02.T_PRODID, TblProd02.T_SEQ).all()
        }
        records_to_add = []

        try:
            dbf_records = dbfread.DBF(PRODUCTION02_DBF_PATH, encoding='latin1')._iter_records()
        except dbfread.exceptions.DBFNotFound:
            raise FileNotFoundError(f"File not found: {PRODUCTION02_DBF_PATH}")

        for record in dbf_records:
            t_prodid = safe_decimal(record.get('T_PRODID'))
            t_seq = safe_int(record.get('T_SEQ'))

            # # Skip if the composite key is invalid or already exists
            # if not t_prodid or (t_prodid, t_seq) in existing_keys:
            #     continue

            try:
                new_prod_detail = TblProd02(
                    T_PRODID=t_prodid,
                    T_LOTNUM=record.get('T_LOTNUM'),
                    T_CDATE=record.get('T_CDATE'),
                    T_PRODDATE=record.get('T_PRODDATE'),
                    T_SEQ=t_seq,
                    T_MATCODE=record.get('T_MATCODE'),
                    T_PRODA=safe_decimal(record.get('T_PRODA')),
                    T_LABA=safe_decimal(record.get('T_LABA')),
                    T_PRODB=safe_decimal(record.get('T_PRODB')),
                    T_LABB=safe_decimal(record.get('T_LABB')),
                    T_WT=safe_decimal(record.get('T_WT')),
                    T_LOSS=safe_decimal(record.get('T_LOSS')),
                    T_CONS=safe_decimal(record.get('T_CONS')),
                    T_DELETED=safe_bool(record.get('T_DELETED')),
                )
                records_to_add.append(new_prod_detail)
            except Exception as e:
                print(f"Skipping corrupt record in tbl_prod02 for T_PRODID={t_prodid}, T_SEQ={t_seq}. Error: {e}")
                continue

        if records_to_add:
            session.add_all(records_to_add)

        return len(records_to_add)


    # --- NEW METHOD for Raw Materials Sync ---
    def _sync_raw_materials(self, main_session) -> int:
        """
        Fetches all raw materials from the external DB and upserts them
        into the main application's database.
        """
        SessionRM = sessionmaker(bind=self.engine_rm)
        session_rm = SessionRM()
        
        try:
            # 1. Fetch all records from the source database using the ORM model
            source_materials = session_rm.query(RawMaterials).all()
            if not source_materials:
                return 0 # Nothing to sync

            # 2. Get existing rm_codes from the destination database to check for updates
            existing_codes = {row.rm_code for row in main_session.query(RawMaterials.rm_code).all()}
            
            new_records = []
            for material in source_materials:
                if material.rm_code not in existing_codes:
                    # Create a new RawMaterials object for the main DB session
                    new_material = RawMaterials(
                        # Map all relevant fields
                        id=material.id, # Keep the same UUID
                        rm_code=material.rm_code,
                        rm_name=material.rm_name,
                        description=material.description,
                        is_deleted=material.is_deleted,
                        # We don't copy created_by etc. unless those users exist in the main DB
                    )
                    new_records.append(new_material)
            
            if new_records:
                main_session.bulk_save_objects(new_records)
            
            return len(new_records)

        finally:
            session_rm.close()


    
    # This method is now only used for tbl_prod01, which has no dependencies
    def _sync_prod01(self, session) -> int:
        """Syncs tbl_prod01, safely handling data conversion errors."""
        existing_prodids: Set[Decimal] = {row.T_PRODID for row in session.query(TblProd01.T_PRODID).all()}
        records_to_add = []
        try:
            dbf_records = dbfread.DBF(PRODUCTION01_DBF_PATH, encoding='latin1')._iter_records()
        except dbfread.exceptions.DBFNotFound:
            raise FileNotFoundError(f"File not found: {PRODUCTION01_DBF_PATH}")

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

    # --- NEW METHOD: Logic for syncing customers ---
    def _sync_customers(self, session) -> int:
        """
        Syncs tbl_customer01.dbf to the main application's Customer table.
        It prevents duplicates based on customer name.
        """
        # Get all existing customer names from the destination table to prevent duplicates
        existing_names: Set[str] = {row.name for row in session.query(Customer.name).all()}
        records_to_add = []

        try:
            dbf_records = dbfread.DBF(CUSTOMER_DBF_PATH, encoding='latin1')._iter_records()
        except dbfread.exceptions.DBFNotFound:
            raise FileNotFoundError(f"File not found: {CUSTOMER_DBF_PATH}")

        for record in dbf_records:
            # The customer name is in the 'T_CUSTOMER' field. Strip whitespace.
            customer_name = record.get('T_CUSTOMER', '').strip()

            # Skip if the name is empty or already exists in our database
            if not customer_name or customer_name in existing_names:
                continue

            # Create a new Customer object. The AuditMixin will handle created_at etc.
            new_customer = Customer(name=customer_name)
            records_to_add.append(new_customer)
            # Add the new name to our set to handle duplicates within the DBF file itself
            existing_names.add(customer_name)

        if records_to_add:
            session.add_all(records_to_add)

        return len(records_to_add)
    # --- END NEW METHOD ---

    def _sync_incoming2(self, session) -> int:
        existing_ctrl_nums: Set[str] = {row.t_ctrlnum for row in session.query(TblIncoming2.t_ctrlnum).all()}
        records_to_add = []
        try:
            dbf_records = dbfread.DBF(INCOMING02_DBF_PATH, encoding='latin1',
                                      parserclass=SafeFieldParser)._iter_records()
        except dbfread.exceptions.DBFNotFound:
            raise FileNotFoundError(f"File not found: {INCOMING02_DBF_PATH}")
        for record in dbf_records:
            # --- THE FIX: Use UPPERCASE keys for all .get() calls ---
            # Also, add strip() to the control number for robustness.
            t_ctrlnum = record.get('T_CTRLNUM', '').strip()

            if not t_ctrlnum or t_ctrlnum in existing_ctrl_nums:
                continue

            try:
                new_incoming_record = TblIncoming2(
                    t_seq=safe_int(record.get('T_SEQ')),
                    t_ctrlnum=t_ctrlnum,
                    t_date=record.get('T_DATE'),
                    t_matcode=record.get('T_MATCODE'),
                    t_qty=safe_decimal(record.get('T_QTY')),
                    t_note=record.get('T_NOTE'),
                    t_uid=record.get('T_UID'),
                    t_deleted=safe_bool(record.get('T_DELETED')),
                    t_customer=record.get('T_CUSTOMER'),
                    t_code=record.get('T_CODE'),
                    t_po=record.get('T_PO'),
                    t_datereq=record.get('T_DATEREQ'),
                    t_datereq2=record.get('T_DATEREQ2'),
                    t_delto=record.get('T_DELTO'),
                    t_orderedb=record.get('T_ORDEREDB'),
                    t_prepared=record.get('T_PREPARED'),
                    t_mattype=record.get('T_MATTYPE'),
                    t_status=record.get('T_STATUS'),
                    t_time=record.get('T_TIME')
                )
                records_to_add.append(new_incoming_record)
                existing_ctrl_nums.add(t_ctrlnum)
            except Exception as e:
                print(f"Skipping corrupt record in tbl_incoming2 for T_CTRLNUM={t_ctrlnum}. Error: {e}")
        if records_to_add:
            session.add_all(records_to_add)
        return len(records_to_add)