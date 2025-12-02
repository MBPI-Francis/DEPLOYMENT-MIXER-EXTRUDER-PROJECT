# models/ExtruderConfig.py
import uuid
from operator import index

from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    DateTime,
    Boolean,
    SmallInteger,
    Integer,
    Numeric,
    UniqueConstraint, Date, Sequence
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import relationship, declared_attr
from datetime import datetime, timezone

from models import Base
from .Mixins import AuditMixin





class ExtruderOldExcelData(Base):
    __tablename__ = "tbl_extruder_old_excel_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), index=True, nullable=True)
    date = Column(String(50), nullable=True)
    customer = Column(String(500), nullable=True)
    qty_input = Column(String(15), nullable=True)
    qty_output = Column(String(15), nullable=True)
    output_per_hour = Column(String(15), nullable=True)
    lot_number = Column(String(500), index=True, nullable=True)
    screw_config = Column(String(12), index=True, nullable=True)
    machine_no = Column(Integer, nullable= True, index=True)
    feed_rate = Column(String(40), nullable=True)
    rpm = Column(String(10), index=True, nullable=True)
    screen = Column(String(10), index=True, nullable=True)
    z1 = Column(String(15), nullable=True)
    z2 = Column(String(15), nullable=True)
    z3 = Column(String(15), nullable=True)
    z4 = Column(String(15), nullable=True)
    z5 = Column(String(15), nullable=True)
    z6 = Column(String(15), nullable=True)
    z7 = Column(String(15), nullable=True)
    z8 = Column(String(15), nullable=True)
    z9 = Column(String(15), nullable=True)
    z10 = Column(String(15), nullable=True)
    z11 = Column(String(15), nullable=True)
    z12 = Column(String(15), nullable=True)
    z13 = Column(String(15), nullable=True)
    resin_used = Column(String(100), index=True, nullable=True)
    remarks = Column(String(500), index=True, nullable=True)




class ExtruderOldAmielData(Base):
    """
    SQLAlchemy model for the 'tbl_extruder_old_amiel_data' table.
    """
    __tablename__ = "tbl_extruder_old_amiel_data"

    # Define the sequence for the primary key
    process_id_seq = Sequence('extruder_process_id_seq')

    # Column definitions based on the provided SQL schema
    process_id = Column(Integer, primary_key=True)
    machine = Column(String)
    qty_order = Column(Numeric) # Using Numeric for double precision
    total_output = Column(Numeric(10, 4))
    customer = Column(String)
    formula_id = Column(Integer)
    product_code = Column(String)
    order_id = Column(Integer)
    total_time = Column(Numeric)
    time_start = Column(ARRAY(DateTime))
    time_end = Column(ARRAY(DateTime))
    output_percent = Column(Numeric)
    loss = Column(Numeric)
    loss_percent = Column(Numeric)
    purging = Column(String)
    resin = Column(String)
    remarks = Column(String)
    screw_config = Column(String)
    feed_rate = Column(Numeric)
    rpm = Column(Integer)
    screen_size = Column(String)
    operator = Column(String)
    supervisor = Column(String)
    materials = Column(JSONB)
    temperature = Column(ARRAY(Integer))
    purge_duration = Column(Integer)
    outputs = Column(ARRAY(Numeric)) # Using Numeric for double precision
    output_per_hour = Column(Numeric)
    production_id = Column(Integer)
    total_input = Column(Numeric)
    lot_number = Column(ARRAY(String))
    createdBy = Column("createdBy", String)
    updatedBy = Column("updatedBy", String)
    resin_quantity = Column(Numeric)
    encoded_on = Column(Date)
    machine_start = Column(DateTime)
    machine_off = Column(DateTime)
