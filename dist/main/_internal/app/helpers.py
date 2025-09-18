# function for pointing hand cursor
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QPushButton, QWidget
from sqlalchemy import text
from sqlalchemy.orm import Session, DeclarativeMeta
from typing import Type, Dict, Any
from constants.Enums import CategoryEnum

class ButtonCursorError(BaseException):
    pass



# FOR CREATING CURSOR POINTER ON BUTTON
def button_cursor_pointer(button_widget: Type[QPushButton]):
    if isinstance(button_widget, QPushButton):
        button_widget.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
    else:
        raise ButtonCursorError("argument is not a QPushButton instance")


# FOR LOGGING AUTH LOGS
def record_auth_log(
    session: Type[Session],
    data_required: Dict[str, Any],
    auth_log_model: Type[DeclarativeMeta],
    commit=False
) -> None:
    
    log = auth_log_model(**data_required)
    
    session.add(log)

    if commit:
        session.commit()


# FOR ADDING NEW USER
def add_new_user(
    session: Type[Session],
    data_required: Dict[str, Any],
    user_model: Type[DeclarativeMeta],
) -> type[DeclarativeMeta]:
    
    new_user = user_model(**data_required)

    session.add(new_user)
    session.flush() # this makes the user ID available to use (ie new_user.user_id) but doesn't commit

    return new_user


# FOR CREATING THE T_REF_NO on the views
def fetch_current_t_refno_in_endorsement(
    session: Session, 
    endorsement_model: Type[DeclarativeMeta]
) -> str:
    table_name = endorsement_model.__tablename__
    column_name = "t_id" # because the id and reference number will only follow the current id

    # Get the sequence name
    result = session.execute(
        text("SELECT pg_get_serial_sequence(:table, :column) AS seq_name"),
        {"table": table_name, "column": column_name}
    )
    seq_name = result.scalar()

    # Get current value of the sequence (non-incrementing)
    result = session.execute(text(f"SELECT last_value FROM {seq_name}"))
    current_value = result.scalar()

    # Optional: You can also +1 if you want the next expected ID
    return f"EF-{current_value + 1}"



# for opening a file
def load_styles(qss_path, classWidget: Type[QWidget]) -> None:
    try:
        with open(qss_path, "r") as f:
            classWidget.setStyleSheet(f.read())
    except FileNotFoundError:
        print("Warning: Style file not found. Default styles will be used.")


# ------    FOR CREATING THE ENDORSEMENT TABLE 2 and LOT EXCESS ITEMS -------
def parse_lot_range(lot_range: str):
    """Extracts start and end numeric parts from the lot range."""
    start_lot, end_lot = lot_range.split("-")
    start_num, start_suffix = int(start_lot[:4]), start_lot[4:]
    end_num, end_suffix = int(end_lot[:4]), end_lot[4:]

    if start_suffix != end_suffix:
        raise ValueError("Lot suffixes must match.")

    return start_num, end_num, start_suffix

def populate_endorsement_items(
    endorsement_model: Type[DeclarativeMeta],
    endorsement_model_t2: Type[DeclarativeMeta],
    endorsement_lot_excess_model: Type[DeclarativeMeta],
    validated_data,
    category,
    has_excess,
):
    t2_items = []
    # excess_items = []

    validated_lot_number = validated_data.t_lotnumberwhole
    validated_qtykg = validated_data.t_qtykg
    validated_wtlot = validated_data.t_wtlot

    if "-" in validated_lot_number:
        start_num, end_num, suffix = parse_lot_range(validated_lot_number)
        remaining_qty = validated_qtykg

        for number in range(start_num, end_num + 1):
            lot_code = f"{str(number).zfill(4)}{suffix}"

            if has_excess and category == CategoryEnum.MB.value:
                if remaining_qty >= validated_wtlot:
                    t2_items.append(
                        endorsement_model_t2(
                            t_refno=validated_data.t_refno,
                            t_lotnumbersingle=lot_code,
                            t_qty=validated_wtlot
                        )
                    )
                    remaining_qty -= validated_wtlot
                else:
                    if remaining_qty > 0:
                        # Create the T2 item first
                        excess_t2_item = endorsement_model_t2(
                            t_refno=validated_data.t_refno,
                            t_lotnumbersingle=lot_code,
                            t_qty=round(remaining_qty, 2)
                        )
                        
                        # Then create the excess item linked to it
                        excess_item = endorsement_lot_excess_model(
                            tbl_endorsement_t2_ref=excess_t2_item,  # This will set the relationship
                            t_excess_amount=round(remaining_qty, 2)
                        )
                        
                        # Set the relationship
                        excess_t2_item.lot_excess = excess_item
                        
                        t2_items.append(excess_t2_item)
                        remaining_qty = 0
                    break
            else:
                t2_items.append(
                    endorsement_model_t2(
                        t_refno=validated_data.t_refno,
                        t_lotnumbersingle=lot_code,
                        t_qty=validated_wtlot
                    )
                )
    else:
        # Single lot entry
        if has_excess and category == CategoryEnum.MB.value:
            full_lots = int(validated_qtykg // validated_wtlot)
            excess = round(validated_qtykg % validated_wtlot, 2)

            # Add full lots (25kg each)
            for _ in range(full_lots):
                t2_items.append(
                    endorsement_model_t2(
                        t_refno=validated_data.t_refno,
                        t_lotnumbersingle=validated_lot_number,
                        t_qty=validated_wtlot
                    )
                )

            # Add excess as a separate entry if it exists
            if excess > 0:
                # Create the excess T2 item
                excess_t2_item = endorsement_model_t2(
                    t_refno=validated_data.t_refno,
                    t_lotnumbersingle=validated_lot_number,
                    t_qty=excess
                )
                
                # Create and link the excess record
                excess_item = endorsement_lot_excess_model(
                    tbl_endorsement_t2_ref=excess_t2_item,  # This sets the relationship
                    t_excess_amount=excess
                )
                
                # Set the relationship
                excess_t2_item.lot_excess = excess_item
                
                t2_items.append(excess_t2_item)
        else:
            # No excess logic, just add normally
            t2_items.append(
                endorsement_model_t2(
                    t_refno=validated_data.t_refno,
                    t_lotnumbersingle=validated_lot_number,
                    t_qty=validated_qtykg
                )
            )

    # Attach to parent model
    endorsement_model.endorsement_t2_items = t2_items
# ------------------------------------------------------------------------------------------