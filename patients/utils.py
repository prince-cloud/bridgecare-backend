from datetime import datetime


def generate_patient_id():
    """
    Create a unique patient id based on:
    1. Current time in HHMM format (e.g., 10:14 → 1014, 15:20 → 1520)
    2. Current date in MDDYY format (e.g., 06-12-2025 → 61225, removing leading zero from month)

    Format: HHMM + MDDYY = 4 digits + 5 digits = 9 digits total
    Example: 1014 + 61225 = 101461225
    """
    now = datetime.now()

    # Format time as HHMM (e.g., 10:14 → 1014, 15:20 → 1520)
    time_formatted = now.strftime("%H%M")  # 4 digits

    # Format date as MDDYY (e.g., 06-12-2025 → 61225)
    # Month without leading zero, Day (2 digits), Year last 2 digits
    month = now.month  # Will be 1-12 (no leading zero)
    day = now.strftime("%d")  # 2 digits with leading zero
    year = now.strftime("%y")  # 2 digits
    date_formatted = f"{month}{day}{year}"  # 5 digits (e.g., 61225)

    patient_id = f"{time_formatted}{date_formatted}"

    return patient_id
