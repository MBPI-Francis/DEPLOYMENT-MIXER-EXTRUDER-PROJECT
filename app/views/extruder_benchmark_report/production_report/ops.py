# app/views/extruder_production_report/ops.py

import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime, time

from models.ViewModels import ViewExtruderSummary


def get_production_report_data(session: Session, date_from, date_to):
    query = select(ViewExtruderSummary)

    # FILTER BY PRODUCTION START TIME (As requested)
    start_dt = datetime.combine(date_from, time.min)
    end_dt = datetime.combine(date_to, time.max)
    query = query.where(ViewExtruderSummary.time_start.between(start_dt, end_dt))

    query = query.order_by(ViewExtruderSummary.time_start.desc())

    df = pd.read_sql(query, session.bind)
    if df.empty: return pd.DataFrame()

    # Numeric handling
    cols = ["total_output", "expected_output", "output_per_hour", "duration_hours", "purging_duration_minutes",
            "yield_value"]
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        else:
            df[c] = 0.0

    # Calculations
    df["loss_qty"] = (df["expected_output"] - df["total_output"]).round(2)
    df["loss_percentage"] = df.apply(
        lambda x: (x["loss_qty"] / x["expected_output"] * 100) if x["expected_output"] > 0 else 0.0, axis=1).round(2)

    # Format Purging Range String
    def format_range(row):
        s, e = row.get("purging_start_time"), row.get("purging_end_time")
        if pd.isna(s) or pd.isna(e): return "-"
        return f"{s.strftime('%H:%M')} - {e.strftime('%H:%M')}"

    df["purging_range"] = df.apply(format_range, axis=1)

    # Aliases for View -> UI mapping
    df["output_percentage"] = df["yield_value"].round(2)
    df["duration_hours"] = df["duration_hours"].round(2)
    df["total_output"] = df["total_output"].round(2)
    df["expected_output"] = df["expected_output"].round(2)

    return df