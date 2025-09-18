# app/database/external_models.py

from datetime import datetime
from sqlalchemy import Boolean, String, TIMESTAMP, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
import uuid
from models import Base

class RawMaterials(Base):
    """
    SQLAlchemy model for the 'tbl_raw_materials' table in the external database.
    """
    __tablename__ = 'tbl_raw_materials'
    __table_args__ = {'schema': 'public'}

    # Note the use of UUID from the postgresql dialect
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rm_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    rm_name: Mapped[str | None] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(String(300))
    is_deleted: Mapped[bool | None] = mapped_column(Boolean)


    def __repr__(self) -> str:
        return f"<TblRawMaterials(id={self.id}, rm_code='{self.rm_code}')>"