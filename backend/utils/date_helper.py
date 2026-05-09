import re
import logging
from datetime import datetime

def parse_date(date_str: str) -> datetime:
    """
    Universal date parser that handles various formats and defaults to current year.
    Returns datetime.min if parsing fails.
    """
    if not date_str or date_str == 'N/A':
        return datetime.min

    if isinstance(date_str, datetime):
        return date_str.replace(hour=0, minute=0, second=0, microsecond=0)

    date_str = str(date_str).strip()
    current_year = datetime.now().year

    # 1. ISO/Full datetime (YYYY-MM-DD)
    if re.match(r'\d{4}-\d{2}-\d{2}', date_str):
        try:
            return datetime.strptime(date_str.split()[0], "%Y-%m-%d")
        except: pass

    # 2. DD-MMM-YY or DD-MMM-YYYY (e.g., 20-Sep-25)
    match = re.search(r'(\d{1,2})[-/\s]([A-Za-z]{3})[-/\s]?(\d{0,4})', date_str, re.IGNORECASE)
    if match:
        day, month_name, year_suffix = match.groups()
        if not year_suffix or len(year_suffix) < 2:
            year = str(current_year)
        elif len(year_suffix) == 2:
            year = f"20{year_suffix}"
        else:
            year = year_suffix
        try:
            return datetime.strptime(f"{day}-{month_name}-{year}", "%d-%b-%Y")
        except: pass

    # 3. Numeric DD-MM-YY or DD/MM/YY
    match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{2,4})', date_str)
    if match:
        d1, d2, year_suffix = match.groups()
        # Intelligent detection: if d1 > 12, it's likely DD-MM
        if int(d1) > 12:
            day, month = d1, d2
        elif int(d2) > 12:
            day, month = d2, d1
        else:
            day, month = d1, d2 # Default to DD-MM (Indian standard)
        
        if len(year_suffix) == 2:
            year = f"20{year_suffix}"
        else:
            year = year_suffix
        try:
            return datetime(int(year), int(month), int(day))
        except: pass

    # 4. DD-MMM (Missing Year)
    match = re.search(r'(\d{1,2})[-/\s]([A-Za-z]{3})$', date_str, re.IGNORECASE)
    if match:
        day, month_name = match.groups()
        try:
            return datetime.strptime(f"{day}-{month_name}-{current_year}", "%d-%b-%Y")
        except: pass

    return datetime.min

def normalize_date_key(date_str: str) -> str:
    """Normalize date to DD-MMM-YY format for consistent database keys"""
    dt = parse_date(date_str)
    if dt != datetime.min:
        return dt.strftime("%d-%b-%y")
    return str(date_str)
