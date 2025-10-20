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
    # ... other columns are correct
    process_id = Column(String(100), index=True)
    production_id = Column(String(100), index=True)
    formula_no = Column(String(100))
    order_no = Column(String(100))
    product_code = Column(String(100))
    customer = Column(String(500))
    lot_number = Column(String(100), index=True)
    qty_order = Column(Numeric(10, 2))
    total_input = Column(Numeric(10, 2))
    remarks = Column(Text)
    prepared_by = Column(String(255))
    is_completed = Column(Boolean, default=False, nullable=False)
    machine_id = Column(Integer, ForeignKey("tbl_extruder_machines.id"), nullable=False)
    machine_datetime_start = Column(DateTime(timezone=True))
    machine_datetime_end = Column(DateTime(timezone=True))

    # Relationships
    machine = relationship("ExtruderMachine", back_populates="extruder_form_data")
    machine_temps = relationship("MachineTemp", back_populates="extruder_form_data", cascade="all, delete-orphan")
    used_materials = relationship("UsedMaterial", back_populates="extruder_form_data", cascade="all, delete-orphan")
    purging_headers = relationship("PurgingHeader", back_populates="extruder_form_data", cascade="all, delete-orphan")
    extruder_outputs = relationship("ExtruderOutput", back_populates="extruder_form_data", cascade="all, delete-orphan")
    machine_configs = relationship("MachineConfig", back_populates="extruder_form_data", cascade="all, delete-orphan")
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


class UsedMaterial(Base, AuditMixin):
    __tablename__ = "tbl_extruder_used_materials"
    id = Column(Integer, primary_key=True, autoincrement=True)
    extruder_form_data_id = Column(Integer, ForeignKey("tbl_extruder_form_data.id"), nullable=False)
    formula_id = Column(String(100))
    material = Column(String(255), nullable=False)
    qty = Column(Numeric(10, 2), nullable=False)
    extruder_form_data = relationship("ExtruderFormData", back_populates="used_materials")


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

    # --- FIX 1: Added the missing relationship to the Resin model ---
    resin_used = relationship("Resin", back_populates="purging_headers")


class PurgingDetail(Base, AuditMixin):
    __tablename__ = "tbl_extruder_purging_details"
    id = Column(Integer, primary_key=True, autoincrement=True)
    purging_header_id = Column(Integer, ForeignKey("tbl_extruder_purging_headers.id"), nullable=False)
    resin_id = Column(SmallInteger, ForeignKey("tbl_extruder_resins.id"), nullable=False)
    qty = Column(Numeric(10, 2))

    # --- FIX 2: Restored the correct back_populates argument ---
    resin = relationship("Resin", back_populates="purging_details")
    purging_header = relationship("PurgingHeader", back_populates="purging_details")


# --- Other models remain the same ---

class ExtruderOutput(Base, AuditMixin):
    __tablename__ = "tbl_extruder_outputs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    extruder_form_data_id = Column(Integer, ForeignKey("tbl_extruder_form_data.id"), nullable=False)
    date = Column(DateTime(timezone=True))
    time_start = Column(DateTime(timezone=True))
    time_end = Column(DateTime(timezone=True))
    qty_output = Column(Numeric(10, 2))
    qty_loss = Column(Numeric(10, 2))
    extruder_form_data = relationship("ExtruderFormData", back_populates="extruder_outputs")


class MachineConfig(Base, AuditMixin):
    __tablename__ = "tbl_extruder_machine_configs"
    id = Column(Integer, primary_key=True, autoincrement=True)
    extruder_form_data_id = Column(Integer, ForeignKey("tbl_extruder_form_data.id"), nullable=False)
    screen_size_id = Column(Integer, ForeignKey("tbl_extruder_screen_sizes.id"), nullable=False)
    screw_config = Column(String(255))
    feed_rate = Column(String(100))
    rpm = Column(String(100))
    extruder_form_data = relationship("ExtruderFormData", back_populates="machine_configs")
    screen_size = relationship("ScreenSize", back_populates="machine_configs")


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
    machine_configs = relationship("MachineConfig", back_populates="screen_size")