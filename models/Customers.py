from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from models import Base
from models.Mixins import AuditMixin


class Customer(Base, AuditMixin):
    __tablename__ = "tbl_customers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(250), nullable=False, unique=True, index=True)
