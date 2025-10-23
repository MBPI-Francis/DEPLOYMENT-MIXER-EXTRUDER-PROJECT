# models/ExtruderCore.py

import uuid
from sqlalchemy import (
    Column,
    String,
    ForeignKey,
    DateTime,
    Boolean,
    SmallInteger,
    Integer,
    Numeric,
    Text
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from models import Base
from .Mixins import AuditMixin


class ExtruderFormData(Base, AuditMixin):
    __tablename__ = "tbl_extruder_form_data"
    id = Column(Integer, primary_key=True, autoincrement=True)
    process_id = Column(String(100), index=True)
    production_id = Column(String(100), index=True)
    formula_no = Column(String(100))
    order_no = Column(String(100))
    product_code = Column(String(100))
    customer = Column(String(500))
    lot_number = Column(String(100), index=True)
    qty_order = Column(Numeric(10, 2))
    qty_produced = Column(Numeric(10, 2))
    remarks = Column(Text)
    prepared_by = Column(String(255))
    is_completed = Column(Boolean, default=False, nullable=False)

    # Foreign Keys
    machine_id = Column(Integer, ForeignKey("tbl_extruder_machines.id"), nullable=False)
    shift_id = Column(Integer, ForeignKey("tbl_extruder_shifts.id"), nullable=False)

    # Relationships
    machine = relationship("ExtruderMachine", back_populates="extruder_form_data")
    shift = relationship("Shift", back_populates="extruder_form_data")

    machine_temps = relationship("MachineTemp", back_populates="extruder_form_data", cascade="all, delete-orphan")
    purging_headers = relationship("PurgingHeader", back_populates="extruder_form_data", cascade="all, delete-orphan")
    extruder_outputs = relationship("ExtruderOutput", back_populates="extruder_form_data", cascade="all, delete-orphan")

    # --- FIX: Renamed for consistency and defined as one-to-one ---
    machine_details = relationship("MachineDetail", back_populates="extruder_form_data", cascade="all, delete-orphan",
                                   uselist=False)

    extruder_personnels = relationship("ExtruderPersonnel", back_populates="extruder_form_data",
                                       cascade="all, delete-orphan")


class MachineTemp(Base, AuditMixin):
    __tablename__ = "tbl_extruder_machine_temps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    extruder_form_data_id = Column(Integer, ForeignKey("tbl_extruder_form_data.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("tbl_extruder_zones.id"), nullable=False)
    temp_value = Column(Numeric(10, 2), nullable=False)
    extruder_form_data = relationship("ExtruderFormData", back_populates="machine_temps")
    zone = relationship("Zone", back_populates="machine_temps")


class PurgingHeader(Base, AuditMixin):
    __tablename__ = "tbl_extruder_purging_headers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    extruder_form_data_id = Column(Integer, ForeignKey("tbl_extruder_form_data.id"), nullable=False)
    product_code = Column(String(100))
    time_start = Column(DateTime(timezone=True))
    time_end = Column(DateTime(timezone=True))
    resin_used_id = Column(SmallInteger, ForeignKey("tbl_extruder_resins.id"), nullable=False)
    palletizer_used = Column(Numeric(10, 2))
    siever_used = Column(Numeric(10, 2))
    extruder_form_data = relationship("ExtruderFormData", back_populates="purging_headers")
    purging_details = relationship("PurgingDetail", back_populates="purging_header", cascade="all, delete-orphan")
    resin_used = relationship("Resin", back_populates="purging_headers")


class PurgingDetail(Base, AuditMixin):
    __tablename__ = "tbl_extruder_purging_details"
    id = Column(Integer, primary_key=True, autoincrement=True)
    purging_header_id = Column(Integer, ForeignKey("tbl_extruder_purging_headers.id"), nullable=False)
    resin_id = Column(SmallInteger, ForeignKey("tbl_extruder_resins.id"), nullable=False)
    qty = Column(Numeric(10, 2))
    notes = Column(String(250), nullable=True)
    resin = relationship("Resin", back_populates="purging_details")
    purging_header = relationship("PurgingHeader", back_populates="purging_details")


class ExtruderOutput(Base, AuditMixin):
    __tablename__ = "tbl_extruder_outputs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    extruder_form_data_id = Column(Integer, ForeignKey("tbl_extruder_form_data.id"), nullable=False)
    date = Column(DateTime(timezone=True))
    time_start = Column(DateTime(timezone=True))
    time_end = Column(DateTime(timezone=True))
    qty_output = Column(Numeric(10, 2))
    extruder_form_data = relationship("ExtruderFormData", back_populates="extruder_outputs")


class MachineDetail(Base, AuditMixin):
    __tablename__ = "tbl_extruder_machine_details"
    id = Column(Integer, primary_key=True, autoincrement=True)
    extruder_form_data_id = Column(Integer, ForeignKey("tbl_extruder_form_data.id"), nullable=False)
    screen_size_id = Column(Integer, ForeignKey("tbl_extruder_screen_sizes.id"), nullable=False)
    screw_config_id = Column(Integer, ForeignKey("tbl_extruder_screw_configs.id"), nullable=False)
    feed_rate = Column(String(100))
    rpm = Column(String(100))
    machine_datetime_start = Column(DateTime(timezone=True))
    machine_datetime_end = Column(DateTime(timezone=True))
    is_vacuum_on = Column(Boolean, default=False, nullable=False)

    # --- FIX: Removed redundant/incorrect relationships ---
    extruder_form_data = relationship("ExtruderFormData", back_populates="machine_details")
    screen_size = relationship("ScreenSize", back_populates="machine_details")
    screw_config = relationship("ScrewConfig", back_populates="machine_details")


class Shift(Base, AuditMixin):
    __tablename__ = "tbl_extruder_shifts"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(20))
    description = Column(String(500))

    # --- FIX: A Shift can be used in many form entries, so this should be a list ---
    extruder_form_data = relationship("ExtruderFormData", back_populates="shift")


class ExtruderPersonnel(Base, AuditMixin):
    __tablename__ = "tbl_extruder_personnels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    extruder_form_data_id = Column(Integer, ForeignKey("tbl_extruder_form_data.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("tbl_production_employees.id"), nullable=False)
    position_id = Column(Integer, ForeignKey("tbl_employee_positions.id"), nullable=False)
    extruder_form_data = relationship("ExtruderFormData", back_populates="extruder_personnels")
    employee = relationship("ProductionEmployee", back_populates="extruder_personnels")
    position = relationship("EmployeePosition", back_populates="extruder_personnels")


class ScreenSize(Base, AuditMixin):
    __tablename__ = "tbl_extruder_screen_sizes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    size = Column(String(50), nullable=False, unique=True, index=True)

    # --- FIX: Corrected back_populates to match new name in MachineDetail ---
    machine_details = relationship("MachineDetail", back_populates="screen_size")



class ScrewConfig(Base, AuditMixin):
    __tablename__ = "tbl_extruder_screw_configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True, index=True)

    # --- FIX: Corrected back_populates to match new name in MachineDetail ---
    machine_details = relationship("MachineDetail", back_populates="screw_config")