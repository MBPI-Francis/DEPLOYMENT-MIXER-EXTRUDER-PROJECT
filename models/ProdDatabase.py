# models/ProdDatabase.py

from datetime import date
from decimal import Decimal
from typing import List
from sqlalchemy import (
    Boolean,
    Date,
    Integer,
    Numeric,
    String,
    ForeignKey,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from models import Base
class TblProd01(Base):
    """
    SQLAlchemy model for the 'tbl_prod01' table.
    """
    __tablename__ = 'tbl_prod01'
    __table_args__ = {'schema': 'public'}

    # New: Auto-incrementing primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    # Column definitions from your DBF
    T_PRODID: Mapped[Decimal] = mapped_column(Numeric)
    T_PRODDATE: Mapped[date | None] = mapped_column(Date)
    T_CUSTOMER: Mapped[str | None] = mapped_column(String(255))
    T_FID: Mapped[int | None] = mapped_column(Integer)
    T_INDEX: Mapped[str | None] = mapped_column(String(255))
    T_PRODCODE: Mapped[str | None] = mapped_column(String(255))
    T_PRODCOLO: Mapped[str | None] = mapped_column(String(255))
    T_DOSAGE: Mapped[Decimal | None] = mapped_column(Numeric)
    T_LD: Mapped[Decimal | None] = mapped_column(Numeric)
    T_LOTNUM: Mapped[str | None] = mapped_column(String(255))
    T_ORDERNUM: Mapped[str | None] = mapped_column(String(255))
    T_CMNUM: Mapped[str | None] = mapped_column(String(255))
    T_CMDATE: Mapped[date | None] = mapped_column(Date)
    T_MIXTIME: Mapped[str | None] = mapped_column(String(255))
    T_MACHINE: Mapped[str | None] = mapped_column(String(255))
    T_QTYREQ: Mapped[Decimal | None] = mapped_column(Numeric)
    T_QTYBATCH: Mapped[Decimal | None] = mapped_column(Numeric)
    T_QTYPROD: Mapped[Decimal | None] = mapped_column(Numeric)
    T_REMARKS: Mapped[str | None] = mapped_column(String(255))
    T_NOTE: Mapped[str | None] = mapped_column(String(255))
    T_USERID: Mapped[str | None] = mapped_column(String(255))
    T_PREPARED: Mapped[str | None] = mapped_column(String(255))
    T_ENCODEDB: Mapped[str | None] = mapped_column(String(255))
    T_ENCODEDO: Mapped[str | None] = mapped_column(String(255))
    T_DELETED: Mapped[bool | None] = mapped_column(Boolean)
    T_JDONE: Mapped[str | None] = mapped_column(String(255))
    T_CDATE: Mapped[date | None] = mapped_column(Date)
    T_SDATE: Mapped[str | None] = mapped_column(String(255))
    T_FTYPE: Mapped[str | None] = mapped_column(String(255))

    def __repr__(self) -> str:
        return f"<TblProd01(T_PRODID={self.T_PRODID}, T_PRODCODE='{self.T_PRODCODE}')>"


class TblFormula01(Base):
    """
    SQLAlchemy model for the 'tbl_formula01' table using modern syntax.
    """
    __tablename__ = 'tbl_formula01'
    __table_args__ = {'schema': 'public'}

    # New: Auto-incrementing primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    
    # Existing T_UID is now a regular column, no longer the primary key
    T_UID: Mapped[int] = mapped_column(Integer)
    T_INDEX: Mapped[str | None] = mapped_column(String(255))
    T_DATE: Mapped[date | None] = mapped_column(Date)
    T_CUSTOMER: Mapped[str | None] = mapped_column(String(255))
    T_PRODCODE: Mapped[str | None] = mapped_column(String(255))
    T_PRODCOLO: Mapped[str | None] = mapped_column(String(255))
    T_DOSAGE: Mapped[Decimal | None] = mapped_column(Numeric)
    T_LD: Mapped[Decimal | None] = mapped_column(Numeric)
    T_MIX: Mapped[str | None] = mapped_column(String(255))
    T_RESIN: Mapped[str | None] = mapped_column(String(255))
    T_APP: Mapped[str | None] = mapped_column(String(255))
    T_CMNUM: Mapped[str | None] = mapped_column(String(255))
    T_CMDATE: Mapped[date | None] = mapped_column(Date)
    T_MATCHBY: Mapped[str | None] = mapped_column(String(255))
    T_ENCODEDB: Mapped[str | None] = mapped_column(String(255))
    T_REM: Mapped[str | None] = mapped_column(String(255))
    T_TOTALCON: Mapped[Decimal | None] = mapped_column(Numeric)
    T_USER: Mapped[str | None] = mapped_column(String(255))
    T_DELETED: Mapped[bool | None] = mapped_column(Boolean)
    T_USED: Mapped[bool | None] = mapped_column(Boolean)
    T_UPDATEBY: Mapped[str | None] = mapped_column(String(255))
    T_UDATE: Mapped[str | None] = mapped_column(String(255))
    
    details: Mapped[List["TblFormula02"]] = relationship(
        back_populates="formula_header",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TblFormula01(T_UID={self.T_UID}, T_PRODCODE='{self.T_PRODCODE}')>"


class TblFormula02(Base):
    """
    SQLAlchemy model for the 'tbl_formula02' table, representing
    the details (materials) of a formula.
    """
    __tablename__ = 'tbl_formula02'
    __table_args__ = {'schema': 'public'}

    # New: Auto-incrementing primary key
    id: Mapped[int] = mapped_column(primary_key=True)

    formula_header_id: Mapped[int] = mapped_column(ForeignKey("public.tbl_formula01.id"))

    # Composite Primary Key (T_UID, T_SEQ) is now a unique constraint
    T_UID: Mapped[int] = mapped_column(Integer)
    T_SEQ: Mapped[int] = mapped_column(Integer)
    
    T_MATCODE: Mapped[str | None] = mapped_column(String(255))
    T_CON: Mapped[Decimal | None] = mapped_column(Numeric)
    T_DELETED: Mapped[bool | None] = mapped_column(Boolean)
    T_UPDATEBY: Mapped[str | None] = mapped_column(String(255))
    T_UDATE: Mapped[str | None] = mapped_column(String(255))
    
    formula_header: Mapped["TblFormula01"] = relationship(back_populates="details")


    def __repr__(self) -> str:
        return f"<TblFormula02(T_UID={self.T_UID}, T_SEQ={self.T_SEQ}, T_MATCODE='{self.T_MATCODE}')>"