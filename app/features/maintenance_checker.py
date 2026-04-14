# app/utils/maintenance_checker.py
from datetime import datetime
from sqlalchemy import text


def check_maintenance_status(session_factory):
    """
    Returns (is_under_maintenance, end_date_string)
    """
    session = session_factory()
    try:
        # Querying the tbl_maintenance table
        query = text("SELECT is_maintenance, start_date, end_date FROM tbl_maintenance LIMIT 1")
        result = session.execute(query).fetchone()

        if result:
            is_active, start_dt, end_dt = result
            now = datetime.now()

            # Check if the manual flag is True AND current time is within the window
            if is_active:
                # If dates are provided, check if we are currently inside the window
                if start_dt and end_dt:
                    if start_dt <= now <= end_dt:
                        return True, end_dt.strftime("%B %d, %Y at %I:%M %p")
                else:
                    # If flag is True but no dates, maintenance is active indefinitely
                    return True, "To be determined"

        return False, None
    except Exception as e:
        print(f"Maintenance Check Error: {e}")
        return False, None
    finally:
        session.close()