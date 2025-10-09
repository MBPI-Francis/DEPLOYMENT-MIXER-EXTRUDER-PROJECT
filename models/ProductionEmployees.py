from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import relationship

from models import Base
from models.Mixins import AuditMixin


class ProductionEmployee(Base, AuditMixin):
    __tablename__ = "tbl_production_employees"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nickname = Column(String(100))
    first_name = Column(String(255), nullable=False)
    last_name = Column(String(255), nullable=False)

    # Relationship to child table
    extruder_personnels = relationship("ExtruderPersonnel", back_populates="employee")


class EmployeePosition(Base, AuditMixin):
    __tablename__ = "tbl_employee_positions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True, index=True)

    # Relationship to child table
    extruder_personnels = relationship("ExtruderPersonnel", back_populates="position")