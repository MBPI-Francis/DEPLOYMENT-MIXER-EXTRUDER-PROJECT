# models/ViewModels.py

from sqlalchemy import Column, Integer, String, Numeric, DateTime
from models import Base


class ViewExtruderSummary(Base):
    __tablename__ = 'view_extruder_summary_report'

    # Primary Key
    form_id = Column(Integer, primary_key=True)

    # Identifiers
    reference_number = Column(Integer)
    machine_number = Column(String)
    product_code = Column(String)
    lot_number = Column(String)
    formula_number = Column(String)
    operator = Column(String)

    # Dates
    time_start = Column(DateTime)
    time_end = Column(DateTime)
    created_at = Column(DateTime)

    # Output Metrics
    duration_hours = Column(Numeric)
    output_per_hour = Column(Numeric)
    target_output_per_hour = Column(Numeric)
    total_output = Column(Numeric)
    expected_output = Column(Numeric)  # qty_produced from form

    # Yield (Mapped to yield_value because 'yield' is a Python keyword)
    yield_value = Column(Numeric)

    # Purging / Cleaning
    purging_start_time = Column(DateTime)
    purging_end_time = Column(DateTime)
    purging_duration_minutes = Column(Numeric)
    total_cleaning_material = Column(Numeric)  # New Column
    purging_to_code = Column(String)  # New Column