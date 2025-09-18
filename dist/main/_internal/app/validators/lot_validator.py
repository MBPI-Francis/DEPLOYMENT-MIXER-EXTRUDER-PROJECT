# app/validators/lot_validator.py

import re
from typing import List, Tuple, Optional, Set


class LotNumberValidator:
    """
    A sophisticated validator to check if a user's lot number entry
    is fully covered by a list of existing lot number records,
    which can themselves be single entries or ranges.
    """

    def __init__(self, existing_lot_records: List[str]):
        """
        Initializes the validator with the full list of lot number strings
        from the database for a specific product.

        Args:
            existing_lot_records: A list of strings, e.g., ["9001AM", "9005AM-9010AM"].
        """
        self._valid_lot_pool = self._build_valid_lot_pool(existing_lot_records)

    def _parse_lot_string(self, lot_str: str) -> Optional[Tuple[int, int, str]]:
        """
        Parses a lot string into its constituent parts: start number, end number, and suffix.
        Handles both single lots ("9004AM") and ranges ("9001AM-9003AM").

        THIS IS THE CORRECTED, MORE ROBUST LOGIC.
        """
        lot_str = lot_str.strip().upper()

        # Regex to capture the number and suffix from a single lot part.
        part_regex = re.compile(r'^(\d+)([A-Z]+)$')

        if '-' in lot_str:
            # Handle a potential range
            parts = lot_str.split('-')
            if len(parts) != 2:
                return None  # Invalid format, more than one hyphen

            start_part, end_part = parts

            start_match = part_regex.match(start_part)
            end_match = part_regex.match(end_part)

            if not start_match or not end_match:
                return None  # One or both parts of the range are malformed

            start_num, start_suffix = int(start_match.group(1)), start_match.group(2)
            end_num, end_suffix = int(end_match.group(1)), end_match.group(2)

            if start_suffix != end_suffix:
                return None  # Suffixes in the range must match, e.g., "9001AM-9005PM" is invalid

            if end_num < start_num:
                return None  # End of range cannot be smaller than the start

            return start_num, end_num, start_suffix

        else:
            # Handle a single lot number
            match = part_regex.match(lot_str)
            if not match:
                return None  # Does not match the required "digits + letters" format

            num, suffix = int(match.group(1)), match.group(2)
            return num, num, suffix  # Start and end numbers are the same for a single lot

    def _build_valid_lot_pool(self, records: List[str]) -> Set[str]:
        """
        Expands all database records into a set of individual, valid lot numbers.
        Example: ["9001AM-9003AM"] becomes {"9001AM", "9002AM", "9003AM"}.
        """
        pool = set()
        for record in records:
            parsed = self._parse_lot_string(record)
            if parsed:
                start, end, suffix = parsed
                for i in range(start, end + 1):
                    pool.add(f"{i}{suffix}")
        return pool

    def validate_lot_entry(self, user_input: str, product_code: str) -> Tuple[bool, str]:
        """
        Validates the user's input string, which can contain single lots, ranges,
        or multiple entries separated by semicolons, against the pre-built pool of valid lots.

        Args:
            user_input: The lot number(s) entered by the user (e.g., "1001AM", "1005AM-1007AM", or "1005AM-1007AM; 1109AB-1115AB").
            product_code: The product code being validated against, used for error messages.

        Returns:
            A tuple (is_valid, message).
        """
        user_input = user_input.strip()
        if not user_input:
            # This case is typically handled by the UI, but included for robustness.
            return False, "Lot Number cannot be empty."

        # Split the input by semicolons to handle multiple entries and remove empty parts.
        lot_entries = [entry.strip() for entry in user_input.split(';') if entry.strip()]

        all_required_lots = set()

        # First, parse all entries to check for format errors and gather all required lots.
        for entry in lot_entries:
            parsed_input = self._parse_lot_string(entry)
            if not parsed_input:
                return False, f"Lot Number part '{entry}' has an invalid format. Expected format is '1234AM' or '1234AM-5678AM'."

            start, end, suffix = parsed_input
            for i in range(start, end + 1):
                all_required_lots.add(f"{i}{suffix}")

        # Find which of the required lots are not in the valid pool.
        missing_lots = sorted(list(all_required_lots - self._valid_lot_pool))

        if not missing_lots:
            return True, "OK"
        else:
            # Generate a specific error message listing all missing lots.
            missing_lots_str = ', '.join(missing_lots)
            error_msg = f"Lot Number(s) '{missing_lots_str}' do not exist for the specified Product Code '{product_code}'."
            return False, error_msg