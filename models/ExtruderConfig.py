# models/ExtruderConfig.py
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
    UniqueConstraint
)
from sqlalchemy.orm import relationship, declared_attr
from datetime import datetime, timezone

from models import Base
from .Mixins import AuditMixin


class Resin(Base, AuditMixin):
    __tablename__ = "tbl_extruder_resins"
    id = Column(SmallInteger, primary_key=True, autoincrement=True)
    abbreviation = Column(String(10), nullable=True, unique=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    resin_params = relationship("ResinParams", back_populates="resin", cascade="all, delete-orphan")
    purging_details = relationship("PurgingDetail", back_populates="resin")
    purging_headers = relationship("PurgingHeader", back_populates="resin_used")


class Zone(Base, AuditMixin):
    __tablename__ = "tbl_extruder_zones"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True, index=True)
    processing_params = relationship("ProcessingParams", back_populates="zone", cascade="all, delete-orphan")
    machine_temps = relationship("MachineTemp", back_populates="zone")


class ExtruderMachine(Base, AuditMixin):
    __tablename__ = "tbl_extruder_machines"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(50), nullable=False, unique=True, index=True)

    # Relationships
    processing_params = relationship("ProcessingParams", back_populates="machine", cascade="all, delete-orphan")

    # --- FIX: Removed the incorrect relationship causing the crash ---
    # The link to machine details is indirect, through ExtruderFormData.
    # We add the correct relationship back to ExtruderFormData.
    extruder_form_data = relationship("ExtruderFormData", back_populates="machine")


class ResinParams(Base, AuditMixin):
    __tablename__ = "tbl_extruder_resin_params"
    id = Column(Integer, primary_key=True, autoincrement=True)
    resin_id = Column(SmallInteger, ForeignKey("tbl_extruder_resins.id"), nullable=False)
    motor_rpm = Column(String(50), nullable=False)
    feed_rate = Column(String(50), nullable=False)
    resin = relationship("Resin", back_populates="resin_params")
    processing_params = relationship("ProcessingParams", back_populates="resin_params", cascade="all, delete-orphan")


class ProcessingParams(Base, AuditMixin):
    __tablename__ = "tbl_extruder_processing_params"
    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(Integer, ForeignKey("tbl_extruder_machines.id"), nullable=False)
    resin_params_id = Column(Integer, ForeignKey("tbl_extruder_resin_params.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("tbl_extruder_zones.id"), nullable=False)
    temp_value = Column(Numeric(10, 2), nullable=False)
    machine = relationship("ExtruderMachine", back_populates="processing_params")
    resin_params = relationship("ResinParams", back_populates="processing_params")
    zone = relationship("Zone", back_populates="processing_params")
    __table_args__ = (
        UniqueConstraint('machine_id', 'resin_params_id', 'zone_id', name='_machine_resin_zone_uc'),
    )