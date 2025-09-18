# models.py
# This file defines the SQLAlchemy ORM models corresponding to the database tables.

from datetime import date, datetime, time

from sqlalchemy import (
    BIGINT,
    Boolean,
    Date,
    Float, # In SQL, DOUBLE PRECISION is represented by Float in SQLAlchemy
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    Time,
    TIMESTAMP,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models import Base


# 2. Define the Model for tbl_mixer_machines
class MixerMachine(Base):
    """SQLAlchemy model for the 'tbl_mixer_machines' table."""
    __tablename__ = "tbl_mixer_machines"

    # Columns
    id: Mapped[int] = mapped_column(Integer, primary_key=True, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    created_by: Mapped[int | None] = mapped_column(Integer)
    modified_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    modified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationship to MixerDetail
    # This creates a 'details' attribute on each MixerMachine instance,
    # which will hold a list of all related MixerDetail objects.
    details: Mapped[list["MixerDetail"]] = relationship(
        "MixerDetail", back_populates="machine"
    )

    def __repr__(self) -> str:
        return f"<MixerMachine(id={self.id}, name='{self.name}')>"

# 3. Define the Model for tbl_mixer_headers
class MixerHeader(Base):
    """SQLAlchemy model for the 'tbl_mixer_headers' table."""
    __tablename__ = "tbl_mixer_headers"

    # Columns
    id: Mapped[int] = mapped_column(Integer, primary_key=True, unique=True, nullable=False)
    reference_no: Mapped[int] = mapped_column(BIGINT, nullable=False)
    date: Mapped[date | None] = mapped_column(Date)
    time_start: Mapped[time | None] = mapped_column(Time)
    time_end: Mapped[time | None] = mapped_column(Time)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    modified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationship to MixerDetail
    # This creates a 'details' attribute on each MixerHeader instance.
    details: Mapped[list["MixerDetail"]] = relationship(
        "MixerDetail", back_populates="header"
    )

    def __repr__(self) -> str:
        return f"<MixerHeader(id={self.id}, reference_no={self.reference_no})>"

# 4. Define the Model for tbl_mixer_details
class MixerDetail(Base):
    """SQLAlchemy model for the 'tbl_mixer_details' table."""
    __tablename__ = "tbl_mixer_details"

    # Columns
    id: Mapped[int] = mapped_column(Integer, primary_key=True, unique=True, nullable=False)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False)
    lot_no: Mapped[str] = mapped_column(String(50), nullable=False)
    lot_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    process_time_start: Mapped[time | None] = mapped_column(Time)
    process_time_end: Mapped[time | None] = mapped_column(Time)
    processed_by: Mapped[str] = mapped_column(String(20), nullable=False)
    output_qty: Mapped[float] = mapped_column(Float, nullable=False)
    cleaning_time_start: Mapped[time] = mapped_column(Time, nullable=True)
    cleaning_time_end: Mapped[time] = mapped_column(Time, nullable=True)
    cleaning_rm_code: Mapped[str] = mapped_column(String(30), nullable=True)
    cleaning_qty: Mapped[float] = mapped_column(Float, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[int | None] = mapped_column(Integer)
    modified_by: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    modified_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Foreign Keys
    mc_id: Mapped[int] = mapped_column(ForeignKey("tbl_mixer_machines.id"), nullable=False)
    mixer_header_id: Mapped[int] = mapped_column(ForeignKey("tbl_mixer_headers.id"), nullable=False)

    # Relationships back to the parent tables
    # This creates 'machine' and 'header' attributes on each MixerDetail instance,
    # allowing easy access to the parent objects.
    machine: Mapped["MixerMachine"] = relationship(
        "MixerMachine", back_populates="details"
    )
    header: Mapped["MixerHeader"] = relationship(
        "MixerHeader", back_populates="details"
    )

    def __repr__(self) -> str:
        return f"<MixerDetail(id={self.id}, product_code='{self.product_code}', lot_no='{self.lot_no}')>"


class TempMixerHeader(Base):
    __tablename__ = "temp_tbl_mixer_headers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    reference_no: Mapped[int | None] = mapped_column(BIGINT)
    date: Mapped[date | None] = mapped_column(Date)
    time_start: Mapped[time | None] = mapped_column(Time)
    time_end: Mapped[time | None] = mapped_column(Time)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)

    # Relationship to TempMixerDetail
    details: Mapped[list["TempMixerDetail"]] = relationship(
        "TempMixerDetail", back_populates="header", cascade="all, delete-orphan"
    )

class TempMixerDetail(Base):
    __tablename__ = "temp_tbl_mixer_details"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    temp_header_id: Mapped[int] = mapped_column(ForeignKey("temp_tbl_mixer_headers.id"), nullable=False)
    mc_id: Mapped[int] = mapped_column(Integer, nullable=False)
    product_code: Mapped[str] = mapped_column(String(50), nullable=False)
    lot_no: Mapped[str] = mapped_column(String(50), nullable=False)
    lot_count: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    process_time_start: Mapped[time | None] = mapped_column(Time)
    process_time_end: Mapped[time | None] = mapped_column(Time)
    processed_by: Mapped[str] = mapped_column(String(20), nullable=False)
    output_qty: Mapped[float] = mapped_column(Float, nullable=False)
    cleaning_time_start: Mapped[time] = mapped_column(Time, nullable=True)
    cleaning_time_end: Mapped[time] = mapped_column(Time, nullable=True)
    cleaning_rm_code: Mapped[str] = mapped_column(String(30), nullable=True)
    cleaning_qty: Mapped[float] = mapped_column(Float, nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, nullable=False)

    # Relationship back to the temp header
    header: Mapped["TempMixerHeader"] = relationship("TempMixerHeader", back_populates="details")