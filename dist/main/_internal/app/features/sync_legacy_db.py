import os
from decimal import Decimal, InvalidOperation as DecimalInvalidOperation
from typing import Set, Tuple, Any, Dict, List

import dbfread
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QThread, Qt
from PyQt6.QtWidgets import QProgressDialog, QMessageBox
from dbfread import FieldParser
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

from models import TblProd01, TblFormula01, TblFormula02, RawMaterials, Customer, TblProd02, TblIncoming2
from os import getenv

# --- DATABASE FILE PATHS ---
DBF_PATH = r'\\system-server\SYSTEM-NEW-OLD'
PRODUCTION01_DBF_PATH = os.path.join(DBF_PATH, 'tbl_prod01.dbf')
PRODUCTION02_DBF_PATH = os.path.join(DBF_PATH, 'tbl_prod02.dbf')
FORMULA01_DBF_PATH = os.path.join(DBF_PATH, 'tbl_formula01.dbf')
FORMULA02_DBF_PATH = os.path.join(DBF_PATH, 'tbl_formula02.dbf')
CUSTOMER_DBF_PATH = os.path.join(DBF_PATH, 'tbl_customer01.dbf')
INCOMING02_DBF_PATH = os.path.join(DBF_PATH, 'tbl_incoming2.dbf')

# --- Configuration for the external Raw Materials database ---
DB_CONFIG_RAW_MATERIALS = {
    "host": getenv("DB_HOST"),
    "port": getenv("DB_PORT"),
    "dbname": "RMManagementSystemDB",
    "user": getenv("DB_USER"),
    "password": getenv("DB_PASSWORD")
}


# --- Helper Functions for Safe Data Conversion ---
class SafeFieldParser(FieldParser):
    def parseD(self, field, data):
        try: return super().parseD(field, data)
        except ValueError: return None

def safe_decimal(value: Any) -> Decimal | None:
    try: return Decimal(value) if value is not None else None
    except (ValueError, TypeError, DecimalInvalidOperation): return None

def safe_int(value: Any) -> int | None:
    try: return int(value) if value is not None else None
    except (ValueError, TypeError): return None

def safe_bool(value: Any) -> bool | None:
    if isinstance(value, bool): return value
    if isinstance(value, str): return value.strip().upper() in ('T', 'Y', 'TRUE')
    return bool(value) if value is not None else None


class SyncController:
    """This class orchestrates the UI part of the sync process."""

    def __init__(self, engine, parent_widget):
        self.engine = engine
        self.parent_widget = parent_widget
        self.sync_thread = None
        self.sync_worker = None

    def run_sync(self):
        self.progress_dialog = QProgressDialog("Starting database synchronization...", "Cancel", 0, 100,
                                               self.parent_widget)
        self.progress_dialog.setWindowTitle("Sync in Progress")
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.show()

        self.sync_thread = QThread()
        self.sync_worker = SyncWorker(self.engine, DB_CONFIG_RAW_MATERIALS)
        self.sync_worker.moveToThread(self.sync_thread)

        self.sync_thread.started.connect(self.sync_worker.run)
        self.sync_worker.progress.connect(self.update_progress)
        self.sync_worker.finished.connect(self.on_sync_finished)
        self.sync_worker.error.connect(self.on_sync_error)

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
        self.progress_dialog.close()
        QMessageBox.information(self.parent_widget, "Sync Complete", result_message)

    def on_sync_error(self, error_message):
        self.progress_dialog.close()
        QMessageBox.critical(self.parent_widget, "Sync Failed", error_message)


class SyncWorker(QObject):
    """
    Worker object that performs a fast 'Truncate and Load' sync from DBF
    files and an external PostgreSQL database.
    """
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    progress = pyqtSignal(str, int)

    def __init__(self, main_engine, rm_db_config, parent=None):
        super().__init__(parent)
        self.main_engine = main_engine
        self.rm_db_config = rm_db_config
        self.engine_rm = None

    def _connect_rm_db(self):
        if self.engine_rm: return True
        try:
            rm_db_url = (f"postgresql+psycopg2://{self.rm_db_config['user']}:{self.rm_db_config['password']}"
                         f"@{self.rm_db_config['host']}:{self.rm_db_config['port']}/{self.rm_db_config['dbname']}")
            self.engine_rm = create_engine(rm_db_url, pool_pre_ping=True, connect_args={'connect_timeout': 5})
            with self.engine_rm.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception as e:
            self.error.emit(f"Could not connect to the Raw Materials database.\n\nError: {e}")
            return False

    @pyqtSlot()
    def run(self):
        """Main method that executes the full 'Truncate and Load' sync process."""
        if not self._connect_rm_db():
            return

        main_session = None
        try:
            MainSession = sessionmaker(bind=self.main_engine)
            main_session = MainSession()

            self.progress.emit("Preparing database (clearing old records)...", 5)
            print("--- PRE-SYNC: Truncating all target tables ---")

            # This single command truncates all tables and resets their ID sequences.
            # The CASCADE option handles foreign key relationships correctly.
            truncate_command = text("""
                TRUNCATE TABLE 
                    public.tbl_formula02, public.tbl_formula01,
                    public.tbl_prod02, public.tbl_prod01,
                    public.tbl_incoming2,
                    public.tbl_customers,
                    public.tbl_raw_materials
                RESTART IDENTITY CASCADE;
            """)
            main_session.execute(truncate_command)
            main_session.commit()
            print("All target tables have been truncated.")

            # --- SYNC PHASE: FAST BULK INSERTS ---
            self.progress.emit("Syncing records...", 15)
            f1_new, f2_new = self._sync_formulas(main_session)

            self.progress.emit("Syncing records...", 30)
            p1_new = self._sync_prod01(main_session)

            self.progress.emit("Syncing records...", 45)
            p2_new = self._sync_prod02(main_session)

            self.progress.emit("Syncing records...", 60)
            rm_new = self._sync_raw_materials(main_session)

            self.progress.emit("Syncing records...", 75)
            cust_new = self._sync_customers(main_session)

            self.progress.emit("Syncing records...", 85)
            inc2_new = self._sync_incoming2(main_session)

            self.progress.emit("Finalizing synchronization...", 95)
            main_session.commit()

            result_message = (
                "Synchronization Successful!\n\n"
            )
            self.finished.emit(result_message)

        except Exception as e:
            if main_session: main_session.rollback()
            import traceback
            self.error.emit(f"An error occurred during synchronization:\n\n{traceback.format_exc()}")
        finally:
            if main_session: main_session.close()
            if self.engine_rm: self.engine_rm.dispose()

    def _sync_formulas(self, session) -> Tuple[int, int]:
        """Loads all non-deleted formula headers and details."""
        headers_to_add = []
        headers_map_for_details: Dict[int, TblFormula01] = {}

        dbf_headers = dbfread.DBF(FORMULA01_DBF_PATH, encoding='latin1', parserclass=SafeFieldParser)._iter_records()
        for record in dbf_headers:
            if safe_bool(record.get('T_DELETED')): continue

            t_uid = safe_int(record.get('T_UID'))
            if not t_uid: continue

            new_header = TblFormula01(
                T_UID=t_uid, T_INDEX=record.get('T_INDEX'), T_DATE=record.get('T_DATE'),
                T_CUSTOMER=record.get('T_CUSTOMER'), T_PRODCODE=record.get('T_PRODCODE'),
                T_PRODCOLO=record.get('T_PRODCOLO'), T_DOSAGE=safe_decimal(record.get('T_DOSAGE')),
                T_LD=safe_decimal(record.get('T_LD')), T_MIX=record.get('T_MIX'),
                T_RESIN=record.get('T_RESIN'), T_APP=record.get('T_APP'),
                T_CMNUM=record.get('T_CMNUM'), T_CMDATE=record.get('T_CMDATE'),
                T_MATCHBY=record.get('T_MATCHBY'), T_ENCODEDB=record.get('T_ENCODEDB'),
                T_REM=record.get('T_REM'), T_TOTALCON=safe_decimal(record.get('T_TOTALCON')),
                T_USER=record.get('T_USER'), T_DELETED=False, T_USED=safe_bool(record.get('T_USED')),
                T_UPDATEBY=record.get('T_UPDATEBY'), T_UDATE=record.get('T_UDATE')
            )
            headers_to_add.append(new_header)
            headers_map_for_details[t_uid] = new_header

        if headers_to_add:
            session.bulk_save_objects(headers_to_add)

        details_to_add = []
        dbf_details = dbfread.DBF(FORMULA02_DBF_PATH, encoding='latin1', parserclass=SafeFieldParser)._iter_records()
        for record in dbf_details:
            if safe_bool(record.get('T_DELETED')): continue

            t_uid, t_seq = safe_int(record.get('T_UID')), safe_int(record.get('T_SEQ'))
            if not t_uid or t_seq is None: continue

            parent_header = headers_map_for_details.get(t_uid)
            if parent_header:
                new_detail = TblFormula02(
                    T_UID=t_uid, T_SEQ=t_seq, T_MATCODE=record.get('T_MATCODE'),
                    T_CON=safe_decimal(record.get('T_CON')), T_DELETED=False,
                    T_UPDATEBY=record.get('T_UPDATEBY'), T_UDATE=record.get('T_UDATE')
                )
                parent_header.details.append(new_detail)
                details_to_add.append(new_detail)

        return len(headers_to_add), len(details_to_add)

    def _sync_prod01(self, session) -> int:
        """Loads all non-deleted records from tbl_prod01."""
        records_to_add = []
        dbf_records = dbfread.DBF(PRODUCTION01_DBF_PATH, encoding='latin1', parserclass=SafeFieldParser)._iter_records()
        for record in dbf_records:
            if safe_bool(record.get('T_DELETED')): continue

            records_to_add.append(TblProd01(
                T_PRODID=safe_decimal(record.get('T_PRODID')), T_PRODDATE=record.get('T_PRODDATE'),
                T_CUSTOMER=record.get('T_CUSTOMER'), T_FID=safe_int(record.get('T_FID')),
                T_INDEX=record.get('T_INDEX'), T_PRODCODE=record.get('T_PRODCODE'),
                T_PRODCOLO=record.get('T_PRODCOLO'), T_DOSAGE=safe_decimal(record.get('T_DOSAGE')),
                T_LD=safe_decimal(record.get('T_LD')), T_QTYREQ=safe_decimal(record.get('T_QTYREQ')),
                T_QTYBATCH=safe_decimal(record.get('T_QTYBATCH')), T_QTYPROD=safe_decimal(record.get('T_QTYPROD')),
                T_LOTNUM=record.get('T_LOTNUM'), T_ORDERNUM=record.get('T_ORDERNUM'),
                T_CMNUM=record.get('T_CMNUM'), T_CMDATE=record.get('T_CMDATE'),
                T_MIXTIME=record.get('T_MIXTIME'), T_MACHINE=record.get('T_MACHINE'),
                T_REMARKS=record.get('T_REMARKS'), T_NOTE=record.get('T_NOTE'),
                T_USERID=record.get('T_USERID'), T_PREPARED=record.get('T_PREPARED'),
                T_ENCODEDB=record.get('T_ENCODEDB'), T_ENCODEDO=record.get('T_ENCODEDO'),
                T_DELETED=False, T_JDONE=record.get('T_JDONE'), T_CDATE=record.get('T_CDATE'),
                T_SDATE=record.get('T_SDATE'), T_FTYPE=record.get('T_FTYPE')
            ))

        if records_to_add:
            session.bulk_save_objects(records_to_add)
        return len(records_to_add)

    def _sync_prod02(self, session) -> int:
        """Loads all non-deleted records from tbl_prod02."""
        records_to_add = []
        dbf_records = dbfread.DBF(PRODUCTION02_DBF_PATH, encoding='latin1', parserclass=SafeFieldParser)._iter_records()
        for record in dbf_records:
            if safe_bool(record.get('T_DELETED')): continue

            records_to_add.append(TblProd02(
                T_PRODID=safe_decimal(record.get('T_PRODID')), T_LOTNUM=record.get('T_LOTNUM'),
                T_CDATE=record.get('T_CDATE'), T_PRODDATE=record.get('T_PRODDATE'),
                T_SEQ=safe_int(record.get('T_SEQ')), T_MATCODE=record.get('T_MATCODE'),
                T_PRODA=safe_decimal(record.get('T_PRODA')), T_LABA=safe_decimal(record.get('T_LABA')),
                T_PRODB=safe_decimal(record.get('T_PRODB')), T_LABB=safe_decimal(record.get('T_LABB')),
                T_WT=safe_decimal(record.get('T_WT')), T_LOSS=safe_decimal(record.get('T_LOSS')),
                T_CONS=safe_decimal(record.get('T_CONS')), T_DELETED=False
            ))

        if records_to_add:
            session.bulk_save_objects(records_to_add)
        return len(records_to_add)

    def _sync_raw_materials(self, main_session) -> int:
        """Loads all non-deleted raw materials from the external DB."""
        SessionRM = sessionmaker(bind=self.engine_rm)
        session_rm = SessionRM()
        try:
            source_materials = session_rm.query(RawMaterials).filter(RawMaterials.is_deleted != True).all()
            if not source_materials: return 0

            records_to_add = [
                RawMaterials(
                    id=material.id, rm_code=material.rm_code,
                    rm_name=material.rm_name, description=material.description,
                    is_deleted=material.is_deleted
                ) for material in source_materials
            ]

            if records_to_add:
                main_session.bulk_save_objects(records_to_add)
            return len(records_to_add)
        finally:
            session_rm.close()

    def _sync_customers(self, session) -> int:
        """Loads all customers from the DBF file."""
        records_to_add = []
        dbf_records = dbfread.DBF(CUSTOMER_DBF_PATH, encoding='latin1', parserclass=SafeFieldParser)._iter_records()
        for record in dbf_records:
            customer_name = record.get('T_CUSTOMER', '').strip()
            if not customer_name: continue
            records_to_add.append(Customer(name=customer_name))

        if records_to_add:
            unique_records = {rec.name: rec for rec in records_to_add}.values()
            session.bulk_save_objects(unique_records)
            return len(unique_records)
        return 0

    def _sync_incoming2(self, session) -> int:
        """Loads all non-deleted records from tbl_incoming2."""
        records_to_add = []
        dbf_records = dbfread.DBF(INCOMING02_DBF_PATH, encoding='latin1', parserclass=SafeFieldParser)._iter_records()
        for record in dbf_records:
            if safe_bool(record.get('T_DELETED')): continue

            records_to_add.append(TblIncoming2(
                t_ctrlnum=record.get('T_CTRLNUM', '').strip(),
                t_seq=safe_int(record.get('T_SEQ')), t_date=record.get('T_DATE'),
                t_matcode=record.get('T_MATCODE'), t_qty=safe_decimal(record.get('T_QTY')),
                t_note=record.get('T_NOTE'), t_uid=record.get('T_UID'),
                t_deleted=False, t_customer=record.get('T_CUSTOMER'),
                t_code=record.get('T_CODE'), t_po=record.get('T_PO'),
                t_datereq=record.get('T_DATEREQ'), t_datereq2=record.get('T_DATEREQ2'),
                t_delto=record.get('T_DELTO'), t_orderedb=record.get('T_ORDEREDB'),
                t_prepared=record.get('T_PREPARED'), t_mattype=record.get('T_MATTYPE'),
                t_status=record.get('T_STATUS'), t_time=record.get('T_TIME')
            ))

        if records_to_add:
            session.bulk_save_objects(records_to_add)
        return len(records_to_add)
