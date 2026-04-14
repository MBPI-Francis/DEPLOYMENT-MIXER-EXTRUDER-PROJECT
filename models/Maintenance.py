from sqlalchemy import Column, Integer, Boolean, DateTime

from models import Base

class Maintenance(Base):
    __tablename__ = 'tbl_maintenance'
    id = Column(Integer, primary_key=True)
    is_maintenance = Column(Boolean, default=False)
    start_date = Column(DateTime)
    end_date = Column(DateTime)