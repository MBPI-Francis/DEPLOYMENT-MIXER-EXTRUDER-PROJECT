from enum import Enum
from typing import Literal

# IT super password
class ITCredentials(Enum):
    SUPER_PASSWORD = "**itadmin**"

class AuthLogStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

    @staticmethod
    def get_event_type(event: str):
        event_type = {
            "registration": "REGISTRATION",
            "login": "LOGIN"
        }

        return event_type.get(event, None)

# for user table
class UserRole(Enum):
    ADMIN = "ADMIN"
    SUPERVISOR = "SUPERVISOR"
    USER = "USER"
    DISABLED = "DISABLED"

class Department(Enum):
    IT = "IT"
    WAREHOUSE = "WAREHOUSE"
    PRODUCTION = "PRODUCTION"
    LAB = "LAB"


# for endorsement table
class CategoryEnum(Enum):
    MB = "MB"
    DC = "DC"

class MBDefaultValue(Enum):
    """
    This is the default value of the kilo per bag for Masterbatch Category
    """
    KG = 25

class StatusEnum(Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"

class RemarksEnum(Enum):
    NO_REMARKS = "No Remarks"
    OVERSIZED = "OVERSIZED"

class TableHeader():
    LABELS = {
        "endorsement": [
            "Ref No", "Date Endorse", "Category", 
            "Product Code", "Lot Number", 
            "Qty (kg)", "Status", "Endorsed By", "Source Table",
            "Has Excess"
        ]
    }

    @classmethod
    def get_header(
        cls, 
        header_name: Literal[
            "endorsement",
            "deliveryReceipt",
            "outgoingRecord",
            "qcFailedEndorsement",
            "qcFailedToPassed",
            "qcLabExcess",
            "receivingReport",
            "requisitionLogbook",
            "returnReplacement"
        ]
    ):
        if not isinstance(header_name, str):
            raise ValueError("header_name datatype is incorrect.")
        
        if header_name not in cls.LABELS:
            raise ValueError("header_name value is not valid.")

        return cls.LABELS.get(header_name)
