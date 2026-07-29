import re
from datetime import datetime
from typing import  Optional

def parse_datetime(raw_str: Optional[str]) -> Optional[datetime]:
    """
    Extracts and parses datetime objects from Vietnamese news date strings.
    Handles inputs like:
      - "Thứ 2, 06/07/2026, 00:00"
      - "Thứ Bảy, 11/07/2026 - 08:30"
      - "16-07-2026 - 00:01 AM"
      - "06/07/2026 00:00"
      - "06/07/2026"
    """
    if not raw_str:
        return None

    # Regex matches DD/MM/YYYY or DD-MM-YYYY, plus optional HH:MM (with optional AM/PM)
    pattern = r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})(?:[,\s\-]+(\d{1,2}:\d{2}(?:\s*[AP]M)?))?'
    match = re.search(pattern, raw_str, re.IGNORECASE)

    if not match:
        return None

    date_part, time_part = match.groups()
    normalized_date = date_part.replace("-", "/")

    if time_part:
        clean_time = time_part.strip().upper()
        full_str = f"{normalized_date} {clean_time}"

        # 1. Try 12-hour format with AM/PM (e.g., "16/07/2026 00:01 AM")
        try:
            return datetime.strptime(full_str, "%d/%m/%Y %I:%M %p")
        except ValueError:
            pass

        # 2. Try 24-hour format (e.g., "06/07/2026 00:00")
        try:
            return datetime.strptime(full_str, "%d/%m/%Y %H:%M")
        except ValueError:
            pass

    # Fallback to date only
    try:
        return datetime.strptime(normalized_date, "%d/%m/%Y")
    except ValueError:
        return None
    