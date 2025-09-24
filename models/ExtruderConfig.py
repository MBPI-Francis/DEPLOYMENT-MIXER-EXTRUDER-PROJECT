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
    UniqueConstraint  # Import UniqueConstraint
)
from sqlalchemy.orm import relationship, declared_attr
from datetime import datetime, timezone

from models import Base
from .Mixins import AuditMixin


# --- Parent Models ---

class Resin(Base, AuditMixin):
    __tablename__ = "tbl_extruder_resins"

    id = Column(SmallInteger, primary_key=True, autoincrement=True)
    # Added unique=True and index=True for data integrity and performance
    name = Column(String(50), nullable=False, unique=True, index=True)

    # Relationship to child table
    resin_params = relationship("ResinParams", back_populates="resin", cascade="all, delete-orphan")


class Zone(Base, AuditMixin):
    __tablename__ = "tbl_extruder_zones"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Added unique=True and index=True
    name = Column(String(50), nullable=False, unique=True, index=True)

    # Relationship to child table
    processing_params = relationship("ProcessingParams", back_populates="zone", cascade="all, delete-orphan")


class ExtruderMachine(Base, AuditMixin):
    __tablename__ = "tbl_extruder_machines"

    id = Column(Integer, primary_key=True, autoincrement=True)
    # Added unique=True and index=True
    name = Column(String(50), nullable=False, unique=True, index=True)

    # Relationship to child table
    processing_params = relationship("ProcessingParams", back_populates="machine", cascade="all, delete-orphan")


# --- Child/Junction Models ---

class ResinParams(Base, AuditMixin):
    __tablename__ = "tbl_extruder_resin_params"

    id = Column(Integer, primary_key=True, autoincrement=True)
    resin_id = Column(SmallInteger, ForeignKey("tbl_extruder_resins.id"), nullable=False)
    motor_rpm = Column(String(50), nullable=False)
    feed_rate = Column(String(50), nullable=False)

    # Relationship to parent tables
    resin = relationship("Resin", back_populates="resin_params")
    # Relationship to child tables
    processing_params = relationship("ProcessingParams", back_populates="resin_params", cascade="all, delete-orphan")


class ProcessingParams(Base, AuditMixin):
    __tablename__ = "tbl_extruder_processing_params"

    id = Column(Integer, primary_key=True, autoincrement=True)
    machine_id = Column(Integer, ForeignKey("tbl_extruder_machines.id"), nullable=False)
    resin_params_id = Column(Integer, ForeignKey("tbl_extruder_resin_params.id"), nullable=False)
    zone_id = Column(Integer, ForeignKey("tbl_extruder_zones.id"), nullable=False)
    temp_value = Column(Numeric(10, 2), nullable=False)

    # Relationship to parent tables
    machine = relationship("ExtruderMachine", back_populates="processing_params")
    resin_params = relationship("ResinParams", back_populates="processing_params")
    zone = relationship("Zone", back_populates="processing_params")

    # Table-level constraints
    __table_args__ = (
        # Ensures that you cannot have two entries for the same machine, resin, and zone combination.
        UniqueConstraint('machine_id', 'resin_params_id', 'zone_id', name='_machine_resin_zone_uc'),
    )