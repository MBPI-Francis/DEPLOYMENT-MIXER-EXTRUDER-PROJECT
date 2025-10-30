
from sqlalchemy import (
    Column,
    ForeignKey,
    DateTime,
    Boolean,
    Integer
)

from sqlalchemy.orm import relationship, declared_attr
from datetime import datetime, timezone



# --- Reusable Mixin for Audit Columns ---
class AuditMixin:
    """
    A mixin class to add audit-related columns and relationships to a model.
    """
    is_deleted = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc), nullable=True)

    @declared_attr
    def created_by_id(cls):
        return Column(Integer, ForeignKey("users.user_id"), nullable=True)

    @declared_attr
    def updated_by_id(cls):
        return Column(Integer, ForeignKey("users.user_id"), nullable=True)

    @declared_attr
    def deleted_by_id(cls):
        return Column(Integer, ForeignKey("users.user_id"), nullable=True)

    @declared_attr
    def created_by(cls):
        return relationship("User", foreign_keys=[cls.created_by_id], backref=f"created_{cls.__tablename__}")

    @declared_attr
    def updated_by(cls):
        return relationship("User", foreign_keys=[cls.updated_by_id], backref=f"updated_{cls.__tablename__}")

    @declared_attr
    def deleted_by(cls):
        return relationship("User", foreign_keys=[cls.deleted_by_id], backref=f"deleted_{cls.__tablename__}")

